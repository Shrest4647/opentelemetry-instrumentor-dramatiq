from typing import Collection
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry import trace, metrics, context

from opentelemetry.trace import SpanKind, Tracer, StatusCode
from opentelemetry.propagate import inject, extract
import logging
import dramatiq
import functools
from .package import _instruments
from .version import __version__
from dramatiq.actor import Actor

logger = logging.getLogger(__name__)


class DramatiqInstrumentor(BaseInstrumentor):
    """An instrumentor for Dramatiq
    See `BaseInstrumentor`
    """

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Instruments the dramatiq actors and workers"""

        tracer_provider = kwargs.get("tracer_provider")
        tracer_p = trace.get_tracer_provider()
        tracer = trace.get_tracer(
            __name__,
            __version__,
            tracer_provider=tracer_provider or tracer_p,
            schema_url="https://opentelemetry.io/schemas/1.11.0",
        )
        meter_provider = kwargs.get("meter_provider")
        meter = metrics.get_meter(
            __name__,
            __version__,
            meter_provider,
        )
        self.create_dramatiq_metrics(meter)

        _instrument(
            tracer,
            request_hook=kwargs.get("request_hook"),
        )

    def _uninstrument(self, **kwargs):
        """
        Disables instrumentation of the dramatiq library.
        """
        func_message_with_options = getattr(dramatiq.Actor, "message_with_options")
        func_process_message = getattr(dramatiq.worker._WorkerThread, "process_message")

        if hasattr(func_message_with_options, "__wrapped__"):
            setattr(
                dramatiq.Actor,
                "message_with_options",
                func_message_with_options.__wrapped__,
            )
        if hasattr(func_process_message, "__wrapped__"):
            setattr(
                dramatiq.worker._WorkerThread,
                "process_message",
                func_process_message.__wrapped__,
            )

    def create_dramatiq_metrics(self, meter):
        pass


def _instrument(tracer: Tracer, request_hook=None):
    """Instruments the given tracer with the given request hook.
    Args:
        tracer: The tracer to instrument.
        request_hook: An optional callback which is invoked right before the span is finished processing a response.
    """

    original_message_with_options = Actor.message_with_options
    original_process_message = dramatiq.worker._WorkerThread.process_message  # noqa

    @functools.wraps(original_message_with_options)
    def instrumented_message_with_options(self, *, args=(), kwargs=None, **options):
        """Wraps the original message_with_options method to start a span for the message."""
        span_name = f"dramatiq.producer.{self.actor_name}"
        span_attributes = {}
        with tracer.start_as_current_span(
            span_name,
            kind=SpanKind.SERVER,
            attributes=span_attributes,
        ) as span:
            span.set_attribute("actor_name", self.actor_name)
            span.set_attribute("queue_name", self.queue_name)
            if callable(request_hook):
                request_hook(span)

            context_carrier = {}
            inject(context_carrier)

            logger.debug("Injecting trace context", context_carrier)
            try:
                result = original_message_with_options(
                    self,
                    args=args,
                    kwargs=kwargs,
                    options={
                        **options,
                        "trace_context": context_carrier,
                    },
                )
            except Exception as e:
                span.set_status(StatusCode.UNSET)
                span.record_exception(e)
                raise e
            else:
                span.set_attribute("message_id", result.message_id)
                span.set_status(StatusCode.OK)
                logger.debug("Finished processing message", result.asdict())
                return result

    @functools.wraps(original_process_message)
    def instrumented_process_message(self, message):
        """
        Wraps the process_message method of the _WorkerThread class to create a span for each message.
        Args:
            message: The message to process.
        """
        span_name = f"dramatiq.worker.WorkerThread"
        options = message.options.get("options")
        trace_context = options.get("trace_context") if options else None
        logger.debug("Trace context", trace_context)

        if trace_context:
            trace_context = extract(trace_context) or None
            token = context.attach(trace_context) if trace_context else None

        with tracer.start_span(
            span_name,
            kind=SpanKind.CONSUMER,
            context=trace_context,
        ) as span:
            span.set_attribute("message_id", message.message_id)
            span.set_attribute("actor_name", message.actor_name)
            try:
                result = original_process_message(self, message)
            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                raise e
            else:
                span.set_status(StatusCode.OK)
                return result

    dramatiq.Actor.message_with_options = instrumented_message_with_options
    dramatiq.worker._WorkerThread.process_message = instrumented_process_message

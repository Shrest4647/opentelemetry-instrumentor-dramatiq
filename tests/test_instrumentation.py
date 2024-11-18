import dramatiq
import pytest

from opentelemetry import trace
from opentelemetry_instrumentor_dramatiq import DramatiqInstrumentor


@pytest.fixture
def tracer():
    """Fixture to provide a fresh instance of the tracer."""
    return trace.get_tracer(__name__)


@pytest.fixture
def instrumentor():
    """Fixture to provide a fresh instance of the instrumentor."""
    return DramatiqInstrumentor().instrument()


def test_messages_have_namedtuple_methods(broker, instrumentor):
    @dramatiq.actor
    def add(x, y):
        return x + y

    msg1 = add.message(1, 2)
    assert msg1.asdict() == msg1._asdict()

    assert msg1._field_defaults == {}
    assert msg1._fields == (
        "queue_name",
        "actor_name",
        "args",
        "kwargs",
        "options",
        "message_id",
        "message_timestamp",
    )
    assert "trace_context" in msg1.options["options"]

    msg2 = msg1._replace(queue_name="example")
    assert msg2._asdict()["queue_name"] == "example"

# opentelemetry-instrumentor-dramatiq

Opentelemetry traces instrumentation for Dramatiq (An async processing library for python)

## Installation

```bash
pip install opentelemetry-instrumentor-dramatiq
```

## Usage

```python
import dramatiq
from opentelemetry import trace
from opentelemetry_instrumentor_dramatiq import DramatiqInstrumentor

tracer = trace.get_tracer(__name__)

# Instrument the dramatiq library at the start of your application
DramatiqInstrumentor().instrument()

@dramatiq.actor(queue_name="default")
@tracer.start_as_current_span("my_actor")  # trace the actor
def my_actor(message):
    print(message)

my_actor.send("Hello, world!")

```

## Contributing

Contributions are welcome!

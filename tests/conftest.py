import dramatiq
import pytest
from dramatiq.brokers.stub import StubBroker

from dramatiq import Worker


@pytest.fixture(scope="session")
def broker():
    """Fixture to provide a fresh instance of the broker."""
    broker = StubBroker()
    broker.flush_all()
    broker.emit_after("process_boot")
    return broker


@pytest.fixture()
def stub_worker(broker):
    worker = Worker(broker, worker_timeout=100)
    worker.start()
    yield worker
    worker.stop()

from mail_control.modules.system.health import DependencyStatus
from mail_control.operational_health import is_healthy


def test_dependencies_without_queue_are_healthy() -> None:
    status = DependencyStatus(database=True, redis=True, rabbitmq=True)
    assert is_healthy(status, queue_required=False, consumer_count=0)


def test_required_queue_needs_a_consumer() -> None:
    status = DependencyStatus(database=True, redis=True, rabbitmq=True)
    assert not is_healthy(status, queue_required=True, consumer_count=0)
    assert is_healthy(status, queue_required=True, consumer_count=1)


def test_failed_dependency_is_unhealthy() -> None:
    status = DependencyStatus(database=True, redis=False, rabbitmq=True)
    assert not is_healthy(status, queue_required=False, consumer_count=0)

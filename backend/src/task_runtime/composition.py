"""Explicit composition root seam for task definitions shared by API and Worker."""

from task_runtime.outbox import EventTransport
from task_runtime.registry import TaskRegistry

_application_task_registry = TaskRegistry()
_application_event_transport: EventTransport | None = None


def get_application_task_registry() -> TaskRegistry:
    return _application_task_registry


def configure_application_event_transport(
    transport: EventTransport | None,
) -> None:
    global _application_event_transport
    _application_event_transport = transport


def get_application_event_transport() -> EventTransport | None:
    return _application_event_transport


__all__ = [
    "configure_application_event_transport",
    "get_application_event_transport",
    "get_application_task_registry",
]

"""Port marker for request-scoped asynchronous persistence adapters."""

from __future__ import annotations

from typing import Protocol

from configuration_governance.contracts import ConfigLifecycleBackend


class AsyncConfigLifecyclePersistence(ConfigLifecycleBackend, Protocol):
    """Structural contract implemented by the delivery layer's SQLAlchemy adapter."""

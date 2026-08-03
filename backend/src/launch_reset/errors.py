"""Explicit failure types for the destructive reset boundary."""


class ResetSafetyError(RuntimeError):
    """The requested target or scope is not safe enough to execute."""


class ResetExecutionError(RuntimeError):
    """A reset stage failed after the request passed safety validation."""


__all__ = ["ResetExecutionError", "ResetSafetyError"]

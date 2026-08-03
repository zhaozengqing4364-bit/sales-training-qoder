"""Typed task-runtime failures with stable machine codes."""

from __future__ import annotations

from enum import StrEnum


class TaskRuntimeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


class TaskTypeNotRegisteredError(TaskRuntimeError):
    def __init__(self, task_type: str) -> None:
        super().__init__(
            "[TASK_TYPE_NOT_REGISTERED]",
            f"任务类型未注册，无法处理：{task_type}",
        )


class TaskSchemaInvalidError(TaskRuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__("[TASK_SCHEMA_INVALID]", message)


class IdempotencyKeyReusedError(TaskRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "[IDEMPOTENCY_KEY_REUSED]",
            "该幂等键已用于不同请求，请使用新的幂等键后重试。",
        )


class TaskNotFoundError(TaskRuntimeError):
    def __init__(self) -> None:
        super().__init__("[TASK_NOT_FOUND]", "未找到可访问的任务。")


class TaskAccessDeniedError(TaskRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "[TASK_ACCESS_DENIED]",
            "当前账户没有所需的任务访问范围。",
        )


class TaskTransitionError(TaskRuntimeError):
    def __init__(self, source: str, target: str) -> None:
        super().__init__(
            "[TASK_STATE_TRANSITION_INVALID]",
            f"任务当前状态不支持该操作（{source} → {target}）。",
        )


class TaskLeaseLostError(TaskRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "[TASK_LEASE_LOST]",
            "任务执行权已失效，本次结果未被保存。",
        )


class TaskInfrastructureError(TaskRuntimeError):
    """Internal signal that the worker could not durably record an outcome."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(
            "[TASK_INFRASTRUCTURE_UNAVAILABLE]",
            f"任务运行时基础设施暂时不可用，未能持久化操作：{operation}",
        )


class TaskFailureKind(StrEnum):
    PROVIDER_TEMPORARY = "provider_temporary"
    INVALID_INPUT = "invalid_input"
    PERMISSION_DENIED = "permission_denied"
    BUSINESS_CONFLICT = "business_conflict"
    SYSTEM_DEFECT = "system_defect"
    TIMEOUT = "timeout"


class TaskExecutionError(Exception):
    """A classified handler failure; provider details must stay out of message."""

    def __init__(self, *, code: str, message: str, kind: TaskFailureKind) -> None:
        self.code = code
        self.message = message
        self.kind = kind
        super().__init__(f"{code}: {message}")


class TaskCancellationRequested(Exception):
    """Internal control flow raised only at an explicit safe checkpoint."""


class TaskHandlerMissingError(TaskRuntimeError):
    def __init__(self, task_type: str) -> None:
        super().__init__(
            "[TASK_HANDLER_MISSING]",
            f"任务类型缺少可执行处理器：{task_type}",
        )


class OutboxLeaseLostError(TaskRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "[OUTBOX_LEASE_LOST]",
            "事件投递权已失效，本次投递结果未被保存。",
        )


class OutboxEventConflictError(TaskRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "[OUTBOX_EVENT_CONFLICT]",
            "同一业务事件标识对应了不同内容，请更换幂等键后重试。",
        )


class TaskQueryInvalidError(TaskRuntimeError):
    def __init__(self, message: str = "任务查询游标无效，请重新加载列表。") -> None:
        super().__init__("[TASK_QUERY_INVALID]", message)

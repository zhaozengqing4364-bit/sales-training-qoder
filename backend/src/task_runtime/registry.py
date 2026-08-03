"""Explicit task type registry; dynamic handler imports are forbidden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from task_runtime.contracts import TaskPolicy
from task_runtime.errors import (
    TaskRuntimeError,
    TaskSchemaInvalidError,
    TaskTypeNotRegisteredError,
)
from task_runtime.payload_guard import assert_safe_persisted_payload


class TaskHandler(Protocol):
    async def execute(self, context: Any, payload: BaseModel) -> Any: ...


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    task_type: str
    schema_version: int
    input_model: type[BaseModel]
    result_model: type[BaseModel]
    policy: TaskPolicy
    handler: TaskHandler | None = None
    metric_tags: tuple[tuple[str, str], ...] = ()
    allowed_data_classifications: frozenset[str] = frozenset({"internal"})
    max_payload_bytes: int = 32_768


class TaskRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], TaskDefinition] = {}

    def register(self, definition: TaskDefinition) -> None:
        if not definition.allowed_data_classifications:
            raise ValueError("任务类型必须声明至少一个允许的数据分类。")
        if definition.max_payload_bytes < 1:
            raise ValueError("任务 payload 大小上限必须为正数。")
        if definition.handler is not None and not callable(
            getattr(definition.handler, "execute", None)
        ):
            raise TypeError("Task handler must be an explicit object with execute().")
        key = (definition.task_type, definition.schema_version)
        current = self._definitions.get(key)
        if current is not None and self._logical_signature(
            current
        ) != self._logical_signature(definition):
            raise ValueError(
                f"Task type already registered with another definition: "
                f"{definition.task_type}"
            )
        if current is None:
            self._definitions[key] = definition

    def resolve(self, task_type: str, schema_version: int) -> TaskDefinition:
        try:
            return self._definitions[(task_type, schema_version)]
        except KeyError as exc:
            raise TaskTypeNotRegisteredError(f"{task_type}@{schema_version}") from exc

    def has_task_type(self, task_type: str) -> bool:
        return any(
            registered_type == task_type for registered_type, _ in self._definitions
        )

    def definitions_for_type(self, task_type: str) -> tuple[TaskDefinition, ...]:
        definitions = tuple(
            definition
            for (registered_type, _), definition in self._definitions.items()
            if registered_type == task_type
        )
        if not definitions:
            raise TaskTypeNotRegisteredError(task_type)
        return tuple(sorted(definitions, key=lambda item: item.schema_version))

    def registered_keys(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(self._definitions))

    def validate_input(
        self,
        *,
        task_type: str,
        schema_version: int,
        payload: dict[str, Any],
        data_classification: str = "internal",
    ) -> dict[str, Any]:
        definition = self.resolve(task_type, schema_version)
        if data_classification not in definition.allowed_data_classifications:
            raise TaskRuntimeError(
                "[TASK_DATA_CLASSIFICATION_DENIED]",
                "该任务类型不允许持久化此数据分类。",
            )
        try:
            validated = definition.input_model.model_validate(payload)
        except ValidationError as exc:
            raise TaskSchemaInvalidError("任务输入不符合已注册的数据结构。") from exc
        persisted = validated.model_dump(mode="json", exclude_none=True)
        assert_safe_persisted_payload(
            persisted,
            max_bytes=definition.max_payload_bytes,
            code_prefix="TASK_PAYLOAD",
            subject_label="任务输入",
        )
        return persisted

    def parse_input(
        self,
        *,
        task_type: str,
        schema_version: int,
        payload: dict[str, Any],
    ) -> BaseModel:
        definition = self.resolve(task_type, schema_version)
        try:
            return definition.input_model.model_validate(payload)
        except ValidationError as exc:
            raise TaskSchemaInvalidError("任务输入不符合已注册的数据结构。") from exc

    def validate_result(
        self,
        *,
        task_type: str,
        schema_version: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        definition = self.resolve(task_type, schema_version)
        try:
            validated = definition.result_model.model_validate(payload)
        except ValidationError as exc:
            raise TaskSchemaInvalidError("任务结果不符合已注册的数据结构。") from exc
        return validated.model_dump(mode="json")

    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted({task_type for task_type, _ in self._definitions}))

    @staticmethod
    def _logical_signature(definition: TaskDefinition) -> tuple[Any, ...]:
        return (
            definition.task_type,
            definition.schema_version,
            definition.input_model,
            definition.result_model,
            definition.policy,
            type(definition.handler) if definition.handler is not None else None,
            definition.metric_tags,
            definition.allowed_data_classifications,
            definition.max_payload_bytes,
        )

"""Versioned structured input/output schema registry."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from ai_platform.contracts import AIErrorClassification
from ai_platform.errors import AIPlatformError


class OutputSchemaRegistry:
    def __init__(self) -> None:
        self._inputs: dict[str, type[BaseModel]] = {}
        self._outputs: dict[str, type[BaseModel]] = {}

    def register_input(self, version: str, schema: type[BaseModel]) -> None:
        self._register(self._inputs, version=version, schema=schema)

    def register_output(self, version: str, schema: type[BaseModel]) -> None:
        self._register(self._outputs, version=version, schema=schema)

    @staticmethod
    def _register(
        registry: dict[str, type[BaseModel]],
        *,
        version: str,
        schema: type[BaseModel],
    ) -> None:
        current = registry.get(version)
        if current is not None and current is not schema:
            raise ValueError(
                f"AI schema version already registered with another model: {version}"
            )
        if current is None:
            registry[version] = schema

    def validate_input(self, version: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._validate(
            registry=self._inputs,
            version=version,
            payload=payload,
            classification=AIErrorClassification.INPUT_SCHEMA_INVALID,
            code="AI_INPUT_SCHEMA_INVALID",
            message="AI 输入不符合已发布的数据契约。",
        )

    def validate_output(self, version: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._validate(
            registry=self._outputs,
            version=version,
            payload=payload,
            classification=AIErrorClassification.OUTPUT_SCHEMA_INVALID,
            code="AI_OUTPUT_SCHEMA_INVALID",
            message="模型输出不符合已发布的数据契约。",
        )

    @staticmethod
    def _validate(
        *,
        registry: dict[str, type[BaseModel]],
        version: str,
        payload: dict[str, Any],
        classification: AIErrorClassification,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        schema = registry.get(version)
        if schema is None:
            raise AIPlatformError(
                code=code,
                classification=classification,
                message=f"{message} 未注册版本：{version}",
            )
        try:
            return schema.model_validate(payload).model_dump(mode="json")
        except ValidationError as exc:
            raise AIPlatformError(
                code=code,
                classification=classification,
                message=message,
            ) from exc

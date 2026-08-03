from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from task_runtime.contracts import TaskPolicy
from task_runtime.registry import TaskDefinition, TaskRegistry


class InputModel(BaseModel):
    value: str


class ResultModel(BaseModel):
    value: str


class ReferenceOnlyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str | None = None
    prompt: str | None = None
    value: str | None = None
    full_transcript: str | None = None
    customer_audio_base64: str | None = None
    provider_raw_response: str | None = None
    audio_artifact_id: str | None = None
    transcript_artifact_ref: str | None = None


class Handler:
    async def execute(self, context, payload):
        raise NotImplementedError


class OtherHandler:
    async def execute(self, context, payload):
        raise NotImplementedError


def definition(
    *,
    schema_version: int = 1,
    handler=Handler(),
    policy: TaskPolicy | None = None,
):
    return TaskDefinition(
        task_type="test.registry",
        schema_version=schema_version,
        input_model=InputModel,
        result_model=ResultModel,
        policy=policy or TaskPolicy(),
        handler=handler,
    )


def test_logically_equal_registration_is_idempotent_but_drift_fails_closed() -> None:
    registry = TaskRegistry()
    registry.register(definition(handler=Handler()))
    registry.register(definition(handler=Handler()))

    with pytest.raises(ValueError):
        registry.register(definition(handler=OtherHandler()))
    with pytest.raises(ValueError):
        registry.register(definition(policy=TaskPolicy(max_attempts=9)))


def test_multiple_schema_versions_coexist_and_resolve_exactly() -> None:
    registry = TaskRegistry()
    first = definition(schema_version=1, handler=Handler())
    second = definition(schema_version=2, handler=OtherHandler())

    registry.register(first)
    registry.register(second)

    assert registry.resolve("test.registry", 1) is first
    assert registry.resolve("test.registry", 2) is second
    assert registry.registered_keys() == (
        ("test.registry", 1),
        ("test.registry", 2),
    )
    assert registry.registered_types() == ("test.registry",)


def test_dynamic_string_handler_is_rejected() -> None:
    registry = TaskRegistry()
    with pytest.raises(TypeError):
        registry.register(definition(handler="module.path:Handler"))  # type: ignore[arg-type]


def test_persisted_task_payload_rejects_sensitive_content_size_and_classification() -> (
    None
):
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.references",
            schema_version=1,
            input_model=ReferenceOnlyInput,
            result_model=ResultModel,
            policy=TaskPolicy(),
            allowed_data_classifications=frozenset({"internal"}),
            max_payload_bytes=128,
        )
    )

    assert registry.validate_input(
        task_type="test.references",
        schema_version=1,
        payload={"artifact_id": "artifact-1"},
        data_classification="internal",
    ) == {"artifact_id": "artifact-1"}
    assert registry.validate_input(
        task_type="test.references",
        schema_version=1,
        payload={
            "audio_artifact_id": "audio-1",
            "transcript_artifact_ref": "transcript-1",
        },
        data_classification="internal",
    ) == {
        "audio_artifact_id": "audio-1",
        "transcript_artifact_ref": "transcript-1",
    }

    for forbidden_payload in (
        {"prompt": "完整提示词正文"},
        {"full_transcript": "完整转写正文"},
        {"customer_audio_base64": "base64正文"},
        {"provider_raw_response": "模型原始响应"},
    ):
        with pytest.raises(Exception, match="TASK_PAYLOAD_SENSITIVE_CONTENT"):
            registry.validate_input(
                task_type="test.references",
                schema_version=1,
                payload=forbidden_payload,
                data_classification="internal",
            )
    with pytest.raises(Exception, match="TASK_PAYLOAD_TOO_LARGE"):
        registry.validate_input(
            task_type="test.references",
            schema_version=1,
            payload={"value": "x" * 256},
            data_classification="internal",
        )
    with pytest.raises(Exception, match="TASK_DATA_CLASSIFICATION_DENIED"):
        registry.validate_input(
            task_type="test.references",
            schema_version=1,
            payload={"artifact_id": "artifact-1"},
            data_classification="restricted",
        )

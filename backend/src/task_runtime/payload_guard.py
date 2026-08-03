"""Fail-closed guards for payloads persisted by shared infrastructure."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

from task_runtime.errors import TaskRuntimeError

_FORBIDDEN_CONTENT_FIELDS = frozenset(
    {
        "audio",
        "audio_base64",
        "audio_bytes",
        "audio_content",
        "audio_data",
        "audio_url",
        "authorization",
        "api_key",
        "access_token",
        "refresh_token",
        "secret",
        "token",
        "transcript",
        "transcript_text",
        "transcription",
        "prompt",
        "prompt_text",
        "system_prompt",
        "developer_prompt",
        "raw_ai_response",
        "raw_model_response",
        "raw_provider_response",
        "raw_response",
    }
)


def _normalized_field_name(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def _is_sensitive_content_field(value: str) -> bool:
    normalized = _normalized_field_name(value)
    if normalized in _FORBIDDEN_CONTENT_FIELDS:
        return True
    tokens = frozenset(normalized.split("_"))
    reference_markers = {"artifact", "id", "ref", "reference"}
    if tokens & reference_markers:
        return False
    if tokens & {"audio", "transcript", "transcription", "prompt"}:
        return True
    if "raw" in tokens and tokens & {"response", "output", "result"}:
        return True
    if tokens & {"secret", "token"}:
        return True
    if {"api", "key"} <= tokens or {"authorization"} <= tokens:
        return True
    return False


def _raise(code: str, message: str) -> NoReturn:
    raise TaskRuntimeError(code, message)


def assert_safe_persisted_payload(
    payload: dict[str, Any],
    *,
    max_bytes: int,
    code_prefix: str,
    subject_label: str,
) -> None:
    """Reject raw sensitive content, binary values, and oversized JSON.

    Shared runtime records are coordination metadata, not a content store. Business
    modules must pass stable object/artifact references instead of raw source data.
    """

    def visit(value: Any) -> None:
        if isinstance(value, (bytes, bytearray, memoryview)):
            _raise(
                f"[{code_prefix}_SENSITIVE_CONTENT]",
                f"{subject_label}不能包含二进制或敏感原文，请改传对象或制品引用。",
            )
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    _raise(
                        f"[{code_prefix}_NOT_SERIALIZABLE]",
                        f"{subject_label}字段名必须是字符串。",
                    )
                if _is_sensitive_content_field(key):
                    _raise(
                        f"[{code_prefix}_SENSITIVE_CONTENT]",
                        f"{subject_label}不能包含音频、转写、提示词、模型原始响应或密钥正文，请改传对象或制品引用。",
                    )
                visit(child)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            for child in value:
                visit(child)

    visit(payload)
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TaskRuntimeError(
            f"[{code_prefix}_NOT_SERIALIZABLE]",
            f"{subject_label}必须是可序列化的 JSON 数据。",
        ) from exc
    if len(encoded) > max_bytes:
        _raise(
            f"[{code_prefix}_TOO_LARGE]",
            f"{subject_label}超过允许大小，请将正文保存为制品后只传引用。",
        )


__all__ = ["assert_safe_persisted_payload"]

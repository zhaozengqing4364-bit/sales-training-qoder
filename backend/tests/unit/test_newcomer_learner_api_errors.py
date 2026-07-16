"""Learner API error envelope: business messages preserved, unexpected classified."""

from __future__ import annotations

import json

from sqlalchemy.exc import OperationalError

from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.learner_api import (
    _classify_unexpected_error,
    _error,
    _typed_business_error,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionServiceError


def _payload(response: object) -> dict[str, object]:
    body = getattr(response, "body", b"")
    return json.loads(bytes(body))


def test_should_keep_business_message_for_newcomer_orchestration_error() -> None:
    exc = NewcomerOrchestrationError(
        "[NEWCOMER_AUDIO_RUBRIC_NOT_PUBLISHED]",
        "录音评分标准尚未发布，请重新选择或新建评分标准。",
        409,
    )
    response = _error(exc)
    assert response.status_code == 409
    payload = _payload(response)
    assert payload["error"] == "[NEWCOMER_AUDIO_RUBRIC_NOT_PUBLISHED]"
    assert payload["message"] == "录音评分标准尚未发布，请重新选择或新建评分标准。"
    assert payload["trace_id"]


def test_should_keep_business_message_for_audio_submission_service_error() -> None:
    exc = AudioSubmissionServiceError(
        "[COS_UPLOAD_FAILED]",
        "音频上传到 COS 失败。",
        status_code=502,
    )
    assert _typed_business_error(exc) == (
        "[COS_UPLOAD_FAILED]",
        "音频上传到 COS 失败。",
        502,
    )
    response = _error(exc)
    assert response.status_code == 502
    payload = _payload(response)
    assert payload["error"] == "[COS_UPLOAD_FAILED]"
    assert payload["message"] == "音频上传到 COS 失败。"


def test_should_classify_unexpected_errors_with_useful_chinese_message(
    monkeypatch,
) -> None:
    logged: dict[str, object] = {}

    class _FakeLogger:
        def error(self, event: str, **kwargs: object) -> None:
            logged["event"] = event
            logged.update(kwargs)

    monkeypatch.setattr(
        "sales_trainer.orchestration.learner_api.logger",
        _FakeLogger(),
    )
    monkeypatch.setattr(
        "sales_trainer.orchestration.learner_api.get_trace_id",
        lambda: "trace-unexpected-1",
    )

    response = _error(RuntimeError("secret=/tmp/keys.env boom"))
    assert response.status_code == 500
    payload = _payload(response)
    assert payload["error"] == "[NEWCOMER_ACTIVITY_FAILED]"
    assert payload["message"] == "训练操作失败，请稍后重试。"
    assert payload["trace_id"] == "trace-unexpected-1"
    assert "secret" not in str(payload["message"])
    assert "/tmp" not in str(payload["message"])
    assert logged["event"] == "newcomer_learner_activity_failed"
    assert logged["error_type"] == "RuntimeError"
    assert logged["error_code"] == "[NEWCOMER_ACTIVITY_FAILED]"
    assert logged["trace_id"] == "trace-unexpected-1"
    assert logged["exc_info"] is True


def test_should_map_upload_and_service_categories_for_common_exceptions() -> None:
    assert _classify_unexpected_error(FileNotFoundError("x"))[0] == (
        "[NEWCOMER_UPLOAD_FAILED]"
    )
    assert _classify_unexpected_error(ValueError("bad"))[0] == (
        "[NEWCOMER_REQUEST_INVALID]"
    )
    assert "请求无效" in _classify_unexpected_error(ValueError("bad"))[1]
    assert (
        _classify_unexpected_error(
            OperationalError("stmt", {}, Exception("db down"))
        )[0]
        == "[NEWCOMER_SERVICE_UNAVAILABLE]"
    )
    assert "服务暂不可用" in _classify_unexpected_error(
        OperationalError("stmt", {}, Exception("db down"))
    )[1]


def test_should_redact_storage_config_dump_from_client_message(
    monkeypatch,
) -> None:
    logged: dict[str, object] = {}

    class _FakeLogger:
        def warning(self, event: str, **kwargs: object) -> None:
            logged["event"] = event
            logged.update(kwargs)

        def error(self, event: str, **kwargs: object) -> None:
            logged["event"] = event
            logged.update(kwargs)

    monkeypatch.setattr(
        "sales_trainer.orchestration.learner_api.logger",
        _FakeLogger(),
    )
    monkeypatch.setattr(
        "sales_trainer.orchestration.learner_api.get_trace_id",
        lambda: "trace-redact-1",
    )

    exc = AudioSubmissionServiceError(
        "[COS_NOT_CONFIGURED]",
        (
            "COS credentials not configured - missing env vars: "
            "TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY. "
            "Set TENCENT_COS_SECRET_ID, TENCENT_COS_SECRET_KEY, "
            "TENCENT_COS_BUCKET, TENCENT_COS_REGION."
        ),
        status_code=503,
    )
    response = _error(exc)
    assert response.status_code == 503
    payload = _payload(response)
    assert payload["error"] == "[COS_NOT_CONFIGURED]"
    assert payload["message"] == "对象存储暂不可用，请稍后重试或联系管理员。"
    assert "SECRET" not in str(payload["message"])
    assert "TENCENT_COS" not in str(payload["message"])
    assert "missing env vars" not in str(payload["message"]).lower()
    assert logged["event"] == "newcomer_learner_business_message_redacted"
    assert logged["error_code"] == "[COS_NOT_CONFIGURED]"
    assert "TENCENT_COS_SECRET_ID" in str(logged["exception_message"])

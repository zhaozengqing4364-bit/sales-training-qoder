from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from common.error_handling.result import Result
from common.services.runtime_gate import RuntimeAdmissionDecision
from curriculum_practice.websocket import router as examiner_router
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    FrozenExamQuestion,
)
from curriculum_practice.websocket.router import _AuthUser


def examiner_admission_ok() -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=True,
        runtime_type="examiner",
        classification="voluntary",
    )


def examiner_admission_blocked(
    code: str,
) -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=False,
        runtime_type="examiner",
        classification="terminal",
        code=code,
        close_code=4413,
        close_reason=code,
        mark_runtime_failed=True,
    )


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_feature_flag_disabled(monkeypatch) -> None:
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", False)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4404,
        reason="CURRICULUM_EXAMINER_DISABLED",
    )


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_runtime_config_missing(monkeypatch) -> None:
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(
        examiner_router,
        "_build_runtime_from_session",
        AsyncMock(return_value=(None, "EXAMINER_RUNTIME_CONFIG_MISSING")),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(
            return_value=examiner_admission_blocked(
                "EXAMINER_RUNTIME_CONFIG_MISSING"
            )
        ),
    )
    mark_runtime_failed = AsyncMock()
    monkeypatch.setattr(
        examiner_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(examiner_router, "verify_token", lambda token: {"sub": "user-1"})
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-1", role="user", is_active=True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=(None, True)),
    )

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4413,
        reason="EXAMINER_RUNTIME_CONFIG_MISSING",
    )
    mark_runtime_failed.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        failure_code="EXAMINER_RUNTIME_CONFIG_MISSING",
        source="examiner_websocket_reject",
    )


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_token_invalid_before_runtime_work(
    monkeypatch,
) -> None:
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    build_runtime_mock = AsyncMock(return_value=(None, "MOCKED_ERROR"))
    monkeypatch.setattr(examiner_router, "_build_runtime_from_session", build_runtime_mock)
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    admission_mock = AsyncMock(return_value=examiner_admission_ok())
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        admission_mock,
    )

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")
    build_runtime_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_connect_examiner_handler_when_enabled(monkeypatch) -> None:
    websocket = MagicMock()
    handler = MagicMock()
    handler.handle_connection = AsyncMock()
    runtime = ExaminerRuntime(
        session_id="11111111-1111-1111-1111-111111111111",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[
            FrozenExamQuestion(
                question_id="question-1",
                title="题目",
                stem="题干",
                reference_answer="参考答案",
                scoring_criteria={},
            )
        ],
    )
    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(
        examiner_router,
        "_build_runtime_from_session",
        AsyncMock(return_value=(runtime, None)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(examiner_router, "verify_token", lambda token: {"sub": "user-123"})
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-123", role="user", is_active=True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=(None, True)),
    )
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock(return_value=handler)
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="trace-1",
    )

    handler_cls_mock.assert_called_once_with(runtime)
    handler.handle_connection.assert_awaited_once_with(
        websocket,
        "11111111-1111-1111-1111-111111111111",
        "valid-token",
        trace_id="trace-1",
    )
    session_manager.register_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        handler,
        user_id="user-123",
    )
    session_manager.unregister_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        reason="connection_closed",
    )


@pytest.mark.asyncio
async def test_should_register_session_with_user_id_from_user_id_claim(
    monkeypatch,
) -> None:
    websocket = MagicMock()
    handler = MagicMock()
    handler.handle_connection = AsyncMock()
    runtime = ExaminerRuntime(
        session_id="11111111-1111-1111-1111-111111111111",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[
            FrozenExamQuestion(
                question_id="question-1",
                title="题目",
                stem="题干",
                reference_answer="参考答案",
                scoring_criteria={},
            )
        ],
    )
    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(
        examiner_router,
        "_build_runtime_from_session",
        AsyncMock(return_value=(runtime, None)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(
        examiner_router, "verify_token", lambda token: {"user_id": "user-456"},
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-456", role="user", is_active=True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=(None, True)),
    )
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock(return_value=handler)
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    session_manager.register_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        handler,
        user_id="user-456",
    )
    session_manager.unregister_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        reason="connection_closed",
    )


@pytest.mark.asyncio
async def test_should_unregister_session_in_finally_when_handler_raises(
    monkeypatch,
) -> None:
    websocket = MagicMock()
    handler = MagicMock()
    handler.handle_connection = AsyncMock(side_effect=RuntimeError("boom"))
    runtime = ExaminerRuntime(
        session_id="11111111-1111-1111-1111-111111111111",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[
            FrozenExamQuestion(
                question_id="question-1",
                title="题目",
                stem="题干",
                reference_answer="参考答案",
                scoring_criteria={},
            )
        ],
    )
    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(
        examiner_router,
        "_build_runtime_from_session",
        AsyncMock(return_value=(runtime, None)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(examiner_router, "verify_token", lambda token: {"sub": "user-1"})
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-1", role="user", is_active=True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=(None, True)),
    )
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock(return_value=handler)
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    with pytest.raises(RuntimeError, match="boom"):
        await examiner_router._handle_examiner_websocket(
            websocket=websocket,
            session_id="11111111-1111-1111-1111-111111111111",
            token="token",
            trace_id="",
        )

    session_manager.unregister_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        reason="connection_closed",
    )


@pytest.mark.asyncio
async def test_should_build_runtime_from_session_freezing_examiner_questions(monkeypatch) -> None:
    class Session:
        practice_template_id = "template-1"
        curriculum_snapshot = {
            "snapshot_hash": "sha256:snapshot",
            "content_assets": [
                {
                    "asset_type": "examiner_agent",
                    "asset_id": "examiner-1",
                    "version": 1,
                    "hash": "sha256:examiner-v1",
                    "snapshot_label": "published",
                },
                {
                    "asset_type": "question_item",
                    "asset_id": "question-1",
                    "version": 1,
                    "hash": "sha256:question-v1",
                    "snapshot_label": "published",
                },
            ],
        }

    class Template:
        examiner_agent_id = "examiner-1"

    class Agent:
        examiner_agent_id = "examiner-1"
        timeout_config = {"max_seconds": 600}
        question_source_ids = ["question-1"]
        status = "published"
        version = 1
        content_hash = "sha256:examiner-v1"

    class Question:
        question_id = "question-1"
        title = "预算确认"
        stem = "你会如何确认预算？"
        reference_answer = "先确认预算区间。"
        scoring_criteria = {"dimensions": [{"id": "budget"}]}
        status = "published"
        safety_flagged = False
        version = 1
        content_hash = "sha256:question-v1"

    class DbContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, model, key):
            model_name = model.__name__
            if model_name == "PracticeSession" and key == "session-1":
                return Session()
            if model_name == "PracticeTemplate" and key == "template-1":
                return Template()
            if model_name == "ExaminerAgent" and key == "examiner-1":
                return Agent()
            if model_name == "QuestionItem" and key == "question-1":
                return Question()
            return None

    monkeypatch.setattr(examiner_router, "AsyncSessionLocal", lambda: DbContext())

    runtime, failure = await examiner_router._build_runtime_from_session("session-1")
    messages = await runtime.connect() if runtime is not None else []

    assert failure is None
    assert messages[0]["data"]["examiner_agent_id"] == "examiner-1"
    assert messages[0]["data"]["remaining_seconds"] == 600
    assert messages[1]["data"] == {
        "question_index": 0,
        "question_id": "question-1",
        "question_type": "short_answer",
        "title": "预算确认",
        "stem": "你会如何确认预算？",
        "remaining_seconds": 600,
    }


@pytest.mark.asyncio
async def test_should_reject_runtime_when_snapshot_examiner_ref_is_stale(monkeypatch) -> None:
    class Session:
        practice_template_id = "template-1"
        curriculum_snapshot = {
            "snapshot_hash": "sha256:snapshot",
            "content_assets": [
                {
                    "asset_type": "examiner_agent",
                    "asset_id": "examiner-1",
                    "version": 1,
                    "hash": "sha256:examiner-v1",
                    "snapshot_label": "published",
                },
                {
                    "asset_type": "question_item",
                    "asset_id": "question-1",
                    "version": 1,
                    "hash": "sha256:question-v1",
                    "snapshot_label": "published",
                },
            ],
        }

    class Template:
        examiner_agent_id = "examiner-1"

    class Agent:
        examiner_agent_id = "examiner-1"
        timeout_config = {"max_seconds": 600}
        question_source_ids = ["question-1"]
        status = "published"
        version = 2
        content_hash = "sha256:examiner-v2"

    class Question:
        question_id = "question-1"
        title = "预算确认"
        stem = "你会如何确认预算？"
        reference_answer = "先确认预算区间。"
        scoring_criteria = {"dimensions": [{"id": "budget"}]}
        status = "published"
        safety_flagged = False
        version = 1
        content_hash = "sha256:question-v1"

    class DbContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, model, key):
            model_name = model.__name__
            if model_name == "PracticeSession" and key == "session-1":
                return Session()
            if model_name == "PracticeTemplate" and key == "template-1":
                return Template()
            if model_name == "ExaminerAgent" and key == "examiner-1":
                return Agent()
            if model_name == "QuestionItem" and key == "question-1":
                return Question()
            return None

    monkeypatch.setattr(examiner_router, "AsyncSessionLocal", lambda: DbContext())

    runtime, failure = await examiner_router._build_runtime_from_session("session-1")

    assert runtime is None
    assert failure == "EXAMINER_RUNTIME_SNAPSHOT_STALE"


@pytest.mark.asyncio
async def test_should_reject_runtime_when_snapshot_question_ref_is_stale(monkeypatch) -> None:
    class Session:
        practice_template_id = "template-1"
        curriculum_snapshot = {
            "snapshot_hash": "sha256:snapshot",
            "content_assets": [
                {
                    "asset_type": "examiner_agent",
                    "asset_id": "examiner-1",
                    "version": 1,
                    "hash": "sha256:examiner-v1",
                    "snapshot_label": "published",
                },
                {
                    "asset_type": "question_item",
                    "asset_id": "question-1",
                    "version": 1,
                    "hash": "sha256:question-v1",
                    "snapshot_label": "published",
                },
            ],
        }

    class Agent:
        examiner_agent_id = "examiner-1"
        timeout_config = {"max_seconds": 600}
        question_source_ids = ["question-1"]
        status = "published"
        version = 1
        content_hash = "sha256:examiner-v1"

    class Question:
        question_id = "question-1"
        title = "预算确认"
        stem = "你会如何确认预算？"
        reference_answer = "先确认预算区间。"
        scoring_criteria = {"dimensions": [{"id": "budget"}]}
        status = "published"
        safety_flagged = False
        version = 2
        content_hash = "sha256:question-v2"

    class DbContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, model, key):
            model_name = model.__name__
            if model_name == "PracticeSession" and key == "session-1":
                return Session()
            if model_name == "ExaminerAgent" and key == "examiner-1":
                return Agent()
            if model_name == "QuestionItem" and key == "question-1":
                return Question()
            return None

    monkeypatch.setattr(examiner_router, "AsyncSessionLocal", lambda: DbContext())

    runtime, failure = await examiner_router._build_runtime_from_session("session-1")

    assert runtime is None
    assert failure == "EXAMINER_RUNTIME_SNAPSHOT_STALE"


def test_should_expose_examiner_websocket_routes() -> None:
    websocket_paths = {route.path for route in examiner_router.router.routes}
    assert "/ws/curriculum/examiner" in websocket_paths
    assert "/ws/curriculum/examiner/{session_id}" in websocket_paths


@pytest.mark.asyncio
async def test_should_mark_examiner_report_completed_idempotently(monkeypatch) -> None:
    persist_calls = 0

    class FakeReportService:
        def __init__(self, _db: object) -> None:
            pass

        async def persist_completion_report(self, **kwargs: object) -> Result[dict[str, object]]:
            nonlocal persist_calls
            persist_calls += 1
            return Result.ok({"session_id": kwargs["session_id"]})

    monkeypatch.setattr(examiner_router, "ExaminerReportService", FakeReportService)

    first_path = await examiner_router._mark_examiner_report_completed(
        session_id="session-1",
        answers=[{"question_id": "question-1", "question_index": 0, "score": 80}],
        reason="all_questions_answered",
    )
    second_path = await examiner_router._mark_examiner_report_completed(
        session_id="session-1",
        answers=[{"question_id": "question-1", "question_index": 0, "score": 80}],
        reason="reconnected",
    )

    assert first_path == "/exam/session-1/report"
    assert second_path == first_path
    assert persist_calls == 2


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_session_owner_mismatch(
    monkeypatch,
) -> None:
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=("owner-other", True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-1", role="user", is_active=True)),
    )
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(examiner_router, "verify_token", lambda token: {"sub": "user-1"})

    build_runtime_mock = AsyncMock(return_value=(None, "MOCKED_ERROR"))
    monkeypatch.setattr(examiner_router, "_build_runtime_from_session", build_runtime_mock)
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock()
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4003, reason="ACCESS_DENIED")

    build_runtime_mock.assert_not_awaited()
    handler_cls_mock.assert_not_called()
    session_manager.register_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_allow_examiner_websocket_when_admin_connects_to_other_user_session(
    monkeypatch,
) -> None:
    websocket = MagicMock()
    handler = MagicMock()
    handler.handle_connection = AsyncMock()
    runtime = ExaminerRuntime(
        session_id="11111111-1111-1111-1111-111111111111",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[
            FrozenExamQuestion(
                question_id="question-1",
                title="题目",
                stem="题干",
                reference_answer="参考答案",
                scoring_criteria={},
            )
        ],
    )

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=("owner-other", True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-admin", role="admin", is_active=True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_build_runtime_from_session",
        AsyncMock(return_value=(runtime, None)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(examiner_router, "verify_token", lambda token: {"sub": "user-admin"})
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock(return_value=handler)
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    handler_cls_mock.assert_called_once_with(runtime)
    handler.handle_connection.assert_awaited_once()
    session_manager.register_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        handler,
        user_id="user-admin",
    )
    session_manager.unregister_session.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        reason="connection_closed",
    )


# ── New security tests: active user validation + fail-closed owner lookup ──


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_token_user_not_found(
    monkeypatch,
) -> None:
    """token resolves to a user_id, but no matching User row exists in the DB."""
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(
        examiner_router, "verify_token", lambda token: {"sub": "missing-user"},
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=None),
    )

    resolve_owner_mock = AsyncMock()
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        resolve_owner_mock,
    )
    build_runtime_mock = AsyncMock(return_value=(None, "MOCKED_ERROR"))
    monkeypatch.setattr(examiner_router, "_build_runtime_from_session", build_runtime_mock)
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock()
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")

    resolve_owner_mock.assert_not_awaited()
    build_runtime_mock.assert_not_awaited()
    handler_cls_mock.assert_not_called()
    session_manager.register_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_token_user_inactive(
    monkeypatch,
) -> None:
    """token resolves to a user that exists but is_active=False."""
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(
        examiner_router, "verify_token", lambda token: {"sub": "inactive-user"},
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="inactive-user", role="user", is_active=False)),
    )

    resolve_owner_mock = AsyncMock()
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        resolve_owner_mock,
    )
    build_runtime_mock = AsyncMock(return_value=(None, "MOCKED_ERROR"))
    monkeypatch.setattr(examiner_router, "_build_runtime_from_session", build_runtime_mock)
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_admission_decision",
        AsyncMock(return_value=examiner_admission_ok()),
    )
    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock()
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")

    resolve_owner_mock.assert_not_awaited()
    build_runtime_mock.assert_not_awaited()
    handler_cls_mock.assert_not_called()
    session_manager.register_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_reject_examiner_websocket_when_owner_lookup_fails_closed(
    monkeypatch,
) -> None:
    """owner DB lookup fails (transient error, connection loss, etc.) — must fail CLOSED."""
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(examiner_router.settings, "CURRICULUM_EXAMINER_ENABLED", True)
    monkeypatch.setattr(examiner_router, "resolve_websocket_token", lambda **kw: "valid-token")
    monkeypatch.setattr(
        examiner_router, "verify_token", lambda token: {"sub": "user-1"},
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_authenticated_user",
        AsyncMock(return_value=_AuthUser(user_id="user-1", role="user", is_active=True)),
    )
    monkeypatch.setattr(
        examiner_router,
        "_resolve_examiner_session_owner_id",
        AsyncMock(return_value=(None, False)),  # lookup failed
    )

    build_runtime_mock = AsyncMock(return_value=(None, "MOCKED_ERROR"))
    monkeypatch.setattr(examiner_router, "_build_runtime_from_session", build_runtime_mock)
    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    monkeypatch.setattr(
        examiner_router, "get_session_manager", lambda: session_manager,
        raising=False,
    )
    handler_cls_mock = MagicMock()
    monkeypatch.setattr(examiner_router, "ExaminerWebSocketHandler", handler_cls_mock)

    await examiner_router._handle_examiner_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4003, reason="ACCESS_DENIED")

    build_runtime_mock.assert_not_awaited()
    handler_cls_mock.assert_not_called()
    session_manager.register_session.assert_not_awaited()

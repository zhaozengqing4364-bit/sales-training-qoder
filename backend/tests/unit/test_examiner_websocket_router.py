from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from curriculum_practice.websocket import router as examiner_router
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    FrozenExamQuestion,
)
from curriculum_practice.websocket.router import _AuthUser


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
    class Session:
        report_status = "pending"
        report_generated_at = None
        report_status_updated_at = None
        report_retryable = True
        report_error = "previous"

    session = Session()
    commit_count = 0

    class DbContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, model, key):
            return session if key == "session-1" else None

        async def commit(self):
            nonlocal commit_count
            commit_count += 1

    monkeypatch.setattr(examiner_router, "AsyncSessionLocal", lambda: DbContext())

    first_path = await examiner_router._mark_examiner_report_completed(
        session_id="session-1",
        answers=[{"question_id": "question-1"}],
        reason="all_questions_answered",
    )
    first_generated_at = session.report_generated_at
    second_path = await examiner_router._mark_examiner_report_completed(
        session_id="session-1",
        answers=[{"question_id": "question-1"}],
        reason="reconnected",
    )

    assert first_path == "/api/v1/evaluation/sessions/session-1/report"
    assert second_path == first_path
    assert session.report_status == "completed"
    assert isinstance(session.report_generated_at, datetime)
    assert session.report_generated_at == first_generated_at
    assert session.report_retryable is False
    assert session.report_error is None
    assert commit_count == 1


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

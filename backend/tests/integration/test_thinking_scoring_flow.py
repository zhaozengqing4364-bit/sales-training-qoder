from __future__ import annotations

import sys
import types
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import EvaluationRun, PracticeSession, Scenario, User
from evaluation.services.evaluation_run_service import EvaluationRunService
from sales_bot.websocket.components.stepfun_thinking_capture import ThinkingEntry

if "websockets" not in sys.modules:
    websockets_stub = types.ModuleType("websockets")
    exceptions_stub = types.ModuleType("websockets.exceptions")

    class ConnectionClosed(Exception):
        pass

    setattr(exceptions_stub, "ConnectionClosed", ConnectionClosed)
    sys.modules["websockets"] = websockets_stub
    sys.modules["websockets.exceptions"] = exceptions_stub

if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_api_stub = types.ModuleType("chromadb.api")
    chromadb_models_stub = types.ModuleType("chromadb.api.models")
    chromadb_collection_stub = types.ModuleType("chromadb.api.models.Collection")
    chromadb_config_stub = types.ModuleType("chromadb.config")

    class ClientAPI:
        pass

    class Collection:
        pass

    class Settings:
        def __init__(self, **_kwargs: object) -> None:
            pass

    setattr(chromadb_stub, "PersistentClient", lambda *_args, **_kwargs: None)
    setattr(chromadb_api_stub, "ClientAPI", ClientAPI)
    setattr(chromadb_collection_stub, "Collection", Collection)
    setattr(chromadb_config_stub, "Settings", Settings)
    sys.modules["chromadb"] = chromadb_stub
    sys.modules["chromadb.api"] = chromadb_api_stub
    sys.modules["chromadb.api.models"] = chromadb_models_stub
    sys.modules["chromadb.api.models.Collection"] = chromadb_collection_stub
    sys.modules["chromadb.config"] = chromadb_config_stub

from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


async def _create_sales_session(db: AsyncSession) -> PracticeSession:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"thinking_{uuid.uuid4().hex[:8]}",
        name="Thinking User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"thinking_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        runtime_state={},
    )
    db.add_all([user, scenario, session])
    await db.commit()
    return session


@pytest.mark.asyncio
async def test_should_persist_thinking_log_in_runtime_state(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await _create_sales_session(test_db)

    class SessionContext:
        async def __aenter__(self) -> AsyncSession:
            return test_db

        async def __aexit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.AsyncSessionLocal",
        lambda: SessionContext(),
    )
    handler = StepFunRealtimeHandler()
    handler.session_id = str(session.session_id)

    await handler._persist_thinking_entry(
        ThinkingEntry(
            turn_index=3,
            template_stage_key="standard_roleplay",
            response_id="resp_001",
            thinking_text="Reviewer-only reasoning",
            captured_at="2026-05-13T10:00:00Z",
        )
    )

    refreshed = await test_db.scalar(
        select(PracticeSession).where(PracticeSession.session_id == session.session_id)
    )
    assert refreshed is not None
    assert refreshed.runtime_state["thinking_log"] == [
        {
            "turn_index": 3,
            "template_stage_key": "standard_roleplay",
            "response_id": "resp_001",
            "thinking_text": "Reviewer-only reasoning",
            "captured_at": "2026-05-13T10:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_should_attach_thinking_context_to_evaluation_input_without_learner_exposure(
    test_db: AsyncSession,
) -> None:
    session = await _create_sales_session(test_db)
    session.runtime_state = {
        "thinking_log": [
            {
                "turn_index": 2,
                "template_stage_key": "standard_roleplay",
                "response_id": "resp_eval",
                "thinking_text": "Use rubric evidence only for reviewer scoring.",
                "captured_at": "2026-05-13T10:00:00Z",
            }
        ]
    }
    await test_db.commit()

    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "session_evidence_projection"},
    )

    persisted = await test_db.scalar(
        select(EvaluationRun).where(EvaluationRun.run_id == run.run_id)
    )
    assert persisted is not None
    assert persisted.input_evidence_reference["thinking_context"] == [
        {
            "turn_index": 2,
            "template_stage_key": "standard_roleplay",
            "response_id": "resp_eval",
            "thinking_text": "Use rubric evidence only for reviewer scoring.",
            "captured_at": "2026-05-13T10:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_stepfun_handler_delegates_thinking_events_without_inline_chunk_assembly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = StepFunRealtimeHandler()
    captured_entries: list[ThinkingEntry] = []

    async def persist(entry: ThinkingEntry) -> None:
        captured_entries.append(entry)

    monkeypatch.setattr(handler, "_persist_thinking_entry", persist)

    await handler._handle_upstream_event(
        {"type": "response.thinking.delta", "response_id": "resp_delegate", "delta": "abc"}
    )
    await handler._handle_upstream_event(
        {"type": "response.thinking.done", "response_id": "resp_delegate"}
    )

    assert [entry.thinking_text for entry in captured_entries] == ["abc"]

from __future__ import annotations

import sys
import types
import uuid
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from agent.capabilities.realtime_scoring import RealtimeScoringCapability
from agent.context import AgentContext
from common.db.models import PracticeSession, Scenario, User
from sales_bot.websocket.components.stepfun_emotion_analyzer import (
    EmotionSignal,
    apply_emotion_signals_to_runtime_state,
)

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


def _result_data(result: Any) -> dict[str, Any]:
    return cast(dict[str, Any], result.data or {})


@pytest.mark.asyncio
async def test_should_persist_emotion_log_in_practice_session_runtime_state(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"emotion_{uuid.uuid4().hex[:8]}",
        name="Emotion User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"emotion_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        runtime_state={"emotion_log": []},
    )
    test_db.add_all([user, scenario, session])
    await test_db.commit()

    session.runtime_state = apply_emotion_signals_to_runtime_state(
        session.runtime_state,
        [
            EmotionSignal(
                turn_id="turn-1",
                signal_type="speaking_rate",
                value=3.2,
                source_event_ids=("event-1",),
                captured_at="2026-05-13T10:00:00Z",
            )
        ],
        template_stage_key="standard_roleplay",
    )
    await test_db.commit()

    refreshed = await test_db.scalar(
        select(PracticeSession).where(PracticeSession.session_id == session.session_id)
    )
    assert refreshed is not None
    assert refreshed.runtime_state["emotion_log"] == [
        {
            "turn_id": "turn-1",
            "template_stage_key": "standard_roleplay",
            "speaking_rate": 3.2,
            "captured_at": "2026-05-13T10:00:00Z",
            "source_event_ids": ["event-1"],
        }
    ]


@pytest.mark.asyncio
async def test_should_persist_emotion_signals_through_production_handler_path(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"emotion_path_{uuid.uuid4().hex[:8]}",
        name="Emotion Path User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"emotion_path_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        runtime_state={},
    )
    test_db.add_all([user, scenario, session])
    await test_db.commit()

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

    await handler._persist_emotion_signals(
        [
            EmotionSignal(
                turn_id="turn-1",
                signal_type="response_done_to_user_start_ms",
                value=900,
                source_event_ids=("done", "start"),
                captured_at="2026-05-13T10:00:00Z",
            )
        ],
        template_stage_key="standard_roleplay",
    )
    await handler._persist_emotion_signals(
        [
            EmotionSignal(
                turn_id="turn-1",
                signal_type="speaking_rate",
                value=2.8,
                source_event_ids=("transcript",),
                captured_at="2026-05-13T10:00:01Z",
            )
        ],
        template_stage_key="standard_roleplay",
    )

    refreshed = await test_db.scalar(
        select(PracticeSession).where(PracticeSession.session_id == session.session_id)
    )
    assert refreshed is not None
    assert refreshed.runtime_state["emotion_log"] == [
        {
            "turn_id": "turn-1",
            "template_stage_key": "standard_roleplay",
            "response_done_to_user_start_ms": 900,
            "speaking_rate": 2.8,
            "captured_at": "2026-05-13T10:00:01Z",
            "source_event_ids": ["done", "start", "transcript"],
        }
    ]


@pytest.mark.asyncio
async def test_should_allow_realtime_scoring_to_consume_optional_emotion_dimensions() -> None:
    context = AgentContext(
        session_id="emotion-score-session",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        state={
            "emotion_log": [
                {
                    "turn_id": "turn-1",
                    "response_done_to_user_start_ms": 600,
                    "speaking_rate": 3.1,
                    "hesitation_count": 0,
                    "captured_at": "2026-05-13T10:00:00Z",
                }
            ]
        },
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
    )
    capability = RealtimeScoringCapability(
        {
            "enabled": True,
            "emotion_scoring": {
                "enabled": True,
                "dimensions": {"response_confidence": True, "fluency": True},
            },
        }
    )

    result = await capability.execute(context, "我们本周可以安排试点评估和负责人对齐。")

    assert result.success is True
    data = _result_data(result)
    emotion_scores = cast(dict[str, float], data["emotion_dimension_scores"])
    dimension_scores = cast(dict[str, float], data["dimension_scores"])
    assert "response_confidence" in emotion_scores
    assert "fluency" in emotion_scores
    assert dimension_scores["表达信心"] >= 80
    assert dimension_scores["表达流畅度"] >= 80


@pytest.mark.asyncio
async def test_should_change_overall_score_when_emotion_scoring_enabled() -> None:
    baseline_context = AgentContext(
        session_id="emotion-overall-baseline",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        state={},
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
    )
    emotion_context = AgentContext(
        session_id="emotion-overall-enabled",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        state={
            "emotion_log": [
                {
                    "turn_id": "turn-1",
                    "response_done_to_user_start_ms": 3200,
                    "speaking_rate": 0.6,
                    "hesitation_count": 6,
                }
            ]
        },
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
    )
    text = "我们本周可以安排试点评估和负责人对齐。"

    baseline = await RealtimeScoringCapability({"enabled": True}).execute(
        baseline_context, text
    )
    with_emotion = await RealtimeScoringCapability(
        {
            "enabled": True,
            "emotion_scoring": {
                "enabled": True,
                "weight": 0.2,
                "dimensions": {"response_confidence": True, "fluency": True},
            },
        }
    ).execute(emotion_context, text)

    assert with_emotion.success is True
    baseline_data = _result_data(baseline)
    emotion_data = _result_data(with_emotion)
    assert emotion_data["overall_score"] < baseline_data["overall_score"]


@pytest.mark.asyncio
async def test_should_skip_emotion_dimensions_when_template_disables_them() -> None:
    context = AgentContext(
        session_id="emotion-disabled-session",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        state={"emotion_log": [{"response_done_to_user_start_ms": 400, "speaking_rate": 3.0}]},
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
    )
    text = "我们本周可以安排试点评估。"
    baseline = await RealtimeScoringCapability({"enabled": True}).execute(
        AgentContext(
            session_id="emotion-disabled-baseline",
            agent_id="agent-1",
            persona_id="persona-1",
            user_id="user-1",
            state={},
            conversation_history=[],
            agent_config={},
            persona_config={},
            turn_count=1,
        ),
        text,
    )
    capability = RealtimeScoringCapability(
        {"enabled": True, "emotion_scoring": {"enabled": False, "weight": 0.2}}
    )

    result = await capability.execute(context, text)

    assert result.success is True
    result_data = _result_data(result)
    baseline_data = _result_data(baseline)
    assert result_data["emotion_dimension_scores"] == {}
    assert "表达信心" not in cast(dict[str, float], result_data["dimension_scores"])
    assert result_data["overall_score"] == baseline_data["overall_score"]


@pytest.mark.asyncio
async def test_stepfun_handler_delegates_emotion_events_without_inline_algorithm() -> None:
    handler = StepFunRealtimeHandler()
    handler._emotion_analyzer = MagicMock()
    handler._emotion_analyzer.on_speech_started.return_value = []
    handler._persist_emotion_signals = AsyncMock()

    event = {"type": "input_audio_buffer.speech_started", "event_id": "speech-start"}

    await handler._handle_emotion_event(event)

    handler._emotion_analyzer.on_speech_started.assert_called_once_with(event)
    handler._persist_emotion_signals.assert_not_awaited()


@pytest.mark.asyncio
async def test_stepfun_handler_treats_emotion_persistence_failure_as_non_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSessionContext:
        async def __aenter__(self) -> object:
            raise RuntimeError("db unavailable")

        async def __aexit__(self, *_exc: object) -> None:
            return None

    warnings: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.AsyncSessionLocal",
        lambda: FailingSessionContext(),
    )
    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.logger.warning",
        lambda message, **kwargs: warnings.append({"message": message, **kwargs}),
    )
    handler = StepFunRealtimeHandler()
    handler.session_id = "emotion-non-critical-session"

    await handler._persist_emotion_signals(
        [
            EmotionSignal(
                turn_id="turn-1",
                signal_type="speaking_rate",
                value=2.0,
                source_event_ids=("event-1",),
                captured_at="2026-05-13T10:00:00Z",
            )
        ]
    )

    assert warnings
    assert warnings[0]["message"] == "StepFun emotion signal persistence degraded"


@pytest.mark.asyncio
async def test_stepfun_handler_treats_emotion_persistence_sqlalchemy_failure_as_non_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingDb:
        async def execute(self, *_args: object, **_kwargs: object) -> object:
            raise SQLAlchemyError("emotion query failed")

    class FailingSessionContext:
        async def __aenter__(self) -> FailingDb:
            return FailingDb()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    warnings: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.AsyncSessionLocal",
        lambda: FailingSessionContext(),
    )
    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.logger.warning",
        lambda message, **kwargs: warnings.append({"message": message, **kwargs}),
    )
    handler = StepFunRealtimeHandler()
    handler.session_id = "emotion-sqlalchemy-failure-session"

    await handler._persist_emotion_signals(
        [
            EmotionSignal(
                turn_id="turn-1",
                signal_type="speaking_rate",
                value=2.0,
                source_event_ids=("event-1",),
                captured_at="2026-05-13T10:00:00Z",
            )
        ]
    )

    assert warnings
    assert warnings[0]["message"] == "StepFun emotion signal persistence degraded"


@pytest.mark.asyncio
async def test_stepfun_handler_treats_emotion_log_load_sqlalchemy_failure_as_non_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingDb:
        async def execute(self, *_args: object, **_kwargs: object) -> object:
            raise SQLAlchemyError("emotion log query failed")

    class FailingSessionContext:
        async def __aenter__(self) -> FailingDb:
            return FailingDb()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    warnings: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.AsyncSessionLocal",
        lambda: FailingSessionContext(),
    )
    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_handler.logger.warning",
        lambda message, **kwargs: warnings.append({"message": message, **kwargs}),
    )
    handler = StepFunRealtimeHandler()
    handler.session_id = "emotion-log-load-failure-session"
    handler._feedback_context = AgentContext(
        session_id=handler.session_id,
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        state={},
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
    )

    await handler._load_emotion_log_into_feedback_context()

    assert handler._feedback_context.state == {}
    assert warnings
    assert warnings[0]["message"] == "StepFun emotion log loading degraded"

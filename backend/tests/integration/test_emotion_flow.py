from __future__ import annotations

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
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

    exceptions_stub.ConnectionClosed = ConnectionClosed
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
                    "response_latency_ms": 600,
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
    assert "response_confidence" in result.data["emotion_dimension_scores"]
    assert "fluency" in result.data["emotion_dimension_scores"]
    assert result.data["dimension_scores"]["表达信心"] >= 80
    assert result.data["dimension_scores"]["表达流畅度"] >= 80


@pytest.mark.asyncio
async def test_should_skip_emotion_dimensions_when_template_disables_them() -> None:
    context = AgentContext(
        session_id="emotion-disabled-session",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        state={"emotion_log": [{"response_latency_ms": 400, "speaking_rate": 3.0}]},
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
    )
    capability = RealtimeScoringCapability(
        {"enabled": True, "emotion_scoring": {"enabled": False}}
    )

    result = await capability.execute(context, "我们本周可以安排试点评估。")

    assert result.success is True
    assert result.data["emotion_dimension_scores"] == {}
    assert "表达信心" not in result.data["dimension_scores"]


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

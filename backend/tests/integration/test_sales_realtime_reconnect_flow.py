"""Integration coverage for sales StepFun reconnect and terminal snapshot cleanup."""

from __future__ import annotations

import asyncio
import copy
import json
import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketState

import sales_bot.websocket.stepfun_realtime_handler as stepfun_module
from common.db.models import PracticeSession, Scenario, User
from common.error_handling.result import Result
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


class _InMemoryStateService:
    def __init__(self) -> None:
        self.snapshots: dict[str, SessionStateSnapshot] = {}

    async def save_state(self, state: SessionStateSnapshot):
        self.snapshots[state.session_id] = SessionStateSnapshot.from_dict(
            copy.deepcopy(state.to_dict())
        )
        return Result.ok(None)

    async def get_state(self, session_id: str):
        snapshot = self.snapshots.get(session_id)
        if snapshot is None:
            return Result.ok(None)
        return Result.ok(
            SessionStateSnapshot.from_dict(copy.deepcopy(snapshot.to_dict()))
        )

    async def delete_state(self, session_id: str):
        self.snapshots.pop(session_id, None)
        return Result.ok(None)


class _QueueWebSocket:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.client_state = WebSocketState.CONNECTED
        self.accepted = False
        self.close_calls: list[tuple[int, str]] = []
        self.sent_messages: list[dict] = []
        self._incoming: asyncio.Queue[dict] = asyncio.Queue()

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent_messages.append(copy.deepcopy(message))

    async def receive(self) -> dict:
        return await self._incoming.get()

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.close_calls.append((code, reason))
        self.client_state = WebSocketState.DISCONNECTED
        await self._incoming.put({"type": "websocket.disconnect"})

    async def push_json(self, payload: dict) -> None:
        await self._incoming.put({"text": json.dumps(payload, ensure_ascii=False)})

    async def disconnect(self) -> None:
        self.client_state = WebSocketState.DISCONNECTED
        await self._incoming.put({"type": "websocket.disconnect"})


async def _wait_for(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1.5,
    interval: float = 0.01,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition not met before timeout")


async def _create_sales_session(
    db_session: AsyncSession,
    *,
    user: User,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"stepfun_reconnect_sales_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(user.user_id),
        scenario_id=scenario.scenario_id,
        status="preparing",
        voice_mode="stepfun_realtime",
    )
    db_session.add_all([scenario, session])
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def _hold_upstream_forever() -> None:
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        raise


def _prepare_handler(
    *,
    state_service: _InMemoryStateService,
) -> StepFunRealtimeHandler:
    handler = StepFunRealtimeHandler()
    handler.state_service = state_service
    handler._stepfun_api_key = "test-stepfun-key"

    async def _fake_load_effective_policy() -> None:
        handler._effective_policy = {
            "tool_policy": {},
            "knowledge_base_ids": [],
        }

    handler._load_effective_policy = _fake_load_effective_policy  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock()  # type: ignore[name-defined,method-assign]
    handler._close_upstream = AsyncMock()  # type: ignore[name-defined,method-assign]
    handler._receive_upstream_events = _hold_upstream_forever  # type: ignore[method-assign]
    handler._prepare_grounding_context = AsyncMock()  # type: ignore[name-defined,method-assign]
    handler._send_upstream = AsyncMock()  # type: ignore[name-defined,method-assign]
    handler._persist_message = AsyncMock()  # type: ignore[name-defined,method-assign]
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")  # type: ignore[name-defined,method-assign]
    handler._run_realtime_feedback = AsyncMock(return_value={})  # type: ignore[name-defined,method-assign]
    return handler


async def _finish_assistant_turn(handler: StepFunRealtimeHandler, text: str) -> None:
    assert handler._active_response is not None
    handler._active_response.text_parts = [text]
    await handler._handle_upstream_response_done(
        {
            "type": "response.done",
            "response": {},
        }
    )
    await _wait_for(lambda: handler._active_response is None and handler.ai_state == "listening")


@pytest.mark.asyncio
async def test_sales_stepfun_reconnect_restores_turn_continuity_and_cleans_terminal_snapshot(
    test_db: AsyncSession,
    test_engine,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    state_service = _InMemoryStateService()
    session = await _create_sales_session(test_db, user=test_user)
    session_id = str(session.session_id)

    session_factory = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    monkeypatch.setattr(stepfun_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(
        stepfun_module.SessionLifecycleService,
        "trigger_report_generation_if_needed",
        AsyncMock(),
    )

    first_ws = _QueueWebSocket()
    first_handler = _prepare_handler(state_service=state_service)
    first_task = asyncio.create_task(
        first_handler.handle_connection(first_ws, session_id, token="test-token")
    )

    await _wait_for(lambda: any(msg.get("type") == "connected" for msg in first_ws.sent_messages))

    await first_ws.push_json({"type": "control", "data": {"action": "start"}})
    await _wait_for(lambda: first_handler.session_status == "in_progress")

    await first_ws.push_json(
        {"type": "text", "data": {"text": "第一轮：先了解一下你们现在的采购流程"}}
    )
    await _wait_for(lambda: first_handler.turn_count == 1 and first_handler._active_response is not None)
    await _finish_assistant_turn(first_handler, "第一轮回复")

    await first_ws.push_json(
        {"type": "text", "data": {"text": "第二轮：目前最大的阻碍是什么"}}
    )
    await _wait_for(lambda: first_handler.turn_count == 2 and first_handler._active_response is not None)
    first_handler._latest_score_snapshot = {"overall_score": 84.0}
    first_handler._latest_action_card = {"title": "继续深挖预算与时机"}
    await _finish_assistant_turn(first_handler, "第二轮回复")

    await first_ws.disconnect()
    await asyncio.wait_for(first_task, timeout=1.0)

    persisted = state_service.snapshots.get(session_id)
    assert persisted is not None
    assert persisted.turn_count == 2
    assert persisted.session_status == "in_progress"
    assert persisted.ai_state == "listening"
    assert persisted.runtime_state["latest_score_snapshot"] == {"overall_score": 84.0}
    assert persisted.runtime_state["latest_action_card"] == {"title": "继续深挖预算与时机"}

    second_ws = _QueueWebSocket()
    second_handler = _prepare_handler(state_service=state_service)
    second_task = asyncio.create_task(
        second_handler.handle_connection(second_ws, session_id, token="test-token")
    )

    await _wait_for(lambda: any(msg.get("type") == "reconnected" for msg in second_ws.sent_messages))
    reconnected_event = next(
        msg for msg in second_ws.sent_messages if msg.get("type") == "reconnected"
    )
    restored_state = reconnected_event["data"]["restored_state"]
    assert restored_state["turn_count"] == 2
    assert restored_state["session_status"] == "in_progress"
    assert restored_state["ai_state"] == "listening"
    assert restored_state["runtime_state"]["latest_score_snapshot"] == {
        "overall_score": 84.0
    }

    await second_ws.push_json(
        {"type": "text", "data": {"text": "第三轮：如果本月就推进，你最看重什么"}}
    )
    await _wait_for(lambda: second_handler.turn_count == 3 and second_handler._active_response is not None)
    await _finish_assistant_turn(second_handler, "第三轮回复")

    await second_ws.push_json({"type": "control", "data": {"action": "end"}})
    await asyncio.wait_for(second_task, timeout=1.0)

    assert second_handler.session_status == "scoring"
    assert session_id not in state_service.snapshots

    async with session_factory() as verify_db:
        persisted_session = await verify_db.scalar(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        assert persisted_session is not None
        assert str(persisted_session.status) == "scoring"

    session_end_event = next(
        msg for msg in second_ws.sent_messages if msg.get("type") == "session_ended"
    )
    assert session_end_event["data"]["session_status"] == "scoring"
    assert session_end_event["data"]["turn_count"] == 3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from common.services.runtime_gate import RuntimeAdmissionDecision
from sales_bot.websocket import router as sales_router
from sales_bot.websocket.phase4_local_provider import Phase4LocalStepFunProvider

SESSION_ID = "11111111-1111-1111-1111-111111111111"


class ContractWebSocket:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.accepted = False
        self.closed: tuple[int, str] | None = None
        self.sent_json: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, *, code: int, reason: str) -> None:
        self.closed = (code, reason)

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)


def _admission_ok() -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=True,
        runtime_type="sales",
        classification="voluntary",
    )


def _admission_rejected() -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=False,
        runtime_type="sales",
        classification="terminal",
        code="RUNTIME_NOT_RUNNABLE",
        close_code=4413,
        close_reason="RUNTIME_NOT_RUNNABLE",
        mark_runtime_failed=True,
    )


def _patch_runnable_sales_session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    user_id: str | None = "user-1",
    owner_id: str | None = "user-1",
) -> None:
    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=_admission_ok()),
    )
    monkeypatch.setattr(sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "token")
    monkeypatch.setattr(
        sales_router,
        "_extract_user_id_from_token",
        lambda _token: user_id,
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_session_owner_id",
        AsyncMock(return_value=owner_id),
    )
    monkeypatch.setattr(sales_router, "_is_admin_user_id", AsyncMock(return_value=False))
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        AsyncMock(),
    )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_sales_websocket_contract_rejects_invalid_session_id() -> None:
    websocket = ContractWebSocket()

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="not-a-uuid",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    assert websocket.accepted is True
    assert websocket.closed == (4400, "INVALID_SESSION_ID")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_sales_websocket_contract_rejects_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = ContractWebSocket()
    _patch_runnable_sales_session(monkeypatch, user_id=None)
    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id=SESSION_ID,
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    assert websocket.accepted is True
    assert websocket.closed == (4001, "Unauthorized")
    handle_stepfun.assert_not_awaited()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_sales_websocket_contract_rejects_admission_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = ContractWebSocket()
    mark_runtime_failed = AsyncMock()
    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=_admission_rejected()),
    )
    monkeypatch.setattr(sales_router, "mark_session_runtime_failed", mark_runtime_failed)
    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id=SESSION_ID,
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    assert websocket.accepted is True
    assert websocket.closed == (4413, "RUNTIME_NOT_RUNNABLE")
    mark_runtime_failed.assert_awaited_once_with(
        SESSION_ID,
        failure_code="RUNTIME_NOT_RUNNABLE",
        source="sales_websocket_reject",
    )
    handle_stepfun.assert_not_awaited()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_sales_websocket_contract_rejects_owner_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = ContractWebSocket()
    _patch_runnable_sales_session(
        monkeypatch,
        user_id="outsider-user",
        owner_id="owner-user",
    )
    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id=SESSION_ID,
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    assert websocket.accepted is True
    assert websocket.closed == (4003, "ACCESS_DENIED")
    handle_stepfun.assert_not_awaited()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_sales_websocket_contract_connects_with_local_stepfun_message_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    websocket = ContractWebSocket()
    _patch_runnable_sales_session(monkeypatch)

    async def handle_with_local_provider(
        websocket: ContractWebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None:
        provider = Phase4LocalStepFunProvider(
            {
                "fixture_version": "sales-ws-contract.test",
                "provider": "phase4_local_stepfun",
                "script": {
                    "user_transcript": "客户问预算。",
                    "assistant_response": "先确认预算范围，再约定下一步。",
                },
            },
            tmp_path / "sales-ws-contract.jsonl",
        )
        await websocket.accept()
        await websocket.send_json({"type": "connected", "session_id": session_id})
        await websocket.send_json({"type": "status", "status": "listening"})
        await provider.send(json.dumps({"type": "input_audio_buffer.commit"}))
        transcript = json.loads(await provider.recv())
        await provider.send(json.dumps({"type": "response.create"}))
        await provider.recv()
        response_delta = json.loads(await provider.recv())
        await websocket.send_json(
            {"type": "asr_transcript", "text": transcript["transcript"]}
        )
        await websocket.send_json({"type": "tts_audio", "text": response_delta["delta"]})
        await provider.close()

    monkeypatch.setattr(
        sales_router,
        "_handle_stepfun_realtime_connection",
        handle_with_local_provider,
    )

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id=SESSION_ID,
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="trace-sales-contract",
    )

    assert websocket.closed is None
    assert [message["type"] for message in websocket.sent_json] == [
        "connected",
        "status",
        "asr_transcript",
        "tts_audio",
    ]
    assert websocket.sent_json[-1]["text"] == "先确认预算范围，再约定下一步。"

"""
Unit tests for sales websocket router behavior.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from common.db.models import PracticeSession, Scenario, User
from common.services.runtime_gate import RuntimeAdmissionDecision
from sales_bot.websocket import router as sales_router
from sales_trainer.services.roleplay_observation_evaluator import (
    ObservationEvaluationResult,
    ObservationEvidence,
    ObservationLLMAudit,
    ObservationSignal,
)
from sales_trainer.services.roleplay_observation_service import (
    RoleplayObservationService,
)


def test_sales_websocket_auth_policy_marks_query_token_as_compatibility_only() -> None:
    assert sales_router.SALES_WS_AUTH_POLICY["formal"] == [
        "authorization_bearer",
        "session_cookie",
    ]
    assert sales_router.SALES_WS_AUTH_POLICY["compatibility"] == ["query_token"]


def test_sales_legacy_handler_modules_stay_deleted() -> None:
    assert importlib.util.find_spec("sales_bot.websocket.base_sales_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.enhanced_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.simple_handler") is None


def patch_kb_lock_gate(
    monkeypatch: pytest.MonkeyPatch, *, is_unbound: bool
) -> AsyncMock:
    kb_lock_gate = AsyncMock(return_value=is_unbound)
    monkeypatch.setattr(
        sales_router,
        "_is_kb_lock_unbound_session",
        kb_lock_gate,
    )
    return kb_lock_gate


def sales_admission_ok() -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=True,
        runtime_type="sales",
        classification="voluntary",
    )


def sales_admission_blocked(
    code: str,
    close_code: int,
) -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=False,
        runtime_type="sales",
        classification="terminal",
        code=code,
        close_code=close_code,
        close_reason=code,
        mark_runtime_failed=True,
    )


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_when_kb_lock_unbound(monkeypatch):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    mark_runtime_failed = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", None, None)),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_blocked("KB_LOCK_UNBOUND", 4410)),
    )
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )

    handle_stepfun = AsyncMock()
    monkeypatch.setattr(
        sales_router, "_handle_stepfun_realtime_connection", handle_stepfun
    )

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4410, reason="KB_LOCK_UNBOUND")
    mark_runtime_failed.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        failure_code="KB_LOCK_UNBOUND",
        source="sales_websocket_reject",
    )
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_kb_lock_unbound_session_uses_runtime_gate_authority(monkeypatch):
    """Sales websocket KB-lock enforcement stays on the shared RuntimeGate seam."""

    class DummyDbSessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db_context = DummyDbSessionContext()
    gate_calls: list[object] = []

    class DummyRuntimeGate:
        def __init__(self, db):
            gate_calls.append(db)

        async def is_kb_lock_unbound_for_session_id(self, session_id: str) -> bool:
            assert session_id == "session-1"
            return True

    monkeypatch.setattr(sales_router, "AsyncSessionLocal", lambda: db_context)
    monkeypatch.setattr(sales_router, "RuntimeGate", DummyRuntimeGate)

    is_unbound = await sales_router._is_kb_lock_unbound_session("session-1")

    assert is_unbound is True
    assert gate_calls == [db_context]


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_invalid_token_before_runtime_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_ok()),
    )
    monkeypatch.setattr(
        sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "invalid-token"
    )
    monkeypatch.setattr(
        sales_router, "_extract_user_id_from_token", lambda _token: None
    )
    mark_runtime_failed = AsyncMock()
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )

    handle_stepfun = AsyncMock()
    monkeypatch.setattr(
        sales_router, "_handle_stepfun_realtime_connection", handle_stepfun
    )

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")
    mark_runtime_failed.assert_not_awaited()
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_legacy_mode_before_runtime_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    mark_runtime_failed = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "legacy", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_ok()),
    )
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )
    handle_stepfun = AsyncMock()
    monkeypatch.setattr(
        sales_router, "_handle_stepfun_realtime_connection", handle_stepfun
    )

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="legacy",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4412,
        reason="LEGACY_SALES_RUNTIME_DISABLED",
    )
    mark_runtime_failed.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        failure_code="LEGACY_SALES_RUNTIME_DISABLED",
        source="sales_websocket_reject",
    )
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_non_owner_before_stepfun_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_ok()),
    )
    monkeypatch.setattr(
        sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "valid-token"
    )
    monkeypatch.setattr(
        sales_router, "_extract_user_id_from_token", lambda _token: "outsider-user"
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_session_owner_id",
        AsyncMock(return_value="owner-user"),
        raising=False,
    )
    monkeypatch.setattr(
        sales_router, "_is_admin_user_id", AsyncMock(return_value=False)
    )
    mark_runtime_failed = AsyncMock()
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )

    handle_stepfun = AsyncMock()
    monkeypatch.setattr(
        sales_router, "_handle_stepfun_realtime_connection", handle_stepfun
    )

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4003, reason="ACCESS_DENIED")
    mark_runtime_failed.assert_not_awaited()
    handle_stepfun.assert_not_awaited()


def _roleplay_observation_user(role: str = "user") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"roleplay-sink-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Roleplay Sink {role}",
        email=f"roleplay-sink-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _roleplay_observation_scenario() -> Scenario:
    return Scenario(
        scenario_id=str(uuid.uuid4()),
        name="新人实时对练",
        description="新人实时对练",
        scenario_type="sales",
    )


def _roleplay_observation_session(
    learner: User,
    scenario: Scenario,
    *,
    roleplay_observation_policy: dict[str, Any] | None = None,
) -> PracticeSession:
    voice_policy_snapshot: dict[str, Any] = {
        "external_binding": {
            "owner": "sales_trainer",
            "path_key": "newcomer_training_path_v1",
            "path_revision_id": "path-rev-1",
            "path_revision_no": 1,
            "module_key": "realtime_roleplay",
            "binding_key": "newcomer_realtime_roleplay_v1",
        }
    }
    if roleplay_observation_policy is not None:
        voice_policy_snapshot["roleplay_observation_policy"] = (
            roleplay_observation_policy
        )
    return PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="in_progress",
        start_time=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        voice_policy_snapshot=voice_policy_snapshot,
    )


class _DbContext:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def __aenter__(self) -> AsyncSession:
        return self._db

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeRoleplayObservationEvaluator:
    def __init__(
        self,
        *,
        llm_status: str,
        llm_error: str | None = None,
        llm_signals: list[ObservationSignal] | None = None,
        completed: asyncio.Event | None = None,
    ) -> None:
        self._llm_status = llm_status
        self._llm_error = llm_error
        self._llm_signals = llm_signals or []
        self._completed = completed

    def evaluate_signals(self, request: dict[str, Any]) -> ObservationEvaluationResult:
        trace_id = str(request["trace_id"])
        heuristic_signal = ObservationSignal(
            key="prompt_leak_risk",
            source="heuristic",
            dimension="instruction_boundary",
            severity="high",
            confidence=0.9,
            evidence=[
                ObservationEvidence(
                    kind="keyword",
                    value="系统提示",
                    metadata={},
                )
            ],
            detector="heuristic.prompt_leak_risk",
            latency_ms=1,
        )
        return ObservationEvaluationResult(
            trace_id=trace_id,
            signals=[heuristic_signal],
            quality_flags=[heuristic_signal.key],
            heuristic_signal_count=1,
            llm_signal_count=0,
            llm=ObservationLLMAudit(
                enabled=False,
                status="disabled",
                trace_id=trace_id,
            ),
            total_latency_ms=1,
        )

    async def evaluate_background(
        self, request: dict[str, Any]
    ) -> ObservationEvaluationResult:
        trace_id = str(request["trace_id"])
        try:
            return ObservationEvaluationResult(
                trace_id=trace_id,
                signals=list(self._llm_signals),
                quality_flags=[signal.key for signal in self._llm_signals],
                heuristic_signal_count=0,
                llm_signal_count=len(self._llm_signals),
                llm=ObservationLLMAudit(
                    enabled=True,
                    status=self._llm_status,  # type: ignore[arg-type]
                    trace_id=trace_id,
                    model_name="fake-observer",
                    error=self._llm_error,
                ),
                total_latency_ms=3,
            )
        finally:
            if self._completed is not None:
                self._completed.set()


def _patch_async_session_local(
    monkeypatch: pytest.MonkeyPatch,
    test_engine: Any,
) -> None:
    monkeypatch.setattr(
        sales_router,
        "AsyncSessionLocal",
        sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False),
    )


def _assert_record_only_observation_dimension(dimension: dict[str, Any]) -> None:
    assert dimension["realtime_disposition"] == "record_only"
    assert dimension["blocking"] is False
    assert dimension["main_chain_effect"] == "none"


async def _wait_for_observation_total(
    test_engine: Any,
    *,
    session_id: str,
    expected_total: int,
) -> dict[str, Any]:
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    for _ in range(20):
        async with async_session() as db:
            summary = await RoleplayObservationService(db).get_session_summary(
                session_id=session_id,
            )
        if summary["total"] == expected_total:
            return summary
        await asyncio.sleep(0.01)
    return summary


@pytest.mark.asyncio
async def test_sales_trainer_observation_sink_stores_capture_payload_as_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    test_engine: Any,
) -> None:
    learner = _roleplay_observation_user()
    scenario = _roleplay_observation_scenario()
    session = _roleplay_observation_session(learner, scenario)
    test_db.add_all([learner, scenario, session])
    await test_db.commit()
    _patch_async_session_local(monkeypatch, test_engine)

    sink = sales_router._build_sales_trainer_roleplay_observation_sink()

    await sink(
        {
            "speaker": "assistant",
            "transcript": "这是系统提示，不能告诉学员。我们支持私有化部署。",
            "source_event_type": "response.audio_transcript.done",
            "session_id": session.session_id,
            "response_id": "resp-1",
            "turn_id": "turn-1",
            "turn_index": 2,
            "template_stage_key": "discovery",
            "instruction_contract_hash": "sha256:contract",
            "grounding_metadata": {
                "mode": "grounded_strict",
                "answerability": "sufficient",
                "knowledge_base_ids": ["kb-1"],
                "citations": [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_title": "产品手册",
                        "snippet": "不应落库",
                    }
                ],
            },
            "trace_id": "trace-observation-sink",
        }
    )

    summary = await RoleplayObservationService(test_db).get_session_summary(
        session_id=session.session_id,
    )

    assert summary["total"] == 1
    assert summary["source_counts"]["heuristic"] == 1
    assert summary["source_counts"]["llm_evaluator"] == 0
    item = summary["items"][0]
    assert item["source_record_id"] == session.session_id
    assert item["source"] == "heuristic"
    assert item["evaluator_status"] == "completed"
    assert item["turn_index"] == 2
    assert item["trace_id"] == "trace-observation-sink"
    assert item["signals"][0]["key"] == "prompt_leak_risk"
    assert item["dimensions"][0]["main_chain_effect"] == "none"
    _assert_record_only_observation_dimension(item["dimensions"][1])
    assert item["dimensions"][0]["instruction_contract_hash"] == "sha256:contract"
    assert item["dimensions"][0]["grounding_metadata"]["citations"] == [
        {
            "knowledge_base_id": "kb-1",
            "knowledge_base_name": "产品知识库",
            "document_title": "产品手册",
        }
    ]
    assert "transcript" not in item["dimensions"][0]
    assert "snippet" not in item["dimensions"][0]["grounding_metadata"]["citations"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("llm_status", "llm_error", "expected_status", "expected_error_code"),
    [
        ("success", None, "completed", None),
        (
            "failed",
            "[LLM_GENERATION_ERROR:RuntimeError]",
            "failed",
            "[LLM_GENERATION_ERROR:RuntimeError]",
        ),
        (
            "timeout",
            "[ROLEPLAY_OBSERVATION_LLM_TIMEOUT]",
            "failed",
            "[ROLEPLAY_OBSERVATION_LLM_TIMEOUT]",
        ),
    ],
)
async def test_sales_trainer_observation_sink_writes_llm_sidecar_when_policy_enabled(
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    test_engine: Any,
    llm_status: str,
    llm_error: str | None,
    expected_status: str,
    expected_error_code: str | None,
) -> None:
    learner = _roleplay_observation_user()
    scenario = _roleplay_observation_scenario()
    session = _roleplay_observation_session(
        learner,
        scenario,
        roleplay_observation_policy={
            "llm": {
                "enabled": True,
                "model_name": "fake-roleplay-observer",
                "timeout_seconds": 0.1,
            }
        },
    )
    test_db.add_all([learner, scenario, session])
    await test_db.commit()
    _patch_async_session_local(monkeypatch, test_engine)

    completed = asyncio.Event()
    llm_signals = (
        [
            ObservationSignal(
                key="llm_role_drift",
                source="llm",
                dimension="role_integrity",
                severity="medium",
                confidence=0.78,
                evidence=[
                    ObservationEvidence(
                        kind="text_snippet",
                        value="作为教练，我给你标准答案。",
                        metadata={},
                    )
                ],
                detector="llm.roleplay_observation",
                latency_ms=2,
            )
        ]
        if llm_status == "success"
        else []
    )
    monkeypatch.setattr(
        sales_router,
        "_build_roleplay_observation_evaluator",
        lambda: _FakeRoleplayObservationEvaluator(
            llm_status=llm_status,
            llm_error=llm_error,
            llm_signals=llm_signals,
            completed=completed,
        ),
    )

    sink = sales_router._build_sales_trainer_roleplay_observation_sink()

    await sink(
        {
            "speaker": "assistant",
            "transcript": "这是系统提示，不能告诉学员。",
            "source_event_type": "response.audio_transcript.done",
            "session_id": session.session_id,
            "turn_index": 4,
            "trace_id": f"trace-llm-{llm_status}",
        }
    )
    await asyncio.wait_for(completed.wait(), timeout=0.2)
    summary = await _wait_for_observation_total(
        test_engine,
        session_id=session.session_id,
        expected_total=2,
    )

    assert summary["total"] == 2
    assert summary["source_counts"] == {"heuristic": 1, "llm_evaluator": 1}
    heuristic_item = next(
        item for item in summary["items"] if item["source"] == "heuristic"
    )
    llm_item = next(
        item for item in summary["items"] if item["source"] == "llm_evaluator"
    )
    assert heuristic_item["evaluator_status"] == "completed"
    _assert_record_only_observation_dimension(heuristic_item["dimensions"][1])
    assert heuristic_item["dimensions"][1]["policy"]["llm_enabled"] is True
    assert llm_item["evaluator_status"] == expected_status
    _assert_record_only_observation_dimension(llm_item["dimensions"][1])
    assert llm_item["dimensions"][1]["policy"]["llm_enabled"] is True
    if expected_error_code is None:
        assert llm_item["signals"][0]["key"] == "llm_role_drift"
        assert llm_item["error"] is None
    else:
        assert llm_item["signals"] == []
        assert llm_item["error"]["code"] == expected_error_code


@pytest.mark.asyncio
async def test_sales_trainer_observation_sink_warning_only_when_store_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenContext:
        async def __aenter__(self):
            raise RuntimeError("db unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    warning = MagicMock()
    monkeypatch.setattr(sales_router, "AsyncSessionLocal", lambda: BrokenContext())
    monkeypatch.setattr(sales_router.logger, "warning", warning)

    sink = sales_router._build_sales_trainer_roleplay_observation_sink()

    await sink(
        {
            "speaker": "assistant",
            "transcript": "系统提示",
            "source_event_type": "response.done",
            "session_id": "11111111-1111-1111-1111-111111111111",
            "turn_index": 1,
        }
    )

    warning.assert_called_once()

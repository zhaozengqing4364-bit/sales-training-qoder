from __future__ import annotations

from typing import Any

import pytest

from common.roleplay_contracts import check_roleplay_output
from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin


class _FailingSinkRoleplayObserver(StepFunRealtimeUpstreamMixin):
    def __init__(self) -> None:
        self._effective_policy: dict[str, Any] = {}
        self.turn_count = 3
        self.persist_attempts = 0

    def _current_sales_stage_code(self) -> str:
        return "discovery"

    def _roleplay_contract(self) -> dict[str, Any]:
        return _roleplay_contract()

    def _roleplay_visible_keys(self, _contract: dict[str, Any]) -> list[str]:
        return ["customer_background"]

    def _roleplay_disclosed_keys(self) -> list[str]:
        return []

    async def _persist_runtime_metrics_to_session(self) -> None:
        self.persist_attempts += 1
        raise RuntimeError("observability sink unavailable")


@pytest.mark.asyncio
async def test_should_record_roleplay_observation_without_blocking_when_sink_fails() -> None:
    observer = _FailingSinkRoleplayObserver()
    decision = {
        "allowed": True,
        "severity": "warning",
        "violation_code": "ROLEPLAY_HEURISTIC_DRIFT",
        "action": "mark_for_report",
        "audit_payload": {"signal_source": "heuristic"},
    }

    await observer._record_roleplay_compliance_decision(
        decision,
        response_id="response-1",
        action_override=None,
    )

    metrics = observer._effective_policy["runtime_metrics"]["roleplay_compliance"]
    assert metrics["violation_count"] == 1
    assert metrics["blocking_violation_count"] == 0
    assert metrics["last_decision"] == decision
    assert metrics["timeline"][0]["action"] == "mark_for_report"
    assert observer.persist_attempts == 1


def test_should_emit_heuristic_hidden_information_signal_without_llm() -> None:
    decision = check_roleplay_output(
        contract=_roleplay_contract(),
        text="上次拜访我们聊过预算，这次直接推进采购。",
        current_visible_keys=["customer_background"],
        current_sales_stage="discovery",
    )

    assert decision["allowed"] is False
    assert decision["severity"] == "blocking"
    assert decision["violation_code"] == "ROLEPLAY_HIDDEN_INFORMATION_LEAK"
    assert decision["action"] in {"regenerate_once", "cancel_stream"}


def _roleplay_contract() -> dict[str, Any]:
    return {
        "schema_version": "roleplay_contract_v1",
        "contract_version": "it_leader_roleplay_v1",
        "audit": {"contract_hash": "sha256:test-contract"},
        "relationship_context": {"has_prior_meeting": False},
        "visible_information_scope": {
            "initial_visible_keys": ["customer_background"],
            "hidden_by_default_keys": ["上次拜访", "预算"],
        },
        "disclosure_policy": {"never_disclose_keys": ["上次拜访"]},
        "sales_stage_policy": {"forbidden_stage_codes": []},
        "runtime_violation_policy": {
            "hidden_information_leak": "cancel_or_regenerate_once",
            "relationship_history_contradiction": "cancel_or_regenerate_once",
        },
    }

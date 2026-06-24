from __future__ import annotations

from typing import Any

import pytest

from sales_bot.websocket.stepfun_realtime_feedback import StepFunRealtimeFeedbackMixin
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler
from sales_bot.websocket.stepfun_realtime_upstream import StepFunRealtimeUpstreamMixin


class DisclosureTrackingUpstream(StepFunRealtimeUpstreamMixin):
    def __init__(self, disclosure_state: dict[str, Any]) -> None:
        self._roleplay_disclosure_state = disclosure_state
        self._effective_policy = {"roleplay_contract": {"schema_version": "test"}}
        self._curriculum_snapshot = {}
        self._latest_stage_data = {"current_stage": "opening"}
        self.persist_calls = 0

    async def _persist_roleplay_disclosure_state(self) -> None:
        self.persist_calls += 1


def test_stepfun_runtime_grounding_entry_resolves_to_upstream_mixin() -> None:
    handler = StepFunRealtimeHandler()

    assert handler._prepare_grounding_context.__func__ is (
        StepFunRealtimeUpstreamMixin._prepare_grounding_context
    )
    assert "_prepare_grounding_context" not in StepFunRealtimeFeedbackMixin.__dict__


@pytest.mark.asyncio
async def test_disclosure_update_skips_persistence_when_state_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"status": "ready", "disclosed_keys": ["company_profile"]}
    upstream = DisclosureTrackingUpstream(state)

    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_upstream.resolve_roleplay_disclosure_state",
        lambda **_kwargs: state,
    )

    await upstream._update_roleplay_disclosure_state(
        learner_message="继续了解公司背景",
        turn_number=2,
        sales_stage="opening",
    )

    assert upstream.persist_calls == 0


@pytest.mark.asyncio
async def test_disclosure_update_persists_when_state_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"status": "ready", "disclosed_keys": ["company_profile"]}
    next_state = {"status": "ready", "disclosed_keys": ["company_profile", "budget"]}
    upstream = DisclosureTrackingUpstream(state)

    monkeypatch.setattr(
        "sales_bot.websocket.stepfun_realtime_upstream.resolve_roleplay_disclosure_state",
        lambda **_kwargs: next_state,
    )

    await upstream._update_roleplay_disclosure_state(
        learner_message="预算怎么安排？",
        turn_number=3,
        sales_stage="discovery",
    )

    assert upstream.persist_calls == 1
    assert upstream._roleplay_disclosure_state == next_state

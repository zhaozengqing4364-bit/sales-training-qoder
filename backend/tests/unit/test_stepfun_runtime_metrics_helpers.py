"""Unit tests for StepFun runtime metrics helper utilities."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sales_bot.websocket.components.stepfun_roleplay_runtime_helpers import (
    V1_ROLEPLAY_RUNTIME_STATE_KEY,
)
from sales_bot.websocket.components.stepfun_runtime_metrics_helpers import (
    apply_knowledge_runtime_metric,
    persist_runtime_metrics_to_session,
)


def _build_ledger_event(*, query: str, status: str, result_count: int) -> dict[str, object]:
    return {
        "attempted_at": "2026-03-28T12:00:00Z",
        "query": query,
        "status": status,
        "result_count": result_count,
        "retrieval_mode": "vector",
        "knowledge_base_ids": ["kb-1"],
        "result_summaries": [
            {
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "score": 0.88,
                "snippet": "命中摘要",
                "retrieval_mode": "vector",
            }
        ],
    }


def test_apply_knowledge_runtime_metric_initializes_updates_metrics_and_appends_ledger():
    effective_policy: dict[str, object] = {}

    metrics = apply_knowledge_runtime_metric(
        effective_policy=effective_policy,
        query="产品定价",
        result_count=2,
        status="hit",
        knowledge_base_ids=["kb-1"],
        top_k=3,
        similarity_threshold=0.65,
        retrieval_mode="vector",
        ledger_event=_build_ledger_event(query="产品定价", status="hit", result_count=2),
    )

    assert metrics["attempt_count"] == 1
    assert metrics["hit_query_count"] == 1
    assert metrics["total_results"] == 2
    assert metrics["last_query"] == "产品定价"
    assert metrics["last_status"] == "hit"
    assert metrics["bound_knowledge_base_ids"] == ["kb-1"]
    assert metrics["last_top_k"] == 3
    assert metrics["last_similarity_threshold"] == 0.65
    assert metrics["last_retrieval_mode"] == "vector"
    assert metrics["mode_counts"]["vector"] == 1
    assert len(metrics["recent_attempts"]) == 1
    assert metrics["recent_attempts"][0]["query"] == "产品定价"


async def test_persist_runtime_metrics_to_session_updates_snapshot_copy_with_bounded_ledger():
    original_snapshot = {"knowledge_base_ids": ["kb-1"]}
    session_obj = SimpleNamespace(
        voice_policy_snapshot=original_snapshot,
        runtime_state={},
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        async def execute(self, _stmt):
            return DummyResult()

        commit = AsyncMock(return_value=None)

    class DummyDbSessionContext:
        def __init__(self):
            self.db = DummyDb()

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    effective_policy = {
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 2,
                "hit_query_count": 1,
                "hit_rate": 0.5,
                "recent_attempts": [
                    _build_ledger_event(query="产品定价", status="hit", result_count=2)
                ],
            }
        }
    }

    updated = await persist_runtime_metrics_to_session(
        session_id="session-test",
        effective_policy=effective_policy,
        session_factory=lambda: DummyDbSessionContext(),
    )

    assert updated is True
    assert session_obj.voice_policy_snapshot is not original_snapshot
    runtime = session_obj.voice_policy_snapshot.get("runtime_metrics", {}).get(
        "knowledge_retrieval", {}
    )
    assert runtime.get("attempt_count") == 2
    assert runtime.get("hit_query_count") == 1
    assert runtime.get("hit_rate") == 0.5
    assert runtime["recent_attempts"][0]["query"] == "产品定价"
    assert session_obj.voice_policy_snapshot.get("knowledge_base_ids") == ["kb-1"]

    effective_policy["runtime_metrics"]["knowledge_retrieval"]["recent_attempts"][0][
        "query"
    ] = "被后续内存更新污染"
    assert runtime["recent_attempts"][0]["query"] == "产品定价"


async def test_persist_runtime_metrics_to_session_updates_v1_runtime_state_patch():
    session_obj = SimpleNamespace(
        voice_policy_snapshot={"roleplay_contract_hash": "sha256:frozen"},
        runtime_state={"existing": {"keep": True}},
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        async def execute(self, _stmt):
            return DummyResult()

        commit = AsyncMock(return_value=None)

    class DummyDbSessionContext:
        def __init__(self):
            self.db = DummyDb()

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    updated = await persist_runtime_metrics_to_session(
        session_id="session-v1",
        effective_policy={
            "roleplay_contract_hash": "sha256:frozen",
            "roleplay_contract": {"contract_version": "it_leader_roleplay_v1"},
            "session_state_card": {
                "schema_version": "session_state_card_v1",
                "version": 2,
                "sequence": 2,
                "current_phase_id": "current_state_discovery",
                "current_phase_type": "roleplay_phase",
                "customer_attitude": "持续追问 PoC 指标",
                "learner_actions_done": ["说明拜访目的"],
                "objections_raised": ["担心影响稳定性"],
                "quality_flags": [],
            },
            "runtime_metrics": {},
        },
        session_factory=lambda: DummyDbSessionContext(),
    )

    assert updated is True
    assert session_obj.runtime_state["existing"] == {"keep": True}
    roleplay_state = session_obj.runtime_state[V1_ROLEPLAY_RUNTIME_STATE_KEY]
    assert roleplay_state["roleplay_contract_hash"] == "sha256:frozen"
    assert roleplay_state["session_state_card"]["version"] == 2
    assert (
        roleplay_state["runtime_observability"]["roleplay_contract_hash"]
        == "sha256:frozen"
    )
    assert roleplay_state["runtime_observability"]["state_card_version"] == 2


async def test_persist_runtime_metrics_to_session_returns_false_without_runtime_metrics():
    updated = await persist_runtime_metrics_to_session(
        session_id="session-test",
        effective_policy={},
    )

    assert updated is False


async def test_persist_runtime_metrics_to_session_rejects_malformed_ledger_without_mutating_original_snapshot():
    original_snapshot = {
        "knowledge_base_ids": ["kb-1"],
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 1,
                "recent_attempts": [
                    _build_ledger_event(query="旧问题", status="miss", result_count=0)
                ],
            }
        },
    }
    frozen_original = deepcopy(original_snapshot)
    session_obj = SimpleNamespace(
        voice_policy_snapshot=original_snapshot,
        runtime_state={},
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        async def execute(self, _stmt):
            return DummyResult()

        commit = AsyncMock(return_value=None)

    class DummyDbSessionContext:
        def __init__(self):
            self.db = DummyDb()

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    updated = await persist_runtime_metrics_to_session(
        session_id="session-test",
        effective_policy={
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 2,
                    "recent_attempts": "not-a-list",
                }
            }
        },
        session_factory=lambda: DummyDbSessionContext(),
    )

    assert updated is False
    assert session_obj.voice_policy_snapshot == frozen_original

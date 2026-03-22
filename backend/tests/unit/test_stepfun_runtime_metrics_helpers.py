"""Unit tests for StepFun runtime metrics helper utilities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from sales_bot.websocket.components.stepfun_runtime_metrics_helpers import (
    apply_knowledge_runtime_metric,
    persist_runtime_metrics_to_session,
)


def test_apply_knowledge_runtime_metric_initializes_and_updates_metrics():
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


async def test_persist_runtime_metrics_to_session_updates_snapshot_copy():
    original_snapshot = {"knowledge_base_ids": ["kb-1"]}
    session_obj = SimpleNamespace(voice_policy_snapshot=original_snapshot)

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
                    "hit_query_count": 1,
                    "hit_rate": 0.5,
                }
            }
        },
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
    assert session_obj.voice_policy_snapshot.get("knowledge_base_ids") == ["kb-1"]


async def test_persist_runtime_metrics_to_session_returns_false_without_runtime_metrics():
    updated = await persist_runtime_metrics_to_session(
        session_id="session-test",
        effective_policy={},
    )

    assert updated is False

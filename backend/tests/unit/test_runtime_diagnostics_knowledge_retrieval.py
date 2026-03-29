"""Unit tests for ledger-aware runtime diagnostics knowledge retrieval fallbacks."""

from __future__ import annotations

from types import SimpleNamespace

from common.conversation.runtime_diagnostics import build_session_runtime_diagnostics


def _session_stub() -> SimpleNamespace:
    return SimpleNamespace(
        session_id="session-ledger-test",
        voice_mode="stepfun_realtime",
        effectiveness_snapshot={},
    )


def _snapshot_with_knowledge_metrics(knowledge_metrics: dict[str, object]) -> dict[str, object]:
    return {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
        },
        "runtime_metrics": {
            "knowledge_retrieval": knowledge_metrics,
        },
    }


def test_build_session_runtime_diagnostics_uses_latest_valid_ledger_entry_for_search_failures_when_flat_fields_missing():
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics(
            {
                "attempt_count": 1,
                "hit_query_count": 0,
                "total_results": 0,
                "recent_attempts": [
                    {
                        "attempted_at": "2026-03-28T12:00:00Z",
                        "query": "ROI 案例",
                        "status": "search_failed",
                        "result_count": 0,
                        "retrieval_mode": "hybrid",
                        "knowledge_base_ids": ["kb-1"],
                        "error_summary": "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout",
                        "result_summaries": [],
                    }
                ],
            }
        ),
    )

    assert diagnostics["status"] == "search_failed"
    assert diagnostics["summary"] == "知识检索触发失败，请检查知识库或 Embedding 服务"
    assert diagnostics["last_status"] == "search_failed"
    assert diagnostics["last_query"] == "ROI 案例"
    assert diagnostics["last_error"] == "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout"
    assert diagnostics["last_result_count"] == 0
    assert diagnostics["last_retrieval_mode"] == "hybrid"
    assert diagnostics["updated_at"] == "2026-03-28T12:00:00Z"


def test_build_session_runtime_diagnostics_ignores_malformed_recent_attempts_and_uses_latest_valid_event():
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics(
            {
                "attempt_count": 2,
                "hit_query_count": 0,
                "total_results": 0,
                "recent_attempts": [
                    "not-a-dict",
                    {"query": "", "status": "", "result_count": "oops"},
                    {
                        "attempted_at": "2026-03-28T12:01:00Z",
                        "query": "竞品对比",
                        "status": "miss",
                        "result_count": 0,
                        "retrieval_mode": "vector",
                        "knowledge_base_ids": ["kb-1"],
                        "result_summaries": [],
                    },
                ],
            }
        ),
    )

    assert diagnostics["status"] == "miss"
    assert diagnostics["last_status"] == "miss"
    assert diagnostics["last_query"] == "竞品对比"
    assert diagnostics["last_result_count"] == 0
    assert diagnostics["last_retrieval_mode"] == "vector"
    assert diagnostics["updated_at"] == "2026-03-28T12:01:00Z"


def test_build_session_runtime_diagnostics_keeps_flat_fields_when_recent_attempts_have_no_valid_entries():
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics(
            {
                "attempt_count": 1,
                "hit_query_count": 0,
                "total_results": 0,
                "last_status": "kb_not_ready",
                "last_query": "产品目录",
                "last_error": "[KB_NOT_READY] still indexing",
                "last_result_count": 0,
                "last_retrieval_mode": "vector",
                "updated_at": "2026-03-28T11:59:00Z",
                "recent_attempts": [None, "broken"],
            }
        ),
    )

    assert diagnostics["status"] == "kb_not_ready"
    assert diagnostics["last_status"] == "kb_not_ready"
    assert diagnostics["last_query"] == "产品目录"
    assert diagnostics["last_error"] == "[KB_NOT_READY] still indexing"
    assert diagnostics["updated_at"] == "2026-03-28T11:59:00Z"

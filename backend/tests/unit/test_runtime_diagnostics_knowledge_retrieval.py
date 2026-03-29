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


# ---------------------------------------------------------------------------
# Tests for build_retrieval_facts — shared retrieval-truth read model
# ---------------------------------------------------------------------------
from common.conversation.runtime_diagnostics import build_retrieval_facts


class TestBuildRetrievalFacts:
    """Comprehensive tests for the shared retrieval-facts read model."""

    # -- None / malformed input ---------------------------------------------------

    def test_returns_none_when_snapshot_is_none(self):
        assert build_retrieval_facts(None) is None

    def test_returns_none_when_snapshot_is_not_dict(self):
        assert build_retrieval_facts("not a dict") is None
        assert build_retrieval_facts(42) is None

    def test_returns_none_when_no_runtime_metrics(self):
        assert build_retrieval_facts({"tool_policy": {}}) is None

    def test_returns_none_when_runtime_metrics_is_not_dict(self):
        assert build_retrieval_facts({"runtime_metrics": "bad"}) is None

    # -- No knowledge_retrieval key ------------------------------------------------

    def test_returns_not_triggered_when_no_knowledge_retrieval_key(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {},
        })
        assert result is not None
        assert result["status"] == "not_triggered"
        assert result["attempt_count"] == 0
        assert result["hit_count"] == 0
        assert result["kb_bound"] is True
        assert result["retrieval_enabled"] is True
        assert result["recent_attempts"] == []
        assert result["latest_attempt"] is None
        assert result["miss_explanation"] is None
        assert result["failure_explanation"] is None

    # -- Hit case ------------------------------------------------------------------

    def test_hit_case_with_result_summaries(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1", "kb-2"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 3,
                    "hit_query_count": 2,
                    "hit_rate": 0.6667,
                    "recent_attempts": [
                        {
                            "attempted_at": "2026-03-28T12:00:00Z",
                            "query": "产品价格",
                            "status": "hit",
                            "result_count": 5,
                            "retrieval_mode": "hybrid",
                            "knowledge_base_ids": ["kb-1"],
                            "result_summaries": [
                                {
                                    "knowledge_base_id": "kb-1",
                                    "knowledge_base_name": "产品手册",
                                    "snippet": "产品A的价格为...",
                                    "score": 0.89,
                                    "retrieval_mode": "hybrid",
                                },
                                {
                                    "knowledge_base_id": "kb-1",
                                    "knowledge_base_name": "产品手册",
                                    "snippet": "价格策略包括...",
                                    "retrieval_mode": "vector",
                                },
                            ],
                            "error_summary": None,
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert result["status"] == "hit"
        assert result["kb_bound"] is True
        assert result["knowledge_base_ids"] == ["kb-1", "kb-2"]
        assert result["knowledge_base_count"] == 2
        assert result["attempt_count"] == 3
        assert result["hit_count"] == 2
        assert result["hit_rate"] == 0.6667
        assert result["miss_explanation"] is None
        assert result["failure_explanation"] is None
        assert result["latest_attempt"] is not None
        assert result["latest_attempt"]["status"] == "hit"
        assert result["latest_attempt"]["knowledge_base_ids"] == ["kb-1"]
        assert len(result["latest_attempt"]["result_summaries"]) == 2
        assert result["latest_attempt"]["result_summaries"][0]["knowledge_base_id"] == "kb-1"
        assert result["latest_attempt"]["result_summaries"][0]["snippet"] == "产品A的价格为..."
        assert result["latest_attempt"]["result_summaries"][0]["score"] == 0.89

    # -- Miss case -----------------------------------------------------------------

    def test_miss_case_with_explanation(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 2,
                    "hit_query_count": 0,
                    "hit_rate": 0.0,
                    "last_status": "miss",
                    "recent_attempts": [
                        {
                            "attempted_at": "2026-03-28T12:01:00Z",
                            "query": "竞品对比分析",
                            "status": "miss",
                            "result_count": 0,
                            "retrieval_mode": "vector",
                            "knowledge_base_ids": ["kb-1"],
                            "result_summaries": [],
                            "error_summary": None,
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert result["status"] == "miss"
        assert result["latest_attempt"] is not None
        assert result["latest_attempt"]["query"] == "竞品对比分析"
        assert result["miss_explanation"] is not None
        assert "竞品对比分析" in result["miss_explanation"]
        assert "补充相关文档" in result["miss_explanation"]
        assert result["failure_explanation"] is None
        # knowledge_base_ids preserved
        assert result["latest_attempt"]["knowledge_base_ids"] == ["kb-1"]
        assert result["latest_attempt"]["result_summaries"] == []

    # -- Failure case --------------------------------------------------------------

    def test_failure_case_with_explanation(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "last_status": "search_failed",
                    "recent_attempts": [
                        {
                            "attempted_at": "2026-03-28T12:02:00Z",
                            "query": "ROI 案例",
                            "status": "search_failed",
                            "result_count": 0,
                            "retrieval_mode": "hybrid",
                            "knowledge_base_ids": ["kb-1"],
                            "error_summary": "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout",
                            "result_summaries": [],
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert result["status"] == "search_failed"
        assert result["failure_explanation"] is not None
        assert "embedding timeout" in result["failure_explanation"]
        assert result["miss_explanation"] is None

    # -- Bounded recent_attempts ---------------------------------------------------

    def test_bounded_recent_attempts_keeps_last_10(self):
        attempts = []
        for i in range(15):
            attempts.append({
                "attempted_at": f"2026-03-28T12:{i:02d}:00Z",
                "query": f"query-{i}",
                "status": "hit" if i % 3 == 0 else "miss",
                "result_count": 1 if i % 3 == 0 else 0,
                "retrieval_mode": "vector",
                "knowledge_base_ids": ["kb-1"],
                "result_summaries": [],
                "error_summary": None,
            })

        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 15,
                    "hit_query_count": 5,
                    "hit_rate": 0.3333,
                    "recent_attempts": attempts,
                },
            },
        })
        assert result is not None
        assert len(result["recent_attempts"]) == 10
        # Should keep the last 10 (indices 5..14)
        assert result["recent_attempts"][0]["query"] == "query-5"
        assert result["recent_attempts"][-1]["query"] == "query-14"

    # -- Malformed entries skipped -------------------------------------------------

    def test_malformed_entries_skipped(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 2,
                    "hit_query_count": 0,
                    "recent_attempts": [
                        "not-a-dict",
                        None,
                        {"status": "", "query": ""},
                        {
                            "attempted_at": "2026-03-28T12:03:00Z",
                            "query": "valid query",
                            "status": "miss",
                            "result_count": 0,
                            "retrieval_mode": "vector",
                            "knowledge_base_ids": ["kb-1"],
                            "result_summaries": [],
                            "error_summary": None,
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert len(result["recent_attempts"]) == 1
        assert result["recent_attempts"][0]["query"] == "valid query"

    # -- Disabled ------------------------------------------------------------------

    def test_disabled_when_internal_retrieval_off(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": False},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 0,
                    "hit_query_count": 0,
                },
            },
        })
        assert result is not None
        assert result["status"] == "disabled"
        assert result["retrieval_enabled"] is False

    # -- No knowledge base ---------------------------------------------------------

    def test_no_knowledge_base(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": [],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 0,
                },
            },
        })
        assert result is not None
        assert result["status"] == "no_knowledge_base"
        assert result["kb_bound"] is False

    # -- KB not ready --------------------------------------------------------------

    def test_kb_not_ready(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 0,
                    "last_status": "kb_not_ready",
                    "last_error": "[KB_NOT_READY] still indexing",
                },
            },
        })
        assert result is not None
        assert result["status"] == "kb_not_ready"

    # -- Miss explanation without query --------------------------------------------

    def test_miss_explanation_fallback_when_no_query(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "last_status": "miss",
                    "recent_attempts": [
                        {
                            "status": "miss",
                            "query": "",
                            "result_count": 0,
                            "knowledge_base_ids": [],
                            "result_summaries": [],
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert result["status"] == "miss"
        assert result["miss_explanation"] is not None
        # Should use the generic fallback (no specific query)
        assert "补充知识库文档" in result["miss_explanation"]

    # -- Knowledge base IDs bounded to 8 in attempt entries -----------------------

    def test_attempt_kb_ids_bounded_to_8(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-main"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 1,
                    "last_status": "hit",
                    "recent_attempts": [
                        {
                            "status": "hit",
                            "query": "test",
                            "result_count": 1,
                            "knowledge_base_ids": [f"kb-{i}" for i in range(15)],
                            "result_summaries": [],
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert len(result["latest_attempt"]["knowledge_base_ids"]) == 8

    # -- Result summaries bounded to 3 and snippet truncated -----------------------

    def test_result_summaries_bounded_and_snippet_truncated(self):
        long_snippet = "A" * 500
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 1,
                    "last_status": "hit",
                    "recent_attempts": [
                        {
                            "status": "hit",
                            "query": "test",
                            "result_count": 5,
                            "knowledge_base_ids": ["kb-1"],
                            "result_summaries": [
                                {
                                    "knowledge_base_id": f"kb-{i}",
                                    "knowledge_base_name": f"KB {i}",
                                    "snippet": long_snippet,
                                    "retrieval_mode": "vector",
                                    "score": 0.9,
                                }
                                for i in range(6)
                            ],
                        },
                    ],
                },
            },
        })
        assert result is not None
        summaries = result["latest_attempt"]["result_summaries"]
        assert len(summaries) == 3  # bounded to 3
        assert len(summaries[0]["snippet"]) == 240  # truncated to 240 chars

    # -- Failure explanation fallback when no error_summary ------------------------

    def test_failure_explanation_fallback(self):
        result = build_retrieval_facts({
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"enable_internal_retrieval": True},
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "last_status": "search_failed",
                    "last_error": "[KNOWLEDGE_SEARCH_UNAVAILABLE]",
                    "recent_attempts": [
                        {
                            "status": "search_failed",
                            "query": "test",
                            "result_count": 0,
                            "knowledge_base_ids": ["kb-1"],
                            "result_summaries": [],
                            # error_summary intentionally missing
                        },
                    ],
                },
            },
        })
        assert result is not None
        assert result["status"] == "search_failed"
        assert result["failure_explanation"] is not None
        assert "Embedding 服务" in result["failure_explanation"]


# ---------------------------------------------------------------------------
# Tests for retrieval_facts passthrough in build_session_runtime_diagnostics
# (T03: knowledge-check reuses projected retrieval_facts)
# ---------------------------------------------------------------------------


def _projection_with_retrieval_facts() -> dict[str, object]:
    """A completed-session projection snapshot containing retrieval_facts."""
    return {
        "retrieval_facts": {
            "kb_bound": True,
            "knowledge_base_ids": ["kb-1"],
            "knowledge_base_count": 1,
            "retrieval_enabled": True,
            "status": "hit",
            "summary": "知识检索已触发并命中知识库",
            "attempt_count": 3,
            "hit_count": 2,
            "hit_rate": 0.6667,
            "latest_attempt": {
                "status": "hit",
                "query": "产品价格",
                "result_count": 5,
                "retrieval_mode": "hybrid",
                "knowledge_base_ids": ["kb-1"],
                "result_summaries": [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品手册",
                        "snippet": "产品A的价格为...",
                        "retrieval_mode": "hybrid",
                        "score": 0.89,
                    },
                ],
                "attempted_at": "2026-03-28T12:00:00Z",
                "error_summary": None,
            },
            "recent_attempts": [],
            "miss_explanation": None,
            "failure_explanation": None,
        },
    }


def test_diagnostics_reuses_projection_retrieval_facts_for_completed_session():
    """Completed session: retrieval_facts from projection appear verbatim in diagnostics output."""
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics(
            {
                "attempt_count": 3,
                "hit_query_count": 2,
                "hit_rate": 0.6667,
                "last_status": "hit",
                "last_query": "产品价格",
            }
        ),
        live_runtime_active=False,
        projection_effectiveness_snapshot=_projection_with_retrieval_facts(),
    )

    rf = diagnostics["retrieval_facts"]
    assert rf is not None
    assert rf["status"] == "hit"
    assert rf["kb_bound"] is True
    assert rf["knowledge_base_ids"] == ["kb-1"]
    assert rf["attempt_count"] == 3
    assert rf["hit_count"] == 2
    assert rf["latest_attempt"]["query"] == "产品价格"
    assert len(rf["latest_attempt"]["result_summaries"]) == 1
    assert rf["latest_attempt"]["result_summaries"][0]["score"] == 0.89


def test_diagnostics_returns_none_retrieval_facts_for_live_session():
    """Live session: retrieval_facts should be None regardless of projection content."""
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics({"attempt_count": 1}),
        live_runtime_active=True,
        projection_effectiveness_snapshot=_projection_with_retrieval_facts(),
    )

    assert diagnostics["retrieval_facts"] is None


def test_diagnostics_preserves_backward_compatible_fields_with_retrieval_facts():
    """When retrieval_facts is present, all existing fields are still correct."""
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics(
            {
                "attempt_count": 2,
                "hit_query_count": 1,
                "total_results": 5,
                "last_status": "hit",
                "last_query": "测试查询",
                "last_result_count": 3,
                "last_retrieval_mode": "hybrid",
                "updated_at": "2026-03-28T12:00:00Z",
                "recent_queries": ["测试查询", "上一次查询"],
            }
        ),
        live_runtime_active=False,
        projection_effectiveness_snapshot=_projection_with_retrieval_facts(),
    )

    # retrieval_facts present
    assert diagnostics["retrieval_facts"] is not None

    # Existing backward-compatible fields still correct
    assert diagnostics["session_id"] == "session-ledger-test"
    assert diagnostics["voice_mode"] == "stepfun_realtime"
    assert diagnostics["status"] == "hit"
    assert diagnostics["summary"] == "知识检索已触发并命中知识库"
    assert diagnostics["attempt_count"] == 2
    assert diagnostics["hit_query_count"] == 1
    assert diagnostics["total_results"] == 5
    assert diagnostics["last_query"] == "测试查询"
    assert diagnostics["last_result_count"] == 3
    assert diagnostics["last_retrieval_mode"] == "hybrid"
    assert diagnostics["updated_at"] == "2026-03-28T12:00:00Z"
    assert diagnostics["recent_queries"] == ["测试查询", "上一次查询"]
    assert diagnostics["kb_bound"] is True
    assert diagnostics["internal_retrieval_enabled"] is True
    assert diagnostics["upstream_unstable"] is False


def test_diagnostics_ignores_retrieval_facts_in_projection_for_live_session():
    """Even when projection has retrieval_facts, a live session returns None.

    Live session truth comes from the live handler, not the projection overlay.
    """
    diagnostics = build_session_runtime_diagnostics(
        session=_session_stub(),
        snapshot=_snapshot_with_knowledge_metrics(
            {"attempt_count": 5, "hit_query_count": 3, "last_status": "hit"}
        ),
        live_runtime_active=True,
        projection_effectiveness_snapshot=_projection_with_retrieval_facts(),
    )

    # Live session must not carry projection retrieval_facts
    assert diagnostics["retrieval_facts"] is None

    # But other fields derived from live snapshot should still work
    assert diagnostics["attempt_count"] == 5
    assert diagnostics["hit_query_count"] == 3
    assert diagnostics["last_status"] == "hit"


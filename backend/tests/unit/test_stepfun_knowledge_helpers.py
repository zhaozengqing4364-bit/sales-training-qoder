"""Unit tests for StepFun knowledge helper utilities."""

from __future__ import annotations

import pytest

from common.knowledge.retrieval_helpers import (
    build_answerability_assessment,
    build_rewritten_queries,
)
from sales_bot.websocket.components.stepfun_helpers import (
    ensure_knowledge_runtime_metrics,
    update_knowledge_runtime_metrics,
)
from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    build_kb_not_ready_payload,
    build_knowledge_retrieval_ledger_event,
    build_missing_query_payload,
    build_no_kb_payload,
    build_search_failed_payload,
    is_entity_focused_query,
    merge_runtime_metrics_snapshot,
    normalize_knowledge_base_ids,
    normalize_query,
    resolve_grounding_context_limits,
    resolve_metadata_filter,
    resolve_rerank_params,
    resolve_retrieval_params,
    transform_search_rows,
)


def test_normalize_query_and_kb_ids():
    assert normalize_query({"query": "  产品是什么  "}) == "产品是什么"
    assert normalize_query({}) == ""

    ids = normalize_knowledge_base_ids({"knowledge_base_ids": ["kb-1", "", None, 2]})
    assert ids == ["kb-1", "2"]
    assert normalize_knowledge_base_ids({"knowledge_base_ids": "invalid"}) == []


def test_resolve_retrieval_params_with_defaults_and_invalid_values():
    top_k, threshold, enable_hybrid, keyword_limit = resolve_retrieval_params({}, {})
    assert top_k == 5
    assert threshold == 0.58
    assert enable_hybrid is True
    assert keyword_limit == 32


def test_build_rewritten_queries_expands_configured_asr_aliases_without_hardcoding():
    variants = build_rewritten_queries(
        "帮我介绍一下石溪科技",
        tool_policy={
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["石溪", "实习"],
                }
            ]
        },
    )

    assert variants[0] == "帮我介绍一下石溪科技"
    assert "帮我介绍一下石犀科技" in variants


def test_build_rewritten_queries_expands_canonical_to_alias_variants_for_legacy_docs():
    variants = build_rewritten_queries(
        "石犀科技报价",
        tool_policy={
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["石溪"],
                }
            ]
        },
    )

    assert "石溪科技报价" in variants

    top_k, threshold, enable_hybrid, keyword_limit = resolve_retrieval_params(
        {"top_k": "x"},
        {
            "retrieval_similarity_threshold": "oops",
            "retrieval_enable_hybrid": False,
            "retrieval_keyword_candidate_limit": "bad",
        },
    )
    assert top_k == 5
    assert threshold == 0.58
    assert enable_hybrid is False
    assert keyword_limit == 32


def test_answerability_blocks_hits_that_do_not_support_query_terms():
    assessment = build_answerability_assessment(
        query="介绍一下实习成绩",
        results=[
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技产品手册",
                "snippet": "石犀科技是成都本土的智慧城市解决方案提供商。",
                "score": 0.93,
            },
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技能力说明",
                "snippet": "石犀科技提供销售训练、角色扮演和复盘评分能力。",
                "score": 0.9,
            }
        ],
        source_status="hit",
        strict_kb_mode=True,
        rewritten_queries=["介绍一下实习成绩"],
    )

    assert assessment["answerability"] == "insufficient"
    assert assessment["evidence_supported"] is False


def test_answerability_accepts_evidence_supported_by_configured_asr_alias_variant():
    rewritten_queries = build_rewritten_queries(
        "介绍一下实习科技",
        tool_policy={
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["实习"],
                }
            ]
        },
    )

    assessment = build_answerability_assessment(
        query="介绍一下实习科技",
        results=[
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技产品手册",
                "snippet": "石犀科技是成都本土的智慧城市解决方案提供商。",
                "score": 0.93,
            },
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技能力说明",
                "snippet": "石犀科技提供销售训练、角色扮演和复盘评分能力。",
                "score": 0.9,
            }
        ],
        source_status="hit",
        strict_kb_mode=True,
        rewritten_queries=rewritten_queries,
    )

    assert "介绍一下石犀科技" in rewritten_queries
    assert assessment["evidence_supported"] is True
    assert assessment["answerability"] == "sufficient"


def test_resolve_retrieval_params_applies_entity_query_adaptation():
    top_k, threshold, _, _ = resolve_retrieval_params(
        {},
        {"retrieval_top_k": 4, "retrieval_similarity_threshold": 0.65},
        query="石犀S3产品参数",
    )

    assert top_k == 6
    assert threshold == 0.57


def test_resolve_metadata_filter_from_arguments_and_policy():
    metadata_filter = resolve_metadata_filter(
        {
            "metadata_filter": {
                "product_line": "enterprise",
                "regions": ["cn", "", None, "sg"],
                "empty": "   ",
            }
        },
        {},
    )

    assert metadata_filter == {"product_line": "enterprise", "regions": ["cn", "sg"]}

    from_policy = resolve_metadata_filter(
        {},
        {
            "retrieval_metadata_filter": {
                "tenant": 7,
                "tiers": [1, 2, None],
            }
        },
    )
    assert from_policy == {"tenant": 7, "tiers": [1, 2]}


def test_build_special_payloads():
    assert build_missing_query_payload()["message"] == "缺少 query 参数"
    assert build_no_kb_payload("问句")["message"] == "当前会话未关联内部知识库"
    assert (
        build_kb_not_ready_payload("问句")["message"]
        == "内部知识库文档尚未处理完成，请稍后重试"
    )
    failed = build_search_failed_payload("问句", "err")
    assert failed["message"] == "知识检索失败"
    assert failed["error"] == "err"


def test_transform_search_rows_and_keyword_fallback_status():
    rows = [
        {
            "knowledge_base_id": "kb-1",
            "knowledge_base_name": "KB1",
            "content": "A" * 300,
            "score": 0.9,
            "retrieval_mode": "keyword_fallback",
        }
    ]
    results, mode, status = transform_search_rows(rows, top_k=3)

    assert len(results) == 1
    assert len(results[0]["snippet"]) == 220
    assert results[0]["retrieval_mode"] == "keyword_fallback"
    assert mode == "keyword_fallback"
    assert status == "hit_keyword_fallback"


def test_merge_runtime_metrics_snapshot_returns_new_object():
    base = {"knowledge_base_ids": ["kb-1"]}
    runtime = {"knowledge_retrieval": {"attempt_count": 2, "hit_rate": 0.5}}

    merged = merge_runtime_metrics_snapshot(
        base_snapshot=base,
        runtime_metrics=runtime,
    )

    assert merged is not None
    assert merged is not base
    assert merged["knowledge_base_ids"] == ["kb-1"]
    assert merged["runtime_metrics"]["knowledge_retrieval"]["attempt_count"] == 2


def test_merge_runtime_metrics_snapshot_returns_none_without_knowledge_metrics():
    assert (
        merge_runtime_metrics_snapshot(
            base_snapshot={},
            runtime_metrics={"other": {}},
        )
        is None
    )


def test_transform_search_rows_hybrid_mode():
    rows = [
        {
            "knowledge_base_id": "kb-1",
            "knowledge_base_name": "KB1",
            "content": "混合检索结果",
            "score": 0.93,
            "retrieval_mode": "hybrid",
        }
    ]
    results, mode, status = transform_search_rows(rows, top_k=2)

    assert len(results) == 1
    assert results[0]["retrieval_mode"] == "hybrid"
    assert mode == "hybrid"
    assert status == "hit"


def test_transform_search_rows_uses_wider_snippet_for_entity_query():
    rows = [
        {
            "knowledge_base_id": "kb-1",
            "knowledge_base_name": "KB1",
            "content": "B" * 500,
            "score": 0.91,
            "retrieval_mode": "vector",
        }
    ]
    results, _, _ = transform_search_rows(rows, top_k=3, query="石犀S3参数")

    assert len(results) == 1
    assert len(results[0]["snippet"]) == 360


def test_entity_query_helpers():
    assert is_entity_focused_query("石犀S3价格") is True
    assert (
        is_entity_focused_query("请你帮我分析今天这段很长的销售对话哪里有问题") is False
    )
    assert is_entity_focused_query("竞品A价格更低时，你们有什么客户案例证明ROI？") is True

    assert resolve_grounding_context_limits("石犀S3价格") == (6, 420)


def test_resolve_retrieval_params_expands_sales_objection_queries():
    top_k, threshold, _, keyword_limit = resolve_retrieval_params(
        {},
        {
            "retrieval_top_k": 4,
            "retrieval_similarity_threshold": 0.66,
            "retrieval_keyword_candidate_limit": 24,
        },
        query="竞品A价格更低时，你们有什么客户案例证明ROI？",
    )

    assert top_k == 7
    assert threshold == 0.56
    assert keyword_limit == 48


def test_transform_search_rows_uses_wider_snippet_for_sales_objection_query():
    rows = [
        {
            "knowledge_base_id": "kb-1",
            "knowledge_base_name": "KB1",
            "content": "C" * 600,
            "score": 0.91,
            "retrieval_mode": "hybrid",
        }
    ]

    results, _, _ = transform_search_rows(
        rows,
        top_k=4,
        query="竞品A价格更低时，你们有什么客户案例证明ROI？",
    )

    assert len(results) == 1
    assert len(results[0]["snippet"]) == 420


@pytest.mark.parametrize(
    "query",
    [
        "你拿什么证明这个ROI不是口号？",
        "预算卡死时这笔报价怎么回本？",
        "竞品A更便宜，为什么还要换你们？",
        "上线风险这么高，你们怎么保证试点负责人和排期？",
    ],
)
def test_sales_objection_queries_expand_helper_limits_across_roi_price_competitor_and_implementation_cases(
    query: str,
):
    top_k, threshold, _, keyword_limit = resolve_retrieval_params(
        {},
        {
            "retrieval_top_k": 4,
            "retrieval_similarity_threshold": 0.66,
            "retrieval_keyword_candidate_limit": 24,
        },
        query=query,
    )
    results, _, _ = transform_search_rows(
        [
            {
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "KB1",
                "content": "D" * 640,
                "score": 0.91,
                "retrieval_mode": "hybrid",
            }
        ],
        top_k=4,
        query=query,
    )

    assert top_k == 7
    assert threshold == 0.56
    assert keyword_limit == 48
    assert len(results) == 1
    assert len(results[0]["snippet"]) == 420


def test_build_knowledge_retrieval_ledger_event_normalizes_and_bounds_result_summaries():
    event = build_knowledge_retrieval_ledger_event(
        query="  竞品A   价格 更低  ",
        status="hit",
        result_count=5,
        retrieval_mode="hybrid",
        knowledge_base_ids=["kb-1", "", None, "kb-2"],
        error_message="  embedding timeout  ",
        results=[
            {
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "score": 0.91,
                "snippet": "A" * 400,
                "retrieval_mode": "hybrid",
                "raw_payload": {"provider": "stepfun"},
            },
            {
                "knowledge_base_id": "kb-2",
                "knowledge_base_name": "案例库",
                "score": "0.87",
                "snippet": "B" * 32,
                "retrieval_mode": "vector",
            },
            {
                "knowledge_base_id": "kb-3",
                "knowledge_base_name": "FAQ",
                "score": 0.51,
                "snippet": "C" * 32,
                "retrieval_mode": "keyword_fallback",
            },
            {
                "knowledge_base_id": "kb-4",
                "knowledge_base_name": "raw-row-should-be-trimmed-by-cap",
                "score": 0.49,
                "snippet": "D" * 32,
                "retrieval_mode": "vector",
            },
            {
                "content": "raw provider row should be rejected",
                "score": 0.99,
            },
        ],
    )

    assert event["query"] == "竞品A 价格 更低"
    assert event["status"] == "hit"
    assert event["result_count"] == 5
    assert event["retrieval_mode"] == "hybrid"
    assert event["knowledge_base_ids"] == ["kb-1", "kb-2"]
    assert event["error_summary"] == "embedding timeout"
    assert len(event["result_summaries"]) == 3
    assert len(event["result_summaries"][0]["snippet"]) <= 240
    assert "raw_payload" not in event["result_summaries"][0]
    assert event["result_summaries"][2]["knowledge_base_id"] == "kb-3"


def test_update_knowledge_runtime_metrics_caps_recent_attempt_ledger():
    effective_policy: dict[str, object] = {}
    metrics = ensure_knowledge_runtime_metrics(effective_policy)

    for index in range(12):
        update_knowledge_runtime_metrics(
            metrics,
            query=f"问题 {index}",
            result_count=index % 2,
            status="hit" if index % 2 else "miss",
            knowledge_base_ids=["kb-1"],
            ledger_event={
                "attempted_at": f"2026-03-28T12:00:{index:02d}Z",
                "query": f"问题 {index}",
                "status": "hit" if index % 2 else "miss",
                "result_count": index % 2,
                "retrieval_mode": "vector",
                "result_summaries": [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "score": 0.8,
                        "snippet": "命中摘要",
                        "retrieval_mode": "vector",
                    }
                ],
            },
        )

    assert len(metrics["recent_attempts"]) == 10
    assert metrics["recent_attempts"][0]["query"] == "问题 2"
    assert metrics["recent_attempts"][-1]["query"] == "问题 11"


def test_resolve_rerank_params_with_defaults_and_invalid_values():
    enabled, top_k = resolve_rerank_params({})
    assert enabled is True
    assert top_k == 8

    enabled, top_k = resolve_rerank_params(
        {
            "retrieval_enable_rerank": False,
            "retrieval_rerank_top_k": "bad",
        }
    )
    assert enabled is False
    assert top_k == 8

"""Unit tests for StepFun knowledge helper utilities."""

from __future__ import annotations

from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    build_kb_not_ready_payload,
    build_missing_query_payload,
    build_no_kb_payload,
    build_search_failed_payload,
    is_entity_focused_query,
    merge_runtime_metrics_snapshot,
    normalize_knowledge_base_ids,
    normalize_query,
    resolve_grounding_context_limits,
    resolve_metadata_filter,
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
    assert threshold == 0.65
    assert enable_hybrid is True
    assert keyword_limit == 32

    top_k, threshold, enable_hybrid, keyword_limit = resolve_retrieval_params(
        {"top_k": "x"},
        {
            "retrieval_similarity_threshold": "oops",
            "retrieval_enable_hybrid": False,
            "retrieval_keyword_candidate_limit": "bad",
        },
    )
    assert top_k == 5
    assert threshold == 0.65
    assert enable_hybrid is False
    assert keyword_limit == 32


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

    assert resolve_grounding_context_limits("石犀S3价格") == (5, 360)

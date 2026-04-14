from __future__ import annotations

import pytest

from common.knowledge_engine.config_repo import KnowledgeRankingProfileConfig
from common.knowledge_engine.reranker import KnowledgeReranker


def test_reranker_prioritizes_title_entity_doc_type_section_and_exposes_breakdown():
    reranker = KnowledgeReranker(
        ranking_profiles={
            "product_overview": KnowledgeRankingProfileConfig(
                profile_key="product_overview",
                title_exact_boost=0.25,
                entity_match_boost=0.2,
                doc_type_weights={"product": 0.18, "faq": 0.05},
                section_weights={"overview": 0.14, "pricing": 0.02},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
            )
        }
    )

    ranked = reranker.rerank(
        rows=[
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技产品介绍",
                "content": "石犀科技是一家销售训练平台，支持企业训练。",
                "score": 0.52,
                "retrieval_mode": "hybrid",
                "metadata": {"doc_type": "product", "section": "overview"},
            },
            {
                "knowledge_base_id": "kb-1",
                "document_title": "常见问题",
                "content": "平台也支持企业训练。",
                "score": 0.66,
                "retrieval_mode": "hybrid",
                "metadata": {"doc_type": "faq", "section": "pricing"},
            },
        ],
        profile_key="product_overview",
        query="请介绍一下石犀科技",
        normalized_query="请介绍一下石犀科技",
        resolved_entities=["石犀科技"],
        top_k=2,
    )

    assert [item["document_title"] for item in ranked] == ["石犀科技产品介绍"]
    breakdown = ranked[0]["score_breakdown"]
    assert breakdown["base_score"] == pytest.approx(0.52)
    assert breakdown["title_exact"] == pytest.approx(0.25)
    assert breakdown["entity_match"] == pytest.approx(0.2)
    assert breakdown["doc_type"] == pytest.approx(0.18)
    assert breakdown["section"] == pytest.approx(0.14)
    assert breakdown["diversity_penalty"] == pytest.approx(0.0)
    assert ranked[0]["ranking_passed"] is True


def test_reranker_penalizes_duplicate_titles_and_applies_keyword_threshold():
    reranker = KnowledgeReranker(
        ranking_profiles={
            "product_overview": KnowledgeRankingProfileConfig(
                profile_key="product_overview",
                title_exact_boost=0.2,
                entity_match_boost=0.15,
                doc_type_weights={"product": 0.1},
                section_weights={"overview": 0.05},
                min_pass_score=0.6,
                min_pass_score_keyword=0.4,
            )
        }
    )

    ranked = reranker.rerank(
        rows=[
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技产品介绍",
                "content": "石犀科技是一家销售训练平台。",
                "score": 0.36,
                "retrieval_mode": "keyword_fallback",
                "metadata": {"doc_type": "product", "section": "overview"},
            },
            {
                "knowledge_base_id": "kb-1",
                "document_title": "石犀科技产品介绍",
                "content": "石犀科技帮助团队完成销售演练。",
                "score": 0.34,
                "retrieval_mode": "keyword_fallback",
                "metadata": {"doc_type": "product", "section": "overview"},
            },
        ],
        profile_key="product_overview",
        query="介绍一下石犀科技",
        normalized_query="介绍一下石犀科技",
        resolved_entities=["石犀科技"],
        top_k=2,
    )

    assert len(ranked) == 1
    assert ranked[0]["document_title"] == "石犀科技产品介绍"
    assert ranked[0]["ranking_passed"] is True
    assert ranked[0]["score_breakdown"]["diversity_penalty"] == pytest.approx(0.0)



def test_reranker_returns_input_order_when_profile_missing():
    reranker = KnowledgeReranker(ranking_profiles={})
    rows = [
        {"document_title": "A", "score": 0.2, "metadata": {}},
        {"document_title": "B", "score": 0.1, "metadata": {}},
    ]

    ranked = reranker.rerank(
        rows=rows,
        profile_key="missing",
        query="介绍一下",
        normalized_query="介绍一下",
        resolved_entities=[],
        top_k=2,
    )

    assert [item["document_title"] for item in ranked] == ["A", "B"]
    assert all(item["score_breakdown"]["strategy"] == "passthrough" for item in ranked)

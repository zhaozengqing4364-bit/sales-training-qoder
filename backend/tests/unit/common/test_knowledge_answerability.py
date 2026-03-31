from __future__ import annotations

import pytest

from common.knowledge_engine.answerability import KnowledgeAnswerabilityEvaluator
from common.knowledge_engine.config_repo import KnowledgeAnswerabilityProfileConfig
from common.knowledge_engine.haystack_adapter import (
    KnowledgeExecutedQueryStep,
    KnowledgeHaystackExecutionResult,
)


class TestKnowledgeAnswerabilityEvaluator:
    def test_marks_sufficient_when_all_required_slots_are_covered_and_optional_pushes_total_over_threshold(self):
        evaluator = KnowledgeAnswerabilityEvaluator(
            answerability_profiles={
                "product_overview": KnowledgeAnswerabilityProfileConfig(
                    profile_key="product_overview",
                    required_slots=["definition", "capability"],
                    optional_slots=["use_case"],
                    sufficient_threshold=1.0,
                    partial_threshold=0.5,
                )
            }
        )

        result = evaluator.evaluate(
            profile_key="product_overview",
            rows=[
                {
                    "document_title": "产品手册",
                    "snippet": "石犀科技是一款企业销售训练平台，可用于新员工带教。",
                    "slot_hits": ["definition", "use_case"],
                },
                {
                    "document_title": "能力说明",
                    "content": "平台支持角色扮演演练、话术复盘与评分。",
                    "slot_hits": ["capability"],
                },
            ],
            execution_result=KnowledgeHaystackExecutionResult(
                rows=[],
                executed_steps=[
                    KnowledgeExecutedQueryStep(
                        query="石犀科技 产品介绍",
                        stage="primary",
                        profile_key="product_overview",
                        status="hit",
                        hit_count=2,
                        retrieval_modes=["hybrid"],
                    )
                ],
                search_failures=[],
                stopped_early=True,
            ),
        )

        assert result.answerability == "sufficient"
        assert result.source_status == "ready"
        assert result.covered_required_slots == ["definition", "capability"]
        assert result.missing_required_slots == []
        assert result.covered_optional_slots == ["use_case"]
        assert result.coverage["required_ratio"] == pytest.approx(1.0)
        assert result.coverage["optional_ratio"] == pytest.approx(1.0)
        assert result.coverage["overall_ratio"] == pytest.approx(1.0)
        assert result.audit["hit_count"] == 2
        assert result.audit["executed_query_count"] == 1

    def test_marks_partial_when_only_some_required_slots_are_covered_even_if_hits_exist(self):
        evaluator = KnowledgeAnswerabilityEvaluator(
            answerability_profiles={
                "product_overview": KnowledgeAnswerabilityProfileConfig(
                    profile_key="product_overview",
                    required_slots=["definition", "capability"],
                    optional_slots=["use_case"],
                    sufficient_threshold=1.0,
                    partial_threshold=0.5,
                )
            }
        )

        result = evaluator.evaluate(
            profile_key="product_overview",
            rows=[
                {
                    "document_title": "产品手册",
                    "snippet": "石犀科技是一款企业销售训练平台。",
                    "slot_hits": ["definition"],
                },
                {
                    "document_title": "FAQ",
                    "snippet": "也可配合培训场景使用。",
                    "slot_hits": [],
                },
            ],
            execution_result=KnowledgeHaystackExecutionResult(
                rows=[],
                executed_steps=[
                    KnowledgeExecutedQueryStep(
                        query="石犀科技 产品介绍",
                        stage="primary",
                        profile_key="product_overview",
                        status="hit",
                        hit_count=2,
                        retrieval_modes=["hybrid"],
                    )
                ],
                search_failures=[],
                stopped_early=False,
            ),
        )

        assert result.answerability == "partial"
        assert result.source_status == "ready"
        assert result.covered_required_slots == ["definition"]
        assert result.missing_required_slots == ["capability"]
        assert result.coverage["required_ratio"] == pytest.approx(0.5)
        assert result.coverage["overall_ratio"] == pytest.approx(1 / 3)
        assert result.audit["matched_slot_count"] == 1

    def test_marks_insufficient_when_hits_exist_but_required_slots_do_not_reach_partial_threshold(self):
        evaluator = KnowledgeAnswerabilityEvaluator(
            answerability_profiles={
                "product_overview": KnowledgeAnswerabilityProfileConfig(
                    profile_key="product_overview",
                    required_slots=["definition", "capability"],
                    optional_slots=["use_case"],
                    sufficient_threshold=1.0,
                    partial_threshold=0.6,
                )
            }
        )

        result = evaluator.evaluate(
            profile_key="product_overview",
            rows=[
                {
                    "document_title": "FAQ",
                    "snippet": "适合 onboarding 场景。",
                    "slot_hits": ["use_case"],
                }
            ],
            execution_result=KnowledgeHaystackExecutionResult(
                rows=[],
                executed_steps=[
                    KnowledgeExecutedQueryStep(
                        query="石犀科技 产品介绍",
                        stage="primary",
                        profile_key="product_overview",
                        status="hit",
                        hit_count=1,
                        retrieval_modes=["keyword_fallback"],
                    )
                ],
                search_failures=[],
                stopped_early=False,
            ),
        )

        assert result.answerability == "insufficient"
        assert result.source_status == "ready"
        assert result.covered_required_slots == []
        assert result.missing_required_slots == ["definition", "capability"]
        assert result.covered_optional_slots == ["use_case"]
        assert result.coverage["required_ratio"] == pytest.approx(0.0)
        assert result.coverage["overall_ratio"] == pytest.approx(1 / 3)

    def test_marks_blocked_when_retrieval_failed_before_any_slot_could_be_covered(self):
        evaluator = KnowledgeAnswerabilityEvaluator(
            answerability_profiles={
                "product_overview": KnowledgeAnswerabilityProfileConfig(
                    profile_key="product_overview",
                    required_slots=["definition", "capability"],
                    optional_slots=["use_case"],
                    sufficient_threshold=1.0,
                    partial_threshold=0.5,
                )
            }
        )

        result = evaluator.evaluate(
            profile_key="product_overview",
            rows=[],
            execution_result=KnowledgeHaystackExecutionResult(
                rows=[],
                executed_steps=[
                    KnowledgeExecutedQueryStep(
                        query="石犀科技 产品介绍",
                        stage="primary",
                        profile_key="product_overview",
                        status="failed",
                        error="[KNOWLEDGE_SEARCH_UNAVAILABLE] timeout",
                    )
                ],
                search_failures=["[KNOWLEDGE_SEARCH_UNAVAILABLE] timeout"],
                stopped_early=False,
            ),
        )

        assert result.answerability == "blocked"
        assert result.source_status == "blocked"
        assert result.covered_required_slots == []
        assert result.missing_required_slots == ["definition", "capability"]
        assert result.audit["blocked_reason"] == "retrieval_failed"
        assert result.audit["search_failures"] == ["[KNOWLEDGE_SEARCH_UNAVAILABLE] timeout"]

    def test_falls_back_to_hit_count_when_profile_is_missing_so_existing_callers_can_degrade_safely(self):
        evaluator = KnowledgeAnswerabilityEvaluator(answerability_profiles={})

        result = evaluator.evaluate(
            profile_key="missing_profile",
            rows=[
                {"document_title": "A", "snippet": "石犀科技是一款企业销售训练平台。"},
                {"document_title": "B", "snippet": "支持角色扮演训练。"},
            ],
            execution_result=KnowledgeHaystackExecutionResult(
                rows=[],
                executed_steps=[
                    KnowledgeExecutedQueryStep(
                        query="石犀科技 产品介绍",
                        stage="primary",
                        profile_key="missing_profile",
                        status="hit",
                        hit_count=2,
                        retrieval_modes=["hybrid"],
                    )
                ],
                search_failures=[],
                stopped_early=False,
            ),
        )

        assert result.answerability == "partial"
        assert result.source_status == "ready"
        assert result.audit["mode"] == "count_fallback"
        assert result.audit["hit_count"] == 2

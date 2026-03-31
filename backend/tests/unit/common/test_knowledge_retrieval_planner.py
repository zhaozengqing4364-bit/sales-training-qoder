from common.knowledge_engine.config_repo import KnowledgeQueryProfileConfig
from common.knowledge_engine.intent_classifier import KnowledgeIntentClassification
from common.knowledge_engine.retrieval_planner import KnowledgeRetrievalPlanner


def _classification(
    *,
    query: str,
    normalized_query: str,
    profile_key: str,
    intent_key: str = "company_intro",
    matched: bool = True,
    resolved_entities: list[str] | None = None,
    matched_terms: list[str] | None = None,
):
    return KnowledgeIntentClassification(
        original_query=query,
        normalized_query=normalized_query,
        intent_key=intent_key,
        profile_key=profile_key,
        matched=matched,
        resolved_entities=list(resolved_entities or []),
        matched_terms=list(matched_terms or []),
        fallback_reason=None if matched else "first_available_profile",
        trace=None,
    )


class TestKnowledgeRetrievalPlanner:
    def test_planner_builds_progressive_multi_query_plan_with_entity_first_then_profile_expansions(self):
        planner = KnowledgeRetrievalPlanner(
            query_profiles={
                "product_overview": KnowledgeQueryProfileConfig(
                    profile_key="product_overview",
                    description="产品介绍",
                    rewrite_strategy="multi_query",
                    max_rewrite_queries=4,
                    stop_after_first_success=True,
                )
            }
        )

        plan = planner.build_plan(
            _classification(
                query="请介绍一下世袭科技",
                normalized_query="请介绍一下石犀科技",
                profile_key="product_overview",
                resolved_entities=["石犀科技"],
            )
        )

        assert plan.profile_key == "product_overview"
        assert plan.intent_key == "company_intro"
        assert plan.strategy == "multi_query"
        assert plan.stop_after_first_success is True
        assert plan.resolved_entities == ["石犀科技"]
        assert [step.query for step in plan.steps] == [
            "请介绍一下石犀科技",
            "石犀科技 产品介绍",
            "石犀科技 核心能力",
            "石犀科技 适用场景",
        ]
        assert [step.stage for step in plan.steps] == [
            "primary",
            "expansion",
            "expansion",
            "expansion",
        ]
        assert all(step.profile_key == "product_overview" for step in plan.steps)
        assert plan.audit["query_count"] == 4
        assert plan.audit["generated_from_entity"] is True

    def test_planner_respects_single_query_strategy_and_dedupes_keyword_matches(self):
        planner = KnowledgeRetrievalPlanner(
            query_profiles={
                "pricing_lookup": KnowledgeQueryProfileConfig(
                    profile_key="pricing_lookup",
                    description="价格问答",
                    rewrite_strategy="single_query",
                    max_rewrite_queries=1,
                    stop_after_first_success=False,
                )
            }
        )

        plan = planner.build_plan(
            _classification(
                query="石犀科技价格价格怎么样",
                normalized_query="石犀科技价格价格怎么样",
                profile_key="pricing_lookup",
                intent_key="entity_pricing",
                resolved_entities=["石犀科技"],
                matched_terms=["价格", "价格"],
            )
        )

        assert [step.query for step in plan.steps] == ["石犀科技价格价格怎么样"]
        assert plan.stop_after_first_success is False
        assert plan.audit["matched_terms"] == ["价格"]
        assert plan.audit["query_count"] == 1

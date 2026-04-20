from common.knowledge_engine.config_repo import (
    KnowledgeIntentRuleConfig,
    KnowledgeQueryProfileConfig,
)
from common.knowledge_engine.entity_resolver import (
    KnowledgeEntityResolution,
    KnowledgeResolvedEntityMatch,
)
from common.knowledge_engine.intent_classifier import KnowledgeIntentClassifier


def _build_resolution(*, normalized_query: str, canonical_entities: list[str]):
    return KnowledgeEntityResolution(
        original_query="请介绍一下世袭科技",
        normalized_query=normalized_query,
        resolved=bool(canonical_entities),
        canonical_entities=canonical_entities,
        matches=[
            KnowledgeResolvedEntityMatch(
                canonical_entity=canonical_entities[0],
                matched_text="世袭科技",
                entity_type="company",
                confidence=0.96,
                match_source="alias",
                start_index=5,
                end_index=9,
            )
        ]
        if canonical_entities
        else [],
    )


class TestKnowledgeIntentClassifier:
    def test_classifier_prefers_high_priority_regex_rule_and_returns_profile_key(self):
        classifier = KnowledgeIntentClassifier(
            query_profiles={
                "product_overview": KnowledgeQueryProfileConfig(
                    profile_key="product_overview",
                    description="产品介绍",
                    rewrite_strategy="multi_query",
                    max_rewrite_queries=4,
                    stop_after_first_success=True,
                ),
                "pricing_lookup": KnowledgeQueryProfileConfig(
                    profile_key="pricing_lookup",
                    description="价格问答",
                    rewrite_strategy="single_query",
                    max_rewrite_queries=1,
                    stop_after_first_success=False,
                ),
            },
            intent_rules=[
                KnowledgeIntentRuleConfig(
                    intent_key="pricing_query",
                    priority=20,
                    match_type="keyword_contains",
                    pattern="价格|报价",
                    profile_key="pricing_lookup",
                ),
                KnowledgeIntentRuleConfig(
                    intent_key="company_intro",
                    priority=10,
                    match_type="regex",
                    pattern="介绍一下.*石犀科技",
                    profile_key="product_overview",
                ),
            ],
        )

        result = classifier.classify(
            "请介绍一下世袭科技",
            entity_resolution=_build_resolution(
                normalized_query="请介绍一下石犀科技",
                canonical_entities=["石犀科技"],
            ),
        )

        assert result.matched is True
        assert result.intent_key == "company_intro"
        assert result.profile_key == "product_overview"
        assert result.normalized_query == "请介绍一下石犀科技"
        assert result.resolved_entities == ["石犀科技"]
        assert result.trace is not None
        assert result.trace.match_type == "regex"
        assert result.trace.priority == 10
        assert result.trace.pattern == "介绍一下.*石犀科技"

    def test_classifier_supports_entity_keyword_rules_only_when_entity_and_keyword_both_match(self):
        classifier = KnowledgeIntentClassifier(
            query_profiles={
                "pricing_lookup": KnowledgeQueryProfileConfig(
                    profile_key="pricing_lookup",
                    description="价格问答",
                    rewrite_strategy="multi_query",
                    max_rewrite_queries=4,
                    stop_after_first_success=False,
                )
            },
            intent_rules=[
                KnowledgeIntentRuleConfig(
                    intent_key="entity_pricing",
                    priority=5,
                    match_type="entity_keyword_contains",
                    pattern="价格|报价",
                    profile_key="pricing_lookup",
                )
            ],
        )

        matched = classifier.classify(
            "石犀科技价格怎么样",
            entity_resolution=_build_resolution(
                normalized_query="石犀科技价格怎么样",
                canonical_entities=["石犀科技"],
            ),
        )
        unmatched = classifier.classify(
            "价格怎么样",
            entity_resolution=_build_resolution(
                normalized_query="价格怎么样",
                canonical_entities=[],
            ),
        )

        assert matched.matched is True
        assert matched.intent_key == "entity_pricing"
        assert matched.profile_key == "pricing_lookup"
        assert matched.matched_terms == ["价格"]
        assert matched.trace is not None
        assert matched.trace.match_type == "entity_keyword_contains"

        assert unmatched.matched is False
        assert unmatched.intent_key == "general_lookup"
        assert unmatched.profile_key == ""
        assert unmatched.trace is None
        assert unmatched.fallback_reason == "no_matching_rule"

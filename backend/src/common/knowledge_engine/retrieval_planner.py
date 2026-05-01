from __future__ import annotations

from dataclasses import dataclass, field

from common.knowledge_engine.config_repo import KnowledgeQueryProfileConfig
from common.knowledge_engine.intent_classifier import KnowledgeIntentClassification


@dataclass(frozen=True)
class KnowledgeRetrievalStep:
    query: str
    stage: str
    profile_key: str


@dataclass(frozen=True)
class KnowledgeRetrievalPlan:
    profile_key: str
    intent_key: str
    strategy: str
    stop_after_first_success: bool
    resolved_entities: list[str] = field(default_factory=list)
    steps: list[KnowledgeRetrievalStep] = field(default_factory=list)
    audit: dict[str, object] = field(default_factory=dict)


class KnowledgeRetrievalPlanner:
    """Build a progressive retrieval plan from classified intent + query profile."""

    def __init__(
        self,
        *,
        query_profiles: dict[str, KnowledgeQueryProfileConfig] | None = None,
    ) -> None:
        self._query_profiles = dict(query_profiles or {})

    def build_plan(
        self, classification: KnowledgeIntentClassification
    ) -> KnowledgeRetrievalPlan:
        profile = self._query_profiles.get(classification.profile_key)
        if profile is None:
            raise KeyError(
                f"Unknown knowledge query profile: {classification.profile_key}"
            )

        steps = self._build_steps(classification=classification, profile=profile)
        deduped_terms = _dedupe_preserve_order(classification.matched_terms)
        return KnowledgeRetrievalPlan(
            profile_key=profile.profile_key,
            intent_key=classification.intent_key,
            strategy=profile.rewrite_strategy,
            stop_after_first_success=profile.stop_after_first_success,
            resolved_entities=list(classification.resolved_entities),
            steps=steps,
            audit={
                "query_count": len(steps),
                "generated_from_entity": bool(classification.resolved_entities),
                "matched_terms": deduped_terms,
                "fallback_reason": classification.fallback_reason,
            },
        )

    def _build_steps(
        self,
        *,
        classification: KnowledgeIntentClassification,
        profile: KnowledgeQueryProfileConfig,
    ) -> list[KnowledgeRetrievalStep]:
        raw_queries = self._build_queries(
            classification=classification, profile=profile
        )
        deduped_queries = _dedupe_preserve_order(raw_queries)[
            : max(1, profile.max_rewrite_queries)
        ]
        return [
            KnowledgeRetrievalStep(
                query=query,
                stage="primary" if index == 0 else "expansion",
                profile_key=profile.profile_key,
            )
            for index, query in enumerate(deduped_queries)
        ]

    def _build_queries(
        self,
        *,
        classification: KnowledgeIntentClassification,
        profile: KnowledgeQueryProfileConfig,
    ) -> list[str]:
        primary_query = (
            classification.normalized_query.strip()
            or classification.original_query.strip()
        )
        if profile.rewrite_strategy == "single_query":
            return [primary_query]

        queries = [primary_query]
        entity_focus = (
            classification.resolved_entities[0].strip()
            if classification.resolved_entities
            else ""
        )
        for suffix in _rewrite_suffixes(profile.profile_key):
            if entity_focus:
                queries.append(f"{entity_focus} {suffix}".strip())
            else:
                queries.append(f"{primary_query} {suffix}".strip())
        return queries


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in deduped:
            continue
        deduped.append(candidate)
    return deduped


def _rewrite_suffixes(profile_key: str) -> tuple[str, ...]:
    if profile_key == "product_overview":
        return ("产品介绍", "核心能力", "适用场景")
    if "pricing" in profile_key:
        return ("价格", "报价", "成本")
    return ("产品介绍", "核心能力", "适用场景")

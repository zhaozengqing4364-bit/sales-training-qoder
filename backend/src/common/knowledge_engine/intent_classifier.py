from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Pattern

from common.knowledge_engine.config_repo import (
    KnowledgeIntentRuleConfig,
    KnowledgeQueryProfileConfig,
)
from common.knowledge_engine.entity_resolver import KnowledgeEntityResolution


@dataclass(frozen=True)
class KnowledgeIntentMatchTrace:
    intent_key: str
    profile_key: str
    match_type: str
    pattern: str
    priority: int
    matched_terms: list[str] = field(default_factory=list)
    matched_entities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeIntentClassification:
    original_query: str
    normalized_query: str
    intent_key: str
    profile_key: str
    matched: bool
    resolved_entities: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    trace: KnowledgeIntentMatchTrace | None = None


class KnowledgeIntentClassifier:
    """Classify resolved user queries into project-owned retrieval profiles."""

    def __init__(
        self,
        *,
        query_profiles: dict[str, KnowledgeQueryProfileConfig] | None = None,
        intent_rules: list[KnowledgeIntentRuleConfig] | None = None,
    ) -> None:
        self._query_profiles = dict(query_profiles or {})
        self._intent_rules = tuple(
            sorted(
                (rule for rule in (intent_rules or []) if rule.profile_key in self._query_profiles),
                key=lambda item: (item.priority, item.intent_key, item.profile_key, item.pattern),
            )
        )

    def classify(
        self,
        query: str,
        *,
        entity_resolution: KnowledgeEntityResolution | None = None,
    ) -> KnowledgeIntentClassification:
        normalized_query = (entity_resolution.normalized_query if entity_resolution else query).strip()
        resolved_entities = list(entity_resolution.canonical_entities if entity_resolution else [])

        for rule in self._intent_rules:
            matched_terms = self._match_rule(
                rule=rule,
                normalized_query=normalized_query,
                resolved_entities=resolved_entities,
            )
            if matched_terms is None:
                continue

            trace = KnowledgeIntentMatchTrace(
                intent_key=rule.intent_key,
                profile_key=rule.profile_key,
                match_type=rule.match_type,
                pattern=rule.pattern,
                priority=rule.priority,
                matched_terms=matched_terms,
                matched_entities=resolved_entities,
            )
            return KnowledgeIntentClassification(
                original_query=query,
                normalized_query=normalized_query,
                intent_key=rule.intent_key,
                profile_key=rule.profile_key,
                matched=True,
                resolved_entities=resolved_entities,
                matched_terms=matched_terms,
                trace=trace,
            )

        fallback_profile_key = self._resolve_fallback_profile_key()
        fallback_reason = "first_available_profile" if fallback_profile_key else "no_available_profile"
        return KnowledgeIntentClassification(
            original_query=query,
            normalized_query=normalized_query,
            intent_key="general_lookup",
            profile_key=fallback_profile_key,
            matched=False,
            resolved_entities=resolved_entities,
            matched_terms=[],
            fallback_reason=fallback_reason,
            trace=None,
        )

    def _resolve_fallback_profile_key(self) -> str:
        if not self._query_profiles:
            return ""
        return sorted(self._query_profiles)[0]

    def _match_rule(
        self,
        *,
        rule: KnowledgeIntentRuleConfig,
        normalized_query: str,
        resolved_entities: list[str],
    ) -> list[str] | None:
        if rule.match_type == "regex":
            return self._match_regex(rule.pattern, normalized_query)
        if rule.match_type == "keyword_contains":
            return self._match_keywords(rule.pattern, normalized_query)
        if rule.match_type == "entity_keyword_contains":
            if not resolved_entities:
                return None
            return self._match_keywords(rule.pattern, normalized_query)
        return None

    @staticmethod
    def _match_regex(pattern: str, normalized_query: str) -> list[str] | None:
        compiled = _safe_compile_regex(pattern)
        if compiled is None:
            return None
        match = compiled.search(normalized_query)
        if match is None:
            return None
        matched_text = match.group(0).strip()
        return [matched_text] if matched_text else []

    @staticmethod
    def _match_keywords(pattern: str, normalized_query: str) -> list[str] | None:
        matched_terms: list[str] = []
        for keyword in _split_keywords(pattern):
            if keyword in normalized_query and keyword not in matched_terms:
                matched_terms.append(keyword)
        return matched_terms or None


def _split_keywords(pattern: str) -> list[str]:
    raw_tokens = re.split(r"[|,，\n]+", pattern)
    return [token.strip() for token in raw_tokens if token and token.strip()]


def _safe_compile_regex(pattern: str) -> Pattern[str] | None:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None

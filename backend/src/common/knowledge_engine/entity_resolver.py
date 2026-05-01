from __future__ import annotations

import re
from dataclasses import dataclass

from common.knowledge_engine.config_repo import KnowledgeEntityAliasConfig


@dataclass(frozen=True)
class KnowledgeResolvedEntityMatch:
    canonical_entity: str
    matched_text: str
    entity_type: str
    confidence: float
    match_source: str
    start_index: int
    end_index: int


@dataclass(frozen=True)
class KnowledgeEntityResolution:
    original_query: str
    normalized_query: str
    resolved: bool
    canonical_entities: list[str]
    matches: list[KnowledgeResolvedEntityMatch]


class KnowledgeEntityResolver:
    """Deterministic alias/canonical resolver for query understanding.

    This resolver intentionally avoids fuzzy NLP. It only rewrites configured aliases to
    canonical entity names and records a trace payload that downstream planner/debug flows
    can consume.
    """

    def __init__(
        self,
        *,
        entity_aliases: list[KnowledgeEntityAliasConfig] | None = None,
    ) -> None:
        self._entity_aliases = tuple(entity_aliases or [])
        self._alias_entries = tuple(
            sorted(
                self._entity_aliases,
                key=lambda item: (-len(item.alias), item.alias, item.canonical_entity),
            )
        )
        self._canonical_index = self._build_canonical_index(self._entity_aliases)

    def resolve_query(self, query: str) -> KnowledgeEntityResolution:
        normalized_query = query
        matches: list[KnowledgeResolvedEntityMatch] = []
        canonical_entities: list[str] = []
        seen_canonical_entities: set[str] = set()

        for alias_config in self._alias_entries:
            alias_matches = list(re.finditer(re.escape(alias_config.alias), query))
            if not alias_matches:
                continue

            normalized_query = normalized_query.replace(
                alias_config.alias,
                alias_config.canonical_entity,
            )
            for match in alias_matches:
                matches.append(
                    KnowledgeResolvedEntityMatch(
                        canonical_entity=alias_config.canonical_entity,
                        matched_text=match.group(0),
                        entity_type=alias_config.entity_type,
                        confidence=alias_config.confidence,
                        match_source="alias",
                        start_index=match.start(),
                        end_index=match.end(),
                    )
                )
            if alias_config.canonical_entity not in seen_canonical_entities:
                seen_canonical_entities.add(alias_config.canonical_entity)
                canonical_entities.append(alias_config.canonical_entity)

        for canonical_entity, alias_config in self._canonical_index.items():
            canonical_matches = list(re.finditer(re.escape(canonical_entity), query))
            if not canonical_matches:
                continue

            for match in canonical_matches:
                matches.append(
                    KnowledgeResolvedEntityMatch(
                        canonical_entity=canonical_entity,
                        matched_text=match.group(0),
                        entity_type=alias_config.entity_type,
                        confidence=alias_config.confidence,
                        match_source="canonical",
                        start_index=match.start(),
                        end_index=match.end(),
                    )
                )
            if canonical_entity not in seen_canonical_entities:
                seen_canonical_entities.add(canonical_entity)
                canonical_entities.append(canonical_entity)

        return KnowledgeEntityResolution(
            original_query=query,
            normalized_query=normalized_query,
            resolved=bool(matches),
            canonical_entities=canonical_entities,
            matches=sorted(
                matches, key=lambda item: (item.start_index, item.end_index)
            ),
        )

    @staticmethod
    def _build_canonical_index(
        entity_aliases: tuple[KnowledgeEntityAliasConfig, ...]
        | list[KnowledgeEntityAliasConfig],
    ) -> dict[str, KnowledgeEntityAliasConfig]:
        canonical_index: dict[str, KnowledgeEntityAliasConfig] = {}
        for alias_config in entity_aliases:
            existing = canonical_index.get(alias_config.canonical_entity)
            if existing is None or alias_config.confidence > existing.confidence:
                canonical_index[alias_config.canonical_entity] = alias_config
        return canonical_index

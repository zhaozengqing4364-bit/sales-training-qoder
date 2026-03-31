from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db.models import (
    KnowledgeAnswerabilityProfile,
    KnowledgeConfigVersion,
    KnowledgeEntityAlias,
    KnowledgeIntentRule,
    KnowledgeQueryProfile,
    KnowledgeRankingProfile,
)


@dataclass(frozen=True)
class KnowledgeQueryProfileConfig:
    profile_key: str
    description: str | None
    rewrite_strategy: str
    max_rewrite_queries: int
    stop_after_first_success: bool
    profile_source: str = "database"


@dataclass(frozen=True)
class KnowledgeIntentRuleConfig:
    intent_key: str
    priority: int
    match_type: str
    pattern: str
    profile_key: str
    profile_source: str = "database"


@dataclass(frozen=True)
class KnowledgeEntityAliasConfig:
    canonical_entity: str
    alias: str
    entity_type: str
    confidence: float
    profile_source: str = "database"


@dataclass(frozen=True)
class KnowledgeRankingProfileConfig:
    profile_key: str
    title_exact_boost: float
    entity_match_boost: float
    doc_type_weights: dict[str, float] = field(default_factory=dict)
    section_weights: dict[str, float] = field(default_factory=dict)
    min_pass_score: float = 0.0
    min_pass_score_keyword: float = 0.0
    profile_source: str = "database"


@dataclass(frozen=True)
class KnowledgeAnswerabilityProfileConfig:
    profile_key: str
    required_slots: list[str] = field(default_factory=list)
    optional_slots: list[str] = field(default_factory=list)
    sufficient_threshold: float = 1.0
    partial_threshold: float = 0.0
    profile_source: str = "database"


@dataclass(frozen=True)
class KnowledgeAnswerConfigSnapshot:
    config_version_id: str
    config_version_name: str
    profile_source: str = "database"
    query_profiles: dict[str, KnowledgeQueryProfileConfig] = field(default_factory=dict)
    intent_rules: list[KnowledgeIntentRuleConfig] = field(default_factory=list)
    entity_aliases: list[KnowledgeEntityAliasConfig] = field(default_factory=list)
    ranking_profiles: dict[str, KnowledgeRankingProfileConfig] = field(default_factory=dict)
    answerability_profiles: dict[str, KnowledgeAnswerabilityProfileConfig] = field(default_factory=dict)


class KnowledgeAnswerConfigRepository:
    """DB-backed repository for the active knowledge-answer config snapshot."""

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_active_config(self) -> KnowledgeAnswerConfigSnapshot | None:
        active_version = self._get_active_version()
        if active_version is None:
            return None

        return KnowledgeAnswerConfigSnapshot(
            config_version_id=active_version.id,
            config_version_name=active_version.version_name,
            query_profiles=self._load_query_profiles(active_version.id),
            intent_rules=self._load_intent_rules(active_version.id),
            entity_aliases=self._load_entity_aliases(active_version.id),
            ranking_profiles=self._load_ranking_profiles(active_version.id),
            answerability_profiles=self._load_answerability_profiles(active_version.id),
        )

    def _get_active_version(self) -> KnowledgeConfigVersion | None:
        statement = (
            select(KnowledgeConfigVersion)
            .where(
                KnowledgeConfigVersion.status == "active",
                KnowledgeConfigVersion.enabled.is_(True),
            )
            .order_by(
                KnowledgeConfigVersion.updated_at.desc(),
                KnowledgeConfigVersion.created_at.desc(),
                KnowledgeConfigVersion.id.desc(),
            )
            .limit(1)
        )
        return self._db_session.execute(statement).scalar_one_or_none()

    def _load_query_profiles(
        self,
        config_version_id: str,
    ) -> dict[str, KnowledgeQueryProfileConfig]:
        statement = (
            select(KnowledgeQueryProfile)
            .where(
                KnowledgeQueryProfile.config_version_id == config_version_id,
                KnowledgeQueryProfile.enabled.is_(True),
            )
            .order_by(KnowledgeQueryProfile.profile_key.asc())
        )
        profiles = self._db_session.execute(statement).scalars().all()
        return {
            profile.profile_key: KnowledgeQueryProfileConfig(
                profile_key=profile.profile_key,
                description=profile.description,
                rewrite_strategy=profile.rewrite_strategy,
                max_rewrite_queries=profile.max_rewrite_queries,
                stop_after_first_success=profile.stop_after_first_success,
            )
            for profile in profiles
        }

    def _load_intent_rules(self, config_version_id: str) -> list[KnowledgeIntentRuleConfig]:
        statement = (
            select(KnowledgeIntentRule)
            .where(
                KnowledgeIntentRule.config_version_id == config_version_id,
                KnowledgeIntentRule.enabled.is_(True),
            )
            .order_by(
                KnowledgeIntentRule.priority.asc(),
                KnowledgeIntentRule.intent_key.asc(),
            )
        )
        rules = self._db_session.execute(statement).scalars().all()
        return [
            KnowledgeIntentRuleConfig(
                intent_key=rule.intent_key,
                priority=rule.priority,
                match_type=rule.match_type,
                pattern=rule.pattern,
                profile_key=rule.profile_key,
            )
            for rule in rules
        ]

    def _load_entity_aliases(
        self,
        config_version_id: str,
    ) -> list[KnowledgeEntityAliasConfig]:
        statement = (
            select(KnowledgeEntityAlias)
            .where(
                KnowledgeEntityAlias.config_version_id == config_version_id,
                KnowledgeEntityAlias.enabled.is_(True),
            )
            .order_by(
                KnowledgeEntityAlias.alias.asc(),
                KnowledgeEntityAlias.canonical_entity.asc(),
            )
        )
        aliases = self._db_session.execute(statement).scalars().all()
        return [
            KnowledgeEntityAliasConfig(
                canonical_entity=alias.canonical_entity,
                alias=alias.alias,
                entity_type=alias.entity_type,
                confidence=alias.confidence,
            )
            for alias in aliases
        ]

    def _load_ranking_profiles(
        self,
        config_version_id: str,
    ) -> dict[str, KnowledgeRankingProfileConfig]:
        statement = (
            select(KnowledgeRankingProfile)
            .where(
                KnowledgeRankingProfile.config_version_id == config_version_id,
                KnowledgeRankingProfile.enabled.is_(True),
            )
            .order_by(KnowledgeRankingProfile.profile_key.asc())
        )
        profiles = self._db_session.execute(statement).scalars().all()
        return {
            profile.profile_key: KnowledgeRankingProfileConfig(
                profile_key=profile.profile_key,
                title_exact_boost=profile.title_exact_boost,
                entity_match_boost=profile.entity_match_boost,
                doc_type_weights=_json_object(profile.doc_type_weights_json),
                section_weights=_json_object(profile.section_weights_json),
                min_pass_score=profile.min_pass_score,
                min_pass_score_keyword=profile.min_pass_score_keyword,
            )
            for profile in profiles
        }

    def _load_answerability_profiles(
        self,
        config_version_id: str,
    ) -> dict[str, KnowledgeAnswerabilityProfileConfig]:
        statement = (
            select(KnowledgeAnswerabilityProfile)
            .where(
                KnowledgeAnswerabilityProfile.config_version_id == config_version_id,
                KnowledgeAnswerabilityProfile.enabled.is_(True),
            )
            .order_by(KnowledgeAnswerabilityProfile.profile_key.asc())
        )
        profiles = self._db_session.execute(statement).scalars().all()
        return {
            profile.profile_key: KnowledgeAnswerabilityProfileConfig(
                profile_key=profile.profile_key,
                required_slots=_json_string_list(profile.required_slots_json),
                optional_slots=_json_string_list(profile.optional_slots_json),
                sufficient_threshold=profile.sufficient_threshold,
                partial_threshold=profile.partial_threshold,
            )
            for profile in profiles
        }


def _json_object(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, float] = {}
    for key, raw in value.items():
        normalized[str(key)] = float(raw)
    return normalized



def _json_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]

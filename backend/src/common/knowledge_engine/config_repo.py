from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db.models import (
    KnowledgeAnswerabilityProfile,
    KnowledgeChunkingPreset,
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
    # Unified scoring weights (elevated from hardcoded _rerank_results)
    base_weight: float = 0.50
    coverage_weight: float = 0.20
    phrase_bonus: float = 0.15
    title_bonus_max: float = 0.10
    ratio_bonus_max: float = 0.05
    cross_encoder_weight: float = 0.0
    diversity_penalty: float = 0.12
    profile_source: str = "database"


@dataclass(frozen=True)
class KnowledgeChunkingPresetConfig:
    """Named chunking configuration within a config version."""

    profile_key: str
    description: str | None
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    is_default: bool
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
    ranking_profiles: dict[str, KnowledgeRankingProfileConfig] = field(
        default_factory=dict
    )
    answerability_profiles: dict[str, KnowledgeAnswerabilityProfileConfig] = field(
        default_factory=dict
    )
    chunking_presets: dict[str, KnowledgeChunkingPresetConfig] = field(
        default_factory=dict
    )


class KnowledgeAnswerConfigRepository:
    """DB-backed repository for the active knowledge-answer config snapshot."""

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_active_config(self) -> KnowledgeAnswerConfigSnapshot | None:
        active_version = self._get_active_version()
        if active_version is None:
            return None

        config_version_id = _as_str(active_version.id)
        return KnowledgeAnswerConfigSnapshot(
            config_version_id=config_version_id,
            config_version_name=_as_str(active_version.version_name),
            query_profiles=self._load_query_profiles(config_version_id),
            intent_rules=self._load_intent_rules(config_version_id),
            entity_aliases=self._load_entity_aliases(config_version_id),
            ranking_profiles=self._load_ranking_profiles(config_version_id),
            answerability_profiles=self._load_answerability_profiles(
                config_version_id
            ),
            chunking_presets=self._load_chunking_presets(config_version_id),
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
        configs: dict[str, KnowledgeQueryProfileConfig] = {}
        for profile in profiles:
            profile_key = _as_str(profile.profile_key)
            configs[profile_key] = KnowledgeQueryProfileConfig(
                profile_key=profile_key,
                description=_as_optional_str(profile.description),
                rewrite_strategy=_as_str(profile.rewrite_strategy),
                max_rewrite_queries=_as_int(profile.max_rewrite_queries),
                stop_after_first_success=_as_bool(profile.stop_after_first_success),
            )
        return configs

    def _load_intent_rules(
        self, config_version_id: str
    ) -> list[KnowledgeIntentRuleConfig]:
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
                intent_key=_as_str(rule.intent_key),
                priority=_as_int(rule.priority),
                match_type=_as_str(rule.match_type),
                pattern=_as_str(rule.pattern),
                profile_key=_as_str(rule.profile_key),
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
                canonical_entity=_as_str(alias.canonical_entity),
                alias=_as_str(alias.alias),
                entity_type=_as_str(alias.entity_type),
                confidence=_as_float(alias.confidence),
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
        configs: dict[str, KnowledgeRankingProfileConfig] = {}
        for profile in profiles:
            profile_key = _as_str(profile.profile_key)
            configs[profile_key] = KnowledgeRankingProfileConfig(
                profile_key=profile_key,
                title_exact_boost=_as_float(profile.title_exact_boost),
                entity_match_boost=_as_float(profile.entity_match_boost),
                doc_type_weights=_json_object(profile.doc_type_weights_json),
                section_weights=_json_object(profile.section_weights_json),
                min_pass_score=_as_float(profile.min_pass_score),
                min_pass_score_keyword=_as_float(profile.min_pass_score_keyword),
                base_weight=_as_float(getattr(profile, "base_weight", 0.50)),
                coverage_weight=_as_float(getattr(profile, "coverage_weight", 0.20)),
                phrase_bonus=_as_float(getattr(profile, "phrase_bonus", 0.15)),
                title_bonus_max=_as_float(getattr(profile, "title_bonus_max", 0.10)),
                ratio_bonus_max=_as_float(getattr(profile, "ratio_bonus_max", 0.05)),
                cross_encoder_weight=_as_float(
                    getattr(profile, "cross_encoder_weight", 0.0)
                ),
                diversity_penalty=_as_float(
                    getattr(profile, "diversity_penalty", 0.12)
                ),
            )
        return configs

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
        configs: dict[str, KnowledgeAnswerabilityProfileConfig] = {}
        for profile in profiles:
            profile_key = _as_str(profile.profile_key)
            configs[profile_key] = KnowledgeAnswerabilityProfileConfig(
                profile_key=profile_key,
                required_slots=_json_string_list(profile.required_slots_json),
                optional_slots=_json_string_list(profile.optional_slots_json),
                sufficient_threshold=_as_float(profile.sufficient_threshold),
                partial_threshold=_as_float(profile.partial_threshold),
            )
        return configs

    def _load_chunking_presets(
        self,
        config_version_id: str,
    ) -> dict[str, KnowledgeChunkingPresetConfig]:
        statement = (
            select(KnowledgeChunkingPreset)
            .where(
                KnowledgeChunkingPreset.config_version_id == config_version_id,
                KnowledgeChunkingPreset.enabled.is_(True),
            )
            .order_by(KnowledgeChunkingPreset.profile_key.asc())
        )
        presets = self._db_session.execute(statement).scalars().all()
        configs: dict[str, KnowledgeChunkingPresetConfig] = {}
        for preset in presets:
            profile_key = _as_str(preset.profile_key)
            configs[profile_key] = KnowledgeChunkingPresetConfig(
                profile_key=profile_key,
                description=_as_optional_str(preset.description),
                chunking_strategy=_as_str(preset.chunking_strategy),
                chunk_size=_as_int(preset.chunk_size),
                chunk_overlap=_as_int(preset.chunk_overlap),
                is_default=_as_bool(preset.is_default),
            )
        return configs


def _as_str(value: Any) -> str:
    return str(value)


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_int(value: Any) -> int:
    return int(value)


def _as_float(value: Any) -> float:
    return float(value)


def _as_bool(value: Any) -> bool:
    return bool(value)


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

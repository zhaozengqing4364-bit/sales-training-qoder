"""Admin-governed scoring ruleset schemas, resolver, and dry-run engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ScoringRuleset, SystemLog, User
from common.monitoring.logger import get_logger, get_trace_id

from .canonical import (
    CANONICAL_ROLLUP_IDS,
    CanonicalScenarioType,
    build_canonical_views,
    get_canonical_dimension_definitions,
)

logger = get_logger(__name__)

SCORING_RULESET_SCHEMA_VERSION = "scoring_ruleset_schema_v1"
SCORING_RULESET_SCORE_BASIS = (
    "configured_scoring_ruleset_weighted_canonical_dimensions"
)
LEGACY_COMPAT_RULESET_VERSION = "session_evidence_projection_v1"
LEGACY_COMPAT_SCORE_BASIS = "session_evidence_projection_evaluable_only"

ScoringRulesetStatus = Literal["draft", "published", "archived"]


def _normalize_scenario_type(value: str | None) -> CanonicalScenarioType:
    normalized = str(value or "sales").strip().lower()
    return "presentation" if normalized == "presentation" else "sales"


def _coerce_score(value: Any, fallback: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = float(fallback)
    return round(max(0.0, min(100.0, score)), 2)


def _default_not_evaluable_reasons() -> dict[str, str]:
    return {
        "missing_min_messages": "缺少足够对话证据，无法按当前评分规则评估。",
        "missing_score_evidence": "缺少会话分数或实时评分证据，无法按当前评分规则评估。",
        "missing_stage_evidence": "缺少销售阶段证据，无法按当前评分规则评估。",
    }


class RulesetRollupContribution(BaseModel):
    """How one canonical dimension contributes to a legacy report rollup."""

    model_config = ConfigDict(extra="forbid")

    rollup_id: Literal["logic", "accuracy", "completeness"]
    weight: float = Field(..., gt=0, le=10)


class ScoringDimensionRule(BaseModel):
    """Configurable scoring dimension inside a ruleset definition."""

    model_config = ConfigDict(extra="forbid")

    dimension_id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=80)
    weight: float = Field(..., gt=0, le=10)
    rollup_contributions: list[RulesetRollupContribution] = Field(
        default_factory=list,
        min_length=1,
    )
    min_evidence: dict[str, Any] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=500)


class ScoringMinimumEvidence(BaseModel):
    """Evidence thresholds that prevent fake scores when inputs are missing."""

    model_config = ConfigDict(extra="forbid")

    min_messages: int = Field(default=0, ge=0, le=200)
    require_score_evidence: bool = True
    require_stage_evidence: bool = False


class ScoringRulesetDefinition(BaseModel):
    """Versionable scoring ruleset definition for sales or presentation reports."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["scoring_ruleset_schema_v1"] = (
        SCORING_RULESET_SCHEMA_VERSION
    )
    scenario_type: Literal["sales", "presentation"]
    score_basis: str = Field(
        default=SCORING_RULESET_SCORE_BASIS,
        min_length=1,
        max_length=160,
    )
    dimensions: list[ScoringDimensionRule] = Field(min_length=1)
    min_evidence: ScoringMinimumEvidence = Field(
        default_factory=ScoringMinimumEvidence
    )
    not_evaluable_reasons: dict[str, str] = Field(
        default_factory=_default_not_evaluable_reasons
    )

    @model_validator(mode="after")
    def validate_dimension_contract(self) -> ScoringRulesetDefinition:
        expected = {
            item.dimension_id: item
            for item in get_canonical_dimension_definitions(self.scenario_type)
        }
        seen: set[str] = set()
        for dimension in self.dimensions:
            if dimension.dimension_id not in expected:
                raise ValueError(
                    f"dimension_id '{dimension.dimension_id}' is not valid for "
                    f"{self.scenario_type}"
                )
            if dimension.dimension_id in seen:
                raise ValueError(f"duplicate dimension_id '{dimension.dimension_id}'")
            seen.add(dimension.dimension_id)
            invalid_rollups = [
                item.rollup_id
                for item in dimension.rollup_contributions
                if item.rollup_id not in CANONICAL_ROLLUP_IDS
            ]
            if invalid_rollups:
                raise ValueError(
                    f"dimension '{dimension.dimension_id}' has invalid rollups: "
                    f"{', '.join(invalid_rollups)}"
                )

        total_weight = sum(dimension.weight for dimension in self.dimensions)
        if total_weight <= 0:
            raise ValueError("dimension weights must be positive")
        return self


@dataclass(slots=True)
class ScoringRulesetView:
    ruleset_id: str | None
    scenario_type: CanonicalScenarioType
    version: str
    display_name: str
    description: str | None
    status: ScoringRulesetStatus
    definition: ScoringRulesetDefinition
    is_active: bool
    source: Literal["default", "admin"]
    created_at: datetime | None = None
    updated_at: datetime | None = None
    published_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleset_id": self.ruleset_id,
            "scenario_type": self.scenario_type,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "status": self.status,
            "definition": self.definition.model_dump(mode="json"),
            "is_active": self.is_active,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
        }


class ScoringRulesetService:
    """Read, validate, publish, rollback, and dry-run scoring rulesets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def build_default_definition(
        scenario_type: str | CanonicalScenarioType,
    ) -> ScoringRulesetDefinition:
        normalized = _normalize_scenario_type(str(scenario_type))
        dimensions: list[ScoringDimensionRule] = []
        for definition in get_canonical_dimension_definitions(normalized):
            rollup_contributions = [
                RulesetRollupContribution(
                    rollup_id=contribution.rollup_id,
                    weight=round(float(contribution.weight), 4),
                )
                for contribution in definition.rollup_contributions
            ]
            dimension_weight = round(
                sum(item.weight for item in rollup_contributions) or 1.0,
                4,
            )
            dimensions.append(
                ScoringDimensionRule(
                    dimension_id=definition.dimension_id,
                    label=definition.label,
                    weight=dimension_weight,
                    rollup_contributions=rollup_contributions,
                )
            )

        return ScoringRulesetDefinition(
            scenario_type=normalized,
            score_basis=LEGACY_COMPAT_SCORE_BASIS,
            dimensions=dimensions,
            min_evidence=ScoringMinimumEvidence(
                min_messages=1 if normalized == "sales" else 0,
                require_score_evidence=True,
                require_stage_evidence=False,
            ),
        )

    @classmethod
    def build_default_view(
        cls,
        scenario_type: str | CanonicalScenarioType,
    ) -> ScoringRulesetView:
        normalized = _normalize_scenario_type(str(scenario_type))
        return ScoringRulesetView(
            ruleset_id=None,
            scenario_type=normalized,
            version=LEGACY_COMPAT_RULESET_VERSION,
            display_name="Legacy compatible session evidence projection",
            description="Safe fallback that preserves existing report scoring behavior.",
            status="published",
            definition=cls.build_default_definition(normalized),
            is_active=True,
            source="default",
        )

    @staticmethod
    def view_from_model(row: ScoringRuleset) -> ScoringRulesetView:
        definition = ScoringRulesetDefinition.model_validate(row.definition_json or {})
        return ScoringRulesetView(
            ruleset_id=str(row.ruleset_id),
            scenario_type=_normalize_scenario_type(str(row.scenario_type)),
            version=str(row.version),
            display_name=str(row.display_name),
            description=row.description,
            status=str(row.status),  # type: ignore[arg-type]
            definition=definition,
            is_active=bool(row.is_active),
            source="admin",
            created_at=row.created_at,
            updated_at=row.updated_at,
            published_at=row.published_at,
        )

    async def list_rulesets(
        self,
        *,
        scenario_type: str | None = None,
    ) -> list[ScoringRulesetView]:
        stmt = select(ScoringRuleset)
        if scenario_type:
            stmt = stmt.where(
                ScoringRuleset.scenario_type == _normalize_scenario_type(scenario_type)
            )
        stmt = stmt.order_by(
            ScoringRuleset.scenario_type,
            ScoringRuleset.created_at.desc(),
        )
        result = await self.db.execute(stmt)
        return [self.view_from_model(row) for row in result.scalars().all()]

    async def get_ruleset(self, ruleset_id: str) -> ScoringRuleset | None:
        result = await self.db.execute(
            select(ScoringRuleset).where(ScoringRuleset.ruleset_id == ruleset_id)
        )
        return result.scalar_one_or_none()

    async def get_active_or_default(
        self,
        scenario_type: str | CanonicalScenarioType,
    ) -> ScoringRulesetView:
        normalized = _normalize_scenario_type(str(scenario_type))
        try:
            result = await self.db.execute(
                select(ScoringRuleset)
                .where(
                    ScoringRuleset.scenario_type == normalized,
                    ScoringRuleset.status == "published",
                    ScoringRuleset.is_active.is_(True),
                )
                .order_by(ScoringRuleset.published_at.desc())
                .limit(1)
            )
        except SQLAlchemyError as exc:
            logger.warning(
                "scoring_ruleset_active_lookup_failed_using_default",
                scenario_type=normalized,
                error=str(exc),
            )
            return self.build_default_view(normalized)

        row = result.scalar_one_or_none()
        if row is None:
            return self.build_default_view(normalized)
        try:
            return self.view_from_model(row)
        except ValueError as exc:
            logger.warning(
                "scoring_ruleset_active_invalid_using_default",
                scenario_type=normalized,
                ruleset_id=str(row.ruleset_id),
                error=str(exc),
            )
            return self.build_default_view(normalized)

    async def create_ruleset(
        self,
        *,
        scenario_type: str,
        version: str,
        display_name: str,
        definition: ScoringRulesetDefinition,
        actor: User,
        description: str | None = None,
    ) -> ScoringRulesetView:
        normalized = _normalize_scenario_type(scenario_type)
        if definition.scenario_type != normalized:
            raise ValueError("[SCORING_RULESET_SCENARIO_MISMATCH]")

        row = ScoringRuleset(
            scenario_type=normalized,
            version=version.strip(),
            display_name=display_name.strip(),
            description=description,
            status="draft",
            definition_json=definition.model_dump(mode="json"),
            is_active=False,
            created_by=str(actor.user_id),
            updated_by=str(actor.user_id),
        )
        self.db.add(row)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise ValueError("[SCORING_RULESET_VERSION_EXISTS]") from exc

        self._queue_audit_log(
            action="scoring_ruleset.create",
            actor=actor,
            reason="create draft scoring ruleset",
            before=None,
            after=self._snapshot(row),
        )
        return self.view_from_model(row)

    async def update_ruleset(
        self,
        *,
        ruleset_id: str,
        actor: User,
        display_name: str | None = None,
        description: str | None = None,
        definition: ScoringRulesetDefinition | None = None,
    ) -> ScoringRulesetView:
        row = await self.get_ruleset(ruleset_id)
        if row is None:
            raise ValueError("[SCORING_RULESET_NOT_FOUND]")
        if row.status == "published" and row.is_active:
            raise ValueError("[SCORING_RULESET_ACTIVE_IMMUTABLE]")
        before = self._snapshot(row)
        if display_name is not None:
            row.display_name = display_name.strip()
        if description is not None:
            row.description = description
        if definition is not None:
            if definition.scenario_type != row.scenario_type:
                raise ValueError("[SCORING_RULESET_SCENARIO_MISMATCH]")
            row.definition_json = definition.model_dump(mode="json")
        row.updated_by = str(actor.user_id)
        row.updated_at = datetime.now(UTC)
        await self.db.flush()

        self._queue_audit_log(
            action="scoring_ruleset.update",
            actor=actor,
            reason="update draft scoring ruleset",
            before=before,
            after=self._snapshot(row),
        )
        return self.view_from_model(row)

    async def publish_ruleset(
        self,
        *,
        ruleset_id: str,
        actor: User,
        reason: str | None,
    ) -> ScoringRulesetView:
        row = await self.get_ruleset(ruleset_id)
        if row is None:
            raise ValueError("[SCORING_RULESET_NOT_FOUND]")
        before = await self._active_snapshot(str(row.scenario_type))

        # Validate again at the publish boundary so invalid rows cannot become active.
        ScoringRulesetDefinition.model_validate(row.definition_json or {})
        await self._deactivate_active(str(row.scenario_type))
        row.status = "published"
        row.is_active = True
        row.published_by = str(actor.user_id)
        row.published_at = datetime.now(UTC)
        row.updated_by = str(actor.user_id)
        row.updated_at = datetime.now(UTC)
        await self.db.flush()

        self._queue_audit_log(
            action="scoring_ruleset.publish",
            actor=actor,
            reason=reason or "publish scoring ruleset",
            before=before,
            after=self._snapshot(row),
        )
        return self.view_from_model(row)

    async def rollback_to_ruleset(
        self,
        *,
        ruleset_id: str,
        actor: User,
        reason: str | None,
    ) -> ScoringRulesetView:
        row = await self.get_ruleset(ruleset_id)
        if row is None:
            raise ValueError("[SCORING_RULESET_NOT_FOUND]")
        if row.status != "published":
            raise ValueError("[SCORING_RULESET_ROLLBACK_TARGET_NOT_PUBLISHED]")
        before = await self._active_snapshot(str(row.scenario_type))
        await self._deactivate_active(str(row.scenario_type))
        row.is_active = True
        row.published_by = str(actor.user_id)
        row.published_at = datetime.now(UTC)
        row.updated_by = str(actor.user_id)
        row.updated_at = datetime.now(UTC)
        await self.db.flush()

        self._queue_audit_log(
            action="scoring_ruleset.rollback",
            actor=actor,
            reason=reason or "rollback scoring ruleset",
            before=before,
            after=self._snapshot(row),
        )
        return self.view_from_model(row)

    async def dry_run_session(
        self,
        *,
        session_id: str,
        candidate_definition: ScoringRulesetDefinition | None = None,
        candidate_ruleset_id: str | None = None,
    ) -> dict[str, Any]:
        from common.conversation.session_evidence import SessionEvidenceService

        projection_result = await SessionEvidenceService(self.db).get_projection(
            session_id=session_id,
        )
        if not projection_result.is_success:
            raise ValueError(projection_result.fallback or "[SESSION_EVIDENCE_FAILED]")
        projection = projection_result.value

        baseline = await self.get_active_or_default(projection.scenario_type)
        if candidate_definition is not None:
            candidate = ScoringRulesetView(
                ruleset_id=None,
                scenario_type=candidate_definition.scenario_type,
                version="dry_run_candidate",
                display_name="Dry-run candidate",
                description=None,
                status="draft",
                definition=candidate_definition,
                is_active=False,
                source="admin",
            )
        elif candidate_ruleset_id:
            row = await self.get_ruleset(candidate_ruleset_id)
            if row is None:
                raise ValueError("[SCORING_RULESET_NOT_FOUND]")
            candidate = self.view_from_model(row)
        else:
            raise ValueError("[SCORING_RULESET_DRY_RUN_CANDIDATE_REQUIRED]")

        if candidate.scenario_type != projection.scenario_type:
            raise ValueError("[SCORING_RULESET_SCENARIO_MISMATCH]")

        baseline_score = self.score_projection(
            projection=projection,
            ruleset=baseline,
        )
        candidate_score = self.score_projection(
            projection=projection,
            ruleset=candidate,
        )
        return self.compare_scores(
            session_id=session_id,
            baseline=baseline_score,
            candidate=candidate_score,
        )

    @classmethod
    def score_projection(
        cls,
        *,
        projection: Any,
        ruleset: ScoringRulesetView,
    ) -> dict[str, Any]:
        completeness = (
            projection.evidence_completeness
            if isinstance(projection.evidence_completeness, dict)
            else {}
        )
        not_evaluable_reason = cls._not_evaluable_reason(
            completeness=completeness,
            ruleset=ruleset,
        )
        if not_evaluable_reason is not None:
            return {
                "ruleset_version": ruleset.version,
                "ruleset_id": ruleset.ruleset_id,
                "score_basis": ruleset.definition.score_basis,
                "evaluable": False,
                "not_evaluable_reason": not_evaluable_reason,
                "overall_score": None,
                "rollups": {},
                "dimensions": [],
                "evidence_completeness": completeness,
            }

        dimension_scores = cls._dimension_score_map(projection)
        weighted_dimensions: list[dict[str, Any]] = []
        total_weight = sum(dimension.weight for dimension in ruleset.definition.dimensions)
        weighted_total = 0.0
        rollup_weighted_totals = {rollup_id: 0.0 for rollup_id in CANONICAL_ROLLUP_IDS}
        rollup_weight_totals = {rollup_id: 0.0 for rollup_id in CANONICAL_ROLLUP_IDS}

        for dimension in ruleset.definition.dimensions:
            fallback = getattr(projection, "overall_score", 0.0)
            score = _coerce_score(
                dimension_scores.get(dimension.dimension_id),
                fallback=fallback,
            )
            normalized_weight = dimension.weight / total_weight
            weighted_total += score * normalized_weight
            for contribution in dimension.rollup_contributions:
                rollup_weighted_totals[contribution.rollup_id] += (
                    score * contribution.weight
                )
                rollup_weight_totals[contribution.rollup_id] += contribution.weight
            weighted_dimensions.append(
                {
                    "dimension_id": dimension.dimension_id,
                    "label": dimension.label,
                    "score": score,
                    "weight": round(normalized_weight, 4),
                }
            )

        rollups = {
            rollup_id: _coerce_score(
                (
                    rollup_weighted_totals[rollup_id]
                    / rollup_weight_totals[rollup_id]
                )
                if rollup_weight_totals[rollup_id] > 0
                else getattr(projection, f"{rollup_id}_score", 0.0)
            )
            for rollup_id in CANONICAL_ROLLUP_IDS
        }
        return {
            "ruleset_version": ruleset.version,
            "ruleset_id": ruleset.ruleset_id,
            "score_basis": ruleset.definition.score_basis,
            "evaluable": True,
            "not_evaluable_reason": None,
            "overall_score": _coerce_score(weighted_total),
            "rollups": rollups,
            "dimensions": weighted_dimensions,
            "evidence_completeness": completeness,
        }

    @staticmethod
    def compare_scores(
        *,
        session_id: str,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        baseline_score = baseline.get("overall_score")
        candidate_score = candidate.get("overall_score")
        delta: float | None = None
        if isinstance(baseline_score, (int, float)) and isinstance(
            candidate_score,
            (int, float),
        ):
            delta = round(float(candidate_score) - float(baseline_score), 2)

        dimension_deltas: list[dict[str, Any]] = []
        baseline_by_id = {
            str(item.get("dimension_id")): item
            for item in baseline.get("dimensions", [])
            if isinstance(item, dict)
        }
        for item in candidate.get("dimensions", []):
            if not isinstance(item, dict):
                continue
            dimension_id = str(item.get("dimension_id"))
            old = baseline_by_id.get(dimension_id, {})
            old_score = old.get("score")
            new_score = item.get("score")
            score_delta: float | None = None
            if isinstance(old_score, (int, float)) and isinstance(new_score, (int, float)):
                score_delta = round(float(new_score) - float(old_score), 2)
            dimension_deltas.append(
                {
                    "dimension_id": dimension_id,
                    "label": item.get("label"),
                    "baseline_score": old_score,
                    "candidate_score": new_score,
                    "delta": score_delta,
                }
            )

        return {
            "session_id": session_id,
            "mode": "dry_run",
            "mutates_history": False,
            "baseline": baseline,
            "candidate": candidate,
            "delta": {
                "overall_score": delta,
                "dimensions": dimension_deltas,
            },
        }

    @staticmethod
    def report_metadata_for_view(view: ScoringRulesetView) -> dict[str, Any]:
        return {
            "ruleset_id": view.ruleset_id,
            "version": view.version,
            "scenario_type": view.scenario_type,
            "source": view.source,
            "score_basis": view.definition.score_basis,
        }

    async def _deactivate_active(self, scenario_type: str) -> None:
        result = await self.db.execute(
            select(ScoringRuleset).where(
                ScoringRuleset.scenario_type == _normalize_scenario_type(scenario_type),
                ScoringRuleset.is_active.is_(True),
            )
        )
        for active in result.scalars().all():
            active.is_active = False
            active.updated_at = datetime.now(UTC)

    async def _active_snapshot(self, scenario_type: str) -> dict[str, Any] | None:
        active = await self.get_active_or_default(scenario_type)
        return active.to_dict()

    @staticmethod
    def _snapshot(row: ScoringRuleset) -> dict[str, Any]:
        return {
            "ruleset_id": str(row.ruleset_id),
            "scenario_type": str(row.scenario_type),
            "version": str(row.version),
            "display_name": str(row.display_name),
            "status": str(row.status),
            "is_active": bool(row.is_active),
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }

    def _queue_audit_log(
        self,
        *,
        action: str,
        actor: User,
        reason: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        details = {
            "actor_id": str(actor.user_id),
            "actor_role": str(getattr(actor, "role", "")),
            "reason": reason,
            "trace_id": get_trace_id(),
            "before": before,
            "after": after,
        }
        self.db.add(
            SystemLog(
                action=action,
                user_id=str(actor.user_id),
                user_identifier=str(getattr(actor, "email", "") or actor.user_id),
                status="success",
                details=json.dumps(details, ensure_ascii=False),
            )
        )

    @staticmethod
    def _dimension_score_map(projection: Any) -> dict[str, float]:
        kernel = getattr(projection, "canonical_evaluation_kernel", None)
        dimensions = kernel.get("dimensions") if isinstance(kernel, dict) else None
        scores: dict[str, float] = {}
        if isinstance(dimensions, list):
            for item in dimensions:
                if not isinstance(item, dict):
                    continue
                dimension_id = item.get("dimension_id")
                if isinstance(dimension_id, str) and dimension_id:
                    scores[dimension_id] = _coerce_score(item.get("score"))
        if scores:
            return scores

        canonical_kernel, _compat = build_canonical_views(
            scenario_type=getattr(projection, "scenario_type", "sales"),
            surface_id="report",
            overall_score=getattr(projection, "overall_score", 0.0),
            logic_score=getattr(projection, "logic_score", None),
            accuracy_score=getattr(projection, "accuracy_score", None),
            completeness_score=getattr(projection, "completeness_score", None),
        )
        return {
            str(item.get("dimension_id")): _coerce_score(item.get("score"))
            for item in canonical_kernel.get("dimensions", [])
            if isinstance(item, dict) and item.get("dimension_id")
        }

    @staticmethod
    def _not_evaluable_reason(
        *,
        completeness: dict[str, Any],
        ruleset: ScoringRulesetView,
    ) -> str | None:
        min_evidence = ruleset.definition.min_evidence
        reasons = ruleset.definition.not_evaluable_reasons
        message_count = int(completeness.get("message_count") or 0)
        if message_count < min_evidence.min_messages:
            return reasons.get("missing_min_messages", "missing_min_messages")
        if min_evidence.require_score_evidence:
            has_session_scores = bool(completeness.get("session_scores", False))
            has_message_scores = int(completeness.get("message_scores") or 0) > 0
            if not has_session_scores and not has_message_scores:
                return reasons.get("missing_score_evidence", "missing_score_evidence")
        if min_evidence.require_stage_evidence and int(
            completeness.get("stage_evidence") or 0
        ) <= 0:
            return reasons.get("missing_stage_evidence", "missing_stage_evidence")
        return None


__all__ = [
    "LEGACY_COMPAT_RULESET_VERSION",
    "LEGACY_COMPAT_SCORE_BASIS",
    "SCORING_RULESET_SCHEMA_VERSION",
    "SCORING_RULESET_SCORE_BASIS",
    "ScoringDimensionRule",
    "ScoringMinimumEvidence",
    "ScoringRulesetDefinition",
    "ScoringRulesetService",
    "ScoringRulesetView",
]

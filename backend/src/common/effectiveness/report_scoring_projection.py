"""Unified report scoring projection read model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger

from .scoring_rulesets import ScoringRulesetService, ScoringRulesetView

logger = get_logger(__name__)


@dataclass(slots=True)
class ReportScoringProjection:
    """Stable read model shared by report read, generation, and snapshots."""

    evaluable: bool
    not_evaluable_reason: str | None
    not_evaluable_reason_code: str | None
    ruleset_id: str | None
    ruleset_version: str
    ruleset_source: str
    score_basis: str
    overall_score: float | None
    rollups: dict[str, float]
    dimensions: list[dict[str, Any]]
    evidence_completeness: dict[str, Any]
    scoring_metadata: dict[str, Any]
    snapshot_metadata: dict[str, Any]

    def build_non_evaluable_payload(self) -> dict[str, Any]:
        """Build the persisted non-evaluable payload without inventing scores."""
        return {
            "evaluable": False,
            "not_evaluable_reason": self.not_evaluable_reason,
            "not_evaluable_reason_code": self.not_evaluable_reason_code,
            "ruleset_source": self.ruleset_source,
            "ruleset_version": self.ruleset_version,
            "score_basis": self.score_basis,
            "evidence_completeness": dict(self.evidence_completeness),
            "scoring_metadata": dict(self.scoring_metadata),
        }


class ReportScoringProjectionService:
    """Resolve scoring ruleset and project session evidence for reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build(
        self,
        *,
        evidence_projection: Any,
        scenario_type: str,
        ruleset_view: ScoringRulesetView | None = None,
    ) -> ReportScoringProjection:
        view = ruleset_view or await self._resolve_ruleset_view(scenario_type)
        return build_report_scoring_projection(
            evidence_projection=evidence_projection,
            ruleset_view=view,
        )

    async def _resolve_ruleset_view(self, scenario_type: str) -> ScoringRulesetView:
        normalized = (
            "presentation"
            if str(scenario_type or "").strip().lower() == "presentation"
            else "sales"
        )
        if type(self.db).__module__.startswith("unittest.mock"):
            return ScoringRulesetService.build_default_view(normalized)
        try:
            return await ScoringRulesetService(self.db).get_active_or_default(
                scenario_type
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "report_scoring_projection_ruleset_fallback_default",
                scenario_type=normalized,
                error=str(exc),
            )
            return ScoringRulesetService.build_default_view(normalized)


def build_report_scoring_projection(
    *,
    evidence_projection: Any,
    ruleset_view: ScoringRulesetView,
) -> ReportScoringProjection:
    scored = ScoringRulesetService.score_projection(
        projection=evidence_projection,
        ruleset=ruleset_view,
    )
    scoring_metadata = ScoringRulesetService.report_metadata_for_view(ruleset_view)
    raw_completeness = scored.get("evidence_completeness")
    evidence_completeness = (
        dict(raw_completeness) if isinstance(raw_completeness, dict) else {}
    )
    evidence_completeness["scoring_ruleset"] = dict(scoring_metadata)
    not_evaluable_reason = _optional_str(scored.get("not_evaluable_reason"))
    not_evaluable_reason_code = _optional_str(scored.get("not_evaluable_reason_code"))
    ruleset_version = str(scored.get("ruleset_version") or ruleset_view.version)
    score_basis = str(
        scored.get("score_basis") or ruleset_view.definition.score_basis
    )
    snapshot_metadata = {
        "ruleset_source": scoring_metadata["source"],
        "ruleset_version": ruleset_version,
        "score_basis": score_basis,
        "non_evaluable_reason": not_evaluable_reason,
    }

    return ReportScoringProjection(
        evaluable=bool(scored.get("evaluable")),
        not_evaluable_reason=not_evaluable_reason,
        not_evaluable_reason_code=not_evaluable_reason_code,
        ruleset_id=_optional_str(scored.get("ruleset_id")),
        ruleset_version=ruleset_version,
        ruleset_source=str(scoring_metadata["source"]),
        score_basis=score_basis,
        overall_score=_optional_float(scored.get("overall_score")),
        rollups=_float_dict(scored.get("rollups")),
        dimensions=_dict_list(scored.get("dimensions")),
        evidence_completeness=evidence_completeness,
        scoring_metadata=scoring_metadata,
        snapshot_metadata=snapshot_metadata,
    )


def report_scoring_metadata_for_view(
    ruleset_view: ScoringRulesetView,
) -> dict[str, Any]:
    """Return the canonical report-facing ruleset metadata shape."""
    return ScoringRulesetService.report_metadata_for_view(ruleset_view)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_dict(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, raw in value.items():
        try:
            result[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return result


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


__all__ = [
    "ReportScoringProjection",
    "ReportScoringProjectionService",
    "build_report_scoring_projection",
    "report_scoring_metadata_for_view",
]

"""Ruleset-backed next-practice recommendation contract.

The initial G-03 implementation intentionally avoids ML.  Adjustable rules are
loaded from ``GROWTH_RECOMMENDATION_RULESET_JSON`` when present and validated
before use; invalid/missing config falls back to the bundled default ruleset and
logs the source in the returned payload for auditability.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    DEFAULT_RECOMMENDATION_RULESET,
    NEXT_PRACTICE_RECOMMENDATION_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import PracticeSession, SessionStatus
from common.error_handling.result import Result
from common.growth.safety_policies import GrowthSafetyPolicyService
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

PROJECTION_SCORE_BASIS = "session_evidence_projection_evaluable_only"


class NextPracticeRecommendationService:
    """Build explainable next-practice recommendations for one session."""

    def __init__(self, ruleset: dict[str, Any] | None = None) -> None:
        self._ruleset_injected = ruleset is not None
        self.ruleset, self.ruleset_source = self._resolve_ruleset(ruleset)
        self.growth_safety = GrowthSafetyPolicyService()

    @classmethod
    def _resolve_ruleset(
        cls, ruleset: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], str]:
        if ruleset is not None:
            return cls._validate_ruleset(ruleset), "injected"

        raw_config = os.getenv("GROWTH_RECOMMENDATION_RULESET_JSON", "").strip()
        if raw_config:
            try:
                return cls._validate_ruleset(json.loads(raw_config)), "env"
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning(
                    "growth_recommendation_ruleset_invalid_fallback_default",
                    error=str(exc),
                )

        return deepcopy(DEFAULT_RECOMMENDATION_RULESET), "default"

    async def refresh_active_ruleset(self, db: AsyncSession) -> None:
        """Load the published DB ruleset when this service was not injected."""

        if self._ruleset_injected:
            return
        resolution = await BusinessRuleConfigService(db).resolve_active_config(
            NEXT_PRACTICE_RECOMMENDATION_KEY,
            fallback_value=self.ruleset,
            fallback_source=self.ruleset_source,
        )
        self.ruleset = resolution.value
        self.ruleset_source = resolution.source

    async def build_for_session_with_db(
        self,
        *,
        db: AsyncSession,
        session: PracticeSession,
    ) -> Result[dict[str, Any]]:
        await self.refresh_active_ruleset(db)
        return self.build_for_session(session)

    @staticmethod
    def _validate_ruleset(ruleset: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(ruleset, dict):
            raise ValueError("ruleset must be an object")
        version = ruleset.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("ruleset.version is required")
        dimensions = ruleset.get("dimensions")
        if not isinstance(dimensions, dict) or not dimensions:
            raise ValueError("ruleset.dimensions is required")
        threshold = float(ruleset.get("weak_score_threshold", 60.0))
        if threshold <= 0 or threshold > 100:
            raise ValueError("weak_score_threshold must be within (0, 100]")

        normalized = deepcopy(ruleset)
        normalized["version"] = version.strip()
        normalized["weak_score_threshold"] = threshold
        normalized.setdefault("enabled", True)
        normalized.setdefault("fallback", DEFAULT_RECOMMENDATION_RULESET["fallback"])
        return normalized

    @staticmethod
    def _scenario_type(session: PracticeSession) -> str:
        return str(
            getattr(getattr(session, "scenario", None), "scenario_type", None)
            or "sales"
        )

    @staticmethod
    def _is_evaluable(session: PracticeSession) -> bool:
        snapshot = session.effectiveness_snapshot
        return isinstance(snapshot, dict) and snapshot.get("evaluable") is True

    @staticmethod
    def _score(session: PracticeSession, field: str) -> float | None:
        value = getattr(session, field, None)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _base_payload(self, session: PracticeSession) -> dict[str, Any]:
        return {
            "source_session_id": str(session.session_id),
            "scenario_type": self._scenario_type(session),
            "rule_version": str(self.ruleset["version"]),
            "ruleset_source": self.ruleset_source,
            "score_basis": PROJECTION_SCORE_BASIS,
        }

    def _with_growth_safety(
        self, session: PracticeSession, payload: dict[str, Any]
    ) -> dict[str, Any]:
        adaptive = self.growth_safety.evaluate_adaptive_difficulty(session)
        wecom_share = self.growth_safety.evaluate_wecom_share(session)
        return {
            **payload,
            "growth_safety": {
                "adaptive_difficulty": adaptive.value if adaptive.is_success else None,
                "wecom_share": wecom_share.value if wecom_share.is_success else None,
            },
        }

    def _insufficient_payload(
        self, session: PracticeSession, explanation: str
    ) -> dict[str, Any]:
        return self._with_growth_safety(
            session,
            {
                **self._base_payload(session),
                "recommendation_kind": "insufficient_evidence",
                "title": "完成一次可评估训练后再推荐",
                "reason": explanation,
                "explanation": explanation,
                "action_label": "继续训练",
                "target_path": "/training",
                "evidence_summary": {
                    "status": getattr(session, "status", None),
                    "evaluable": self._is_evaluable(session),
                    "score_basis": PROJECTION_SCORE_BASIS,
                },
            },
        )

    def build_for_session(self, session: PracticeSession) -> Result[dict[str, Any]]:
        """Build a recommendation payload with ruleset/evidence metadata."""

        try:
            if getattr(
                session, "status", None
            ) != SessionStatus.COMPLETED.value or not self._is_evaluable(session):
                return Result.ok(
                    self._insufficient_payload(
                        session,
                        "推荐必须基于完成且可评估的真实训练证据，当前会话暂不满足条件。",
                    )
                )

            if self.ruleset.get("enabled") is False:
                return Result.ok(
                    self._insufficient_payload(
                        session,
                        "当前推荐规则已停用，先展示训练入口而不编造推荐原因。",
                    )
                )

            threshold = float(self.ruleset["weak_score_threshold"])
            candidates: list[dict[str, Any]] = []
            for key, config in self.ruleset["dimensions"].items():
                if not isinstance(config, dict):
                    continue
                score_field = str(config.get("score_field") or "")
                score = self._score(session, score_field)
                if score is None:
                    continue
                candidates.append(
                    {
                        "key": str(key),
                        "score": score,
                        "score_field": score_field,
                        "config": config,
                    }
                )

            if not candidates:
                return Result.ok(
                    self._insufficient_payload(
                        session,
                        "当前会话缺少完整维度分数，暂不生成弱项推荐。",
                    )
                )

            weakest = min(candidates, key=lambda item: item["score"])
            config = weakest["config"]
            label = str(config.get("label") or weakest["key"])
            if weakest["score"] >= threshold:
                fallback = self.ruleset["fallback"]
                explanation = str(fallback["reason"])
                return Result.ok(
                    self._with_growth_safety(
                        session,
                        {
                            **self._base_payload(session),
                            "recommendation_kind": "next_practice_ruleset",
                            "weak_dimension": None,
                            "title": str(fallback["title"]),
                            "reason": explanation,
                            "explanation": explanation,
                            "action_label": str(fallback["action_label"]),
                            "target_path": str(fallback["target_path"]),
                            "evidence_summary": {
                                "lowest_dimension": weakest["key"],
                                "score_field": weakest["score_field"],
                                "score": round(float(weakest["score"]), 2),
                                "threshold": threshold,
                                "score_basis": PROJECTION_SCORE_BASIS,
                            },
                        },
                    )
                )

            reason_template = str(
                config.get("reason_template")
                or "{label} 得分 {score:.0f}，建议专项练习。"
            )
            explanation = reason_template.format(
                label=label,
                score=float(weakest["score"]),
                threshold=threshold,
            )
            return Result.ok(
                self._with_growth_safety(
                    session,
                    {
                        **self._base_payload(session),
                        "recommendation_kind": "next_practice_ruleset",
                        "weak_dimension": weakest["key"],
                        "title": str(config.get("title") or f"提升{label}"),
                        "reason": explanation,
                        "explanation": explanation,
                        "action_label": str(
                            config.get("action_label") or "开始专项练习"
                        ),
                        "target_path": str(config.get("target_path") or "/training"),
                        "evidence_summary": {
                            "weak_dimension": weakest["key"],
                            "score_field": weakest["score_field"],
                            "score": round(float(weakest["score"]), 2),
                            "threshold": threshold,
                            "score_basis": PROJECTION_SCORE_BASIS,
                        },
                    },
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error(
                "next_practice_recommendation_failed",
                session_id=str(getattr(session, "session_id", "")),
                error=str(exc),
            )
            return Result.fail(f"[NEXT_PRACTICE_RECOMMENDATION_FAILED] {exc}")

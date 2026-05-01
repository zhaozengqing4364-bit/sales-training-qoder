"""Central growth safety gates for high-risk retention features.

G-08 adaptive difficulty and G-10 enterprise WeChat sharing are intentionally
safe-by-default.  This module provides a config validated, explainable policy
surface so product code can show truthful disabled/dry-run states without
mutating training difficulty or exposing private highlights before governance is
ready.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

PROJECTION_SCORE_BASIS = "session_evidence_projection_evaluable_only"

DEFAULT_ADAPTIVE_DIFFICULTY_POLICY: dict[str, Any] = {
    "version": "adaptive_difficulty_policy_v1",
    "enabled": False,
    "mode": "dry_run",
    "lower_score_threshold": 55.0,
    "raise_score_threshold": 85.0,
    "max_adjustment_step": 1,
    "rollback_strategy": "keep_current_difficulty",
}

DEFAULT_WECOM_SHARE_POLICY: dict[str, Any] = {
    "version": "wecom_share_policy_v1",
    "enabled": False,
    "adr_approved": False,
    "ttl_days": 7,
    "allowed_domains": [],
    "rollback_strategy": "disable_share_links",
}


class GrowthSafetyPolicyService:
    """Evaluate governed growth features without producing fake affordances."""

    def __init__(
        self,
        *,
        adaptive_policy: dict[str, Any] | None = None,
        wecom_share_policy: dict[str, Any] | None = None,
    ) -> None:
        self.adaptive_policy, self.adaptive_policy_source = self._resolve_policy(
            explicit_policy=adaptive_policy,
            env_name="GROWTH_ADAPTIVE_DIFFICULTY_POLICY_JSON",
            default_policy=DEFAULT_ADAPTIVE_DIFFICULTY_POLICY,
            validator=self._validate_adaptive_policy,
        )
        self.wecom_share_policy, self.wecom_share_policy_source = self._resolve_policy(
            explicit_policy=wecom_share_policy,
            env_name="GROWTH_WECOM_SHARE_POLICY_JSON",
            default_policy=DEFAULT_WECOM_SHARE_POLICY,
            validator=self._validate_wecom_share_policy,
        )

    @staticmethod
    def _resolve_policy(
        *,
        explicit_policy: dict[str, Any] | None,
        env_name: str,
        default_policy: dict[str, Any],
        validator,
    ) -> tuple[dict[str, Any], str]:
        if explicit_policy is not None:
            return validator(explicit_policy), "injected"

        raw_config = os.getenv(env_name, "").strip()
        if raw_config:
            try:
                return validator(json.loads(raw_config)), "env"
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning(
                    "growth_policy_invalid_fallback_default",
                    env_name=env_name,
                    error=str(exc),
                )

        return deepcopy(default_policy), "default"

    @staticmethod
    def _require_version(policy: dict[str, Any]) -> str:
        version = policy.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("policy.version is required")
        return version.strip()

    @classmethod
    def _validate_adaptive_policy(cls, policy: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(policy, dict):
            raise ValueError("adaptive policy must be an object")

        normalized = deepcopy(DEFAULT_ADAPTIVE_DIFFICULTY_POLICY)
        normalized.update(deepcopy(policy))
        normalized["version"] = cls._require_version(normalized)

        mode = str(normalized.get("mode") or "dry_run")
        if mode not in {"dry_run", "active"}:
            raise ValueError("adaptive policy mode must be dry_run or active")
        normalized["mode"] = mode

        lower_threshold = float(normalized.get("lower_score_threshold", 55.0))
        raise_threshold = float(normalized.get("raise_score_threshold", 85.0))
        if not 0 <= lower_threshold < raise_threshold <= 100:
            raise ValueError(
                "adaptive thresholds must satisfy 0 <= lower < raise <= 100"
            )
        normalized["lower_score_threshold"] = lower_threshold
        normalized["raise_score_threshold"] = raise_threshold

        max_step = int(normalized.get("max_adjustment_step", 1))
        if max_step < 1 or max_step > 3:
            raise ValueError("max_adjustment_step must be within 1..3")
        normalized["max_adjustment_step"] = max_step
        normalized["enabled"] = bool(normalized.get("enabled", False))
        normalized["rollback_strategy"] = str(
            normalized.get("rollback_strategy") or "keep_current_difficulty"
        )
        return normalized

    @classmethod
    def _validate_wecom_share_policy(cls, policy: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(policy, dict):
            raise ValueError("wecom share policy must be an object")

        normalized = deepcopy(DEFAULT_WECOM_SHARE_POLICY)
        normalized.update(deepcopy(policy))
        normalized["version"] = cls._require_version(normalized)
        normalized["enabled"] = bool(normalized.get("enabled", False))
        normalized["adr_approved"] = bool(normalized.get("adr_approved", False))

        ttl_days = int(normalized.get("ttl_days", 7))
        if ttl_days < 1 or ttl_days > 90:
            raise ValueError("ttl_days must be within 1..90")
        normalized["ttl_days"] = ttl_days

        allowed_domains = normalized.get("allowed_domains") or []
        if not isinstance(allowed_domains, list) or any(
            not isinstance(domain, str) or not domain.strip()
            for domain in allowed_domains
        ):
            raise ValueError("allowed_domains must be a list of non-empty strings")
        normalized["allowed_domains"] = [domain.strip() for domain in allowed_domains]
        normalized["rollback_strategy"] = str(
            normalized.get("rollback_strategy") or "disable_share_links"
        )
        return normalized

    @staticmethod
    def _session_id(session: Any) -> str:
        return str(getattr(session, "session_id", ""))

    @staticmethod
    def _is_completed(session: Any) -> bool:
        return str(getattr(session, "status", "")) == "completed"

    @staticmethod
    def _is_evaluable(session: Any) -> bool:
        snapshot = getattr(session, "effectiveness_snapshot", None)
        return isinstance(snapshot, dict) and snapshot.get("evaluable") is True

    @staticmethod
    def _overall_score(session: Any) -> float | None:
        direct_score = getattr(session, "overall_score", None)
        if direct_score is not None:
            try:
                return float(direct_score)
            except (TypeError, ValueError):
                return None

        score_values: list[float] = []
        for field in ("logic_score", "accuracy_score", "completeness_score"):
            value = getattr(session, field, None)
            if value is None:
                return None
            try:
                score_values.append(float(value))
            except (TypeError, ValueError):
                return None
        return round(sum(score_values) / len(score_values), 2)

    def _evidence_blocked_payload(
        self,
        *,
        session: Any,
        feature: str,
        policy: dict[str, Any],
        policy_source: str,
    ) -> dict[str, Any]:
        return {
            "feature": feature,
            "status": "blocked_by_evidence",
            "enabled": False,
            "policy_version": policy["version"],
            "policy_source": policy_source,
            "score_basis": PROJECTION_SCORE_BASIS,
            "source_session_id": self._session_id(session),
            "explanation": "增长能力必须基于 completed 且 evaluable 的真实训练证据，当前会话不满足条件。",
            "rollback_strategy": policy["rollback_strategy"],
        }

    def evaluate_adaptive_difficulty(self, session: Any) -> Result[dict[str, Any]]:
        """Return an explainable dry-run adaptive difficulty decision."""

        policy = self.adaptive_policy
        if not self._is_completed(session) or not self._is_evaluable(session):
            return Result.ok(
                self._evidence_blocked_payload(
                    session=session,
                    feature="adaptive_difficulty",
                    policy=policy,
                    policy_source=self.adaptive_policy_source,
                )
            )

        score = self._overall_score(session)
        if score is None:
            return Result.ok(
                {
                    **self._evidence_blocked_payload(
                        session=session,
                        feature="adaptive_difficulty",
                        policy=policy,
                        policy_source=self.adaptive_policy_source,
                    ),
                    "status": "blocked_by_missing_score",
                    "explanation": "当前会话缺少完整评分，不能计算自适应难度建议。",
                }
            )

        if not policy["enabled"]:
            return Result.ok(
                {
                    "feature": "adaptive_difficulty",
                    "status": "disabled",
                    "enabled": False,
                    "mode": policy["mode"],
                    "policy_version": policy["version"],
                    "policy_source": self.adaptive_policy_source,
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "source_session_id": self._session_id(session),
                    "overall_score": score,
                    "suggested_adjustment": "none",
                    "explanation": "自适应难度默认关闭；仅展示当前证据，不改变下一轮训练难度。",
                    "rollback_strategy": policy["rollback_strategy"],
                }
            )

        if score <= policy["lower_score_threshold"]:
            adjustment = "decrease"
            reason = "本次可评估训练得分低于降级阈值，dry-run 建议下一轮降低难度。"
        elif score >= policy["raise_score_threshold"]:
            adjustment = "increase"
            reason = "本次可评估训练得分高于升级阈值，dry-run 建议下一轮提高难度。"
        else:
            adjustment = "keep"
            reason = "本次可评估训练得分处于稳定区间，dry-run 建议保持当前难度。"

        return Result.ok(
            {
                "feature": "adaptive_difficulty",
                "status": "dry_run"
                if policy["mode"] == "dry_run"
                else "active_candidate",
                "enabled": True,
                "mode": policy["mode"],
                "policy_version": policy["version"],
                "policy_source": self.adaptive_policy_source,
                "score_basis": PROJECTION_SCORE_BASIS,
                "source_session_id": self._session_id(session),
                "overall_score": score,
                "suggested_adjustment": adjustment,
                "max_adjustment_step": policy["max_adjustment_step"],
                "explanation": reason,
                "rollback_strategy": policy["rollback_strategy"],
            }
        )

    def evaluate_wecom_share(self, session: Any) -> Result[dict[str, Any]]:
        """Return whether enterprise WeChat sharing may be exposed."""

        policy = self.wecom_share_policy
        if not self._is_completed(session) or not self._is_evaluable(session):
            return Result.ok(
                self._evidence_blocked_payload(
                    session=session,
                    feature="wecom_share",
                    policy=policy,
                    policy_source=self.wecom_share_policy_source,
                )
            )

        can_share = (
            policy["enabled"]
            and policy["adr_approved"]
            and len(policy["allowed_domains"]) > 0
        )
        if not can_share:
            return Result.ok(
                {
                    "feature": "wecom_share",
                    "status": "blocked_by_governance",
                    "enabled": False,
                    "policy_version": policy["version"],
                    "policy_source": self.wecom_share_policy_source,
                    "score_basis": PROJECTION_SCORE_BASIS,
                    "source_session_id": self._session_id(session),
                    "explanation": "企业微信分享默认不展示；需先完成 ADR、安全域名和分享权限配置。",
                    "ttl_days": policy["ttl_days"],
                    "allowed_domains": policy["allowed_domains"],
                    "rollback_strategy": policy["rollback_strategy"],
                }
            )

        return Result.ok(
            {
                "feature": "wecom_share",
                "status": "available",
                "enabled": True,
                "policy_version": policy["version"],
                "policy_source": self.wecom_share_policy_source,
                "score_basis": PROJECTION_SCORE_BASIS,
                "source_session_id": self._session_id(session),
                "explanation": "企业微信分享已通过配置治理，可按 TTL 和安全域名生成受控分享链接。",
                "ttl_days": policy["ttl_days"],
                "allowed_domains": policy["allowed_domains"],
                "rollback_strategy": policy["rollback_strategy"],
            }
        )

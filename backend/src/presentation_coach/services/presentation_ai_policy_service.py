"""Presentation AI policy service.

Provides scoped policy CRUD and effective policy resolution for PPT coaching.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import PresentationAIPolicy
from common.db.models import PracticeSession
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from presentation_coach.services.feedback_service import get_feedback_service

logger = get_logger(__name__)


ALLOWED_SCOPE_TYPES = {"global", "scenario", "presentation"}

DEFAULT_PROMPT_CONFIG: dict[str, Any] = {
    "enable_prompt_first": True,
    "interruption_template_id": None,
}

DEFAULT_RULE_CONFIG: dict[str, Any] = {
    "similarity_threshold": 0.75,
    "point_tracker_cooldown_seconds": 30,
    "feedback_cooldown_seconds": 30,
    "allow_critical_forbidden_interrupt": True,
    "allow_regular_forbidden_interrupt": True,
    "missing_points_interrupt_ratio_threshold": 0.3,
    "missing_points_min_count": 1,
    "missing_points_preview_count": 2,
}

DEFAULT_FALLBACK_CONFIG: dict[str, Any] = {
    "enable_interruption_detector_fallback": True,
    "allow_scenario_prompt_fallback": True,
    "fallback_when_template_missing": True,
    "fallback_when_render_error": True,
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _to_int(value: Any, default: int, minimum: int = 0, maximum: int = 600) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _to_float(
    value: Any,
    default: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


class PresentationAIPolicyService:
    """Business service for presentation AI policy management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize_scope(
        self,
        scope_type: str,
        scope_id: str | None,
    ) -> tuple[str, str | None]:
        scope_result = self._normalize_scope_result(scope_type, scope_id)
        if not scope_result.is_success:
            raise ValueError(scope_result.fallback or "[INVALID_SCOPE]")
        return scope_result.value or ("global", None)

    def _normalize_scope_result(
        self,
        scope_type: str,
        scope_id: str | None,
    ) -> Result[tuple[str, str | None]]:
        normalized_scope = str(scope_type or "").strip().lower()
        if normalized_scope not in ALLOWED_SCOPE_TYPES:
            return Result.fail("[INVALID_SCOPE_TYPE]")

        normalized_scope_id = str(scope_id).strip() if scope_id is not None else None
        if normalized_scope == "global":
            normalized_scope_id = None
        elif not normalized_scope_id:
            return Result.fail("[SCOPE_ID_REQUIRED]")

        return Result.ok((normalized_scope, normalized_scope_id))

    def _default_policy_payload(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "prompt_config": dict(DEFAULT_PROMPT_CONFIG),
            "rule_config": dict(DEFAULT_RULE_CONFIG),
            "fallback_config": dict(DEFAULT_FALLBACK_CONFIG),
        }

    def _normalize_prompt_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_PROMPT_CONFIG, **raw}
        template_id = merged.get("interruption_template_id")
        normalized_template_id = str(template_id).strip() if template_id else None
        return {
            "enable_prompt_first": _to_bool(
                merged.get("enable_prompt_first"),
                DEFAULT_PROMPT_CONFIG["enable_prompt_first"],
            ),
            "interruption_template_id": normalized_template_id or None,
        }

    def _normalize_prompt_patch(self, raw: dict[str, Any]) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if "enable_prompt_first" in raw:
            patch["enable_prompt_first"] = _to_bool(
                raw.get("enable_prompt_first"),
                DEFAULT_PROMPT_CONFIG["enable_prompt_first"],
            )
        if "interruption_template_id" in raw:
            template_id = raw.get("interruption_template_id")
            patch["interruption_template_id"] = (
                str(template_id).strip() if template_id else None
            )
        return patch

    def _normalize_rule_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_RULE_CONFIG, **raw}
        return {
            "similarity_threshold": _to_float(
                merged.get("similarity_threshold"),
                DEFAULT_RULE_CONFIG["similarity_threshold"],
                minimum=0.1,
                maximum=0.99,
            ),
            "point_tracker_cooldown_seconds": _to_int(
                merged.get("point_tracker_cooldown_seconds"),
                DEFAULT_RULE_CONFIG["point_tracker_cooldown_seconds"],
                minimum=0,
                maximum=600,
            ),
            "feedback_cooldown_seconds": _to_int(
                merged.get("feedback_cooldown_seconds"),
                DEFAULT_RULE_CONFIG["feedback_cooldown_seconds"],
                minimum=0,
                maximum=600,
            ),
            "allow_critical_forbidden_interrupt": _to_bool(
                merged.get("allow_critical_forbidden_interrupt"),
                DEFAULT_RULE_CONFIG["allow_critical_forbidden_interrupt"],
            ),
            "allow_regular_forbidden_interrupt": _to_bool(
                merged.get("allow_regular_forbidden_interrupt"),
                DEFAULT_RULE_CONFIG["allow_regular_forbidden_interrupt"],
            ),
            "missing_points_interrupt_ratio_threshold": _to_float(
                merged.get("missing_points_interrupt_ratio_threshold"),
                DEFAULT_RULE_CONFIG["missing_points_interrupt_ratio_threshold"],
                minimum=0.0,
                maximum=1.0,
            ),
            "missing_points_min_count": _to_int(
                merged.get("missing_points_min_count"),
                DEFAULT_RULE_CONFIG["missing_points_min_count"],
                minimum=1,
                maximum=50,
            ),
            "missing_points_preview_count": _to_int(
                merged.get("missing_points_preview_count"),
                DEFAULT_RULE_CONFIG["missing_points_preview_count"],
                minimum=1,
                maximum=10,
            ),
        }

    def _normalize_rule_patch(self, raw: dict[str, Any]) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if "similarity_threshold" in raw:
            patch["similarity_threshold"] = _to_float(
                raw.get("similarity_threshold"),
                DEFAULT_RULE_CONFIG["similarity_threshold"],
                minimum=0.1,
                maximum=0.99,
            )
        if "point_tracker_cooldown_seconds" in raw:
            patch["point_tracker_cooldown_seconds"] = _to_int(
                raw.get("point_tracker_cooldown_seconds"),
                DEFAULT_RULE_CONFIG["point_tracker_cooldown_seconds"],
                minimum=0,
                maximum=600,
            )
        if "feedback_cooldown_seconds" in raw:
            patch["feedback_cooldown_seconds"] = _to_int(
                raw.get("feedback_cooldown_seconds"),
                DEFAULT_RULE_CONFIG["feedback_cooldown_seconds"],
                minimum=0,
                maximum=600,
            )
        if "allow_critical_forbidden_interrupt" in raw:
            patch["allow_critical_forbidden_interrupt"] = _to_bool(
                raw.get("allow_critical_forbidden_interrupt"),
                DEFAULT_RULE_CONFIG["allow_critical_forbidden_interrupt"],
            )
        if "allow_regular_forbidden_interrupt" in raw:
            patch["allow_regular_forbidden_interrupt"] = _to_bool(
                raw.get("allow_regular_forbidden_interrupt"),
                DEFAULT_RULE_CONFIG["allow_regular_forbidden_interrupt"],
            )
        if "missing_points_interrupt_ratio_threshold" in raw:
            patch["missing_points_interrupt_ratio_threshold"] = _to_float(
                raw.get("missing_points_interrupt_ratio_threshold"),
                DEFAULT_RULE_CONFIG["missing_points_interrupt_ratio_threshold"],
                minimum=0.0,
                maximum=1.0,
            )
        if "missing_points_min_count" in raw:
            patch["missing_points_min_count"] = _to_int(
                raw.get("missing_points_min_count"),
                DEFAULT_RULE_CONFIG["missing_points_min_count"],
                minimum=1,
                maximum=50,
            )
        if "missing_points_preview_count" in raw:
            patch["missing_points_preview_count"] = _to_int(
                raw.get("missing_points_preview_count"),
                DEFAULT_RULE_CONFIG["missing_points_preview_count"],
                minimum=1,
                maximum=10,
            )
        return patch

    def _normalize_fallback_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_FALLBACK_CONFIG, **raw}
        return {
            "enable_interruption_detector_fallback": _to_bool(
                merged.get("enable_interruption_detector_fallback"),
                DEFAULT_FALLBACK_CONFIG["enable_interruption_detector_fallback"],
            ),
            "allow_scenario_prompt_fallback": _to_bool(
                merged.get("allow_scenario_prompt_fallback"),
                DEFAULT_FALLBACK_CONFIG["allow_scenario_prompt_fallback"],
            ),
            "fallback_when_template_missing": _to_bool(
                merged.get("fallback_when_template_missing"),
                DEFAULT_FALLBACK_CONFIG["fallback_when_template_missing"],
            ),
            "fallback_when_render_error": _to_bool(
                merged.get("fallback_when_render_error"),
                DEFAULT_FALLBACK_CONFIG["fallback_when_render_error"],
            ),
        }

    def _normalize_fallback_patch(self, raw: dict[str, Any]) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if "enable_interruption_detector_fallback" in raw:
            patch["enable_interruption_detector_fallback"] = _to_bool(
                raw.get("enable_interruption_detector_fallback"),
                DEFAULT_FALLBACK_CONFIG["enable_interruption_detector_fallback"],
            )
        if "allow_scenario_prompt_fallback" in raw:
            patch["allow_scenario_prompt_fallback"] = _to_bool(
                raw.get("allow_scenario_prompt_fallback"),
                DEFAULT_FALLBACK_CONFIG["allow_scenario_prompt_fallback"],
            )
        if "fallback_when_template_missing" in raw:
            patch["fallback_when_template_missing"] = _to_bool(
                raw.get("fallback_when_template_missing"),
                DEFAULT_FALLBACK_CONFIG["fallback_when_template_missing"],
            )
        if "fallback_when_render_error" in raw:
            patch["fallback_when_render_error"] = _to_bool(
                raw.get("fallback_when_render_error"),
                DEFAULT_FALLBACK_CONFIG["fallback_when_render_error"],
            )
        return patch

    def _serialize_record(self, record: PresentationAIPolicy) -> dict[str, Any]:
        return {
            "id": record.id,
            "scope_type": record.scope_type,
            "scope_id": record.scope_id,
            "enabled": bool(record.enabled),
            "prompt_config": self._normalize_prompt_config(
                _as_dict(record.prompt_config)
            ),
            "rule_config": self._normalize_rule_config(_as_dict(record.rule_config)),
            "fallback_config": self._normalize_fallback_config(
                _as_dict(record.fallback_config)
            ),
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            "updated_by": record.updated_by,
        }

    async def _load_record(
        self,
        scope_type: str,
        scope_id: str | None,
    ) -> PresentationAIPolicy | None:
        result = await self.db.execute(
            select(PresentationAIPolicy).where(
                PresentationAIPolicy.scope_type == scope_type,
                PresentationAIPolicy.scope_id.is_(None)
                if scope_id is None
                else PresentationAIPolicy.scope_id == scope_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_scope_policy(
        self,
        *,
        scope_type: str,
        scope_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_scope, normalized_scope_id = self._normalize_scope(
            scope_type, scope_id
        )
        record = await self._load_record(normalized_scope, normalized_scope_id)
        payload = self._default_policy_payload()

        if record:
            payload = {
                "enabled": bool(record.enabled),
                "prompt_config": self._normalize_prompt_config(
                    _as_dict(record.prompt_config)
                ),
                "rule_config": self._normalize_rule_config(
                    _as_dict(record.rule_config)
                ),
                "fallback_config": self._normalize_fallback_config(
                    _as_dict(record.fallback_config)
                ),
            }

        return {
            "scope_type": normalized_scope,
            "scope_id": normalized_scope_id,
            "exists": record is not None,
            "policy": payload,
            "meta": {
                "id": record.id if record else None,
                "updated_at": record.updated_at.isoformat()
                if record and record.updated_at
                else None,
                "updated_by": record.updated_by if record else None,
            },
        }

    async def get_scope_policy_result(
        self,
        *,
        scope_type: str,
        scope_id: str | None = None,
    ) -> Result[dict[str, Any]]:
        scope_result = self._normalize_scope_result(scope_type, scope_id)
        if not scope_result.is_success:
            return Result.fail(scope_result.fallback or "[INVALID_SCOPE]")

        normalized_scope, normalized_scope_id = scope_result.value or ("global", None)
        return Result.ok(
            await self.get_scope_policy(
                scope_type=normalized_scope,
                scope_id=normalized_scope_id,
            )
        )

    async def upsert_scope_policy(
        self,
        *,
        scope_type: str,
        scope_id: str | None,
        payload: dict[str, Any],
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        normalized_scope, normalized_scope_id = self._normalize_scope(
            scope_type, scope_id
        )
        policy_payload = _as_dict(payload)

        record = await self._load_record(normalized_scope, normalized_scope_id)
        if not record:
            defaults = self._default_policy_payload()
            record = PresentationAIPolicy(
                id=str(uuid.uuid4()),
                scope_type=normalized_scope,
                scope_id=normalized_scope_id,
                enabled=defaults["enabled"],
                prompt_config=defaults["prompt_config"],
                rule_config=defaults["rule_config"],
                fallback_config=defaults["fallback_config"],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.db.add(record)

        if "enabled" in policy_payload:
            record.enabled = _to_bool(
                policy_payload.get("enabled"), bool(record.enabled)
            )

        if "prompt_config" in policy_payload:
            record.prompt_config = self._normalize_prompt_config(
                _as_dict(policy_payload.get("prompt_config"))
            )

        if "rule_config" in policy_payload:
            record.rule_config = self._normalize_rule_config(
                _as_dict(policy_payload.get("rule_config"))
            )

        if "fallback_config" in policy_payload:
            record.fallback_config = self._normalize_fallback_config(
                _as_dict(policy_payload.get("fallback_config"))
            )

        record.updated_by = updated_by
        record.updated_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(record)

        return await self.get_scope_policy(
            scope_type=normalized_scope,
            scope_id=normalized_scope_id,
        )

    async def resolve_effective_policy(
        self,
        *,
        scenario_id: str | None = None,
        presentation_id: str | None = None,
    ) -> dict[str, Any]:
        default_policy = self._default_policy_payload()
        effective_policy = {
            "enabled": True,
            "prompt_config": dict(default_policy["prompt_config"]),
            "rule_config": dict(default_policy["rule_config"]),
            "fallback_config": dict(default_policy["fallback_config"]),
        }

        global_policy = await self._load_record("global", None)
        scenario_policy = (
            await self._load_record("scenario", scenario_id) if scenario_id else None
        )
        presentation_policy = (
            await self._load_record("presentation", presentation_id)
            if presentation_id
            else None
        )

        most_specific = presentation_policy or scenario_policy or global_policy
        if most_specific and not most_specific.enabled:
            return {
                **effective_policy,
                "source": {
                    "resolution": "default_guardrail",
                    "disabled_scope": most_specific.scope_type,
                },
                "resolved_at": datetime.now(UTC).isoformat(),
            }

        applied_scopes: list[str] = []
        for scope_name, policy in (
            ("global", global_policy),
            ("scenario", scenario_policy),
            ("presentation", presentation_policy),
        ):
            if not policy or not policy.enabled:
                continue
            effective_policy["prompt_config"] = {
                **effective_policy["prompt_config"],
                **self._normalize_prompt_patch(_as_dict(policy.prompt_config)),
            }
            effective_policy["rule_config"] = {
                **effective_policy["rule_config"],
                **self._normalize_rule_patch(_as_dict(policy.rule_config)),
            }
            effective_policy["fallback_config"] = {
                **effective_policy["fallback_config"],
                **self._normalize_fallback_patch(_as_dict(policy.fallback_config)),
            }
            applied_scopes.append(scope_name)

        source = {
            "resolution": "scoped_merge",
            "applied_scopes": applied_scopes,
            "scenario_id": scenario_id,
            "presentation_id": presentation_id,
            "global_policy_id": global_policy.id if global_policy else None,
            "scenario_policy_id": scenario_policy.id if scenario_policy else None,
            "presentation_policy_id": (
                presentation_policy.id if presentation_policy else None
            ),
        }

        return {
            **effective_policy,
            "source": source,
            "resolved_at": datetime.now(UTC).isoformat(),
        }

    async def resolve_effective_policy_for_session(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        policy_result = await self.resolve_effective_policy_for_session_result(
            session_id=session_id
        )
        if not policy_result.is_success:
            raise ValueError(policy_result.fallback or "[SESSION_NOT_FOUND]")
        return policy_result.value or {}

    async def resolve_effective_policy_for_session_result(
        self,
        *,
        session_id: str,
    ) -> Result[dict[str, Any]]:
        session_result = await self.db.execute(
            select(
                PracticeSession.scenario_id,
                PracticeSession.presentation_id,
            ).where(PracticeSession.session_id == session_id)
        )
        session_identity = session_result.first()
        if not session_identity:
            return Result.fail("[SESSION_NOT_FOUND]")

        scenario_id = str(session_identity[0]) if session_identity[0] else None
        presentation_id = str(session_identity[1]) if session_identity[1] else None
        effective = await self.resolve_effective_policy(
            scenario_id=scenario_id,
            presentation_id=presentation_id,
        )
        effective["session_id"] = session_id
        return Result.ok(effective)

    async def preview_policy_decision(
        self,
        *,
        transcript: str,
        required_points: list[str],
        forbidden_words: list[Any],
        scenario_id: str | None = None,
        presentation_id: str | None = None,
    ) -> dict[str, Any]:
        effective_policy = await self.resolve_effective_policy(
            scenario_id=scenario_id,
            presentation_id=presentation_id,
        )

        preview_session_id = f"preview-{uuid.uuid4()}"
        feedback_service = get_feedback_service()

        normalized_forbidden_words: list[dict[str, Any]] = []
        for word in forbidden_words:
            if isinstance(word, dict) and isinstance(word.get("phrase"), str):
                normalized_forbidden_words.append(word)
            elif isinstance(word, str) and word.strip():
                normalized_forbidden_words.append(
                    {
                        "phrase": word.strip(),
                        "suggested_alternative": "",
                        "is_regex": False,
                        "severity": "warning",
                    }
                )

        try:
            init_result = await feedback_service.initialize_page(
                session_id=preview_session_id,
                page_number=1,
                required_points=required_points,
                forbidden_words=normalized_forbidden_words,
                rule_config=_as_dict(effective_policy.get("rule_config")),
            )
            if not init_result.is_success:
                return {
                    "effective_policy": effective_policy,
                    "result": {
                        "should_interrupt": False,
                        "reason": "",
                        "message": "策略预览初始化失败，已回退默认。",
                        "point_coverage": {
                            "total": len(required_points),
                            "covered": 0,
                            "missing": len(required_points),
                        },
                        "forbidden_matches": [],
                    },
                }

            feedback_result = await feedback_service.check_transcript(
                session_id=preview_session_id,
                transcript=transcript,
            )
            if not feedback_result.is_success or feedback_result.value is None:
                return {
                    "effective_policy": effective_policy,
                    "result": {
                        "should_interrupt": False,
                        "reason": "",
                        "message": "未触发中断",
                        "point_coverage": {
                            "total": len(required_points),
                            "covered": 0,
                            "missing": len(required_points),
                        },
                        "forbidden_matches": [],
                    },
                }

            feedback = feedback_result.value
            covered_count = sum(
                1 for point in feedback.point_results if point.is_covered
            )
            total_count = len(feedback.point_results)

            return {
                "effective_policy": effective_policy,
                "result": {
                    "should_interrupt": feedback.should_interrupt,
                    "reason": feedback.interruption_reason,
                    "message": feedback.interruption_message,
                    "point_coverage": {
                        "total": total_count,
                        "covered": covered_count,
                        "missing": max(0, total_count - covered_count),
                    },
                    "forbidden_matches": [
                        {
                            "word": item.word,
                            "suggestion": item.suggestion,
                            "severity": item.severity,
                        }
                        for item in feedback.forbidden_matches
                    ],
                },
            }
        finally:
            feedback_service.clear_session(preview_session_id)

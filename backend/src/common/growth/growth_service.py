"""Growth center service for achievements, notifications, AI coach, and goals."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.business_rules.defaults import (
    ACHIEVEMENT_RULES_KEY,
    AI_COACH_RULES_KEY,
    DEFAULT_ACHIEVEMENT_RULESET,
    DEFAULT_AI_COACH_RULESET,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import (
    Achievement,
    Notification,
    PracticeSession,
    SessionStatus,
    UserAchievement,
    UserGoal,
)
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class GrowthCenterService:
    """Config-backed growth service.

    Rulesets can be overridden with JSON environment variables:
    - GROWTH_ACHIEVEMENT_RULESET_JSON
    - GROWTH_AI_COACH_RULESET_JSON

    Invalid config falls back to defaults and records the active ruleset version
    in evidence payloads for audit and rollback.
    """

    def __init__(
        self,
        *,
        achievement_ruleset: dict[str, Any] | None = None,
        ai_coach_ruleset: dict[str, Any] | None = None,
    ) -> None:
        self._achievement_ruleset_injected = achievement_ruleset is not None
        self._ai_coach_ruleset_injected = ai_coach_ruleset is not None
        self.achievement_ruleset = self._load_ruleset(
            injected=achievement_ruleset,
            env_name="GROWTH_ACHIEVEMENT_RULESET_JSON",
            default=DEFAULT_ACHIEVEMENT_RULESET,
            required_key="achievements",
        )
        self.ai_coach_ruleset = self._load_ruleset(
            injected=ai_coach_ruleset,
            env_name="GROWTH_AI_COACH_RULESET_JSON",
            default=DEFAULT_AI_COACH_RULESET,
            required_key="dimensions",
        )
        self.achievement_ruleset_source = "injected" if achievement_ruleset else "default"
        self.ai_coach_ruleset_source = "injected" if ai_coach_ruleset else "default"

    async def _refresh_active_rulesets(self, *, db: AsyncSession) -> None:
        """Load DB-published business-rule configs when available.

        Constructor/env-injected rules remain authoritative for isolated tests and
        explicit overrides; runtime API calls use the database resolver with the
        already-loaded ruleset as the safe fallback.
        """

        service = BusinessRuleConfigService(db)
        if not self._achievement_ruleset_injected:
            achievement_resolution = await service.resolve_active_config(
                ACHIEVEMENT_RULES_KEY,
                fallback_value=self.achievement_ruleset,
                fallback_source=self.achievement_ruleset_source,
            )
            self.achievement_ruleset = achievement_resolution.value
            self.achievement_ruleset_source = achievement_resolution.source
        if not self._ai_coach_ruleset_injected:
            ai_coach_resolution = await service.resolve_active_config(
                AI_COACH_RULES_KEY,
                fallback_value=self.ai_coach_ruleset,
                fallback_source=self.ai_coach_ruleset_source,
            )
            self.ai_coach_ruleset = ai_coach_resolution.value
            self.ai_coach_ruleset_source = ai_coach_resolution.source

    @staticmethod
    def _load_ruleset(
        *,
        injected: dict[str, Any] | None,
        env_name: str,
        default: dict[str, Any],
        required_key: str,
    ) -> dict[str, Any]:
        candidate = injected
        if candidate is None:
            raw = os.getenv(env_name, "").strip()
            if raw:
                try:
                    candidate = json.loads(raw)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "growth_ruleset_json_invalid_fallback_default",
                        env_name=env_name,
                        error=str(exc),
                    )
        if not isinstance(candidate, dict):
            candidate = deepcopy(default)

        version = candidate.get("version")
        if not isinstance(version, str) or not version.strip():
            candidate = deepcopy(default)
        if required_key not in candidate:
            candidate = deepcopy(default)
        return candidate

    @staticmethod
    def _overall_score(session: PracticeSession) -> float | None:
        if any(
            getattr(session, field) is None
            for field in ("logic_score", "accuracy_score", "completeness_score")
        ):
            return None
        return round(
            (
                float(session.logic_score or 0)
                + float(session.accuracy_score or 0)
                + float(session.completeness_score or 0)
            )
            / 3,
            2,
        )

    @staticmethod
    def _is_evaluable(session: PracticeSession) -> bool:
        snapshot = session.effectiveness_snapshot
        return isinstance(snapshot, dict) and snapshot.get("evaluable") is True

    @classmethod
    def _is_completed_evaluable(cls, session: PracticeSession) -> bool:
        return (
            session.status == SessionStatus.COMPLETED.value
            and cls._is_evaluable(session)
            and cls._overall_score(session) is not None
        )

    async def _load_completed_sessions(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        limit: int = 100,
    ) -> list[PracticeSession]:
        result = await db.execute(
            select(PracticeSession)
            .options(selectinload(PracticeSession.scenario))
            .where(PracticeSession.user_id == user_id)
            .where(PracticeSession.status == SessionStatus.COMPLETED.value)
            .order_by(PracticeSession.start_time.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _eligible_sessions(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        limit: int = 100,
    ) -> list[PracticeSession]:
        return [
            session
            for session in await self._load_completed_sessions(
                db=db, user_id=user_id, limit=limit
            )
            if self._is_completed_evaluable(session)
        ]

    @staticmethod
    def _achievement_payload(
        achievement: Achievement,
        user_achievement: UserAchievement | None = None,
    ) -> dict[str, Any]:
        return {
            "achievement_id": str(achievement.achievement_id),
            "code": achievement.code,
            "name": achievement.name,
            "description": achievement.description,
            "icon_key": achievement.icon_key,
            "unlocked_at": user_achievement.unlocked_at.isoformat()
            if user_achievement and user_achievement.unlocked_at
            else None,
            "evidence": user_achievement.evidence_json if user_achievement else None,
        }

    @staticmethod
    def _notification_payload(notification: Notification) -> dict[str, Any]:
        return {
            "notification_id": str(notification.notification_id),
            "type": notification.type,
            "title": notification.title,
            "content": notification.content,
            "action_label": notification.action_label,
            "action_path": notification.action_path,
            "source": notification.source,
            "evidence": notification.evidence_json,
            "is_read": bool(notification.is_read),
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
            "expires_at": notification.expires_at.isoformat()
            if notification.expires_at
            else None,
            "created_at": notification.created_at.isoformat()
            if notification.created_at
            else None,
        }

    async def _sync_achievement_definitions(
        self, *, db: AsyncSession
    ) -> list[Achievement]:
        definitions: list[Achievement] = []
        for item in self.achievement_ruleset.get("achievements", []):
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            condition = item.get("condition")
            if not code or not isinstance(condition, dict):
                continue

            result = await db.execute(select(Achievement).where(Achievement.code == code))
            achievement = result.scalar_one_or_none()
            if achievement is None:
                achievement = Achievement(code=code)
                db.add(achievement)
            achievement.name = str(item.get("name") or code)
            achievement.description = str(item.get("description") or code)
            achievement.icon_key = str(item.get("icon_key") or "trophy")
            achievement.condition_json = {
                "ruleset_version": self.achievement_ruleset.get("version"),
                **condition,
            }
            achievement.enabled = bool(item.get("enabled", True))
            definitions.append(achievement)

        await db.flush()
        return definitions

    @staticmethod
    def _condition_met(
        achievement: Achievement,
        *,
        eligible_sessions: list[PracticeSession],
    ) -> tuple[bool, dict[str, Any]]:
        condition = achievement.condition_json if isinstance(achievement.condition_json, dict) else {}
        condition_type = condition.get("type")
        scores = [
            score
            for score in (
                GrowthCenterService._overall_score(session)
                for session in eligible_sessions
            )
            if score is not None
        ]
        if condition_type == "evaluable_session_count":
            minimum = int(condition.get("min") or 1)
            return len(eligible_sessions) >= minimum, {
                "evaluable_session_count": len(eligible_sessions),
                "min": minimum,
                "ruleset_version": condition.get("ruleset_version"),
            }
        if condition_type == "max_overall_score":
            minimum_score = float(condition.get("min") or 80)
            max_score = max(scores) if scores else 0.0
            return max_score >= minimum_score, {
                "max_overall_score": max_score,
                "min": minimum_score,
                "ruleset_version": condition.get("ruleset_version"),
            }
        return False, {"reason": "unsupported_condition"}

    async def evaluate_achievements(
        self,
        *,
        db: AsyncSession,
        user_id: str,
    ) -> Result[dict[str, Any]]:
        try:
            eligible_sessions = await self._eligible_sessions(db=db, user_id=user_id)
            definitions = await self._sync_achievement_definitions(db=db)
            newly_unlocked: list[dict[str, Any]] = []

            for achievement in definitions:
                if not achievement.enabled:
                    continue
                is_met, evidence = self._condition_met(
                    achievement,
                    eligible_sessions=eligible_sessions,
                )
                if not is_met:
                    continue
                existing_result = await db.execute(
                    select(UserAchievement).where(
                        UserAchievement.user_id == user_id,
                        UserAchievement.achievement_id == achievement.achievement_id,
                    )
                )
                existing = existing_result.scalar_one_or_none()
                if existing is not None:
                    continue

                latest_session = eligible_sessions[0] if eligible_sessions else None
                unlock = UserAchievement(
                    user_id=user_id,
                    achievement_id=achievement.achievement_id,
                    session_id=str(latest_session.session_id)
                    if latest_session is not None
                    else None,
                    evidence_json=evidence,
                )
                db.add(unlock)
                await db.flush()
                newly_unlocked.append(self._achievement_payload(achievement, unlock))
                await self._create_notification_if_absent(
                    db=db,
                    user_id=user_id,
                    type_="achievement",
                    title=f"解锁徽章：{achievement.name}",
                    content=achievement.description,
                    action_label="查看徽章",
                    action_path="/",
                    source=f"achievement:{achievement.code}",
                    evidence=evidence,
                )

            await db.commit()
            return Result.ok(
                {
                    "newly_unlocked": newly_unlocked,
                    "ruleset_version": self.achievement_ruleset.get("version"),
                }
            )
        except (SQLAlchemyError, ValueError, TypeError, IntegrityError) as exc:
            await db.rollback()
            logger.error("growth_achievements_evaluate_failed", user_id=user_id, error=str(exc))
            return Result.fail(f"[ACHIEVEMENT_EVALUATION_FAILED] {exc}")

    async def _create_notification_if_absent(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        type_: str,
        title: str,
        content: str,
        action_label: str | None,
        action_path: str | None,
        source: str,
        evidence: dict[str, Any],
    ) -> Notification | None:
        existing_result = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.source == source,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            return None
        notification = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            content=content,
            action_label=action_label,
            action_path=action_path,
            source=source,
            evidence_json=evidence,
            is_read=False,
        )
        db.add(notification)
        await db.flush()
        return notification

    async def generate_ai_coach_notification(
        self,
        *,
        db: AsyncSession,
        user_id: str,
    ) -> Result[dict[str, Any] | None]:
        try:
            if self.ai_coach_ruleset.get("enabled") is False:
                return Result.ok(None)
            eligible_sessions = await self._eligible_sessions(db=db, user_id=user_id, limit=10)
            if not eligible_sessions:
                return Result.ok(None)

            latest = eligible_sessions[0]
            threshold = float(self.ai_coach_ruleset.get("weak_score_threshold", 60.0))
            dimensions = [
                item for item in self.ai_coach_ruleset.get("dimensions", []) if isinstance(item, dict)
            ]
            scored_dimensions = []
            for dimension in dimensions:
                field = str(dimension.get("score_field") or "")
                score = getattr(latest, field, None)
                if score is None:
                    continue
                scored_dimensions.append(
                    {
                        "key": str(dimension.get("key") or field),
                        "label": str(dimension.get("label") or field),
                        "field": field,
                        "score": float(score),
                    }
                )
            if not scored_dimensions:
                return Result.ok(None)

            weakest = min(scored_dimensions, key=lambda item: item["score"])
            if weakest["score"] >= threshold:
                return Result.ok(None)

            source = f"ai_coach:{latest.session_id}"
            notification = await self._create_notification_if_absent(
                db=db,
                user_id=user_id,
                type_="ai_coach",
                title=f"AI 教练建议：先练{weakest['label']}",
                content=(
                    f"最近一次可评估训练中，{weakest['label']}为 "
                    f"{weakest['score']:.0f} 分，低于 {threshold:.0f} 分阈值。"
                    "建议下一轮先做 10 分钟专项训练。"
                ),
                action_label="按建议训练",
                action_path=f"/practice/{latest.session_id}/report",
                source=source,
                evidence={
                    "source_session_id": str(latest.session_id),
                    "score_field": weakest["field"],
                    "score": weakest["score"],
                    "threshold": threshold,
                    "ruleset_version": self.ai_coach_ruleset.get("version"),
                },
            )
            await db.commit()
            return Result.ok(self._notification_payload(notification) if notification else None)
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            await db.rollback()
            logger.error("ai_coach_notification_failed", user_id=user_id, error=str(exc))
            return Result.fail(f"[AI_COACH_NOTIFICATION_FAILED] {exc}")

    async def list_notifications(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        include_read: bool = False,
    ) -> Result[dict[str, Any]]:
        try:
            now = datetime.now(UTC)
            query = (
                select(Notification)
                .where(Notification.user_id == user_id)
                .where(
                    (Notification.expires_at.is_(None))
                    | (Notification.expires_at >= now)
                )
                .order_by(Notification.created_at.desc())
                .limit(20)
            )
            if not include_read:
                query = query.where(Notification.is_read.is_(False))

            result = await db.execute(query)
            items = [self._notification_payload(item) for item in result.scalars().all()]
            unread = sum(1 for item in items if not item["is_read"])
            return Result.ok({"items": items, "unread_count": unread})
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error("notification_list_failed", user_id=user_id, error=str(exc))
            return Result.fail(f"[NOTIFICATION_LIST_FAILED] {exc}")

    async def mark_notification_read(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        notification_id: str,
    ) -> Result[dict[str, Any]]:
        try:
            result = await db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.notification_id == notification_id,
                )
            )
            notification = result.scalar_one_or_none()
            if notification is None:
                return Result.fail("[NOTIFICATION_NOT_FOUND] Notification not found")
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(notification)
            return Result.ok(self._notification_payload(notification))
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            await db.rollback()
            logger.error("notification_mark_read_failed", user_id=user_id, error=str(exc))
            return Result.fail(f"[NOTIFICATION_MARK_READ_FAILED] {exc}")

    async def upsert_goal(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        goal_type: str,
        target_count: int,
        period: str,
        start_date: date,
        end_date: date,
    ) -> Result[dict[str, Any]]:
        try:
            if target_count <= 0:
                return Result.fail("[INVALID_GOAL_TARGET] target_count must be positive")
            if end_date < start_date:
                return Result.fail("[INVALID_GOAL_RANGE] end_date must be >= start_date")

            active_result = await db.execute(
                select(UserGoal).where(UserGoal.user_id == user_id, UserGoal.is_active.is_(True))
            )
            for goal in active_result.scalars().all():
                goal.is_active = False

            goal = UserGoal(
                user_id=user_id,
                goal_type=goal_type,
                target_count=target_count,
                period=period,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
            )
            db.add(goal)
            await db.commit()
            await db.refresh(goal)
            payload = await self._goal_payload(db=db, goal=goal)
            return Result.ok(payload)
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            await db.rollback()
            logger.error("goal_upsert_failed", user_id=user_id, error=str(exc))
            return Result.fail(f"[GOAL_UPSERT_FAILED] {exc}")

    async def _goal_payload(self, *, db: AsyncSession, goal: UserGoal) -> dict[str, Any]:
        start_dt = datetime.combine(goal.start_date, time.min, tzinfo=UTC)
        end_dt = datetime.combine(goal.end_date, time.max, tzinfo=UTC)
        sessions = await self._eligible_sessions(db=db, user_id=str(goal.user_id), limit=200)
        scoped = [
            session
            for session in sessions
            if session.start_time
            and start_dt <= (
                session.start_time.replace(tzinfo=UTC)
                if session.start_time.tzinfo is None
                else session.start_time.astimezone(UTC)
            )
            <= end_dt
        ]
        if goal.goal_type == "monthly_presentations":
            scoped = [
                session
                for session in scoped
                if str(getattr(getattr(session, "scenario", None), "scenario_type", "")) == "presentation"
            ]
        current_progress = len(scoped)
        target_count = int(goal.target_count)
        return {
            "goal_id": str(goal.goal_id),
            "goal_type": goal.goal_type,
            "period": goal.period,
            "target_count": target_count,
            "current_progress": current_progress,
            "progress_ratio": min(1.0, current_progress / target_count if target_count else 0.0),
            "start_date": goal.start_date.isoformat(),
            "end_date": goal.end_date.isoformat(),
            "is_active": bool(goal.is_active),
        }

    async def _current_goal(self, *, db: AsyncSession, user_id: str) -> dict[str, Any] | None:
        result = await db.execute(
            select(UserGoal)
            .where(UserGoal.user_id == user_id, UserGoal.is_active.is_(True))
            .order_by(UserGoal.created_at.desc())
            .limit(1)
        )
        goal = result.scalar_one_or_none()
        if goal is None:
            return None
        return await self._goal_payload(db=db, goal=goal)

    async def get_dashboard_growth(
        self,
        *,
        db: AsyncSession,
        user_id: str,
    ) -> Result[dict[str, Any]]:
        try:
            await self.evaluate_achievements(db=db, user_id=user_id)
            await self.generate_ai_coach_notification(db=db, user_id=user_id)

            achievements_result = await db.execute(
                select(UserAchievement)
                .options(selectinload(UserAchievement.achievement))
                .where(UserAchievement.user_id == user_id)
                .order_by(UserAchievement.unlocked_at.desc())
            )
            unlocked = [
                self._achievement_payload(item.achievement, item)
                for item in achievements_result.scalars().all()
                if item.achievement is not None
            ]
            notifications = await self.list_notifications(db=db, user_id=user_id)
            goal = await self._current_goal(db=db, user_id=user_id)
            return Result.ok(
                {
                    "achievements": {"unlocked": unlocked},
                    "notifications": notifications.value if notifications.is_success else {"items": [], "unread_count": 0},
                    "goal": goal,
                    "rules": {
                        "achievement_ruleset_version": self.achievement_ruleset.get("version"),
                        "ai_coach_ruleset_version": self.ai_coach_ruleset.get("version"),
                    },
                }
            )
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error("growth_dashboard_failed", user_id=user_id, error=str(exc))
            return Result.fail(f"[GROWTH_DASHBOARD_FAILED] {exc}")

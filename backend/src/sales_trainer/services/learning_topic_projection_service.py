from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerBusinessEtiquetteQuizAttempt
from sales_trainer.schemas import NewcomerLearningTopicConfig
from sales_trainer.services.learning_topic_config_service import (
    NewcomerLearningTopicConfigService,
)


class LearningTopicProjectionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def learner_topics(self, *, user_id: str) -> list[dict[str, Any]]:
        active = await NewcomerLearningTopicConfigService(self._db).active_payload()
        if active is None:
            return []
        payload, revision = active
        topics = [topic for topic in payload.topics if topic.enabled]
        if not topics:
            return []
        attempts = await self._latest_attempts_by_unit(
            user_id=user_id,
            unit_keys=[
                unit.unit_key
                for topic in topics
                for unit in topic.learning_units
                if unit.enabled
            ],
        )
        return [
            self._topic_payload(
                topic,
                attempts,
                revision_id=str(revision.revision_id),
                revision_no=int(revision.revision_no),
            )
            for topic in sorted(topics, key=lambda item: item.order_index)
        ]

    async def _latest_attempts_by_unit(
        self,
        *,
        user_id: str,
        unit_keys: list[str],
    ) -> dict[str, SalesTrainerBusinessEtiquetteQuizAttempt]:
        if not unit_keys:
            return {}
        result = await self._db.execute(
            select(SalesTrainerBusinessEtiquetteQuizAttempt)
            .where(
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == user_id,
                SalesTrainerBusinessEtiquetteQuizAttempt.learning_unit_key.in_(
                    unit_keys
                ),
            )
            .order_by(SalesTrainerBusinessEtiquetteQuizAttempt.submitted_at.desc())
        )
        latest: dict[str, SalesTrainerBusinessEtiquetteQuizAttempt] = {}
        for attempt in result.scalars().all():
            unit_key = str(attempt.learning_unit_key)
            latest.setdefault(unit_key, attempt)
        return latest

    def _topic_payload(
        self,
        topic: NewcomerLearningTopicConfig,
        attempts: dict[str, SalesTrainerBusinessEtiquetteQuizAttempt],
        *,
        revision_id: str,
        revision_no: int,
    ) -> dict[str, Any]:
        units = [
            _unit_payload(unit, attempts.get(unit.unit_key))
            for unit in sorted(topic.learning_units, key=lambda item: item.order_index)
            if unit.enabled
        ]
        status = _topic_status(units)
        ai_coach = None
        if topic.ai_coach is not None:
            configured = (
                bool(topic.ai_coach.prompt_template_id)
                if topic.ai_coach.enabled
                else False
            )
            ai_coach = {
                "enabled": topic.ai_coach.enabled,
                "configured": configured,
                "available": topic.ai_coach.enabled and configured,
                "coach_path": _coach_path(topic.topic_key)
                if topic.ai_coach.enabled and configured
                else None,
                "disabled_reason": None
                if topic.ai_coach.enabled
                else "学习专题未启用 AI 教练。",
                "allowed_interaction_types": list(
                    topic.ai_coach.allowed_interaction_types
                ),
            }
        return {
            "topic_key": topic.topic_key,
            "source_module_key": topic.source_module_key,
            "title": topic.title,
            "description": topic.description,
            "order_index": topic.order_index,
            "learning_content_id": topic.learning_content_id,
            "required": False,
            "blocks_next": False,
            "score_display_policy": topic.score_display_policy,
            "status": status,
            "units": units,
            "ai_coach": ai_coach,
            "source": {
                "resource_type": "newcomer_learning_topics",
                "logical_id": "newcomer_learning_topics_v1",
                "revision_id": revision_id,
                "revision_no": revision_no,
                "future_only": True,
            },
        }


def _coach_path(topic_key: str) -> str | None:
    if topic_key == "business_etiquette":
        return "/sales-trainer/business-skills/coach"
    if topic_key == "customer_faq":
        return "/sales-trainer/learning-topics/customer-faq/coach"
    return None


def _unit_payload(
    unit: Any, attempt: SalesTrainerBusinessEtiquetteQuizAttempt | None
) -> dict[str, Any]:
    passed = attempt.passed if attempt is not None else None
    status = "not_started"
    if attempt is not None:
        if attempt.status == "scored" and passed is True:
            status = "passed"
        elif attempt.status == "scored" and passed is False:
            status = "failed"
        else:
            status = str(attempt.status)
    return {
        "unit_key": unit.unit_key,
        "title": unit.title,
        "order_index": unit.order_index,
        "enabled": unit.enabled,
        "capability_keys": list(unit.capability_keys),
        "require_quiz": unit.require_quiz,
        "quiz_question_count": unit.quiz_question_count,
        "quiz_pass_threshold": unit.quiz_pass_threshold,
        "score": float(attempt.total_score)
        if attempt and attempt.total_score is not None
        else None,
        "max_score": float(attempt.max_score)
        if attempt and attempt.max_score is not None
        else None,
        "passed": passed,
        "status": status,
        "latest_attempt_id": str(attempt.attempt_id) if attempt else None,
        "latest_attempt_submitted_at": attempt.submitted_at if attempt else None,
    }


def _topic_status(units: list[dict[str, Any]]) -> str:
    quiz_units = [unit for unit in units if unit.get("require_quiz")]
    if quiz_units and all(unit.get("passed") is True for unit in quiz_units):
        return "passed"
    if any(unit.get("passed") is False for unit in quiz_units):
        return "needs_remediation"
    if any(unit.get("latest_attempt_id") for unit in units):
        return "in_progress"
    return "not_started"

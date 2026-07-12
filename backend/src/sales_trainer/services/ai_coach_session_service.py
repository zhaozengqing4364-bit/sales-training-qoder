"""Activity-owned AI Coach session lifecycle."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    SalesTrainerAiCoachSession,
    SalesTrainerAiCoachTurn,
)
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AiCoachActivityConfig
from sales_trainer.schemas import AiCoachConfig
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService


class AiCoachSessionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachSessionService:
    def __init__(self, db: AsyncSession, **_: Any) -> None:
        self._db = db
        self._logs = OperationLogService(db)

    async def create_activity_session(
        self, *, context: ActivityExecutionContext, actor: User
    ) -> SalesTrainerAiCoachSession:
        if context.activity.type != "ai_coach":
            raise AiCoachSessionServiceError(
                "[NEWCOMER_ACTIVITY_TYPE_MISMATCH]", "当前任务不是 AI 辅导。", 422
            )
        if context.learner_id != str(actor.user_id):
            raise AiCoachSessionServiceError(
                "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]", "不能替其他学员开始 AI 辅导。", 403
            )
        activity_config = context.activity.config
        assert isinstance(activity_config, AiCoachActivityConfig)
        profile = await SalesTrainerAssetRevisionService(self._db).active_revision(
            resource_type="ai_coach_profile",
            logical_id=activity_config.coach_profile_id,
        )
        if profile is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_PROFILE_NOT_PUBLISHED]", "AI 教练配置尚未发布。", 409
            )
        raw_profile = dict(profile.payload_json)
        try:
            config = AiCoachConfig.model_validate(
                raw_profile.get("config", raw_profile)
            )
        except ValidationError as exc:
            raise AiCoachSessionServiceError(
                "[AI_COACH_PROFILE_INVALID]", "AI 教练配置不完整。", 409
            ) from exc
        if not config.enabled or not config.prompt_template_id:
            raise AiCoachSessionServiceError(
                "[AI_COACH_NOT_CONFIGURED]", "AI 教练尚未配置可用提示模板。", 409
            )
        session = SalesTrainerAiCoachSession(
            user_id=context.learner_id,
            module_key=context.module_id,
            path_key="newcomer_training_path_orchestration",
            path_revision_id=context.path_revision_id,
            article_snapshot={},
            path_config_snapshot=context.activity.model_dump(mode="json"),
            prompt_template_id=config.prompt_template_id,
            prompt_revision_id=config.prompt_revision_id,
            prompt_contract_hash=config.prompt_contract_hash,
            config_snapshot={
                **config.model_dump(mode="json"),
                "coach_profile_id": activity_config.coach_profile_id,
                "coach_profile_revision_id": str(profile.revision_id),
                "activity_context": {
                    "enrollment_id": context.enrollment_id,
                    "path_revision_id": context.path_revision_id,
                    "phase_id": context.phase_id,
                    "module_id": context.module_id,
                    "activity_id": context.activity.activity_id,
                },
            },
            status="in_progress",
            trace_id=str(uuid.uuid4()),
        )
        self._db.add(session)
        await self._db.flush()
        self._db.add(
            SalesTrainerAiCoachTurn(
                session_id=session.session_id,
                turn_number=1,
                question=str(
                    raw_profile.get("first_question")
                    or "请先说说你对本次内容的理解。"
                ),
                user_answer="",
                max_score=100,
                missed_points=[],
            )
        )
        await self._logs.record(
            actor=actor,
            action="newcomer_activity.ai_coach.session_created",
            target_type="sales_trainer_ai_coach_session",
            target_id=str(session.session_id),
            metadata={
                "enrollment_id": context.enrollment_id,
                "path_revision_id": context.path_revision_id,
                "activity_id": context.activity.activity_id,
                "coach_profile_revision_id": str(profile.revision_id),
            },
        )
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def finish_activity_session(
        self,
        *,
        session_id: str,
        actor: User,
        passed: bool,
        score: float | None = None,
        max_score: float | None = None,
    ) -> SalesTrainerAiCoachSession:
        session = await self._db.get(SalesTrainerAiCoachSession, session_id)
        if session is None or str(session.user_id) != str(actor.user_id):
            raise AiCoachSessionServiceError(
                "[AI_COACH_SESSION_NOT_FOUND]", "AI 教练会话不存在。", 404
            )
        setattr(session, "status", "completed")
        setattr(session, "mastery_state", "mastered" if passed else "not_mastered")
        setattr(session, "total_score", score)
        setattr(session, "max_score", max_score)
        attempt = await self._db.scalar(
            select(NewcomerTrainingActivityAttempt).where(
                NewcomerTrainingActivityAttempt.evidence_type == "ai_coach_session",
                NewcomerTrainingActivityAttempt.evidence_id == session_id,
            )
        )
        if attempt is None:
            raise AiCoachSessionServiceError(
                "[NEWCOMER_ACTIVITY_ATTEMPT_NOT_FOUND]", "训练记录不存在。", 409
            )
        setattr(attempt, "status", "completed" if passed else "failed")
        setattr(attempt, "passed", passed)
        setattr(attempt, "score", score)
        setattr(attempt, "max_score", max_score)
        await self._db.commit()
        await self._db.refresh(session)
        return session


__all__ = ["AiCoachSessionService", "AiCoachSessionServiceError"]

"""Activity-owned AI Coach session lifecycle."""

from __future__ import annotations

import hashlib
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
from sales_trainer.services.ai_coach_scoring_service import AiCoachScoringService
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
    def __init__(
        self,
        db: AsyncSession,
        *,
        scoring: AiCoachScoringService | None = None,
        **_: Any,
    ) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._scoring = scoring or AiCoachScoringService()

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
        first_question = str(
            raw_profile.get("first_question")
            or "请先说说你对本次内容的理解。"
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
            coach_state={"current_question": first_question, "turn_number": 1},
        )
        self._db.add(session)
        await self._db.flush()
        self._db.add(
            SalesTrainerAiCoachTurn(
                session_id=session.session_id,
                turn_number=1,
                question=first_question,
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

    async def submit_activity_turn(
        self,
        *,
        session_id: str,
        actor: User,
        answer: str,
        client_token: str,
    ) -> dict[str, Any]:
        session = await self._db.scalar(
            select(SalesTrainerAiCoachSession)
            .where(SalesTrainerAiCoachSession.session_id == session_id)
            .with_for_update()
        )
        if session is None or str(session.user_id) != str(actor.user_id):
            raise AiCoachSessionServiceError(
                "[AI_COACH_SESSION_NOT_FOUND]", "AI 教练会话不存在。", 404
            )
        coach_state = dict(session.coach_state or {})
        client_token_hash = hashlib.sha256(client_token.encode("utf-8")).hexdigest()
        if coach_state.get("last_client_token_hash") == client_token_hash and isinstance(
            coach_state.get("last_response"), dict
        ):
            return dict(coach_state["last_response"])
        if str(session.status) != "in_progress":
            return self._session_state(session, feedback=None, question=None)
        turns = list(
            (
                await self._db.execute(
                    select(SalesTrainerAiCoachTurn)
                    .where(SalesTrainerAiCoachTurn.session_id == session_id)
                    .order_by(SalesTrainerAiCoachTurn.turn_number)
                    .with_for_update()
                )
            ).scalars()
        )
        if not turns:
            raise AiCoachSessionServiceError(
                "[AI_COACH_TURN_NOT_FOUND]", "AI 教练当前问题不存在。", 409
            )
        current = turns[-1]
        if str(current.user_answer or "").strip():
            return self._session_state(
                session,
                feedback=str(current.ai_feedback or ""),
                question=str(current.next_question or "") or None,
            )
        config = dict(session.config_snapshot or {})
        scored = await self._scoring.score_turn(
            question=str(current.question),
            user_answer=answer,
            config=config,
            session_id=session_id,
            previous_turns=[
                {"question": str(item.question), "user_answer": str(item.user_answer)}
                for item in turns[:-1]
            ],
        )
        if not scored.is_success or scored.value is None:
            raise AiCoachSessionServiceError(
                str(scored.fallback or "[AI_COACH_SCORING_FAILED]"),
                "AI 教练暂时无法完成反馈，请稍后重试。",
                503,
            )
        output = scored.value
        setattr(current, "user_answer", answer)
        setattr(current, "ai_feedback", str(output["feedback"]))
        setattr(current, "score", output.get("score"))
        setattr(current, "max_score", output.get("max_score"))
        setattr(current, "missed_points", list(output.get("missed_points") or []))
        setattr(
            current,
            "next_question",
            str(output.get("next_question") or "") or None,
        )
        setattr(current, "raw_model_output", output.get("raw_model_output"))
        setattr(current, "validated_output", output)
        passed = bool(output.get("passed"))
        max_turns = int(config.get("max_turns") or 10)
        finished = passed or int(current.turn_number) >= max_turns
        next_question = None if finished else str(
            output.get("next_question") or "请结合反馈再补充说明。"
        )
        if finished:
            await self.finish_activity_session(
                session_id=session_id,
                actor=actor,
                passed=passed,
                score=float(output["score"]),
                max_score=float(output.get("max_score") or 100),
            )
        else:
            self._db.add(
                SalesTrainerAiCoachTurn(
                    session_id=session_id,
                    turn_number=int(current.turn_number) + 1,
                    question=next_question,
                    user_answer="",
                    max_score=100,
                    missed_points=[],
                )
            )
            await self._logs.record(
                actor=actor,
                action="newcomer_activity.ai_coach.turn_submitted",
                target_type="sales_trainer_ai_coach_session",
                target_id=session_id,
                metadata={"turn_number": int(current.turn_number)},
            )
        response = self._session_state(
            session,
            feedback=str(output["feedback"]),
            question=next_question,
        )
        setattr(
            session,
            "coach_state",
            {
                "current_question": next_question,
                "turn_number": int(current.turn_number) + (0 if finished else 1),
                "last_client_token_hash": client_token_hash,
                "last_response": response,
            },
        )
        await self._db.commit()
        return response

    @staticmethod
    def _session_state(
        session: SalesTrainerAiCoachSession,
        *,
        feedback: str | None,
        question: str | None,
    ) -> dict[str, Any]:
        return {
            "session_id": str(session.session_id),
            "status": str(session.status),
            "mastery_state": str(session.mastery_state)
            if session.mastery_state is not None
            else None,
            "feedback": feedback,
            "next_question": question,
        }


__all__ = ["AiCoachSessionService", "AiCoachSessionServiceError"]

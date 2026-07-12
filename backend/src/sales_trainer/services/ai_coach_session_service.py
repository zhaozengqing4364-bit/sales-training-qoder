from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from common.db.models import User
from common.db.typing import json_dict_or_empty, orm_scalar
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from prompt_templates.service import PromptTemplateService
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAiCoachTurn,
)
from sales_trainer.schemas import (
    AI_COACH_INTERACTION_SCHEMA_VERSION,
    AI_COACH_PUBLIC_INTERACTION_SCHEMA_VERSION,
    AiCoachAnswerKeyV1,
    AiCoachAnswerPayloadV1,
    AiCoachConfig,
    AiCoachFeedbackGuidanceV1,
    AiCoachInteractionInternalV1,
    AiCoachInteractionPublicV1,
    AiCoachPublicInteractionOptionV1,
    AiCoachScoreResultV1,
    AiCoachScoringPointV1,
    AiCoachScoringRubricV1,
    AiCoachSessionPublicResponse,
    AiCoachTurnPublicV1,
    NewcomerArticleBinding,
    NewcomerPathConfigPayload,
)
from sales_trainer.services.ai_coach_model_config import (
    AiCoachModelConfigError,
    model_config_contract_payload,
    model_config_id,
    resolve_ai_coach_llm_model_config_from_db,
)
from sales_trainer.services.ai_coach_scoring_service import AiCoachScoringService
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_SKILLS_SOURCE_MODULE_KEY,
    LearningTopicConfigError,
    NewcomerLearningTopicConfigService,
)
from sales_trainer.services.operation_log_service import OperationLogService

if TYPE_CHECKING:
    from sales_trainer.orchestration.activities.base import ActivityExecutionContext

from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_AUDIT_HISTORY_UNAVAILABLE,
    RESULT_OK,
    PromptTemplateRevisionResolver,
    PromptTemplateRevisionResolverError,
)

logger = get_logger(__name__)

# Fields allowed in the learner-facing public projection of a turn.
ALLOWED_PUBLIC_TURN_FIELDS: frozenset[str] = frozenset(
    {
        "turn_id",
        "turn_number",
        "public_interaction",
        "user_answer_payload",
        "score",
        "max_score",
        "ai_feedback",
        "missed_points",
        "next_turn_available",
    }
)
ALLOWED_PUBLIC_SESSION_FIELDS: frozenset[str] = frozenset(
    {
        "session_id",
        "module_key",
        "status",
        "mastery_state",
        "total_score",
        "max_score",
        "current_turn",
        "min_turns",
        "max_turns",
        "mastery_threshold",
        "overall_mastered",
        "created_at",
        "updated_at",
        "turns",
    }
)
AI_COACH_CONFIG_FIELD_NAMES: frozenset[str] = frozenset(AiCoachConfig.model_fields)
SPECIFIC_COACH_MODE_INTERACTION_TYPES: dict[str, str] = {
    "single_choice_drill": "single_choice",
    "multiple_choice_drill": "multiple_choice",
    "short_answer_drill": "short_answer",
}


class AiCoachSessionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachSessionService:
    """Service for managing AI coach sessions."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        scoring_service: AiCoachScoringService | None = None,
    ) -> None:
        self._db = db
        self._scoring = scoring_service or AiCoachScoringService()
        self._logs = OperationLogService(db)

    async def create_activity_session(
        self,
        *,
        context: ActivityExecutionContext,
        actor: User,
    ) -> SalesTrainerAiCoachSession:
        """Create a governed coach session from a pinned activity snapshot."""
        from sales_trainer.orchestration.contracts import AiCoachActivityConfig

        if context.activity.type != "ai_coach":
            raise AiCoachSessionServiceError(
                "[NEWCOMER_ACTIVITY_TYPE_MISMATCH]", "当前任务不是 AI 辅导。", 422
            )
        if context.learner_id != str(actor.user_id):
            raise AiCoachSessionServiceError(
                "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]",
                "不能替其他学员开始 AI 辅导。",
                403,
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
        raw_config = raw_profile.get("config", raw_profile)
        try:
            config = AiCoachConfig.model_validate(raw_config)
        except ValidationError as exc:
            raise AiCoachSessionServiceError(
                "[AI_COACH_PROFILE_INVALID]", "AI 教练配置不完整。", 409
            ) from exc
        if not config.enabled or not config.prompt_template_id:
            raise AiCoachSessionServiceError(
                "[AI_COACH_NOT_CONFIGURED]", "AI 教练尚未配置可用提示模板。", 409
            )
        trace_id = str(uuid.uuid4())
        session = SalesTrainerAiCoachSession(
            user_id=context.learner_id,
            module_key=context.module_id,
            path_key="newcomer_training_path_orchestration",
            path_revision_id=context.path_revision_id,
            path_revision_no=None,
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
            trace_id=trace_id,
        )
        self._db.add(session)
        await self._db.flush()
        self._db.add(
            SalesTrainerAiCoachTurn(
                session_id=session.session_id,
                turn_number=1,
                question=str(
                    raw_profile.get("first_question") or "请先说说你对本次内容的理解。"
                ),
                user_answer="",
                score=None,
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

    async def create_session(
        self,
        user_id: str,
        module_key: str,
    ) -> SalesTrainerAiCoachSession:
        """Create a new AI coach session for a user and module.

        Reads the current path config, freezes prompt/config snapshot,
        and initializes the session with the first question.
        """
        trace_id = str(uuid.uuid4())

        (
            path_revision_id,
            path_revision_no,
            module_config,
            ai_coach_config,
        ) = await self._resolve_active_ai_coach_module(module_key)

        if not ai_coach_config.enabled:
            raise AiCoachSessionServiceError(
                "[AI_COACH_DISABLED]",
                "该模块未启用 AI 教练。",
                status_code=409,
            )
        if not ai_coach_config.prompt_template_id:
            raise AiCoachSessionServiceError(
                "[AI_COACH_NOT_CONFIGURED]",
                "AI 教练未绑定 prompt template，无法生成互动卡片。",
                status_code=409,
            )

        article_snapshot = await self._resolve_article_snapshot(
            module_key=module_key,
            module_config=module_config,
        )

        # Build initial question
        first_question = self._build_first_question(article_snapshot, module_config)

        config_snapshot = ai_coach_config.model_dump(mode="json")

        session = SalesTrainerAiCoachSession(
            user_id=user_id,
            module_key=module_key,
            path_key=NEWCOMER_PATH_LOGICAL_ID,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            article_snapshot=article_snapshot,
            path_config_snapshot=module_config or {},
            prompt_template_id=ai_coach_config.prompt_template_id,
            prompt_revision_id=ai_coach_config.prompt_revision_id,
            prompt_contract_hash=ai_coach_config.prompt_contract_hash,
            config_snapshot=config_snapshot,
            status="in_progress",
            trace_id=trace_id,
        )
        self._db.add(session)
        await self._db.flush()

        # Create first turn with the initial question
        turn = SalesTrainerAiCoachTurn(
            session_id=session.session_id,
            turn_number=1,
            question=first_question,
            user_answer="",
            score=None,
            max_score=100,
            missed_points=[],
        )
        self._db.add(turn)
        await self._db.flush()

        await self._logs.record(
            actor=None,
            action="ai_coach_session_created",
            target_type="sales_trainer_ai_coach_session",
            target_id=orm_scalar(session.session_id, str),
            metadata={
                "user_id": user_id,
                "module_key": module_key,
                "path_revision_id": path_revision_id,
                "trace_id": trace_id,
            },
        )
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def submit_turn(
        self,
        session_id: str,
        user_answer: str,
        *,
        actor: User | None = None,
    ) -> SalesTrainerAiCoachTurn:
        """Submit an answer for the current turn.

        Validates session ownership, calls LLM for scoring,
        and generates the next question.
        """
        if actor is not None:
            session = await self.get_session(session_id, str(actor.user_id))
            if session is None:
                raise AiCoachSessionServiceError(
                    "[AI_COACH_SESSION_NOT_FOUND]",
                    "AI 教练会话不存在。",
                    status_code=404,
                )
        else:
            session = await self._require_session(session_id)

        if session.status != "in_progress":
            raise AiCoachSessionServiceError(
                "[AI_COACH_SESSION_NOT_IN_PROGRESS]",
                "会话已结束，无法提交新的回答。",
                status_code=409,
            )

        # Get the latest turn
        latest_turn = await self._get_latest_turn(session_id)
        if latest_turn is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_TURN_NOT_FOUND]",
                "没有活跃的问答轮次。",
                status_code=409,
            )

        # Update the current turn with user's answer
        setattr(latest_turn, "user_answer", user_answer)

        # Get previous turns for context
        previous_turns = await self._get_previous_turns(session_id)

        # Call scoring service
        config = json_dict_or_empty(session.config_snapshot)
        config["article_snapshot"] = json_dict_or_empty(session.article_snapshot)

        scoring_result = await self._scoring.score_turn(
            question=orm_scalar(latest_turn.question, str),
            user_answer=user_answer,
            config=config,
            session_id=session_id,
            previous_turns=previous_turns,
        )

        if not scoring_result.is_success:
            logger.warning(
                "ai_coach_scoring_failed",
                session_id=session_id,
                turn_id=latest_turn.turn_id,
                fallback=scoring_result.fallback,
            )
            setattr(latest_turn, "ai_feedback", "评分服务暂时不可用，请稍后重试。")
            setattr(latest_turn, "score", 0)
            setattr(latest_turn, "max_score", 100)
            setattr(latest_turn, "missed_points", [])
            setattr(latest_turn, "raw_model_output", {"error": scoring_result.fallback})
            await self._db.flush()
            raise AiCoachSessionServiceError(
                "[AI_COACH_SCORING_FAILED]",
                scoring_result.fallback or "评分失败，请稍后重试。",
                status_code=502,
            )

        output = scoring_result.value
        if output is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_SCORING_EMPTY]",
                "评分结果为空。",
                status_code=502,
            )

        setattr(latest_turn, "ai_feedback", output.get("feedback", ""))
        setattr(latest_turn, "score", output.get("score"))
        setattr(latest_turn, "max_score", output.get("max_score", 100))
        setattr(latest_turn, "missed_points", output.get("missed_points", []))
        setattr(latest_turn, "next_question", output.get("next_question"))
        setattr(latest_turn, "raw_model_output", output.get("raw_model_output"))
        setattr(
            latest_turn,
            "validated_output",
            {
                "score": output.get("score"),
                "max_score": output.get("max_score"),
                "feedback": output.get("feedback"),
                "missed_points": output.get("missed_points"),
                "next_question": output.get("next_question"),
                "passed": output.get("passed"),
                "reasoning": output.get("reasoning"),
            },
        )
        await self._db.flush()

        # Check if we should create next turn or finish
        config_snapshot = json_dict_or_empty(session.config_snapshot)
        max_turns = int(config_snapshot.get("max_turns", 10))
        min_turns = int(config_snapshot.get("min_turns", 3))
        mastery_threshold = float(config_snapshot.get("mastery_threshold", 80.0))

        current_turn_count = await self._get_turn_count(session_id)

        should_finish = False
        if current_turn_count >= max_turns:
            should_finish = True
        elif current_turn_count >= min_turns:
            # Check if mastery achieved
            if output.get("passed") is True:
                should_finish = True
            elif output.get("score", 0) >= mastery_threshold:
                should_finish = True

        if should_finish:
            await self.finish_session(session_id)
        else:
            # Create next turn with the next question
            next_question = output.get("next_question")
            if not next_question:
                next_question = self._build_follow_up_question(
                    json_dict_or_empty(session.article_snapshot),
                    current_turn_count,
                )

            next_turn = SalesTrainerAiCoachTurn(
                session_id=session_id,
                turn_number=current_turn_count + 1,
                question=next_question,
                user_answer="",
                score=None,
                max_score=100,
                missed_points=[],
            )
            self._db.add(next_turn)
            await self._db.flush()

        latest_score_value = orm_scalar(latest_turn.score, float, nullable=True)
        await self._logs.record(
            actor=actor,
            action="ai_coach_turn_submitted",
            target_type="sales_trainer_ai_coach_turn",
            target_id=orm_scalar(latest_turn.turn_id, str),
            metadata={
                "session_id": session_id,
                "turn_number": orm_scalar(latest_turn.turn_number, int),
                "score": float(latest_score_value)
                if latest_score_value is not None
                else None,
            },
        )
        await self._db.commit()
        await self._db.refresh(latest_turn)
        return latest_turn

    async def finish_session(
        self,
        session_id: str,
    ) -> SalesTrainerAiCoachSession:
        """Finish the session and calculate total score and mastery state."""
        session = await self._require_session(session_id)

        if session.status == "completed":
            return session

        turns = await self._get_all_turns(session_id)
        scored_turns = [t for t in turns if t.score is not None]

        if not scored_turns:
            setattr(session, "status", "failed")
            setattr(session, "mastery_state", "not_mastered")
            await self._db.flush()
            await self._db.commit()
            await self._db.refresh(session)
            return session

        total_score = sum(float(t.score) for t in scored_turns)
        avg_score = total_score / len(scored_turns)

        config_snapshot = json_dict_or_empty(session.config_snapshot)
        mastery_threshold = float(config_snapshot.get("mastery_threshold", 80.0))

        max_score = sum(float(t.max_score or 100) for t in scored_turns)

        setattr(session, "total_score", avg_score)
        setattr(
            session, "max_score", max_score / len(scored_turns) if scored_turns else 100
        )
        setattr(
            session,
            "mastery_state",
            "mastered" if avg_score >= mastery_threshold else "not_mastered",
        )
        setattr(session, "status", "completed")
        setattr(session, "updated_at", datetime.now(UTC))
        await self._db.flush()

        await self._logs.record(
            actor=None,
            action="ai_coach_session_finished",
            target_type="sales_trainer_ai_coach_session",
            target_id=session_id,
            metadata={
                "total_score": float(session.total_score)
                if session.total_score
                else None,
                "mastery_state": session.mastery_state,
                "turn_count": len(scored_turns),
            },
        )
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def get_session(
        self,
        session_id: str,
        user_id: str,
        *,
        allow_admin: bool = False,
    ) -> SalesTrainerAiCoachSession | None:
        """Get session with permission check."""
        session = await self._db.get(SalesTrainerAiCoachSession, session_id)
        if session is None:
            return None
        if allow_admin:
            return session
        if session.user_id != user_id:
            raise AiCoachSessionServiceError(
                "[ACCESS_DENIED]",
                "无权查看该 AI 教练会话。",
                status_code=403,
            )
        return session

    async def _require_session(self, session_id: str) -> SalesTrainerAiCoachSession:
        session = await self._db.get(SalesTrainerAiCoachSession, session_id)
        if session is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_SESSION_NOT_FOUND]",
                "AI 教练会话不存在。",
                status_code=404,
            )
        return session

    async def _get_latest_turn(self, session_id: str) -> SalesTrainerAiCoachTurn | None:
        result = await self._db.execute(
            select(SalesTrainerAiCoachTurn)
            .where(SalesTrainerAiCoachTurn.session_id == session_id)
            .order_by(SalesTrainerAiCoachTurn.turn_number.desc())
        )
        return result.scalars().first()

    async def _get_turn_count(self, session_id: str) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(SalesTrainerAiCoachTurn)
            .where(SalesTrainerAiCoachTurn.session_id == session_id)
        )
        return int(result.scalar() or 0)

    async def _get_all_turns(self, session_id: str) -> list[SalesTrainerAiCoachTurn]:
        result = await self._db.execute(
            select(SalesTrainerAiCoachTurn)
            .where(SalesTrainerAiCoachTurn.session_id == session_id)
            .order_by(SalesTrainerAiCoachTurn.turn_number.asc())
        )
        return list(result.scalars().all())

    async def list_turns(self, session_id: str) -> list[SalesTrainerAiCoachTurn]:
        """Public alias used by ai_coach_api serializer (delegates to internal)."""
        return await self._get_all_turns(session_id)

    async def _resolve_active_ai_coach_module(
        self,
        module_key: str,
    ) -> tuple[str, int, dict[str, Any], AiCoachConfig]:
        if module_key == BUSINESS_SKILLS_SOURCE_MODULE_KEY:
            try:
                (
                    path_revision_id,
                    path_revision_no,
                    module,
                ) = await NewcomerLearningTopicConfigService(
                    self._db
                ).active_business_etiquette_module_config()
            except LearningTopicConfigError as exc:
                raise AiCoachSessionServiceError(
                    exc.code,
                    exc.message,
                    exc.status_code,
                ) from exc
            if module.ai_coach is None:
                raise AiCoachSessionServiceError(
                    "[AI_COACH_NOT_CONFIGURED]",
                    "商务礼仪规范学习专题未配置 AI 教练。",
                    status_code=409,
                )
            return (
                path_revision_id,
                path_revision_no,
                module.model_dump(mode="json"),
                module.ai_coach,
            )
        path_response = await SalesTrainerPathConfigService(self._db).get_config()
        path_payload = path_response.get("path")
        active_revision_id = path_response.get("active_revision_id")
        active_revision_no = path_response.get("active_revision_no")
        if path_payload is None or not active_revision_id or active_revision_no is None:
            raise AiCoachSessionServiceError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径尚未发布 active revision，AI Coach 不能启动。",
                status_code=409,
            )
        path_revision_id = str(active_revision_id)
        path_revision_no = int(active_revision_no)
        try:
            payload = NewcomerPathConfigPayload.model_validate(path_payload)
        except ValidationError as exc:
            raise AiCoachSessionServiceError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                "新人训练路径 AI Coach 配置非法。",
                status_code=409,
            ) from exc
        for module in payload.modules:
            if module.module_key != module_key:
                continue
            if module.ai_coach is None:
                raise AiCoachSessionServiceError(
                    "[AI_COACH_NOT_CONFIGURED]",
                    "该模块未配置 AI 教练。",
                    status_code=409,
                )
            return (
                path_revision_id,
                path_revision_no,
                module.model_dump(mode="json"),
                module.ai_coach,
            )
        raise AiCoachSessionServiceError(
            "[AI_COACH_NOT_CONFIGURED]",
            "AI 教练模块不存在。",
            status_code=404,
        )

    async def _resolve_article_snapshot(
        self,
        *,
        module_key: str,
        module_config: dict[str, Any],
    ) -> dict[str, Any]:
        learning_content_id = module_config.get("learning_content_id")
        if not learning_content_id:
            return {}
        try:
            article_binding = await ArticleBindingService(
                self._db
            ).resolve_module_article(
                NewcomerArticleBinding(
                    module_key=module_key,
                    learning_content_id=str(learning_content_id),
                )
            )
        except ArticleBindingServiceError as exc:
            raise AiCoachSessionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        return {
            "module_key": article_binding.get("module_key"),
            "learning_content_id": article_binding.get("learning_content_id"),
            "title": article_binding.get("title"),
            "summary": article_binding.get("summary"),
            "chapters": article_binding.get("chapters", []),
        }

    async def _get_previous_turns(self, session_id: str) -> list[dict[str, Any]]:
        turns = await self._get_all_turns(session_id)
        return [
            {
                "turn_number": t.turn_number,
                "question": t.question,
                "user_answer": t.user_answer,
                "score": float(t.score) if t.score is not None else None,
                "ai_feedback": t.ai_feedback,
            }
            for t in turns
            if t.user_answer and t.score is not None
        ]

    def _build_first_question(
        self,
        article_snapshot: dict[str, Any],
        module_config: dict[str, Any] | None,
    ) -> str:
        """Build the first question for the AI coach session."""
        title = article_snapshot.get("title", "")
        if title:
            return (
                f"欢迎开始 AI 教练训练！今天我们学习的主题是「{title}」。"
                f"请简要说明你对这个主题的理解。"
            )
        module_title = module_config.get("title", "") if module_config else ""
        if module_title:
            return (
                f"欢迎开始 AI 教练训练！今天我们学习的模块是「{module_title}」。"
                f"请简要说明你对这个主题的理解。"
            )
        return "欢迎开始 AI 教练训练！请简要说明你对今天学习主题的理解。"

    def _build_follow_up_question(
        self,
        article_snapshot: dict[str, Any],
        turn_count: int,
    ) -> str:
        """Build a follow-up question when LLM doesn't provide one."""
        chapters = article_snapshot.get("chapters", [])
        if chapters and isinstance(chapters, list) and turn_count <= len(chapters):
            chapter = chapters[turn_count - 1]
            if isinstance(chapter, dict):
                chapter_title = chapter.get("title", "")
                if chapter_title:
                    return f"请详细说明「{chapter_title}」部分的内容要点。"
        return "请继续补充你对这个主题的理解。"

    # ------------------------------------------------------------------
    # v1 layered-interaction path
    #
    # The legacy ``create_session`` / ``submit_turn`` / ``finish_session``
    # methods above are preserved unchanged. The v1 path below adds:
    #   * ``create_session_v1``     — pre-generates the first interaction
    #     through ``generate_interaction`` and stores the layered snapshot.
    #   * ``submit_turn_v1``        — accepts ``answer_payload``, scores via
    #     ``score_choice`` / ``score_short_answer``, then generates the
    #     next interaction.
    #   * ``finish_session_v1``     — defers mastery judgement to a single
    #     ``_evaluate_mastery`` helper (no scattered thresholds).
    #   * ``generate_interaction``  — prompt-template binding + contract
    #     hash verification + LLM call + Pydantic validation.
    #   * ``score_choice``          — implements the three
    #     ``partial_credit_policy`` strategies; never hardcodes outcomes.
    #   * ``score_short_answer``    — separate scoring-prompt revision.
    #   * ``serialize_session_public`` — strict allow-list projection of a
    #     session + turns for the learner API.
    # ------------------------------------------------------------------

    async def create_session_v1(
        self,
        user_id: str,
        module_key: str,
        *,
        coach_mode: str | None = None,
        interaction_type: str | None = None,
    ) -> SalesTrainerAiCoachSession:
        """Create a new AI coach session using the v1 layered contract.

        Mirrors ``create_session`` but generates the first interaction via
        ``generate_interaction`` so the stored turn carries
        ``interaction_snapshot`` + ``public_interaction`` from the start.

        Falls back to the legacy path when the module's ``AiCoachConfig`` has
        no ``prompt_template_id`` (legacy / un-configured modules).
        """
        trace_id = str(uuid.uuid4())

        (
            path_revision_id,
            path_revision_no,
            module_config,
            ai_coach_config,
        ) = await self._resolve_active_ai_coach_module(module_key)

        if not ai_coach_config.enabled:
            raise AiCoachSessionServiceError(
                "[AI_COACH_DISABLED]",
                "该模块未启用 AI 教练。",
                status_code=409,
            )
        self._validate_requested_interaction_type_allowed(
            ai_coach_config=ai_coach_config,
            coach_mode=coach_mode,
            interaction_type=interaction_type,
        )

        article_snapshot = await self._resolve_article_snapshot(
            module_key=module_key,
            module_config=module_config,
        )

        config_snapshot = ai_coach_config.model_dump(mode="json")
        # Pin the runtime schema version to the backend constant; admin
        # input is intentionally ignored.
        config_snapshot["pinned_schema_version"] = (
            ai_coach_config.pinned_schema_version()
        )
        # Snapshot the caller-selected drill mode so ``generate_interaction``
        # can honour the constraint (e.g. single_choice_drill always
        # emits single_choice). Without this, the 4 buttons in the
        # frontend would only relabel the session — the actual prompt
        # contract would still be mixed_drill.
        if coach_mode is not None:
            config_snapshot["active_coach_mode"] = coach_mode
        if interaction_type is not None:
            config_snapshot["active_interaction_type"] = interaction_type

        session = SalesTrainerAiCoachSession(
            user_id=user_id,
            module_key=module_key,
            path_key=NEWCOMER_PATH_LOGICAL_ID,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            article_snapshot=article_snapshot,
            path_config_snapshot=module_config or {},
            prompt_template_id=ai_coach_config.prompt_template_id,
            prompt_revision_id=ai_coach_config.prompt_revision_id,
            prompt_contract_hash=ai_coach_config.prompt_contract_hash,
            config_snapshot=config_snapshot,
            status="in_progress",
            trace_id=trace_id,
        )
        self._db.add(session)
        await self._db.flush()

        # Create the first turn. We always materialise a turn row so the
        # legacy list paths keep working even when no v1 template is bound.
        turn = SalesTrainerAiCoachTurn(
            session_id=session.session_id,
            turn_number=1,
            question="",
            user_answer="",
            score=None,
            max_score=100,
            missed_points=[],
        )
        self._db.add(turn)
        await self._db.flush()

        try:
            await self.generate_interaction(session, turn)
        except AiCoachSessionServiceError:
            await self._db.rollback()
            raise

        await self._logs.record(
            actor=None,
            action="ai_coach_session_created_v1",
            target_type="sales_trainer_ai_coach_session",
            target_id=orm_scalar(session.session_id, str),
            metadata={
                "user_id": user_id,
                "module_key": module_key,
                "path_revision_id": path_revision_id,
                "trace_id": trace_id,
                "schema_version": turn.schema_version,
            },
        )
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def generate_interaction(
        self,
        session: SalesTrainerAiCoachSession,
        turn: SalesTrainerAiCoachTurn,
    ) -> AiCoachInteractionInternalV1:
        """Render, verify, call, and store the v1 interaction payload.

        Steps:
          1. Resolve ``(prompt_template_id, prompt_revision_id)`` via the
             existing ``PromptTemplateRevisionResolver`` (Context research
             confirmed this is the canonical wrapper).
          2. Compile the runtime prompt contract via
             ``PromptTemplateService.compile_runtime_prompt_contract``.
          3. Compare the compiled ``contract_hash`` with the session's
             ``prompt_contract_hash``; mismatch raises
             ``[AI_COACH_PROMPT_CONTRACT_MISMATCH]`` (no fallback path).
          4. Call the LLM, parse the JSON, validate as
             ``AiCoachInteractionInternalV1``; invalid payloads raise
             ``[AI_COACH_INTERACTION_INVALID]``.
          5. Project to ``AiCoachInteractionPublicV1`` (strips
             answer_key / scoring_rubric / source_evidence / raw).
          6. Persist the snapshots on the turn.
        """
        template_id = orm_scalar(session.prompt_template_id, str, nullable=True)
        if not template_id:
            raise AiCoachSessionServiceError(
                "[AI_COACH_PROMPT_TEMPLATE_MISSING]",
                "AI 教练会话未绑定 prompt template。",
                status_code=409,
            )

        config_snapshot = json_dict_or_empty(session.config_snapshot)
        ai_coach_config_raw = config_snapshot.get("ai_coach") or config_snapshot
        try:
            ai_coach_config = self._load_ai_coach_config_from_snapshot(
                ai_coach_config_raw
            )
        except ValidationError:
            ai_coach_config = AiCoachConfig()

        resolver = PromptTemplateRevisionResolver(self._db)
        try:
            resolution = await resolver.resolve(
                template_id=template_id,
                prompt_revision_id=orm_scalar(
                    session.prompt_revision_id,
                    str,
                    nullable=True,
                ),
            )
        except PromptTemplateRevisionResolverError as exc:
            raise self._prompt_resolver_service_error(exc) from exc
        if resolution.status != RESULT_OK:
            await self._logs.record(
                actor=None,
                action="ai_coach_prompt_revision_fallback_blocked",
                target_type="sales_trainer_ai_coach_session",
                target_id=orm_scalar(session.session_id, str),
                metadata={
                    "template_id": template_id,
                    "prompt_revision_id": orm_scalar(
                        session.prompt_revision_id,
                        str,
                        nullable=True,
                    ),
                    "resolution_status": resolution.status,
                },
            )
            if resolution.status == RESULT_AUDIT_HISTORY_UNAVAILABLE:
                raise AiCoachSessionServiceError(
                    "[AI_COACH_PROMPT_REVISION_AUDIT_MISSING]",
                    "已发布 prompt revision 缺少审计历史，无法渲染。",
                    status_code=409,
                )
            # Default: RESULT_HEAD_USED_AS_FALLBACK or any other non-OK state.
            raise AiCoachSessionServiceError(
                "[AI_COACH_PROMPT_REVISION_FALLBACK]",
                "未按已发布 revision 渲染 AI 教练互动卡片，已中止。",
                status_code=409,
            )
        template = resolution.snapshot.template

        try:
            model_config = await resolve_ai_coach_llm_model_config_from_db(
                self._db, ai_coach_config.generation_model
            )
        except AiCoachModelConfigError as exc:
            raise AiCoachSessionServiceError(exc.code, exc.message, 409) from exc

        # 2. Compile the runtime contract using the resolved template.
        prompt_service = PromptTemplateService(self._db)
        variables = await self._build_generation_variables(
            session=session, turn=turn, ai_coach_config=ai_coach_config
        )
        compile_result = prompt_service.compile_runtime_prompt_contract(
            template=template,
            variables=variables,
            runtime_consumer="ai_coach.generate_interaction",
            system_message=self._build_generation_system_message(ai_coach_config),
            model_config=model_config_contract_payload(model_config),
        )
        if not compile_result.is_success or compile_result.value is None:
            raise AiCoachSessionServiceError(
                f"[AI_COACH_PROMPT_COMPILE_FAILED:{compile_result.fallback or 'unknown'}]",
                "无法编译 AI 教练 prompt contract。",
                status_code=502,
            )
        contract = compile_result.value

        setattr(session, "prompt_contract_hash", contract.contract_hash)

        # 4. LLM call. We use the shared LLMService so cost / metrics /
        # tracing stay consistent with the rest of the sales_trainer stack.
        llm_service = (
            LLMService(config=model_config)
            if model_config is not None
            else LLMService()
        )
        llm_result = await llm_service.generate(
            prompt=contract.rendered_prompt,
            session_id=orm_scalar(session.session_id, str),
            system_message=contract.system_message,
            allow_fallback_response=False,
        )
        if not llm_result.is_success or not llm_result.value:
            raise AiCoachSessionServiceError(
                "[AI_COACH_LLM_GENERATION_FAILED]",
                "AI 教练 LLM 生成失败。",
                status_code=502,
            )

        raw_payload = self._extract_json(str(llm_result.value))
        if raw_payload is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_INTERACTION_INVALID]",
                "AI 教练 LLM 输出不是合法 JSON。",
                status_code=502,
            )

        try:
            internal = AiCoachInteractionInternalV1.model_validate(raw_payload)
        except ValidationError as exc:
            raise AiCoachSessionServiceError(
                f"[AI_COACH_INTERACTION_INVALID:{exc.errors()[0]['type']}]",
                "AI 教练 interaction payload 不符合 v1 契约。",
                status_code=502,
            ) from exc

        # Enforce the user-selected drill mode: if the caller picked
        # ``single_choice_drill`` we must not accept a multi-choice
        # generation, and so on. The clamp is fail-loud rather than
        # silent rewrite — the LLM contract is that the prompt template
        # already constrains the type, so a mismatch is a real config
        # error worth surfacing, not "fixing" by coercion.
        config_snapshot = json_dict_or_empty(session.config_snapshot)
        active_mode = config_snapshot.get("active_coach_mode")
        active_explicit_type = config_snapshot.get("active_interaction_type")
        raw_allowed_types = config_snapshot.get("allowed_interaction_types")
        allowed_types = (
            [str(item) for item in raw_allowed_types]
            if isinstance(raw_allowed_types, list) and raw_allowed_types
            else [str(item) for item in AiCoachConfig().allowed_interaction_types]
        )
        expected_type = AiCoachSessionService._expected_interaction_type_for_mode(
            active_mode=active_mode,
            active_explicit_type=active_explicit_type,
            turn_number=orm_scalar(turn.turn_number, int),
            allowed_types=allowed_types,
        )
        if expected_type is not None and internal.interaction_type != expected_type:
            raise AiCoachSessionServiceError(
                "[AI_COACH_INTERACTION_INVALID]",
                f"训练模式 {active_mode} 要求题型 {expected_type}，"
                f"实际生成 {internal.interaction_type}。",
                status_code=502,
            )

        # 5. Project to public spec (no answer_key / scoring_rubric /
        # source_evidence / raw). Done via Pydantic's allow-list by
        # constructing the public model from the internal model.
        public = self._project_to_public(internal, session=session, turn=turn)

        # 6. Persist.
        setattr(turn, "interaction_snapshot", internal.model_dump(mode="json"))
        setattr(turn, "public_interaction", public.model_dump(mode="json"))
        setattr(turn, "schema_version", AI_COACH_INTERACTION_SCHEMA_VERSION)
        # Backward-compatible legacy fields.
        setattr(turn, "question", internal.stem)
        await self._db.flush()
        return internal

    async def submit_turn_v1(
        self,
        session_id: str,
        answer_payload: AiCoachAnswerPayloadV1,
        *,
        actor: User | None = None,
    ) -> SalesTrainerAiCoachTurn:
        """Submit a structured v1 answer and score it.

        Branches on ``answer_payload.variant``:
          * ``"choice"`` → ``score_choice`` (deterministic, no LLM).
          * ``"text"``   → ``score_short_answer`` (LLM with a separate
            scoring prompt revision).

        After scoring, the next interaction is generated via
        ``generate_interaction``. The legacy fields ``user_answer`` and
        ``next_question`` are also updated so the legacy response model
        still works.
        """
        if actor is not None:
            session = await self.get_session(session_id, str(actor.user_id))
            if session is None:
                raise AiCoachSessionServiceError(
                    "[AI_COACH_SESSION_NOT_FOUND]",
                    "AI 教练会话不存在。",
                    status_code=404,
                )
        else:
            session = await self._require_session(session_id)

        if session.status != "in_progress":
            raise AiCoachSessionServiceError(
                "[AI_COACH_SESSION_NOT_IN_PROGRESS]",
                "会话已结束，无法提交新的回答。",
                status_code=409,
            )

        latest_turn = await self._get_latest_turn(session_id)
        if latest_turn is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_TURN_NOT_FOUND]",
                "没有活跃的问答轮次。",
                status_code=409,
            )

        internal = self._load_internal_interaction(latest_turn)
        if internal is None:
            raise AiCoachSessionServiceError(
                "[AI_COACH_INTERACTION_INVALID]",
                "当前 turn 不含 v1 interaction snapshot，无法评分。",
                status_code=409,
            )
        self._validate_answer_payload(internal, answer_payload)

        # Score using the dedicated strategy.
        scoring_runtime_metadata: dict[str, object] = {}
        score_result: AiCoachScoreResultV1
        if answer_payload.variant == "choice":
            score_result = self.score_choice(
                answer_payload=answer_payload,
                answer_key=internal.answer_key,
                scoring_rubric=internal.scoring_rubric,
                feedback_guidance=internal.feedback_guidance,
            )
        else:
            config_snapshot = json_dict_or_empty(session.config_snapshot)
            scoring_prompt_template_id = config_snapshot.get(
                "scoring_prompt_template_id"
            )
            scoring_prompt_revision_id = config_snapshot.get(
                "scoring_prompt_revision_id"
            )
            scoring_contract_hash = config_snapshot.get("scoring_contract_hash")
            short_answer_result = await self.score_short_answer(
                answer_text=answer_payload.text or "",
                reference_answer=internal.answer_key.reference_answer or "",
                scoring_rubric=internal.scoring_rubric,
                session_id=session_id,
                scoring_prompt_template_id=scoring_prompt_template_id,
                scoring_prompt_revision_id=scoring_prompt_revision_id,
                scoring_contract_hash=scoring_contract_hash,
                scoring_model=config_snapshot.get("scoring_model"),
                runtime_metadata_out=scoring_runtime_metadata,
            )
            if not short_answer_result.is_success:
                failure_code = (
                    short_answer_result.fallback or "[AI_COACH_SCORING_FAILED]"
                )
                if failure_code.startswith("[AI_COACH_PROMPT") or failure_code in {
                    "[AI_COACH_SCORING_PROMPT_MISSING]",
                }:
                    raise AiCoachSessionServiceError(
                        failure_code,
                        "简答评分 Prompt 配置错误。",
                        status_code=409,
                    )
                raise AiCoachSessionServiceError(
                    f"[AI_COACH_SCORING_FAILED:{failure_code}]",
                    "简答评分失败。",
                    status_code=502,
                )
            short_answer_score_result = short_answer_result.value
            if short_answer_score_result is None:
                raise AiCoachSessionServiceError(
                    "[AI_COACH_SCORING_EMPTY]",
                    "简答评分结果为空。",
                    status_code=502,
                )
            score_result = short_answer_score_result

        # Persist scoring + payload on the turn.
        setattr(
            latest_turn,
            "user_answer",
            answer_payload.text
            if answer_payload.variant == "text"
            else ",".join(answer_payload.option_ids or []),
        )
        setattr(latest_turn, "score", score_result.score)
        setattr(latest_turn, "max_score", score_result.max_score)
        setattr(latest_turn, "ai_feedback", score_result.feedback)
        setattr(latest_turn, "missed_points", list(score_result.missed_points))
        setattr(latest_turn, "answer_payload", answer_payload.model_dump(mode="json"))
        score_result_payload = score_result.model_dump(mode="json")
        if answer_payload.variant == "text" and scoring_runtime_metadata:
            score_result_payload["runtime_audit"] = {
                "scoring": dict(scoring_runtime_metadata)
            }
        setattr(latest_turn, "score_result", score_result_payload)
        setattr(latest_turn, "validated_output", score_result_payload)
        await self._db.flush()

        # Decide whether to continue or finish.
        config_snapshot = json_dict_or_empty(session.config_snapshot)
        max_turns = int(config_snapshot.get("max_turns", 10))
        min_turns = int(config_snapshot.get("min_turns", 3))
        mastery_threshold = float(config_snapshot.get("mastery_threshold", 80.0))
        current_turn_count = await self._get_turn_count(session_id)

        should_finish = self._should_finish_session(
            turn_count=current_turn_count,
            min_turns=min_turns,
            max_turns=max_turns,
            mastery_threshold=mastery_threshold,
            latest_score=score_result.score,
        )

        if should_finish:
            await self.finish_session_v1(session_id)
        else:
            next_turn = SalesTrainerAiCoachTurn(
                session_id=session_id,
                turn_number=current_turn_count + 1,
                question="",
                user_answer="",
                score=None,
                max_score=100,
                missed_points=[],
            )
            self._db.add(next_turn)
            await self._db.flush()
            await self.generate_interaction(session, next_turn)

        await self._logs.record(
            actor=actor,
            action="ai_coach_turn_submitted_v1",
            target_type="sales_trainer_ai_coach_turn",
            target_id=orm_scalar(latest_turn.turn_id, str),
            metadata={
                "session_id": session_id,
                "turn_number": orm_scalar(latest_turn.turn_number, int),
                "variant": answer_payload.variant,
                "score": score_result.score,
                "max_score": score_result.max_score,
            },
        )
        await self._db.commit()
        await self._db.refresh(latest_turn)
        return latest_turn

    async def finish_session_v1(
        self,
        session_id: str,
    ) -> SalesTrainerAiCoachSession:
        """Finalise the v1 session using a single mastery predicate.

        The mastery rule lives in ``_evaluate_mastery`` so the threshold
        cannot drift between ``submit_turn_v1`` and ``finish_session_v1``.
        """
        session = await self._require_session(session_id)

        if session.status == "completed":
            return session

        turns = await self._get_all_turns(session_id)
        scored_turns = [t for t in turns if t.score is not None]

        if not scored_turns:
            setattr(session, "status", "failed")
            setattr(session, "mastery_state", "not_mastered")
            await self._db.flush()
            await self._db.commit()
            await self._db.refresh(session)
            return session

        total_score = sum(float(t.score) for t in scored_turns)
        avg_score = total_score / len(scored_turns)
        max_score = sum(float(t.max_score or 100) for t in scored_turns)

        config_snapshot = json_dict_or_empty(session.config_snapshot)
        mastery_threshold = float(config_snapshot.get("mastery_threshold", 80.0))

        setattr(session, "total_score", avg_score)
        setattr(
            session, "max_score", max_score / len(scored_turns) if scored_turns else 100
        )
        setattr(
            session,
            "mastery_state",
            self._evaluate_mastery(
                avg_score=avg_score,
                mastery_threshold=mastery_threshold,
            ),
        )
        setattr(session, "status", "completed")
        setattr(session, "updated_at", datetime.now(UTC))
        await self._db.flush()

        await self._logs.record(
            actor=None,
            action="ai_coach_session_finished_v1",
            target_type="sales_trainer_ai_coach_session",
            target_id=session_id,
            metadata={
                "total_score": float(session.total_score)
                if session.total_score
                else None,
                "mastery_state": session.mastery_state,
                "turn_count": len(scored_turns),
                "mastery_threshold": mastery_threshold,
            },
        )
        await self._db.commit()
        await self._db.refresh(session)
        return session

    # ------------------------------------------------------------------
    # Scoring primitives
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_answer_payload(
        internal: AiCoachInteractionInternalV1,
        answer_payload: AiCoachAnswerPayloadV1,
    ) -> None:
        if internal.interaction_type == "short_answer":
            if answer_payload.variant != "text":
                raise AiCoachSessionServiceError(
                    "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
                    "简答题必须提交 text answer_payload。",
                    status_code=422,
                )
            return

        if answer_payload.variant != "choice":
            raise AiCoachSessionServiceError(
                "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
                "选择题必须提交 choice answer_payload。",
                status_code=422,
            )

        submitted = list(answer_payload.option_ids or [])
        valid_option_ids = {option.option_id for option in (internal.options or [])}
        invalid = [
            option_id for option_id in submitted if option_id not in valid_option_ids
        ]
        if invalid:
            raise AiCoachSessionServiceError(
                "[AI_COACH_ANSWER_OPTION_INVALID]",
                "提交选项不属于当前互动卡片。",
                status_code=422,
            )

        if internal.interaction_type == "single_choice" and len(submitted) != 1:
            raise AiCoachSessionServiceError(
                "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
                "单选题必须提交且仅提交一个选项。",
                status_code=422,
            )

    def score_choice(
        self,
        *,
        answer_payload: AiCoachAnswerPayloadV1,
        answer_key: AiCoachAnswerKeyV1,
        scoring_rubric: AiCoachScoringRubricV1,
        feedback_guidance: AiCoachFeedbackGuidanceV1 | None = None,
    ) -> AiCoachScoreResultV1:
        """Deterministic choice scoring driven by the rubric.

        Policies (all derived from ``scoring_rubric.partial_credit_policy``):

        * ``all_or_nothing``: option_ids must match exactly.
        * ``proportional``:  max_score * (correct/total_correct) *
                                       (1 - wrong/total_options)
        * ``tiered``:        sum of points whose key was covered by the
                             user's selections.
        """
        max_score = float(scoring_rubric.max_score)
        user_selected = list(answer_payload.option_ids or [])
        correct_set = set(answer_key.option_ids)
        user_set = set(user_selected)
        total_correct = max(len(correct_set), 1)

        policy = scoring_rubric.partial_credit_policy

        if policy == "all_or_nothing":
            score = max_score if user_set == correct_set else 0.0
            missed: list[str] = []
            if score < max_score:
                missed = self._build_missed_points(
                    scoring_rubric=scoring_rubric,
                    correct=correct_set,
                    user=user_set,
                )
            feedback = self._choice_feedback(
                hit=score >= max_score,
                correct=correct_set,
                user=user_set,
                guidance=feedback_guidance,
            )
            return AiCoachScoreResultV1(
                score=score,
                max_score=max_score,
                feedback=feedback,
                missed_points=missed,
                next_turn_available=True,
                finished=False,
            )

        if policy == "proportional":
            correct_selected = len(user_set & correct_set)
            wrong_selected = len(user_set - correct_set)
            # ``total_options`` is a runtime value: the rubric doesn't pin
            # the option pool, so we infer it from the answer_key + user
            # set so the deduction term is always well-defined.
            total_options = max(
                len(correct_set | user_set),
                1,
            )
            raw = (correct_selected / total_correct) * (
                1.0 - (wrong_selected / total_options)
            )
            score = round(max_score * max(0.0, raw), 2)
            missed = self._build_missed_points(
                scoring_rubric=scoring_rubric,
                correct=correct_set,
                user=user_set,
            )
            feedback = self._choice_feedback(
                hit=score >= max_score,
                correct=correct_set,
                user=user_set,
                guidance=feedback_guidance,
            )
            return AiCoachScoreResultV1(
                score=score,
                max_score=max_score,
                feedback=feedback,
                missed_points=missed,
                next_turn_available=True,
                finished=False,
            )

        if policy == "tiered":
            score = 0.0
            for point in scoring_rubric.points:
                if self._point_covered(point, user_set, correct_set):
                    score += float(point.score)
            score = min(round(score, 2), max_score)
            missed = self._build_missed_points(
                scoring_rubric=scoring_rubric,
                correct=correct_set,
                user=user_set,
            )
            feedback = self._choice_feedback(
                hit=score >= max_score,
                correct=correct_set,
                user=user_set,
                guidance=feedback_guidance,
            )
            return AiCoachScoreResultV1(
                score=score,
                max_score=max_score,
                feedback=feedback,
                missed_points=missed,
                next_turn_available=True,
                finished=False,
            )

        # Defensive: an unknown policy means the schema is being misused
        # upstream; surface that loudly instead of silently scoring zero.
        raise AiCoachSessionServiceError(
            f"[AI_COACH_UNKNOWN_PARTIAL_CREDIT_POLICY:{policy}]",
            "未知的 partial_credit_policy。",
            status_code=500,
        )

    async def score_short_answer(
        self,
        *,
        answer_text: str,
        reference_answer: str,
        scoring_rubric: AiCoachScoringRubricV1,
        session_id: str,
        scoring_prompt_template_id: str | None = None,
        scoring_prompt_revision_id: str | None = None,
        scoring_contract_hash: str | None = None,
        scoring_model: str | None = None,
        runtime_metadata_out: dict[str, object] | None = None,
    ) -> Result[AiCoachScoreResultV1]:
        """LLM-based short-answer scoring using a separate prompt revision.

        The scoring prompt is intentionally distinct from the generation
        prompt so the two contracts can evolve independently. When the
        caller does not supply a scoring-prompt binding we fail loudly
        with ``[AI_COACH_SCORING_PROMPT_MISSING]`` rather than silently
        fall back to a hard-coded prompt, because:

        * 简答评分走 prompt_templates governance 链路是宪法要求；
        * 静默回退会破坏"严格按 published revision 渲染"的合同；
        * 缺 scoring prompt 是配置错误，应该让 admin 修配置，
          而不是让学员看到一份硬编码的"AI 评分"。

        Returns ``Result.fail`` with a typed error code on any failure;
        the route layer surfaces it as ``[AI_COACH_SCORING_FAILED]`` or
        ``[AI_COACH_PROMPT_CONTRACT_MISMATCH]`` etc.
        """
        max_score = float(scoring_rubric.max_score)
        if not answer_text.strip():
            return Result.ok(
                AiCoachScoreResultV1(
                    score=0.0,
                    max_score=max_score,
                    feedback="未提供回答。",
                    missed_points=[],
                    next_turn_available=True,
                    finished=False,
                )
            )

        if not scoring_prompt_template_id:
            return Result.fail("[AI_COACH_SCORING_PROMPT_MISSING]")

        resolver = PromptTemplateRevisionResolver(self._db)
        try:
            resolution = await resolver.resolve(
                template_id=scoring_prompt_template_id,
                prompt_revision_id=scoring_prompt_revision_id,
            )
        except PromptTemplateRevisionResolverError as exc:
            return Result.fail(self._prompt_resolver_public_code(exc))

        if resolution.status != RESULT_OK:
            # Audit history unavailable / head fallback — refuse to score
            # against an unreviewed prompt to preserve contract integrity.
            return Result.fail(
                f"[AI_COACH_SCORING_PROMPT_REVISION_UNRESOLVED:{resolution.status}]"
            )

        template = resolution.snapshot.template
        try:
            model_config = await resolve_ai_coach_llm_model_config_from_db(
                self._db,
                scoring_model,
            )
        except AiCoachModelConfigError as exc:
            return Result.fail(exc.code)

        compile_result = PromptTemplateService(
            self._db
        ).compile_runtime_prompt_contract(
            template=template,
            variables=self._build_short_answer_variables(
                answer_text=answer_text,
                reference_answer=reference_answer,
                scoring_rubric=scoring_rubric,
            ),
            runtime_consumer="ai_coach.score_short_answer",
            system_message=self._build_short_answer_system_message(),
            model_config=model_config_contract_payload(model_config),
        )
        if not compile_result.is_success or compile_result.value is None:
            return Result.fail("[AI_COACH_SCORING_PROMPT_RENDER_FAILED]")
        contract = compile_result.value

        if scoring_contract_hash and contract.contract_hash != scoring_contract_hash:
            return Result.fail("[AI_COACH_SCORING_PROMPT_CONTRACT_MISMATCH]")

        llm_service = (
            LLMService(config=model_config)
            if model_config is not None
            else LLMService()
        )
        if runtime_metadata_out is not None:
            runtime_metadata_out.update(
                {
                    "prompt_template_id": str(contract.template_id),
                    "prompt_revision_id": resolution.snapshot.prompt_revision_id,
                    "contract_hash": contract.contract_hash,
                    "requested_model": scoring_model,
                    "model_config_id": model_config_id(model_config),
                    "model_provider": llm_service.provider,
                    "model_name": llm_service.model_name,
                }
            )
        llm_result = await llm_service.generate(
            prompt=contract.rendered_prompt,
            session_id=session_id,
            system_message=contract.system_message
            or self._build_short_answer_system_message(),
            allow_fallback_response=False,
        )
        if not llm_result.is_success or not llm_result.value:
            return Result.fail("[AI_COACH_SHORT_ANSWER_LLM_FAILED]")

        raw_payload = self._extract_json(str(llm_result.value))
        if raw_payload is None:
            return Result.fail("[AI_COACH_SHORT_ANSWER_INVALID_JSON]")

        try:
            score_value = float(raw_payload.get("score", 0))
        except (TypeError, ValueError):
            return Result.fail("[AI_COACH_SHORT_ANSWER_INVALID_SCORE]")
        score_value = max(0.0, min(max_score, score_value))
        feedback_text = str(raw_payload.get("feedback") or "评分完成。").strip()
        if not feedback_text:
            feedback_text = "评分完成。"
        missed_raw = raw_payload.get("missed_points") or []
        if not isinstance(missed_raw, list):
            missed_raw = []
        missed = [str(item) for item in missed_raw if str(item).strip()][:10]
        return Result.ok(
            AiCoachScoreResultV1(
                score=score_value,
                max_score=max_score,
                feedback=feedback_text,
                missed_points=missed,
                next_turn_available=True,
                finished=False,
            )
        )

    def _build_short_answer_system_message(self) -> str:
        """Backend-pinned system message for short-answer scoring."""
        return (
            "你是一位销售培训 AI 评分员。\n"
            "请根据参考答案为学员的简答评分。\n"
            "输出必须是 JSON，字段：\n"
            '{"score": number 0..100, "feedback": str, "missed_points": [str]}'
        )

    def _build_short_answer_variables(
        self,
        *,
        answer_text: str,
        reference_answer: str,
        scoring_rubric: AiCoachScoringRubricV1,
    ) -> dict[str, Any]:
        return {
            "answer_text": answer_text,
            "reference_answer": reference_answer,
            "max_score": float(scoring_rubric.max_score),
            "scoring_points": [
                {
                    "key": p.key,
                    "score": float(p.score),
                    "description": p.description,
                }
                for p in scoring_rubric.points
            ],
            "partial_credit_policy": scoring_rubric.partial_credit_policy,
        }

    @staticmethod
    def _load_ai_coach_config_from_snapshot(raw: object) -> AiCoachConfig:
        if not isinstance(raw, dict):
            return AiCoachConfig.model_validate(raw)
        config_payload = {
            key: value
            for key, value in raw.items()
            if key in AI_COACH_CONFIG_FIELD_NAMES
        }
        return AiCoachConfig.model_validate(config_payload)

    @staticmethod
    def _prompt_resolver_public_code(
        exc: PromptTemplateRevisionResolverError,
    ) -> str:
        match exc.code:
            case "[PROMPT_TEMPLATE_INVALID_ID]":
                return "[AI_COACH_PROMPT_CONFIG_INVALID]"
            case "[PROMPT_TEMPLATE_NOT_FOUND]":
                return "[AI_COACH_PROMPT_REVISION_NOT_FOUND]"
            case _:
                return "[AI_COACH_PROMPT_CONFIG_INVALID]"

    @classmethod
    def _prompt_resolver_service_error(
        cls,
        exc: PromptTemplateRevisionResolverError,
    ) -> AiCoachSessionServiceError:
        code = cls._prompt_resolver_public_code(exc)
        status_code = 404 if code == "[AI_COACH_PROMPT_REVISION_NOT_FOUND]" else 409
        return AiCoachSessionServiceError(
            code,
            exc.message,
            status_code=status_code,
        )

    @staticmethod
    def _active_generation_settings(
        config_snapshot: dict[str, Any],
        ai_coach_config: AiCoachConfig,
    ) -> tuple[str, list[str]]:
        active_mode = config_snapshot.get("active_coach_mode")
        coach_mode = (
            active_mode
            if isinstance(active_mode, str) and active_mode.strip()
            else ai_coach_config.coach_mode
        )
        raw_allowed_types = config_snapshot.get("allowed_interaction_types")
        allowed_types = (
            [str(item) for item in raw_allowed_types]
            if isinstance(raw_allowed_types, list) and raw_allowed_types
            else [str(item) for item in ai_coach_config.allowed_interaction_types]
        )
        return coach_mode, allowed_types

    @staticmethod
    def _validate_requested_interaction_type_allowed(
        *,
        ai_coach_config: AiCoachConfig,
        coach_mode: str | None,
        interaction_type: str | None,
    ) -> None:
        allowed_types = set(ai_coach_config.allowed_interaction_types)
        requested_type = interaction_type
        if requested_type is None and coach_mode is not None:
            requested_type = SPECIFIC_COACH_MODE_INTERACTION_TYPES.get(coach_mode)
        if requested_type is None or requested_type in allowed_types:
            return
        raise AiCoachSessionServiceError(
            "[AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]",
            "当前模块未开放该 AI 教练互动类型。",
            status_code=403,
        )

    @staticmethod
    def _expected_interaction_type_for_mode(
        *,
        active_mode: str | None,
        active_explicit_type: str | None,
        turn_number: int,
        allowed_types: list[str],
    ) -> str | None:
        """Return the interaction_type the LLM should produce for this turn.

        Returns ``None`` when no constraint should be applied
        (e.g. legacy session with no coach_mode set, in which case the
        prompt template's own instructions govern the output).
        """
        if active_explicit_type is not None:
            return active_explicit_type
        specific_type = SPECIFIC_COACH_MODE_INTERACTION_TYPES.get(str(active_mode))
        if specific_type is not None:
            return specific_type
        if active_mode == "mixed_drill" and allowed_types:
            # Round-robin across allowed types so the learner actually
            # sees a mix instead of three single_choice followed by three
            # multi_choice etc.
            if not allowed_types:
                return None
            return allowed_types[(turn_number - 1) % len(allowed_types)]
        return None

    # ------------------------------------------------------------------
    # Public projection (allow-list)
    # ------------------------------------------------------------------

    def serialize_session_public(
        self,
        session: SalesTrainerAiCoachSession,
        turns: list[SalesTrainerAiCoachTurn],
    ) -> AiCoachSessionPublicResponse:
        """Project a session + its turns to the strict public DTO.

        The learner-facing model is built through Pydantic
        (``extra="forbid"``) so any field that is not in the public
        contract raises a validation error instead of leaking. The
        internal ``interaction_snapshot`` is never read here.
        """
        config_snapshot = json_dict_or_empty(session.config_snapshot)
        min_turns = int(config_snapshot.get("min_turns", 3))
        max_turns = int(config_snapshot.get("max_turns", 10))
        mastery_threshold = float(config_snapshot.get("mastery_threshold", 80.0))

        public_turns: list[AiCoachTurnPublicV1] = []
        for turn in turns:
            score_value = orm_scalar(turn.score, float, nullable=True)
            max_score_value = orm_scalar(turn.max_score, float, nullable=True)
            public_turns.append(
                AiCoachTurnPublicV1(
                    turn_id=orm_scalar(turn.turn_id, str),
                    turn_number=orm_scalar(turn.turn_number, int),
                    public_interaction=self._safe_public_interaction(turn),
                    user_answer_payload=self._safe_user_answer_payload(turn),
                    score=float(score_value) if score_value is not None else None,
                    max_score=float(max_score_value)
                    if max_score_value is not None
                    else None,
                    ai_feedback=orm_scalar(turn.ai_feedback, str, nullable=True),
                    missed_points=list(turn.missed_points or []),
                    next_turn_available=True,
                )
            )

        overall_mastered = (
            orm_scalar(session.status, str) == "completed"
            and orm_scalar(session.mastery_state, str, nullable=True) == "mastered"
        )
        total_score_value = orm_scalar(session.total_score, float, nullable=True)
        max_score_value = orm_scalar(session.max_score, float, nullable=True)
        public_turn_payloads: list[dict[str, Any]] = [
            turn.model_dump(mode="json") for turn in public_turns
        ]

        payload: dict[str, Any] = {
            "session_id": orm_scalar(session.session_id, str),
            "module_key": orm_scalar(session.module_key, str),
            "status": orm_scalar(session.status, str),
            "mastery_state": orm_scalar(session.mastery_state, str, nullable=True),
            "total_score": float(total_score_value)
            if total_score_value is not None
            else None,
            "max_score": float(max_score_value)
            if max_score_value is not None
            else None,
            "current_turn": len(turns),
            "min_turns": min_turns,
            "max_turns": max_turns,
            "mastery_threshold": mastery_threshold,
            "overall_mastered": overall_mastered,
            "created_at": orm_scalar(session.created_at, datetime),
            "updated_at": orm_scalar(session.updated_at, datetime),
            "turns": public_turn_payloads,
        }
        # Defensive allow-list sweep: drop anything that is not in the
        # learner-facing contract before model validation. This guards
        # against future schema drift leaking extra columns.
        payload = {
            key: value
            for key, value in payload.items()
            if key in ALLOWED_PUBLIC_SESSION_FIELDS
        }
        for index, turn_payload in enumerate(public_turn_payloads):
            public_turn_payloads[index] = {
                key: value
                for key, value in turn_payload.items()
                if key in ALLOWED_PUBLIC_TURN_FIELDS
            }
        return AiCoachSessionPublicResponse.model_validate(payload)

    # ------------------------------------------------------------------
    # v1 internal helpers
    # ------------------------------------------------------------------

    async def _build_generation_variables(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        turn: SalesTrainerAiCoachTurn,
        ai_coach_config: AiCoachConfig,
    ) -> dict[str, Any]:
        """Compose the variable bag fed to the prompt template renderer.

        Async because it needs to ``await self._get_previous_turns()``.
        """
        article_snapshot = json_dict_or_empty(session.article_snapshot)
        chapters = article_snapshot.get("chapters") or []
        chapter_titles: list[str] = []
        for chapter in chapters:
            if isinstance(chapter, dict):
                title = chapter.get("title")
                if isinstance(title, str) and title.strip():
                    chapter_titles.append(title)
        previous_turns: list[dict[str, Any]] = []
        for row in await self._get_previous_turns(orm_scalar(session.session_id, str)):
            previous_turns.append(
                {
                    "turn_number": row.get("turn_number"),
                    "question": row.get("question"),
                    "user_answer": row.get("user_answer"),
                    "score": row.get("score"),
                }
            )
        active_coach_mode, active_allowed_types = self._active_generation_settings(
            json_dict_or_empty(session.config_snapshot),
            ai_coach_config,
        )
        return {
            "module_key": orm_scalar(session.module_key, str),
            "turn_number": orm_scalar(turn.turn_number, int),
            "article_title": article_snapshot.get("title") or "",
            "article_summary": article_snapshot.get("summary") or "",
            "chapter_titles": chapter_titles,
            "previous_turns": previous_turns,
            "allowed_interaction_types": active_allowed_types,
            "coach_mode": active_coach_mode,
            "min_turns": ai_coach_config.min_turns,
            "max_turns": ai_coach_config.max_turns,
            "mastery_threshold": ai_coach_config.mastery_threshold,
        }

    def _build_generation_system_message(
        self,
        ai_coach_config: AiCoachConfig,
    ) -> str:
        return (
            "你是一位销售培训 AI 对话教练，负责生成下一轮结构化互动卡片；stem 应使用 Chatbot 式自然对话语气。\n"
            "严格输出 JSON，必须满足以下契约字段：\n"
            "{"
            '"schema_version": "ai_coach_interaction_v1",'
            '"interaction_type": "single_choice" | "multiple_choice" | "short_answer",'
            '"stem": str,'
            '"options": [...] | null,'
            '"answer_key": {"option_ids": [...], "reference_answer": str | null},'
            '"scoring_rubric": {"max_score": number, "points": [...], '
            '"partial_credit_policy": "all_or_nothing" | "proportional" | "tiered"},'
            '"feedback_guidance": {"correct": str, "incorrect": str},'
            '"source_evidence": [...] | null'
            "}"
        )

    def _build_short_answer_prompt(
        self,
        *,
        answer_text: str,
        reference_answer: str,
        scoring_rubric: AiCoachScoringRubricV1,
    ) -> str:
        return (
            "学员回答：\n"
            f"{answer_text}\n\n"
            "参考答案：\n"
            f"{reference_answer or '(无)'}\n\n"
            f"满分：{scoring_rubric.max_score}\n"
            '请给出 JSON：{"score": 0..满分, "feedback": str, '
            '"missed_points": [str]}。\n'
        )

    def _load_internal_interaction(
        self,
        turn: SalesTrainerAiCoachTurn,
    ) -> AiCoachInteractionInternalV1 | None:
        snapshot = turn.interaction_snapshot
        if not snapshot:
            return None
        try:
            return AiCoachInteractionInternalV1.model_validate(snapshot)
        except ValidationError:
            return None

    def _project_to_public(
        self,
        internal: AiCoachInteractionInternalV1,
        *,
        session: SalesTrainerAiCoachSession,
        turn: SalesTrainerAiCoachTurn,
    ) -> AiCoachInteractionPublicV1:
        options_payload: list[AiCoachPublicInteractionOptionV1] | None = None
        if internal.options:
            # NOTE: ``is_distractor`` is intentionally dropped here.
            # The public render spec must not leak which option is the
            # answer — that would let the learner defeat the question by
            # always picking the option whose distractor flag is false.
            options_payload = [
                AiCoachPublicInteractionOptionV1(
                    option_id=opt.option_id,
                    text=opt.text,
                )
                for opt in internal.options
            ]
        constraints: dict[str, int] = {}
        if internal.interaction_type == "single_choice":
            constraints["min_selected"] = 1
            constraints["max_selected"] = 1
        elif internal.interaction_type == "multiple_choice":
            constraints["min_selected"] = 1
            constraints["max_selected"] = len(internal.options or [])
        else:  # short_answer
            constraints["min_length"] = 1
            constraints["max_length"] = 8000
        return AiCoachInteractionPublicV1(
            schema_version=AI_COACH_PUBLIC_INTERACTION_SCHEMA_VERSION,
            interaction_id=(
                f"{orm_scalar(session.session_id, str)}:"
                f"{orm_scalar(turn.turn_number, int)}"
            ),
            session_id=orm_scalar(session.session_id, str),
            turn_number=orm_scalar(turn.turn_number, int),
            interaction_type=internal.interaction_type,
            stem=internal.stem,
            options=options_payload,
            answer_constraints=constraints,
        )

    def _safe_public_interaction(
        self, turn: SalesTrainerAiCoachTurn
    ) -> AiCoachInteractionPublicV1 | None:
        raw = turn.public_interaction
        if not raw:
            return None
        try:
            return AiCoachInteractionPublicV1.model_validate(raw)
        except ValidationError:
            return None

    def _safe_user_answer_payload(
        self, turn: SalesTrainerAiCoachTurn
    ) -> dict[str, Any] | None:
        raw = turn.answer_payload
        if not raw:
            return None
        try:
            return AiCoachAnswerPayloadV1.model_validate(raw).model_dump(mode="json")
        except ValidationError:
            return None

    def _build_missed_points(
        self,
        *,
        scoring_rubric: AiCoachScoringRubricV1,
        correct: set[str],
        user: set[str],
    ) -> list[str]:
        missed: list[str] = []
        wrong = sorted(user - correct)
        missing = sorted(correct - user)
        if wrong:
            missed.append(f"多选了：{','.join(wrong)}")
        if missing:
            missed.append(f"漏选了：{','.join(missing)}")
        if not missed and scoring_rubric.points:
            for point in scoring_rubric.points:
                if point.description and point.key not in user:
                    missed.append(point.description)
        return missed[:5]

    def _point_covered(
        self,
        point: AiCoachScoringPointV1,
        user_set: set[str],
        correct_set: set[str],
    ) -> bool:
        if point.key in correct_set:
            return point.key in user_set
        return point.key in user_set

    def _choice_feedback(
        self,
        *,
        hit: bool,
        correct: set[str],
        user: set[str],
        guidance: AiCoachFeedbackGuidanceV1 | None,
    ) -> str:
        if guidance is None:
            return "回答正确。" if hit else "回答错误，请继续学习。"
        if hit:
            return guidance.correct
        wrong = sorted(user - correct)
        missing = sorted(correct - user)
        fragments: list[str] = []
        if wrong:
            fragments.append(f"多选：{','.join(wrong)}")
        if missing:
            fragments.append(f"漏选：{','.join(missing)}")
        suffix = f"（{'; '.join(fragments)}）" if fragments else ""
        return f"{guidance.incorrect}{suffix}"

    def _should_finish_session(
        self,
        *,
        turn_count: int,
        min_turns: int,
        max_turns: int,
        mastery_threshold: float,
        latest_score: float,
    ) -> bool:
        if turn_count >= max_turns:
            return True
        if turn_count >= min_turns and latest_score >= mastery_threshold:
            return True
        return False

    def _evaluate_mastery(
        self,
        *,
        avg_score: float,
        mastery_threshold: float,
    ) -> str:
        return "mastered" if avg_score >= mastery_threshold else "not_mastered"

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract a JSON object from a string. Tolerant of ```json fences."""
        text = (text or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            lines = text.split("\n", 1)
            text = lines[1] if len(lines) > 1 else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
        except json.JSONDecodeError:
            pass
        return None

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.schemas import (
    ExaminerAgentCreate,
    ExaminerAgentSimulationRequest,
    ExaminerAgentSimulationResponse,
    ExaminerAgentUpdate,
    PublishGateDecision,
)
from curriculum_practice.services.content_assets import (
    list_published_template_references,
)
from curriculum_practice.services.examiner_agent_duplicates import (
    build_examiner_agent_duplicate,
)
from curriculum_practice.services.examiner_agent_payloads import (
    examiner_agent_content_hash,
    examiner_agent_create_data,
    examiner_agent_lifecycle_snapshot,
    examiner_agent_ref,
    serialize_examiner_agent,
)
from curriculum_practice.services.examiner_agent_publish_gates import (
    examiner_timeout_seconds,
    resolve_examiner_learner_level,
    validate_examiner_agent_publish,
)
from curriculum_practice.services.examiner_agent_revision_service import (
    ExaminerAgentRevisionService,
)
from curriculum_practice.services.orm_payload_typing import (
    orm_dict,
    orm_list,
    set_orm_field,
)

SERVER_ERROR = "[EXAMINER_AGENT_SERVICE_FAILED]"
ExaminerAgentUnpublishResult = ExaminerAgent | list[dict[str, str]]


class ExaminerAgentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_agents(
        self, *, status: str | None = None
    ) -> Result[list[ExaminerAgent]]:
        stmt = select(ExaminerAgent)
        if status:
            stmt = stmt.where(ExaminerAgent.status == status)
        try:
            result = await self._db.execute(
                stmt.order_by(ExaminerAgent.updated_at.desc())
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(list(result.scalars().all()))

    async def get_agent(self, examiner_agent_id: str) -> Result[ExaminerAgent]:
        try:
            agent = await self._db.get(ExaminerAgent, examiner_agent_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if agent is None:
            return Result.fail("[EXAMINER_AGENT_NOT_FOUND]")
        return Result.ok(agent)

    async def create_agent(
        self, payload: ExaminerAgentCreate, *, actor_id: str | None
    ) -> Result[ExaminerAgent]:
        data = examiner_agent_create_data(payload)
        agent = ExaminerAgent(**data, created_by=actor_id, updated_by=actor_id)
        self._db.add(agent)
        return await self._commit_agent(agent)

    async def update_agent(
        self,
        agent: ExaminerAgent,
        payload: ExaminerAgentUpdate,
        *,
        actor_id: str | None,
    ) -> Result[ExaminerAgent]:
        if agent.status == "archived":
            return Result.fail("[EXAMINER_AGENT_NOT_EDITABLE]")
        if agent.status == "published":
            actor_result = await self._actor_result(actor_id)
            if not actor_result.is_success or actor_result.value is None:
                return Result.fail(
                    actor_result.fallback or "[EXAMINER_AGENT_ACTOR_REQUIRED]"
                )
            await ExaminerAgentRevisionService(self._db).stage_future_revision(
                agent,
                payload,
                actor=actor_result.value,
            )
            return await self._commit_agent(agent)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json")
            setattr(agent, field, value)
        set_orm_field(agent, "updated_by", actor_id)
        return await self._commit_agent(agent)

    async def publish_agent(
        self, agent: ExaminerAgent, *, actor_id: str | None
    ) -> Result[ExaminerAgent | PublishGateDecision]:
        if agent.status == "archived":
            return Result.fail("[EXAMINER_AGENT_NOT_EDITABLE]")
        actor_result = await self._actor_result(actor_id)
        if not actor_result.is_success or actor_result.value is None:
            return Result.fail(
                actor_result.fallback or "[EXAMINER_AGENT_ACTOR_REQUIRED]"
            )
        revision_service = ExaminerAgentRevisionService(self._db)
        if agent.status == "published":
            (
                staged,
                staged_decision,
            ) = await revision_service.stage_publish_working_revision(
                agent,
                actor=actor_result.value,
            )
            if not staged_decision.can_publish:
                return Result(
                    value=staged_decision,
                    fallback="[EXAMINER_AGENT_PUBLISH_GATE_FAILED]",
                    is_success=False,
                )
            if staged:
                return await self._commit_publish_agent(agent)
        decision = await self.validate_publish(agent)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[EXAMINER_AGENT_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        set_orm_field(agent, "status", "published")
        set_orm_field(agent, "published_by", actor_id)
        set_orm_field(agent, "published_at", datetime.now(UTC))
        set_orm_field(agent, "content_hash", examiner_agent_content_hash(agent))
        set_orm_field(agent, "updated_by", actor_id)
        await revision_service.stage_initial_published_revision(
            agent,
            actor=actor_result.value,
        )
        return await self._commit_publish_agent(agent)

    async def archive_agent(
        self, agent: ExaminerAgent, *, actor_id: str | None
    ) -> Result[ExaminerAgent]:
        set_orm_field(agent, "status", "archived")
        set_orm_field(agent, "updated_by", actor_id)
        return await self._commit_agent(agent)

    async def duplicate_agent(
        self, agent: ExaminerAgent, *, actor_id: str | None
    ) -> Result[ExaminerAgent]:
        duplicate = build_examiner_agent_duplicate(agent, actor_id=actor_id)
        self._db.add(duplicate)
        return await self._commit_agent(duplicate)

    async def unpublish_agent(
        self, agent: ExaminerAgent, *, actor_id: str | None, acknowledge: bool = False
    ) -> Result[ExaminerAgentUnpublishResult]:
        if agent.status == "draft":
            return Result.fail("[EXAMINER_AGENT_ALREADY_DRAFT]")
        if agent.status == "archived":
            return Result.fail("[EXAMINER_AGENT_NOT_EDITABLE]")
        references = await list_published_template_references(
            self._db,
            asset_type="examiner_agent",
            asset_id=str(agent.examiner_agent_id),
        )
        if references and not acknowledge:
            return Result(
                value=references,
                fallback="[EXAMINER_AGENT_REFERENCED_BY_PUBLISHED_TEMPLATES]",
                is_success=False,
            )
        set_orm_field(agent, "status", "draft")
        set_orm_field(agent, "published_at", None)
        set_orm_field(agent, "published_by", None)
        set_orm_field(agent, "updated_by", actor_id)
        commit_result = await self._commit_agent(agent)
        if not commit_result.is_success:
            return Result.fail(commit_result.fallback or SERVER_ERROR)
        return Result(value=commit_result.value, is_success=True)

    async def list_template_references(
        self, *, examiner_agent_id: str
    ) -> Result[list[dict[str, str]]]:
        try:
            references = await list_published_template_references(
                self._db,
                asset_type="examiner_agent",
                asset_id=examiner_agent_id,
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(references)

    async def simulate_agent(
        self, agent: ExaminerAgent, payload: ExaminerAgentSimulationRequest
    ) -> Result[ExaminerAgentSimulationResponse | PublishGateDecision]:
        decision = await self.validate_publish(agent)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[EXAMINER_AGENT_SIMULATION_GATE_FAILED]",
                is_success=False,
            )
        question_ids = [str(item) for item in orm_list(agent.question_source_ids)]
        selected_question_id = payload.question_id or question_ids[0]
        if selected_question_id not in question_ids:
            return Result.fail("[EXAMINER_SIMULATION_QUESTION_NOT_BOUND]")
        question = await self._db.get(QuestionItem, selected_question_id)
        if (
            question is None
            or question.status != "published"
            or question.safety_flagged
        ):
            return Result.fail("[EXAMINER_SIMULATION_QUESTION_UNAVAILABLE]")
        learner_level = resolve_examiner_learner_level(
            payload.learner_level,
            orm_dict(agent.learner_level_strategy),
        )
        if learner_level is None:
            return Result.fail("[EXAMINER_LEARNER_LEVEL_NOT_ALLOWED]")
        answer_length = sum(
            1 for char in payload.sample_answer.strip() if char.isalnum()
        )
        score = min(100, max(0, answer_length))
        response = ExaminerAgentSimulationResponse(
            examiner_agent_id=str(agent.examiner_agent_id),
            selected_question_id=selected_question_id,
            learner_level=learner_level,
            scoring_policy_id=str(agent.scoring_policy_id),
            timeout_seconds=examiner_timeout_seconds(orm_dict(agent.timeout_config)),
            result={
                "passed": score >= 10,
                "score": score,
                "feedback": "dry_run_examiner_check",
                "question_title": question.title,
            },
        )
        return Result.ok(response)

    async def _commit_publish_agent(
        self,
        agent: ExaminerAgent,
    ) -> Result[ExaminerAgent | PublishGateDecision]:
        result = await self._commit_agent(agent)
        if not result.is_success or result.value is None:
            return Result.fail(result.fallback or SERVER_ERROR)
        return Result(value=result.value, is_success=True)

    async def validate_publish(self, agent: ExaminerAgent) -> PublishGateDecision:
        return await validate_examiner_agent_publish(
            self._db,
            examiner_agent_lifecycle_snapshot(agent),
        )

    async def _commit_agent(self, agent: ExaminerAgent) -> Result[ExaminerAgent]:
        try:
            await self._db.commit()
            await self._db.refresh(agent)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(agent)

    async def _actor_result(self, actor_id: str | None) -> Result[User]:
        if actor_id is None:
            return Result.fail("[EXAMINER_AGENT_ACTOR_REQUIRED]")
        try:
            actor = await self._db.get(User, actor_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if actor is None:
            return Result.fail("[EXAMINER_AGENT_ACTOR_REQUIRED]")
        return Result.ok(actor)


__all__ = [
    "ExaminerAgentService",
    "examiner_agent_content_hash",
    "examiner_agent_ref",
    "serialize_examiner_agent",
]

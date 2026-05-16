from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ScoringRuleset
from common.error_handling.result import Result
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.schemas import (
    ExaminerAgentCreate,
    ExaminerAgentResponse,
    ExaminerAgentSimulationRequest,
    ExaminerAgentSimulationResponse,
    ExaminerAgentUpdate,
    GateResult,
    LearnerLevel,
    PublishGateDecision,
)

SERVER_ERROR = "[EXAMINER_AGENT_SERVICE_FAILED]"
LEARNER_LEVELS = {"conservative", "beginner", "intermediate", "advanced"}


class ExaminerAgentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_agents(self, *, status: str | None = None) -> Result[list[ExaminerAgent]]:
        stmt = select(ExaminerAgent)
        if status:
            stmt = stmt.where(ExaminerAgent.status == status)
        try:
            result = await self._db.execute(stmt.order_by(ExaminerAgent.updated_at.desc()))
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
        data = _payload_data(payload)
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
        if agent.status != "draft":
            return Result.fail("[EXAMINER_AGENT_NOT_EDITABLE]")
        for field, value in payload.model_dump(exclude_unset=True).items():
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json")
            setattr(agent, field, value)
        agent.updated_by = actor_id
        return await self._commit_agent(agent)

    async def publish_agent(
        self, agent: ExaminerAgent, *, actor_id: str | None
    ) -> Result[ExaminerAgent | PublishGateDecision]:
        if agent.status == "archived":
            return Result.fail("[EXAMINER_AGENT_NOT_EDITABLE]")
        decision = await self.validate_publish(agent)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[EXAMINER_AGENT_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        agent.status = "published"
        agent.published_by = actor_id
        agent.published_at = datetime.now(UTC)
        agent.content_hash = examiner_agent_content_hash(agent)
        agent.updated_by = actor_id
        return await self._commit_agent(agent)

    async def archive_agent(
        self, agent: ExaminerAgent, *, actor_id: str | None
    ) -> Result[ExaminerAgent]:
        agent.status = "archived"
        agent.updated_by = actor_id
        return await self._commit_agent(agent)

    async def simulate_agent(
        self, agent: ExaminerAgent, payload: ExaminerAgentSimulationRequest
    ) -> Result[ExaminerAgentSimulationResponse]:
        decision = await self.validate_publish(agent)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[EXAMINER_AGENT_SIMULATION_GATE_FAILED]",
                is_success=False,
            )
        question_ids = [str(item) for item in agent.question_source_ids or []]
        selected_question_id = payload.question_id or question_ids[0]
        if selected_question_id not in question_ids:
            return Result.fail("[EXAMINER_SIMULATION_QUESTION_NOT_BOUND]")
        question = await self._db.get(QuestionItem, selected_question_id)
        if question is None or question.status != "published" or question.safety_flagged:
            return Result.fail("[EXAMINER_SIMULATION_QUESTION_UNAVAILABLE]")
        learner_level = _resolve_learner_level(
            payload.learner_level,
            agent.learner_level_strategy,
        )
        if learner_level is None:
            return Result.fail("[EXAMINER_LEARNER_LEVEL_NOT_ALLOWED]")
        answer_length = sum(1 for char in payload.sample_answer.strip() if char.isalnum())
        score = min(100, max(0, answer_length))
        response = ExaminerAgentSimulationResponse(
            examiner_agent_id=str(agent.examiner_agent_id),
            selected_question_id=selected_question_id,
            learner_level=learner_level,
            scoring_policy_id=str(agent.scoring_policy_id),
            timeout_seconds=_timeout_seconds(agent.timeout_config),
            result={
                "passed": score >= 10,
                "score": score,
                "feedback": "dry_run_examiner_check",
                "question_title": question.title,
            },
        )
        return Result.ok(response)

    async def validate_publish(self, agent: ExaminerAgent) -> PublishGateDecision:
        results: list[GateResult] = []
        question_ids = [str(item).strip() for item in agent.question_source_ids or []]
        if not question_ids:
            results.append(
                _gate(
                    "examiner_question_source",
                    "[EXAMINER_QUESTION_SOURCE_EMPTY]",
                    "ExaminerAgent requires at least one question source.",
                )
            )
        for question_id in question_ids:
            question = await self._db.get(QuestionItem, question_id)
            if question is None or question.status != "published":
                results.append(
                    _gate(
                        "examiner_question_source",
                        "[EXAMINER_QUESTION_UNPUBLISHED]",
                        f"Question source {question_id} is missing or unpublished.",
                    )
                )
                continue
            if question.safety_flagged:
                results.append(
                    _gate(
                        "examiner_question_safety",
                        "[EXAMINER_QUESTION_SAFETY_FLAGGED]",
                        f"Question source {question_id} is safety flagged.",
                    )
                )
        ruleset = await self._db.get(ScoringRuleset, agent.scoring_policy_id)
        if ruleset is None or ruleset.status != "published" or not bool(ruleset.is_active):
            results.append(
                _gate(
                    "examiner_scoring_policy",
                    "[EXAMINER_SCORING_POLICY_INVALID]",
                    "ExaminerAgent scoring policy must be an active published ruleset.",
                )
            )
        if not _valid_timeout(agent.timeout_config):
            results.append(
                _gate(
                    "examiner_timeout_policy",
                    "[EXAMINER_TIMEOUT_POLICY_INVALID]",
                    "ExaminerAgent timeout_config.max_seconds must be between 1 and 1500.",
                )
            )
        if not _valid_learner_strategy(agent.learner_level_strategy):
            results.append(
                _gate(
                    "examiner_learner_level_strategy",
                    "[EXAMINER_LEARNER_LEVEL_STRATEGY_INVALID]",
                    "ExaminerAgent learner level strategy is invalid.",
                )
            )
        return PublishGateDecision(can_publish=not results, results=results)

    async def _commit_agent(self, agent: ExaminerAgent) -> Result[ExaminerAgent]:
        try:
            await self._db.commit()
            await self._db.refresh(agent)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(agent)


def serialize_examiner_agent(agent: ExaminerAgent) -> ExaminerAgentResponse:
    return ExaminerAgentResponse.model_validate(agent)


def examiner_agent_ref(agent: ExaminerAgent) -> dict[str, object]:
    return {
        "asset_type": "examiner_agent",
        "asset_id": str(agent.examiner_agent_id),
        "version": int(agent.version),
        "hash": str(agent.content_hash or examiner_agent_content_hash(agent)),
        "snapshot_label": "published",
    }


def examiner_agent_content_hash(agent: ExaminerAgent) -> str:
    payload = {
        "name": agent.name,
        "description": agent.description,
        "question_source_ids": list(agent.question_source_ids or []),
        "learner_level_strategy": agent.learner_level_strategy or {},
        "scoring_policy_id": agent.scoring_policy_id,
        "timeout_config": agent.timeout_config or {},
        "safety_config": agent.safety_config or {},
        "prompt_config": agent.prompt_config or {},
        "simulation_config": agent.simulation_config or {},
        "version": agent.version,
    }
    return "sha256:" + sha256(
        dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _payload_data(payload: ExaminerAgentCreate) -> dict[str, object]:
    data = payload.model_dump(mode="json")
    data["learner_level_strategy"] = payload.learner_level_strategy.model_dump(
        mode="json"
    )
    data["timeout_config"] = payload.timeout_config.model_dump(mode="json")
    return data


def _valid_timeout(config: object) -> bool:
    if not isinstance(config, dict):
        return False
    raw_max_seconds = config.get("max_seconds")
    if raw_max_seconds is None:
        return False
    try:
        max_seconds = int(raw_max_seconds)
    except (TypeError, ValueError):
        return False
    return 1 <= max_seconds <= 1500


def _timeout_seconds(config: object) -> int:
    if not isinstance(config, dict):
        return 0
    raw_max_seconds = config.get("max_seconds")
    if raw_max_seconds is None:
        return 0
    try:
        return int(raw_max_seconds)
    except (TypeError, ValueError):
        return 0


def _resolve_learner_level(
    requested_level: LearnerLevel | None,
    strategy: object,
) -> LearnerLevel | None:
    if not isinstance(strategy, dict):
        return requested_level or "conservative"
    allowed_levels = strategy.get("allowed_levels")
    if not isinstance(allowed_levels, list):
        allowed_levels = list(LEARNER_LEVELS)
    level = requested_level or strategy.get("default_level") or "conservative"
    if level == "conservative" and level in allowed_levels:
        return "conservative"
    if level == "beginner" and level in allowed_levels:
        return "beginner"
    if level == "intermediate" and level in allowed_levels:
        return "intermediate"
    if level == "advanced" and level in allowed_levels:
        return "advanced"
    return None


def _valid_learner_strategy(strategy: object) -> bool:
    if not isinstance(strategy, dict):
        return False
    default_level = strategy.get("default_level")
    allowed_levels = strategy.get("allowed_levels")
    return (
        isinstance(default_level, str)
        and default_level in LEARNER_LEVELS
        and isinstance(allowed_levels, list)
        and bool(allowed_levels)
        and all(isinstance(level, str) and level in LEARNER_LEVELS for level in allowed_levels)
        and default_level in allowed_levels
    )


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )

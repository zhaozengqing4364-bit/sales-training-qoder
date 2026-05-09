"""
Staged Evaluation Service

Requirements: C3 - Implement StagedEvaluationService

Features:
- Evaluate conversation stages using configured prompts
- Trigger-based stage detection
- Store evaluation results per stage
- Progress tracking across stages
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from common.error_handling.result import Result
from evaluation.schemas import StageEvaluationResponse, parse_llm_response
from evaluation.triggers.base_trigger import TriggerContext
from prompt_templates.service import PromptTemplateService


def _runtime_field(row: object, name: str) -> Any:
    return cast(Any, getattr(row, name))


def _runtime_int(row: object, name: str, default: int = 0) -> int:
    try:
        return int(getattr(row, name, default) or default)
    except (TypeError, ValueError):
        return default


def _runtime_list(row: object, name: str) -> list[Any]:
    value = getattr(row, name, [])
    return value if isinstance(value, list) else []


@dataclass
class StageEvaluationResult:
    """Result of evaluating a single stage."""

    stage_number: int
    start_turn: int
    end_turn: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    scores: dict[str, float] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class StageConfig:
    """Configuration for a conversation stage."""

    stage_number: int
    name: str
    description: str
    evaluation_prompt_type: str
    triggers: list[Any] = field(default_factory=list)
    start_turn: int | None = None
    end_turn: int | None = None


def _coerce_turn_index(value: Any, total_turns: int) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(total_turns, parsed))


def _message_matches_stage(message: dict[str, Any], stage_markers: set[Any]) -> bool:
    for key in ("stage_number", "stage", "stage_id", "stage_name", "current_stage"):
        value = message.get(key)
        if value in stage_markers or str(value) in stage_markers:
            return True
    metadata = message.get("metadata")
    if isinstance(metadata, dict):
        return _message_matches_stage(metadata, stage_markers)
    return False


class StagedEvaluationService:
    """Service for staged evaluation of conversations.

    Evaluates conversation in stages based on triggers:
    - Detects stage boundaries using triggers
    - Evaluates each stage with configured prompts
    - Stores results for comprehensive reporting
    """

    def __init__(
        self,
        db_session: AsyncSession,
        prompt_service: PromptTemplateService,
        llm_service: LLMService,
    ):
        """Initialize service.

        Args:
            db_session: Database session
            prompt_service: Prompt template service
            llm_service: LLM service for evaluations
        """
        self.db = db_session
        self.prompt_service = prompt_service
        self.llm = llm_service

        # Stage configurations by scenario type
        self._stage_configs: dict[str, list[StageConfig]] = {}

    async def evaluate_stage(
        self,
        session_id: str,
        stage_config: StageConfig,
        conversation_history: list[dict],
    ) -> Result[StageEvaluationResult]:
        """Evaluate a single conversation stage.

        Args:
            session_id: Practice session ID
            stage_config: Configuration for this stage
            conversation_history: Full conversation history

        Returns:
            Result with stage evaluation
        """
        try:
            # Get stage-specific conversation segment from real boundaries.
            start_turn, end_turn = self._resolve_stage_turn_bounds(
                stage_config,
                conversation_history,
            )

            stage_conversation = conversation_history[start_turn:end_turn]

            # Get evaluation prompt
            prompt_result = await self.prompt_service.get_template_for_scenario(
                prompt_type=stage_config.evaluation_prompt_type,
                scenario_type="sales",  # TODO: parameterize
            )

            if not prompt_result:
                return Result.fail(
                    f"[PROMPT_NOT_FOUND:{stage_config.evaluation_prompt_type}]"
                )

            # Render prompt with conversation
            render_variables = {
                "conversation": self._format_conversation(stage_conversation),
                "stage_name": stage_config.name,
                "stage_description": stage_config.description,
            }
            contract_result = self.prompt_service.compile_runtime_prompt_contract(
                template=prompt_result,
                variables=render_variables,
                runtime_consumer=(
                    "evaluation.services.staged_evaluation."
                    "StagedEvaluationService.evaluate_stage"
                ),
                system_message=(
                    "你是一个专业的销售培训评估专家。请严格按照JSON格式返回评估结果。"
                ),
            )
            if not contract_result.is_success:
                return Result.fail(
                    contract_result.fallback or "[PROMPT_CONTRACT_COMPILE_FAILED]"
                )
            compiled_contract = contract_result.value
            if compiled_contract is None:
                return Result.fail("[PROMPT_CONTRACT_COMPILE_FAILED:EMPTY_CONTRACT]")
            compiled_contract = cast(Any, compiled_contract)

            # Call LLM for evaluation
            llm_result = await self.llm.evaluate(compiled_contract)

            if not llm_result.is_success:
                return Result.fail("[LLM_EVALUATION_FAILED]")
            llm_payload = llm_result.value
            if llm_payload is None:
                return Result.fail("[LLM_EVALUATION_FAILED:EMPTY_RESPONSE]")
            llm_payload_typed = cast(str | dict[Any, Any] | bytes, llm_payload)

            # Parse evaluation result
            parse_result = await parse_llm_response(
                llm_payload_typed, StageEvaluationResponse
            )
            if not parse_result.is_success:
                return Result.fail(f"[LLM_VALIDATION_FAILED:{parse_result.fallback}]")

            parsed_eval = cast(StageEvaluationResponse | None, parse_result.value)
            if parsed_eval is None:
                return Result.fail("[LLM_VALIDATION_FAILED:EMPTY_RESPONSE]")

            weaknesses: list[str] = []
            raw_value: str | dict[Any, Any] | bytes = llm_payload_typed
            raw_dict: dict[Any, Any] | None = None
            if isinstance(raw_value, str):
                try:
                    raw_dict = json.loads(raw_value)
                    raw_weaknesses = (
                        raw_dict.get("weaknesses", [])
                        if isinstance(raw_dict, dict)
                        else []
                    )
                    weaknesses = (
                        raw_weaknesses if isinstance(raw_weaknesses, list) else []
                    )
                except json.JSONDecodeError:
                    weaknesses = []
            elif isinstance(raw_value, dict):
                raw_weaknesses = raw_value.get("weaknesses", [])
                weaknesses = raw_weaknesses if isinstance(raw_weaknesses, list) else []

            result = StageEvaluationResult(
                stage_number=stage_config.stage_number,
                start_turn=start_turn,
                end_turn=end_turn,
                timestamp=datetime.now(UTC),
                scores=parsed_eval.scores,
                strengths=parsed_eval.strengths,
                weaknesses=weaknesses,
                suggestions=parsed_eval.suggestions,
                summary=parsed_eval.summary,
            )

            # Store in database
            store_result = await self._store_evaluation(session_id, result)
            if not store_result.is_success:
                return Result.fail(store_result.fallback or "[DATABASE_ERROR]")

            return Result.ok(result)

        except Exception as e:
            return Result.fail(f"[STAGE_EVALUATION_ERROR:{str(e)}]")

    @staticmethod
    def _resolve_stage_turn_bounds(
        stage_config: StageConfig,
        conversation_history: list[dict],
    ) -> tuple[int, int]:
        """Resolve stage bounds from explicit config or message stage metadata."""
        total_turns = len(conversation_history)
        explicit_start = _coerce_turn_index(stage_config.start_turn, total_turns)
        explicit_end = _coerce_turn_index(stage_config.end_turn, total_turns)
        if explicit_start is not None or explicit_end is not None:
            start_turn = explicit_start if explicit_start is not None else 0
            end_turn = explicit_end if explicit_end is not None else total_turns
            if end_turn < start_turn:
                end_turn = start_turn
            return start_turn, end_turn

        stage_markers = {
            stage_config.stage_number,
            str(stage_config.stage_number),
            stage_config.name,
        }
        matching_indices = [
            index
            for index, message in enumerate(conversation_history)
            if _message_matches_stage(message, stage_markers)
        ]
        if matching_indices:
            return min(matching_indices), max(matching_indices) + 1

        return 0, total_turns

    async def check_triggers(
        self,
        session_id: str,
        conversation_history: list[dict],
        stage_configs: list[StageConfig],
    ) -> list[StageConfig]:
        """Check if any stage triggers are activated.

        Args:
            session_id: Session ID
            conversation_history: Current conversation
            stage_configs: Available stage configurations

        Returns:
            List of triggered stage configs
        """
        triggered = []

        last_user_message = None
        last_bot_message = None
        for message in reversed(conversation_history):
            role = message.get("role")
            if last_user_message is None and role == "user":
                last_user_message = message.get("content")
            if last_bot_message is None and role in {"assistant", "bot", "ai"}:
                last_bot_message = message.get("content")
            if last_user_message is not None and last_bot_message is not None:
                break

        for config in stage_configs:
            for trigger in config.triggers:
                context = TriggerContext(
                    session_id=session_id,
                    turn_count=len(conversation_history),
                    messages=conversation_history,
                    last_user_message=last_user_message,
                    last_bot_message=last_bot_message,
                    turns_since_last_trigger=0,
                    current_stage=str(config.stage_number),
                )

                if await trigger.check(context):
                    triggered.append(config)
                    break  # Don't check other triggers for this stage

        return triggered

    async def get_stage_results(
        self,
        session_id: str,
    ) -> list[StageEvaluationResult]:
        """Get all stage evaluation results for a session.

        Args:
            session_id: Session ID

        Returns:
            List of stage evaluation results
        """
        from common.db.models import StagedEvaluationResult as DBModel

        result = await self.db.execute(
            select(DBModel)
            .where(DBModel.session_id == session_id)
            .order_by(DBModel.stage_number)
        )

        db_results = result.scalars().all()

        return [
            StageEvaluationResult(
                stage_number=_runtime_int(r, "stage_number"),
                start_turn=_runtime_int(r, "start_turn"),
                end_turn=_runtime_int(r, "end_turn"),
                timestamp=_runtime_field(r, "created_at"),
                scores=dict(_runtime_field(r, "scores") or {}),
                strengths=[str(item) for item in _runtime_list(r, "strengths")],
                weaknesses=[str(item) for item in _runtime_list(r, "weaknesses")],
                suggestions=[str(item) for item in _runtime_list(r, "suggestions")],
                summary=str(_runtime_field(r, "summary") or ""),
            )
            for r in db_results
        ]

    async def register_stage_config(
        self,
        scenario_type: str,
        configs: list[StageConfig],
    ) -> None:
        """Register stage configurations for a scenario type.

        Args:
            scenario_type: Type of scenario (e.g., 'sales', 'presentation')
            configs: List of stage configurations
        """
        self._stage_configs[scenario_type] = configs

    def get_stage_configs(self, scenario_type: str) -> list[StageConfig]:
        """Get stage configurations for a scenario type.

        Args:
            scenario_type: Scenario type

        Returns:
            List of stage configurations
        """
        return self._stage_configs.get(scenario_type, [])

    def _format_conversation(self, conversation: list[dict]) -> str:
        """Format conversation for prompt.

        Args:
            conversation: List of conversation turns

        Returns:
            Formatted conversation string
        """
        lines = []
        for turn in conversation:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def _store_evaluation(
        self,
        session_id: str,
        result: StageEvaluationResult,
    ) -> Result[None]:
        """Store evaluation result in database.

        Args:
            session_id: Session ID
            result: Evaluation result to store
        """
        from common.db.models import StagedEvaluationResult as DBModel

        db_result = DBModel(
            id=str(uuid4()),
            session_id=session_id,
            stage_number=result.stage_number,
            start_turn=result.start_turn,
            end_turn=result.end_turn,
            created_at=result.timestamp,
            scores=result.scores,
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            suggestions=result.suggestions,
            summary=result.summary,
        )

        try:
            self.db.add(db_result)
            await self.db.commit()
            return Result.ok(None)
        except Exception as e:
            await self.db.rollback()
            return Result.fail(f"[DATABASE_ERROR:{str(e)}]")

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

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from evaluation.triggers.base_trigger import TriggerContext
from evaluation.schemas import StageEvaluationResponse, parse_llm_response
from prompt_templates.service import PromptTemplateService
from common.ai.llm_service import LLMService
from common.error_handling.result import Result


@dataclass
class StageEvaluationResult:
    """Result of evaluating a single stage."""

    stage_number: int
    start_turn: int
    end_turn: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
            # Get stage-specific conversation segment
            start_turn = stage_config.stage_number * 2  # Simplified logic
            end_turn = len(conversation_history)

            stage_conversation = conversation_history[start_turn:end_turn]

            # Get evaluation prompt
            prompt_result = await self.prompt_service.get_template_for_scenario(
                prompt_type=stage_config.evaluation_prompt_type,
                scenario_type="sales",  # TODO: parameterize
            )

            if not prompt_result:
                return Result.fail(f"[PROMPT_NOT_FOUND:{stage_config.evaluation_prompt_type}]")

            # Render prompt with conversation
            render_request = {
                "template_id": prompt_result.id,
                "variables": {
                    "conversation": self._format_conversation(stage_conversation),
                    "stage_name": stage_config.name,
                    "stage_description": stage_config.description,
                },
            }

            # Call LLM for evaluation
            llm_result = await self.llm.evaluate(render_request)

            if not llm_result.is_success:
                return Result.fail("[LLM_EVALUATION_FAILED]")

            # Parse evaluation result
            parse_result = await parse_llm_response(llm_result.value, StageEvaluationResponse)
            if not parse_result.is_success:
                return Result.fail(f"[LLM_VALIDATION_FAILED:{parse_result.fallback}]")

            parsed_eval = parse_result.value
            if parsed_eval is None:
                return Result.fail("[LLM_VALIDATION_FAILED:EMPTY_RESPONSE]")

            weaknesses: list[str] = []
            raw_value = llm_result.value
            if isinstance(raw_value, str):
                try:
                    raw_dict = json.loads(raw_value)
                    raw_weaknesses = raw_dict.get("weaknesses", []) if isinstance(raw_dict, dict) else []
                    weaknesses = raw_weaknesses if isinstance(raw_weaknesses, list) else []
                except json.JSONDecodeError:
                    weaknesses = []
            elif isinstance(raw_value, dict):
                raw_weaknesses = raw_value.get("weaknesses", [])
                weaknesses = raw_weaknesses if isinstance(raw_weaknesses, list) else []

            result = StageEvaluationResult(
                stage_number=stage_config.stage_number,
                start_turn=start_turn,
                end_turn=end_turn,
                timestamp=datetime.now(timezone.utc),
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
                stage_number=r.stage_number,
                start_turn=r.start_turn,
                end_turn=r.end_turn,
                timestamp=(
                    r.created_at
                    if getattr(r, "created_at", None) is not None
                    else getattr(r, "timestamp", datetime.now(timezone.utc))
                ),
                scores=r.scores or {},
                strengths=r.strengths or [],
                weaknesses=r.weaknesses or [],
                suggestions=r.suggestions or [],
                summary=r.summary or "",
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
            scores=result.scores,
            strengths=result.strengths,
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

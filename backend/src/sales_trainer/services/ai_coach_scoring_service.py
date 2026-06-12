from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from common.ai.llm_service import LLMService
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class AiCoachScoreOutputV1(BaseModel):
    """Validated output schema for AI coach scoring (v1)."""

    score: float = Field(..., ge=0, le=100)
    max_score: float = Field(100, ge=0, le=100)
    feedback: str = Field(..., min_length=1)
    missed_points: list[str] = Field(default_factory=list)
    next_question: str | None = Field(None)
    passed: bool = False
    reasoning: str | None = Field(None)


class AiCoachScoringServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachScoringService:
    """Service for scoring AI coach turns using LLM."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm_service = llm_service or LLMService()

    async def score_turn(
        self,
        *,
        question: str,
        user_answer: str,
        config: dict[str, Any],
        session_id: str,
        previous_turns: list[dict[str, Any]] | None = None,
    ) -> Result[dict[str, Any]]:
        """Score a single turn using LLM.

        Args:
            question: The question asked by the AI coach.
            user_answer: The user's answer.
            config: AI coach config snapshot (contains prompt_template_id, etc.).
            session_id: Session ID for cost tracking.
            previous_turns: Optional list of previous turns for context.

        Returns:
            Result with parsed scoring output dict or fallback message.
        """
        if not self._llm_service.is_configured:
            return Result.fail("[LLM_NOT_CONFIGURED]")

        system_message = self._build_system_message(config)
        prompt = self._build_scoring_prompt(
            question=question,
            user_answer=user_answer,
            config=config,
            previous_turns=previous_turns,
        )

        try:
            result = await self._llm_service.generate(
                prompt=prompt,
                session_id=session_id,
                system_message=system_message,
                allow_fallback_response=False,
            )
        except Exception as exc:
            logger.error(
                "ai_coach_llm_generation_failed",
                session_id=session_id,
                error=str(exc),
            )
            return Result.fail("[AI_COACH_LLM_GENERATION_FAILED]")

        if not result.is_success or not result.value:
            logger.warning(
                "ai_coach_scoring_llm_failed",
                session_id=session_id,
                fallback=result.fallback,
            )
            return Result.fail(result.fallback or "[AI_COACH_SCORING_FAILED]")

        raw_output = self._extract_json(str(result.value))
        if raw_output is None:
            logger.warning(
                "ai_coach_scoring_invalid_json",
                session_id=session_id,
                raw_value=str(result.value)[:500],
            )
            return Result.fail("[AI_COACH_SCORING_RESPONSE_INVALID]")

        validated = self.validate_output(
            raw_output,
            schema_version=config.get("output_schema_version", "v1"),
        )
        if not validated.is_success:
            logger.warning(
                "ai_coach_scoring_validation_failed",
                session_id=session_id,
                fallback=validated.fallback,
            )
            return Result.fail(
                validated.fallback or "[AI_COACH_SCORING_VALIDATION_FAILED]"
            )

        output = validated.value
        if output is None:
            return Result.fail("[AI_COACH_SCORING_VALIDATION_EMPTY]")

        return Result.ok(
            {
                "score": output.score,
                "max_score": output.max_score,
                "feedback": output.feedback,
                "missed_points": output.missed_points,
                "next_question": output.next_question,
                "passed": output.passed,
                "reasoning": output.reasoning,
                "raw_model_output": raw_output,
            }
        )

    def validate_output(
        self,
        raw_output: dict[str, Any],
        schema_version: str,
    ) -> Result[AiCoachScoreOutputV1]:
        """Validate raw LLM output against the specified schema version.

        Args:
            raw_output: Parsed JSON dict from LLM response.
            schema_version: Schema version string (e.g., "v1").

        Returns:
            Result with validated output model or fallback message.
        """
        if schema_version == "v1":
            try:
                validated = AiCoachScoreOutputV1.model_validate(raw_output)
                return Result.ok(validated)
            except ValidationError as exc:
                logger.warning(
                    "ai_coach_output_validation_failed",
                    schema_version=schema_version,
                    errors=str(exc),
                )
                return Result.fail("[AI_COACH_OUTPUT_VALIDATION_FAILED]")
        return Result.fail(f"[AI_COACH_UNKNOWN_SCHEMA_VERSION:{schema_version}]")

    def _build_system_message(self, config: dict[str, Any]) -> str:
        """Build system message from config."""
        default_system = (
            "你是一位专业的销售培训 AI 教练。你的任务是根据学员的回答进行评分和反馈，"
            "并决定下一道问题。评分标准：0-100 分，80 分以上视为掌握。"
            "输出必须是 JSON 格式，包含以下字段："
            "score(数字), max_score(数字, 默认100), feedback(字符串), "
            "missed_points(字符串数组), next_question(字符串或null), passed(布尔值), reasoning(字符串或null)。"
        )
        return str(config.get("system_prompt") or default_system)

    def _build_scoring_prompt(
        self,
        *,
        question: str,
        user_answer: str,
        config: dict[str, Any],
        previous_turns: list[dict[str, Any]] | None,
    ) -> str:
        """Build the scoring prompt for the LLM."""
        prompt_parts = [
            f"问题：{question}",
            f"学员回答：{user_answer}",
        ]

        if previous_turns:
            prompt_parts.append("\n之前的对话记录：")
            for turn in previous_turns[-5:]:  # Include last 5 turns for context
                prompt_parts.append(f"  问题：{turn.get('question', '')}")
                prompt_parts.append(f"  回答：{turn.get('user_answer', '')}")

        mastery_threshold = config.get("mastery_threshold", 80.0)
        prompt_parts.append(f"\n掌握阈值：{mastery_threshold}分（达到或超过视为掌握）")

        article_snapshot = config.get("article_snapshot")
        if article_snapshot and isinstance(article_snapshot, dict):
            article_title = article_snapshot.get("title", "")
            if article_title:
                prompt_parts.append(f"\n学习文章标题：{article_title}")
            chapters = article_snapshot.get("chapters", [])
            if chapters and isinstance(chapters, list):
                prompt_parts.append("\n学习文章章节要点：")
                for chapter in chapters[:3]:
                    if isinstance(chapter, dict):
                        prompt_parts.append(f"  - {chapter.get('title', '')}")

        prompt_parts.append(
            "\n请根据以上信息，对学员的回答进行评分和反馈。输出必须是有效的 JSON 格式。"
        )

        return "\n".join(prompt_parts)

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON object from text, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence
            lines = text.split("\n", 1)
            if len(lines) > 1:
                text = lines[1]
            else:
                text = text[3:]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3].strip()
            # Remove language identifier if present
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
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

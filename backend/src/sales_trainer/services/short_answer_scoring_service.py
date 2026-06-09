from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from common.ai.config_manager import get_config_manager
from common.ai.llm_service import LLMService
from common.ai.models import ModelConfig, ModelType
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from sales_trainer.rules import (
    DEFAULT_SHORT_ANSWER_PASS_THRESHOLD,
    DEFAULT_SHORT_ANSWER_PROMPT_TEMPLATE,
    DEFAULT_SHORT_ANSWER_SYSTEM_PROMPT,
    normalize_short_answer_ai_config,
)

logger = get_logger(__name__)


class ShortAnswerQuestion(Protocol):
    @property
    def question_id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def stem(self) -> str: ...

    @property
    def reference_answer(self) -> str | None: ...

    @property
    def scoring_criteria(self) -> dict[str, Any]: ...

    @property
    def scoring_dimensions(self) -> list[str] | None: ...


@dataclass(frozen=True)
class ShortAnswerScoreOutcome:
    score: float
    passed: bool
    feedback: str
    reason: str | None
    raw_response: dict[str, Any] | None


class ShortAnswerScoringService:
    def __init__(
        self,
        *,
        llm_service: LLMService | None = None,
        llm_service_factory: Any | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._llm_service_factory = llm_service_factory or LLMService

    async def score(
        self,
        question: ShortAnswerQuestion,
        *,
        answer_text: str,
    ) -> Result[ShortAnswerScoreOutcome]:
        answer = answer_text.strip()
        if not answer:
            return Result.ok(
                ShortAnswerScoreOutcome(
                    score=0,
                    passed=False,
                    feedback="未作答，无法评分。",
                    reason="empty_answer",
                    raw_response={"score": 0, "reason": "empty_answer"},
                )
            )

        criteria = question.scoring_criteria or {}
        ai_config = normalize_short_answer_ai_config(criteria.get("ai_scoring"))
        if ai_config.get("enabled") is False:
            return Result.fail("[SHORT_ANSWER_AI_SCORING_DISABLED]")

        service = self._resolve_llm_service(ai_config)
        prompt = _render_prompt(question, answer=answer, ai_config=ai_config)
        result = await service.generate(
            prompt=prompt,
            session_id=f"sales_trainer_short_answer:{question.question_id}",
            system_message=str(
                ai_config.get("system_prompt") or DEFAULT_SHORT_ANSWER_SYSTEM_PROMPT
            ),
            allow_fallback_response=False,
        )
        if not result.is_success or not result.value:
            logger.warning(
                "sales_trainer_short_answer_scoring_failed",
                question_id=str(question.question_id),
                fallback=result.fallback,
            )
            return Result.fail(result.fallback or "[SHORT_ANSWER_AI_SCORING_FAILED]")

        parsed = _parse_score_payload(str(result.value))
        if parsed is None:
            logger.warning(
                "sales_trainer_short_answer_scoring_invalid_json",
                question_id=str(question.question_id),
            )
            return Result.fail("[SHORT_ANSWER_AI_SCORING_RESPONSE_INVALID]")

        score = float(parsed["score"])
        threshold = float(
            ai_config.get("pass_threshold", DEFAULT_SHORT_ANSWER_PASS_THRESHOLD)
        )
        return Result.ok(
            ShortAnswerScoreOutcome(
                score=score,
                passed=score >= threshold,
                feedback=str(parsed["feedback"]),
                reason=parsed.get("reason"),
                raw_response=parsed,
            )
        )

    def _resolve_llm_service(self, ai_config: dict[str, Any]) -> LLMService:
        if self._llm_service is not None:
            return self._llm_service
        model_config = _model_config_from_ai_config(ai_config)
        if model_config is not None:
            return self._llm_service_factory(model_config)
        return self._llm_service_factory()


def _model_config_from_ai_config(ai_config: dict[str, Any]) -> ModelConfig | None:
    manager = get_config_manager()
    config_id = str(ai_config.get("model_config_id") or "").strip()
    base_config = (
        manager.get_config_by_id(config_id)
        if config_id
        else manager.get_default_config(ModelType.LLM)
    )
    if base_config is None:
        return None
    extra_config = dict(base_config.extra_config or {})
    for key in ("temperature", "timeout", "max_retries", "max_tokens"):
        if ai_config.get(key) is not None:
            extra_config[key] = ai_config[key]
    return ModelConfig(
        name=str(base_config.name),
        model_type="llm",
        provider=str(base_config.provider),
        base_url=str(base_config.base_url),
        api_key_encrypted=str(base_config.api_key_encrypted),
        model_name=str(base_config.model_name),
        extra_config=extra_config,
    )


def _render_prompt(
    question: ShortAnswerQuestion,
    *,
    answer: str,
    ai_config: dict[str, Any],
) -> str:
    criteria = question.scoring_criteria or {}
    template = str(
        ai_config.get("prompt_template") or DEFAULT_SHORT_ANSWER_PROMPT_TEMPLATE
    )
    return template.format(
        title=question.title,
        stem=question.stem,
        reference_answer=(question.reference_answer or "").strip(),
        dimensions=json.dumps(question.scoring_dimensions or [], ensure_ascii=False),
        criteria=json.dumps(criteria, ensure_ascii=False),
        answer=answer,
    )


def _parse_score_payload(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_score = payload.get("score")
    if raw_score is None:
        return None
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None
    feedback = payload.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        return None
    normalized: dict[str, Any] = {
        "score": max(0.0, min(100.0, score)),
        "feedback": feedback.strip(),
    }
    reason = payload.get("reason")
    if isinstance(reason, str) and reason.strip():
        normalized["reason"] = reason.strip()
    return normalized

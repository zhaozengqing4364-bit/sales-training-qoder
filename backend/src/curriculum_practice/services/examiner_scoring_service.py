from __future__ import annotations

import json
from typing import Any

from common.ai.llm_service import LLMService
from common.monitoring.logger import get_logger
from curriculum_practice.websocket.examiner_runtime import (
    ExamScorer,
    FrozenExamQuestion,
    _default_scorer,
)

logger = get_logger(__name__)


def _parse_llm_score_payload(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        score = int(payload.get("score", 0))
    except (TypeError, ValueError):
        return None
    feedback = payload.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        return None
    result: dict[str, Any] = {
        "score": max(0, min(100, score)),
        "feedback": feedback.strip(),
    }
    reason = payload.get("reason")
    if isinstance(reason, str) and reason.strip():
        result["reason"] = reason.strip()
    return result


def build_llm_exam_scorer(
    *,
    llm_service: LLMService,
    session_id: str,
) -> ExamScorer:
    async def score(
        *,
        question: FrozenExamQuestion,
        answer_text: str,
    ) -> dict[str, object]:
        answer = answer_text.strip()
        if not answer:
            return {"score": 0, "feedback": "未作答，无法评分", "reason": "EMPTY_ANSWER"}

        criteria = question.scoring_criteria or {}
        prompt = f"""你是售前培训 AI 考官。请根据题干、参考答案和评分标准，对学员答案打分。

题目：{question.title}
题干：{question.stem}
参考答案：{(question.reference_answer or "").strip() or "无"}
评分标准：{json.dumps(criteria, ensure_ascii=False)}
学员答案：{answer}

请严格返回 JSON（不要 markdown 代码块）：
{{"score": <0-100整数>, "feedback": "<50字以内简短点评>", "reason": "<可选，说明扣分或加分依据>"}}"""

        result = await llm_service.generate(
            prompt=prompt,
            session_id=session_id,
            system_message="你是专业的售前知识考核评分官。只输出合法 JSON，score 必须是 0-100 的整数。",
            allow_fallback_response=False,
        )
        if not result.is_success:
            logger.warning(
                "Examiner LLM scoring failed; falling back to keyword scorer",
                session_id=session_id,
                question_id=question.question_id,
                fallback=result.fallback,
            )
            return await _default_scorer(question=question, answer_text=answer_text)

        parsed = _parse_llm_score_payload(result.value or "")
        if parsed is None:
            logger.warning(
                "Examiner LLM scoring returned invalid JSON; falling back to keyword scorer",
                session_id=session_id,
                question_id=question.question_id,
            )
            return await _default_scorer(question=question, answer_text=answer_text)
        return parsed

    return score

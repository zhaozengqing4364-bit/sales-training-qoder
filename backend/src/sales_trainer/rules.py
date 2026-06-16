from __future__ import annotations

from typing import Any

DEFAULT_AUDIO_PASS_THRESHOLD = 70.0
DEFAULT_QUESTION_DIMENSION = "sales_trainer_answer_quality"
DEFAULT_SHORT_ANSWER_PASS_THRESHOLD = 60.0
DEFAULT_QUIZ_PASS_THRESHOLD: float | None = None

DEFAULT_SHORT_ANSWER_SYSTEM_PROMPT = (
    "你是销售训练简答题评分员。只输出合法 JSON，不要输出 markdown。"
)

DEFAULT_SHORT_ANSWER_PROMPT_TEMPLATE = """请根据题干、参考答案和评分维度，对学员答案评分。

题目：{title}
题干：{stem}
参考答案：{reference_answer}
评分维度：{dimensions}
评分标准：{criteria}
学员答案：{answer}

硬性规则：
- 如果学员答案为空、寒暄、玩笑、敷衍、无关、只重复题干，或没有给出任何具体做法，score 必须为 0。
- 如果学员答案没有覆盖参考答案的核心要点，即使语言流畅，也不能给高分。
- feedback 必须指出缺失点，不能只说“答得不错”。

请严格返回 JSON：
{{"score": <0-100数字>, "feedback": "<面向学员的简短反馈>", "reason": "<评分依据>"}}"""


def resolve_audio_pass_threshold(unit_config: dict[str, Any] | None) -> float:
    audio_config = (unit_config or {}).get("audio") or {}
    return float(audio_config.get("pass_threshold", DEFAULT_AUDIO_PASS_THRESHOLD))


def resolve_quiz_pass_threshold(unit_config: dict[str, Any] | None) -> float | None:
    quiz_config = (unit_config or {}).get("quiz") or {}
    raw_threshold = quiz_config.get("pass_threshold", DEFAULT_QUIZ_PASS_THRESHOLD)
    if raw_threshold is None:
        return None
    threshold = float(raw_threshold)
    return threshold if threshold else None


def normalize_short_answer_ai_config(raw_config: object) -> dict[str, Any]:
    config = dict(raw_config) if isinstance(raw_config, dict) else {}
    config.setdefault("enabled", True)
    config.setdefault("pass_threshold", DEFAULT_SHORT_ANSWER_PASS_THRESHOLD)
    return config

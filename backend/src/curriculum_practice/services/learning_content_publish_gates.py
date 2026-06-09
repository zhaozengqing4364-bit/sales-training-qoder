from __future__ import annotations

from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import GateResult, PublishGateDecision


def learning_content_publish_decision(
    content: LearningContent,
    chapters: list[LearningChapter],
) -> PublishGateDecision:
    results: list[GateResult] = []
    if not chapters:
        results.append(
            _gate(
                "chapter_presence",
                "no_chapters",
                "LearningContent requires at least one chapter.",
            )
        )
    if any(not chapter.content.strip() for chapter in chapters):
        results.append(
            _gate(
                "chapter_content",
                "empty_chapter_content",
                "Every chapter must contain content.",
            )
        )
    expected_order = list(range(1, len(chapters) + 1))
    actual_order = [chapter.order_index for chapter in chapters]
    if actual_order != expected_order:
        results.append(
            _gate(
                "chapter_order",
                "non_contiguous_chapter_order",
                "Chapter order must be contiguous from 1.",
            )
        )
    if content.safety_flagged:
        results.append(
            _gate(
                "content_safety",
                "security_flagged_content",
                "Security flagged content cannot be published.",
            )
        )
    return PublishGateDecision(can_publish=not results, results=results)


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )

"""Unit tests for presentation feedback policy rule overrides."""

from __future__ import annotations

from presentation_coach.services.aho_matcher import ForbiddenWordMatch
from presentation_coach.services.feedback_service import (
    PresentationFeedbackRuleConfig,
    PresentationFeedbackService,
)
from presentation_coach.services.semantic_point_tracker import (
    FeedbackDeduplicator,
    PointCoverageResult,
)


def _point(point_id: str, content: str, covered: bool) -> PointCoverageResult:
    return PointCoverageResult(
        point_id=point_id,
        point_content=content,
        is_covered=covered,
        confidence=1.0 if covered else 0.0,
    )


def test_regular_forbidden_interrupt_can_be_disabled() -> None:
    service = PresentationFeedbackService()
    dedup = FeedbackDeduplicator(cooldown_seconds=0)
    cfg = PresentationFeedbackRuleConfig(
        allow_critical_forbidden_interrupt=True,
        allow_regular_forbidden_interrupt=False,
    )

    should_interrupt, reason, message = service._determine_interruption(
        point_results=[_point("point_1", "痛点", True)],
        forbidden_matches=[
            ForbiddenWordMatch(
                word="大概",
                position=0,
                matched_text="大概",
                suggestion="建议给出明确数据",
                severity="warning",
            )
        ],
        dedup=dedup,
        rule_config=cfg,
    )

    assert should_interrupt is False
    assert reason == ""
    assert message == ""


def test_critical_forbidden_interrupt_has_priority() -> None:
    service = PresentationFeedbackService()
    dedup = FeedbackDeduplicator(cooldown_seconds=0)
    cfg = PresentationFeedbackRuleConfig(
        allow_critical_forbidden_interrupt=True,
        allow_regular_forbidden_interrupt=True,
    )

    should_interrupt, reason, message = service._determine_interruption(
        point_results=[_point("point_1", "痛点", True)],
        forbidden_matches=[
            ForbiddenWordMatch(
                word="保证100%",
                position=0,
                matched_text="保证100%",
                suggestion="请给出客观条件",
                severity="critical",
            )
        ],
        dedup=dedup,
        rule_config=cfg,
    )

    assert should_interrupt is True
    assert reason == "forbidden_word"
    assert "保证100%" in message


def test_missing_points_interrupt_threshold_is_configurable() -> None:
    service = PresentationFeedbackService()
    dedup = FeedbackDeduplicator(cooldown_seconds=0)
    cfg = PresentationFeedbackRuleConfig(
        missing_points_interrupt_ratio_threshold=0.6,
        missing_points_min_count=2,
        missing_points_preview_count=1,
        allow_critical_forbidden_interrupt=False,
        allow_regular_forbidden_interrupt=False,
    )

    should_interrupt, reason, message = service._determine_interruption(
        point_results=[
            _point("point_1", "痛点", True),
            _point("point_2", "价值", False),
            _point("point_3", "证据", False),
        ],
        forbidden_matches=[],
        dedup=dedup,
        rule_config=cfg,
    )

    assert should_interrupt is True
    assert reason == "missing_point"
    assert "价值" in message

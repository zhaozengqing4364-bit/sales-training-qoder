"""Unit tests for presentation feedback policy rule overrides."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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


def test_cleanup_expired_sessions_clears_all_session_maps() -> None:
    service = PresentationFeedbackService(session_ttl_seconds=60, max_sessions=10)
    now = datetime.now(UTC)
    service._trackers["old-session"] = object()
    service._deduplicators["old-session"] = object()
    service._forbidden_matchers["old-session"] = object()
    service._rule_configs["old-session"] = PresentationFeedbackRuleConfig()
    service._page_contexts["old-session"] = {"page_number": 1}
    service._last_accessed_at["old-session"] = now - timedelta(seconds=61)

    expired = service.cleanup_expired_sessions(now=now)

    assert expired == ["old-session"]
    assert "old-session" not in service._trackers
    assert "old-session" not in service._deduplicators
    assert "old-session" not in service._forbidden_matchers
    assert "old-session" not in service._rule_configs
    assert "old-session" not in service._page_contexts
    assert "old-session" not in service._last_accessed_at


def test_enforce_session_limit_evicts_oldest_session_state() -> None:
    service = PresentationFeedbackService(session_ttl_seconds=3600, max_sessions=2)
    now = datetime.now(UTC)
    for index, session_id in enumerate(("oldest", "middle", "newest")):
        service._trackers[session_id] = object()
        service._page_contexts[session_id] = {"page_number": index + 1}
        service._last_accessed_at[session_id] = now + timedelta(seconds=index)

    evicted = service._enforce_session_limit()

    assert evicted == ["oldest"]
    assert "oldest" not in service._trackers
    assert "oldest" not in service._page_contexts
    assert set(service._last_accessed_at) == {"middle", "newest"}

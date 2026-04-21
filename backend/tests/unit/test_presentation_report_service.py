from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.session_evidence import SessionEvidenceService
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


@pytest.fixture
def presentation_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_build_presentation_review_groups_page_and_point_level_issues(
    presentation_db_session: AsyncSession,
) -> None:
    session_id = str(uuid4())
    practice_session = SimpleNamespace(
        session_id=session_id,
        presentation_id="ppt-issue-001",
        start_time=datetime(2026, 3, 1, tzinfo=UTC),
        end_time=datetime(2026, 3, 1, 0, 12, tzinfo=UTC),
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
    )
    user_messages = [
        SimpleNamespace(
            content=(
                "这一页先讲客户痛点，但我先展开实施计划和里程碑，"
                "我们百分之百保证两周就能上线。"
            ),
            role="user",
            turn_number=1,
            timestamp=datetime(2026, 3, 1, 0, 1, tzinfo=UTC),
            transcript_metadata={"page_number": 1},
        ),
        SimpleNamespace(
            content=(
                "实施计划会分成需求确认、联调、验收三个环节。"
                "为了让大家放心，我把实施计划的里程碑、联调方式、验收节奏、"
                "培训安排、上线窗口再完整讲一遍，这样大家会更清楚。"
            ),
            role="user",
            turn_number=2,
            timestamp=datetime(2026, 3, 1, 0, 2, tzinfo=UTC),
            transcript_metadata={"page_number": 2},
        ),
        SimpleNamespace(
            content="大家还有问题吗？如果追问负责人是谁，我这边暂时只能说后面再确认。",
            role="user",
            turn_number=3,
            timestamp=datetime(2026, 3, 1, 0, 3, tzinfo=UTC),
            transcript_metadata={"page_number": 2},
        ),
    ]
    interruption_events = [
        SimpleNamespace(
            interruption_type="forbidden_word",
            trigger_content="百分之百保证",
        ),
        SimpleNamespace(
            interruption_type="missing_point",
            trigger_content="实施计划会分成需求确认、联调、验收三个环节。",
        ),
        SimpleNamespace(
            interruption_type="vague_response",
            trigger_content="大家还有问题吗？如果追问负责人是谁，我这边暂时只能说后面再确认。",
        ),
    ]
    pages = [
        SimpleNamespace(page_id="page-1", page_number=1),
        SimpleNamespace(page_id="page-2", page_number=2),
    ]
    required_points = [
        SimpleNamespace(page_id="page-1", description="客户痛点"),
        SimpleNamespace(page_id="page-2", description="实施计划"),
        SimpleNamespace(page_id="page-2", description="负责人安排"),
    ]
    forbidden_words = [
        SimpleNamespace(page_id="page-1", presentation_id=None, phrase="百分之百保证"),
        SimpleNamespace(page_id=None, presentation_id="ppt-issue-001", phrase="零风险"),
    ]
    presentation_db_session.execute.side_effect = [
        _ScalarResult(practice_session),
        _ScalarsResult(user_messages),
        _ScalarsResult(interruption_events),
        _ScalarsResult(pages),
        _ScalarsResult(required_points),
        _ScalarsResult(forbidden_words),
    ]

    service = PresentationReportService(presentation_db_session)

    result = await service.build_presentation_review(session_id)

    assert result.is_success
    review = result.value
    assert review["diagnostics"]["page_issue_cluster_count"] == 5
    assert review["diagnostics"]["page_issue_types"] == [
        "forbidden_word",
        "missing_point",
        "off_page",
        "overlong_explanation",
        "weak_qa_handling",
    ]

    page_1_summary = review["page_summaries"][0]
    page_1_issue_types = {
        issue["issue_type"] for issue in page_1_summary["issue_clusters"]
    }
    assert page_1_issue_types == {"off_page", "forbidden_word"}

    off_page_issue = next(
        issue
        for issue in page_1_summary["issue_clusters"]
        if issue["issue_type"] == "off_page"
    )
    assert off_page_issue["related_page_numbers"] == [2]
    assert off_page_issue["linked_points"] == ["实施计划"]
    assert off_page_issue["turn_numbers"] == [1]

    forbidden_issue = next(
        issue
        for issue in page_1_summary["issue_clusters"]
        if issue["issue_type"] == "forbidden_word"
    )
    assert forbidden_issue["linked_phrases"] == ["百分之百保证"]
    assert forbidden_issue["turn_numbers"] == [1]

    page_2_summary = review["page_summaries"][1]
    page_2_issue_types = {
        issue["issue_type"] for issue in page_2_summary["issue_clusters"]
    }
    assert page_2_issue_types == {
        "missing_point",
        "overlong_explanation",
        "weak_qa_handling",
    }

    missing_point_issue = next(
        issue
        for issue in page_2_summary["issue_clusters"]
        if issue["issue_type"] == "missing_point"
    )
    assert missing_point_issue["linked_points"] == ["负责人安排"]
    assert missing_point_issue["turn_numbers"] == [2, 3]

    overlong_issue = next(
        issue
        for issue in page_2_summary["issue_clusters"]
        if issue["issue_type"] == "overlong_explanation"
    )
    assert overlong_issue["turn_numbers"] == [2]
    assert overlong_issue["summary"]

    weak_qa_issue = next(
        issue
        for issue in page_2_summary["issue_clusters"]
        if issue["issue_type"] == "weak_qa_handling"
    )
    assert weak_qa_issue["turn_numbers"] == [3]
    assert weak_qa_issue["evidence"] == [
        "大家还有问题吗？如果追问负责人是谁，我这边暂时只能说后面再确认。"
    ]


def test_presentation_evidence_completeness_counts_page_issue_clusters() -> None:
    completeness = SessionEvidenceService._build_presentation_evidence_completeness(
        messages=[
            {"turn_number": 1, "transcript_metadata": {"page_number": 1}},
            {"turn_number": 2, "transcript_metadata": {"page_number": 2}},
        ],
        review={
            "page_summaries": [
                {
                    "page_number": 1,
                    "issue_clusters": [
                        {"issue_type": "off_page"},
                        {"issue_type": "forbidden_word"},
                    ],
                },
                {
                    "page_number": 2,
                    "issue_clusters": [
                        {"issue_type": "missing_point"},
                        {"issue_type": "overlong_explanation"},
                        {"issue_type": "weak_qa_handling"},
                    ],
                },
            ],
            "required_talking_points": {
                "status": "complete",
                "total": 3,
                "covered": 2,
                "missing": 1,
                "coverage_ratio": 2 / 3,
            },
            "diagnostics": {
                "has_page_metadata": True,
                "pages_with_messages": 2,
                "total_pages": 2,
                "page_coverage_ratio": 1.0,
                "required_points_total": 3,
                "required_points_covered": 2,
                "required_points_missing": 1,
                "required_coverage_ratio": 2 / 3,
                "degraded_reasons": [],
            },
        },
    )

    assert completeness["complete"] is True
    assert completeness["page_issue_cluster_count"] == 5
    assert completeness["page_issue_types"] == [
        "forbidden_word",
        "missing_point",
        "off_page",
        "overlong_explanation",
        "weak_qa_handling",
    ]

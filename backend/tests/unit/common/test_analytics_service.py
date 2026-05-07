from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.analytics_service import AnalyticsService
from common.db.models import (
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
    User,
)


@pytest.mark.asyncio
async def test_common_gaps_uses_page_backed_talking_point_description(
    test_db: AsyncSession,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"analytics_common_gaps_{uuid.uuid4().hex[:8]}",
        name="Analytics Common Gaps User",
        email=f"analytics-common-gaps-{uuid.uuid4().hex[:8]}@example.com",
        role="user",
        is_active=True,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="Presentation common gaps",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Quarterly sales deck",
        file_url="https://example.test/quarterly-sales.pptx",
        status="ready",
        total_pages=1,
    )
    page = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="ROI proof",
    )
    talking_point = RequiredTalkingPoint(
        point_id=str(uuid.uuid4()),
        page_id=page.page_id,
        description="Quantified ROI evidence",
        created_by="admin",
        confirmed_by_admin=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        presentation_id=presentation.presentation_id,
        status="completed",
    )

    test_db.add_all([user, scenario, presentation, page, talking_point, session])
    await test_db.commit()

    result = await AnalyticsService().get_common_gaps(
        test_db,
        scenario_type="presentation",
    )

    assert result.is_success
    assert result.value is not None
    assert [gap.point_text for gap in result.value] == ["Quantified ROI evidence"]

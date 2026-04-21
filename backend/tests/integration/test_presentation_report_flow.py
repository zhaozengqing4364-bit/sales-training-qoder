from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import (
    Base,
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
    User,
)
from common.db.session import get_db
from main import app
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def owner(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"presentation-flow-owner-{uuid.uuid4().hex[:8]}",
        name="Presentation Flow Owner",
        email=f"presentation_flow_owner_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_headers(owner: User):
    token = create_access_token(data={"sub": str(owner.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _seed_presentation_session(
    db_session: AsyncSession,
    *,
    owner: User,
    missing_page_metadata: bool,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="presentation shared report flow",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="演讲复盘 API 集成测试",
        file_url="file:///tmp/presentation-flow.pptx",
        status="ready",
        version_number=5,
        total_pages=2,
        ocr_progress=1.0,
    )
    page_1 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="第一页业务目标与客户问题",
    )
    page_2 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=2,
        ocr_extracted_text="第二页ROI结果与客户案例",
    )
    talking_points = [
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_1.page_id,
            description="业务目标",
            created_by="admin",
            confirmed_by_admin=True,
        ),
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_2.page_id,
            description="ROI结果",
            created_by="admin",
            confirmed_by_admin=True,
        ),
    ]
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        presentation_id=presentation.presentation_id,
        status="completed",
        start_time=datetime.now(UTC) - timedelta(minutes=14),
        end_time=datetime.now(UTC),
        total_duration_seconds=14 * 60,
    )

    first_page_metadata = None if missing_page_metadata else {"page_number": 1}
    second_page_metadata = None if missing_page_metadata else {"page_number": 2}
    messages = [
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="第一页先讲业务目标。",
            timestamp=datetime.now(UTC) - timedelta(minutes=13),
            duration_ms=102_000,
            transcript_metadata=first_page_metadata,
            score_snapshot={"overall_score": 86},
        ),
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=2,
            role="user",
            content=(
                "第二页给出 ROI 结果，并补上一个客户案例。"
                if not missing_page_metadata
                else "第二页继续补业务目标，但没有说明 ROI 结果。"
            ),
            timestamp=datetime.now(UTC) - timedelta(minutes=10),
            duration_ms=115_000,
            transcript_metadata=second_page_metadata,
            score_snapshot={"overall_score": 90},
        ),
    ]

    db_session.add_all([scenario, presentation, page_1, page_2, session, *talking_points, *messages])
    await db_session.commit()
    return session


def _dimension_score(review: dict[str, object], name: str) -> float:
    for item in review["dimension_scores"]:  # type: ignore[index]
        if item["name"] == name:  # type: ignore[index]
            return float(item["score"])  # type: ignore[index]
    raise AssertionError(f"Missing dimension score for {name}")


@pytest.mark.asyncio
async def test_shared_report_route_uses_canonical_presentation_review_builder(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    session = await _seed_presentation_session(
        db_session,
        owner=owner,
        missing_page_metadata=False,
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()["data"]

    review_result = await PresentationReportService(db_session).build_presentation_review(
        session.session_id,
    )
    assert review_result.is_success is True
    review = review_result.value

    assert payload["scenario_type"] == "presentation"
    assert payload["presentation_review"] == review
    assert payload["overall_score"] == pytest.approx(review["overall_score"])
    assert payload["logic_score"] == pytest.approx(_dimension_score(review, "流畅连贯性"))
    assert payload["accuracy_score"] == pytest.approx(_dimension_score(review, "准确性"))
    assert payload["completeness_score"] == pytest.approx(
        (
            _dimension_score(review, "专业性")
            + _dimension_score(review, "生动性")
            + _dimension_score(review, "互动问答")
            + _dimension_score(review, "其他表现")
        )
        / 4,
        abs=0.05,
    )


@pytest.mark.asyncio
async def test_shared_report_route_returns_degraded_presentation_payload_without_page_metadata(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    session = await _seed_presentation_session(
        db_session,
        owner=owner,
        missing_page_metadata=True,
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()["data"]

    review_result = await PresentationReportService(db_session).build_presentation_review(
        session.session_id,
    )
    assert review_result.is_success is True
    review = review_result.value

    assert payload["scenario_type"] == "presentation"
    assert payload["presentation_review"] == review
    assert payload["presentation_review"]["required_talking_points"]["status"] == "degraded"
    assert payload["presentation_review"]["page_summaries"] == []
    assert payload["presentation_review"]["diagnostics"]["degraded_reasons"] == [
        "missing_page_metadata",
    ]
    assert payload["evidence_completeness"]["scenario_type"] == "presentation"
    assert payload["evidence_completeness"]["page_metadata_complete"] is False
    assert payload["evidence_completeness"]["required_talking_points_status"] == "degraded"
    assert payload["evidence_completeness"]["degraded_reasons"] == [
        "missing_page_metadata",
    ]

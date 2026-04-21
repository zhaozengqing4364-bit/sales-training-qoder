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
        wechat_user_id=f"presentation-contract-owner-{uuid.uuid4().hex[:8]}",
        name="Presentation Contract Owner",
        email=f"presentation_contract_owner_{uuid.uuid4().hex[:6]}@example.com",
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
) -> tuple[PracticeSession, Presentation]:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="presentation shared report contract",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="AI 演讲复盘合同测试",
        file_url="file:///tmp/presentation-contract.pptx",
        status="ready",
        version_number=3,
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
            page_id=page_1.page_id,
            description="客户问题",
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
        start_time=datetime.now(UTC) - timedelta(minutes=12),
        end_time=datetime.now(UTC),
        total_duration_seconds=12 * 60,
        audio_url="https://example.com/presentation.mp3",
        transcript_url="https://example.com/presentation.txt",
    )

    message_metadata_1 = None if missing_page_metadata else {"page_number": 1}
    message_metadata_2 = None if missing_page_metadata else {"page_number": 2}
    messages = [
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="第一页先讲业务目标和客户问题。",
            timestamp=datetime.now(UTC) - timedelta(minutes=11),
            duration_ms=95_000,
            transcript_metadata=message_metadata_1,
            score_snapshot={"overall_score": 84},
        ),
        ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session.session_id,
            turn_number=2,
            role="user",
            content=(
                "第二页补充 ROI 结果和同类客户案例。"
                if not missing_page_metadata
                else "第二页只补充业务目标，没有补上回报数据。"
            ),
            timestamp=datetime.now(UTC) - timedelta(minutes=9),
            duration_ms=110_000,
            transcript_metadata=message_metadata_2,
            score_snapshot={"overall_score": 88},
        ),
    ]

    db_session.add_all([scenario, presentation, page_1, page_2, session, *talking_points, *messages])
    await db_session.commit()
    return session, presentation


@pytest.mark.asyncio
async def test_shared_report_contract_exposes_presentation_baseline_happy_path(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    session, presentation = await _seed_presentation_session(
        db_session,
        owner=owner,
        missing_page_metadata=False,
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]

    assert data["session_id"] == session.session_id
    assert data["scenario_type"] == "presentation"
    assert data["retry_entry"] == {
        "scenario_type": "presentation",
        "agent_id": None,
        "persona_id": None,
        "presentation_id": presentation.presentation_id,
    }

    review = data["presentation_review"]
    assert review["overall_score"] > 0
    assert [item["name"] for item in review["dimension_scores"]] == [
        "流畅连贯性",
        "准确性",
        "专业性",
        "生动性",
        "互动问答",
        "其他表现",
    ]
    assert [item["page_number"] for item in review["page_summaries"]] == [1, 2]
    assert review["required_talking_points"] == {
        "status": "complete",
        "total": 3,
        "covered": 3,
        "missing": 0,
        "coverage_ratio": 1.0,
    }
    assert review["diagnostics"]["has_page_metadata"] is True
    assert review["diagnostics"]["degraded_reasons"] == []

    assert data["pass_flags"] is None
    assert data["main_issue"] is None
    assert data["next_goal"] is None
    assert data["overall_result"] is None
    assert data["evaluable"] is None
    assert data["not_evaluable_reason"] is None


@pytest.mark.asyncio
async def test_shared_report_contract_keeps_presentation_shape_when_page_metadata_is_missing(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    session, presentation = await _seed_presentation_session(
        db_session,
        owner=owner,
        missing_page_metadata=True,
    )

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]

    assert data["scenario_type"] == "presentation"
    assert data["retry_entry"] == {
        "scenario_type": "presentation",
        "agent_id": None,
        "persona_id": None,
        "presentation_id": presentation.presentation_id,
    }

    review = data["presentation_review"]
    assert review["page_summaries"] == []
    assert review["required_talking_points"]["status"] == "degraded"
    assert review["required_talking_points"]["total"] == 3
    assert review["required_talking_points"]["covered"] == 2
    assert review["required_talking_points"]["missing"] == 1
    assert review["diagnostics"]["has_page_metadata"] is False
    assert review["diagnostics"]["degraded_reasons"] == ["missing_page_metadata"]

    assert data["pass_flags"] is None
    assert data["main_issue"] is None
    assert data["next_goal"] is None
    assert data["overall_result"] is None
    assert data["evaluable"] is None
    assert data["not_evaluable_reason"] is None

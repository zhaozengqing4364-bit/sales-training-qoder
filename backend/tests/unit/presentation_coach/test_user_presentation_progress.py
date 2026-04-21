import pytest

from common.db.models import Presentation, User
from presentation_coach.services.user_presentation_progress import (
    UserPresentationProgressService,
)


@pytest.mark.asyncio
async def test_user_presentation_progress_saves_current_users_last_page(test_db):
    user = User(wechat_user_id="ppt-progress-user", name="PPT Progress User")
    presentation = Presentation(
        title="标准演示",
        file_url="/tmp/deck.pptx",
        status="ready",
        total_pages=12,
    )
    test_db.add_all([user, presentation])
    await test_db.flush()

    result = await UserPresentationProgressService().save_progress(
        db=test_db,
        user_id=str(user.user_id),
        presentation_id=str(presentation.presentation_id),
        last_page_number=5,
        session_id="session-ppt-1",
    )

    assert result.is_success
    payload = result.value
    assert payload["last_page_number"] == 5
    assert payload["presentation_id"] == str(presentation.presentation_id)
    assert payload["user_id"] == str(user.user_id)
    assert payload["source"] == "user_presentation_progress"

    loaded = await UserPresentationProgressService().get_progress(
        db=test_db,
        user_id=str(user.user_id),
        presentation_id=str(presentation.presentation_id),
    )
    assert loaded.is_success
    assert loaded.value["last_page_number"] == 5


@pytest.mark.asyncio
async def test_user_presentation_progress_is_isolated_by_user(test_db):
    owner = User(wechat_user_id="ppt-owner", name="Owner")
    other = User(wechat_user_id="ppt-other", name="Other")
    presentation = Presentation(
        title="标准演示",
        file_url="/tmp/deck.pptx",
        status="ready",
        total_pages=12,
    )
    test_db.add_all([owner, other, presentation])
    await test_db.flush()

    await UserPresentationProgressService().save_progress(
        db=test_db,
        user_id=str(owner.user_id),
        presentation_id=str(presentation.presentation_id),
        last_page_number=7,
    )

    loaded = await UserPresentationProgressService().get_progress(
        db=test_db,
        user_id=str(other.user_id),
        presentation_id=str(presentation.presentation_id),
    )

    assert loaded.is_success
    assert loaded.value is None


@pytest.mark.asyncio
async def test_user_presentation_progress_rejects_invalid_page(test_db):
    user = User(wechat_user_id="ppt-invalid", name="PPT Invalid")
    presentation = Presentation(
        title="标准演示",
        file_url="/tmp/deck.pptx",
        status="ready",
        total_pages=8,
    )
    test_db.add_all([user, presentation])
    await test_db.flush()

    result = await UserPresentationProgressService().save_progress(
        db=test_db,
        user_id=str(user.user_id),
        presentation_id=str(presentation.presentation_id),
        last_page_number=99,
    )

    assert not result.is_success
    assert "[INVALID_PRESENTATION_PAGE]" in result.fallback

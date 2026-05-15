from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import LearningChapter, LearningContent, LearningProgress

async def _create_published_content(
    db: AsyncSession,
    *,
    status: str = "published",
) -> tuple[LearningContent, list[LearningChapter]]:
    content = LearningContent(
        title="售前试点学习讲义",
        summary="完成后进入考试",
        owner="training-ops",
        source="issue-68",
        status=status,
        safety_flagged=False,
        version=1,
        content_hash="sha256:test",
    )
    db.add(content)
    await db.flush()
    chapters = [
        LearningChapter(
            learning_content_id=content.learning_content_id,
            title="第一章：建立信任",
            content="开场破冰与信任建立。",
            order_index=1,
        ),
        LearningChapter(
            learning_content_id=content.learning_content_id,
            title="第二章：需求澄清",
            content="挖掘客户真实需求。",
            order_index=2,
        ),
    ]
    db.add_all(chapters)
    await db.commit()
    await db.refresh(content)
    for chapter in chapters:
        await db.refresh(chapter)
    return content, chapters


def _headers_for(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_should_fetch_current_user_learning_progress(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    content, chapters = await _create_published_content(test_db)
    test_db.add(
        LearningProgress(
            user_id=str(test_user.user_id),
            learning_content_id=content.learning_content_id,
            chapter_id=chapters[0].chapter_id,
        )
    )
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert data["learning_content_id"] == content.learning_content_id
    assert [chapter["chapter_id"] for chapter in data["chapters"]] == [
        chapter.chapter_id for chapter in chapters
    ]
    assert data["progress"]["total_chapters"] == 2
    assert data["progress"]["completed_count"] == 1
    assert data["progress"]["completed_chapter_ids"] == [chapters[0].chapter_id]
    assert data["progress"]["is_completed"] is False
    assert data["progress"]["state"] == "in_progress"
    assert data["progress"]["primary_cta"] == "continue learning"


@pytest.mark.asyncio
async def test_should_complete_chapter_idempotently_and_report_all_completed(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    content, chapters = await _create_published_content(test_db)

    first_response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}"
        f"/chapters/{chapters[0].chapter_id}/complete",
        headers=auth_headers,
    )
    repeated_response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}"
        f"/chapters/{chapters[0].chapter_id}/complete",
        headers=auth_headers,
    )
    final_response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}"
        f"/chapters/{chapters[1].chapter_id}/complete",
        headers=auth_headers,
    )

    assert first_response.status_code == 200, first_response.json()
    assert repeated_response.status_code == 200, repeated_response.json()
    assert repeated_response.json()["data"]["already_completed"] is True
    assert final_response.status_code == 200, final_response.json()
    progress = final_response.json()["data"]["progress"]
    assert progress["completed_count"] == 2
    assert progress["is_completed"] is True
    assert progress["state"] == "completed"
    assert progress["primary_cta"] == "start exam"

    count_result = await test_db.execute(
        select(func.count()).select_from(LearningProgress).where(
            LearningProgress.user_id == str(test_user.user_id),
            LearningProgress.learning_content_id == content.learning_content_id,
            LearningProgress.chapter_id == chapters[0].chapter_id,
        )
    )
    assert count_result.scalar_one() == 1


@pytest.mark.asyncio
async def test_should_scope_learning_progress_to_current_user(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
    another_user: User,
) -> None:
    content, chapters = await _create_published_content(test_db)
    test_db.add(
        LearningProgress(
            user_id=str(test_user.user_id),
            learning_content_id=content.learning_content_id,
            chapter_id=chapters[0].chapter_id,
        )
    )
    await test_db.commit()

    owner_response = await async_client.get(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}",
        headers=auth_headers,
    )
    other_response = await async_client.get(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}",
        headers=_headers_for(another_user),
    )

    assert owner_response.status_code == 200
    assert owner_response.json()["data"]["progress"]["completed_count"] == 1
    assert other_response.status_code == 200, other_response.json()
    assert other_response.json()["data"]["progress"]["completed_count"] == 0
    assert other_response.json()["data"]["progress"]["completed_chapter_ids"] == []


@pytest.mark.asyncio
async def test_should_reject_unpublished_content_and_foreign_chapter(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    draft_content, draft_chapters = await _create_published_content(test_db, status="draft")
    content, _chapters = await _create_published_content(test_db)

    draft_response = await async_client.get(
        f"/api/v1/curriculum-practice/study/learning-contents/{draft_content.learning_content_id}",
        headers=auth_headers,
    )
    foreign_chapter_response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}"
        f"/chapters/{draft_chapters[0].chapter_id}/complete",
        headers=auth_headers,
    )

    assert draft_response.status_code == 404
    assert draft_response.json()["error"] == "[LEARNING_CONTENT_NOT_FOUND]"
    assert foreign_chapter_response.status_code == 404
    assert foreign_chapter_response.json()["error"] == "[LEARNING_CHAPTER_NOT_FOUND]"

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import LearningChapter, LearningContent


async def _published_learning_content(
    db: AsyncSession,
) -> tuple[LearningContent, LearningChapter]:
    content = LearningContent(
        title="学员讲义契约",
        summary="阅读后开始考试",
        owner="training-ops",
        source="contract-test",
        status="published",
        safety_flagged=False,
        version=1,
        content_hash="sha256:contract",
    )
    db.add(content)
    await db.flush()
    chapter = LearningChapter(
        learning_content_id=content.learning_content_id,
        title="第一章",
        content="阅读内容",
        order_index=1,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(content)
    await db.refresh(chapter)
    return content, chapter


@pytest.mark.asyncio
async def test_study_content_api_contract_returns_chapters_and_current_user_progress(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    content, chapter = await _published_learning_content(test_db)

    response = await async_client.get(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data.keys() >= {
        "learning_content_id",
        "title",
        "summary",
        "chapters",
        "progress",
    }
    assert data["chapters"][0].keys() >= {"chapter_id", "title", "content", "order_index"}
    assert data["chapters"][0]["chapter_id"] == chapter.chapter_id
    assert data["progress"].keys() >= {
        "completed_chapter_ids",
        "completed_count",
        "total_chapters",
        "is_completed",
        "state",
        "primary_cta",
    }
    assert data["progress"]["state"] == "not_started"
    assert data["progress"]["primary_cta"] == "continue learning"


@pytest.mark.asyncio
async def test_complete_chapter_api_contract_returns_idempotency_and_next_cta(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    content, chapter = await _published_learning_content(test_db)

    response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}"
        f"/chapters/{chapter.chapter_id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert data.keys() >= {"chapter_id", "already_completed", "progress"}
    assert data["chapter_id"] == chapter.chapter_id
    assert data["already_completed"] is False
    assert data["progress"]["is_completed"] is True
    assert data["progress"]["state"] == "completed"
    assert data["progress"]["primary_cta"] == "start exam"

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PracticeSession, User
from curriculum_practice.models import (
    ExaminerAgent,
    LearningChapter,
    LearningContent,
    LearningProgress,
    QuestionCategory,
    QuestionItem,
)


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
async def test_should_start_exam_after_all_chapters_completed(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    content, chapters = await _create_published_content(test_db)
    category = QuestionCategory(name="课程考题", order_index=1)
    test_db.add(category)
    await test_db.flush()
    question = QuestionItem(
        category_id=category.category_id,
        title="信任建立考题",
        stem="如何建立客户信任？",
        reference_answer="确认 背景 需求 案例",
        scoring_criteria={"keywords": ["确认", "背景", "需求", "案例"]},
        scoring_dimensions=["coverage"],
        status="published",
        safety_flagged=False,
        version=1,
        content_hash="question-hash",
    )
    test_db.add(question)
    await test_db.flush()
    agent = ExaminerAgent(
        name="课程 AI 考官",
        question_source_ids=[question.question_id],
        learner_level_strategy={"default_level": "beginner", "allowed_levels": ["beginner"]},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="published",
        version=1,
        content_hash="agent-hash",
    )
    test_db.add(agent)
    test_db.add_all(
        LearningProgress(
            user_id=str(test_user.user_id),
            learning_content_id=content.learning_content_id,
            chapter_id=chapter.chapter_id,
        )
        for chapter in chapters
    )
    await test_db.commit()

    response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}/start-exam",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    session = await test_db.get(PracticeSession, data["session_id"])
    assert session is not None
    assert session.user_id == str(test_user.user_id)
    assert session.status == "in_progress"
    assert session.curriculum_snapshot["kind"] == "curriculum_examiner_session"
    assert session.curriculum_snapshot["learning_content_id"] == content.learning_content_id
    assert [asset["asset_type"] for asset in session.curriculum_snapshot["content_assets"]] == [
        "examiner_agent",
        "question_item",
    ]
    assert session.curriculum_snapshot["content_assets"][0]["asset_id"] == agent.examiner_agent_id
    assert session.curriculum_snapshot["content_assets"][1]["asset_id"] == question.question_id


@pytest.mark.asyncio
async def test_should_reject_start_exam_before_learning_completed(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    content, _chapters = await _create_published_content(test_db)

    response = await async_client.post(
        f"/api/v1/curriculum-practice/study/learning-contents/{content.learning_content_id}/start-exam",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[LEARNING_CONTENT_NOT_COMPLETED]"


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

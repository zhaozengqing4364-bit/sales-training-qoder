from __future__ import annotations

import uuid
from typing import TypedDict

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperQuestionBinding,
    ExamPaperUpdate,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
    PaperAttemptCreate,
    PaperRollbackRequest,
    QuizAnswerSubmit,
)
from sales_trainer.services.exam_paper_service import (
    ExamPaperService,
    ExamPaperServiceError,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


class PaperQuestionBindingPayload(TypedDict):
    question_id: str
    question_revision_id: str | None
    question_revision_no: int | None
    question_payload_hash: str | None
    legacy_snapshot_only: bool
    question_snapshot: dict[str, object]


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-paper-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Paper {role}",
        email=f"newcomer-paper-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _question(
    question_id: str,
    *,
    category_id: str,
    title: str,
    correct_answer: str = "A",
) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title=title,
        stem=f"{title} 的正确答案是什么？",
        reference_answer=correct_answer,
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "正确"},
                {"value": "B", "label": "错误"},
            ],
            "correct_answer": correct_answer,
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


@pytest.mark.asyncio
async def test_should_create_publish_and_fetch_paper_with_ordered_questions(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="business-skills-category",
        name="商务技巧",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "business-question-1",
        category_id=category.category_id,
        title="见客户前准备",
    )
    second = _question(
        "business-question-2",
        category_id=category.category_id,
        title="商务礼仪",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-skills-entry",
            title="商务礼仪入门考卷",
            module_key="business_skills",
            pass_threshold=12,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=second.question_id,
                    order_index=2,
                    points=5,
                ),
                ExamPaperQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                ),
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)
    revision = await _latest_paper_revision(test_db, published.paper_id)
    first_binding = _paper_question_binding(revision, index=0)
    second_binding = _paper_question_binding(revision, index=1)

    fetched = await service.get_published_paper(published.paper_id)
    serialized = await service.serialize_paper(fetched)
    serialized_questions = _paper_questions(serialized)

    assert first_binding["question_id"] == first.question_id
    assert first_binding["question_revision_id"] is None
    assert first_binding["question_revision_no"] is None
    assert first_binding["question_payload_hash"] is None
    assert first_binding["legacy_snapshot_only"] is True
    assert first_binding["question_snapshot"]["title"] == "见客户前准备"
    assert second_binding["question_id"] == second.question_id
    assert second_binding["question_revision_id"] is None
    assert second_binding["question_payload_hash"] is None
    assert second_binding["legacy_snapshot_only"] is True
    assert second_binding["question_snapshot"]["title"] == "商务礼仪"
    assert serialized["paper_key"] == "business-skills-entry"
    assert serialized["status"] == "published"
    assert [item["question_id"] for item in serialized_questions] == [
        first.question_id,
        second.question_id,
    ]
    assert [item["points"] for item in serialized_questions] == [10, 5]


@pytest.mark.asyncio
async def test_should_submit_published_paper_attempt_through_quiz_scoring(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-paper-submit-category",
        name="商务技巧提交",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "business-submit-question-1",
        category_id=category.category_id,
        title="客户拜访礼仪",
    )
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-submit-paper",
            title="商务技巧提交考卷",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)

    attempt = await service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published.paper_id,
            answers=[
                QuizAnswerSubmit(question_id=question.question_id, answer_payload="A")
            ],
        ),
        actor=learner,
    )
    serialized = await service.serialize_attempt(attempt)

    assert serialized["paper_id"] == published.paper_id
    assert serialized["paper_title"] == "商务技巧提交考卷"
    assert serialized["status"] == "scored"
    assert serialized["total_score"] == 10
    assert serialized["passed"] is True


@pytest.mark.asyncio
async def test_should_require_article_completion_before_article_exam_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-paper-reading-gate-category",
        name="商务技巧阅读门禁",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "business-reading-gate-question-1",
        category_id=category.category_id,
        title="客户拜访阅读门禁",
    )
    content = LearningContent(
        learning_content_id="business-reading-gate-content",
        title="见客户前商务礼仪",
        summary="阅读完成后才可以考试。",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    chapter = LearningChapter(
        chapter_id="business-reading-gate-chapter-1",
        learning_content_id=content.learning_content_id,
        title="拜访前准备",
        content="先确认客户背景、到访时间和接待安排。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, learner, category, question, content, chapter])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-reading-gate-paper",
            title="商务技巧阅读门禁考卷",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)
    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定商务技巧阅读门禁",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="business_skills",
                    module_type="article_exam",
                    enabled=True,
                    order_index=1,
                    title="商务技巧",
                    target_unit_id=published.unit_id,
                    learning_content_id=content.learning_content_id,
                    exam_paper_id=published.paper_id,
                    completion_rule="passed",
                )
            ],
        ),
        actor=admin,
    )
    await path_service.publish_config(actor=admin, reason="发布阅读门禁路径")
    attempt_payload = PaperAttemptCreate(
        paper_id=published.paper_id,
        answers=[
            QuizAnswerSubmit(question_id=question.question_id, answer_payload="A")
        ],
    )

    with pytest.raises(ExamPaperServiceError) as exc_info:
        await service.submit_paper_attempt(attempt_payload, actor=learner)

    assert exc_info.value.code == "[NEWCOMER_ARTICLE_PROGRESS_REQUIRED]"
    assert exc_info.value.status_code == 403

    complete_result = await LearningProgressService(test_db).complete_chapter(
        user_id=str(learner.user_id),
        content_id=content.learning_content_id,
        chapter_id=chapter.chapter_id,
    )
    assert complete_result.is_success

    attempt = await service.submit_paper_attempt(attempt_payload, actor=learner)
    serialized = await service.serialize_attempt(attempt)
    assert serialized["status"] == "scored"
    assert serialized["passed"] is True


@pytest.mark.asyncio
async def test_should_reject_missing_draft_and_archived_papers(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="business-paper-hidden-category",
        name="商务技巧隐藏",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "business-hidden-question-1",
        category_id=category.category_id,
        title="隐藏考卷题",
    )
    test_db.add_all([admin, category, question])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-hidden-paper",
            title="草稿商务考卷",
            module_key="business_skills",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )

    with pytest.raises(ExamPaperServiceError) as draft_error:
        await service.get_published_paper(paper.paper_id)
    assert draft_error.value.code == "[PAPER_NOT_PUBLISHED]"

    published = await service.publish_paper(paper.paper_id, actor=admin)
    await service.archive_paper(published.paper_id, actor=admin)

    with pytest.raises(ExamPaperServiceError) as archived_error:
        await service.get_published_paper(published.paper_id)
    assert archived_error.value.code == "[PAPER_NOT_PUBLISHED]"

    with pytest.raises(ExamPaperServiceError) as missing_error:
        await service.get_published_paper(str(uuid.uuid4()))
    assert missing_error.value.code == "[PAPER_NOT_FOUND]"


@pytest.mark.asyncio
async def test_should_update_draft_paper_title_and_questions(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="business-paper-update-category",
        name="商务技巧更新",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "business-update-question-1",
        category_id=category.category_id,
        title="原题",
    )
    second = _question(
        "business-update-question-2",
        category_id=category.category_id,
        title="新增题",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-update-paper",
            title="商务技巧草稿考卷",
            module_key="business_skills",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )

    updated = await service.update_paper(
        paper.paper_id,
        ExamPaperUpdate(
            title="商务技巧已编辑草稿",
            module_key="business_skills",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=12,
                ),
                ExamPaperQuestionBinding(
                    question_id=second.question_id,
                    order_index=2,
                    points=12,
                ),
            ],
        ),
        actor=admin,
    )
    serialized = await service.serialize_paper(updated)
    serialized_questions = _paper_questions(serialized)

    assert serialized["title"] == "商务技巧已编辑草稿"
    assert [item["question_id"] for item in serialized_questions] == [
        first.question_id,
        second.question_id,
    ]
    assert [item["points"] for item in serialized_questions] == [12, 12]


@pytest.mark.asyncio
async def test_should_edit_published_paper_as_future_revision_without_polluting_existing_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-paper-revision-category",
        name="商务技巧修订",
        order_index=1,
        usage_scope="sales_trainer",
    )
    old_question = _question(
        "business-revision-question-old",
        category_id=category.category_id,
        title="旧题",
    )
    new_question = _question(
        "business-revision-question-new",
        category_id=category.category_id,
        title="新题",
    )
    test_db.add_all([admin, learner, category, old_question, new_question])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-revision-paper",
            title="商务技巧正式考卷",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=old_question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)
    initial_revision = await _latest_paper_revision(test_db, published.paper_id)
    old_attempt = await service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published.paper_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=old_question.question_id,
                    answer_payload="A",
                )
            ],
        ),
        actor=learner,
    )

    await service.update_paper(
        published.paper_id,
        ExamPaperUpdate(
            title="商务技巧修订待发布",
            pass_threshold=12,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=new_question.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )
    working_revision = await _latest_paper_revision(
        test_db,
        published.paper_id,
        status="working",
    )
    working_binding = _paper_question_binding(working_revision)

    before_republish = await service.serialize_paper(
        await service.get_published_paper(published.paper_id)
    )
    before_republish_question = _first_paper_question(before_republish)
    assert before_republish["title"] == "商务技巧正式考卷"
    assert before_republish_question["question_id"] == old_question.question_id
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert working_binding["question_id"] == new_question.question_id
    assert working_binding["question_revision_id"] is None
    assert working_binding["question_payload_hash"] is None
    assert working_binding["legacy_snapshot_only"] is True
    assert working_binding["question_snapshot"]["title"] == "新题"

    republished = await service.publish_paper(published.paper_id, actor=admin)
    after_republish = await service.serialize_paper(republished)
    serialized_old_attempt = await service.serialize_attempt(old_attempt)
    after_republish_question = _first_paper_question(after_republish)
    old_attempt_answer = _first_attempt_answer(serialized_old_attempt)

    assert after_republish["title"] == "商务技巧修订待发布"
    assert after_republish_question["question_id"] == new_question.question_id
    assert after_republish_question["points"] == 12
    assert old_attempt_answer["question_title"] == "旧题"
    assert old_attempt_answer["score"] == 10
    assert serialized_old_attempt["paper_id"] == published.paper_id
    assert serialized_old_attempt["paper_title"] == "商务技巧正式考卷"


@pytest.mark.asyncio
async def test_should_rollback_paper_revision_for_future_attempts_only(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="business-paper-rollback-category",
        name="商务技巧回滚",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "business-rollback-question-first",
        category_id=category.category_id,
        title="第一版题",
    )
    second = _question(
        "business-rollback-question-second",
        category_id=category.category_id,
        title="第二版题",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-rollback-paper",
            title="商务技巧第一版",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)
    initial_revision = await _latest_paper_revision(test_db, published.paper_id)

    await service.update_paper(
        published.paper_id,
        ExamPaperUpdate(
            title="商务技巧第二版",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_paper(published.paper_id, actor=admin)

    rolled_back = await service.rollback_paper(
        published.paper_id,
        PaperRollbackRequest(
            target_revision_id=initial_revision.revision_id,
            reason="恢复第一版题目",
        ),
        actor=admin,
    )
    serialized = await service.serialize_paper(rolled_back)
    first_question = _first_paper_question(serialized)

    assert serialized["title"] == "商务技巧第一版"
    assert first_question["question_id"] == first.question_id


@pytest.mark.asyncio
async def test_should_expose_paper_revision_history_and_unpublished_summary(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="business-paper-history-category",
        name="商务技巧历史版本",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(
        "business-history-question-first",
        category_id=category.category_id,
        title="第一版题",
    )
    second = _question(
        "business-history-question-second",
        category_id=category.category_id,
        title="待发布题",
    )
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-history-paper",
            title="商务技巧第一版",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)
    initial_summary = await service.serialize_paper(published)

    await service.update_paper(
        published.paper_id,
        ExamPaperUpdate(
            title="商务技巧待发布版",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )

    serialized = await service.serialize_paper(
        await service.get_published_paper(published.paper_id)
    )
    history = await service.list_paper_revisions(published.paper_id)

    assert serialized["title"] == "商务技巧第一版"
    assert serialized["active_revision_id"] == initial_summary["active_revision_id"]
    assert serialized["working_revision_id"] is not None
    assert serialized["has_unpublished_revision"] is True
    assert [item["status"] for item in history] == ["working", "published"]
    assert [item["title"] for item in history] == ["商务技巧待发布版", "商务技巧第一版"]
    assert history[0]["is_working"] is True
    assert history[0]["is_active"] is False
    assert history[0]["question_count"] == 1
    assert history[1]["is_active"] is True


@pytest.mark.asyncio
async def test_should_map_unit_validation_errors_when_updating_draft_paper(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    category = QuestionCategory(
        category_id="business-paper-update-error-category",
        name="商务技巧更新异常",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "business-update-error-question-1",
        category_id=category.category_id,
        title="原题",
    )
    test_db.add_all([admin, category, question])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-update-error-paper",
            title="商务技巧异常草稿",
            module_key="business_skills",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )

    with pytest.raises(ExamPaperServiceError) as error:
        await service.update_paper(
            paper.paper_id,
            ExamPaperUpdate(
                questions=[
                    ExamPaperQuestionBinding(
                        question_id="missing-business-question",
                        order_index=1,
                        points=10,
                    )
                ],
            ),
            actor=admin,
        )

    assert error.value.code == "[QUESTION_ITEM_NOT_FOUND_OR_UNPUBLISHED]"


@pytest.mark.asyncio
async def test_should_reject_attempt_question_not_bound_to_paper(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-paper-question-boundary",
        name="商务技巧题目边界",
        order_index=1,
        usage_scope="sales_trainer",
    )
    bound_question = _question(
        "business-bound-question-1",
        category_id=category.category_id,
        title="已绑定题",
    )
    unbound_question = _question(
        "business-unbound-question-1",
        category_id=category.category_id,
        title="未绑定题",
    )
    test_db.add_all([admin, learner, category, bound_question, unbound_question])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-boundary-paper",
            title="商务技巧题目边界考卷",
            module_key="business_skills",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=bound_question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)

    with pytest.raises(ExamPaperServiceError) as error:
        await service.submit_paper_attempt(
            PaperAttemptCreate(
                paper_id=published.paper_id,
                answers=[
                    QuizAnswerSubmit(
                        question_id=unbound_question.question_id,
                        answer_payload="A",
                    )
                ],
            ),
            actor=learner,
        )

    assert error.value.code == "[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]"


async def _latest_paper_revision(
    test_db: AsyncSession,
    paper_id: str,
    *,
    status: str = "published",
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_exam_paper",
            SalesTrainerAssetRevision.logical_id == paper_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    revision = result.scalar_one()
    return revision


def _paper_question_binding(
    revision: SalesTrainerAssetRevision,
    *,
    index: int = 0,
) -> PaperQuestionBindingPayload:
    payload = revision.payload_json
    assert isinstance(payload, dict)
    questions = payload["questions"]
    assert isinstance(questions, list)
    question = questions[index]
    assert isinstance(question, dict)
    question_snapshot = question["question_snapshot"]
    assert isinstance(question_snapshot, dict)
    return {
        "question_id": str(question["question_id"]),
        "question_revision_id": _optional_str(question.get("question_revision_id")),
        "question_revision_no": _optional_int(question.get("question_revision_no")),
        "question_payload_hash": _optional_str(question.get("question_payload_hash")),
        "legacy_snapshot_only": bool(question["legacy_snapshot_only"]),
        "question_snapshot": question_snapshot,
    }


def _paper_questions(payload: dict[str, object]) -> list[dict[str, object]]:
    questions = payload["questions"]
    assert isinstance(questions, list)
    narrowed: list[dict[str, object]] = []
    for question in questions:
        assert isinstance(question, dict)
        narrowed.append(question)
    return narrowed


def _first_paper_question(payload: dict[str, object]) -> dict[str, object]:
    return _paper_questions(payload)[0]


def _first_attempt_answer(payload: dict[str, object]) -> dict[str, object]:
    answers = payload["answers"]
    assert isinstance(answers, list)
    answer = answers[0]
    assert isinstance(answer, dict)
    return answer


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None

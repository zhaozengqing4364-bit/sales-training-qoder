from __future__ import annotations

import uuid
from typing import TypedDict

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PromptTemplate, User
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
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


def _typed_question(
    question_id: str,
    *,
    category_id: str,
    title: str,
    question_type: str,
) -> QuestionItem:
    criteria_by_type: dict[str, dict[str, object]] = {
        "single_choice": {
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "正确"},
                {"value": "B", "label": "错误"},
            ],
            "correct_answer": "A",
        },
        "multiple_choice": {
            "question_type": "multiple_choice",
            "options": [
                {"value": "A", "label": "准备客户背景"},
                {"value": "B", "label": "确认拜访目标"},
            ],
            "correct_answers": ["A", "B"],
        },
        "true_false": {
            "question_type": "true_false",
            "correct_bool": False,
        },
        "short_answer": {
            "question_type": "short_answer",
            "ai_scoring": {"enabled": True, "pass_threshold": 70},
        },
    }
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title=title,
        stem=f"{title} 的正确答案是什么？",
        reference_answer="保持尊重和清晰表达。",
        scoring_criteria=criteria_by_type[question_type],
        scoring_dimensions=["business_skills"],
        status="published",
        usage_scope="sales_trainer",
    )


def _ai_coach_config() -> dict[str, object]:
    return {
        "enabled": True,
        "coach_mode": "mixed_drill",
        "allowed_interaction_types": ["single_choice", "multiple_choice"],
        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        "prompt_revision_id": None,
        "prompt_contract_hash": None,
        "scoring_prompt_template_id": None,
        "scoring_prompt_revision_id": None,
        "scoring_contract_hash": None,
        "min_turns": 3,
        "max_turns": 10,
        "mastery_threshold": 90,
        "output_schema_version": "ai_coach_interaction_v1",
        "generation_model": None,
        "scoring_model": None,
        "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
        "failure_behavior": "skip_turn",
    }


def _ai_coach_prompt_template() -> PromptTemplate:
    return PromptTemplate(
        id="11111111-1111-1111-1111-111111111111",
        name="商务技巧 AI 教练对话生成",
        prompt_type="stage",
        business_purpose=PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION,
        category="sales_trainer_ai_coach",
        template="请根据 {{ module_key }} 和 {{ coach_mode }} 生成教练回复。",
        variables=["module_key", "coach_mode"],
        is_active=True,
        is_default=False,
        is_system=False,
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
    assert _is_payload_hash(first_binding["question_payload_hash"])
    assert first_binding["legacy_snapshot_only"] is True
    assert first_binding["question_snapshot"]["title"] == "见客户前准备"
    assert second_binding["question_id"] == second.question_id
    assert second_binding["question_revision_id"] is None
    assert _is_payload_hash(second_binding["question_payload_hash"])
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
    test_db.add_all(
        [
            admin,
            learner,
            category,
            question,
            content,
            chapter,
            _ai_coach_prompt_template(),
        ]
    )
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
                    ai_coach=_ai_coach_config(),
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
async def test_should_ignore_legacy_unit_path_for_article_exam_prerequisite(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="legacy-business-paper-reading-gate-category",
        name="旧路径商务技巧阅读门禁",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "legacy-business-read-gate-q1",
        category_id=category.category_id,
        title="旧路径客户拜访阅读门禁",
    )
    content = LearningContent(
        learning_content_id="legacy-business-reading-gate-content",
        title="旧路径见客户前商务礼仪",
        summary="旧 unit.config 中的 path 只能作为迁移诊断，不得驱动 learner 执行。",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    chapter = LearningChapter(
        chapter_id="legacy-business-reading-gate-chapter-1",
        learning_content_id=content.learning_content_id,
        title="旧路径拜访前准备",
        content="这条阅读进度不能由旧 unit.config 强制要求。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, learner, category, question, content, chapter])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="legacy-business-reading-gate-paper",
            title="旧路径商务技巧阅读门禁考卷",
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
    unit = await test_db.get(SalesTrainerUnit, published.unit_id)
    assert unit is not None
    unit.config = {
        "path": {
            "enabled": True,
            "path_key": "newcomer_training_path_v1",
            "path_title": "旧新人训练路径",
            "module_key": "business_skills",
            "module_type": "article_exam",
            "order_index": 1,
            "learning_content_id": content.learning_content_id,
            "exam_paper_id": published.paper_id,
        }
    }
    await test_db.commit()

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
    assert _is_payload_hash(working_binding["question_payload_hash"])
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
async def test_should_score_attempt_from_paper_question_snapshot_after_question_changes(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-paper-question-snapshot-category",
        name="商务技巧题目快照",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question(
        "business-question-snapshot-1",
        category_id=category.category_id,
        title="发布时题目",
        correct_answer="A",
    )
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-question-snapshot-paper",
            title="商务技巧题目快照考卷",
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
    published_revision = await _latest_paper_revision(test_db, published.paper_id)
    published_binding = _paper_question_binding(published_revision)

    question.title = "题库后来改名"
    question.scoring_criteria = {
        **question.scoring_criteria,
        "correct_answer": "B",
    }
    await test_db.commit()

    attempt = await service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published.paper_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=question.question_id,
                    answer_payload="A",
                )
            ],
        ),
        actor=learner,
    )
    serialized = await service.serialize_attempt(attempt)
    answer = _first_attempt_answer(serialized)

    assert answer["question_title"] == "发布时题目"
    assert answer["correct_answer"] == "A"
    assert answer["score"] == 10
    assert answer["question_revision_id"] is None
    assert answer["question_payload_hash"] == published_binding["question_payload_hash"]
    assert _is_payload_hash(answer["question_payload_hash"])


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


@pytest.mark.asyncio
async def test_should_reject_incomplete_paper_attempt_without_creating_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-paper-incomplete-category",
        name="商务技巧空卷边界",
        order_index=1,
        usage_scope="sales_trainer",
    )
    questions = [
        _typed_question(
            "business-incomplete-single",
            category_id=category.category_id,
            title="单选题",
            question_type="single_choice",
        ),
        _typed_question(
            "business-incomplete-multiple",
            category_id=category.category_id,
            title="多选题",
            question_type="multiple_choice",
        ),
        _typed_question(
            "business-incomplete-true-false",
            category_id=category.category_id,
            title="判断题",
            question_type="true_false",
        ),
        _typed_question(
            "business-incomplete-short",
            category_id=category.category_id,
            title="简答题",
            question_type="short_answer",
        ),
    ]
    test_db.add_all([admin, learner, category, *questions])
    await test_db.commit()

    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-incomplete-paper",
            title="商务技巧空卷边界考卷",
            module_key="business_skills",
            questions=[
                ExamPaperQuestionBinding(
                    question_id=question.question_id,
                    order_index=index,
                    points=10,
                )
                for index, question in enumerate(questions, start=1)
            ],
        ),
        actor=admin,
    )
    published = await service.publish_paper(paper.paper_id, actor=admin)
    valid_answers = {
        questions[0].question_id: "A",
        questions[1].question_id: ["A", "B"],
        questions[2].question_id: "false",
        questions[3].question_id: "拜访前先确认客户背景和目标。",
    }
    invalid_answer_maps = [
        {key: value for key, value in valid_answers.items() if key != questions[3].question_id},
        {**valid_answers, questions[0].question_id: ""},
        {**valid_answers, questions[1].question_id: []},
        {**valid_answers, questions[2].question_id: ""},
        {**valid_answers, questions[3].question_id: "  "},
    ]

    for answer_map in invalid_answer_maps:
        with pytest.raises(ExamPaperServiceError) as error:
            await service.submit_paper_attempt(
                PaperAttemptCreate(
                    paper_id=published.paper_id,
                    answers=[
                        QuizAnswerSubmit(
                            question_id=question_id,
                            answer_payload=answer_payload,
                        )
                        for question_id, answer_payload in answer_map.items()
                    ],
                ),
                actor=learner,
            )

        assert error.value.code == "[QUIZ_ANSWER_INCOMPLETE]"
        assert error.value.status_code == 422

    attempt_count = await test_db.scalar(
        select(func.count()).select_from(SalesTrainerQuizAttempt)
    )
    assert attempt_count == 0


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


def _is_payload_hash(value: object) -> bool:
    return isinstance(value, str) and value.startswith("sha256:")

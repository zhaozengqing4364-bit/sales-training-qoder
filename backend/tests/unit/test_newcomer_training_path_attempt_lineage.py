from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperQuestionBinding,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
    PaperAttemptCreate,
    QuizAnswerSubmit,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.exam_paper_revision_constants import PAPER_RESOURCE_TYPE
from sales_trainer.services.exam_paper_service import ExamPaperService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"attempt-lineage-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Attempt Lineage {role}",
        email=f"attempt-lineage-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _question(question_id: str, *, category_id: str) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title="客户拜访礼仪",
        stem="见客户前应该先确认什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "确认客户背景与拜访目标"},
                {"value": "B", "label": "临场发挥"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


@pytest.mark.asyncio
async def test_should_freeze_path_revision_lineage_when_submitting_paper_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="attempt-lineage-category",
        name="商务技巧路径版本",
        order_index=1,
        usage_scope="sales_trainer",
    )
    question = _question("attempt-lineage-question", category_id=category.category_id)
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()

    paper_service = ExamPaperService(test_db)
    paper = await paper_service.create_paper(
        ExamPaperCreate(
            paper_key="attempt-lineage-paper",
            title="商务技巧路径版本考卷",
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
    published = await paper_service.publish_paper(paper.paper_id, actor=admin)

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定商务技巧考卷",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="business_skills",
                    module_type="article_exam",
                    enabled=True,
                    order_index=1,
                    title="商务技巧",
                    target_unit_id=published.unit_id,
                    exam_paper_id=published.paper_id,
                    completion_rule="submitted",
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="商务技巧路径生效",
    )

    attempt = await paper_service.submit_paper_attempt(
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
    serialized = await paper_service.serialize_attempt(attempt)
    answers = serialized["answers"]
    assert isinstance(answers, list)
    first_answer = answers[0]
    assert isinstance(first_answer, dict)
    answer_context = first_answer["attempt_context"]
    assert isinstance(answer_context, dict)

    assert serialized["path_revision_id"] == str(publish_result.revision.revision_id)
    assert serialized["path_revision_no"] == 1
    assert serialized["path_key"] == "newcomer_training_path_v1"
    assert serialized["module_key"] == "business_skills"
    assert serialized["legacy_snapshot_only"] is False
    assert answer_context["path_revision_id"] == serialized["path_revision_id"]
    assert answer_context["paper_revision_id"] == serialized["paper_revision_id"]


@pytest.mark.asyncio
async def test_should_freeze_path_revision_lineage_for_legacy_paper_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="attempt-lineage-legacy-category",
        name="商务技巧旧版路径版本",
        order_index=2,
        usage_scope="sales_trainer",
    )
    question = _question(
        "attempt-lineage-legacy-question",
        category_id=category.category_id,
    )
    test_db.add_all([admin, learner, category, question])
    await test_db.commit()

    paper_service = ExamPaperService(test_db)
    paper = await paper_service.create_paper(
        ExamPaperCreate(
            paper_key="attempt-lineage-legacy-paper",
            title="商务技巧旧版考卷",
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
    published = await paper_service.publish_paper(paper.paper_id, actor=admin)
    active_revision = await SalesTrainerAssetRevisionService(
        test_db
    ).active_revision(
        resource_type=PAPER_RESOURCE_TYPE,
        logical_id=published.paper_id,
    )
    assert active_revision is not None
    active_revision.payload_json = {
        "title": published.title,
        "questions": [
            {
                "question_id": question.question_id,
                "order_index": 1,
                "points": 10,
            }
        ],
    }
    await test_db.commit()

    path_service = SalesTrainerPathConfigService(test_db)
    await path_service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="绑定旧版商务技巧考卷",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="business_skills",
                    module_type="article_exam",
                    enabled=True,
                    order_index=1,
                    title="商务技巧",
                    target_unit_id=published.unit_id,
                    exam_paper_id=published.paper_id,
                    completion_rule="submitted",
                )
            ],
        ),
        actor=admin,
    )
    publish_result = await path_service.publish_config(
        actor=admin,
        reason="旧版商务技巧路径生效",
    )

    attempt = await paper_service.submit_paper_attempt(
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
    serialized = await paper_service.serialize_attempt(attempt)
    answers = serialized["answers"]
    assert isinstance(answers, list)
    first_answer = answers[0]
    assert isinstance(first_answer, dict)
    answer_context = first_answer["attempt_context"]

    assert isinstance(answer_context, dict)
    assert answer_context["path_revision_id"] == str(
        publish_result.revision.revision_id
    )
    assert answer_context["paper_revision_id"] == str(active_revision.revision_id)
    assert serialized["legacy_snapshot_only"] is False

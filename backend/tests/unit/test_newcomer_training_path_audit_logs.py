from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperQuestionBinding,
    ExamPaperUpdate,
    SalesTrainerUnitCreate,
    SalesTrainerUnitUpdate,
    UnitQuestionBinding,
)
from sales_trainer.services.exam_paper_service import ExamPaperService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.unit_service import UnitService


def _admin() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"audit-admin-{uuid.uuid4().hex[:8]}",
        name="Audit Admin",
        email=f"audit-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
    )


def _question(question_id: str, *, category_id: str, title: str) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title=title,
        stem=f"{title} 的正确答案是什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "正确"},
                {"value": "B", "label": "错误"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


async def _seed_questions(
    test_db: AsyncSession,
    *,
    category_id: str,
) -> tuple[User, QuestionItem, QuestionItem]:
    admin = _admin()
    category = QuestionCategory(
        category_id=category_id,
        name="新人训练路径审计",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question(f"{category_id}-first", category_id=category_id, title="第一题")
    second = _question(f"{category_id}-second", category_id=category_id, title="第二题")
    test_db.add_all([admin, category, first, second])
    await test_db.commit()
    return admin, first, second


@pytest.mark.asyncio
async def test_should_record_unit_update_before_and_after_metadata(
    test_db: AsyncSession,
) -> None:
    admin, first, second = await _seed_questions(
        test_db,
        category_id="audit-unit-update-category",
    )
    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="商务技巧草稿",
            description="旧说明",
            unit_type="quiz",
            config={"path": {"enabled": True, "path_key": "default", "order_index": 2}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )

    await service.update_unit(
        unit,
        SalesTrainerUnitUpdate(
            name="商务技巧新版草稿",
            description="新说明",
            config={
                "path": {
                    "enabled": True,
                    "path_key": "newcomer_training_path_v1",
                    "module_key": "business_skills",
                    "module_type": "article_exam",
                    "order_index": 2,
                }
            },
            questions=[
                UnitQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )

    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_unit",
        target_id=unit.unit_id,
    )
    update_log = next(log for log in logs if log.action == "unit_updated")
    metadata = update_log.metadata_json

    assert set(metadata["changed_fields"]) == {
        "config",
        "description",
        "name",
        "questions",
    }
    assert metadata["previous"]["name"] == "商务技巧草稿"
    assert metadata["next"]["name"] == "商务技巧新版草稿"
    assert metadata["previous"]["question_ids"] == [first.question_id]
    assert metadata["next"]["question_ids"] == [second.question_id]
    assert metadata["path"]["previous_path_key"] == "default"
    assert metadata["path"]["next_path_key"] == "newcomer_training_path_v1"
    assert metadata["path"]["next_module_key"] == "business_skills"


@pytest.mark.asyncio
async def test_should_record_publish_and_archive_status_transitions(
    test_db: AsyncSession,
) -> None:
    admin, first, _ = await _seed_questions(
        test_db,
        category_id="audit-unit-status-category",
    )
    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="PPT 讲解录音",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )

    await service.publish_unit(unit, actor=admin)
    await service.archive_unit(unit, actor=admin)

    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_unit",
        target_id=unit.unit_id,
    )
    publish_log = next(log for log in logs if log.action == "unit_published")
    archive_log = next(log for log in logs if log.action == "unit_archived")

    assert publish_log.metadata_json["previous_status"] == "draft"
    assert publish_log.metadata_json["next_status"] == "published"
    assert archive_log.metadata_json["previous_status"] == "published"
    assert archive_log.metadata_json["next_status"] == "archived"


@pytest.mark.asyncio
async def test_should_record_exam_paper_lifecycle_before_and_after_metadata(
    test_db: AsyncSession,
) -> None:
    admin, first, second = await _seed_questions(
        test_db,
        category_id="audit-paper-category",
    )
    service = ExamPaperService(test_db)
    paper = await service.create_paper(
        ExamPaperCreate(
            paper_key="business-skills-audit",
            title="商务技巧考卷草稿",
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

    await service.update_paper(
        paper.paper_id,
        ExamPaperUpdate(
            title="商务技巧考卷新版",
            pass_threshold=12,
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
    await service.publish_paper(paper.paper_id, actor=admin)
    await service.archive_paper(paper.paper_id, actor=admin)

    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_exam_paper",
        target_id=paper.paper_id,
    )
    update_log = next(log for log in logs if log.action == "exam_paper_updated")
    publish_log = next(log for log in logs if log.action == "exam_paper_published")
    archive_log = next(log for log in logs if log.action == "exam_paper_archived")

    assert set(update_log.metadata_json["changed_fields"]) == {
        "pass_threshold",
        "questions",
        "title",
    }
    assert update_log.metadata_json["previous"]["question_ids"] == [first.question_id]
    assert update_log.metadata_json["next"]["question_ids"] == [second.question_id]
    assert publish_log.metadata_json["previous_status"] == "draft"
    assert publish_log.metadata_json["next_status"] == "published"
    assert archive_log.metadata_json["previous_status"] == "published"
    assert archive_log.metadata_json["next_status"] == "archived"
    assert archive_log.metadata_json["previous_unit_status"] == "published"
    assert archive_log.metadata_json["next_unit_status"] == "archived"

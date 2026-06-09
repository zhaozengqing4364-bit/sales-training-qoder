from __future__ import annotations

import uuid
from typing import TypedDict

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperQuestionBinding,
    ExamPaperUpdate,
    PaperAttemptCreate,
    QuizAnswerSubmit,
    SalesTrainerQuestionCreate,
    SalesTrainerQuestionOption,
    SalesTrainerQuestionUpdate,
)
from sales_trainer.services.exam_paper_service import ExamPaperService
from sales_trainer.services.question_service import SalesTrainerQuestionService


class PaperQuestionBindingPayload(TypedDict):
    question_revision_id: str | None
    question_revision_no: int | None
    question_payload_hash: str | None
    legacy_snapshot_only: bool
    question_snapshot: dict[str, object]


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-question-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Question {role}",
        email=f"newcomer-question-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_edit_published_question_as_future_revision_without_polluting_existing_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    category = QuestionCategory(
        category_id="business-question-revision-category",
        name="商务技巧题目修订",
        order_index=1,
        usage_scope="sales_trainer",
    )
    test_db.add_all([admin, learner, category])
    await test_db.commit()

    question_service = SalesTrainerQuestionService(test_db)
    question = await question_service.create_question(
        SalesTrainerQuestionCreate(
            title="旧题",
            stem="见客户前应优先准备什么？",
            category_id=category.category_id,
            question_type="single_choice",
            options=[
                SalesTrainerQuestionOption(value="A", label="客户背景和拜访目标"),
                SalesTrainerQuestionOption(value="B", label="临场自由发挥"),
            ],
            correct_answer="A",
            explanation="先准备客户背景和目标。",
        ),
        actor_id=str(admin.user_id),
    )
    published_question = await question_service.publish_question(
        str(question.question_id),
        actor_id=str(admin.user_id),
    )
    initial_revision = await _latest_question_revision(test_db, str(question.question_id))

    paper_service = ExamPaperService(test_db)
    paper = await paper_service.create_paper(
        ExamPaperCreate(
            paper_key="business-question-revision-paper",
            title="商务技巧题目修订考卷",
            module_key="business_skills",
            pass_threshold=10,
            questions=[
                ExamPaperQuestionBinding(
                    question_id=str(published_question.question_id),
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    published_paper = await paper_service.publish_paper(paper.paper_id, actor=admin)
    initial_paper_revision = await _latest_paper_revision(
        test_db,
        published_paper.paper_id,
    )
    initial_paper_question = _paper_question_binding(initial_paper_revision)
    old_attempt = await paper_service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published_paper.paper_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=str(published_question.question_id),
                    answer_payload="A",
                )
            ],
        ),
        actor=learner,
    )

    assert initial_paper_question["question_revision_id"] == initial_revision.revision_id
    assert initial_paper_question["question_revision_no"] == initial_revision.revision_no
    assert initial_paper_question["question_payload_hash"] == initial_revision.payload_hash
    assert initial_paper_question["legacy_snapshot_only"] is False
    assert initial_paper_question["question_snapshot"]["title"] == "旧题"

    await question_service.update_question(
        str(published_question.question_id),
        SalesTrainerQuestionUpdate(
            title="新题",
            stem="见客户前最不应该依赖什么？",
            options=[
                SalesTrainerQuestionOption(value="A", label="客户背景和拜访目标"),
                SalesTrainerQuestionOption(value="B", label="临场自由发挥"),
            ],
            correct_answer="B",
            explanation="不能只依赖临场发挥。",
        ),
        actor_id=str(admin.user_id),
    )

    unchanged = await question_service.get_question(str(published_question.question_id))
    working_revision = await _latest_question_revision(
        test_db,
        str(question.question_id),
        status="working",
    )

    assert unchanged.title == "旧题"
    assert unchanged.scoring_criteria["correct_answer"] == "A"
    assert working_revision.payload_json["title"] == "新题"
    assert working_revision.payload_json["scoring_criteria"]["correct_answer"] == "B"
    assert working_revision.change_class == "scoring_high_risk"
    assert working_revision.source_revision_id == initial_revision.revision_id

    await question_service.publish_question(
        str(published_question.question_id),
        actor_id=str(admin.user_id),
    )
    published_new_question = await question_service.get_question(
        str(published_question.question_id)
    )
    published_new_revision = await _latest_question_revision(
        test_db,
        str(question.question_id),
    )
    unchanged_paper_attempt = await paper_service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published_paper.paper_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=str(published_question.question_id),
                    answer_payload="A",
                )
            ],
        ),
        actor=learner,
    )
    await paper_service.update_paper(
        published_paper.paper_id,
        ExamPaperUpdate(
            questions=[
                ExamPaperQuestionBinding(
                    question_id=str(published_question.question_id),
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await paper_service.publish_paper(published_paper.paper_id, actor=admin)
    refreshed_paper_revision = await _latest_paper_revision(
        test_db,
        published_paper.paper_id,
    )
    refreshed_paper_question = _paper_question_binding(refreshed_paper_revision)
    refreshed_paper_attempt = await paper_service.submit_paper_attempt(
        PaperAttemptCreate(
            paper_id=published_paper.paper_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=str(published_question.question_id),
                    answer_payload="B",
                )
            ],
        ),
        actor=learner,
    )

    old_attempt_payload = await paper_service.serialize_attempt(old_attempt)
    unchanged_paper_attempt_payload = await paper_service.serialize_attempt(
        unchanged_paper_attempt
    )
    refreshed_paper_attempt_payload = await paper_service.serialize_attempt(
        refreshed_paper_attempt
    )
    old_answer = _first_attempt_answer(old_attempt_payload)
    unchanged_answer = _first_attempt_answer(unchanged_paper_attempt_payload)
    refreshed_answer = _first_attempt_answer(refreshed_paper_attempt_payload)

    assert published_new_question.title == "新题"
    assert published_new_question.scoring_criteria["correct_answer"] == "B"
    assert refreshed_paper_question["question_revision_id"] == (
        published_new_revision.revision_id
    )
    assert refreshed_paper_question["question_revision_no"] == (
        published_new_revision.revision_no
    )
    assert refreshed_paper_question["question_payload_hash"] == (
        published_new_revision.payload_hash
    )
    assert refreshed_paper_question["legacy_snapshot_only"] is False
    assert refreshed_paper_question["question_snapshot"]["title"] == "新题"
    assert old_attempt_payload["paper_revision_id"] == initial_paper_revision.revision_id
    assert old_answer["question_title"] == "旧题"
    assert old_answer["correct_answer"] == "A"
    assert old_answer["score"] == 10
    assert unchanged_paper_attempt_payload["paper_revision_id"] == (
        initial_paper_revision.revision_id
    )
    assert unchanged_answer["question_title"] == "旧题"
    assert unchanged_answer["correct_answer"] == "A"
    assert unchanged_answer["score"] == 10
    assert refreshed_paper_attempt_payload["paper_revision_id"] == (
        refreshed_paper_revision.revision_id
    )
    assert refreshed_answer["question_title"] == "新题"
    assert refreshed_answer["correct_answer"] == "B"
    assert refreshed_answer["score"] == 10


async def _latest_question_revision(
    test_db: AsyncSession,
    question_id: str,
    *,
    status: str = "published",
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_question",
            SalesTrainerAssetRevision.logical_id == question_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _latest_paper_revision(
    test_db: AsyncSession,
    paper_id: str,
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_exam_paper",
            SalesTrainerAssetRevision.logical_id == paper_id,
            SalesTrainerAssetRevision.status == "published",
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()


def _paper_question_binding(
    revision: SalesTrainerAssetRevision,
) -> PaperQuestionBindingPayload:
    payload = revision.payload_json
    assert isinstance(payload, dict)
    questions = payload["questions"]
    assert isinstance(questions, list)
    question = questions[0]
    assert isinstance(question, dict)
    question_snapshot = question["question_snapshot"]
    assert isinstance(question_snapshot, dict)
    return {
        "question_revision_id": _optional_str(question.get("question_revision_id")),
        "question_revision_no": _optional_int(question.get("question_revision_no")),
        "question_payload_hash": _optional_str(question.get("question_payload_hash")),
        "legacy_snapshot_only": bool(question["legacy_snapshot_only"]),
        "question_snapshot": question_snapshot,
    }


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _first_attempt_answer(payload: dict[str, object]) -> dict[str, object]:
    answers = payload["answers"]
    assert isinstance(answers, list)
    answer = answers[0]
    assert isinstance(answer, dict)
    return answer

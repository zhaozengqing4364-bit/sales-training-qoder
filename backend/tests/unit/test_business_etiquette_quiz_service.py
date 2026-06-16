from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.schemas import (
    BusinessEtiquetteQuizAnswerSubmit,
    BusinessEtiquetteTrainingUnitConfig,
    BusinessEtiquetteUnitQuizAttemptCreate,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.business_etiquette_quiz_service import (
    BusinessEtiquetteQuizService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.question_bank.contracts import SALES_TRAINER_QUESTION_SCOPE
from sales_trainer.services.short_answer_scoring_service import ShortAnswerScoreOutcome


class FakeBusinessEtiquetteShortAnswerScoringService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def score(self, question: QuestionItem, *, answer_text: str):
        self.calls.append(
            {
                "question_id": str(question.question_id),
                "answer_text": answer_text,
            }
        )
        return Result.ok(
            ShortAnswerScoreOutcome(
                score=0,
                passed=False,
                feedback="AI 判断该答案没有提供商务拜访的具体做法。",
                reason="answer_has_no_action",
                raw_response={"score": 0, "reason": "answer_has_no_action"},
                scoring_source="ai_llm",
                scoring_provider="deepseek",
                scoring_model="deepseek-chat",
                scoring_latency_ms=1280,
            )
        )


def _user(role: str = "user") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-quiz-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette Quiz {role}",
        email=f"business-etiquette-quiz-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


async def _seed_active_path(
    test_db: AsyncSession,
    *,
    admin: User,
    quiz_question_count: int = 1,
    quiz_question_type_weights: dict[str, float] | None = None,
    quiz_allow_retake: bool = True,
    quiz_max_attempts: int | None = None,
) -> None:
    payload = NewcomerPathConfigPayload(
        path_key=NEWCOMER_PATH_LOGICAL_ID,
        title="新人训练路径",
        modules=[
            NewcomerPathModuleConfig(
                module_key="business_skills",
                module_type="article_exam",
                enabled=True,
                order_index=1,
                title="商务礼仪",
                learning_units=[
                    BusinessEtiquetteTrainingUnitConfig(
                        unit_key="trust_foundation",
                        title="职业信任底座",
                        description="尊重分寸、第一印象。",
                        order_index=1,
                        enabled=True,
                        source_chapter_orders=[1],
                        capability_keys=["respect_boundaries"],
                        unlock_after_unit_keys=[],
                        require_reading=True,
                        require_quiz=True,
                        require_ai_coach=True,
                        quiz_question_count=quiz_question_count,
                        quiz_pass_threshold=None,
                        quiz_allow_retake=quiz_allow_retake,
                        quiz_max_attempts=quiz_max_attempts,
                        quiz_question_type_weights=quiz_question_type_weights or {},
                    )
                ],
            )
        ],
    )
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload.model_dump(mode="json"),
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪小单元配置",
    )
    await test_db.commit()


async def _seed_active_training_pack(test_db: AsyncSession, *, admin: User) -> None:
    snapshot = default_business_etiquette_capability_snapshot()
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload={
            "schema_version": 1,
            "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            "book_title": "商务礼仪",
            "original_chapter_count": 1,
            "original_chapters": [{"title": "第 1 章", "order_index": 1}],
            CAPABILITY_SNAPSHOT_KEY: {
                "schema_version": 1,
                "capabilities": snapshot["capabilities"],
                "chapter_bindings": [
                    {
                        "chapter_order": 1,
                        "capability_keys": ["respect_boundaries"],
                    }
                ],
            },
        },
        actor=admin,
        change_class="semantic",
        reason="发布商务礼仪训练包",
    )
    await test_db.commit()


async def _seed_published_question(
    test_db: AsyncSession,
    *,
    admin: User,
    title: str = "迟到处理",
    stem: str = "商务拜访即将迟到时，最合适的做法是什么？",
    question_type: str = "single_choice",
) -> QuestionItem:
    category = QuestionCategory(
        name="商务礼仪",
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(category)
    await test_db.flush()
    criteria = {
        "question_type": question_type,
        "dimensions": ["respect_boundaries"],
        "explanation": "守时体现尊重。",
    }
    if question_type in {"single_choice", "multiple_choice"}:
        criteria.update(
            {
                "options": [
                    {"value": "A", "label": "提前说明并表达歉意"},
                    {"value": "B", "label": "到场后再解释"},
                ],
                "correct_answer": "A",
            }
        )
    question = QuestionItem(
        category_id=category.category_id,
        title=title,
        stem=stem,
        reference_answer="提前说明并表达歉意",
        scoring_criteria=criteria,
        scoring_dimensions=["respect_boundaries"],
        tags=[
            "business_etiquette",
            "capability:respect_boundaries",
            "chapter:1",
        ],
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        difficulty="easy",
        status="published",
        safety_flagged=False,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(question)
    await test_db.commit()
    await test_db.refresh(question)
    return question


@pytest.mark.asyncio
async def test_should_load_business_etiquette_unit_quiz_from_published_questions(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(test_db, admin=admin)
    await _seed_active_training_pack(test_db, admin=admin)
    question = await _seed_published_question(test_db, admin=admin)

    quiz = await BusinessEtiquetteQuizService(test_db).get_unit_quiz(
        "trust_foundation",
        user_id=str(learner.user_id),
    )

    assert quiz.learning_unit_key == "trust_foundation"
    assert quiz.training_pack_revision_id is not None
    assert quiz.questions[0].question_id == question.question_id
    assert quiz.questions[0].capability_keys == ["respect_boundaries"]
    assert quiz.questions[0].options[0].value == "A"


@pytest.mark.asyncio
async def test_should_preview_business_etiquette_unit_quiz_without_attempt_limit(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(
        test_db,
        admin=admin,
        quiz_allow_retake=False,
        quiz_max_attempts=1,
    )
    await _seed_active_training_pack(test_db, admin=admin)
    question = await _seed_published_question(test_db, admin=admin)
    service = BusinessEtiquetteQuizService(test_db)

    submitted = await service.submit_attempt(
        "trust_foundation",
        BusinessEtiquetteUnitQuizAttemptCreate(
            answers=[
                BusinessEtiquetteQuizAnswerSubmit(
                    question_id=str(question.question_id),
                    answer_payload="A",
                )
            ]
        ),
        actor=learner,
    )
    preview = await service.preview_unit_quiz("trust_foundation")

    assert submitted.status == "scored"
    assert preview.learning_unit_key == "trust_foundation"
    assert preview.questions[0].question_id == question.question_id


@pytest.mark.asyncio
async def test_should_submit_business_etiquette_unit_quiz_and_score_capabilities(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(test_db, admin=admin)
    await _seed_active_training_pack(test_db, admin=admin)
    question = await _seed_published_question(test_db, admin=admin)

    result = await BusinessEtiquetteQuizService(test_db).submit_attempt(
        "trust_foundation",
        BusinessEtiquetteUnitQuizAttemptCreate(
            answers=[
                BusinessEtiquetteQuizAnswerSubmit(
                    question_id=str(question.question_id),
                    answer_payload="A",
                )
            ]
        ),
        actor=learner,
    )

    assert result.status == "scored"
    assert result.passed is True
    assert result.total_score == 10
    assert result.max_score == 10
    assert result.capability_scores[0].capability_key == "respect_boundaries"
    assert result.capability_scores[0].normalized_score == 100
    assert result.capability_scores[0].mastered is True
    assert result.answers[0].is_correct is True
    assert result.recommended_chapter_orders == [1]


@pytest.mark.asyncio
async def test_should_select_questions_by_configured_type_weights(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(
        test_db,
        admin=admin,
        quiz_question_count=1,
        quiz_question_type_weights={"short_answer": 1, "single_choice": 0},
    )
    await _seed_active_training_pack(test_db, admin=admin)
    await _seed_published_question(
        test_db,
        admin=admin,
        title="迟到处理单选",
        question_type="single_choice",
    )
    short_answer = await _seed_published_question(
        test_db,
        admin=admin,
        title="迟到处理简答",
        stem="请说明商务拜访即将迟到时的处理步骤。",
        question_type="short_answer",
    )

    quiz = await BusinessEtiquetteQuizService(test_db).get_unit_quiz(
        "trust_foundation",
        user_id=str(learner.user_id),
    )

    assert len(quiz.questions) == 1
    assert quiz.questions[0].question_id == short_answer.question_id
    assert quiz.questions[0].question_type == "short_answer"


@pytest.mark.asyncio
async def test_should_score_business_etiquette_short_answer_through_ai(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(
        test_db,
        admin=admin,
        quiz_question_count=1,
        quiz_question_type_weights={"short_answer": 1},
    )
    await _seed_active_training_pack(test_db, admin=admin)
    short_answer = await _seed_published_question(
        test_db,
        admin=admin,
        title="拜访要点简答",
        stem="请说明商务拜访时需要注意的两个要点。",
        question_type="short_answer",
    )

    fake_scoring = FakeBusinessEtiquetteShortAnswerScoringService()
    result = await BusinessEtiquetteQuizService(
        test_db,
        short_answer_scoring_service=fake_scoring,
    ).submit_attempt(
        "trust_foundation",
        BusinessEtiquetteUnitQuizAttemptCreate(
            answers=[
                BusinessEtiquetteQuizAnswerSubmit(
                    question_id=str(short_answer.question_id),
                    answer_payload="哈哈",
                )
            ]
        ),
        actor=learner,
    )

    assert fake_scoring.calls == [
        {
            "question_id": str(short_answer.question_id),
            "answer_text": "哈哈",
        }
    ]
    assert result.status == "scored"
    assert result.passed is False
    assert result.total_score == 0
    assert result.max_score == 10
    assert result.answers[0].is_correct is False
    assert result.answers[0].score == 0
    assert result.answers[0].analysis is not None
    assert "AI 判断" in result.answers[0].analysis
    assert result.answers[0].scoring_source == "ai_llm"
    assert result.answers[0].scoring_provider == "deepseek"
    assert result.answers[0].scoring_model == "deepseek-chat"
    assert result.answers[0].scoring_latency_ms == 1280

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import (
    NewcomerArticleBinding,
    SalesTrainerUnitCreate,
    UnitQuestionBinding,
)
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)
from sales_trainer.services.exam_paper_service import (
    ExamPaperService,
    ExamPaperServiceError,
)
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService


def _user() -> User:
    return User(
        user_id="newcomer-boundary-user",
        wechat_user_id="newcomer-boundary-user",
        name="Newcomer Boundary User",
        email="newcomer-boundary-user@example.com",
        role="admin",
    )


def _question() -> tuple[QuestionCategory, QuestionItem]:
    category = QuestionCategory(
        category_id="newcomer-boundary-category",
        name="新人路径边界题库",
        usage_scope="sales_trainer",
        order_index=1,
    )
    question = QuestionItem(
        question_id="newcomer-boundary-question",
        category_id=category.category_id,
        title="新人路径边界题",
        stem="见客户前第一步是什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "确认目标"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["business_skills"],
        usage_scope="sales_trainer",
        status="published",
    )
    return category, question


def test_sales_trainer_newcomer_path_does_not_import_realtime_runtime() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "sales_trainer"
    offenders: list[str] = []

    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "sales_bot" in text or "PracticeSession" in text or "/practice/" in text:
            offenders.append(str(path.relative_to(source_root)))

    assert offenders == ["__init__.py"]


@pytest.mark.asyncio
async def test_realtime_placeholder_is_disabled_and_does_not_create_practice_session(
    test_db: AsyncSession,
) -> None:
    user = _user()
    unit = SalesTrainerUnit(
        unit_id="newcomer-realtime-placeholder",
        name="实时对练占位",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": False,
                "path_key": "newcomer_training_path_v1",
                "module_key": "realtime_placeholder",
                "module_type": "realtime_placeholder",
                "order_index": 4,
                "completion_rule": "submitted",
                "disabled_reason": "暂不开放",
            }
        },
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    test_db.add_all([user, unit])
    await test_db.commit()

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(user.user_id)
    practice_session_count = await test_db.scalar(
        select(func.count()).select_from(PracticeSession)
    )

    assert paths == []
    assert practice_session_count == 0


@pytest.mark.asyncio
async def test_article_exam_module_targets_business_skills_flow(
    test_db: AsyncSession,
) -> None:
    user = _user()
    unit = SalesTrainerUnit(
        unit_id="newcomer-business-skills-target",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 2,
                "completion_rule": "submitted",
            }
        },
        created_by=user.user_id,
        updated_by=user.user_id,
    )
    test_db.add_all([user, unit])
    await test_db.commit()

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(user.user_id)

    assert paths[0]["levels"][0]["target_path"] == "/sales-trainer/business-skills"


@pytest.mark.asyncio
async def test_newcomer_module_invalid_config_reports_typed_error(
    test_db: AsyncSession,
) -> None:
    user = _user()
    category, question = _question()
    test_db.add_all([user, category, question])
    await test_db.commit()

    with pytest.raises(SalesTrainerUnitError) as exc:
        await UnitService(test_db).create_unit(
            SalesTrainerUnitCreate(
                name="非法新人模块",
                unit_type="quiz",
                config={
                    "quiz": {"pass_threshold": 10},
                    "path": {
                        "enabled": True,
                        "path_key": "newcomer_training_path_v1",
                        "module_key": "business_skills",
                        "module_type": "sales_queue",
                        "order_index": 1,
                    },
                },
                questions=[
                    UnitQuestionBinding(
                        question_id=question.question_id,
                        order_index=1,
                        points=10,
                    )
                ],
            ),
            actor=user,
        )

    assert exc.value.code == "[NEWCOMER_MODULE_CONFIG_INVALID]"
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_missing_article_and_paper_keep_typed_failures(
    test_db: AsyncSession,
) -> None:
    with pytest.raises(ArticleBindingServiceError) as article_error:
        await ArticleBindingService(test_db).resolve_module_article(
            binding=NewcomerArticleBinding(module_key="business_skills")
        )
    with pytest.raises(ExamPaperServiceError) as paper_error:
        await ExamPaperService(test_db).get_published_paper("missing-paper")

    assert article_error.value.code == "[LEARNING_CONTENT_NOT_PUBLISHED]"
    assert paper_error.value.code == "[PAPER_NOT_FOUND]"

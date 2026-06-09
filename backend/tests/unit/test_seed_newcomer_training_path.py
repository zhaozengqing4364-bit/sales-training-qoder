from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import LearningContent, QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)


def _load_seed_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "seed_newcomer_training_path.py"
    )
    spec = importlib.util.spec_from_file_location(
        "seed_newcomer_training_path", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_is_idempotent(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    first = await seed_module.seed(test_db)
    second = await seed_module.seed(test_db)
    verified = await seed_module.verify(test_db)

    assert first.verified is True
    assert second.verified is True
    assert verified.verified is True

    unit_count = await test_db.scalar(
        select(func.count())
        .select_from(SalesTrainerUnit)
        .where(
            SalesTrainerUnit.config["path"]["path_key"].as_string()
            == seed_module.PATH_KEY
        )
    )
    assert unit_count == len(seed_module.MODULE_KEYS)

    paper_count = await test_db.scalar(
        select(func.count())
        .select_from(SalesTrainerExamPaper)
        .where(SalesTrainerExamPaper.paper_key == seed_module.BUSINESS_SKILLS_PAPER_KEY)
    )
    assert paper_count == 1
    paper = (
        await test_db.execute(
            select(SalesTrainerExamPaper).where(
                SalesTrainerExamPaper.paper_key
                == seed_module.BUSINESS_SKILLS_PAPER_KEY
            )
        )
    ).scalars().one()
    paper_question_count = await test_db.scalar(
        select(func.count())
        .select_from(SalesTrainerUnitQuestion)
        .where(SalesTrainerUnitQuestion.unit_id == paper.unit_id)
    )
    assert paper_question_count == 4

    content_count = await test_db.scalar(
        select(func.count())
        .select_from(LearningContent)
        .where(LearningContent.source == "seed_newcomer_training_path")
    )
    assert content_count == 1

    question_count = await test_db.scalar(
        select(func.count())
        .select_from(QuestionItem)
        .where(QuestionItem.usage_scope == "sales_trainer")
    )
    assert question_count == 4


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_flushes_business_unit_before_paper(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    await seed_module.seed(test_db)

    paper = (
        await test_db.execute(
            select(SalesTrainerExamPaper).where(
                SalesTrainerExamPaper.paper_key
                == seed_module.BUSINESS_SKILLS_PAPER_KEY
            )
        )
    ).scalars().one()
    business_unit = await test_db.get(SalesTrainerUnit, paper.unit_id)

    assert business_unit is not None
    assert business_unit.config["path"]["module_key"] == "business_skills"


@pytest.mark.asyncio
async def test_verify_newcomer_training_path_ignores_unrelated_sales_trainer_questions(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()
    await seed_module.seed(test_db)
    category = (
        await test_db.execute(select(QuestionCategory).limit(1))
    ).scalars().one()
    extra_question = QuestionItem(
        question_id="unrelated-sales-trainer-question",
        category_id=category.category_id,
        title="其他销售训练题",
        stem="这道题不属于新人训练路径种子。",
        reference_answer="A",
        scoring_criteria={"question_type": "single_choice"},
        scoring_dimensions=["other"],
        usage_scope="sales_trainer",
        status="published",
    )
    test_db.add(extra_question)
    await test_db.commit()

    verified = await seed_module.verify(test_db)

    assert verified.verified is True


@pytest.mark.asyncio
async def test_verify_newcomer_training_path_reports_missing_baseline(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    with pytest.raises(seed_module.VerifyError, match="missing"):
        await seed_module.verify(test_db)

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PromptTemplate, User
from curriculum_practice.models import LearningContent, QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import NewcomerPathConfigPayload, NewcomerPathModuleConfig
from sales_trainer.services.asset_revision_service import SalesTrainerAssetRevisionService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


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

    prompt_count = await test_db.scalar(
        select(func.count())
        .select_from(PromptTemplate)
        .where(PromptTemplate.category == seed_module.AI_COACH_PROMPT_CATEGORY)
    )
    assert prompt_count == 1


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
    ai_coach = business_unit.config["path"]["ai_coach"]
    assert ai_coach["enabled"] is True
    assert ai_coach["allowed_interaction_types"] == ["single_choice", "multiple_choice"]
    assert ai_coach["proactive_coaching_enabled"] is True
    assert ai_coach["session_start_behavior"] == "plan_and_first_card"
    assert ai_coach["auto_advance_enabled"] is True
    assert "continue_drill" in ai_coach["allowed_next_actions"]
    assert ai_coach["prompt_template_id"]
    prompt = await test_db.get(PromptTemplate, ai_coach["prompt_template_id"])
    assert prompt is not None
    assert prompt.category == seed_module.AI_COACH_PROMPT_CATEGORY
    assert prompt.prompt_type == "stage"


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_syncs_active_ai_coach_prompt(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    await seed_module.seed(test_db)
    path_service = SalesTrainerPathConfigService(test_db)
    current = await path_service.get_config()
    stale_payload = _path_payload_with_stale_ai_coach_prompt(current["path"])
    owner = (
        await test_db.execute(
            select(User).where(User.email == seed_module.OWNER_EMAIL)
        )
    ).scalars().one()
    stale_revision = await SalesTrainerAssetRevisionService(
        test_db
    ).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=stale_payload.model_dump(mode="json"),
        actor=owner,
        change_class="semantic",
        reason="test stale AI coach config",
    )
    await test_db.commit()

    before = await path_service.get_config()
    before_business = _business_module(before["path"])
    assert before_business.ai_coach is not None
    assert before_business.ai_coach.prompt_template_id is None

    await seed_module.seed(test_db)

    after = await path_service.get_config()
    after_business = _business_module(after["path"])
    assert after_business.ai_coach is not None
    assert after_business.ai_coach.prompt_template_id
    assert after["active_revision_no"] > stale_revision.revision.revision_no


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
async def test_verify_newcomer_training_path_ignores_unselected_path_units(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()
    await seed_module.seed(test_db)
    test_db.add(
        SalesTrainerUnit(
            unit_id="unselected-newcomer-path-unit",
            name="未选择实验模块",
            description="不属于新人路径 canonical 模块集。",
            unit_type="quiz",
            status="published",
            config={
                "path": {
                    "enabled": True,
                    "path_key": seed_module.PATH_KEY,
                    "path_title": seed_module.PATH_TITLE,
                    "goal_title": seed_module.GOAL_TITLE,
                    "module_key": "experimental_extra",
                    "order_index": 99,
                    "completion_rule": "submitted",
                }
            },
        )
    )
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


def _path_payload_with_stale_ai_coach_prompt(
    raw_path: dict[str, object],
) -> NewcomerPathConfigPayload:
    payload = NewcomerPathConfigPayload.model_validate(raw_path)
    modules: list[NewcomerPathModuleConfig] = []
    for module in payload.modules:
        data = module.model_dump(mode="json")
        if module.module_key == "business_skills":
            ai_coach = dict(data.get("ai_coach") or {})
            ai_coach["enabled"] = True
            ai_coach["prompt_template_id"] = None
            data["ai_coach"] = ai_coach
        modules.append(NewcomerPathModuleConfig.model_validate(data))
    return NewcomerPathConfigPayload(
        path_key=payload.path_key,
        title=payload.title,
        goal_title=payload.goal_title,
        description=payload.description,
        enabled=payload.enabled,
        modules=modules,
    )


def _business_module(raw_path: dict[str, object]) -> NewcomerPathModuleConfig:
    payload = NewcomerPathConfigPayload.model_validate(raw_path)
    return next(
        module for module in payload.modules if module.module_key == "business_skills"
    )

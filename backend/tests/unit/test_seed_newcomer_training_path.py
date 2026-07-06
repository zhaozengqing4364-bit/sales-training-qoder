from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import pwd_context
from common.db.models import PromptTemplate, User
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import NewcomerPathConfigPayload, NewcomerPathModuleConfig
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
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


@pytest.fixture(autouse=True)
def _isolate_seed_material_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv(
        "SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path / "sales_trainer_materials")
    )


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
    assert unit_count == (
        len(seed_module.MODULE_KEYS) + len(seed_module.ELEVATOR_DURATION_OPTIONS) - 1
    )

    active_revision = await SalesTrainerAssetRevisionService(test_db).active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    assert active_revision is not None
    active_payload = NewcomerPathConfigPayload.model_validate(
        active_revision.payload_json
    )
    module_capability_keys = {
        module.module_key: module.capability_keys for module in active_payload.modules
    }
    for module_key, capability_keys in (
        seed_module.READINESS_CAPABILITY_KEYS_BY_MODULE.items()
    ):
        if module_key in module_capability_keys:
            assert module_capability_keys[module_key] == capability_keys
    elevator_module = next(
        module
        for module in active_payload.modules
        if module.module_key == "elevator_pitch"
    )
    assert elevator_module.enabled is True
    assert elevator_module.title == "第3关：金字塔演讲"
    assert elevator_module.completion_rule == "passed"
    assert elevator_module.scoring_prompt_id
    assert [
        option.duration_minutes for option in elevator_module.duration_options
    ] == list(seed_module.ELEVATOR_DURATION_OPTIONS)
    assert all(option.target_unit_id for option in elevator_module.duration_options)
    elevator_prompt = await test_db.get(
        SalesTrainerAudioScorePrompt,
        elevator_module.scoring_prompt_id,
    )
    assert elevator_prompt is not None
    assert elevator_prompt.status == "published"
    assert elevator_prompt.purpose == "elevator_pitch"
    assert len(elevator_prompt.learner_rubric["criteria"]) == 5

    paper_count = await test_db.scalar(
        select(func.count())
        .select_from(SalesTrainerExamPaper)
        .where(SalesTrainerExamPaper.paper_key == seed_module.BUSINESS_SKILLS_PAPER_KEY)
    )
    assert paper_count == 1
    paper = (
        (
            await test_db.execute(
                select(SalesTrainerExamPaper).where(
                    SalesTrainerExamPaper.paper_key
                    == seed_module.BUSINESS_SKILLS_PAPER_KEY
                )
            )
        )
        .scalars()
        .one()
    )
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
    content = (
        (
            await test_db.execute(
                select(LearningContent).where(
                    LearningContent.source == "seed_newcomer_training_path"
                )
            )
        )
        .scalars()
        .one()
    )
    chapter_count = await test_db.scalar(
        select(func.count())
        .select_from(LearningChapter)
        .where(LearningChapter.learning_content_id == content.learning_content_id)
    )
    assert chapter_count == 8
    active_training_pack = await SalesTrainerAssetRevisionService(
        test_db
    ).active_revision(
        resource_type=seed_module.BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=seed_module.DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    )
    assert active_training_pack is not None
    training_pack_payload = active_training_pack.payload_json
    assert training_pack_payload["learning_content_id"] == str(
        content.learning_content_id
    )
    assert training_pack_payload["learning_content_status"] == "published"
    assert training_pack_payload["original_chapter_count"] == 8
    assert len(training_pack_payload["capability_snapshot"]["capabilities"]) == 8
    assert len(training_pack_payload["capability_snapshot"]["chapter_bindings"]) == 8

    question_count = await test_db.scalar(
        select(func.count())
        .select_from(QuestionItem)
        .where(QuestionItem.usage_scope == "sales_trainer")
    )
    assert question_count == 4
    seeded_questions = (
        (
            await test_db.execute(
                select(QuestionItem).where(QuestionItem.usage_scope == "sales_trainer")
            )
        )
        .scalars()
        .all()
    )
    assert any(
        "respect_boundaries" in list(question.scoring_dimensions or [])
        for question in seeded_questions
    )

    prompt_count = await test_db.scalar(
        select(func.count())
        .select_from(PromptTemplate)
        .where(PromptTemplate.category == seed_module.AI_COACH_PROMPT_CATEGORY)
    )
    assert prompt_count == 2
    prompt_types = set(
        (
            await test_db.execute(
                select(PromptTemplate.prompt_type).where(
                    PromptTemplate.category == seed_module.AI_COACH_PROMPT_CATEGORY
                )
            )
        )
        .scalars()
        .all()
    )
    assert prompt_types == {"stage", "scoring"}
    path_service = SalesTrainerPathConfigService(test_db)
    current_path = await path_service.get_config()
    business_module = _business_module(current_path["path"])
    assert business_module.capability_keys == (
        seed_module.READINESS_CAPABILITY_KEYS_BY_MODULE[
            seed_module.BUSINESS_SKILLS_MODULE_KEY
        ]
    )
    assert len(business_module.learning_units) == 7
    assert business_module.learning_units[0].unit_key == "trust_foundation"
    assert business_module.learning_units[-1].source_chapter_orders == [8]
    assert business_module.ai_coach is not None
    assert business_module.ai_coach.auto_advance_enabled is False

    ppt_unit = (
        (
            await test_db.execute(
                select(SalesTrainerUnit).where(
                    SalesTrainerUnit.name == "PPT讲解",
                    SalesTrainerUnit.unit_type == "audio_scoring",
                )
            )
        )
        .scalars()
        .one()
    )
    ppt_audio = ppt_unit.config["audio"]
    assert ppt_unit.config["path"]["completion_rule"] == "passed"
    assert ppt_unit.config["path"]["capability_keys"] == (
        seed_module.READINESS_CAPABILITY_KEYS_BY_MODULE["ppt_explanation"]
    )
    assert ppt_audio["purpose"] == "ppt_pitch"
    assert ppt_audio["scoring_prompt_id"]
    ppt_prompt = await test_db.get(
        SalesTrainerAudioScorePrompt,
        ppt_audio["scoring_prompt_id"],
    )
    assert ppt_prompt is not None
    assert ppt_prompt.status == "published"
    assert ppt_prompt.purpose == "ppt_pitch"
    assert len(ppt_prompt.learner_rubric["criteria"]) == 6
    assert "dimension_scores" in ppt_prompt.output_schema
    assert ppt_unit.config["task_brief"]["title"] == "第1关：PPT讲解录音"
    ppt_bindings = ppt_unit.config["materials"]["bindings"]
    assert ppt_bindings[0]["required"] is True
    assert ppt_bindings[0]["confirmation_required"] is True
    ppt_material = await test_db.get(
        SalesTrainerMaterial, ppt_bindings[0]["material_id"]
    )
    assert ppt_material is not None
    assert ppt_material.status == "published"
    assert ppt_material.current_version_id
    ppt_version = await test_db.get(
        SalesTrainerMaterialVersion,
        ppt_material.current_version_id,
    )
    assert ppt_version is not None
    assert ppt_version.status == "published"
    assert ppt_version.content_type == "text/markdown"

    elevator_units = (
        (
            await test_db.execute(
                select(SalesTrainerUnit)
                .where(
                    SalesTrainerUnit.config["path"]["module_key"].as_string()
                    == "elevator_pitch",
                    SalesTrainerUnit.unit_type == "audio_scoring",
                )
                .order_by(SalesTrainerUnit.name.asc())
            )
        )
        .scalars()
        .all()
    )
    assert len(elevator_units) == len(seed_module.ELEVATOR_DURATION_OPTIONS)
    for unit in elevator_units:
        assert unit.config["path"]["enabled"] is True
        assert unit.config["path"]["completion_rule"] == "passed"
        assert unit.config["path"]["capability_keys"] == (
            seed_module.READINESS_CAPABILITY_KEYS_BY_MODULE["elevator_pitch"]
        )
        assert unit.config["audio"]["purpose"] == "elevator_pitch"
        assert (
            unit.config["audio"]["scoring_prompt_id"]
            == elevator_module.scoring_prompt_id
        )


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_archives_legacy_elevator_units(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()
    legacy_ids: list[str] = []
    for duration_minutes in seed_module.ELEVATOR_DURATION_OPTIONS:
        legacy_id = seed_module._uuid()
        legacy_ids.append(legacy_id)
        test_db.add(
            SalesTrainerUnit(
                unit_id=legacy_id,
                name=f"电梯演讲 · {duration_minutes} 分钟",
                description="旧版电梯演讲占位单元。",
                unit_type="audio_scoring",
                status="published",
                config={
                    "audio": {"purpose": "elevator_pitch", "pass_threshold": 70},
                    "path": {
                        "path_key": seed_module.PATH_KEY,
                        "module_key": "elevator_pitch",
                        "module_type": "audio_scoring_group",
                        "enabled": False,
                    },
                    "duration_minutes": duration_minutes,
                },
            )
        )
    await test_db.flush()

    await seed_module.seed(test_db)

    legacy_units = (
        (
            await test_db.execute(
                select(SalesTrainerUnit).where(SalesTrainerUnit.unit_id.in_(legacy_ids))
            )
        )
        .scalars()
        .all()
    )
    assert {unit.status for unit in legacy_units} == {"archived"}
    active_revision = await SalesTrainerAssetRevisionService(test_db).active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    assert active_revision is not None
    active_payload = NewcomerPathConfigPayload.model_validate(
        active_revision.payload_json
    )
    elevator_module = next(
        module
        for module in active_payload.modules
        if module.module_key == "elevator_pitch"
    )
    target_unit_ids = [
        option.target_unit_id for option in elevator_module.duration_options
    ]
    assert not set(target_unit_ids).intersection(legacy_ids)
    assert len(target_unit_ids) == len(set(target_unit_ids))


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_flushes_business_unit_before_paper(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    await seed_module.seed(test_db)

    paper = (
        (
            await test_db.execute(
                select(SalesTrainerExamPaper).where(
                    SalesTrainerExamPaper.paper_key
                    == seed_module.BUSINESS_SKILLS_PAPER_KEY
                )
            )
        )
        .scalars()
        .one()
    )
    business_unit = await test_db.get(SalesTrainerUnit, paper.unit_id)

    assert business_unit is not None
    assert business_unit.config["path"]["module_key"] == "business_skills"
    ai_coach = business_unit.config["path"]["ai_coach"]
    assert ai_coach["enabled"] is True
    assert ai_coach["allowed_interaction_types"] == [
        "single_choice",
        "multiple_choice",
        "short_answer",
    ]
    assert ai_coach["allowed_training_card_types"] == [
        "scenario_judgment",
        "expression_rewrite",
        "role_response",
    ]
    assert ai_coach["proactive_coaching_enabled"] is True
    assert ai_coach["session_start_behavior"] == "plan_then_wait"
    assert ai_coach["auto_advance_enabled"] is False
    assert ai_coach["max_cards_per_message"] == 1
    assert ai_coach["max_auto_steps_per_session"] == 5
    assert "continue_drill" in ai_coach["allowed_next_actions"]
    assert ai_coach["prompt_template_id"]
    assert ai_coach["scoring_prompt_template_id"]
    prompt = await test_db.get(PromptTemplate, ai_coach["prompt_template_id"])
    assert prompt is not None
    assert prompt.category == seed_module.AI_COACH_PROMPT_CATEGORY
    assert prompt.prompt_type == "stage"
    assert prompt.business_purpose == seed_module.AI_COACH_PROMPT_PURPOSE
    scoring_prompt = await test_db.get(
        PromptTemplate, ai_coach["scoring_prompt_template_id"]
    )
    assert scoring_prompt is not None
    assert scoring_prompt.category == seed_module.AI_COACH_PROMPT_CATEGORY
    assert scoring_prompt.prompt_type == "scoring"
    assert scoring_prompt.business_purpose == seed_module.AI_COACH_PROMPT_PURPOSE


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
        (
            await test_db.execute(
                select(User).where(User.email == seed_module.OWNER_EMAIL)
            )
        )
        .scalars()
        .one()
    )
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
async def test_seed_newcomer_training_path_backfills_business_learning_units(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    await seed_module.seed(test_db)
    path_service = SalesTrainerPathConfigService(test_db)
    current = await path_service.get_config()
    missing_units_payload = _path_payload_without_business_learning_units(
        current["path"]
    )
    owner = (
        (
            await test_db.execute(
                select(User).where(User.email == seed_module.OWNER_EMAIL)
            )
        )
        .scalars()
        .one()
    )
    stale_revision = await SalesTrainerAssetRevisionService(
        test_db
    ).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=missing_units_payload.model_dump(mode="json"),
        actor=owner,
        change_class="semantic",
        reason="test missing business etiquette learning units",
    )
    await test_db.commit()

    before = await path_service.get_config()
    before_business = _business_module(before["path"])
    assert before_business.learning_units == []

    await seed_module.seed(test_db)

    after = await path_service.get_config()
    after_business = _business_module(after["path"])
    assert len(after_business.learning_units) == 7
    assert after_business.learning_units[0].unit_key == "trust_foundation"
    assert after_business.learning_units[-1].unit_key == "integration_repair"
    assert after["active_revision_no"] > stale_revision.revision.revision_no


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_rebinds_article_without_chapters(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()

    await seed_module.seed(test_db)
    path_service = SalesTrainerPathConfigService(test_db)
    current = await path_service.get_config()
    empty_content = LearningContent(
        learning_content_id="business-etiquette-empty-content",
        title="空商务礼仪文章",
        summary="已发布但没有章节。",
        owner="test",
        source="test.empty_business_etiquette",
        status="published",
    )
    test_db.add(empty_content)
    await test_db.flush()
    broken_payload = _path_payload_with_business_article(
        current["path"],
        learning_content_id=empty_content.learning_content_id,
    )
    owner = (
        (
            await test_db.execute(
                select(User).where(User.email == seed_module.OWNER_EMAIL)
            )
        )
        .scalars()
        .one()
    )
    stale_revision = await SalesTrainerAssetRevisionService(
        test_db
    ).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=broken_payload.model_dump(mode="json"),
        actor=owner,
        change_class="binding",
        reason="test empty business etiquette article binding",
    )
    await test_db.commit()

    before = await path_service.get_config()
    before_business = _business_module(before["path"])
    assert before_business.learning_content_id == empty_content.learning_content_id

    await seed_module.seed(test_db)

    seed_content = (
        (
            await test_db.execute(
                select(LearningContent).where(
                    LearningContent.source == "seed_newcomer_training_path"
                )
            )
        )
        .scalars()
        .one()
    )
    after = await path_service.get_config()
    after_business = _business_module(after["path"])
    assert after_business.learning_content_id == seed_content.learning_content_id
    assert after["active_revision_no"] > stale_revision.revision.revision_no


@pytest.mark.asyncio
async def test_verify_newcomer_training_path_ignores_unrelated_sales_trainer_questions(
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()
    await seed_module.seed(test_db)
    category = (
        (await test_db.execute(select(QuestionCategory).limit(1))).scalars().one()
    )
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


@pytest.mark.asyncio
async def test_seed_newcomer_training_path_syncs_seed_account_passwords(
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
) -> None:
    seed_module = _load_seed_module()
    monkeypatch.setenv("SMOKE_ADMIN_PASSWORD", "SeedSmokePass123!")

    await seed_module.seed(test_db)

    for email in (
        seed_module.OWNER_EMAIL,
        seed_module.LEARNER_EMAIL,
        seed_module.MANAGER_EMAIL,
    ):
        user = (
            (await test_db.execute(select(User).where(User.email == email)))
            .scalars()
            .one()
        )
        assert pwd_context.verify("SeedSmokePass123!", user.hashed_password)

    monkeypatch.setenv("SMOKE_ADMIN_PASSWORD", "SeedSmokePass456!")
    await seed_module.seed(test_db)

    learner = (
        (
            await test_db.execute(
                select(User).where(User.email == seed_module.LEARNER_EMAIL)
            )
        )
        .scalars()
        .one()
    )
    assert pwd_context.verify("SeedSmokePass456!", learner.hashed_password)
    assert not pwd_context.verify("SeedSmokePass123!", learner.hashed_password)
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


def test_newcomer_seed_cli_defaults_to_verify_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_module = _load_seed_module()
    calls: list[bool] = []

    async def fake_run(*, verify_only: bool) -> tuple[int, None, None]:
        calls.append(verify_only)
        return 0, None, None

    monkeypatch.setattr(seed_module, "run", fake_run)

    exit_code = seed_module.main([])

    assert exit_code == 0
    assert calls == [True]


def test_newcomer_seed_cli_requires_apply_to_mutate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_module = _load_seed_module()
    calls: list[bool] = []

    async def fake_run(*, verify_only: bool) -> tuple[int, None, None]:
        calls.append(verify_only)
        return 0, None, None

    monkeypatch.setattr(seed_module, "run", fake_run)

    exit_code = seed_module.main(["--apply"])

    assert exit_code == 0
    assert calls == [False]


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


def _path_payload_without_business_learning_units(
    raw_path: dict[str, object],
) -> NewcomerPathConfigPayload:
    payload = NewcomerPathConfigPayload.model_validate(raw_path)
    modules: list[NewcomerPathModuleConfig] = []
    for module in payload.modules:
        data = module.model_dump(mode="json")
        if module.module_key == "business_skills":
            data["learning_units"] = []
        modules.append(NewcomerPathModuleConfig.model_validate(data))
    return NewcomerPathConfigPayload(
        path_key=payload.path_key,
        title=payload.title,
        goal_title=payload.goal_title,
        description=payload.description,
        enabled=payload.enabled,
        modules=modules,
    )


def _path_payload_with_business_article(
    raw_path: dict[str, object],
    *,
    learning_content_id: str,
) -> NewcomerPathConfigPayload:
    payload = NewcomerPathConfigPayload.model_validate(raw_path)
    modules: list[NewcomerPathModuleConfig] = []
    for module in payload.modules:
        data = module.model_dump(mode="json")
        if module.module_key == "business_skills":
            data["learning_content_id"] = learning_content_id
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

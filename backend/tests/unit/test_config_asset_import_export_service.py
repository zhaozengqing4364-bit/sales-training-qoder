"""Unit tests for config asset import/export services."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import select

from admin.config_assets.export_service import ConfigAssetExportService
from admin.config_assets.import_service import ConfigAssetImportService
from admin.config_assets.importers import IMPORTERS
from admin.config_assets.schema import validate_export_bundle
from admin.config_assets.types import AssetRef, ImportOptions
from agent.models import Agent, Persona, VoiceRuntimeProfile
from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import ConfigBundleAuditLog, ScoringRuleset, SystemLog, User
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import PracticeTemplate

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "docs/architecture/config-asset-export-v1.schema.json"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures/config_asset_export_v1_example.json"
)
PRESALES_EXPORT_PATH = (
    REPO_ROOT / "backend/config-assets/presales-cio-first-visit.export.json"
)


@pytest.fixture(scope="module")
def example_export() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def presales_export() -> dict[str, object]:
    return json.loads(PRESALES_EXPORT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def export_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def test_should_have_service_layer_importer_for_every_schema_asset_type() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    asset_types = set(schema["$defs"]["asset_type"]["enum"])

    assert set(IMPORTERS) == asset_types
    assert {
        name for name, importer in IMPORTERS.items() if "placeholder" in importer.__name__
    } == set()


async def _admin(test_db) -> User:
    user = User(
        wechat_user_id="config-asset-admin",
        name="Config Asset Admin",
        email="config-asset-admin@example.com",
        role="admin",
    )
    test_db.add(user)
    await test_db.flush()
    return user


async def _seed_bootstrap(test_db) -> None:
    test_db.add_all(
        [
            Agent(
                id="agent-bootstrap",
                name="Bootstrap Agent",
                description="agent",
                category="sales",
                status="published",
            ),
            VoiceRuntimeProfile(
                id="runtime-bootstrap",
                name="Bootstrap Runtime",
                is_active=True,
                voice_mode="stepfun_realtime",
                model_name="step-audio-2",
                voice_name="qingchunshaonv",
            ),
            ScoringRuleset(
                ruleset_id="ruleset-bootstrap",
                scenario_type="sales",
                version="sales-bootstrap",
                display_name="Bootstrap Ruleset",
                status="published",
                definition_json={"scenario_type": "sales"},
                is_active=True,
            ),
        ]
    )
    await test_db.flush()


@pytest.mark.asyncio
async def test_should_validate_export_output_from_service(
    test_db,
    example_export: dict[str, object],
    export_validator: Draft202012Validator,
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)
    test_db.add(
        KnowledgeBase(
            id="kb-export-1",
            name="presales-cio-first-visit-kb",
            description="kb",
            category="product",
            vector_collection="presales_cio_first_visit",
            status="active",
        )
    )
    await test_db.flush()

    bundle = await ConfigAssetExportService(test_db).export_bundle(
        asset_refs=[
            AssetRef(
                asset_type="knowledge_base",
                natural_key="presales-cio-first-visit-kb",
            )
        ],
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )
    validate_export_bundle(bundle)
    errors = sorted(export_validator.iter_errors(bundle), key=lambda item: list(item.path))
    assert not errors


@pytest.mark.asyncio
async def test_should_export_practice_template_with_natural_asset_refs(
    test_db,
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)
    persona = Persona(
        id="persona-export-1",
        name="Export Persona",
        category="customer",
        difficulty="medium",
        system_prompt="prompt",
        status="active",
    )
    test_db.add(persona)
    test_db.add(
        KnowledgeBase(
            id="kb-export-template",
            name="Export Knowledge",
            category="product",
            vector_collection="export_knowledge",
            status="active",
        )
    )
    test_db.add(
        PracticeTemplate(
            template_id="template-export-1",
            name="Export Template",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id="agent-bootstrap",
            persona_id="persona-export-1",
            runtime_profile_id="runtime-bootstrap",
            voice_mode="stepfun_realtime",
            scoring_ruleset_id="ruleset-bootstrap",
            knowledge_base_refs=["kb-export-template"],
            situation_pack_code="first_visit",
            status="draft",
        )
    )
    await test_db.flush()

    bundle = await ConfigAssetExportService(test_db).export_bundle(
        asset_refs=[
            AssetRef(
                asset_type="practice_template",
                natural_key="export-template",
            )
        ],
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    template_asset = bundle["assets"][0]
    asset_refs = template_asset["payload"]["asset_refs"]
    assert "agent_id" not in asset_refs
    assert "persona_id" not in asset_refs
    assert "runtime_profile_id" not in asset_refs
    assert "scoring_ruleset_id" not in asset_refs
    assert asset_refs["agent"]["natural_key"] == "bootstrap-agent"
    assert asset_refs["persona"]["natural_key"] == "export-persona"
    assert asset_refs["runtime_profile"]["natural_key"] == "bootstrap-runtime"
    assert asset_refs["scoring_ruleset"]["natural_key"] == "sales-bootstrap"
    assert asset_refs["knowledge_bases"] == [
        {
            "asset_type": "knowledge_base",
            "namespace": "default",
            "natural_key": "export-knowledge",
        }
    ]


@pytest.mark.asyncio
async def test_should_fail_template_import_without_explicit_required_refs(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)
    bundle = json.loads(json.dumps(example_export))
    template = next(
        asset for asset in bundle["assets"] if asset["asset_type"] == "practice_template"
    )
    template["payload"]["asset_refs"].pop("agent")

    report = await ConfigAssetImportService(test_db).import_bundle(
        bundle,
        options=ImportOptions(dry_run=True, conflict_strategy="new_version"),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    failed = [item for item in report.results if item.asset_type == "practice_template"]
    assert failed[0].status == "failed"
    assert failed[0].message == "missing dependency refs: agent"


@pytest.mark.asyncio
async def test_should_import_fixture_dry_run_without_writes(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)
    before_personas = len((await test_db.execute(select(Persona))).scalars().all())

    report = await ConfigAssetImportService(test_db).import_bundle(
        example_export,
        options=ImportOptions(dry_run=True, conflict_strategy="new_version"),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert report.dry_run is True
    assert report.imported == 4
    assert report.failed == 0
    assert report.audit_recorded is False
    after_personas = len((await test_db.execute(select(Persona))).scalars().all())
    assert after_personas == before_personas


@pytest.mark.asyncio
async def test_should_import_presales_cio_package_without_bootstrap_seed(
    test_db,
    presales_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)

    report = await ConfigAssetImportService(test_db).import_bundle(
        presales_export,
        options=ImportOptions(dry_run=False, conflict_strategy="new_version"),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert report.failed == 0, report.as_dict()
    template = (
        await test_db.execute(
            select(PracticeTemplate).where(
                PracticeTemplate.name == "制造业 CIO 首次拜访闭环训练"
            )
        )
    ).scalar_one()
    assert template.learning_content_id
    assert template.examiner_agent_id
    assert template.situation_pack_code == "first_visit"


@pytest.mark.asyncio
async def test_should_publish_presales_cio_package_after_import(
    test_db,
    presales_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)

    report = await ConfigAssetImportService(test_db).import_bundle(
        presales_export,
        options=ImportOptions(
            dry_run=False,
            conflict_strategy="new_version",
            publish_after_import=True,
            import_reason="unit-test-presales-publish",
        ),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert not [error for error in report.errors if error.startswith("[PUBLISH_")]


@pytest.mark.asyncio
async def test_should_record_import_audit_on_apply(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)

    report = await ConfigAssetImportService(test_db).import_bundle(
        example_export,
        options=ImportOptions(
            dry_run=False,
            conflict_strategy="new_version",
            import_reason="unit-test-import",
        ),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert report.audit_recorded is True
    assert report.imported >= 3
    logs = (
        await test_db.execute(
            select(SystemLog).where(SystemLog.action == "config_asset_import")
        )
    ).scalars().all()
    assert len(logs) == 1
    audits = (
        await test_db.execute(
            select(ConfigBundleAuditLog).where(
                ConfigBundleAuditLog.action == "create_draft"
            )
        )
    ).scalars().all()
    assert len(audits) >= 1


@pytest.mark.asyncio
async def test_should_reject_topology_mismatch(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    broken = json.loads(json.dumps(example_export))
    broken["topology_order"] = broken["topology_order"][:-1]

    report = await ConfigAssetImportService(test_db).import_bundle(
        broken,
        options=ImportOptions(dry_run=True),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert report.total == 0
    assert report.errors == ["[TOPOLOGY_MISMATCH] topology_order must match exported asset refs"]


@pytest.mark.asyncio
async def test_should_reject_package_internal_dependency_order_violation(
    test_db,
    presales_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    broken = json.loads(json.dumps(presales_export))
    broken["topology_order"] = [
        "practice_template:cio-first-visit-loop",
        *[
            ref
            for ref in broken["topology_order"]
            if ref != "practice_template:cio-first-visit-loop"
        ],
    ]

    report = await ConfigAssetImportService(test_db).import_bundle(
        broken,
        options=ImportOptions(dry_run=True),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert report.total == 0
    assert report.errors == [
        "[TOPOLOGY_DEPENDENCY_ORDER] agent:bootstrap-agent must be imported before practice_template:cio-first-visit-loop"
    ]


@pytest.mark.asyncio
async def test_should_import_practice_template_with_curriculum_plan_binding(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)

    report = await ConfigAssetImportService(test_db).import_bundle(
        example_export,
        options=ImportOptions(dry_run=False, conflict_strategy="new_version"),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    assert report.failed == 0, report.as_dict()
    template = (
        await test_db.execute(
            select(PracticeTemplate).where(
                PracticeTemplate.name == "制造业 CIO 首次拜访闭环训练"
            )
        )
    ).scalar_one()
    assert isinstance(template.curriculum_plan, dict)
    practice_stage = next(
        stage
        for stage in template.curriculum_plan["stages"]
        if stage["stage_type"] == "practice"
    )
    assert practice_stage["persona_id"] == template.persona_id
    assert practice_stage["situation_pack_code"] == "first_visit"
    assert report.failed == 0


@pytest.mark.asyncio
async def test_should_publish_config_bundle_asset_after_import(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)
    bundle = json.loads(json.dumps(example_export))
    bundle["assets"] = [
        asset
        for asset in bundle["assets"]
        if asset["asset_type"] in {"knowledge_base", "situation_pack", "persona"}
    ]
    bundle["topology_order"] = [
        ref
        for ref in bundle["topology_order"]
        if not ref.startswith("practice_template:")
    ]

    report = await ConfigAssetImportService(test_db).import_bundle(
        bundle,
        options=ImportOptions(
            dry_run=False,
            conflict_strategy="new_version",
            publish_after_import=True,
            import_reason="unit-test-publish",
        ),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    resolution = await BusinessRuleConfigService(test_db).resolve_active_config(
        ROLEPLAY_SITUATION_PACKS_KEY
    )
    packs = resolution.value.get("packs", []) if resolution.value else []
    imported_pack = next(
        item for item in packs if str(item.get("code")) == "first_visit"
    )
    assert imported_pack.get("status") == "published"
    publish_audits = (
        await test_db.execute(
            select(ConfigBundleAuditLog).where(
                ConfigBundleAuditLog.action == "publish"
            )
        )
    ).scalars().all()
    assert len(publish_audits) >= 1
    assert not any(error.startswith("[PUBLISH_") for error in report.errors)


@pytest.mark.asyncio
async def test_should_fail_import_when_conflict_strategy_is_fail(
    test_db,
    example_export: dict[str, object],
) -> None:
    admin = await _admin(test_db)
    await _seed_bootstrap(test_db)
    await ConfigAssetImportService(test_db).import_bundle(
        example_export,
        options=ImportOptions(dry_run=False, conflict_strategy="new_version"),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    second_report = await ConfigAssetImportService(test_db).import_bundle(
        example_export,
        options=ImportOptions(dry_run=False, conflict_strategy="fail"),
        actor_id=str(admin.user_id),
        actor_identifier=str(admin.email),
    )

    failed = [
        item for item in second_report.results if item.status == "failed"
    ]
    assert failed
    assert all(item.message == "natural_key already exists" for item in failed)

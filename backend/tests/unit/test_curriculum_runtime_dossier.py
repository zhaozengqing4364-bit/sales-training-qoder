from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import CaseItem, RoleProfile
from curriculum_practice.services.runtime_dossier import (
    CURRICULUM_RUNTIME_SNAPSHOT_STALE,
    CurriculumRuntimeDossierError,
    CurriculumRuntimeDossierHydrator,
    compose_curriculum_runtime_instructions,
)


@pytest.mark.asyncio
async def test_should_hydrate_case_item_and_role_profile_from_frozen_refs(
    test_db: AsyncSession,
) -> None:
    case_item = CaseItem(
        industry="制造业",
        company_profile="客户公司正在扩产，需要降低质检成本。",
        customer_role="采购总监",
        pain_points=["产线返工率高"],
        objections=["预算紧张"],
        hidden_information="隐藏预算不能进入初始 prompt",
        success_criteria=["确认试点范围"],
        allowed_disclosure_policy={"phases": [{"trigger": "ask", "disclose": "budget"}]},
        status="published",
        version=2,
        content_hash="case-hash-v2",
    )
    role_profile = RoleProfile(
        role_type="customer",
        role_name="谨慎采购总监",
        persona_ref="persona-1",
        communication_style="先质疑 ROI，再要求证据。",
        pressure_level="high",
        knowledge_boundary=["了解质检流程"],
        behavior_rules=["追问实施周期"],
        voice_style_hint="语速偏快",
        status="published",
        version=3,
        content_hash="role-hash-v3",
    )
    test_db.add_all([case_item, role_profile])
    await test_db.commit()

    dossier = await CurriculumRuntimeDossierHydrator(test_db).hydrate(
        {
            "roleplay_contract": {
                "schema_version": "roleplay_contract_v1",
                "contract_id": "sha256:test-contract",
                "source_track": "curriculum_template",
                "source_refs": [],
                "situation": {
                    "code": "first_visit",
                    "version": "v1",
                    "label": "首次拜访",
                },
                "relationship_context": {
                    "prior_interactions": "none",
                    "has_prior_meeting": False,
                    "has_seen_proposal": False,
                    "has_discussed_budget": False,
                    "has_existing_partnership": False,
                    "meeting_history_summary": None,
                },
                "sales_stage_policy": {
                    "stage_authority": "SalesStageCapability",
                    "initial_stage_hint": "opening",
                    "forbidden_stage_codes": ["price_negotiation"],
                    "stage_transition_notes": [],
                },
                "visible_information_scope": {
                    "initial_visible_keys": [
                        "industry",
                        "company_profile",
                        "customer_role",
                        "pain_points",
                    ],
                    "conditionally_visible_keys": ["hidden_information"],
                    "hidden_by_default_keys": ["hidden_information"],
                },
                "forbidden_claim_patterns": ["上次拜访"],
                "forbidden_topic_codes": [],
                "conflict_response_strategy": "customer_confused_correction",
                "behavior_rules_for_prompt_only": [],
                "disclosure_policy": {
                    "default_hidden": True,
                    "phases": [],
                    "never_disclose_keys": [],
                },
                "runtime_violation_policy": {
                    "relationship_history_contradiction": "cancel_or_regenerate_once",
                    "hidden_information_leak": "cancel_or_regenerate_once",
                    "forbidden_topic": "mark_and_continue",
                    "persona_style_drift": "mark_for_report",
                },
                "audit": {
                    "compiled_at": "2026-05-26T00:00:00Z",
                    "compiled_by": "actor-1",
                    "compiler_version": "roleplay_contract_compiler_v1",
                    "contract_hash": "sha256:test-contract",
                },
            },
            "content_assets": [
                {
                    "asset_type": "case_item",
                    "asset_id": str(case_item.case_item_id),
                    "version": 2,
                    "hash": "case-hash-v2",
                    "snapshot_label": "published",
                },
                {
                    "asset_type": "role_profile",
                    "asset_id": str(role_profile.role_profile_id),
                    "version": 3,
                    "hash": "role-hash-v3",
                    "snapshot_label": "published",
                },
            ]
        }
    )

    instructions = compose_curriculum_runtime_instructions("Persona base", dossier)
    assert "Persona base" in instructions
    assert "客户公司正在扩产" in instructions
    assert "谨慎采购总监" in instructions
    assert "确认试点范围" not in instructions
    assert "隐藏预算不能进入初始 prompt" not in instructions
    assert dossier.runtime_metrics()["case_item_count"] == 1
    assert dossier.runtime_metrics()["role_profile_count"] == 1
    assert dossier.runtime_metrics()["roleplay_contract"]["status"] == "ready"


@pytest.mark.asyncio
async def test_should_fail_when_frozen_case_hash_is_stale(
    test_db: AsyncSession,
) -> None:
    case_item = CaseItem(
        industry="制造业",
        company_profile="新版本公司背景",
        customer_role="采购总监",
        pain_points=["产线返工率高"],
        objections=["预算紧张"],
        hidden_information="隐藏信息",
        success_criteria=["确认试点范围"],
        allowed_disclosure_policy={"phases": [{"trigger": "ask", "disclose": "budget"}]},
        status="published",
        version=2,
        content_hash="case-hash-v2",
    )
    test_db.add(case_item)
    await test_db.commit()

    with pytest.raises(CurriculumRuntimeDossierError) as exc_info:
        await CurriculumRuntimeDossierHydrator(test_db).hydrate(
            {
                "content_assets": [
                    {
                        "asset_type": "case_item",
                        "asset_id": str(case_item.case_item_id),
                        "version": 1,
                        "hash": "case-hash-v1",
                        "snapshot_label": "published",
                    }
                ]
            }
        )

    assert exc_info.value.code == CURRICULUM_RUNTIME_SNAPSHOT_STALE


@pytest.mark.asyncio
async def test_should_not_fallback_to_latest_role_profile_when_ref_missing(
    test_db: AsyncSession,
) -> None:
    latest_role = RoleProfile(
        role_type="customer",
        role_name="最新角色",
        communication_style="最新风格",
        pressure_level="medium",
        knowledge_boundary=["最新知识"],
        behavior_rules=["最新行为"],
        voice_style_hint="最新声音",
        status="published",
        version=1,
        content_hash="latest-role-hash",
    )
    test_db.add(latest_role)
    await test_db.commit()

    with pytest.raises(CurriculumRuntimeDossierError):
        await CurriculumRuntimeDossierHydrator(test_db).hydrate(
            {
                "content_assets": [
                    {
                        "asset_type": "role_profile",
                        "asset_id": "missing-role",
                        "version": 1,
                        "hash": "missing-role-hash",
                        "snapshot_label": "published",
                    }
                ]
            }
        )

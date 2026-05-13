from __future__ import annotations

from json import dumps

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from curriculum_practice.schemas import PublishedTemplateRef
from curriculum_practice.services.snapshots import RuntimeSnapshotService
from evaluation.services.evaluation_run_service import (
    EvaluationRunService,
    extract_curriculum_lineage,
)
from evaluation.services.training_report_snapshot_service import (
    TrainingReportSnapshotService,
)


@pytest.mark.asyncio
async def test_should_propagate_stage_snapshots_without_hidden_information() -> None:
    service = RuntimeSnapshotService(reference_reader=_reference_reader)

    snapshot = await service.build_for_session(
        template_ref=PublishedTemplateRef(
            asset_id="parent-template",
            version=1,
            hash="sha256:parent-template",
        ),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
        created_at="2026-05-13T00:00:00+00:00",
    )
    lineage = extract_curriculum_lineage(snapshot.model_dump())
    encoded = dumps(lineage, ensure_ascii=False)

    assert lineage is not None
    assert lineage["stage_snapshots"]["template_stage_opening"]["template_ref"] == {
        "asset_type": "practice_template",
        "asset_id": "child-template",
        "version": 1,
        "hash": "sha256:child-template",
        "snapshot_label": "published",
    }
    assert "hidden_information" not in encoded
    assert "隐藏预算" not in encoded


@pytest.mark.asyncio
async def test_should_preserve_stage_snapshots_from_evaluation_run_to_report(
    test_db: AsyncSession,
) -> None:
    service = RuntimeSnapshotService(reference_reader=_reference_reader)
    snapshot = await service.build_for_session(
        template_ref=PublishedTemplateRef(
            asset_id="parent-template",
            version=1,
            hash="sha256:parent-template",
        ),
        training_task_ref={"id": "task-1", "scenario_type": "sales"},
        actor_id="actor-1",
        created_at="2026-05-13T00:00:00+00:00",
    )
    user = User(
        user_id="stage-lineage-user",
        wechat_user_id="stage-lineage-user",
        name="Stage Lineage User",
        role="user",
    )
    scenario = Scenario(
        scenario_id="stage-lineage-scenario",
        scenario_type="sales",
        name="stage lineage scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id="stage-lineage-session",
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        curriculum_snapshot=snapshot.model_dump(mode="json"),
    )
    test_db.add_all([user, scenario, session])
    await test_db.commit()

    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "session_evidence_projection"},
    )
    report = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "stable report"},
        ruleset_source="session_evidence_projection",
        ruleset_version="session_evidence_projection_v1",
        score_basis="persisted_snapshot",
        non_evaluable_reason=None,
    )

    expected_lineage = run.input_evidence_reference["curriculum_lineage"]
    assert report.report_payload["lineage"] == expected_lineage
    assert report.report_payload["lineage"]["stage_snapshots"] == expected_lineage[
        "stage_snapshots"
    ]


def _reference_reader(asset_type: str, asset_id: str) -> object | None:
    references: dict[tuple[str, str], object] = {
        ("practice_template", "parent-template"): {
            "template_id": "parent-template",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:parent-template",
            "scenario_type": "sales",
            "mode": "customer_roleplay",
            "agent_id": "agent-1",
            "persona_id": "persona-1",
            "runtime_profile_id": "runtime-1",
            "voice_mode": "stepfun_realtime",
            "scoring_ruleset_id": "ruleset-1",
            "knowledge_base_refs": [],
            "curriculum_plan": {
                "name": "多阶段训练",
                "stages": [
                    {
                        "template_stage_key": "template_stage_opening",
                        "order": 1,
                        "name": "开场",
                        "template_ref": {
                            "asset_type": "practice_template",
                            "asset_id": "child-template",
                            "version": 1,
                            "hash": "sha256:child-template",
                            "snapshot_label": "published",
                        },
                        "completion_policy": {
                            "min_score": 7.0,
                            "min_rounds": 2,
                            "max_duration_seconds": 600,
                        },
                        "failure_policy": "retry_current",
                        "prerequisites": [],
                    }
                ],
            },
        },
        ("practice_template", "child-template"): {
            "template_id": "child-template",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:child-template",
            "scenario_type": "sales",
            "mode": "customer_roleplay",
            "agent_id": "agent-1",
            "persona_id": "persona-1",
            "runtime_profile_id": "runtime-1",
            "voice_mode": "stepfun_realtime",
            "scoring_ruleset_id": "ruleset-1",
            "knowledge_base_refs": [],
            "case_item_id": "case-1",
        },
        ("voice_runtime_profile", "runtime-1"): {
            "id": "runtime-1",
            "is_active": True,
            "voice_mode": "stepfun_realtime",
            "model_name": "step-audio-2",
        },
        ("scoring_ruleset", "ruleset-1"): {
            "ruleset_id": "ruleset-1",
            "status": "published",
            "version": "sales-v1",
        },
        ("case_item", "case-1"): {
            "case_item_id": "case-1",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:case",
            "hidden_information": "隐藏预算",
        },
    }
    return references.get((asset_type, asset_id))

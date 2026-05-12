from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ConfigBundle,
    ConfigVersion,
    PracticeSession,
    Scenario,
    User,
)
from curriculum_practice.schemas import (
    CurriculumRuntimeRef,
    CurriculumRuntimeSnapshot,
    CurriculumTrainingTaskRef,
    CurriculumVersionRef,
)
from evaluation.services.evaluation_run_service import EvaluationRunService
from evaluation.services.training_report_snapshot_service import (
    TrainingReportSnapshotService,
)


def _snapshot() -> dict:
    return CurriculumRuntimeSnapshot(
        snapshot_hash="sha256:session-snapshot-v1",
        created_at="2026-05-12T00:00:00+00:00",
        training_task=CurriculumTrainingTaskRef(
            id="session-report-immutable",
            scenario_type="sales",
        ),
        practice_template=CurriculumVersionRef(
            asset_type="practice_template",
            asset_id="template-report",
            version=1,
            hash="sha256:template-v1",
            snapshot_label="published",
        ),
        content_assets=[
            CurriculumVersionRef(
                asset_type="knowledge_base",
                asset_id="kb-report-v1",
                version=1,
                hash="sha256:kb-v1",
                snapshot_label="legacy_unversioned",
            )
        ],
        rubric=CurriculumVersionRef(
            asset_type="scoring_ruleset",
            asset_id="ruleset-report",
            version="sales-v1",
            hash="sha256:ruleset-v1",
            snapshot_label="published",
        ),
        runtime=CurriculumRuntimeRef(
            agent_id="agent-report",
            persona_id="persona-report",
            runtime_profile_id="runtime-report",
            voice_policy_snapshot_hash="sha256:voice-policy-v1",
            instruction_contract_hash="sha256:instruction-v1",
        ),
        llm_nodes=[],
    ).model_dump()


@pytest.mark.asyncio
async def test_should_keep_report_lineage_snapshot_immutable_after_content_and_config_changes(
    test_db: AsyncSession,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"report_lineage_{uuid.uuid4().hex[:8]}",
        name="Report Lineage User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"report_lineage_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        curriculum_snapshot=_snapshot(),
    )
    bundle = ConfigBundle(
        bundle_id=str(uuid.uuid4()),
        bundle_key=f"sales.report.{uuid.uuid4().hex[:8]}",
        domain="scoring",
        display_name="Sales report bundle",
        adapter_key="sales_report",
        read_path="/admin/config-bundles/report",
        admin_entry="/admin/config-center",
        enabled=True,
    )
    version = ConfigVersion(
        version_id=str(uuid.uuid4()),
        bundle_id=bundle.bundle_id,
        source_config_id=str(uuid.uuid4()),
        version_number=1,
        version_label="sales-report-v1",
        status="published",
        snapshot_json={"scoring": {"ruleset": "sales-v1"}},
        source_updated_at=datetime.now(UTC),
    )
    test_db.add_all([user, scenario, session, bundle, version])
    await test_db.commit()

    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "session_evidence_projection"},
        config_bundle_id=str(bundle.bundle_id),
        config_version_id=str(version.version_id),
    )
    report = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "curriculum report"},
        ruleset_source="session_evidence_projection",
        ruleset_version="session_evidence_projection_v1",
        score_basis="persisted_snapshot",
        non_evaluable_reason=None,
    )
    original_report_payload = deepcopy(report.report_payload)
    original_config_snapshot = deepcopy(report.config_bundle_snapshot)

    mutated_snapshot = deepcopy(session.curriculum_snapshot)
    mutated_snapshot["practice_template"]["version"] = 2
    mutated_snapshot["practice_template"]["hash"] = "sha256:template-v2"
    mutated_snapshot["content_assets"][0]["hash"] = "sha256:kb-v2"
    session.curriculum_snapshot = mutated_snapshot
    version.version_number = 2
    version.version_label = "sales-report-v2"
    version.snapshot_json = {"scoring": {"ruleset": "sales-v2"}}
    await test_db.commit()

    unchanged = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "new report"},
        ruleset_source="latest_projection",
        ruleset_version="latest_projection_v2",
        score_basis="latest_config",
        non_evaluable_reason=None,
    )

    assert unchanged.snapshot_id == report.snapshot_id
    assert unchanged.report_payload == original_report_payload
    assert unchanged.config_bundle_snapshot == original_config_snapshot

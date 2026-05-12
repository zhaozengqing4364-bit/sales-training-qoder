from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
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
        snapshot_hash="sha256:snapshot-flow",
        created_at="2026-05-12T00:00:00+00:00",
        training_task=CurriculumTrainingTaskRef(
            id="session-flow",
            scenario_type="sales",
        ),
        practice_template=CurriculumVersionRef(
            asset_type="practice_template",
            asset_id="template-flow",
            version=1,
            hash="sha256:template-flow",
            snapshot_label="published",
        ),
        content_assets=[],
        rubric=CurriculumVersionRef(
            asset_type="scoring_ruleset",
            asset_id="ruleset-flow",
            version="sales-v1",
            hash="sha256:ruleset-flow",
            snapshot_label="published",
        ),
        runtime=CurriculumRuntimeRef(
            agent_id="agent-flow",
            persona_id="persona-flow",
            runtime_profile_id="runtime-flow",
            voice_policy_snapshot_hash="sha256:voice-policy-flow",
            instruction_contract_hash="sha256:instruction-flow",
        ),
        llm_nodes=[],
    ).model_dump()


@pytest.mark.asyncio
async def test_curriculum_lineage_flows_from_session_to_run_and_report_snapshot(
    test_db: AsyncSession,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"curriculum_lineage_{uuid.uuid4().hex[:8]}",
        name="Curriculum Lineage User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"curriculum_lineage_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        curriculum_snapshot=_snapshot(),
    )
    test_db.add_all([user, scenario, session])
    await test_db.commit()

    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "session_evidence_projection"},
    )
    report = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "curriculum lineage report"},
        ruleset_source="session_evidence_projection",
        ruleset_version="session_evidence_projection_v1",
        score_basis="persisted_snapshot",
        non_evaluable_reason=None,
    )

    assert "curriculum_lineage" in run.input_evidence_reference
    assert run.input_evidence_reference["curriculum_lineage"]["content_assets"] == []
    assert run.input_evidence_reference["curriculum_lineage"]["llm_suggestions"] == []
    assert report.report_payload["lineage"] == run.input_evidence_reference[
        "curriculum_lineage"
    ]

from __future__ import annotations

import uuid
from copy import deepcopy

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from evaluation.services.evaluation_run_service import (
    EvaluationRunService,
    extract_curriculum_lineage,
)
from evaluation.services.training_report_snapshot_service import (
    TrainingReportSnapshotService,
)


def _curriculum_snapshot() -> dict:
    return {
        "practice_template": {
            "asset_type": "practice_template",
            "asset_id": "template-1",
            "version": 2,
            "hash": "sha256:template",
            "snapshot_label": "published",
        },
        "content_assets": {
            "knowledge_bases": [
                {
                    "asset_type": "knowledge_base",
                    "asset_id": "kb-1",
                    "version": 1,
                    "hash": "sha256:kb",
                    "snapshot_label": "published",
                }
            ]
        },
        "rubric": {
            "asset_type": "scoring_ruleset",
            "asset_id": "ruleset-1",
            "version": "sales-v1",
            "hash": "sha256:ruleset",
            "snapshot_label": "published",
        },
        "llm_suggestions": {
            "prompt_contract": {
                "asset_type": "prompt_contract",
                "asset_id": "prompt-1",
                "version": 1,
                "hash": "sha256:prompt",
                "snapshot_label": "published",
            }
        },
        "runtime": {"runtime_profile_id": "runtime-1"},
    }


async def _create_practice_session(
    db: AsyncSession,
    *,
    curriculum_snapshot: dict | None,
) -> PracticeSession:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"lineage_{uuid.uuid4().hex[:8]}",
        name="Lineage User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"lineage_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        curriculum_snapshot=curriculum_snapshot,
    )
    db.add_all([user, scenario, session])
    await db.commit()
    return session


def test_should_extract_required_curriculum_lineage_from_snapshot() -> None:
    snapshot = _curriculum_snapshot()
    original = deepcopy(snapshot)

    lineage = extract_curriculum_lineage(snapshot)

    assert lineage is not None
    assert lineage == {
        "practice_template": snapshot["practice_template"],
        "content_assets": snapshot["content_assets"],
        "rubric": snapshot["rubric"],
        "llm_suggestions": snapshot["llm_suggestions"],
    }
    assert snapshot == original
    assert lineage is not snapshot
    assert lineage["practice_template"] is not snapshot["practice_template"]


@pytest.mark.asyncio
async def test_should_attach_curriculum_lineage_to_new_evaluation_run(
    test_db: AsyncSession,
) -> None:
    snapshot = _curriculum_snapshot()
    session = await _create_practice_session(
        test_db,
        curriculum_snapshot=snapshot,
    )

    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "session_evidence_projection"},
    )

    assert run.input_evidence_reference == {
        "source": "session_evidence_projection",
        "curriculum_lineage": extract_curriculum_lineage(snapshot),
    }


@pytest.mark.asyncio
async def test_should_copy_evaluation_run_curriculum_lineage_to_report_payload(
    test_db: AsyncSession,
) -> None:
    snapshot = _curriculum_snapshot()
    session = await _create_practice_session(
        test_db,
        curriculum_snapshot=snapshot,
    )
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

    assert report.report_payload == {
        "summary": "stable report",
        "lineage": run.input_evidence_reference["curriculum_lineage"],
    }


@pytest.mark.asyncio
async def test_should_keep_legacy_run_and_report_compatible_without_snapshot(
    test_db: AsyncSession,
) -> None:
    session = await _create_practice_session(
        test_db,
        curriculum_snapshot=None,
    )

    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "legacy_projection"},
    )
    report = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "legacy report"},
        ruleset_source=None,
        ruleset_version=None,
        score_basis=None,
        non_evaluable_reason=None,
    )

    assert run.input_evidence_reference == {"source": "legacy_projection"}
    assert report.report_payload == {"summary": "legacy report"}


@pytest.mark.asyncio
async def test_should_not_recalculate_existing_report_lineage_when_run_changes(
    test_db: AsyncSession,
) -> None:
    session = await _create_practice_session(
        test_db,
        curriculum_snapshot=None,
    )
    run = await EvaluationRunService(test_db).ensure_pending_run(
        session_id=str(session.session_id),
        input_evidence_reference={"source": "legacy_projection"},
    )
    existing = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "legacy report"},
        ruleset_source=None,
        ruleset_version=None,
        score_basis=None,
        non_evaluable_reason=None,
    )
    run.input_evidence_reference = {
        "source": "legacy_projection",
        "curriculum_lineage": extract_curriculum_lineage(_curriculum_snapshot()),
    }
    await test_db.commit()

    unchanged = await TrainingReportSnapshotService(test_db).ensure_snapshot(
        evaluation_run_id=str(run.run_id),
        report_payload={"summary": "new report"},
        ruleset_source="session_evidence_projection",
        ruleset_version="session_evidence_projection_v1",
        score_basis="persisted_snapshot",
        non_evaluable_reason=None,
    )

    assert unchanged.snapshot_id == existing.snapshot_id
    assert unchanged.report_payload == {"summary": "legacy report"}

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from sales_trainer.services.readiness_dossier_projection import (
    ReadinessDossierError,
    ReadinessDossierProjection,
)


def _completed_journey() -> dict[str, object]:
    return {
        "learner_id": "learner-1",
        "learner_name": "学员一",
        "department": "销售一部",
        "path_key": "newcomer_training_path_v1",
        "path_revision_id": "revision-1",
        "path_revision_no": 1,
        "source": "active_revision",
        "training_stage": "passed",
        "overall_progress": {
            "total_modules": 1,
            "completed_modules": 1,
            "passed_modules": 1,
            "failed_modules": 0,
            "needs_remediation_modules": 0,
        },
        "modules": [
            {
                "module_key": "ppt_explanation",
                "title": "PPT 讲解",
                "kind": "audio_submission",
                "module_type": "audio_scoring",
                "required": True,
                "completion_satisfied": True,
                "status": "passed",
                "passed": True,
                "outcome_history": [
                    {
                        "record_type": "audio_submission",
                        "source_record_id": "audio-1",
                        "status": "passed",
                        "score": 90,
                        "max_score": 100,
                        "passed": True,
                        "submitted_at": "2026-07-11T08:00:00Z",
                    }
                ],
                "diagnostics": [],
                "unmet_reasons": [],
            }
        ],
        "learning_topics": [],
        "diagnostics": [],
    }


def test_readiness_projection_is_deterministic_and_does_not_mutate_sources() -> None:
    projection = ReadinessDossierProjection()
    journey = _completed_journey()
    original = deepcopy(journey)
    generated_at = datetime(2026, 7, 11, 9, 30, tzinfo=UTC)

    dossier = projection._dossier_payload(
        journey,  # type: ignore[arg-type]
        records=[],
        review_actions=[],
        generated_at=generated_at,
    )

    assert journey == original
    assert dossier["generated_at"] is generated_at
    assert dossier["status"] == "pending_review"
    assert dossier["summary"]["evidence_count"] == 1
    assert dossier["evidence"][0]["evidence_id"] == "audio_submission:audio-1"
    assert dossier["realtime_gate"]["locked"] is True


def test_readiness_projection_approval_is_fail_closed() -> None:
    projection = ReadinessDossierProjection()

    with pytest.raises(ReadinessDossierError) as blocked:
        projection._ensure_dossier_can_be_approved(
            {"status": "blocked_by_config", "summary": {"evidence_count": 1}}
        )
    with pytest.raises(ReadinessDossierError) as missing_evidence:
        projection._ensure_dossier_can_be_approved(
            {"status": "pending_review", "summary": {"evidence_count": 0}}
        )

    assert blocked.value.code == "[READINESS_DOSSIER_CONFIG_BLOCKED]"
    assert missing_evidence.value.code == "[READINESS_DOSSIER_NOT_READY]"


def test_readiness_projection_groups_workbench_by_review_state() -> None:
    projection = ReadinessDossierProjection()
    base = {
        "learner": {"learner_id": "learner-1"},
        "competencies": [],
        "summary": {"evidence_count": 1},
        "next_actions": [{"target_path": "/readiness/learner-1"}],
        "latest_review_action": None,
    }
    dossiers = [
        {**base, "status": "pending_review"},
        {**base, "status": "approved"},
        {
            **base,
            "status": "needs_remediation",
            "latest_review_action": {
                "decision": "require_retraining",
                "retraining_task": {"status": "pending"},
            },
        },
    ]

    groups = projection._workbench_groups(dossiers)

    assert groups["pending_review"]["count"] == 1
    assert groups["approved"]["count"] == 1
    assert groups["needs_retraining"]["count"] == 1

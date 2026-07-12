from __future__ import annotations

import uuid

import pytest

from common.db.models import User
from sales_trainer.models import NewcomerTrainingActivityAttempt
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.journey_service import NewcomerJourneyService
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService
from sales_trainer.services.readiness_dossier_service import (
    ReadinessDossierError,
    ReadinessDossierService,
)


def _user(role: str, *, department: str = "销售一部") -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"readiness-{role}-{suffix}",
        name=f"Readiness {role}",
        email=f"readiness-{role}-{suffix}@example.com",
        department=department,
        role=role,
        is_active=True,
    )


def _payload() -> TrainingPathPayload:
    return TrainingPathPayload.model_validate(
        {
            "title": "可配置新人训练",
            "phases": [
                {
                    "phase_id": "phase-product",
                    "title": "产品能力",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-product-c",
                            "title": "产品 C",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "activity-product-c-assignment",
                                    "type": "assignment",
                                    "title": "提交产品 C 总结",
                                    "order_index": 1,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


async def _seed_completed_attempt(test_db):
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.flush()

    revisions = TrainingPathRevisionService(test_db)
    await revisions.save_draft(payload=_payload(), actor=admin, reason="readiness test")
    await revisions.publish(actor=admin, reason="readiness test")
    journey = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=learner
    )
    attempt = NewcomerTrainingActivityAttempt(
        enrollment_id=journey.enrollment_id,
        path_revision_id=journey.path_revision_id,
        activity_id="activity-product-c-assignment",
        activity_type="assignment",
        attempt_no=1,
        status="completed",
        passed=True,
        client_token=f"readiness-{uuid.uuid4()}",
        activity_snapshot={
            "activity_id": "activity-product-c-assignment",
            "type": "assignment",
            "title": "提交产品 C 总结",
            "context": {
                "phase_id": "phase-product",
                "phase_title": "产品能力",
                "module_id": "module-product-c",
                "module_title": "产品 C",
            },
        },
        result_snapshot={
            "capability_scores": [
                {"capability_key": "structured_explanation", "score": 88}
            ]
        },
        evidence_type="assignment_submission",
        evidence_id=f"assignment-{uuid.uuid4()}",
    )
    test_db.add(attempt)
    await test_db.commit()
    return admin, learner, attempt


@pytest.mark.asyncio
async def test_should_project_readiness_from_frozen_activity_identity(test_db) -> None:
    admin, learner, attempt = await _seed_completed_attempt(test_db)

    dossier = await ReadinessDossierService(test_db).get_dossier(
        str(learner.user_id), viewer=admin, team_department=None
    )

    assert dossier["status"] == "pending_review"
    assert dossier["evidence"][0]["activity_id"] == attempt.activity_id
    assert dossier["evidence"][0]["module_title"] == "产品 C"
    assert dossier["competencies"] == [
        {"capability_key": "structured_explanation", "score": 88.0}
    ]
    assert "module_key" not in dossier["evidence"][0]


@pytest.mark.asyncio
async def test_should_apply_review_decision_without_changing_attempt(test_db) -> None:
    admin, learner, attempt = await _seed_completed_attempt(test_db)
    service = ReadinessDossierService(test_db)

    action = await service.create_review_action(
        str(learner.user_id),
        actor=admin,
        team_department=None,
        decision="approve",
        reason="证据完整。",
        source_evidence_ids=[str(attempt.evidence_id)],
    )
    dossier = await service.get_dossier(
        str(learner.user_id), viewer=admin, team_department=None
    )

    assert action["decision"] == "approve"
    assert dossier["status"] == "approved"
    assert dossier["latest_review_action"]["decision"] == "approve"
    assert (await test_db.get(NewcomerTrainingActivityAttempt, attempt.attempt_id)).status == (
        "completed"
    )


@pytest.mark.asyncio
async def test_should_reject_unknown_activity_evidence(test_db) -> None:
    admin, learner, _ = await _seed_completed_attempt(test_db)

    with pytest.raises(ReadinessDossierError) as error:
        await ReadinessDossierService(test_db).create_review_action(
            str(learner.user_id),
            actor=admin,
            team_department=None,
            decision="retrain",
            reason="需要补练。",
            source_evidence_ids=["not-owned"],
        )

    assert error.value.code == "[READINESS_DOSSIER_EVIDENCE_INVALID]"


@pytest.mark.asyncio
async def test_should_enforce_department_scope(test_db) -> None:
    admin, learner, _ = await _seed_completed_attempt(test_db)

    with pytest.raises(ReadinessDossierError) as error:
        await ReadinessDossierService(test_db).get_dossier(
            str(learner.user_id), viewer=admin, team_department="其他部门"
        )

    assert error.value.status_code == 404

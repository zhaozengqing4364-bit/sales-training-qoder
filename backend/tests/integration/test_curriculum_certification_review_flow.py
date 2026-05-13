from __future__ import annotations

import sys
import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_api_stub = types.ModuleType("chromadb.api")
    chromadb_models_stub = types.ModuleType("chromadb.api.models")
    chromadb_collection_stub = types.ModuleType("chromadb.api.models.Collection")
    chromadb_config_stub = types.ModuleType("chromadb.config")

    class ClientAPI:
        pass

    class Collection:
        pass

    class Settings:
        def __init__(self, **_kwargs: object) -> None:
            pass

    setattr(chromadb_stub, "PersistentClient", lambda *_args, **_kwargs: None)
    setattr(chromadb_api_stub, "ClientAPI", ClientAPI)
    setattr(chromadb_collection_stub, "Collection", Collection)
    setattr(chromadb_config_stub, "Settings", Settings)
    sys.modules["chromadb"] = chromadb_stub
    sys.modules["chromadb.api"] = chromadb_api_stub
    sys.modules["chromadb.api.models"] = chromadb_models_stub
    sys.modules["chromadb.api.models.Collection"] = chromadb_collection_stub
    sys.modules["chromadb.config"] = chromadb_config_stub

if "websockets" not in sys.modules:
    websockets_stub = types.ModuleType("websockets")
    exceptions_stub = types.ModuleType("websockets.exceptions")

    class ConnectionClosed(Exception):
        pass

    setattr(exceptions_stub, "ConnectionClosed", ConnectionClosed)
    sys.modules["websockets"] = websockets_stub
    sys.modules["websockets.exceptions"] = exceptions_stub

if "prometheus_client" not in sys.modules:
    prometheus_stub = types.ModuleType("prometheus_client")
    exposition_stub = types.ModuleType("prometheus_client.exposition")

    class _Metric:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def labels(self, *_args: object, **_kwargs: object) -> _Metric:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            pass

        def observe(self, *_args: object, **_kwargs: object) -> None:
            pass

        def set(self, *_args: object, **_kwargs: object) -> None:
            pass

        def info(self, *_args: object, **_kwargs: object) -> None:
            pass

    setattr(prometheus_stub, "Counter", _Metric)
    setattr(prometheus_stub, "Gauge", _Metric)
    setattr(prometheus_stub, "Histogram", _Metric)
    setattr(prometheus_stub, "Info", _Metric)
    setattr(exposition_stub, "generate_latest", lambda: b"")
    sys.modules["prometheus_client"] = prometheus_stub
    sys.modules["prometheus_client.exposition"] = exposition_stub

if "oss2" not in sys.modules:
    oss2_stub = types.ModuleType("oss2")

    class Auth:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    class Bucket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def sign_url(self, *_args: object, **_kwargs: object) -> str:
            return "https://oss.test/signed"

    setattr(oss2_stub, "Auth", Auth)
    setattr(oss2_stub, "Bucket", Bucket)
    sys.modules["oss2"] = oss2_stub

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import (
    ComprehensiveReport,
    PracticeSession,
    RetrainingTask,
    Scenario,
    TrainingTask,
    User,
)
from curriculum_practice.models import PracticeTemplate


async def _create_user(
    db: AsyncSession,
    *,
    role: str,
    email_prefix: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{email_prefix}_{uuid.uuid4().hex[:8]}",
        name=email_prefix,
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _certification_plan(template_id: str) -> dict[str, object]:
    return {
        "name": "新人认证路径",
        "stages": [
            {
                "template_stage_key": "template_stage_onboarding_certification_review",
                "order": 1,
                "name": "新人认证主管复核",
                "template_ref": {
                    "asset_type": "practice_template",
                    "asset_id": template_id,
                    "version": 1,
                    "hash": "hash-certification-queue",
                    "snapshot_label": "published",
                },
                "completion_policy": {
                    "min_score": 8,
                    "min_rounds": 1,
                    "max_duration_seconds": 600,
                },
                "prerequisites": [],
            }
        ],
    }


CERTIFICATION_SESSION_ID = "77777777-7777-7777-7777-777777777777"
ORDINARY_SESSION_ID = "88888888-8888-8888-8888-888888888888"


async def _create_completed_template_session(
    db: AsyncSession,
    *,
    user: User,
    template: PracticeTemplate,
    session_id: str,
    score: float,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=f"scenario-{session_id}",
        scenario_type="sales",
        name=f"scenario-{session_id}",
        is_active=True,
    )
    stage_snapshots = {}
    if isinstance(template.curriculum_plan, dict):
        stage_snapshots = {
            "template_stage_onboarding_certification_review": {
                "template_ref": {
                    "asset_id": str(template.template_id),
                    "version": 1,
                },
                "runtime_payload": {"mode": template.mode},
            }
        }
    session = PracticeSession(
        session_id=session_id,
        user_id=str(user.user_id),
        scenario_id=scenario.scenario_id,
        practice_template_id=str(template.template_id),
        curriculum_snapshot={
            "curriculum_plan": template.curriculum_plan,
            "stage_snapshots": stage_snapshots,
        },
        runtime_state={
            "thinking_log": [
                {
                    "turn_index": 2,
                    "template_stage_key": "template_stage_onboarding_certification_review",
                    "response_id": "resp-cert-review",
                    "thinking_text": "Reviewer-only certification reasoning",
                    "captured_at": "2026-05-13T10:00:00Z",
                }
            ]
        },
        status="completed",
        report_status="completed",
        logic_score=score,
        accuracy_score=score,
        completeness_score=score,
        effectiveness_snapshot={"evaluable": True},
        start_time=datetime.now(UTC) - timedelta(minutes=20),
        end_time=datetime.now(UTC),
    )
    report = ComprehensiveReport(
        session_id=session_id,
        overall_score=score,
        dimension_scores=[{"name": "价值逻辑", "score": score}],
        key_strengths=["能完成基础表达"],
        key_improvements=["认证证据需要主管复核"],
        recommendations=["等待主管给出认证结论"],
        stage_summaries=[{"stage_key": "template_stage_onboarding_certification_review"}],
    )
    message = ConversationMessage(
        session_id=session_id,
        turn_number=1,
        role="user",
        content="这是认证复核训练的关键证据。",
        timestamp=datetime.now(UTC),
        transcript_metadata={"stage_key": "template_stage_onboarding_certification_review"},
    )
    db.add_all([scenario, session, report, message])
    await db.commit()
    await db.refresh(session)
    return session


@pytest.mark.asyncio
async def test_certification_session_enters_review_queue_after_report_generation(
    async_client,
    test_db: AsyncSession,
) -> None:
    supervisor = await _create_user(
        test_db, role="admin", email_prefix="cert-queue-supervisor"
    )
    learner = await _create_user(
        test_db, role="user", email_prefix="cert-queue-learner"
    )
    certification_template = PracticeTemplate(
        template_id="55555555-5555-5555-5555-555555555555",
        name="新人认证复核模板",
        description="certification review template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-certification-queue",
        curriculum_plan=_certification_plan("55555555-5555-5555-5555-555555555555"),
    )
    ordinary_template = PracticeTemplate(
        template_id="66666666-6666-6666-6666-666666666666",
        name="普通专项训练模板",
        description="ordinary practice template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-ordinary",
    )
    test_db.add_all([certification_template, ordinary_template])
    await test_db.commit()
    certification_session = await _create_completed_template_session(
        test_db,
        user=learner,
        template=certification_template,
        session_id=CERTIFICATION_SESSION_ID,
        score=72.0,
    )
    await _create_completed_template_session(
        test_db,
        user=learner,
        template=ordinary_template,
        session_id=ORDINARY_SESSION_ID,
        score=91.0,
    )

    response = await async_client.get(
        "/api/v1/supervisor/certification-review-queue",
        headers=_auth_headers(supervisor),
    )

    assert response.status_code == 200, response.json()
    items = response.json()["data"]
    assert [item["session_id"] for item in items] == [
        str(certification_session.session_id)
    ]
    item = items[0]
    assert item["outcome"] == "pending"
    assert item["learner"]["user_id"] == str(learner.user_id)
    assert item["curriculum"]["practice_template"]["template_id"] == str(
        certification_template.template_id
    )
    assert "template_stage_onboarding_certification_review" in item["curriculum"][
        "stage_snapshots"
    ]
    assert item["score"] == 72.0
    assert item["evidence"]["transcript_anchors"][0]["quote"] == "这是认证复核训练的关键证据。"
    assert item["evidence"]["thinking_evidence"][0]["thinking_text"] == (
        "Reviewer-only certification reasoning"
    )
    assert item["submitted_at"] is not None


@pytest.mark.asyncio
async def test_retrain_action_creates_followup_training_task_and_audit_metadata(
    async_client,
    test_db: AsyncSession,
) -> None:
    supervisor = await _create_user(
        test_db, role="admin", email_prefix="cert-retrain-supervisor"
    )
    learner = await _create_user(
        test_db, role="user", email_prefix="cert-retrain-learner"
    )
    certification_template = PracticeTemplate(
        template_id="99999999-9999-9999-9999-999999999999",
        name="复训认证模板",
        description="certification retraining template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-certification-queue",
        curriculum_plan=_certification_plan("99999999-9999-9999-9999-999999999999"),
    )
    test_db.add(certification_template)
    await test_db.commit()
    await _create_completed_template_session(
        test_db,
        user=learner,
        template=certification_template,
        session_id="99999999-0000-0000-0000-999999999999",
        score=64.0,
    )
    queue_response = await async_client.get(
        "/api/v1/supervisor/certification-review-queue",
        headers=_auth_headers(supervisor),
    )
    review_id = queue_response.json()["data"][0]["review_id"]

    response = await async_client.patch(
        f"/api/v1/supervisor/reviews/{review_id}/decision",
        headers=_auth_headers(supervisor),
        json={
            "decision": "needs_retraining",
            "readiness_status": "shadow_only",
            "comment": "认证未通过，需要复训价值逻辑。",
            "required_retraining": True,
            "skill_dimension": "价值逻辑",
            "audit_metadata": {
                "reason": "认证未通过，需要复训价值逻辑。",
                "report_id": "99999999-0000-0000-0000-999999999999",
                "reviewed_at": "2026-05-13T10:30:00Z",
            },
        },
    )

    assert response.status_code == 200, response.json()
    review = response.json()["data"]
    assert review["decision"] == "needs_retraining"
    assert review["audit_metadata"]["reason"] == "认证未通过，需要复训价值逻辑。"
    assert review["audit_metadata"]["report_id"] == "99999999-0000-0000-0000-999999999999"
    assert review["audit_metadata"]["reviewer_id"] == str(supervisor.user_id)
    assert review["retraining_tasks"][0]["skill_dimension"] == "价值逻辑"
    assert review["retraining_tasks"][0]["training_task_id"] is not None

    retraining_task = await test_db.get(
        RetrainingTask, review["retraining_tasks"][0]["task_id"]
    )
    assert retraining_task is not None
    followup_task = await test_db.get(TrainingTask, retraining_task.training_task_id)
    assert followup_task is not None
    assert followup_task.assignee_id == str(learner.user_id)
    assert followup_task.practice_template_id == str(certification_template.template_id)
    assert followup_task.source == "supervisor_certification_retrain"

    refreshed_queue = await async_client.get(
        "/api/v1/supervisor/certification-review-queue",
        headers=_auth_headers(supervisor),
    )
    assert refreshed_queue.status_code == 200, refreshed_queue.json()
    assert all(
        item["session_id"] != "99999999-0000-0000-0000-999999999999"
        for item in refreshed_queue.json()["data"]
    )

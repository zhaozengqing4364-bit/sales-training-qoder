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
from common.db.models import (
    EvaluationRun,
    PracticeSession,
    Scenario,
    TrainingReportSnapshot,
    User,
)
from curriculum_practice.models import PracticeTemplate


async def _create_user(test_db: AsyncSession, *, role: str, name: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{name}_{uuid.uuid4().hex[:8]}",
        name=name,
        email=f"{name}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_can_load_curriculum_analytics_dashboard(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin = await _create_user(test_db, role="admin", name="curriculum-analytics-admin")
    learner = await _create_user(test_db, role="user", name="curriculum-analytics-learner")
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="课程分析 API 场景",
        is_active=True,
    )
    template = PracticeTemplate(
        template_id="55555555-4444-3333-2222-111111111111",
        name="课程分析 API 模板",
        description="api dashboard template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-api",
        persona_id="persona-api",
        runtime_profile_id="runtime-api",
        scoring_ruleset_id="ruleset-api",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-api-template",
    )
    session_id = "12121212-3434-5656-7878-909090909090"
    started_at = datetime.now(UTC) - timedelta(days=2)
    session = PracticeSession(
        session_id=session_id,
        user_id=str(learner.user_id),
        scenario_id=str(scenario.scenario_id),
        practice_template_id=str(template.template_id),
        curriculum_snapshot={
            "practice_template": {
                "template_id": str(template.template_id),
                "name": template.name,
                "version": 1,
                "content_hash": "hash-api-template",
            }
        },
        status="completed",
        report_status="completed",
        logic_score=66,
        accuracy_score=76,
        completeness_score=86,
        start_time=started_at,
        end_time=started_at + timedelta(minutes=6),
        effectiveness_snapshot={"evaluable": True},
    )
    evaluation_run = EvaluationRun(
        run_id=str(uuid.uuid4()),
        session_id=session_id,
        status="succeeded",
        input_evidence_reference={"source": "api-test"},
        result_payload={"overall_score": 76},
    )
    snapshot = TrainingReportSnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session_id,
        evaluation_run_id=str(evaluation_run.run_id),
        report_payload={
            "overall_score": 76,
            "dimension_scores": [{"name": "价值表达", "score": 66}],
        },
        evidence_completeness={"conversation": True},
        generated_at=started_at + timedelta(minutes=7),
    )
    test_db.add_all([scenario, template, session, evaluation_run, snapshot])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/analytics/curriculum",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["summary"]["completed_count"] == 1
    assert payload["data"]["summary"]["top_weak_dimension"] == "价值表达"
    assert payload["data"]["heatmap"][0]["template_name"] == "课程分析 API 模板"
    assert payload["data"]["score_trend"][0]["sample_count"] == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_load_curriculum_analytics_dashboard(
    async_client,
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", name="curriculum-analytics-denied")

    response = await async_client.get(
        "/api/v1/admin/analytics/curriculum",
        headers=_auth_headers(learner),
    )

    assert response.status_code in {401, 403}

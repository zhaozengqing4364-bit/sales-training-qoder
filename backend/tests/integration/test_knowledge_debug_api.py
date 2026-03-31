from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import agent.models  # noqa: F401
from common.auth.service import create_access_token
from common.db.models import (
    KnowledgeAnswerRun,
    KnowledgeAnswerRunStep,
    PracticeSession,
    Scenario,
    User,
)


async def _create_sales_session(
    db_session: AsyncSession,
    *,
    user_id: str,
    name: str,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=name,
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        voice_mode="stepfun_realtime",
    )
    db_session.add_all([scenario, session])
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def _create_user(
    db_session: AsyncSession,
    *,
    role: str,
    email_prefix: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"wechat_{email_prefix}_{uuid.uuid4().hex[:8]}",
        name=f"{role.title()} User",
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _seed_run(
    db_session: AsyncSession,
    *,
    session_id: str,
    query_text: str,
    answerability: str,
    final_status: str,
    created_at: datetime,
    blocked_reason: str | None = None,
) -> KnowledgeAnswerRun:
    run = KnowledgeAnswerRun(
        id=str(uuid.uuid4()),
        session_id=session_id,
        config_version_id=None,
        entrypoint="stepfun_realtime",
        query_text=query_text,
        answerability=answerability,
        final_status=final_status,
        blocked_reason=blocked_reason,
        citations_json=[
            {
                "document_title": "产品手册",
                "snippet": "石犀科技提供销售训练能力。",
            }
        ],
        retrieval_summary_json={
            "executed_query_count": 2,
            "hit_count": 1,
        },
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run


async def _seed_step(
    db_session: AsyncSession,
    *,
    run_id: str,
    step_order: int,
    step_name: str,
    status: str,
    duration_ms: int,
    created_at: datetime,
) -> KnowledgeAnswerRunStep:
    step = KnowledgeAnswerRunStep(
        id=str(uuid.uuid4()),
        answer_run_id=run_id,
        step_name=step_name,
        step_order=step_order,
        status=status,
        input_payload={"query": "请介绍一下石犀科技"},
        output_payload={"status": status, "step_name": step_name},
        duration_ms=duration_ms,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(step)
    await db_session.commit()
    await db_session.refresh(step)
    return step


@pytest.mark.asyncio
async def test_list_answer_runs_returns_latest_first_with_step_counts(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    practice_session = await _create_sales_session(
        test_db,
        user_id=str(test_user.user_id),
        name="knowledge_debug_list",
    )
    older_run = await _seed_run(
        test_db,
        session_id=str(practice_session.session_id),
        query_text="旧问题",
        answerability="partial",
        final_status="completed",
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    latest_run = await _seed_run(
        test_db,
        session_id=str(practice_session.session_id),
        query_text="新问题",
        answerability="sufficient",
        final_status="completed",
        created_at=datetime.now(UTC),
    )
    await _seed_step(
        test_db,
        run_id=older_run.id,
        step_order=1,
        step_name="resolve",
        status="completed",
        duration_ms=5,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    await _seed_step(
        test_db,
        run_id=latest_run.id,
        step_order=1,
        step_name="resolve",
        status="completed",
        duration_ms=3,
        created_at=datetime.now(UTC),
    )
    await _seed_step(
        test_db,
        run_id=latest_run.id,
        step_order=2,
        step_name="assemble",
        status="completed",
        duration_ms=4,
        created_at=datetime.now(UTC),
    )

    response = await async_client.get(
        "/api/v1/knowledge-debug/runs",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["trace_id"]
    assert [item["id"] for item in body["data"]["items"]] == [latest_run.id, older_run.id]
    assert body["data"]["items"][0]["query_text"] == "新问题"
    assert body["data"]["items"][0]["step_count"] == 2
    assert body["data"]["items"][1]["step_count"] == 1


@pytest.mark.asyncio
async def test_get_answer_run_detail_returns_audit_fields(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    practice_session = await _create_sales_session(
        test_db,
        user_id=str(test_user.user_id),
        name="knowledge_debug_detail",
    )
    run = await _seed_run(
        test_db,
        session_id=str(practice_session.session_id),
        query_text="请介绍一下石犀科技",
        answerability="blocked",
        final_status="blocked",
        blocked_reason="retrieval_timeout",
        created_at=datetime.now(UTC),
    )

    response = await async_client.get(
        f"/api/v1/knowledge-debug/runs/{run.id}",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["id"] == run.id
    assert body["data"]["session_id"] == str(practice_session.session_id)
    assert body["data"]["answerability"] == "blocked"
    assert body["data"]["final_status"] == "blocked"
    assert body["data"]["blocked_reason"] == "retrieval_timeout"
    assert body["data"]["retrieval_summary"]["executed_query_count"] == 2
    assert body["data"]["citations"][0]["document_title"] == "产品手册"


@pytest.mark.asyncio
async def test_get_answer_run_steps_returns_ordered_breakdown(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()

    practice_session = await _create_sales_session(
        test_db,
        user_id=str(test_user.user_id),
        name="knowledge_debug_steps",
    )
    run = await _seed_run(
        test_db,
        session_id=str(practice_session.session_id),
        query_text="步骤调试问题",
        answerability="partial",
        final_status="completed",
        created_at=datetime.now(UTC),
    )
    await _seed_step(
        test_db,
        run_id=run.id,
        step_order=2,
        step_name="assemble",
        status="completed",
        duration_ms=7,
        created_at=datetime.now(UTC),
    )
    await _seed_step(
        test_db,
        run_id=run.id,
        step_order=1,
        step_name="resolve",
        status="completed",
        duration_ms=5,
        created_at=datetime.now(UTC),
    )

    response = await async_client.get(
        f"/api/v1/knowledge-debug/runs/{run.id}/steps",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["run_id"] == run.id
    assert [item["step_order"] for item in body["data"]["items"]] == [1, 2]
    assert [item["step_name"] for item in body["data"]["items"]] == ["resolve", "assemble"]
    assert body["data"]["items"][0]["input_payload"]["query"] == "请介绍一下石犀科技"


@pytest.mark.asyncio
async def test_knowledge_debug_api_requires_admin_or_support_role(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "user"
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/knowledge-debug/runs",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_answer_run_detail_returns_404_for_unknown_run(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "support"
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/knowledge-debug/runs/{uuid.uuid4()}",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[KNOWLEDGE_RUN_NOT_FOUND]"

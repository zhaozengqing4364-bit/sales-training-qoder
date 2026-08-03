from __future__ import annotations

import uuid

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from readiness.models import ReadinessCommandAudit


async def _create_user(test_db: AsyncSession, *, role: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"readiness-{role}-{uuid.uuid4().hex[:8]}",
        name=f"readiness-{role}",
        email=f"readiness-{role}-{uuid.uuid4().hex[:6]}@example.com",
        role=role,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readiness_queue_enforces_role_capabilities_and_audits_denials(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    content_admin = await _create_user(test_db, role="content_admin")
    operations = await _create_user(test_db, role="operations")
    training_manager = await _create_user(test_db, role="support")
    platform_admin = await _create_user(test_db, role="admin")

    for denied_user in (content_admin, operations):
        denied = await async_client.get(
            "/api/v1/admin/newcomer-training/reviews",
            headers=_auth_headers(denied_user),
        )
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"] == "[READINESS_PERMISSION_DENIED]"

    manager_response = await async_client.get(
        "/api/v1/admin/newcomer-training/reviews",
        headers=_auth_headers(training_manager),
    )
    assert manager_response.status_code == 200, manager_response.text
    assert manager_response.json()["data"]["contract_version"] == "1"

    admin_response = await async_client.get(
        "/api/v1/admin/newcomer-training/reviews",
        headers=_auth_headers(platform_admin),
    )
    assert admin_response.status_code == 200, admin_response.text

    denied_audits = list(
        (
            await test_db.scalars(
                select(ReadinessCommandAudit).where(
                    ReadinessCommandAudit.command == "list_review_queue",
                    ReadinessCommandAudit.result == "denied",
                )
            )
        ).all()
    )
    assert {item.actor_id for item in denied_audits} >= {
        str(content_admin.user_id),
        str(operations.user_id),
    }


def test_readiness_http_contract_is_registered_once() -> None:
    from foundation_readiness_api import admin_router, learner_router

    route_contracts = [
        (route.path, method)
        for router in (learner_router, admin_router)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
    ]
    methods_by_path = set(route_contracts)
    required = {
        ("/newcomer-training/dossier", "GET"),
        ("/newcomer-training/dossier/appeals", "POST"),
        ("/admin/newcomer-training/reviews", "GET"),
        ("/admin/newcomer-training/reviews/{dossier_id}", "GET"),
        (
            "/admin/newcomer-training/reviews/{dossier_id}/commands/preview-exception",
            "POST",
        ),
        (
            "/admin/newcomer-training/reviews/{dossier_id}/commands/record-decision",
            "POST",
        ),
        (
            "/admin/newcomer-training/reviews/{dossier_id}/commands/assign-retraining",
            "POST",
        ),
    }
    assert required <= methods_by_path
    for route_contract in required:
        assert route_contracts.count(route_contract) == 1

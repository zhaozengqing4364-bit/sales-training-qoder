from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.services.provisioning import ProvisioningService
from common.db.models import User


async def _admin(db: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"provision-admin-{uuid.uuid4().hex}",
        name="Provision Admin",
        email=f"admin-{uuid.uuid4().hex}@example.com",
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_preview_and_confirm_fifty_rows_is_idempotent(test_db: AsyncSession) -> None:
    admin = await _admin(test_db)
    lines = ["name,email,role,team_code,team_name,primary_leader_email"]
    lines.append("Lead,lead50@example.com,training_manager,east-50,East 50,lead50@example.com")
    for index in range(49):
        lines.append(
            f"Learner {index},learner{index}@example.com,user,east-50,East 50,lead50@example.com"
        )
    service = ProvisioningService(test_db)
    preview = await service.preview(
        csv_text="\n".join(lines),
        source_name="fifty.csv",
        idempotency_key="fifty-rows-idempotency",
        actor=admin,
    )
    assert len(preview["rows"]) == 50
    assert all(row["status"] == "valid" for row in preview["rows"])

    result = await service.confirm(
        batch_id=preview["batch_id"],
        actor=admin,
        team_overrides={},
    )
    assert result["status"] == "completed"
    assert len(result["credentials"]) == 50
    assert len({item["temporary_password"] for item in result["credentials"]}) == 50

    repeated = await service.confirm(
        batch_id=preview["batch_id"], actor=admin, team_overrides={}
    )
    assert repeated["status"] == "completed"
    assert repeated["credentials"] == []
    assert int(await test_db.scalar(select(func.count()).select_from(User))) == 51


@pytest.mark.asyncio
async def test_team_failure_rolls_back_only_that_team(test_db: AsyncSession) -> None:
    admin = await _admin(test_db)
    csv_text = "\n".join(
        [
            "name,email,role,team_code,team_name,primary_leader_email",
            "Good Lead,good-lead@example.com,training_manager,good,Good,good-lead@example.com",
            "Good User,good-user@example.com,user,good,Good,good-lead@example.com",
            "Bad User,bad-user@example.com,user,bad,Bad,missing-lead@example.com",
        ]
    )
    service = ProvisioningService(test_db)
    preview = await service.preview(
        csv_text=csv_text,
        source_name="partial.csv",
        idempotency_key="partial-team-idempotency",
        actor=admin,
    )
    result = await service.confirm(
        batch_id=preview["batch_id"], actor=admin, team_overrides={}
    )
    assert result["status"] == "partially_completed"
    assert {item["email"] for item in result["credentials"]} == {
        "good-lead@example.com",
        "good-user@example.com",
    }
    assert await test_db.scalar(
        select(User.user_id).where(User.email == "bad-user@example.com")
    ) is None

    leader = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"retry-lead-{uuid.uuid4().hex}",
        name="Retry Lead",
        email="retry-lead@example.com",
        role="training_manager",
        is_active=True,
    )
    test_db.add(leader)
    await test_db.commit()
    retried = await service.confirm(
        batch_id=preview["batch_id"],
        actor=admin,
        team_overrides={"bad": {"primary_leader_email": leader.email}},
        retry_team_codes={"bad"},
    )
    assert retried["status"] == "completed"
    assert [item["email"] for item in retried["credentials"]] == [
        "bad-user@example.com"
    ]
    assert (
        int(
            await test_db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.email == "good-user@example.com")
            )
        )
        == 1
    )

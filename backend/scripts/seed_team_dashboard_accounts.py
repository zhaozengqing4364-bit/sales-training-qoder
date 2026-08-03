"""为本地团队看板创建显式 Team 关系测试账号。

该脚本只用于开发/测试环境。账号、团队、主成员关系和组长关系都可重复执行，
不再写入已退役的 ``User.department`` 字段。
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401
import sales_trainer.models as _sales_trainer_models  # noqa: F401
from common.auth.service import pwd_context
from common.db.models import Team, User
from common.db.session import AsyncSessionLocal
from common.teams.service import TeamService

DEFAULT_PASSWORD = os.getenv(
    "TEAM_DASHBOARD_SEED_PASSWORD", "local-team-only-2026"
).strip()

SEED_ACCOUNTS: tuple[dict[str, str], ...] = (
    {
        "email": "admin.one@team.com",
        "name": "王管理员",
        "role": "admin",
        "purpose": "本地测试管理员",
    },
    {
        "email": "manager.one@team.com",
        "name": "张经理",
        "role": "training_manager",
        "team_code": "sales-one",
        "team_name": "销售一组",
        "team_role": "leader",
        "purpose": "销售一组组长",
    },
    {
        "email": "learner.one@team.com",
        "name": "学员甲",
        "role": "user",
        "team_code": "sales-one",
        "team_name": "销售一组",
        "team_role": "member",
        "purpose": "销售一组学员",
    },
    {
        "email": "learner.two@team.com",
        "name": "学员乙",
        "role": "user",
        "team_code": "sales-one",
        "team_name": "销售一组",
        "team_role": "member",
        "purpose": "销售一组学员",
    },
    {
        "email": "manager.two@team.com",
        "name": "李经理",
        "role": "training_manager",
        "team_code": "sales-two",
        "team_name": "销售二组",
        "team_role": "leader",
        "purpose": "销售二组组长",
    },
    {
        "email": "learner.three@team.com",
        "name": "学员丙",
        "role": "user",
        "team_code": "sales-two",
        "team_name": "销售二组",
        "team_role": "member",
        "purpose": "销售二组学员，用于验证跨 Team 隔离",
    },
)


async def upsert_account(db, account: dict[str, str]) -> tuple[User, bool]:
    email = account["email"].strip().lower()
    user = await db.scalar(select(User).where(User.email == email))
    created = user is None
    now = datetime.now(UTC)
    if user is None:
        user = User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=f"seed_team_{email}",
            name=account["name"],
            email=email,
            role=account["role"],
            is_active=True,
            created_at=now,
        )
        db.add(user)

    user.name = account["name"]
    user.role = account["role"]
    user.hashed_password = pwd_context.hash(DEFAULT_PASSWORD)
    user.credential_status = "active"
    user.temporary_password_expires_at = None
    user.password_changed_at = now
    user.is_active = True
    if not user.wechat_user_id:
        user.wechat_user_id = f"seed_team_{email}"
    await db.flush()
    return user, created


async def upsert_team(db, *, code: str, name: str, actor: User) -> Team:
    team = await db.scalar(select(Team).where(Team.code == code))
    if team is None:
        return await TeamService(db).create_team(code=code, name=name, actor=actor)
    team.name = name
    team.is_active = True
    await db.flush()
    return team


async def run() -> None:
    if os.getenv("ENVIRONMENT", "development").strip().lower() not in {
        "development",
        "test",
    }:
        raise RuntimeError("seed_team_dashboard_accounts 只允许在 development/test 运行")
    if len(DEFAULT_PASSWORD) < 12:
        raise RuntimeError("TEAM_DASHBOARD_SEED_PASSWORD 至少需要 12 个字符")

    async with AsyncSessionLocal() as db:
        users: dict[str, User] = {}
        created_by_email: dict[str, bool] = {}
        for account in SEED_ACCOUNTS:
            user, created = await upsert_account(db, account)
            users[account["email"]] = user
            created_by_email[account["email"]] = created

        actor = users["admin.one@team.com"]
        teams: dict[str, Team] = {}
        for account in SEED_ACCOUNTS:
            team_code = account.get("team_code")
            if not team_code or team_code in teams:
                continue
            teams[team_code] = await upsert_team(
                db,
                code=team_code,
                name=account["team_name"],
                actor=actor,
            )

        team_service = TeamService(db)
        for account in SEED_ACCOUNTS:
            team_code = account.get("team_code")
            team_role = account.get("team_role")
            if not team_code or not team_role:
                continue
            user = users[account["email"]]
            team = teams[team_code]
            if team_role == "leader":
                await team_service.assign_leader(team=team, leader=user, actor=actor)
            else:
                await team_service.assign_primary_member(
                    team=team,
                    learner=user,
                    actor=actor,
                )

        await db.commit()

    print("团队看板测试数据已准备完成。")
    print(
        "账号使用受管本地密码；可通过 "
        "TEAM_DASHBOARD_SEED_PASSWORD 覆盖开发默认值。"
    )
    for account in SEED_ACCOUNTS:
        action = "新建" if created_by_email[account["email"]] else "更新"
        team_name = account.get("team_name", "未分配团队")
        print(
            f"[{action}] {account['email']} · {account['name']} · "
            f"{team_name} · {account['purpose']}"
        )


if __name__ == "__main__":
    asyncio.run(run())

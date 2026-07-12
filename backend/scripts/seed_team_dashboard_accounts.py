"""为团队学习看板测试创建多角色 seed 账号。

幂等：按 email 查找，存在则更新 role/department/hashed_password，不存在则创建。
仅 dev/测试环境使用，依赖 development 环境的 DB。

运行：
    cd backend && .venv/bin/python scripts/seed_team_dashboard_accounts.py

所有账号密码统一为 123456。
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.auth.service import pwd_context
from common.db.models import User
from common.db.session import AsyncSessionLocal

DEFAULT_PASSWORD = "123456"

# 账号清单：email(name 3 词) / name / department / role
# 覆盖：主测 training_manager、同部门 learner、跨部门 learner、空部门 manager、learner 角色对照
SEED_ACCOUNTS: list[dict[str, str | None]] = [
    {
        "email": "manager.one@team.com",
        "name": "张经理",
        "department": "销售一部",
        "role": "training_manager",
        "purpose": "主测账号：登录看 /team 看板，看到本部门学员",
    },
    {
        "email": "learner.one@team.com",
        "name": "学员甲",
        "department": "销售一部",
        "role": "user",
        "purpose": "同部门学员：被 manager.one 看到（DB role=user，无 learner）",
    },
    {
        "email": "learner.two@team.com",
        "name": "学员乙",
        "department": "销售一部",
        "role": "user",
        "purpose": "同部门学员：被 manager.one 看到",
    },
    {
        "email": "learner.three@team.com",
        "name": "学员丙",
        "department": "销售二部",
        "role": "user",
        "purpose": "跨部门学员：不应被 manager.one 看到（验证 AC5 权限隔离）",
    },
    {
        "email": "manager.two@team.com",
        "name": "李经理",
        "department": "",  # 空 department
        "role": "training_manager",
        "purpose": "空部门 manager：登录看板显示空部门提示（验证 AC8）",
    },
    {
        "email": "admin.one@team.com",
        "name": "王管理员",
        "department": "运营部",
        "role": "admin",
        "purpose": "管理员：登录看 / 管理后台，可创建/管理其他账号",
    },
]


async def upsert_account(db, account: dict[str, str | None]) -> tuple[User, bool]:
    """幂等 upsert 单个账号。返回 (user, created)。"""
    email = account["email"]
    result = await db.execute(
        User.__table__.select().where(User.__table__.c.email == email)
    )
    row = result.mappings().first()

    hashed_password = pwd_context.hash(DEFAULT_PASSWORD)
    department = account.get("department") or None
    wechat_user_id = f"seed_team_{email}"  # 稳定占位，保证 unique 且可重复执行

    if row is None:
        user = User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=wechat_user_id,
            name=account["name"],
            email=email,
            department=department,
            role=account["role"],
            hashed_password=hashed_password,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user, True

    # 已存在则更新关键字段（保持 user_id 不变）
    await db.execute(
        User.__table__.update()
        .where(User.__table__.c.email == email)
        .values(
            name=account["name"],
            department=department,
            role=account["role"],
            hashed_password=hashed_password,
            is_active=True,
            wechat_user_id=wechat_user_id,
        )
        .returning(User.__table__.c.user_id)
    )
    await db.commit()
    # 重新查询拿回完整对象
    refreshed = await db.execute(
        User.__table__.select().where(User.__table__.c.email == email)
    )
    user_row = refreshed.mappings().first()
    # 构造轻量返回对象（够打印即可）
    user = User()  # type: ignore[call-arg]
    user.user_id = user_row["user_id"]  # type: ignore[assignment]
    user.email = email  # type: ignore[assignment]
    user.name = account["name"]  # type: ignore[assignment]
    user.department = department  # type: ignore[assignment]
    user.role = account["role"]  # type: ignore[assignment]
    return user, False


async def run() -> None:
    print("=" * 60)
    print("团队学习看板测试账号 seed")
    print("=" * 60)
    print()
    print(f"统一密码：{DEFAULT_PASSWORD}")
    print()

    async with AsyncSessionLocal() as db:
        for account in SEED_ACCOUNTS:
            user, created = await upsert_account(db, account)
            action = "新建" if created else "更新"
            dept_display = account.get("department") or "(空)"
            print(f"[{action}] {account['email']}")
            print(f"        姓名：{account['name']}")
            print(f"        部门：{dept_display}")
            print(f"        角色：{account['role']}")
            print(f"        密码：{DEFAULT_PASSWORD}")
            print(f"        用途：{account.get('purpose', '')}")
            print()

    print("=" * 60)
    print("完成。用以上任意 email + 密码 123456 登录。")
    print("验证路径：")
    print("  - manager.one@team.com 登录 → 自动跳 /team → 看到销售一部的学员甲、学员乙（看不到销售二部的学员丙）")
    print("  - manager.two@team.com 登录 → /team 显示空部门提示")
    print("  - learner.one@team.com 登录 → 跳 / （不进看板，sidebar 无「我的团队」）")
    print("  - admin.one@team.com 登录 → 跳 / + sidebar 有「管理后台」")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run())

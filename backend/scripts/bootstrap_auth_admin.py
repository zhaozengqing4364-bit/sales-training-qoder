"""
Bootstrap a local admin/support/user account for controlled login.

Usage:
  python scripts/bootstrap_auth_admin.py --email admin@qoder.ai --name 管理员
  python scripts/bootstrap_auth_admin.py --email support@qoder.ai --role support
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

from sqlalchemy import select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register Agent/Persona mappers for PracticeSession relationships

from common.db.models import User
from common.db.session import AsyncSessionLocal


def _normalize_wechat_user_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


async def bootstrap_user(
    *,
    email: str,
    name: str,
    role: str,
    department: str | None,
    wechat_user_id: str | None,
) -> None:
    async with AsyncSessionLocal() as db:
        normalized_email = email.strip().lower()
        target_wechat_user_id = (wechat_user_id or _normalize_wechat_user_id(normalized_email)).strip()

        result = await db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                user_id=str(uuid.uuid4()),
                email=normalized_email,
                name=name.strip() or "管理员",
                role=role,
                department=department.strip() if department else None,
                is_active=True,
                wechat_user_id=target_wechat_user_id,
            )
            db.add(user)
            await db.commit()
            print(
                f"[created] user_id={user.user_id} email={user.email} role={user.role} "
                f"wechat_user_id={user.wechat_user_id}"
            )
            return

        user.name = name.strip() or user.name or "管理员"
        user.role = role
        user.department = department.strip() if department else user.department
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = target_wechat_user_id

        await db.commit()
        print(
            f"[updated] user_id={user.user_id} email={user.email} role={user.role} "
            f"wechat_user_id={user.wechat_user_id}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap auth user for local environment")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--name", default="管理员", help="Display name")
    parser.add_argument(
        "--role",
        default="admin",
        choices=["admin", "support", "user"],
        help="User role",
    )
    parser.add_argument("--department", default=None, help="Department")
    parser.add_argument("--wechat-user-id", default=None, help="Optional explicit wechat_user_id")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        bootstrap_user(
            email=args.email,
            name=args.name,
            role=args.role,
            department=args.department,
            wechat_user_id=args.wechat_user_id,
        )
    )

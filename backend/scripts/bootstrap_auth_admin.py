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
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register Agent/Persona mappers for PracticeSession relationships
from common.auth.credentials import (
    generate_temporary_password,
    temporary_password_ttl_hours,
)
from common.auth.service import pwd_context
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
    wechat_user_id: str | None,
    password: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        normalized_email = email.strip().lower()
        target_wechat_user_id = (
            wechat_user_id or _normalize_wechat_user_id(normalized_email)
        ).strip()
        configured_password = str(password or "").strip()
        generated_password = not configured_password
        initial_password = configured_password or generate_temporary_password()
        if len(initial_password) < 8:
            raise ValueError("Bootstrap password must contain at least 8 characters")

        result = await db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                user_id=str(uuid.uuid4()),
                email=normalized_email,
                name=name.strip() or "管理员",
                role=role,
                hashed_password=pwd_context.hash(initial_password),
                credential_status="temporary" if generated_password else "active",
                temporary_password_expires_at=(
                    datetime.now(UTC)
                    + timedelta(hours=temporary_password_ttl_hours())
                    if generated_password
                    else None
                ),
                password_changed_at=datetime.now(UTC) if not generated_password else None,
                is_active=True,
                wechat_user_id=target_wechat_user_id,
            )
            db.add(user)
            await db.commit()
            print(
                f"[created] user_id={user.user_id} email={user.email} role={user.role} "
                f"wechat_user_id={user.wechat_user_id}"
            )
            if generated_password:
                print(f"temporary_password={initial_password}")
            return

        user.name = name.strip() or user.name or "管理员"
        user.role = role
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = target_wechat_user_id
        password_updated = bool(configured_password or not user.hashed_password)
        if password_updated:
            user.hashed_password = pwd_context.hash(initial_password)
            user.credential_version = int(user.credential_version or 0) + 1
            user.credential_status = "temporary" if generated_password else "active"
            user.temporary_password_expires_at = (
                datetime.now(UTC) + timedelta(hours=temporary_password_ttl_hours())
                if generated_password
                else None
            )
            user.password_changed_at = (
                datetime.now(UTC) if not generated_password else None
            )

        await db.commit()
        print(
            f"[updated] user_id={user.user_id} email={user.email} role={user.role} "
            f"wechat_user_id={user.wechat_user_id}"
        )
        if generated_password and password_updated:
            print(f"temporary_password={initial_password}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap auth user for local environment"
    )
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--name", default="管理员", help="Display name")
    parser.add_argument(
        "--role",
        default="admin",
        choices=["admin", "support", "user"],
        help="User role",
    )
    parser.add_argument(
        "--password",
        default=None,
        help=(
            "Managed local password. Defaults to BOOTSTRAP_ADMIN_PASSWORD or "
            "SMOKE_ADMIN_PASSWORD; otherwise a one-time temporary password is generated."
        ),
    )
    parser.add_argument(
        "--wechat-user-id", default=None, help="Optional explicit wechat_user_id"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        bootstrap_user(
            email=args.email,
            name=args.name,
            role=args.role,
            wechat_user_id=args.wechat_user_id,
            password=(
                args.password
                or os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
                or os.getenv("SMOKE_ADMIN_PASSWORD")
            ),
        )
    )

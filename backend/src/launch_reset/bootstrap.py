"""Alembic-only schema bootstrap, idempotent system seed, and managed admin."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from admin.api.permissions import DEFAULT_ADMIN_ROLE_PERMISSIONS
from common.auth.credentials import normalize_email, temporary_password_ttl_hours
from common.auth.service import pwd_context
from common.db.model_registry import AdminRolePermission, User
from launch_reset.errors import ResetExecutionError, ResetSafetyError
from launch_reset.guards import sync_database_url
from launch_reset.scopes import BACKEND_ROOT


class AlembicSchemaBootstrap:
    def __init__(self, raw_url: str) -> None:
        self.raw_url = raw_url

    def upgrade_head(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["DATABASE_URL"] = self.raw_url
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ResetExecutionError("[RESET_ALEMBIC_UPGRADE_FAILED]")
        return {"status": "head"}


class SystemSeedService:
    """Own stable, non-business dictionaries required by the control plane."""

    def __init__(self, raw_url: str) -> None:
        self.engine = create_engine(sync_database_url(raw_url))

    def seed(self) -> dict[str, int]:
        created = 0
        existing = 0
        try:
            with Session(self.engine) as session, session.begin():
                for role, permissions in DEFAULT_ADMIN_ROLE_PERMISSIONS.items():
                    for permission in sorted(permissions):
                        found = session.scalar(
                            select(AdminRolePermission.id).where(
                                AdminRolePermission.role == role,
                                AdminRolePermission.permission == permission,
                            )
                        )
                        if found is not None:
                            existing += 1
                            continue
                        session.add(
                            AdminRolePermission(role=role, permission=permission)
                        )
                        created += 1
        finally:
            self.engine.dispose()
        return {"created": created, "existing": existing}


class ManagedAdminBootstrap:
    def __init__(self, raw_url: str) -> None:
        self.engine = create_engine(sync_database_url(raw_url))

    def bootstrap(
        self, *, email: str, name: str, initial_password: str
    ) -> dict[str, Any]:
        try:
            validated_email = TypeAdapter(EmailStr).validate_python(email)
        except ValidationError as exc:
            raise ResetSafetyError("[RESET_ADMIN_EMAIL_INVALID]") from exc
        normalized_email = normalize_email(str(validated_email))
        normalized_name = name.strip()
        if not normalized_name:
            raise ResetSafetyError("[RESET_ADMIN_NAME_REQUIRED]")
        if len(initial_password) < 12:
            raise ResetSafetyError("[RESET_ADMIN_PASSWORD_TOO_SHORT]")

        try:
            with Session(self.engine) as session, session.begin():
                user_count = int(
                    session.scalar(select(func.count()).select_from(User)) or 0
                )
                existing = session.scalar(
                    select(User).where(func.lower(User.email) == normalized_email)
                )
                if user_count and existing is None:
                    raise ResetSafetyError("[RESET_ADMIN_NOT_ONLY_USER]")
                if user_count > 1:
                    raise ResetSafetyError("[RESET_ADMIN_NOT_ONLY_USER]")
                if existing is not None:
                    if existing.role != "admin" or not existing.is_active:
                        raise ResetSafetyError("[RESET_ADMIN_EXISTING_STATE_INVALID]")
                    return {
                        "user_id": str(existing.user_id),
                        "email": normalized_email,
                        "created": False,
                    }

                now = datetime.now(UTC)
                user = User(
                    user_id=str(uuid.uuid4()),
                    wechat_user_id=f"launch-admin-{hashlib_email(normalized_email)}",
                    name=normalized_name,
                    email=normalized_email,
                    hashed_password=pwd_context.hash(initial_password),
                    credential_status="temporary",
                    temporary_password_expires_at=now
                    + timedelta(hours=temporary_password_ttl_hours()),
                    credential_version=1,
                    role="admin",
                    created_at=now,
                    is_active=True,
                )
                session.add(user)
                session.flush()
                return {
                    "user_id": str(user.user_id),
                    "email": normalized_email,
                    "created": True,
                }
        finally:
            self.engine.dispose()


def hashlib_email(email: str) -> str:
    import hashlib

    return hashlib.sha256(email.encode()).hexdigest()[:20]


__all__ = ["AlembicSchemaBootstrap", "ManagedAdminBootstrap", "SystemSeedService"]

"""Bulk account provisioning with preview and team-scoped atomic execution."""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.credentials import (
    generate_temporary_password,
    normalize_email,
    temporary_password_ttl_hours,
)
from common.auth.roles import ROLE_TRAINING_MANAGER, ROLE_USER
from common.auth.service import pwd_context
from common.db.models import (
    ProvisioningBatch,
    ProvisioningRow,
    ProvisioningTeamExecution,
    SystemLog,
    Team,
    TeamLeaderAssignment,
    User,
)
from common.teams.service import TeamDomainError, TeamService

_EMAIL = TypeAdapter(EmailStr)
REQUIRED_COLUMNS = {"name", "email", "role", "team_code"}
IMPORT_ROLES = {ROLE_USER, ROLE_TRAINING_MANAGER}


class ProvisioningError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _row_payload(row: ProvisioningRow) -> dict[str, Any]:
    return {
        "row_number": row.row_number,
        "name": row.name,
        "email": row.email,
        "role": row.role,
        "team_code": row.team_code,
        "team_name": row.team_name,
        "primary_leader_email": row.primary_leader_email,
        "status": row.status,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "user_id": row.user_id,
    }


class ProvisioningService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def preview(
        self,
        *,
        csv_text: str,
        source_name: str,
        idempotency_key: str,
        actor: User,
    ) -> dict[str, Any]:
        existing_batch = await self.db.scalar(
            select(ProvisioningBatch).where(
                ProvisioningBatch.idempotency_key == idempotency_key.strip()
            )
        )
        if existing_batch is not None:
            return await self.get_batch(str(existing_batch.batch_id))

        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
        columns = {str(column or "").strip() for column in (reader.fieldnames or [])}
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ProvisioningError(
                "[PROVISIONING_COLUMNS_MISSING]",
                f"CSV 缺少必填列：{'、'.join(missing)}",
            )

        batch = ProvisioningBatch(
            idempotency_key=idempotency_key.strip(),
            source_name=source_name.strip() or "accounts.csv",
            status="previewed",
            created_by=str(actor.user_id),
        )
        self.db.add(batch)
        await self.db.flush()

        seen_emails: set[str] = set()
        grouped: dict[str, list[ProvisioningRow]] = defaultdict(list)
        for row_number, raw in enumerate(reader, start=2):
            if row_number > 501:
                raise ProvisioningError(
                    "[PROVISIONING_ROW_LIMIT_EXCEEDED]",
                    "单次最多导入 500 个账号，请拆分文件后重试。",
                )
            name = str(raw.get("name") or "").strip()
            email = normalize_email(raw.get("email"))
            role = str(raw.get("role") or "").strip().lower()
            team_code = str(raw.get("team_code") or "").strip().lower()
            error_code: str | None = None
            error_message: str | None = None
            try:
                email = str(_EMAIL.validate_python(email)).lower()
            except ValidationError:
                error_code, error_message = "[INVALID_EMAIL]", "公司邮箱格式无效。"
            if not name:
                error_code, error_message = "[NAME_REQUIRED]", "姓名不能为空。"
            elif role not in IMPORT_ROLES:
                error_code, error_message = (
                    "[INVALID_ROLE]",
                    "角色仅支持 user 或 training_manager。",
                )
            elif not team_code:
                error_code, error_message = "[TEAM_CODE_REQUIRED]", "团队编码不能为空。"
            elif email in seen_emails:
                error_code, error_message = (
                    "[DUPLICATE_EMAIL_IN_FILE]",
                    "文件内邮箱重复。",
                )
            seen_emails.add(email)
            if error_code is None and await self.db.scalar(
                select(User.user_id).where(func.lower(User.email) == email)
            ):
                error_code, error_message = "[EMAIL_ALREADY_EXISTS]", "邮箱已存在。"

            row = ProvisioningRow(
                batch_id=str(batch.batch_id),
                row_number=row_number,
                name=name or "未命名",
                email=email,
                role=role or ROLE_USER,
                team_code=team_code or "invalid",
                team_name=str(raw.get("team_name") or "").strip() or None,
                primary_leader_email=normalize_email(raw.get("primary_leader_email"))
                or None,
                employee_number=str(raw.get("employee_number") or "").strip() or None,
                status="invalid" if error_code else "valid",
                error_code=error_code,
                error_message=error_message,
            )
            self.db.add(row)
            grouped[row.team_code].append(row)

        if not grouped:
            raise ProvisioningError(
                "[PROVISIONING_EMPTY]", "CSV 中没有可处理的数据行。"
            )
        for team_code in grouped:
            self.db.add(
                ProvisioningTeamExecution(
                    batch_id=str(batch.batch_id), team_code=team_code, status="pending"
                )
            )
        await self.db.commit()
        return await self.get_batch(str(batch.batch_id))

    async def get_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self.db.get(ProvisioningBatch, batch_id)
        if batch is None:
            raise ProvisioningError(
                "[PROVISIONING_BATCH_NOT_FOUND]", "开户批次不存在。", status_code=404
            )
        rows = list(
            (
                await self.db.scalars(
                    select(ProvisioningRow)
                    .where(ProvisioningRow.batch_id == batch_id)
                    .order_by(ProvisioningRow.row_number)
                )
            ).all()
        )
        executions = list(
            (
                await self.db.scalars(
                    select(ProvisioningTeamExecution)
                    .where(ProvisioningTeamExecution.batch_id == batch_id)
                    .order_by(ProvisioningTeamExecution.team_code)
                )
            ).all()
        )
        team_codes = sorted({row.team_code for row in rows})
        existing_teams = {
            team.code: team
            for team in (
                await self.db.scalars(select(Team).where(Team.code.in_(team_codes)))
            ).all()
        }
        return {
            "batch_id": str(batch.batch_id),
            "status": batch.status,
            "source_name": batch.source_name,
            "rows": [_row_payload(row) for row in rows],
            "teams": [
                {
                    "team_code": execution.team_code,
                    "status": execution.status,
                    "error_code": execution.error_code,
                    "exists": execution.team_code in existing_teams,
                    "row_count": sum(
                        1 for row in rows if row.team_code == execution.team_code
                    ),
                }
                for execution in executions
            ],
        }

    async def confirm(
        self,
        *,
        batch_id: str,
        actor: User,
        team_overrides: dict[str, dict[str, str]],
        retry_team_codes: set[str] | None = None,
    ) -> dict[str, Any]:
        batch = await self.db.get(ProvisioningBatch, batch_id)
        if batch is None:
            raise ProvisioningError(
                "[PROVISIONING_BATCH_NOT_FOUND]", "开户批次不存在。", status_code=404
            )
        rows = list(
            (
                await self.db.scalars(
                    select(ProvisioningRow)
                    .where(ProvisioningRow.batch_id == batch_id)
                    .order_by(ProvisioningRow.row_number)
                )
            ).all()
        )
        executions = {
            execution.team_code: execution
            for execution in (
                await self.db.scalars(
                    select(ProvisioningTeamExecution).where(
                        ProvisioningTeamExecution.batch_id == batch_id
                    )
                )
            ).all()
        }
        grouped: dict[str, list[ProvisioningRow]] = defaultdict(list)
        for row in rows:
            grouped[row.team_code].append(row)

        credentials: list[dict[str, Any]] = []
        batch.status = "processing"
        await self.db.flush()
        for team_code, team_rows in grouped.items():
            execution = executions[team_code]
            if execution.status == "completed":
                continue
            if retry_team_codes is not None and team_code not in retry_team_codes:
                continue
            execution.attempted_at = datetime.now(UTC)
            if any(row.status == "invalid" for row in team_rows):
                execution.status = "failed"
                execution.error_code = "[TEAM_HAS_INVALID_ROWS]"
                continue
            team_credentials: list[dict[str, Any]] = []
            try:
                async with self.db.begin_nested():
                    override = team_overrides.get(team_code, {})
                    team = await self.db.scalar(
                        select(Team).where(Team.code == team_code)
                    )
                    if team is None:
                        team_name = override.get("name") or next(
                            (row.team_name for row in team_rows if row.team_name), None
                        )
                        if not team_name:
                            raise ProvisioningError(
                                "[TEAM_NAME_REQUIRED]", "新团队必须填写名称。"
                            )
                        team = await TeamService(self.db).create_team(
                            code=team_code, name=team_name, actor=actor
                        )

                    created_users: dict[str, User] = {}
                    for row in sorted(
                        team_rows, key=lambda item: item.role != ROLE_TRAINING_MANAGER
                    ):
                        if await self.db.scalar(
                            select(User.user_id).where(
                                func.lower(User.email) == row.email
                            )
                        ):
                            raise ProvisioningError(
                                "[EMAIL_ALREADY_EXISTS]", f"{row.email} 已存在。"
                            )
                        password = generate_temporary_password()
                        expires_at = datetime.now(UTC) + timedelta(
                            hours=temporary_password_ttl_hours()
                        )
                        user = User(
                            user_id=str(uuid.uuid4()),
                            wechat_user_id=f"provisioned_{uuid.uuid4().hex}",
                            name=row.name,
                            email=row.email,
                            role=row.role,
                            is_active=True,
                            hashed_password=pwd_context.hash(password),
                            credential_status="temporary",
                            temporary_password_expires_at=expires_at,
                            credential_version=1,
                        )
                        self.db.add(user)
                        await self.db.flush()
                        created_users[row.email] = user
                        row.user_id = str(user.user_id)
                        row.status = "created"
                        row.error_code = None
                        row.error_message = None
                        team_credentials.append(
                            {
                                "row_number": row.row_number,
                                "name": row.name,
                                "email": row.email,
                                "temporary_password": password,
                                "temporary_password_expires_at": expires_at.isoformat(),
                            }
                        )

                    leader_email = normalize_email(
                        override.get("primary_leader_email")
                    ) or next(
                        (
                            row.primary_leader_email
                            for row in team_rows
                            if row.primary_leader_email
                        ),
                        "",
                    )
                    leader = created_users.get(leader_email) or await self.db.scalar(
                        select(User).where(func.lower(User.email) == leader_email)
                    )
                    if leader is None:
                        existing_primary = await self.db.scalar(
                            select(TeamLeaderAssignment).where(
                                TeamLeaderAssignment.team_id == str(team.team_id),
                                TeamLeaderAssignment.assignment_role == "primary",
                                TeamLeaderAssignment.effective_to.is_(None),
                            )
                        )
                        if existing_primary is None:
                            raise ProvisioningError(
                                "[PRIMARY_LEADER_REQUIRED]", "团队必须指定主组长。"
                            )
                    else:
                        await TeamService(self.db).assign_leader(
                            team=team, leader=leader, actor=actor
                        )
                    for row in team_rows:
                        if row.role == ROLE_USER:
                            await TeamService(self.db).assign_primary_member(
                                team=team, learner=created_users[row.email], actor=actor
                            )
                    self.db.add(
                        SystemLog(
                            action="admin.provisioning.team.completed",
                            user_id=str(actor.user_id),
                            user_identifier=actor.email
                            or actor.name
                            or str(actor.user_id),
                            status="success",
                            details=json.dumps(
                                {
                                    "batch_id": batch_id,
                                    "team_code": team_code,
                                    "created_count": len(team_rows),
                                },
                                ensure_ascii=False,
                            ),
                        )
                    )
                execution.status = "completed"
                execution.error_code = None
                credentials.extend(team_credentials)
            except (ProvisioningError, TeamDomainError, SQLAlchemyError) as exc:
                error_code = getattr(exc, "code", "[TEAM_PROVISIONING_FAILED]")
                error_message = getattr(
                    exc,
                    "message",
                    "该团队开户未完成，团队内数据已全部回滚，可修正后重试。",
                )
                execution.status = "failed"
                execution.error_code = error_code
                for row in team_rows:
                    row.status = "failed"
                    row.error_code = error_code
                    row.error_message = error_message

        completed = sum(item.status == "completed" for item in executions.values())
        failed = sum(item.status == "failed" for item in executions.values())
        batch.status = (
            "completed"
            if completed and not failed
            else "partially_completed"
            if completed and failed
            else "failed"
        )
        batch.confirmed_at = datetime.now(UTC)
        await self.db.commit()
        result = await self.get_batch(batch_id)
        result["credentials"] = credentials
        return result

    async def reset_credentials(self, *, batch_id: str, actor: User) -> dict[str, Any]:
        batch = await self.db.get(ProvisioningBatch, batch_id)
        if batch is None:
            raise ProvisioningError(
                "[PROVISIONING_BATCH_NOT_FOUND]", "开户批次不存在。", status_code=404
            )
        rows = list(
            (
                await self.db.scalars(
                    select(ProvisioningRow).where(
                        ProvisioningRow.batch_id == batch_id,
                        ProvisioningRow.status == "created",
                        ProvisioningRow.user_id.is_not(None),
                    )
                )
            ).all()
        )
        credentials: list[dict[str, Any]] = []
        for row in rows:
            user = await self.db.get(User, row.user_id)
            if user is None or not user.is_active:
                continue
            password = generate_temporary_password()
            expires_at = datetime.now(UTC) + timedelta(
                hours=temporary_password_ttl_hours()
            )
            user.hashed_password = pwd_context.hash(password)
            user.credential_status = "temporary"
            user.temporary_password_expires_at = expires_at
            user.password_changed_at = None
            user.credential_version = int(user.credential_version or 1) + 1
            credentials.append(
                {
                    "row_number": row.row_number,
                    "name": user.name,
                    "email": user.email,
                    "temporary_password": password,
                    "temporary_password_expires_at": expires_at.isoformat(),
                }
            )
        self.db.add(
            SystemLog(
                action="admin.provisioning.credentials.reset",
                user_id=str(actor.user_id),
                user_identifier=actor.email or actor.name or str(actor.user_id),
                status="success",
                details=json.dumps(
                    {"batch_id": batch_id, "reset_count": len(credentials)},
                    ensure_ascii=False,
                ),
            )
        )
        await self.db.commit()
        return {"batch_id": batch_id, "credentials": credentials}

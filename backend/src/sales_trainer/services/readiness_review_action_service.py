from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerReadinessReviewAction
from sales_trainer.permissions import (
    can_review_sales_trainer_readiness,
    is_sales_trainer_admin,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.readiness_state import (
    READINESS_CONTRACT_VERSION,
    READINESS_DOSSIER_TARGET_TYPE,
    REVIEW_ACTION_CREATED,
)

ReadinessDecision = Literal[
    "approve",
    "require_retraining",
    "mark_manual_follow_up",
]
READINESS_DECISIONS = frozenset(
    {"approve", "require_retraining", "mark_manual_follow_up"}
)
IDEMPOTENCY_CONSTRAINT_NAME = "uq_readiness_review_actor_idempotency"
SQLITE_IDEMPOTENCY_CONSTRAINT_COLUMNS = (
    "sales_trainer_readiness_review_actions.actor_id",
    "sales_trainer_readiness_review_actions.idempotency_key",
)


@dataclass(frozen=True, slots=True)
class ReadinessAuditContext:
    request_id: str | None
    ip_address: str | None
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class ReadinessReviewActionSnapshot:
    action_id: str
    audit_log_id: str | None
    decision: str
    reason: str | None
    capability_keys: list[str]
    source_evidence_ids: list[str]
    actor_id: str | None
    actor_role: str | None
    created_at: datetime | None
    retraining_task: dict[str, Any] | None
    state_storage: Literal["readiness_review_action", "operation_log"]


class ReadinessReviewActionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _unique_non_empty(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _review_request_hash(
    *,
    learner_id: str,
    decision: ReadinessDecision,
    reason: str,
    capability_keys: list[str],
    source_evidence_ids: list[str],
) -> str:
    canonical = json.dumps(
        {
            "learner_id": learner_id,
            "decision": decision,
            "reason": reason.strip(),
            "capability_keys": sorted(capability_keys),
            "source_evidence_ids": sorted(source_evidence_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _created_at_key(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_idempotency_conflict(error: IntegrityError) -> bool:
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None) or getattr(
        original,
        "constraint_name",
        None,
    )
    if constraint_name == IDEMPOTENCY_CONSTRAINT_NAME:
        return True

    # SQLite reports unique violations by column list rather than constraint
    # name. Inspect only the DBAPI error text, not the rendered INSERT statement.
    original_message = str(original)
    if IDEMPOTENCY_CONSTRAINT_NAME in original_message:
        return True
    return all(
        column_name in original_message
        for column_name in SQLITE_IDEMPOTENCY_CONSTRAINT_COLUMNS
    )


class ReadinessReviewActionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        logs: OperationLogService | None = None,
    ) -> None:
        self._db = db
        self._logs = logs or OperationLogService(db)

    async def create(
        self,
        *,
        learner_id: str,
        actor: User,
        team_department: str | None,
        decision: ReadinessDecision,
        reason: str,
        capability_keys: list[str],
        source_evidence_ids: list[str],
        idempotency_key: str,
        expected_latest_review_action_id: str | None,
        audit_context: ReadinessAuditContext,
        request_capability_keys: list[str] | None = None,
        request_source_evidence_ids: list[str] | None = None,
    ) -> SalesTrainerReadinessReviewAction:
        if not can_review_sales_trainer_readiness(actor):
            raise ReadinessReviewActionError(
                "[READINESS_REVIEW_ROLE_REQUIRED]",
                "当前账号无权执行训练达标复核。",
                403,
            )
        if decision not in READINESS_DECISIONS:
            raise ReadinessReviewActionError(
                "[READINESS_REVIEW_DECISION_INVALID]",
                "复核决定不在允许范围内。",
                400,
            )
        # A uniqueness race may require rolling the AsyncSession back. SQLAlchemy
        # expires ORM instances on rollback even when expire_on_commit=False, so
        # keep primitive actor fields before entering that path.
        actor_id = str(actor.user_id)
        actor_role = str(getattr(actor, "role", "") or "")

        normalized_key = str(idempotency_key or "").strip()
        if not 16 <= len(normalized_key) <= 100:
            raise ReadinessReviewActionError(
                "[READINESS_IDEMPOTENCY_KEY_INVALID]",
                "复核提交标识格式无效。",
                400,
            )
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ReadinessReviewActionError(
                "[READINESS_REVIEW_REASON_REQUIRED]",
                "请填写复核原因。",
                400,
            )
        normalized_capabilities = _unique_non_empty(capability_keys)
        normalized_evidence_ids = _unique_non_empty(source_evidence_ids)
        # Idempotency identifies the caller's normalized request, not Dossier
        # defaults expanded from mutable evidence. The service still computes
        # the hash itself; callers may provide values, never a trusted hash.
        fingerprint_capabilities = _unique_non_empty(
            capability_keys
            if request_capability_keys is None
            else request_capability_keys
        )
        fingerprint_evidence_ids = _unique_non_empty(
            source_evidence_ids
            if request_source_evidence_ids is None
            else request_source_evidence_ids
        )

        learner = await self._db.scalar(
            select(User).where(User.user_id == learner_id).with_for_update()
        )
        if learner is None or not self._learner_is_in_scope(
            learner,
            actor=actor,
            team_department=team_department,
        ):
            raise ReadinessReviewActionError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )

        request_hash = _review_request_hash(
            learner_id=learner_id,
            decision=decision,
            reason=normalized_reason,
            capability_keys=fingerprint_capabilities,
            source_evidence_ids=fingerprint_evidence_ids,
        )
        replay = await self._find_idempotent(
            actor_id=actor_id,
            key=normalized_key,
        )
        if replay is not None:
            return self._validate_idempotent_replay(replay, request_hash=request_hash)

        latest_id = await self._latest_version_id_for_learner(learner_id)
        if latest_id != expected_latest_review_action_id:
            raise ReadinessReviewActionError(
                "[READINESS_REVIEW_VERSION_CONFLICT]",
                "档案已被其他复核动作更新，请刷新后重试。",
                409,
                details={"latest_review_action_id": latest_id},
            )

        action = SalesTrainerReadinessReviewAction(
            learner_id=learner_id,
            actor_id=actor_id,
            actor_role=actor_role,
            decision=decision,
            reason=normalized_reason,
            capability_keys=normalized_capabilities,
            source_evidence_ids=normalized_evidence_ids,
            retraining_task=None,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            expected_previous_action_id=latest_id,
        )
        self._db.add(action)
        try:
            await self._db.flush()
        except IntegrityError as error:
            # The database unique constraint is the final guard for two requests
            # that race before either can observe the other's idempotency row.
            # Roll back the failed insert before reading the winning row. This
            # path is only reached before the action/audit transaction has any
            # other business write.
            idempotency_conflict = _is_idempotency_conflict(error)
            await self._db.rollback()
            if not idempotency_conflict:
                raise
            replay = await self._find_idempotent(
                actor_id=actor_id,
                key=normalized_key,
            )
            if replay is None:
                raise
            return self._validate_idempotent_replay(
                replay,
                request_hash=request_hash,
            )

        if decision == "require_retraining":
            retraining_task: dict[str, Any] | None = {
                "task_id": f"retraining:{action.action_id}",
                "status": "pending",
                "source": "readiness_review_action",
                "capability_keys": normalized_capabilities,
                "source_evidence_ids": normalized_evidence_ids,
                "target_learner_id": learner_id,
            }
            setattr(action, "retraining_task", retraining_task)
        else:
            retraining_task = None

        log = await self._logs.record(
            actor=actor,
            action=REVIEW_ACTION_CREATED,
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            request_id=audit_context.request_id,
            ip_address=audit_context.ip_address,
            user_agent=audit_context.user_agent,
            metadata={
                "contract_version": READINESS_CONTRACT_VERSION,
                "action_id": str(action.action_id),
                "decision": decision,
                "reason": normalized_reason,
                "capability_keys": normalized_capabilities,
                "source_evidence_ids": normalized_evidence_ids,
                "retraining_task": retraining_task,
                "state_storage": "readiness_review_action",
            },
        )
        setattr(action, "audit_log_id", str(log.log_id))
        await self._db.commit()
        await self._db.refresh(action)
        return action

    async def list_for_learner(
        self,
        learner_id: str,
        *,
        limit: int = 200,
    ) -> list[SalesTrainerReadinessReviewAction]:
        normalized_limit = max(1, min(int(limit), 500))
        result = await self._db.execute(
            select(SalesTrainerReadinessReviewAction)
            .where(SalesTrainerReadinessReviewAction.learner_id == learner_id)
            .order_by(
                SalesTrainerReadinessReviewAction.created_at.desc(),
                SalesTrainerReadinessReviewAction.action_id.desc(),
            )
            .limit(normalized_limit)
        )
        return list(result.scalars().all())

    async def list_merged_for_learner(
        self,
        learner_id: str,
        *,
        limit: int = 200,
    ) -> list[ReadinessReviewActionSnapshot]:
        normalized_limit = max(1, min(int(limit), 500))
        # Compatibility logs include canonical audit mirrors that are filtered
        # below. Scan a stable window even when a caller only asks for the
        # latest item, otherwise the one fetched row can be a mirror and hide
        # the actual latest legacy decision.
        legacy_scan_limit = max(normalized_limit, 200)
        stored = await self.list_for_learner(
            learner_id,
            limit=normalized_limit,
        )
        audit_ids_result = await self._db.execute(
            select(SalesTrainerReadinessReviewAction.audit_log_id).where(
                SalesTrainerReadinessReviewAction.learner_id == learner_id,
                SalesTrainerReadinessReviewAction.audit_log_id.is_not(None),
            )
        )
        canonical_audit_ids = {
            str(log_id)
            for log_id in audit_ids_result.scalars().all()
            if log_id is not None
        }
        legacy_logs, _ = await self._logs.list_logs(
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            limit=legacy_scan_limit,
        )

        items = [self._stored_snapshot(action) for action in stored]
        for log in legacy_logs:
            if log.action != REVIEW_ACTION_CREATED:
                continue
            if str(log.log_id) in canonical_audit_ids:
                continue
            metadata: dict[str, Any] = (
                log.metadata_json if isinstance(log.metadata_json, dict) else {}
            )
            if metadata.get("state_storage") == "readiness_review_action":
                continue
            items.append(self._legacy_snapshot(log))
        return sorted(
            items,
            key=lambda item: (
                _created_at_key(item.created_at),
                item.action_id,
            ),
            reverse=True,
        )[:normalized_limit]

    @staticmethod
    def _learner_is_in_scope(
        learner: User,
        *,
        actor: User,
        team_department: str | None,
    ) -> bool:
        if is_sales_trainer_admin(actor):
            return True
        actor_department = str(getattr(actor, "department", "") or "").strip()
        if not actor_department:
            return False
        if team_department is not None and team_department != actor_department:
            return False
        return str(getattr(learner, "department", "") or "").strip() == (
            actor_department
        )

    async def _find_idempotent(
        self,
        *,
        actor_id: str,
        key: str,
    ) -> SalesTrainerReadinessReviewAction | None:
        return cast(
            SalesTrainerReadinessReviewAction | None,
            await self._db.scalar(
                select(SalesTrainerReadinessReviewAction).where(
                    SalesTrainerReadinessReviewAction.actor_id == actor_id,
                    SalesTrainerReadinessReviewAction.idempotency_key == key,
                )
            ),
        )

    @staticmethod
    def _validate_idempotent_replay(
        replay: SalesTrainerReadinessReviewAction,
        *,
        request_hash: str,
    ) -> SalesTrainerReadinessReviewAction:
        if str(replay.request_hash) != request_hash:
            raise ReadinessReviewActionError(
                "[READINESS_IDEMPOTENCY_KEY_REUSED]",
                "该提交标识已用于另一项复核内容，请刷新后重新提交。",
                409,
            )
        return replay

    async def _latest_version_id_for_learner(
        self,
        learner_id: str,
    ) -> str | None:
        actions = await self.list_merged_for_learner(learner_id, limit=1)
        return actions[0].action_id if actions else None

    @staticmethod
    def _stored_snapshot(
        action: SalesTrainerReadinessReviewAction,
    ) -> ReadinessReviewActionSnapshot:
        return ReadinessReviewActionSnapshot(
            action_id=str(action.action_id),
            audit_log_id=(
                str(action.audit_log_id) if action.audit_log_id is not None else None
            ),
            decision=str(action.decision),
            reason=action.reason,
            capability_keys=_unique_non_empty(action.capability_keys or []),
            source_evidence_ids=_unique_non_empty(action.source_evidence_ids or []),
            actor_id=str(action.actor_id) if action.actor_id else None,
            actor_role=action.actor_role,
            created_at=cast(datetime | None, action.created_at),
            retraining_task=(
                action.retraining_task
                if isinstance(action.retraining_task, dict)
                else None
            ),
            state_storage="readiness_review_action",
        )

    @staticmethod
    def _legacy_snapshot(log: Any) -> ReadinessReviewActionSnapshot:
        metadata: dict[str, Any] = (
            log.metadata_json if isinstance(log.metadata_json, dict) else {}
        )
        task = metadata.get("retraining_task")
        return ReadinessReviewActionSnapshot(
            action_id=str(log.log_id),
            audit_log_id=str(log.log_id),
            decision=str(metadata.get("decision") or "mark_manual_follow_up"),
            reason=(
                str(metadata["reason"]) if metadata.get("reason") is not None else None
            ),
            capability_keys=_unique_non_empty(metadata.get("capability_keys") or []),
            source_evidence_ids=_unique_non_empty(
                metadata.get("source_evidence_ids") or []
            ),
            actor_id=str(log.actor_id) if log.actor_id else None,
            actor_role=log.actor_role,
            created_at=cast(datetime | None, log.created_at),
            retraining_task=task if isinstance(task, dict) else None,
            state_storage="operation_log",
        )

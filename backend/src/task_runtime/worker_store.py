"""PostgreSQL worker store with recoverable leases and execution fencing."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from task_runtime.contracts import (
    ClaimedTask,
    Clock,
    TaskCompletion,
    TaskPolicy,
    TaskProgressUpdate,
    TaskState,
)
from task_runtime.errors import (
    TaskCancellationRequested,
    TaskExecutionError,
    TaskFailureKind,
    TaskLeaseLostError,
    TaskSchemaInvalidError,
)
from task_runtime.models import (
    DurableTask,
    TaskAttempt,
    TaskLease,
    TaskPayloadArtifact,
    TaskProgress,
    TaskResultRef,
    TaskTypeControl,
)
from task_runtime.outbox import append_task_event
from task_runtime.repository import SystemClock
from task_runtime.retry_policy import retry_backoff_seconds
from task_runtime.state_machine import require_task_transition


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class FencedTaskExecution:
    """Locks the current fence for the surrounding business transaction."""

    def __init__(
        self,
        session: AsyncSession,
        claim: ClaimedTask,
        *,
        clock: Clock,
    ) -> None:
        self._session = session
        self.claim = claim
        self._clock = clock

    async def assert_current(self) -> None:
        await self._load_current()

    async def current_state(self) -> TaskState:
        task, _ = await self._load_current()
        return TaskState(task.state)

    async def report_progress(self, update: TaskProgressUpdate) -> int:
        task, _ = await self._load_current()
        if TaskState(task.state) is TaskState.CANCEL_REQUESTED:
            raise TaskCancellationRequested()
        latest_result = await self._session.execute(
            select(func.max(TaskProgress.sequence)).where(
                TaskProgress.task_id == task.task_id
            )
        )
        sequence = int(latest_result.scalar_one_or_none() or 0) + 1
        now = self._clock.now()
        progress = TaskProgress(
            task_id=task.task_id,
            sequence=sequence,
            current=update.current,
            total=update.total,
            stage=update.stage,
            label=update.label,
            created_at=now,
        )
        self._session.add(progress)
        task.updated_at = now
        task.version += 1
        await append_task_event(
            self._session,
            task,
            event_type="TaskProgressed",
            occurred_at=now,
            actor_id=None,
            details={"sequence": sequence, "stage": update.stage},
        )
        await self._session.flush([task, progress])
        return sequence

    async def _load_current(self) -> tuple[DurableTask, TaskLease]:
        now = self._clock.now()
        result = await self._session.execute(
            select(DurableTask, TaskLease)
            .join(TaskLease, TaskLease.task_id == DurableTask.task_id)
            .where(DurableTask.task_id == self.claim.task_id)
            .where(DurableTask.fence_generation == self.claim.fence_generation)
            .where(
                DurableTask.state.in_(
                    [TaskState.RUNNING.value, TaskState.CANCEL_REQUESTED.value]
                )
            )
            .where(TaskLease.attempt_id == self.claim.attempt_id)
            .where(TaskLease.fence_generation == self.claim.fence_generation)
            .where(TaskLease.owner_id == self.claim.worker_id)
            .where(TaskLease.lease_token_hash == _token_hash(self.claim.lease_token))
            .where(TaskLease.expires_at > now)
            .with_for_update()
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            raise TaskLeaseLostError()
        return row[0], row[1]


class SQLAlchemyTaskWorkerStore:
    """Worker-facing task persistence; the caller owns commit/rollback."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    def execution(self, claim: ClaimedTask) -> FencedTaskExecution:
        return FencedTaskExecution(self._session, claim, clock=self._clock)

    async def claim_next(
        self,
        *,
        worker_id: str,
        task_types: frozenset[str] | None = None,
    ) -> ClaimedTask | None:
        now = self._clock.now()
        aged_cutoff = now - timedelta(minutes=5)
        running_task = aliased(DurableTask)
        recent_task = aliased(DurableTask)
        running_count = (
            select(func.count(running_task.task_id))
            .where(running_task.organization_id == DurableTask.organization_id)
            .where(running_task.task_type == DurableTask.task_type)
            .where(
                running_task.state.in_(
                    [TaskState.RUNNING.value, TaskState.CANCEL_REQUESTED.value]
                )
            )
            .correlate(DurableTask, TaskTypeControl)
            .scalar_subquery()
        )
        recent_count = (
            select(func.count(TaskAttempt.attempt_id))
            .join(recent_task, recent_task.task_id == TaskAttempt.task_id)
            .where(recent_task.organization_id == DurableTask.organization_id)
            .where(recent_task.task_type == DurableTask.task_type)
            .where(TaskAttempt.started_at >= now - timedelta(minutes=1))
            .correlate(DurableTask, TaskTypeControl)
            .scalar_subquery()
        )
        blocked_by_control = exists(
            select(TaskTypeControl.control_id)
            .where(TaskTypeControl.organization_id == DurableTask.organization_id)
            .where(TaskTypeControl.task_type == DurableTask.task_type)
            .where(
                or_(
                    TaskTypeControl.is_paused.is_(True),
                    and_(
                        TaskTypeControl.max_concurrency.is_not(None),
                        running_count >= TaskTypeControl.max_concurrency,
                    ),
                    and_(
                        TaskTypeControl.rate_limit_per_minute.is_not(None),
                        recent_count >= TaskTypeControl.rate_limit_per_minute,
                    ),
                )
            )
        )
        base_query = (
            select(DurableTask)
            .where(DurableTask.state == TaskState.QUEUED.value)
            .where(DurableTask.next_run_at <= now)
            .where(
                (DurableTask.deadline_at.is_(None)) | (DurableTask.deadline_at > now)
            )
            .where(~blocked_by_control)
        )
        if task_types is not None:
            if not task_types:
                return None
            base_query = base_query.where(DurableTask.task_type.in_(task_types))

        async def select_allowed(
            query: Select[tuple[DurableTask]],
        ) -> DurableTask | None:
            excluded_task_ids: set[str] = set()
            while True:
                candidate_query = query
                if excluded_task_ids:
                    candidate_query = candidate_query.where(
                        DurableTask.task_id.not_in(excluded_task_ids)
                    )
                result = await self._session.execute(candidate_query)
                candidate = result.scalar_one_or_none()
                if candidate is None:
                    return None
                control_result = await self._session.execute(
                    select(TaskTypeControl)
                    .where(TaskTypeControl.organization_id == candidate.organization_id)
                    .where(TaskTypeControl.task_type == candidate.task_type)
                    .with_for_update()
                    .limit(1)
                )
                control = control_result.scalar_one_or_none()
                if control is None or await self._control_allows_claim(
                    control,
                    task=candidate,
                    now=now,
                ):
                    return candidate
                excluded_task_ids.add(candidate.task_id)

        aged_query = (
            base_query.where(DurableTask.created_at <= aged_cutoff)
            .order_by(
                DurableTask.created_at.asc(),
                DurableTask.next_run_at.asc(),
                DurableTask.task_id.asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        task = await select_allowed(aged_query)
        if task is None:
            priority_query = (
                base_query.order_by(
                    DurableTask.priority.desc(),
                    DurableTask.next_run_at.asc(),
                    DurableTask.created_at.asc(),
                    DurableTask.task_id.asc(),
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            task = await select_allowed(priority_query)
        if task is None:
            return None

        require_task_transition(TaskState(task.state), TaskState.RUNNING)
        attempt_id = str(uuid.uuid4())
        lease_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        try:
            frozen_policy = TaskPolicy.model_validate(task.retry_policy_json)
        except ValidationError as exc:
            raise TaskSchemaInvalidError(
                "任务持久化执行策略无效，已拒绝领取。"
            ) from exc
        if (
            task.timeout_seconds != frozen_policy.timeout_seconds
            or task.max_attempts != frozen_policy.max_attempts
        ):
            raise TaskSchemaInvalidError("任务执行策略快照不一致，已拒绝领取。")
        lease_seconds = frozen_policy.lease_seconds
        expires_at = now + timedelta(seconds=lease_seconds)
        task.state = TaskState.RUNNING.value
        task.attempt_count += 1
        task.fence_generation += 1
        task.version += 1
        task.updated_at = now
        attempt = TaskAttempt(
            attempt_id=attempt_id,
            task_id=task.task_id,
            attempt_no=task.attempt_count,
            worker_id=worker_id,
            outcome="running",
            started_at=now,
        )
        self._session.add(attempt)
        await self._session.flush([task, attempt])
        lease = TaskLease(
            lease_id=lease_id,
            task_id=task.task_id,
            attempt_id=attempt_id,
            lease_token_hash=_token_hash(token),
            fence_generation=task.fence_generation,
            owner_id=worker_id,
            acquired_at=now,
            renewed_at=now,
            expires_at=expires_at,
        )
        self._session.add(lease)
        await self._session.flush([lease])
        await append_task_event(
            self._session,
            task,
            event_type="TaskLeaseClaimed",
            occurred_at=now,
            actor_id=None,
            details={"attempt_id": attempt_id, "attempt_no": task.attempt_count},
        )

        artifact_result = await self._session.execute(
            select(TaskPayloadArtifact)
            .where(TaskPayloadArtifact.artifact_id == task.input_artifact_id)
            .limit(1)
        )
        artifact = artifact_result.scalar_one()
        return ClaimedTask(
            task_id=task.task_id,
            task_type=task.task_type,
            schema_version=task.schema_version,
            organization_id=task.organization_id,
            actor_id=task.actor_id,
            resource_type=task.resource_type,
            resource_id=task.resource_id,
            input_payload=artifact.payload_json,
            timeout_seconds=task.timeout_seconds,
            lease_seconds=lease_seconds,
            max_attempts=task.max_attempts,
            deadline_at=task.deadline_at,
            retry_policy=frozen_policy,
            attempt_id=attempt_id,
            attempt_no=task.attempt_count,
            worker_id=worker_id,
            lease_token=token,
            lease_expires_at=expires_at,
            fence_generation=task.fence_generation,
            correlation_id=task.correlation_id,
            trace_id=task.trace_id,
        )

    async def _control_allows_claim(
        self,
        control: TaskTypeControl,
        *,
        task: DurableTask,
        now: datetime,
    ) -> bool:
        if control.is_paused:
            return False
        if control.max_concurrency is not None:
            running_result = await self._session.execute(
                select(func.count(DurableTask.task_id))
                .where(DurableTask.organization_id == task.organization_id)
                .where(DurableTask.task_type == task.task_type)
                .where(
                    DurableTask.state.in_(
                        [TaskState.RUNNING.value, TaskState.CANCEL_REQUESTED.value]
                    )
                )
            )
            if int(running_result.scalar_one() or 0) >= control.max_concurrency:
                return False
        if control.rate_limit_per_minute is not None:
            recent_result = await self._session.execute(
                select(func.count(TaskAttempt.attempt_id))
                .join(DurableTask, DurableTask.task_id == TaskAttempt.task_id)
                .where(DurableTask.organization_id == task.organization_id)
                .where(DurableTask.task_type == task.task_type)
                .where(TaskAttempt.started_at >= now - timedelta(minutes=1))
            )
            if int(recent_result.scalar_one() or 0) >= control.rate_limit_per_minute:
                return False
        return True

    async def renew_lease(self, claim: ClaimedTask) -> ClaimedTask:
        execution = self.execution(claim)
        task, lease = await execution._load_current()
        now = self._clock.now()
        lease.renewed_at = now
        lease.expires_at = now + timedelta(seconds=claim.lease_seconds)
        task.version += 1
        task.updated_at = now
        await append_task_event(
            self._session,
            task,
            event_type="TaskLeaseRenewed",
            occurred_at=now,
            actor_id=None,
            details={"attempt_id": claim.attempt_id},
        )
        await self._session.flush([task, lease])
        return claim.model_copy(update={"lease_expires_at": lease.expires_at})

    async def complete(
        self,
        claim: ClaimedTask,
        completion: TaskCompletion,
    ) -> TaskState:
        task, lease = await self.execution(claim)._load_current()
        if claim.deadline_at is not None and claim.deadline_at <= self._clock.now():
            raise TaskExecutionError(
                code="deadline_expired",
                message="任务截止时间已过。",
                kind=TaskFailureKind.TIMEOUT,
            )
        state = TaskState(task.state)
        require_task_transition(state, TaskState.SUCCEEDED)
        attempt = await self._load_attempt(lease.attempt_id)
        try:
            result_items = completion.result_items_payload()
        except (TypeError, ValueError) as exc:
            raise TaskSchemaInvalidError(
                "任务结果项必须是数量和大小受限的业务对象引用。"
            ) from exc
        self._session.add(
            TaskResultRef(
                task_id=task.task_id,
                result_kind=completion.result_kind.value,
                resource_type=completion.resource_type,
                resource_id=completion.resource_id,
                location=completion.location,
                saved_items_json=result_items["saved_items"],
                remaining_items_json=result_items["remaining_items"],
                retryable_items_json=result_items["retryable_items"],
                created_at=self._clock.now(),
            )
        )
        now = self._clock.now()
        task.state = TaskState.SUCCEEDED.value
        task.completed_at = now
        task.updated_at = now
        task.version += 1
        task.fence_generation += 1
        task.last_error_code = None
        task.last_error_message = None
        attempt.outcome = "succeeded"
        attempt.finished_at = now
        await append_task_event(
            self._session,
            task,
            event_type="TaskSucceeded",
            occurred_at=now,
            actor_id=None,
            details={
                "attempt_id": attempt.attempt_id,
                "result_kind": completion.result_kind.value,
                "result_resource_type": completion.resource_type,
                "result_resource_id": completion.resource_id,
            },
        )
        await self._session.delete(lease)
        await self._session.flush()
        return TaskState.SUCCEEDED

    async def fail(
        self,
        claim: ClaimedTask,
        *,
        code: str,
        kind: TaskFailureKind,
    ) -> TaskState:
        task, lease = await self.execution(claim)._load_current()
        state = TaskState(task.state)
        attempt = await self._load_attempt(lease.attempt_id)
        now = self._clock.now()
        if state is TaskState.CANCEL_REQUESTED:
            target = TaskState.CANCELLED
            attempt.outcome = "cancelled"
            task.completed_at = now
        elif code == "deadline_expired":
            target = TaskState.DEAD_LETTER
            attempt.outcome = "dead_letter"
            task.completed_at = now
        elif self._should_retry(task, code=code, kind=kind, now=now):
            target = TaskState.RETRY_WAIT
            attempt.outcome = "retry_wait"
            task.next_run_at = now + timedelta(seconds=self._backoff_seconds(task))
        else:
            target = TaskState.DEAD_LETTER
            attempt.outcome = "dead_letter"
            task.completed_at = now
        require_task_transition(state, target)
        task.state = target.value
        if target is TaskState.CANCELLED:
            task.last_error_code = None
            task.last_error_message = None
        else:
            task.last_error_code = code
            task.last_error_message = (
                "任务截止时间已过，未再保存晚到结果。"
                if code == "deadline_expired"
                else self._safe_error_message(kind, target=target)
            )
        task.updated_at = now
        task.version += 1
        task.fence_generation += 1
        attempt.error_code = code
        attempt.error_classification = kind.value
        attempt.finished_at = now
        await append_task_event(
            self._session,
            task,
            event_type="TaskAttemptFailed",
            occurred_at=now,
            actor_id=None,
            details={
                "attempt_id": attempt.attempt_id,
                "error_code": code,
                "error_classification": kind.value,
            },
        )
        followup_event = {
            TaskState.RETRY_WAIT: "TaskRetryScheduled",
            TaskState.DEAD_LETTER: "TaskDeadLettered",
            TaskState.CANCELLED: "TaskCancelAcknowledged",
        }[target]
        await append_task_event(
            self._session,
            task,
            event_type=followup_event,
            occurred_at=now,
            actor_id=None,
            details={"attempt_id": attempt.attempt_id},
        )
        await self._session.delete(lease)
        await self._session.flush()
        return target

    async def acknowledge_cancel(self, claim: ClaimedTask) -> TaskState:
        task, lease = await self.execution(claim)._load_current()
        state = TaskState(task.state)
        require_task_transition(state, TaskState.CANCELLED)
        attempt = await self._load_attempt(lease.attempt_id)
        now = self._clock.now()
        task.state = TaskState.CANCELLED.value
        task.last_error_code = None
        task.last_error_message = None
        task.completed_at = now
        task.updated_at = now
        task.version += 1
        task.fence_generation += 1
        attempt.outcome = "cancelled"
        attempt.error_code = None
        attempt.error_classification = None
        attempt.finished_at = now
        await append_task_event(
            self._session,
            task,
            event_type="TaskCancelAcknowledged",
            occurred_at=now,
            actor_id=None,
            details={"attempt_id": attempt.attempt_id},
        )
        await self._session.delete(lease)
        await self._session.flush()
        return TaskState.CANCELLED

    async def recover_expired(self, *, limit: int = 100) -> int:
        now = self._clock.now()
        result = await self._session.execute(
            select(DurableTask, TaskLease)
            .join(TaskLease, TaskLease.task_id == DurableTask.task_id)
            .where(TaskLease.expires_at <= now)
            .where(
                DurableTask.state.in_(
                    [TaskState.RUNNING.value, TaskState.CANCEL_REQUESTED.value]
                )
            )
            .order_by(TaskLease.expires_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        rows = result.all()
        for task, lease in rows:
            attempt_result = await self._session.execute(
                select(TaskAttempt)
                .where(TaskAttempt.attempt_id == lease.attempt_id)
                .with_for_update()
                .limit(1)
            )
            attempt = attempt_result.scalar_one()
            state = TaskState(task.state)
            if state is TaskState.CANCEL_REQUESTED:
                target = TaskState.CANCELLED
                attempt.outcome = "cancelled"
                task.completed_at = now
            elif task.deadline_at is not None and task.deadline_at <= now:
                target = TaskState.DEAD_LETTER
                attempt.outcome = "dead_letter"
                task.last_error_code = "deadline_expired"
                task.last_error_message = "任务截止时间已过，未再执行。"
                task.completed_at = now
            elif task.attempt_count >= task.max_attempts:
                target = TaskState.DEAD_LETTER
                attempt.outcome = "dead_letter"
                task.last_error_code = "lease_expired_attempts_exhausted"
                task.last_error_message = (
                    "任务执行中断，重试次数已用尽，可联系管理员处理。"
                )
                task.completed_at = now
            else:
                target = TaskState.RETRY_WAIT
                attempt.outcome = "lease_expired"
                task.last_error_code = "lease_expired"
                task.last_error_message = "任务执行中断，将自动重试。"
                task.next_run_at = now + timedelta(seconds=self._backoff_seconds(task))
            require_task_transition(state, target)
            task.state = target.value
            task.fence_generation += 1
            task.version += 1
            task.updated_at = now
            attempt.finished_at = now
            await append_task_event(
                self._session,
                task,
                event_type="TaskLeaseExpired",
                occurred_at=now,
                actor_id=None,
                details={"attempt_id": attempt.attempt_id},
            )
            followup_event = {
                TaskState.RETRY_WAIT: "TaskRetryScheduled",
                TaskState.DEAD_LETTER: "TaskDeadLettered",
                TaskState.CANCELLED: "TaskCancelAcknowledged",
            }[target]
            await append_task_event(
                self._session,
                task,
                event_type=followup_event,
                occurred_at=now,
                actor_id=None,
                details={"attempt_id": attempt.attempt_id},
            )
            await self._session.delete(lease)
        await self._session.flush()
        return len(rows)

    async def acknowledge_unleased_cancellations(self, *, limit: int = 100) -> int:
        """Acknowledge queued/retry cancellations that have no in-flight Worker."""

        now = self._clock.now()
        result = await self._session.execute(
            select(DurableTask)
            .where(DurableTask.state == TaskState.CANCEL_REQUESTED.value)
            .where(
                ~exists(
                    select(TaskLease.lease_id).where(
                        TaskLease.task_id == DurableTask.task_id
                    )
                )
            )
            .order_by(DurableTask.updated_at.asc(), DurableTask.task_id.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        tasks = list(result.scalars())
        for task in tasks:
            require_task_transition(TaskState.CANCEL_REQUESTED, TaskState.CANCELLED)
            task.state = TaskState.CANCELLED.value
            task.last_error_code = None
            task.last_error_message = None
            task.completed_at = now
            task.updated_at = now
            task.version += 1
            task.fence_generation += 1
            await append_task_event(
                self._session,
                task,
                event_type="TaskCancelAcknowledged",
                occurred_at=now,
                actor_id=None,
            )
        await self._session.flush(tasks)
        return len(tasks)

    async def reap_expired_queued(self, *, limit: int = 100) -> int:
        now = self._clock.now()
        result = await self._session.execute(
            select(DurableTask)
            .where(DurableTask.state == TaskState.QUEUED.value)
            .where(DurableTask.deadline_at.is_not(None))
            .where(DurableTask.deadline_at <= now)
            .order_by(DurableTask.deadline_at.asc(), DurableTask.task_id.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        tasks = list(result.scalars())
        for task in tasks:
            require_task_transition(TaskState.QUEUED, TaskState.DEAD_LETTER)
            task.state = TaskState.DEAD_LETTER.value
            task.last_error_code = "deadline_expired"
            task.last_error_message = "任务截止时间已过，未再执行。"
            task.completed_at = now
            task.updated_at = now
            task.version += 1
            task.fence_generation += 1
            await append_task_event(
                self._session,
                task,
                event_type="TaskDeadLettered",
                occurred_at=now,
                actor_id=None,
                details={"error_code": "deadline_expired"},
            )
        await self._session.flush(tasks)
        return len(tasks)

    async def release_due_retries(self, *, limit: int = 100) -> int:
        now = self._clock.now()
        result = await self._session.execute(
            select(DurableTask)
            .where(DurableTask.state == TaskState.RETRY_WAIT.value)
            .where(
                or_(
                    DurableTask.next_run_at <= now,
                    DurableTask.deadline_at <= now,
                )
            )
            .order_by(DurableTask.next_run_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        tasks = list(result.scalars())
        for task in tasks:
            if task.deadline_at is not None and task.deadline_at <= now:
                target = TaskState.DEAD_LETTER
                task.last_error_code = "deadline_expired"
                task.last_error_message = "任务截止时间已过，未再执行。"
                task.completed_at = now
            else:
                target = TaskState.QUEUED
            require_task_transition(TaskState.RETRY_WAIT, target)
            task.state = target.value
            task.version += 1
            task.updated_at = now
            await append_task_event(
                self._session,
                task,
                event_type=(
                    "TaskDeadLettered"
                    if target is TaskState.DEAD_LETTER
                    else "TaskRetryReleased"
                ),
                occurred_at=now,
                actor_id=None,
            )
        await self._session.flush(tasks)
        return len(tasks)

    @staticmethod
    def _backoff_seconds(task: DurableTask) -> int:
        return retry_backoff_seconds(task.attempt_count, task.retry_policy_json)

    async def _load_attempt(self, attempt_id: str) -> TaskAttempt:
        result = await self._session.execute(
            select(TaskAttempt)
            .where(TaskAttempt.attempt_id == attempt_id)
            .with_for_update()
            .limit(1)
        )
        return result.scalar_one()

    @staticmethod
    def _should_retry(
        task: DurableTask,
        *,
        code: str,
        kind: TaskFailureKind,
        now: datetime,
    ) -> bool:
        if task.attempt_count >= task.max_attempts:
            return False
        if task.deadline_at is not None and task.deadline_at <= now:
            return False
        policy = task.retry_policy_json
        if code in policy["terminal_error_codes"]:
            return False
        if code in policy["retryable_error_codes"]:
            return True
        return kind in {
            TaskFailureKind.PROVIDER_TEMPORARY,
            TaskFailureKind.SYSTEM_DEFECT,
            TaskFailureKind.TIMEOUT,
        }

    @staticmethod
    def _safe_error_message(
        kind: TaskFailureKind,
        *,
        target: TaskState,
    ) -> str:
        if target is TaskState.DEAD_LETTER and kind in {
            TaskFailureKind.PROVIDER_TEMPORARY,
            TaskFailureKind.SYSTEM_DEFECT,
            TaskFailureKind.TIMEOUT,
        }:
            return "任务执行中断，重试次数已用尽，可联系管理员处理。"
        messages = {
            TaskFailureKind.PROVIDER_TEMPORARY: "外部服务暂时不可用，任务将按策略重试。",
            TaskFailureKind.INVALID_INPUT: "任务输入不符合处理要求。",
            TaskFailureKind.PERMISSION_DENIED: "任务无权访问所需对象。",
            TaskFailureKind.BUSINESS_CONFLICT: "任务因业务状态变化未能继续。",
            TaskFailureKind.SYSTEM_DEFECT: "任务处理发生系统错误。",
            TaskFailureKind.TIMEOUT: "任务处理超时。",
        }
        return messages[kind]


__all__ = ["FencedTaskExecution", "SQLAlchemyTaskWorkerStore"]

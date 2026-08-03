"""System Admin HTTP adapter for scoped durable-task operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.permissions import (
    TASK_RUNTIME_OPERATE_PERMISSION,
    TASK_RUNTIME_READ_PERMISSION,
    require_admin_permission,
    user_has_persisted_admin_permission,
)
from common.api.response import error_response, success_response
from common.db.models import User
from common.db.session import get_db
from task_runtime.composition import get_application_task_registry
from task_runtime.contracts import TaskState
from task_runtime.errors import (
    IdempotencyKeyReusedError,
    TaskAccessDeniedError,
    TaskLeaseLostError,
    TaskNotFoundError,
    TaskQueryInvalidError,
    TaskRuntimeError,
    TaskSchemaInvalidError,
    TaskTransitionError,
    TaskTypeNotRegisteredError,
)
from task_runtime.operator_service import (
    OperatorActor,
    SQLAlchemyTaskAccessPolicy,
    TaskAccessPolicyPort,
    TaskOperatorService,
)
from task_runtime.registry import TaskRegistry

router = APIRouter(prefix="/task-runtime", tags=["admin-task-runtime"])


class TaskTypeControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=500)


class TaskTypeLimitsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    max_concurrency: int | None = Field(default=None, ge=1, le=10_000)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=1_000_000)
    reason: str = Field(min_length=1, max_length=500)


class TaskOperatorCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, min_length=1, max_length=500)


async def require_task_runtime_reader(
    current_user: User = Depends(
        require_admin_permission(TASK_RUNTIME_READ_PERMISSION)
    ),
) -> User:
    return current_user


async def require_task_runtime_operator(
    current_user: User = Depends(
        require_admin_permission(TASK_RUNTIME_OPERATE_PERMISSION)
    ),
) -> User:
    return current_user


def get_task_access_policy(
    db: AsyncSession = Depends(get_db),
) -> TaskAccessPolicyPort:
    return SQLAlchemyTaskAccessPolicy(db)


def get_task_registry() -> TaskRegistry:
    return get_application_task_registry()


def _actor(user: User, *, operate: bool = False) -> OperatorActor:
    capabilities = {"task_runtime.read"}
    if operate:
        capabilities.add("task_runtime.operate")
    return OperatorActor(
        actor_id=str(user.user_id),
        capabilities=frozenset(capabilities),
    )


async def get_task_reader_actor(
    user: User = Depends(require_task_runtime_reader),
    db: AsyncSession = Depends(get_db),
) -> OperatorActor:
    capabilities = {TASK_RUNTIME_READ_PERMISSION}
    if await user_has_persisted_admin_permission(
        db,
        user,
        TASK_RUNTIME_OPERATE_PERMISSION,
    ):
        capabilities.add(TASK_RUNTIME_OPERATE_PERMISSION)
    return OperatorActor(
        actor_id=str(user.user_id),
        capabilities=frozenset(capabilities),
    )


def _error_response(exc: TaskRuntimeError) -> JSONResponse:
    if isinstance(exc, TaskAccessDeniedError):
        status = 403
    elif isinstance(exc, TaskNotFoundError):
        status = 404
    elif isinstance(
        exc,
        (IdempotencyKeyReusedError, TaskLeaseLostError, TaskTransitionError),
    ):
        status = 409
    elif isinstance(
        exc,
        (TaskQueryInvalidError, TaskSchemaInvalidError, TaskTypeNotRegisteredError),
    ):
        status = 422
    else:
        status = 400
    return JSONResponse(
        status_code=status,
        content=error_response(exc.code, message=exc.message),
    )


def _success(value: object) -> JSONResponse:
    return JSONResponse(content=jsonable_encoder(success_response(value)))


@router.get("/tasks")
async def list_tasks(
    organization_id: str = Query(min_length=1, max_length=120),
    state: list[TaskState] | None = Query(default=None),
    task_type: str | None = Query(default=None, min_length=3, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=500),
    actor: OperatorActor = Depends(get_task_reader_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        page = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).list_tasks(
            organization_id=organization_id,
            actor=actor,
            states=frozenset(state) if state else None,
            task_type=task_type,
            limit=limit,
            cursor=cursor,
        )
    except TaskRuntimeError as exc:
        return _error_response(exc)
    return _success(page)


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    actor: OperatorActor = Depends(get_task_reader_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        detail = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).get_task(task_id, actor=actor)
    except (TaskAccessDeniedError, TaskNotFoundError) as exc:
        return _error_response(exc)
    return _success(detail)


@router.post("/tasks/{task_id}/redrive")
async def redrive_task(
    task_id: str,
    body: TaskOperatorCommandRequest | None = None,
    idempotency_key: str = Header(
        min_length=1, max_length=200, alias="Idempotency-Key"
    ),
    current_user: User = Depends(require_task_runtime_operator),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        reference = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).redrive_dead_letter(
            task_id=task_id,
            actor=_actor(current_user, operate=True),
            idempotency_key=idempotency_key,
            reason=body.reason if body is not None else None,
        )
        await db.commit()
    except TaskRuntimeError as exc:
        await db.rollback()
        return _error_response(exc)
    return _success(reference)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    body: TaskOperatorCommandRequest | None = None,
    idempotency_key: str = Header(
        min_length=1, max_length=200, alias="Idempotency-Key"
    ),
    current_user: User = Depends(require_task_runtime_operator),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        detail = await TaskOperatorService(
            db,
            registry=registry,
            access_policy=access_policy,
        ).request_cancel(
            task_id=task_id,
            actor=_actor(current_user, operate=True),
            idempotency_key=idempotency_key,
            reason=body.reason if body is not None else None,
        )
        await db.commit()
    except TaskRuntimeError as exc:
        await db.rollback()
        return _error_response(exc)
    return _success(detail)


@router.post("/task-types/{task_type}/pause")
async def pause_task_type(
    task_type: str,
    body: TaskTypeControlRequest,
    idempotency_key: str = Header(
        min_length=1, max_length=200, alias="Idempotency-Key"
    ),
    current_user: User = Depends(require_task_runtime_operator),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        view = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).pause_task_type(
            organization_id=body.organization_id,
            task_type=task_type,
            actor=_actor(current_user, operate=True),
            idempotency_key=idempotency_key,
            reason=body.reason,
        )
        await db.commit()
    except TaskRuntimeError as exc:
        await db.rollback()
        return _error_response(exc)
    return _success(view)


@router.post("/task-types/{task_type}/resume")
async def resume_task_type(
    task_type: str,
    body: TaskTypeControlRequest,
    idempotency_key: str = Header(
        min_length=1, max_length=200, alias="Idempotency-Key"
    ),
    current_user: User = Depends(require_task_runtime_operator),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        view = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).resume_task_type(
            organization_id=body.organization_id,
            task_type=task_type,
            actor=_actor(current_user, operate=True),
            idempotency_key=idempotency_key,
            reason=body.reason,
        )
        await db.commit()
    except TaskRuntimeError as exc:
        await db.rollback()
        return _error_response(exc)
    return _success(view)


@router.put("/task-types/{task_type}/limits")
async def configure_task_type_limits(
    task_type: str,
    body: TaskTypeLimitsRequest,
    idempotency_key: str = Header(
        min_length=1, max_length=200, alias="Idempotency-Key"
    ),
    current_user: User = Depends(require_task_runtime_operator),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        view = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).configure_task_type_limits(
            organization_id=body.organization_id,
            task_type=task_type,
            actor=_actor(current_user, operate=True),
            idempotency_key=idempotency_key,
            max_concurrency=body.max_concurrency,
            rate_limit_per_minute=body.rate_limit_per_minute,
            reason=body.reason,
        )
        await db.commit()
    except TaskRuntimeError as exc:
        await db.rollback()
        return _error_response(exc)
    return _success(view)


@router.get("/health")
async def task_runtime_health(
    organization_id: str = Query(min_length=1, max_length=120),
    actor: OperatorActor = Depends(get_task_reader_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_task_registry),
    access_policy: TaskAccessPolicyPort = Depends(get_task_access_policy),
) -> JSONResponse:
    try:
        health = await TaskOperatorService(
            db, registry=registry, access_policy=access_policy
        ).health(
            organization_id=organization_id,
            actor=actor,
        )
    except TaskRuntimeError as exc:
        return _error_response(exc)
    return _success(health)


__all__ = [
    "get_task_access_policy",
    "get_task_reader_actor",
    "get_task_registry",
    "require_task_runtime_operator",
    "require_task_runtime_reader",
    "router",
]

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.services.practice_session_service import (
    PracticeRuntimeDescriptorService,
    PracticeServiceError,
)
from common.training_tasks.schemas import (
    TrainingTaskCompleteRequest,
    TrainingTaskCreate,
    TrainingTaskListResponse,
    TrainingTaskResponse,
    TrainingTaskStartSessionRequest,
    TrainingTaskStartSessionResponse,
    TrainingTaskStatus,
    TrainingTaskUpdate,
)
from common.training_tasks.service import (
    can_manage_training_tasks,
    complete_training_task,
    create_training_task,
    get_training_task,
    list_training_tasks,
    mark_training_task_terminal,
    start_training_task_session,
    update_training_task,
)

router = APIRouter(prefix="/training-tasks")


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": None}


def _error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_training_task_endpoint(
    payload: TrainingTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not can_manage_training_tasks(current_user):
        raise HTTPException(status_code=403, detail="[ROLE_REQUIRED]")
    task = await create_training_task(db, payload)
    return _success(TrainingTaskResponse.model_validate(task).model_dump(mode="json"))


@router.get("")
async def list_training_tasks_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    task_status: TrainingTaskStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    total, tasks = await list_training_tasks(
        db,
        current_user,
        page=page,
        page_size=page_size,
        status=task_status.value if task_status else None,
    )
    response = TrainingTaskListResponse(
        total=total,
        items=[TrainingTaskResponse.model_validate(task) for task in tasks],
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )
    return _success(response.model_dump(mode="json"))


@router.post("/{task_id}/complete")
async def complete_training_task_endpoint(
    task_id: str,
    payload: TrainingTaskCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = await get_training_task(db, task_id, current_user)
    if task is None:
        raise _error(404, "[TRAINING_TASK_NOT_FOUND]")
    try:
        updated = await complete_training_task(db, task, payload)
    except LookupError as exc:
        await db.rollback()
        raise _error(404, str(exc)) from exc
    except PermissionError as exc:
        await db.rollback()
        raise _error(403, str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise _error(409, str(exc)) from exc
    return _success(TrainingTaskResponse.model_validate(updated).model_dump(mode="json"))


async def _mark_terminal_endpoint(
    task_id: str,
    terminal_status: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any]:
    if not can_manage_training_tasks(current_user):
        raise _error(403, "[ROLE_REQUIRED]")
    task = await get_training_task(db, task_id, current_user)
    if task is None:
        raise _error(404, "[TRAINING_TASK_NOT_FOUND]")
    try:
        updated = await mark_training_task_terminal(
            db,
            task,
            status=terminal_status,
        )
    except ValueError as exc:
        await db.rollback()
        raise _error(409, str(exc)) from exc
    return _success(TrainingTaskResponse.model_validate(updated).model_dump(mode="json"))


@router.post("/{task_id}/cancel")
async def cancel_training_task_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await _mark_terminal_endpoint(task_id, "cancelled", current_user, db)


@router.post("/{task_id}/expire")
async def expire_training_task_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await _mark_terminal_endpoint(task_id, "expired", current_user, db)


@router.get("/{task_id}")
async def get_training_task_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = await get_training_task(db, task_id, current_user)
    if task is None:
        raise HTTPException(status_code=404, detail="[TRAINING_TASK_NOT_FOUND]")
    return _success(TrainingTaskResponse.model_validate(task).model_dump(mode="json"))


@router.patch("/{task_id}")
async def update_training_task_endpoint(
    task_id: str,
    payload: TrainingTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not can_manage_training_tasks(current_user):
        raise HTTPException(status_code=403, detail="[ROLE_REQUIRED]")
    task = await get_training_task(db, task_id, current_user)
    if task is None:
        raise HTTPException(status_code=404, detail="[TRAINING_TASK_NOT_FOUND]")
    updated = await update_training_task(db, task, payload)
    return _success(TrainingTaskResponse.model_validate(updated).model_dump(mode="json"))


@router.post("/{task_id}/start-session")
async def start_training_task_session_endpoint(
    task_id: str,
    payload: TrainingTaskStartSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = await get_training_task(db, task_id, current_user)
    if task is None:
        raise _error(404, "[TRAINING_TASK_NOT_FOUND]")
    try:
        updated_task, session = await start_training_task_session(
            db,
            task,
            payload,
            current_user=current_user,
        )
    except PracticeServiceError as exc:
        await db.rollback()
        raise _error(exc.status_code, exc.error_code) from exc
    except ValueError as exc:
        await db.rollback()
        raise _error(409, str(exc)) from exc

    session_response = PracticeRuntimeDescriptorService.build_session_response(
        session,
        scenario_type=str(updated_task.scenario_type),
    )
    response = TrainingTaskStartSessionResponse.model_validate(
        {
            **TrainingTaskResponse.model_validate(updated_task).model_dump(),
            "session": session_response,
        }
    )
    return _success(response.model_dump(mode="json"))

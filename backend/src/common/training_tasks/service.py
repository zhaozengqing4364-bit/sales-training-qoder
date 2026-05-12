from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, TrainingTask, User
from common.db.schemas import ScenarioType, SessionCreate
from common.services.practice_session_service import PracticeSessionCreateService
from common.training_tasks.schemas import (
    TrainingTaskCompleteRequest,
    TrainingTaskCreate,
    TrainingTaskStartSessionRequest,
    TrainingTaskUpdate,
)

MANAGER_ROLES = {"admin", "support"}


def can_manage_training_tasks(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() in MANAGER_ROLES


def can_read_training_task(task: TrainingTask, user: User) -> bool:
    return can_manage_training_tasks(user) or str(task.assignee_id) == str(user.user_id)


async def get_training_task(
    db: AsyncSession,
    task_id: str,
    current_user: User,
) -> TrainingTask | None:
    task = await db.get(TrainingTask, task_id)
    if task is None or not can_read_training_task(task, current_user):
        return None
    return task


async def list_training_tasks(
    db: AsyncSession,
    current_user: User,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[int, list[TrainingTask]]:
    filters: list[Any] = []
    if not can_manage_training_tasks(current_user):
        filters.append(TrainingTask.assignee_id == str(current_user.user_id))
    if status:
        filters.append(TrainingTask.status == status)

    count_stmt = select(func.count()).select_from(TrainingTask).where(*filters)
    total = int((await db.execute(count_stmt)).scalar() or 0)

    stmt = (
        select(TrainingTask)
        .where(*filters)
        .order_by(TrainingTask.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return total, list(result.scalars().all())


async def create_training_task(
    db: AsyncSession,
    payload: TrainingTaskCreate,
) -> TrainingTask:
    task = TrainingTask(**payload.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_training_task(
    db: AsyncSession,
    task: TrainingTask,
    payload: TrainingTaskUpdate,
) -> TrainingTask:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


def _training_task_focus_payload(task: TrainingTask) -> dict[str, str]:
    payload = {
        "version": "training_task_focus_v1",
        "training_task_id": str(task.task_id),
        "goal": str(task.goal),
    }
    if task.focus_intent:
        payload["focus_intent"] = str(task.focus_intent)
    return payload


def _training_task_context(task: TrainingTask) -> dict[str, str]:
    context = {
        "task_id": str(task.task_id),
        "title": str(task.title),
        "goal": str(task.goal),
        "source": str(task.source),
    }
    if task.focus_intent:
        context["focus_intent"] = str(task.focus_intent)
    return context


async def start_training_task_session(
    db: AsyncSession,
    task: TrainingTask,
    payload: TrainingTaskStartSessionRequest,
    *,
    current_user: User,
) -> tuple[TrainingTask, Any]:
    if task.status != "assigned":
        raise ValueError("[INVALID_TRAINING_TASK_TRANSITION]")

    session_payload = SessionCreate(
        scenario_type=ScenarioType(str(task.scenario_type)),
        presentation_id=payload.presentation_id,
        scenario_id=payload.scenario_id,
        agent_id=payload.agent_id,
        persona_id=payload.persona_id,
        voice_mode=payload.voice_mode,
        runtime_profile_id=payload.runtime_profile_id,
        focus_intent=_training_task_focus_payload(task),
    )
    create_result = await PracticeSessionCreateService(db).create_session(
        session_payload,
        current_user=current_user,
    )
    session = create_result.session
    snapshot = deepcopy(session.voice_policy_snapshot) if isinstance(session.voice_policy_snapshot, dict) else {}
    snapshot["training_task_context"] = _training_task_context(task)
    session.voice_policy_snapshot = snapshot
    task.status = "in_progress"
    await db.commit()
    await db.refresh(task)
    await db.refresh(session)
    return task, session


def _summary_text(value: Any, key: str) -> str | None:
    if not isinstance(value, dict):
        return None
    text = value.get(key)
    return str(text) if text is not None else None


def _build_before_after_summary(
    task: TrainingTask,
    session: PracticeSession,
) -> dict[str, Any]:
    snapshot = session.effectiveness_snapshot if isinstance(session.effectiveness_snapshot, dict) else {}
    return {
        "before": {
            "goal": str(task.goal),
            "focus_intent": task.focus_intent,
        },
        "after": {
            "session_id": str(session.session_id),
            "session_status": str(session.status),
            "overall_result": snapshot.get("overall_result"),
            "main_capability_passed": snapshot.get("main_capability_passed"),
            "main_issue": _summary_text(snapshot.get("main_issue"), "issue_text"),
            "next_goal": _summary_text(snapshot.get("next_goal"), "goal_text"),
        },
    }


async def complete_training_task(
    db: AsyncSession,
    task: TrainingTask,
    payload: TrainingTaskCompleteRequest,
) -> TrainingTask:
    if task.status in {"completed", "expired", "cancelled"}:
        raise ValueError("[INVALID_TRAINING_TASK_TRANSITION]")
    if task.status != "in_progress":
        raise ValueError("[INVALID_TRAINING_TASK_TRANSITION]")
    session = await db.get(PracticeSession, payload.session_id)
    if session is None:
        raise LookupError("[SESSION_NOT_FOUND]")
    if str(session.user_id) != str(task.assignee_id):
        raise PermissionError("[ACCESS_DENIED]")
    if str(session.status) not in {"completed", "scoring"}:
        raise ValueError("[SESSION_NOT_TERMINAL]")

    task.resulting_session_id = str(session.session_id)
    task.before_after_summary = _build_before_after_summary(task, session)
    task.status = "completed"
    await db.commit()
    await db.refresh(task)
    return task


async def mark_training_task_terminal(
    db: AsyncSession,
    task: TrainingTask,
    *,
    status: str,
) -> TrainingTask:
    if task.status in {"completed", "expired", "cancelled"}:
        raise ValueError("[INVALID_TRAINING_TASK_TRANSITION]")
    if status not in {"cancelled", "expired"}:
        raise ValueError("[INVALID_TRAINING_TASK_TRANSITION]")
    task.status = status
    await db.commit()
    await db.refresh(task)
    return task

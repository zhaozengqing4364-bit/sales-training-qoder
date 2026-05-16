from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, TrainingTask, User
from common.db.schemas import ScenarioType, SessionCreate
from common.services.practice_session_service import (
    PracticeServiceError,
    PracticeSessionCreateService,
)
from common.training_tasks.schemas import (
    TrainingTaskBatchAssignAssignedItem,
    TrainingTaskBatchAssignReasonItem,
    TrainingTaskBatchAssignRequest,
    TrainingTaskBatchAssignResponse,
    TrainingTaskCompleteRequest,
    TrainingTaskCreate,
    TrainingTaskStartSessionRequest,
    TrainingTaskUpdate,
)
from curriculum_practice.models import PracticeTemplate

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
    data = payload.model_dump()
    data["practice_template_id"] = await _validated_practice_template_id(
        db,
        data.get("practice_template_id"),
    )
    task = TrainingTask(**data)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def batch_assign_training_tasks(
    db: AsyncSession,
    payload: TrainingTaskBatchAssignRequest,
    *,
    current_user: User,
) -> TrainingTaskBatchAssignResponse:
    try:
        template_id = str(UUID(str(payload.template_id)))
    except ValueError:
        return _batch_failed(payload.user_ids, "[PRACTICE_TEMPLATE_INVALID]")

    template = await db.get(PracticeTemplate, template_id)
    if template is None:
        return _batch_failed(payload.user_ids, "[PRACTICE_TEMPLATE_NOT_FOUND]")
    if template.status != "published":
        return _batch_failed(payload.user_ids, "[PRACTICE_TEMPLATE_NOT_PUBLISHED]")

    curriculum_reason = _validate_curriculum_plan_id(
        template,
        payload.curriculum_plan_id,
    )
    if curriculum_reason is not None:
        return _batch_failed(payload.user_ids, curriculum_reason)

    assigned: list[TrainingTaskBatchAssignAssignedItem] = []
    skipped: list[TrainingTaskBatchAssignReasonItem] = []
    failed: list[TrainingTaskBatchAssignReasonItem] = []
    assigner_department = getattr(current_user, "department", None)

    for user_id in payload.user_ids:
        assignee = await db.get(User, user_id)
        if assignee is None:
            failed.append(
                TrainingTaskBatchAssignReasonItem(
                    user_id=user_id,
                    reason="[USER_NOT_FOUND]",
                )
            )
            continue
        if getattr(assignee, "department", None) != assigner_department:
            failed.append(
                TrainingTaskBatchAssignReasonItem(
                    user_id=user_id,
                    reason="[DEPARTMENT_SCOPE_VIOLATION]",
                )
            )
            continue

        existing = (
            await db.execute(
                select(TrainingTask).where(
                    TrainingTask.assignee_id == user_id,
                    TrainingTask.practice_template_id == template_id,
                )
            )
        ).scalars().first()
        if existing is not None:
            skipped.append(
                TrainingTaskBatchAssignReasonItem(
                    user_id=user_id,
                    reason="[TRAINING_TASK_ALREADY_ASSIGNED]",
                )
            )
            continue

        task = TrainingTask(
            title=payload.title,
            assignee_id=user_id,
            scenario_type=payload.scenario_type.value,
            goal=payload.goal,
            focus_intent=payload.focus_intent,
            due_date=payload.due_date,
            completion_criteria=payload.completion_criteria,
            practice_template_id=template_id,
            curriculum_plan_id=payload.curriculum_plan_id,
            source="batch_assign",
            status="assigned",
        )
        db.add(task)
        await db.flush()
        assigned.append(
            TrainingTaskBatchAssignAssignedItem(
                user_id=user_id,
                task_id=str(task.task_id),
            )
        )

    await db.commit()
    return TrainingTaskBatchAssignResponse(
        assigned_count=len(assigned),
        skipped_count=len(skipped),
        failed_count=len(failed),
        assigned=assigned,
        skipped=skipped,
        failed=failed,
    )


def _batch_failed(
    user_ids: list[str],
    reason: str,
) -> TrainingTaskBatchAssignResponse:
    failed = [TrainingTaskBatchAssignReasonItem(user_id=user_id, reason=reason) for user_id in user_ids]
    return TrainingTaskBatchAssignResponse(
        assigned_count=0,
        skipped_count=0,
        failed_count=len(failed),
        assigned=[],
        skipped=[],
        failed=failed,
    )


def _validate_curriculum_plan_id(
    template: PracticeTemplate,
    curriculum_plan_id: str,
) -> str | None:
    curriculum_plan = template.curriculum_plan
    if not isinstance(curriculum_plan, dict):
        return "[CURRICULUM_PLAN_NOT_FOUND]"
    configured_id = (
        curriculum_plan.get("curriculum_plan_id")
        or curriculum_plan.get("plan_id")
        or curriculum_plan.get("id")
        or template.template_id
    )
    if str(configured_id) != str(curriculum_plan_id):
        return "[CURRICULUM_PLAN_NOT_FOUND]"
    stages = curriculum_plan.get("stages")
    if not isinstance(stages, list):
        return "[CURRICULUM_PLAN_INVALID]"
    stage_types = {stage.get("stage_type") for stage in stages if isinstance(stage, dict)}
    if not {"study", "exam", "practice"} <= stage_types:
        return "[CURRICULUM_PLAN_INVALID]"
    return None


async def update_training_task(
    db: AsyncSession,
    task: TrainingTask,
    payload: TrainingTaskUpdate,
) -> TrainingTask:
    update_data = payload.model_dump(exclude_unset=True)
    if "practice_template_id" in update_data:
        update_data["practice_template_id"] = await _validated_practice_template_id(
            db,
            update_data.get("practice_template_id"),
        )
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


async def _validated_practice_template_id(
    db: AsyncSession,
    practice_template_id: Any,
) -> str | None:
    if not practice_template_id:
        return None
    try:
        template_id = str(UUID(str(practice_template_id)))
    except ValueError as exc:
        raise ValueError("[PRACTICE_TEMPLATE_INVALID]") from exc
    template = await db.get(PracticeTemplate, template_id)
    if template is None:
        raise LookupError("[PRACTICE_TEMPLATE_NOT_FOUND]")
    if template.status != "published":
        raise ValueError("[PRACTICE_TEMPLATE_NOT_PUBLISHED]")
    return template_id


def _practice_template_id_for_session(task: TrainingTask) -> UUID | None:
    if not task.practice_template_id:
        return None
    try:
        return UUID(str(task.practice_template_id))
    except ValueError as exc:
        raise PracticeServiceError(
            "[PRACTICE_TEMPLATE_INVALID]",
            status_code=400,
        ) from exc


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
        practice_template_id=_practice_template_id_for_session(task),
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

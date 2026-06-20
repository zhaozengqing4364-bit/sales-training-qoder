from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, User
from common.db.schemas import SessionCreate
from common.services.practice_session_ports import (
    PracticeSessionPortError,
    PracticeTemplateRuntimeIdentity,
    register_practice_session_snapshot_applier,
    register_practice_template_runtime_identity_resolver,
)
from common.training_tasks.ports import (
    TrainingTaskPracticeTemplate,
    register_training_task_practice_template_resolver,
)
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.services.session_snapshots import (
    CurriculumSessionSnapshotError,
    apply_curriculum_snapshot_to_session,
)


async def resolve_curriculum_practice_template_runtime_identity(
    db: AsyncSession,
    session_data: SessionCreate,
    scenario_type_value: str,
    requested_agent_id: str | None,
    requested_persona_id: str | None,
) -> PracticeTemplateRuntimeIdentity | None:
    if session_data.practice_template_id is None:
        return None

    template = await db.get(
        PracticeTemplate,
        str(session_data.practice_template_id),
    )
    if template is None:
        raise PracticeSessionPortError("[PRACTICE_TEMPLATE_NOT_FOUND]", status_code=404)
    if template.status != "published":
        raise PracticeSessionPortError(
            "[PRACTICE_TEMPLATE_NOT_PUBLISHED]",
            status_code=400,
        )
    if template.scenario_type != scenario_type_value:
        raise PracticeSessionPortError(
            "[PRACTICE_TEMPLATE_SCENARIO_TYPE_MISMATCH]",
            status_code=400,
        )

    template_agent_id = str(template.agent_id)
    template_persona_id = str(template.persona_id)
    template_runtime_profile_id = str(template.runtime_profile_id)
    requested_runtime_profile_id = (
        str(session_data.runtime_profile_id) if session_data.runtime_profile_id else None
    )
    mismatched_fields: list[str] = []
    if requested_agent_id and requested_agent_id != template_agent_id:
        mismatched_fields.append("agent_id")
    if requested_persona_id and requested_persona_id != template_persona_id:
        mismatched_fields.append("persona_id")
    if (
        requested_runtime_profile_id
        and requested_runtime_profile_id != template_runtime_profile_id
    ):
        mismatched_fields.append("runtime_profile_id")
    if mismatched_fields:
        raise PracticeSessionPortError(
            "[PRACTICE_TEMPLATE_RUNTIME_IDENTITY_MISMATCH]",
            status_code=400,
            message="practice_template_id 已绑定固定 agent/persona/runtime_profile，请使用模板身份创建会话。",
            details={"mismatched_fields": mismatched_fields},
        )

    return PracticeTemplateRuntimeIdentity(
        agent_id=template_agent_id,
        persona_id=template_persona_id,
        runtime_profile_id=template_runtime_profile_id,
        voice_mode=str(template.voice_mode) if template.voice_mode else None,
    )


async def apply_curriculum_practice_session_snapshot(
    db: AsyncSession,
    session: PracticeSession,
    session_data: SessionCreate,
    scenario_type_value: str,
    current_user: User,
) -> None:
    try:
        await apply_curriculum_snapshot_to_session(
            db=db,
            session=session,
            practice_template_id=session_data.practice_template_id,
            scenario_type_value=scenario_type_value,
            actor_id=str(current_user.user_id),
        )
    except CurriculumSessionSnapshotError as exc:
        raise PracticeSessionPortError(
            exc.error_code,
            status_code=exc.status_code,
            message=exc.message,
        ) from exc


async def resolve_curriculum_training_task_practice_template(
    db: AsyncSession,
    template_id: str,
) -> TrainingTaskPracticeTemplate | None:
    template = await db.get(PracticeTemplate, template_id)
    if template is None:
        return None
    return TrainingTaskPracticeTemplate(
        template_id=str(template.template_id),
        status=str(template.status),
        curriculum_plan=template.curriculum_plan
        if isinstance(template.curriculum_plan, dict)
        else None,
    )


def register_curriculum_practice_session_contributor() -> None:
    register_practice_template_runtime_identity_resolver(
        resolve_curriculum_practice_template_runtime_identity,
    )
    register_practice_session_snapshot_applier(
        apply_curriculum_practice_session_snapshot,
    )
    register_training_task_practice_template_resolver(
        resolve_curriculum_training_task_practice_template,
    )

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.schemas import (
    NewcomerPathConfigPayload,
    NewcomerPathConfigSaveRequest,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    payload_from_revision,
)
from sales_trainer.services.path_config_operations import get_path_revision

AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS: frozenset[str] = frozenset(
    {
        "prompt_template_id",
        "prompt_revision_id",
        "scoring_prompt_template_id",
        "scoring_prompt_revision_id",
        "min_turns",
        "max_turns",
        "mastery_threshold",
        "allowed_interaction_types",
        "allowed_training_card_types",
        "chat_enabled",
        "allowed_ui_event_types",
        "max_cards_per_message",
        "streaming_enabled",
        "entry_resume_policy",
        "generation_timeout_seconds",
        "chat_welcome_message",
        "empty_response_recovery_message",
        "empty_response_recovery_prompts",
        "generation_failure_recovery_message",
        "generation_failure_recovery_prompts",
        "coach_mode",
        "correct_streak_to_increase_difficulty",
        "incorrect_streak_to_remediate",
        "incorrect_streak_to_pause",
        "remediation_strategy",
        "summary_when_mastery_reached",
        "allowed_next_actions",
        "failure_behavior",
        "retry_policy",
        "generation_model",
        "scoring_model",
    }
)


def requires_manage_prompts(field: str) -> bool:
    return field in AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS


def changed_ai_coach_high_risk_fields(
    current_path: object,
    incoming_payload: NewcomerPathConfigSaveRequest,
) -> set[str]:
    current = (
        NewcomerPathConfigPayload.model_validate(current_path)
        if current_path is not None
        else NewcomerPathConfigPayload()
    )
    current_ai_coach_by_key = {
        module.module_key: (
            module.ai_coach.model_dump(mode="json") if module.ai_coach else {}
        )
        for module in current.modules
    }
    incoming_keys = {module.module_key for module in incoming_payload.modules}
    changed: set[str] = set()
    for module_key, previous in current_ai_coach_by_key.items():
        if previous and module_key not in incoming_keys:
            changed.update(AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS)
    for incoming_module in incoming_payload.modules:
        previous = current_ai_coach_by_key.get(incoming_module.module_key, {})
        if incoming_module.ai_coach is None:
            if previous:
                changed.update(AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS)
            continue
        ai_coach = incoming_module.ai_coach.model_dump(mode="json")
        changed.update(
            field
            for field in AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS
            if field in ai_coach and ai_coach.get(field) != previous.get(field)
        )
    return changed


def save_request_from_path_payload(
    path_payload: NewcomerPathConfigPayload,
    *,
    reason: str,
) -> NewcomerPathConfigSaveRequest:
    return NewcomerPathConfigSaveRequest(
        **path_payload.model_dump(mode="json"),
        reason=reason,
    )


async def changed_ai_coach_high_risk_fields_for_publish(
    db: AsyncSession,
) -> set[str]:
    revisions = SalesTrainerAssetRevisionService(db)
    active = await revisions.active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    working = await revisions.latest_working_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    if working is None:
        if active is None:
            return set()
        target_payload = NewcomerPathConfigPayload()
    else:
        target_payload = payload_from_revision(working)
    current_path = payload_from_revision(active) if active is not None else None
    return changed_ai_coach_high_risk_fields(
        current_path,
        save_request_from_path_payload(target_payload, reason="publish"),
    )


async def changed_ai_coach_high_risk_fields_for_rollback(
    db: AsyncSession,
    revision_id: str,
) -> set[str]:
    revisions = SalesTrainerAssetRevisionService(db)
    active = await revisions.active_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
    )
    target = await get_path_revision(revisions, revision_id)
    current_path = payload_from_revision(active) if active is not None else None
    return changed_ai_coach_high_risk_fields(
        current_path,
        save_request_from_path_payload(
            payload_from_revision(target),
            reason="rollback",
        ),
    )

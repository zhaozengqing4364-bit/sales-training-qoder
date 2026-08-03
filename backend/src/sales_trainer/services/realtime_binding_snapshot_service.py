"""Freeze and verify realtime-roleplay bindings owned by a path revision."""

from __future__ import annotations

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.orchestration.contracts import (
    ActivityConfig,
    RealtimeRoleplayConfig,
    RealtimeRunnerDescriptor,
    RealtimeScoringFocus,
    TrainingPathPayload,
)
from sales_trainer.orchestration.graph import PathIssue
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.curriculum_practice_adapter import (
    RealtimeBindingAssetSnapshot,
    get_realtime_binding_asset_snapshot,
    practice_template_resource_type,
)

_CONFIGURATION_MESSAGE = "对练配置尚未准备完整，请联系培训管理员。"


async def freeze_realtime_bindings(
    db: AsyncSession,
    payload: TrainingPathPayload,
    *,
    refresh_existing: bool = True,
) -> TrainingPathPayload:
    phases = []
    for phase in payload.phases:
        modules = []
        for module in phase.modules:
            activities: list[ActivityConfig] = []
            for activity in module.activities:
                if activity.type != "realtime_roleplay":
                    activities.append(activity)
                    continue
                config = cast(RealtimeRoleplayConfig, activity.config)
                if config.runner_snapshot is not None and not refresh_existing:
                    activities.append(activity)
                    continue
                activities.append(
                    activity.model_copy(
                        update={"config": await _frozen_config(db, config)}
                    )
                )
            modules.append(module.model_copy(update={"activities": activities}))
        phases.append(phase.model_copy(update={"modules": modules}))
    return payload.model_copy(update={"phases": phases})


async def validate_realtime_binding_snapshots(
    db: AsyncSession,
    payload: TrainingPathPayload,
) -> tuple[PathIssue, ...]:
    issues: list[PathIssue] = []
    for phase_index, phase in enumerate(payload.phases):
        for module_index, module in enumerate(phase.modules):
            for activity_index, activity in enumerate(module.activities):
                if activity.type != "realtime_roleplay":
                    continue
                config = cast(RealtimeRoleplayConfig, activity.config)
                if (
                    not config.practice_template_id.strip()
                    or not config.runtime_profile_id.strip()
                ):
                    continue
                if config.runner_snapshot is None:
                    message = "请重新保存路径草稿，以冻结本次实时对练的发布配置。"
                elif await realtime_binding_matches_snapshot(db, config):
                    continue
                else:
                    message = "实时对练发布配置已变化，请重新保存路径草稿后再发布。"
                issues.append(
                    PathIssue(
                        code="realtime_binding_snapshot_stale",
                        message=f"{activity.title}：{message}",
                        object_id=activity.activity_id,
                        field_path=(
                            f"phases[{phase_index}].modules[{module_index}]"
                            f".activities[{activity_index}].config.runner_snapshot"
                        ),
                    )
                )
    return tuple(issues)


async def realtime_runner_descriptor(
    db: AsyncSession,
    config: RealtimeRoleplayConfig,
) -> RealtimeRunnerDescriptor:
    if config.runner_snapshot is None:
        return await _current_descriptor(db, config)
    ready = await realtime_binding_matches_snapshot(db, config)
    try:
        return RealtimeRunnerDescriptor.model_validate(
            {
                **config.runner_snapshot,
                "type": "realtime_roleplay",
                "configuration_ready": ready,
                "configuration_message": None if ready else _CONFIGURATION_MESSAGE,
            }
        )
    except ValueError:
        return RealtimeRunnerDescriptor(
            configuration_ready=False,
            configuration_message=_CONFIGURATION_MESSAGE,
        )


async def realtime_binding_matches_snapshot(
    db: AsyncSession,
    config: RealtimeRoleplayConfig,
) -> bool:
    if not all(
        (
            config.runner_snapshot is not None,
            config.practice_template_version is not None,
            config.practice_template_content_hash,
            config.runtime_profile_snapshot_hash,
            config.governed_assets_snapshot_hash,
        )
    ):
        return False
    assets = await get_realtime_binding_asset_snapshot(
        db,
        config.practice_template_id,
    )
    if assets is None:
        return False
    return all(
        (
            assets.template_status == "published",
            assets.template_version == config.practice_template_version,
            assets.template_content_hash == config.practice_template_content_hash,
            assets.template_runtime_profile_id == config.runtime_profile_id,
            assets.runtime_is_active,
            assets.runtime_voice_mode == "stepfun_realtime",
            assets.runtime_reference_hash == config.runtime_profile_snapshot_hash,
            assets.governed_assets_hash == config.governed_assets_snapshot_hash,
        )
    )


def realtime_binding_audit_snapshot(
    config: RealtimeRoleplayConfig,
) -> dict[str, object]:
    return {
        "practice_template_revision_id": config.practice_template_revision_id,
        "practice_template_version": config.practice_template_version,
        "practice_template_content_hash": config.practice_template_content_hash,
        "runtime_profile_snapshot_hash": config.runtime_profile_snapshot_hash,
        "governed_assets_snapshot_hash": config.governed_assets_snapshot_hash,
    }


async def _frozen_config(
    db: AsyncSession,
    config: RealtimeRoleplayConfig,
) -> RealtimeRoleplayConfig:
    if not config.practice_template_id.strip() or not config.runtime_profile_id.strip():
        return config.model_copy(
            update={
                "practice_template_revision_id": None,
                "practice_template_version": None,
                "practice_template_content_hash": None,
                "runtime_profile_snapshot_hash": None,
                "governed_assets_snapshot_hash": None,
                "runner_snapshot": None,
            }
        )
    assets = await _assets(db, config.practice_template_id)
    if assets is None:
        return config.model_copy(
            update={
                "practice_template_revision_id": None,
                "practice_template_version": None,
                "practice_template_content_hash": None,
                "runtime_profile_snapshot_hash": None,
                "governed_assets_snapshot_hash": None,
                "runner_snapshot": None,
            }
        )
    descriptor = _descriptor_from_assets(config, assets)
    if not descriptor.configuration_ready:
        return config.model_copy(update={"runner_snapshot": None})
    revision = await SalesTrainerAssetRevisionService(db).active_revision(
        resource_type=practice_template_resource_type(),
        logical_id=config.practice_template_id,
    )
    runner_snapshot = descriptor.model_dump(
        mode="json",
        exclude={"type", "configuration_ready", "configuration_message"},
    )
    return config.model_copy(
        update={
            "practice_template_revision_id": (
                str(revision.revision_id) if revision is not None else None
            ),
            "practice_template_version": assets.template_version,
            "practice_template_content_hash": assets.template_content_hash,
            "runtime_profile_snapshot_hash": assets.runtime_reference_hash,
            "governed_assets_snapshot_hash": assets.governed_assets_hash,
            "runner_snapshot": runner_snapshot,
        }
    )


async def _current_descriptor(
    db: AsyncSession,
    config: RealtimeRoleplayConfig,
) -> RealtimeRunnerDescriptor:
    assets = await _assets(db, config.practice_template_id)
    if assets is None:
        return RealtimeRunnerDescriptor(
            configuration_ready=False,
            configuration_message=_CONFIGURATION_MESSAGE,
        )
    return _descriptor_from_assets(config, assets)


async def _assets(
    db: AsyncSession,
    template_id: str,
) -> RealtimeBindingAssetSnapshot | None:
    return await get_realtime_binding_asset_snapshot(db, template_id)


def _descriptor_from_assets(
    config: RealtimeRoleplayConfig,
    assets: RealtimeBindingAssetSnapshot,
) -> RealtimeRunnerDescriptor:
    ready = all(
        (
            assets.template_status == "published",
            assets.case_status == "published",
            assets.role_status == "published",
            assets.ruleset_status == "published",
            assets.runtime_is_active,
            assets.template_runtime_profile_id == config.runtime_profile_id,
        )
    )
    definition = assets.ruleset_definition
    scenario = _optional_text(assets.template_description, 500)
    if scenario is None:
        scenario = _optional_text(assets.case_company_profile, 500)
    return RealtimeRunnerDescriptor(
        configuration_ready=ready,
        configuration_message=None if ready else _CONFIGURATION_MESSAGE,
        template_title=_optional_text(assets.template_name, 200),
        template_description=_optional_text(assets.template_description, 500),
        template_version=(
            assets.template_version if assets.template_status == "published" else None
        ),
        scenario=scenario,
        counterpart_role=(
            _optional_text(assets.role_name, 160)
            if assets.role_status == "published"
            else None
        ),
        counterpart_style=(
            _optional_text(assets.role_communication_style, 500)
            if assets.role_status == "published"
            else None
        ),
        goals=(
            _text_list(list(assets.case_success_criteria), 8, 200)
            if assets.case_status == "published"
            else []
        ),
        scoring_title=(
            _optional_text(assets.ruleset_display_name, 160)
            if assets.ruleset_status == "published"
            else None
        ),
        scoring_description=(
            _optional_text(assets.ruleset_description, 500)
            if assets.ruleset_status == "published"
            else None
        ),
        scoring_version=(
            _optional_text(assets.ruleset_version, 80)
            if assets.ruleset_status == "published"
            else None
        ),
        scoring_focuses=_scoring_focuses(definition.get("dimensions")),
        passing_score=_score(definition.get("passing_score")),
    )


def _optional_text(value: object, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()[:max_length] or None


def _text_list(value: object, max_items: int, max_length: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for value_item in value[:max_items]:
        text = _optional_text(value_item, max_length)
        if text:
            result.append(text)
    return result


def _score(value: object) -> float | None:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 100
    ):
        return float(value)
    return None


def _scoring_focuses(value: object) -> list[RealtimeScoringFocus]:
    if not isinstance(value, list):
        return []
    result: list[RealtimeScoringFocus] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        label = _optional_text(item.get("label"), 120)
        if label is None:
            continue
        weight = item.get("weight")
        result.append(
            RealtimeScoringFocus(
                label=label,
                description=_optional_text(item.get("description"), 500),
                weight=(
                    float(weight)
                    if isinstance(weight, (int, float))
                    and not isinstance(weight, bool)
                    and 0 <= weight <= 100
                    else None
                ),
            )
        )
    return result


__all__ = [
    "freeze_realtime_bindings",
    "realtime_binding_audit_snapshot",
    "realtime_binding_matches_snapshot",
    "realtime_runner_descriptor",
    "validate_realtime_binding_snapshots",
]

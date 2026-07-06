from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerUnit
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    LEGACY_NEWCOMER_PATH_KEYS,
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    PathBackfillUnit,
    SalesTrainerPathConfigError,
    canonical_path_module_key,
    path_config,
)


async def get_path_revision(
    revisions: SalesTrainerAssetRevisionService,
    revision_id: str,
) -> SalesTrainerAssetRevision:
    revision = await revisions.revision_by_id(revision_id)
    if revision is None:
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_PATH_REVISION_NOT_FOUND]",
            "新人训练路径历史版本不存在。",
            404,
        )
    if (
        str(revision.resource_type) != NEWCOMER_PATH_RESOURCE_TYPE
        or str(revision.logical_id) != NEWCOMER_PATH_LOGICAL_ID
    ):
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_PATH_REVISION_MISMATCH]",
            "该历史版本不属于新人训练路径配置。",
            409,
        )
    return revision


async def record_path_config_event(
    logs: OperationLogService,
    *,
    actor: User,
    action: str,
    after_revision_id: str,
    before_revision_id: str | None,
    reason: str | None,
    trace_id: str | None,
    change_class: str,
) -> None:
    await logs.record(
        actor=actor,
        action=action,
        target_type="newcomer_path_config",
        target_id=NEWCOMER_PATH_LOGICAL_ID,
        request_id=trace_id,
        metadata={
            "before_revision_id": before_revision_id,
            "after_revision_id": after_revision_id,
            "reason": reason,
            "trace_id": trace_id,
            "change_class": change_class,
            "impact_scope": "future_learners_only",
        },
    )


async def load_published_path_units(db: AsyncSession) -> list[PathBackfillUnit]:
    result = await db.execute(
        select(SalesTrainerUnit)
        .where(SalesTrainerUnit.status == "published")
        .order_by(SalesTrainerUnit.updated_at.desc())
    )
    selected: dict[str, PathBackfillUnit] = {}
    allowed_path_keys = {NEWCOMER_PATH_LOGICAL_ID, *LEGACY_NEWCOMER_PATH_KEYS}
    for unit in result.scalars().all():
        raw_config = unit.config
        config = path_config(raw_config) if isinstance(raw_config, dict) else None
        if config is None or config.path_key not in allowed_path_keys:
            continue
        key_and_priority = canonical_path_module_key(unit, config)
        if key_and_priority is None:
            continue
        module_key, priority = key_and_priority
        current = selected.get(module_key)
        if current is None or priority < current.selection_priority:
            selected[module_key] = PathBackfillUnit(
                unit=unit,
                path_config=config,
                module_key=module_key,
                selection_priority=priority,
            )
    return list(selected.values())


async def units_by_id(
    db: AsyncSession,
    unit_ids: list[str],
) -> dict[str, SalesTrainerUnit]:
    if not unit_ids:
        return {}
    result = await db.execute(
        select(SalesTrainerUnit).where(SalesTrainerUnit.unit_id.in_(unit_ids))
    )
    return {str(unit.unit_id): unit for unit in result.scalars().all()}

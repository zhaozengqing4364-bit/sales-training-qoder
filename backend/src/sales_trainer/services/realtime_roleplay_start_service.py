from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY
from common.business_rules.service import (
    BusinessRuleConfigService,
    BusinessRuleResolution,
)
from common.db.models import User
from common.db.schemas import ScenarioType, SessionCreate
from common.services.external_session_start import (
    ExternalSessionStartError,
    ExternalSessionStartService,
)
from sales_trainer.schemas import (
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
    NewcomerRealtimeRuntimeBinding,
)
from sales_trainer.services.learner_unit_access import (
    LearnerUnitAccessError,
    require_learner_active_path_module_access,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


class RealtimeRoleplayStartError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class RealtimeRoleplayStartService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        session_start_service: ExternalSessionStartService | None = None,
    ) -> None:
        self._db = db
        self._session_start = session_start_service
        self._logs = OperationLogService(db)

    async def start(
        self,
        *,
        actor: User,
        module_key: str = "realtime_roleplay",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        path_config = await SalesTrainerPathConfigService(self._db).get_config()
        if path_config.get("source") != "active_revision":
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径尚未发布 active revision，无法开始实时对练。",
                409,
        )
        path = NewcomerPathConfigPayload.model_validate(path_config["path"])
        module = _find_realtime_module(path, module_key)
        binding = _validated_runtime_binding(module)
        try:
            await require_learner_active_path_module_access(
                self._db,
                actor=actor,
                module_key=module.module_key,
            )
        except LearnerUnitAccessError as exc:
            raise RealtimeRoleplayStartError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        runtime_registry = await self._validated_runtime_registry(
            binding.runtime_descriptor_id
        )
        practice_template_id = _practice_template_uuid(binding.practice_template_id)
        external_binding = _external_binding_payload(
            path=path,
            module=module,
            binding=binding.model_dump(mode="json"),
            runtime_registry=runtime_registry,
            path_revision_id=str(path_config["active_revision_id"]),
            path_revision_no=int(path_config["active_revision_no"]),
            actor=actor,
        )
        try:
            session_start = self._session_start or ExternalSessionStartService(self._db)
            result = await session_start.start(
                SessionCreate(
                    scenario_type=ScenarioType.SALES,
                    voice_mode="stepfun_realtime",
                    practice_template_id=practice_template_id,
                ),
                current_user=actor,
                external_binding=external_binding,
            )
        except ExternalSessionStartError as exc:
            raise RealtimeRoleplayStartError(
                exc.error_code,
                exc.message or exc.error_code,
                exc.status_code,
                exc.details,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="newcomer_module.realtime_roleplay.session_started",
            target_type="sales_trainer_realtime_roleplay_session",
            target_id=result.session_id,
            request_id=trace_id,
            metadata={
                "path_key": path.path_key,
                "path_revision_id": path_config["active_revision_id"],
                "path_revision_no": path_config["active_revision_no"],
                "module_key": module.module_key,
                "binding_key": binding.binding_key,
                "runtime_descriptor_id": binding.runtime_descriptor_id,
                "runtime_config_revision_id": binding.runtime_config_revision_id,
                "runtime_registry_config_id": runtime_registry["config_id"],
                "runtime_registry_version": runtime_registry["version"],
            },
        )
        await self._db.commit()
        return {
            "session_id": result.session_id,
            "module_key": module.module_key,
            "path_key": path.path_key,
            "path_revision_id": str(path_config["active_revision_id"]),
            "path_revision_no": int(path_config["active_revision_no"]),
            "practice_url": "/" + "practice" + f"/{result.session_id}",
            "runtime_descriptor_id": binding.runtime_descriptor_id,
            "runtime_registry": deepcopy(runtime_registry),
            "provider_readiness_snapshot": binding.provider_readiness_snapshot.model_dump(
                mode="json"
            ),
            "external_binding": deepcopy(external_binding),
        }

    async def _validated_runtime_registry(
        self,
        runtime_descriptor_id: str,
    ) -> dict[str, Any]:
        resolution = await BusinessRuleConfigService(self._db).resolve_active_config(
            SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY
        )
        registry = resolution.value
        if registry.get("enabled") is not True:
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_PROVIDER_REGISTRY_DISABLED]",
                "实时对练 provider registry 未启用，无法开始实时对练。",
                503,
                details=_registry_details(resolution),
            )

        descriptor = next(
            (
                item
                for item in registry.get("descriptors", [])
                if isinstance(item, dict)
                and item.get("descriptor_id") == runtime_descriptor_id
            ),
            None,
        )
        if descriptor is None:
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_PROVIDER_DESCRIPTOR_MISSING]",
                "实时对练 provider registry 缺少当前 runtime descriptor。",
                503,
                details=_registry_details(resolution)
                | {"runtime_descriptor_id": runtime_descriptor_id},
            )
        if descriptor.get("enabled") is not True:
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_PROVIDER_DISABLED]",
                "实时对练 provider 已被停用，无法开始实时对练。",
                503,
                details=_registry_details(resolution) | {"descriptor": descriptor},
            )
        readiness = descriptor.get("readiness")
        if not isinstance(readiness, dict) or readiness.get("ready") is not True:
            reason = ""
            if isinstance(readiness, dict):
                reason = readiness.get("failure_message") or readiness.get("failure_code") or ""
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
                f"实时对练 provider registry readiness 未通过：{reason or 'provider 未就绪'}。",
                503,
                details=_registry_details(resolution) | {"descriptor": descriptor},
            )
        return _registry_details(resolution) | {"descriptor": deepcopy(descriptor)}


def _find_realtime_module(
    path: NewcomerPathConfigPayload,
    module_key: str,
) -> NewcomerPathModuleConfig:
    for module in path.modules:
        if module.module_key == module_key and module.module_type == "realtime_roleplay":
            return module
    raise RealtimeRoleplayStartError(
        "[NEWCOMER_REALTIME_MODULE_NOT_FOUND]",
        "active path 中不存在可启动的实时对练模块。",
        404,
    )


def _validated_runtime_binding(
    module: NewcomerPathModuleConfig,
) -> NewcomerRealtimeRuntimeBinding:
    if not module.enabled:
        raise RealtimeRoleplayStartError(
            "[NEWCOMER_REALTIME_MODULE_DISABLED]",
            "实时对练模块当前未启用。",
            409,
        )
    binding = module.runtime_binding
    if binding is None:
        raise RealtimeRoleplayStartError(
            "[NEWCOMER_REALTIME_BINDING_INVALID]",
            "实时对练模块缺少 runtime binding。",
            409,
        )
    readiness = binding.provider_readiness_snapshot
    if not readiness.ready:
        reason = readiness.failure_message or readiness.failure_code or "provider 未就绪"
        raise RealtimeRoleplayStartError(
            "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
            f"实时对练 provider readiness 未通过：{reason}。",
            503,
            details=readiness.model_dump(mode="json"),
        )
    if not binding.practice_template_id:
        raise RealtimeRoleplayStartError(
            "[NEWCOMER_REALTIME_BINDING_INVALID]",
            "实时对练 runtime binding 必须配置 practice_template_id。",
            409,
        )
    return binding


def _practice_template_uuid(value: str | None) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise RealtimeRoleplayStartError(
            "[NEWCOMER_REALTIME_BINDING_INVALID]",
            "实时对练 practice_template_id 不是合法 UUID。",
            422,
        ) from exc


def _external_binding_payload(
    *,
    path: NewcomerPathConfigPayload,
    module: NewcomerPathModuleConfig,
    binding: dict[str, Any],
    runtime_registry: dict[str, Any],
    path_revision_id: str,
    path_revision_no: int,
    actor: User,
) -> dict[str, Any]:
    return {
        "owner": "sales_trainer",
        "path_key": path.path_key,
        "path_revision_id": path_revision_id,
        "path_revision_no": path_revision_no,
        "module_key": module.module_key,
        "binding_key": binding["binding_key"],
        "runtime_descriptor_id": binding["runtime_descriptor_id"],
        "scenario_key": binding["scenario_key"],
        "runtime_config_revision_id": binding["runtime_config_revision_id"],
        "runtime_registry": deepcopy(runtime_registry),
        "roleplay_contract_revision_id": binding.get("roleplay_contract_revision_id"),
        "practice_template_id": binding.get("practice_template_id"),
        "provider_readiness_snapshot": deepcopy(
            binding.get("provider_readiness_snapshot") or {}
        ),
        "failure_policy": deepcopy(binding.get("failure_policy") or {}),
        "started_by_user_id": str(actor.user_id),
        "started_at": datetime.now(UTC).isoformat(),
    }


def _registry_details(resolution: BusinessRuleResolution) -> dict[str, Any]:
    return {
        "registry_key": SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        "config_id": resolution.config_id,
        "version": resolution.version,
        "source": resolution.source,
        "status": resolution.status,
        "fallback_reason": resolution.fallback_reason,
    }

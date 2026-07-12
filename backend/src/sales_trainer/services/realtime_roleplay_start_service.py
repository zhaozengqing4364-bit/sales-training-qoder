"""Start StepAudio sessions from a pinned activity identity."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import VoiceRuntimeProfile
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
from curriculum_practice.models import PracticeTemplate
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    activity_snapshot,
)
from sales_trainer.orchestration.contracts import RealtimeRoleplayConfig
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.services.operation_log_service import OperationLogService


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
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._db = db
        self._session_start = session_start_service
        self._attempts = attempts or AttemptRepository(db)
        self._logs = OperationLogService(db)

    async def start(
        self,
        *,
        actor: User,
        execution_context: ActivityExecutionContext,
        client_token: str,
        trace_id: str | None = None,
    ) -> dict[str, object]:
        if execution_context.activity.type != "realtime_roleplay":
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_ACTIVITY_TYPE_MISMATCH]", "当前任务不是实时对练。", 422
            )
        if execution_context.learner_id != str(actor.user_id):
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]",
                "不能替其他学员开始实时对练。",
                403,
            )
        config = execution_context.activity.config
        assert isinstance(config, RealtimeRoleplayConfig)
        template = await self._db.get(PracticeTemplate, config.practice_template_id)
        if template is None or str(template.status) != "published":
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_TEMPLATE_NOT_PUBLISHED]",
                "实时对练模板尚未发布。",
                409,
            )
        runtime = await self._db.get(VoiceRuntimeProfile, config.runtime_profile_id)
        if (
            runtime is None
            or runtime.is_active is not True
            or str(runtime.voice_mode) != "stepfun_realtime"
        ):
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_RUNTIME_NOT_READY]",
                "实时语音运行配置尚未启用。",
                503,
            )
        if str(template.runtime_profile_id) != config.runtime_profile_id:
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_BINDING_MISMATCH]",
                "对练模板与语音运行配置不匹配。",
                409,
            )
        registry = await self._validated_runtime_registry(config.runtime_profile_id)
        attempt = await self._attempts.create(
            enrollment_id=execution_context.enrollment_id,
            path_revision_id=execution_context.path_revision_id,
            activity_id=execution_context.activity.activity_id,
            activity_type="realtime_roleplay",
            activity_snapshot=activity_snapshot(execution_context),
            client_token=client_token,
        )
        binding = {
            "owner": "newcomer_training",
            "enrollment_id": execution_context.enrollment_id,
            "path_revision_id": execution_context.path_revision_id,
            "phase_id": execution_context.phase_id,
            "module_id": execution_context.module_id,
            "activity_id": execution_context.activity.activity_id,
            "attempt_id": str(attempt.attempt_id),
            "practice_template_id": config.practice_template_id,
            "runtime_profile_id": config.runtime_profile_id,
            "runtime_registry": deepcopy(registry),
            "started_by_user_id": str(actor.user_id),
            "started_at": datetime.now(UTC).isoformat(),
        }
        try:
            starter = self._session_start or ExternalSessionStartService(self._db)
            result = await starter.start(
                SessionCreate(
                    scenario_type=ScenarioType.SALES,
                    voice_mode="stepfun_realtime",
                    practice_template_id=_uuid(config.practice_template_id),
                ),
                current_user=actor,
                external_binding=binding,
            )
        except ExternalSessionStartError as exc:
            raise RealtimeRoleplayStartError(
                exc.error_code,
                exc.message or exc.error_code,
                exc.status_code,
                exc.details,
            ) from exc
        await self._attempts.attach_evidence(
            attempt_id=str(attempt.attempt_id),
            evidence_type="practice_session",
            evidence_id=result.session_id,
            status="in_progress",
        )
        await self._logs.record(
            actor=actor,
            action="newcomer_activity.realtime_roleplay.session_started",
            target_type="practice_session",
            target_id=result.session_id,
            request_id=trace_id,
            metadata={
                key: binding[key]
                for key in (
                    "enrollment_id",
                    "path_revision_id",
                    "phase_id",
                    "module_id",
                    "activity_id",
                    "attempt_id",
                )
            },
        )
        await self._db.commit()
        return {
            "session_id": result.session_id,
            "evidence_id": result.session_id,
            "attempt_id": str(attempt.attempt_id),
            "external_binding": deepcopy(binding),
        }

    async def _validated_runtime_registry(
        self, runtime_profile_id: str
    ) -> dict[str, Any]:
        resolution = await BusinessRuleConfigService(self._db).resolve_active_config(
            SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY
        )
        value = resolution.value
        descriptor = next(
            (
                item
                for item in value.get("descriptors", [])
                if isinstance(item, dict)
                and item.get("runtime_profile_id") == runtime_profile_id
            ),
            None,
        )
        if (
            value.get("enabled") is not True
            or descriptor is None
            or descriptor.get("enabled") is not True
        ):
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_PROVIDER_DISABLED]",
                "实时对练服务尚未启用。",
                503,
                _registry_details(resolution),
            )
        readiness = descriptor.get("readiness")
        if not isinstance(readiness, dict) or readiness.get("ready") is not True:
            raise RealtimeRoleplayStartError(
                "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
                "实时对练服务尚未就绪。",
                503,
                _registry_details(resolution),
            )
        return _registry_details(resolution) | {"descriptor": deepcopy(descriptor)}


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise RealtimeRoleplayStartError(
            "[NEWCOMER_REALTIME_TEMPLATE_ID_INVALID]", "实时对练模板标识无效。", 422
        ) from exc


def _registry_details(resolution: BusinessRuleResolution) -> dict[str, Any]:
    return {
        "registry_key": SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
        "config_id": resolution.config_id,
        "version": resolution.version,
        "source": resolution.source,
        "status": resolution.status,
    }


__all__ = ["RealtimeRoleplayStartError", "RealtimeRoleplayStartService"]

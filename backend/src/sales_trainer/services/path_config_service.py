from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from prompt_templates.service import PromptTemplateService
from sales_trainer.ai_coach_policy import (
    changed_ai_coach_high_risk_fields,
    save_request_from_path_payload,
)
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    NewcomerPathConfigPayload,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.asset_revision_service import (
    AssetPublishResult,
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.curriculum_practice_adapter import get_learning_content
from sales_trainer.services.effective_audio_training_config import (
    merge_audio_path_config,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    PathProjection,
    PathUnitProjection,
    SalesTrainerPathConfigError,
    classify_change,
    module_from_unit,
    path_config,
    path_config_from_module,
    payload_from_revision,
    revision_summary,
    validate_path_payload_for_write,
)
from sales_trainer.services.path_config_operations import (
    get_path_revision,
    load_published_path_units,
    record_path_config_event,
    units_by_id,
)
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_AUDIT_HISTORY_UNAVAILABLE,
    RESULT_HEAD_USED_AS_FALLBACK,
    RESULT_OK,
    RESULT_REVISION_NOT_FOUND,
    PromptTemplateRevisionResolver,
    PromptTemplateRevisionResolverError,
)

AI_COACH_PROMPT_CATEGORY = "sales_trainer_ai_coach"


class SalesTrainerPathConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._logs = OperationLogService(db)

    async def get_config(self) -> dict[str, Any]:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        source: Literal["active_revision", "legacy_migration_snapshot"] = (
            "active_revision"
        )
        if active is None:
            path = await self._backfill_payload()
            source = "legacy_migration_snapshot"
        else:
            path = payload_from_revision(active)
        legacy_snapshot_only = active is None
        return {
            "source": source,
            "fallback_reason": "active_revision_missing" if active is None else None,
            "legacy_snapshot_only": legacy_snapshot_only,
            "management_entry": "/admin/newcomer-training/path-config",
            "permission": "sales_trainer.manage_modules",
            "path": path.model_dump(mode="json"),
            "active_revision_id": str(active.revision_id) if active else None,
            "active_revision_no": active.revision_no if active else None,
            "active_revision_snapshot": self._revisions.snapshot(active),
            "working_revision_id": str(working.revision_id) if working else None,
            "working_revision_no": working.revision_no if working else None,
            "has_unpublished_revision": working is not None,
            "diagnostics": self._diagnostics(
                source=source,
                legacy_snapshot_only=legacy_snapshot_only,
                fallback_reason="active_revision_missing" if active is None else None,
                active=active,
                working=working,
                path_payload=path,
            ),
        }

    async def active_projection(self) -> PathProjection | None:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if active is None:
            return None
        payload = payload_from_revision(active)
        if not payload.enabled:
            return PathProjection(
                source="active_revision",
                path_key=payload.path_key,
                revision_id=str(active.revision_id),
                revision_no=int(active.revision_no),
                items=(),
            )
        items = await self._projection_items(payload)
        return PathProjection(
            source="active_revision",
            path_key=payload.path_key,
            revision_id=str(active.revision_id),
            revision_no=int(active.revision_no),
            items=tuple(items),
        )

    async def save_config(
        self,
        payload: NewcomerPathConfigSaveRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        try:
            path_payload = NewcomerPathConfigPayload.model_validate(
                payload.model_dump(mode="json", exclude={"reason"})
            )
        except ValidationError as exc:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                "新人训练路径配置格式错误。",
                422,
            ) from exc
        validate_path_payload_for_write(path_payload)
        await self._validate_ai_coach_prompt_bindings(path_payload)
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        change_class = classify_change(active, path_payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                logical_id=NEWCOMER_PATH_LOGICAL_ID,
                payload=path_payload.model_dump(mode="json"),
                actor=actor,
                change_class=change_class,
                source_revision_id=str(active.revision_id) if active else None,
                reason=payload.reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerPathConfigError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await record_path_config_event(
            self._logs,
            actor=actor,
            action="newcomer_path_config.save_working",
            after_revision_id=str(revision.revision_id),
            before_revision_id=str(active.revision_id) if active else None,
            reason=payload.reason,
            trace_id=trace_id,
            change_class=change_class,
        )
        await self._db.commit()
        return revision

    async def publish_config(
        self,
        *,
        actor: User,
        reason: str,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        _, working, _ = await self._prepare_publish_target()
        try:
            result = await self._revisions.publish_working_revision(
                working,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerPathConfigError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await record_path_config_event(
            self._logs,
            actor=actor,
            action="newcomer_path_config.publish",
            after_revision_id=str(result.revision.revision_id),
            before_revision_id=result.previous_revision_id,
            reason=reason,
            trace_id=trace_id,
            change_class=str(result.revision.change_class),
        )
        await self._db.commit()
        return result

    async def publish_preview(self) -> dict[str, Any]:
        active, working, publish_payload = await self._prepare_publish_target()
        active_payload = payload_from_revision(active) if active is not None else None
        active_revision_id = str(active.revision_id) if active else None
        working_revision_id = str(working.revision_id)
        will_change_active_revision = active_revision_id != working_revision_id
        changed_module_keys = self._changed_module_keys(active_payload, publish_payload)
        affected_module_keys = self._affected_module_keys(active_payload, publish_payload)
        path_fields_changed = self._path_fields_changed(active_payload, publish_payload)
        high_risk_fields = sorted(
            changed_ai_coach_high_risk_fields(
                active_payload.model_dump(mode="json") if active_payload else None,
                save_request_from_path_payload(publish_payload, reason="publish_preview"),
            )
        )
        risk_level, risk_reasons = self._publish_preview_risk(
            active=active,
            working=working,
            changed_module_keys=changed_module_keys,
            path_fields_changed=path_fields_changed,
            high_risk_fields=high_risk_fields,
        )
        rollback_available = active is not None and will_change_active_revision
        return {
            "action": "newcomer_path_config.publish",
            "permission": "sales_trainer.manage_modules",
            "requires_reason": True,
            "requires_trace_id": True,
            "future_only": True,
            "risk_level": risk_level,
            "risk_reasons": risk_reasons,
            "change_class": str(working.change_class),
            "target_revision_id": working_revision_id,
            "target_revision_no": working.revision_no,
            "target_revision_status": working.status,
            "impact_scope": {
                "active_revision_id": active_revision_id,
                "working_revision_id": working_revision_id,
                "will_change_active_revision": will_change_active_revision,
                "future_learner_paths_changed": will_change_active_revision,
                "historical_attempts_changed": False,
                "historical_submissions_changed": False,
                "historical_regrade_required": False,
                "affected_module_keys": affected_module_keys,
                "changed_module_keys": changed_module_keys,
                "path_fields_changed": path_fields_changed,
                "changed_ai_coach_high_risk_fields": high_risk_fields,
                "realtime_provider_readiness": self._realtime_provider_readiness(
                    publish_payload
                ),
                "rollback_available": rollback_available,
            },
            "before_snapshot": self._revisions.snapshot(active),
            "after_snapshot": self._revisions.snapshot(working),
            "audit_event": {
                "action": "newcomer_path_config.publish",
                "target_type": "newcomer_path_config",
                "target_id": NEWCOMER_PATH_LOGICAL_ID,
                "required_fields": [
                    "actor_id",
                    "reason",
                    "trace_id",
                    "before_revision_id",
                    "after_revision_id",
                    "impact_scope",
                ],
            },
            "rollback_hint": {
                "available": rollback_available,
                "preview_endpoint": (
                    "/api/v1/admin/newcomer-training/path-config/rollback/preview"
                    if rollback_available
                    else None
                ),
                "target_revision_id": active_revision_id,
                "target_revision_no": active.revision_no if active else None,
                "message": (
                    "发布后可先对当前 active revision 执行回滚预览，再决定是否回滚。"
                    if rollback_available
                    else "当前没有可作为上一版的已发布 active revision，首次发布后暂无直接回滚目标。"
                ),
            },
        }

    async def rollback_config(
        self,
        *,
        revision_id: str,
        actor: User,
        reason: str,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        revision = await get_path_revision(self._revisions, revision_id)
        try:
            result = await self._revisions.rollback_to_revision(
                revision,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
                expected_resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                expected_logical_id=NEWCOMER_PATH_LOGICAL_ID,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerPathConfigError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await record_path_config_event(
            self._logs,
            actor=actor,
            action="newcomer_path_config.rollback",
            after_revision_id=str(result.revision.revision_id),
            before_revision_id=result.previous_revision_id,
            reason=reason,
            trace_id=trace_id,
            change_class=str(result.revision.change_class),
        )
        await self._db.commit()
        return result

    async def rollback_preview(self, revision_id: str) -> dict[str, Any]:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        revision = await get_path_revision(self._revisions, revision_id)
        if revision.status != "published":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_REVISION_NOT_ROLLBACKABLE]",
                "只能预览回滚到已发布的新人训练路径修订。",
                409,
            )
        active_revision_id = str(active.revision_id) if active else None
        target_revision_id = str(revision.revision_id)
        return {
            "action": "newcomer_path_config.rollback",
            "permission": "sales_trainer.manage_modules",
            "requires_reason": True,
            "requires_trace_id": True,
            "future_only": True,
            "target_revision_id": target_revision_id,
            "target_revision_no": revision.revision_no,
            "target_revision_status": revision.status,
            "impact_scope": {
                "active_revision_id": active_revision_id,
                "target_revision_id": target_revision_id,
                "will_change_active_revision": active_revision_id != target_revision_id,
                "future_learner_paths_changed": active_revision_id != target_revision_id,
                "historical_attempts_changed": False,
                "historical_submissions_changed": False,
                "historical_regrade_required": False,
            },
            "before_snapshot": self._revisions.snapshot(active),
            "after_snapshot": self._revisions.snapshot(revision),
            "audit_event": {
                "action": "newcomer_path_config.rollback",
                "target_type": "newcomer_path_config",
                "target_id": NEWCOMER_PATH_LOGICAL_ID,
                "required_fields": [
                    "actor_id",
                    "reason",
                    "trace_id",
                    "before_revision_id",
                    "after_revision_id",
                    "impact_scope",
                ],
            },
        }

    async def list_revisions(self) -> list[dict[str, Any]]:
        revisions = await self._revisions.list_revisions(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active_id = str(active.revision_id) if active else None
        return [revision_summary(revision, active_id) for revision in revisions]

    def _diagnostics(
        self,
        *,
        source: str,
        legacy_snapshot_only: bool,
        fallback_reason: str | None,
        active: SalesTrainerAssetRevision | None,
        working: SalesTrainerAssetRevision | None,
        path_payload: NewcomerPathConfigPayload,
    ) -> dict[str, Any]:
        return {
            "surface_key": NEWCOMER_PATH_LOGICAL_ID,
            "resource_type": NEWCOMER_PATH_RESOURCE_TYPE,
            "source": source,
            "legacy_snapshot_only": legacy_snapshot_only,
            "fallback_applied": legacy_snapshot_only,
            "fallback_reason": fallback_reason,
            "realtime_provider_readiness": self._realtime_provider_readiness(
                path_payload
            ),
            "management_entry": "/admin/newcomer-training/path-config",
            "permission_policy": {
                "view": "sales_trainer.manage_modules",
                "save": "sales_trainer.manage_modules",
                "publish": "sales_trainer.manage_modules",
                "rollback": "sales_trainer.manage_modules",
                "high_risk_ai_coach": "sales_trainer.manage_prompts",
                "regrade": "sales_trainer.regrade_history",
            },
            "active_revision": revision_summary(active, str(active.revision_id))
            if active
            else None,
            "working_revision": revision_summary(
                working,
                str(active.revision_id) if active else None,
            )
            if working
            else None,
            "high_risk_actions": {
                "publish": {
                    "requires_reason": True,
                    "requires_trace_id": True,
                    "audit_action": "newcomer_path_config.publish",
                    "impact_scope": "future_learners_only",
                    "preview_endpoint": (
                        "/api/v1/admin/newcomer-training/path-config/publish/preview"
                    ),
                },
                "rollback": {
                    "requires_reason": True,
                    "requires_trace_id": True,
                    "audit_action": "newcomer_path_config.rollback",
                    "impact_scope": "future_learners_only",
                    "preview_endpoint": (
                        "/api/v1/admin/newcomer-training/path-config/rollback/preview"
                    ),
                },
                "regrade": {
                    "requires_reason": True,
                    "requires_trace_id": True,
                    "audit_action": "historical_regrade.completed",
                    "impact_scope": "append_only_history",
                    "history_overwrite": False,
                },
            },
        }

    @staticmethod
    def _realtime_provider_readiness(
        path_payload: NewcomerPathConfigPayload,
    ) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for module in path_payload.modules:
            if module.module_type not in {"realtime_roleplay", "realtime_placeholder"}:
                continue
            binding = module.runtime_binding
            readiness = (
                binding.provider_readiness_snapshot.model_dump(mode="json")
                if binding is not None
                else None
            )
            diagnostics.append(
                {
                    "module_key": module.module_key,
                    "module_type": module.module_type,
                    "title": module.title,
                    "enabled": module.enabled,
                    "runtime_descriptor_id": (
                        binding.runtime_descriptor_id if binding is not None else None
                    ),
                    "provider_readiness_snapshot": readiness,
                    "ready": bool(readiness and readiness.get("ready") is True),
                    "failure_code": (
                        readiness.get("failure_code") if readiness is not None else None
                    ),
                    "failure_message": (
                        readiness.get("failure_message") if readiness is not None else None
                    ),
                }
            )
        return diagnostics

    async def _prepare_publish_target(
        self,
    ) -> tuple[
        SalesTrainerAssetRevision | None,
        SalesTrainerAssetRevision,
        NewcomerPathConfigPayload,
    ]:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if working is None:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]",
                "发布新人训练路径前必须先保存一版待发布修订，禁止从 legacy backfill 直接发布。",
                409,
            )
        publish_payload = payload_from_revision(working)
        validate_path_payload_for_write(publish_payload)
        await self._validate_ai_coach_prompt_bindings(publish_payload)
        await self._validate_publish_payload(publish_payload)
        return active, working, publish_payload

    @staticmethod
    def _path_fields_changed(
        before: NewcomerPathConfigPayload | None,
        after: NewcomerPathConfigPayload,
    ) -> list[str]:
        before_meta = {
            "title": before.title if before is not None else None,
            "goal_title": before.goal_title if before is not None else None,
            "description": before.description if before is not None else None,
        }
        after_meta = {
            "title": after.title,
            "goal_title": after.goal_title,
            "description": after.description,
        }
        return sorted(
            field for field, value in after_meta.items() if before_meta.get(field) != value
        )

    @staticmethod
    def _module_dump_by_key(
        payload: NewcomerPathConfigPayload | None,
    ) -> dict[str, dict[str, Any]]:
        if payload is None:
            return {}
        return {
            module.module_key: module.model_dump(mode="json")
            for module in payload.modules
        }

    @classmethod
    def _changed_module_keys(
        cls,
        before: NewcomerPathConfigPayload | None,
        after: NewcomerPathConfigPayload,
    ) -> list[str]:
        before_modules = cls._module_dump_by_key(before)
        after_modules = cls._module_dump_by_key(after)
        return sorted(
            key
            for key in set(before_modules) | set(after_modules)
            if before_modules.get(key) != after_modules.get(key)
        )

    @classmethod
    def _affected_module_keys(
        cls,
        before: NewcomerPathConfigPayload | None,
        after: NewcomerPathConfigPayload,
    ) -> list[str]:
        before_modules = cls._module_dump_by_key(before)
        after_modules = cls._module_dump_by_key(after)
        return sorted(set(before_modules) | set(after_modules))

    @staticmethod
    def _publish_preview_risk(
        *,
        active: SalesTrainerAssetRevision | None,
        working: SalesTrainerAssetRevision,
        changed_module_keys: list[str],
        path_fields_changed: list[str],
        high_risk_fields: list[str],
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []
        if active is None:
            reasons.append("first_publish")
        if high_risk_fields or str(working.change_class) == "scoring_high_risk":
            reasons.append("ai_coach_high_risk_fields_changed")
        if str(working.change_class) == "binding":
            reasons.append("module_binding_changed")
        elif changed_module_keys:
            reasons.append("module_configuration_changed")
        if path_fields_changed:
            reasons.append("path_metadata_changed")
        if not reasons:
            reasons.append("no_effective_content_change")
        if high_risk_fields or str(working.change_class) == "scoring_high_risk":
            return "high", reasons
        if active is None or changed_module_keys or path_fields_changed:
            return "medium", reasons
        return "low", reasons

    async def _backfill_payload(self) -> NewcomerPathConfigPayload:
        backfill_units = await load_published_path_units(self._db)
        modules = []
        path_title = "新人训练路径"
        goal_title: str | None = None
        for item in backfill_units:
            config = item.path_config
            path_title = config.path_title or path_title
            goal_title = config.goal_title or goal_title
            modules.append(module_from_unit(item.unit, config, module_key=item.module_key))
        modules = await self._backfill_audio_group_options(modules)
        return NewcomerPathConfigPayload(
            path_key=NEWCOMER_PATH_LOGICAL_ID,
            title=path_title,
            goal_title=goal_title,
            description=None,
            modules=sorted(modules, key=lambda item: item.order_index),
        )

    async def _backfill_audio_group_options(
        self,
        modules: list[NewcomerPathModuleConfig],
    ) -> list[NewcomerPathModuleConfig]:
        duration_options = await self._audio_group_duration_options("elevator_pitch")
        if not duration_options:
            return modules
        next_modules: list[NewcomerPathModuleConfig] = []
        for module in modules:
            if module.module_key != "elevator_pitch":
                next_modules.append(module)
                continue
            data = module.model_dump(mode="json")
            data["duration_options"] = duration_options
            next_modules.append(NewcomerPathModuleConfig.model_validate(data))
        return next_modules

    async def _audio_group_duration_options(
        self,
        module_key: str,
    ) -> list[dict[str, Any]]:
        result = await self._db.execute(
            select(SalesTrainerUnit).where(
                SalesTrainerUnit.status == "published",
                SalesTrainerUnit.unit_type == "audio_scoring",
            )
        )
        options: list[dict[str, Any]] = []
        for unit in result.scalars().all():
            raw_config = unit.config
            config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
            if not isinstance(config, dict):
                continue
            unit_path_config = path_config(config)
            if unit_path_config is None:
                continue
            raw_module_key = unit_path_config.module_key
            if raw_module_key != module_key:
                is_legacy_elevator = (
                    module_key == "elevator_pitch"
                    and raw_module_key == "pyramid_speech"
                )
                if not is_legacy_elevator:
                    continue
            duration_minutes = config.get("duration_minutes")
            if not isinstance(duration_minutes, int) or duration_minutes <= 0:
                continue
            options.append(
                {
                    "option_key": f"pitch_{duration_minutes}m",
                    "display_name": f"{duration_minutes} 分钟",
                    "duration_minutes": duration_minutes,
                    "target_unit_id": str(unit.unit_id),
                    "order_index": duration_minutes,
                }
            )
        return sorted(options, key=lambda item: int(item["duration_minutes"]))

    async def _projection_items(
        self,
        payload: NewcomerPathConfigPayload,
    ) -> list[PathUnitProjection]:
        unit_ids = self._projection_unit_ids(payload)
        units = await units_by_id(self._db, [unit_id for unit_id in unit_ids if unit_id])
        items: list[PathUnitProjection] = []
        for module in sorted(payload.modules, key=lambda item: item.order_index):
            if module.module_type == "audio_scoring_group":
                if not module.enabled:
                    continue
                for option in sorted(
                    module.duration_options,
                    key=lambda item: (item.order_index, item.option_key),
                ):
                    unit = units.get(option.target_unit_id)
                    if unit is None or str(unit.status) != "published":
                        continue
                    items.append(
                        PathUnitProjection(
                            unit=unit,
                            path_config=path_config_from_module(
                                payload,
                                module,
                                target_unit_id=option.target_unit_id,
                                level_title=option.display_name,
                                order_index=module.order_index,
                            ),
                        )
                    )
                continue
            if (
                not module.enabled
                and module.module_type != "realtime_placeholder"
            ) or not module.target_unit_id:
                continue
            unit = units.get(module.target_unit_id)
            if unit is None or str(unit.status) != "published":
                continue
            items.append(
                PathUnitProjection(
                    unit=unit,
                    path_config=path_config_from_module(payload, module),
                )
            )
        return items

    def _projection_unit_ids(
        self,
        payload: NewcomerPathConfigPayload,
    ) -> list[str]:
        unit_ids: list[str] = []
        for module in payload.modules:
            if module.module_type == "audio_scoring_group":
                if module.enabled:
                    unit_ids.extend(
                        option.target_unit_id for option in module.duration_options
                    )
                continue
            if module.enabled or module.module_type == "realtime_placeholder":
                if module.target_unit_id:
                    unit_ids.append(module.target_unit_id)
        return unit_ids

    async def _validate_ai_coach_prompt_bindings(
        self,
        payload: NewcomerPathConfigPayload,
    ) -> None:
        await self.validate_ai_coach_prompt_bindings_for_modules(payload.modules)

    async def validate_ai_coach_prompt_bindings_for_modules(
        self,
        modules: list[NewcomerPathModuleConfig],
    ) -> None:
        prompt_service = PromptTemplateService(self._db)
        resolver = PromptTemplateRevisionResolver(self._db, service=prompt_service)
        for module in modules:
            if module.ai_coach is None:
                continue
            await self._validate_ai_coach_prompt_binding(
                module=module,
                template_id=module.ai_coach.prompt_template_id,
                prompt_revision_id=module.ai_coach.prompt_revision_id,
                template_field="prompt_template_id",
                revision_field="prompt_revision_id",
                expected_prompt_type="stage",
                binding_label="AI 教练对话生成",
                prompt_service=prompt_service,
                resolver=resolver,
            )
            await self._validate_ai_coach_prompt_binding(
                module=module,
                template_id=module.ai_coach.scoring_prompt_template_id,
                prompt_revision_id=module.ai_coach.scoring_prompt_revision_id,
                template_field="scoring_prompt_template_id",
                revision_field="scoring_prompt_revision_id",
                expected_prompt_type="scoring",
                binding_label="AI 教练简答评分",
                prompt_service=prompt_service,
                resolver=resolver,
            )

    async def _validate_ai_coach_prompt_binding(
        self,
        *,
        module: NewcomerPathModuleConfig,
        template_id: str | None,
        prompt_revision_id: str | None,
        template_field: str,
        revision_field: str,
        expected_prompt_type: str,
        binding_label: str,
        prompt_service: PromptTemplateService,
        resolver: PromptTemplateRevisionResolver,
    ) -> None:
        if not template_id and not prompt_revision_id:
            return
        if prompt_revision_id and not template_id:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                f"{module.title} 的 {revision_field} 不能脱离 {template_field} 单独保存。",
                409,
            )
        try:
            template_uuid = UUID(str(template_id))
        except (TypeError, ValueError) as exc:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                f"{module.title} 的 {template_field} 必须是合法 UUID。",
                409,
            ) from exc
        template = await prompt_service.get_template(template_uuid)
        if template is None:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_REVISION_NOT_FOUND]",
                f"{module.title} 绑定的 {binding_label} PromptTemplate 不存在。",
                404,
            )
        if not bool(getattr(template, "is_active", False)):
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                f"{module.title} 绑定的 {template_field} 已停用，不能用于 {binding_label}。",
                409,
            )
        governance_issues = getattr(template, "governance_issues", []) or []
        if governance_issues:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                f"{module.title} 绑定的 {template_field} 存在治理问题，修复后才能用于 {binding_label}。",
                409,
            )
        if not self._matches_ai_coach_prompt_template(
            template,
            expected_prompt_type=expected_prompt_type,
        ):
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                (
                    f"{module.title} 的 {template_field} 必须绑定"
                    f"{binding_label}专用 PromptTemplate。"
                ),
                409,
            )
        if not prompt_revision_id:
            return
        try:
            resolution = await resolver.resolve(
                template_id=str(template_uuid),
                prompt_revision_id=prompt_revision_id,
            )
        except PromptTemplateRevisionResolverError as exc:
            raise self._prompt_resolver_config_error(
                module=module,
                template_field=template_field,
                binding_label=binding_label,
                exc=exc,
            ) from exc
        if resolution.status == RESULT_OK:
            if not bool(getattr(resolution.snapshot.template, "is_active", False)):
                raise SalesTrainerPathConfigError(
                    "[AI_COACH_PROMPT_CONFIG_INVALID]",
                    (
                        f"{module.title} 的 {revision_field} 指向了已停用的"
                        f"{binding_label} revision。"
                    ),
                    409,
                )
            return
        if resolution.status == RESULT_REVISION_NOT_FOUND:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_REVISION_NOT_FOUND]",
                f"{module.title} 的 {revision_field} 不存在或不可用。",
                404,
            )
        if resolution.status == RESULT_AUDIT_HISTORY_UNAVAILABLE:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_REVISION_AUDIT_MISSING]",
                f"{module.title} 的 {revision_field} 缺少可审计历史，禁止绑定。",
                409,
            )
        if resolution.status == RESULT_HEAD_USED_AS_FALLBACK:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_REVISION_FALLBACK]",
                (
                    f"{module.title} 的 {revision_field} 无法稳定解析到指定 revision，"
                    "禁止回退到当前 head。"
                ),
                409,
            )
        raise SalesTrainerPathConfigError(
            "[AI_COACH_PROMPT_CONFIG_INVALID]",
            f"{module.title} 的 {revision_field} 校验失败。",
            409,
        )

    @staticmethod
    def _matches_ai_coach_prompt_template(
        template: Any,
        *,
        expected_prompt_type: str,
    ) -> bool:
        prompt_type = SalesTrainerPathConfigService._enum_value(
            getattr(template, "prompt_type", None)
        )
        category = str(getattr(template, "category", "") or "").strip()
        business_purpose = SalesTrainerPathConfigService._enum_value(
            getattr(template, "business_purpose", None)
        )
        if prompt_type != expected_prompt_type:
            return False
        if business_purpose:
            return (
                business_purpose == PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
                and category == AI_COACH_PROMPT_CATEGORY
            )
        return category == AI_COACH_PROMPT_CATEGORY

    @staticmethod
    def _prompt_resolver_config_error(
        *,
        module: NewcomerPathModuleConfig,
        template_field: str,
        binding_label: str,
        exc: PromptTemplateRevisionResolverError,
    ) -> SalesTrainerPathConfigError:
        if exc.code == "[PROMPT_TEMPLATE_NOT_FOUND]":
            return SalesTrainerPathConfigError(
                "[AI_COACH_PROMPT_REVISION_NOT_FOUND]",
                f"{module.title} 绑定的 {binding_label} PromptTemplate 不存在。",
                404,
            )
        return SalesTrainerPathConfigError(
            "[AI_COACH_PROMPT_CONFIG_INVALID]",
            f"{module.title} 的 {template_field} 非法：{exc.message}",
            409,
        )

    @staticmethod
    def _enum_value(value: Any) -> str:
        if value is None:
            return ""
        return str(getattr(value, "value", value) or "").strip()

    async def _validate_publish_payload(
        self,
        payload: NewcomerPathConfigPayload,
    ) -> None:
        units = await units_by_id(self._db, self._publish_unit_ids(payload))
        for module in payload.modules:
            if module.module_type == "realtime_roleplay":
                self._validate_realtime_roleplay_module(module)
                continue
            if module.module_type == "realtime_placeholder":
                await self._validate_realtime_placeholder(module, units)
                continue
            if not module.enabled:
                continue
            if module.module_type == "audio_scoring":
                await self._validate_audio_module(payload, module, units)
                continue
            if module.module_type == "audio_scoring_group":
                await self._validate_audio_group_module(payload, module, units)
                continue
            if module.module_type == "article_exam":
                await self._validate_article_exam_module(module, units)
                continue

    def _publish_unit_ids(self, payload: NewcomerPathConfigPayload) -> list[str]:
        unit_ids: list[str] = []
        for module in payload.modules:
            if module.module_type == "audio_scoring_group":
                unit_ids.extend(option.target_unit_id for option in module.duration_options)
                continue
            if module.target_unit_id:
                unit_ids.append(module.target_unit_id)
        return unit_ids

    async def _validate_audio_module(
        self,
        payload: NewcomerPathConfigPayload,
        module: NewcomerPathModuleConfig,
        units: dict[str, SalesTrainerUnit],
    ) -> None:
        unit = await self._published_audio_unit_for_module(module, units)
        path_config = path_config_from_module(payload, module)
        unit_config = unit.config if isinstance(unit.config, dict) else None
        config = merge_audio_path_config(unit_config, path_config)
        await self._validate_audio_prompt(module, config)
        await self._validate_audio_materials(module, config)

    async def _validate_audio_group_module(
        self,
        payload: NewcomerPathConfigPayload,
        module: NewcomerPathModuleConfig,
        units: dict[str, SalesTrainerUnit],
    ) -> None:
        if not module.duration_options:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少演讲时长档位配置。",
                409,
            )
        for option in sorted(
            module.duration_options,
            key=lambda item: (item.order_index, item.option_key),
        ):
            unit = await self._published_audio_unit_for_target(
                module,
                units,
                target_unit_id=option.target_unit_id,
                label=option.display_name,
            )
            path_config = path_config_from_module(
                payload,
                module,
                target_unit_id=option.target_unit_id,
                level_title=option.display_name,
                order_index=module.order_index,
            )
            unit_config = unit.config if isinstance(unit.config, dict) else None
            config = merge_audio_path_config(unit_config, path_config)
            await self._validate_audio_prompt(module, config)
            await self._validate_audio_materials(module, config)

    async def _validate_article_exam_module(
        self,
        module: NewcomerPathModuleConfig,
        units: dict[str, SalesTrainerUnit],
    ) -> None:
        if not module.target_unit_id:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少考试训练单元绑定。",
                409,
            )
        unit = units.get(module.target_unit_id)
        if unit is None or unit.status != "published" or unit.unit_type != "quiz":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title} 绑定的考试训练单元不存在、未发布或类型不正确。",
                409,
            )
        if not module.learning_content_id:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少已发布学习内容绑定。",
                409,
            )
        learning_content = await get_learning_content(self._db, module.learning_content_id)
        if learning_content is None or learning_content.status != "published":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title} 绑定的学习内容不存在或未发布。",
                409,
            )
        if not module.exam_paper_id:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少已发布考试卷绑定。",
                409,
            )
        paper = await self._db.get(SalesTrainerExamPaper, module.exam_paper_id)
        if paper is None or paper.status != "published":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title} 绑定的考试卷不存在或未发布。",
                409,
            )

    @staticmethod
    def _validate_required_ai_coach_module(
        module: NewcomerPathModuleConfig,
    ) -> None:
        if module.module_key != "business_skills" or not module.enabled:
            return
        ai_coach = module.ai_coach
        if ai_coach is None or not ai_coach.enabled:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_NOT_CONFIGURED]",
                f"{module.title} 必须启用 AI 教练后才能发布。",
                409,
            )
        if not ai_coach.prompt_template_id:
            raise SalesTrainerPathConfigError(
                "[AI_COACH_NOT_CONFIGURED]",
                f"{module.title} 必须绑定 AI 教练生成 Prompt 后才能发布。",
                409,
            )

    def _validate_realtime_roleplay_module(
        self,
        module: NewcomerPathModuleConfig,
    ) -> None:
        if not module.enabled:
            return
        binding = module.runtime_binding
        if binding is None:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_REALTIME_BINDING_INVALID]",
                f"{module.title} 启用实时对练前必须配置 runtime binding。",
                409,
            )
        readiness = binding.provider_readiness_snapshot
        if not readiness.ready:
            reason = readiness.failure_message or readiness.failure_code or "provider 未就绪"
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
                f"{module.title} 的实时对练 provider readiness 未通过：{reason}。",
                503,
            )
        if binding.rollback_policy.fallback_to_placeholder:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_REALTIME_BINDING_INVALID]",
                f"{module.title} 的实时对练回滚策略不能回退为占位成功。",
                409,
            )

    async def _validate_realtime_placeholder(
        self,
        module: NewcomerPathModuleConfig,
        units: dict[str, SalesTrainerUnit],
    ) -> None:
        if module.enabled:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title} 是实时对练占位模块，当前版本必须保持停用。",
                409,
            )
        if not module.target_unit_id:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少占位展示单元绑定。",
                409,
            )
        unit = units.get(module.target_unit_id)
        if unit is None or unit.status != "published":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title} 绑定的占位展示单元不存在或未发布。",
                409,
            )

    async def _published_audio_unit_for_module(
        self,
        module: NewcomerPathModuleConfig,
        units: dict[str, SalesTrainerUnit],
    ) -> SalesTrainerUnit:
        return await self._published_audio_unit_for_target(
            module,
            units,
            target_unit_id=module.target_unit_id,
            label=module.title,
        )

    async def _published_audio_unit_for_target(
        self,
        module: NewcomerPathModuleConfig,
        units: dict[str, SalesTrainerUnit],
        *,
        target_unit_id: str | None,
        label: str,
    ) -> SalesTrainerUnit:
        if not target_unit_id:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少音频训练单元绑定。",
                409,
            )
        unit = units.get(target_unit_id)
        if unit is None or unit.status != "published" or unit.unit_type != "audio_scoring":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title}（{label}）绑定的音频训练单元不存在、未发布或类型不正确。",
                409,
            )
        return unit

    async def _validate_audio_prompt(
        self,
        module: NewcomerPathModuleConfig,
        config: dict[str, Any],
    ) -> None:
        audio = config.get("audio")
        prompt_id = audio.get("scoring_prompt_id") if isinstance(audio, dict) else None
        if not prompt_id:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少已发布录音评分标准。",
                409,
            )
        prompt = await self._db.get(SalesTrainerAudioScorePrompt, str(prompt_id))
        if prompt is None or prompt.status != "published":
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_CONFIG_INVALID]",
                f"{module.title} 绑定的录音评分标准不存在或未发布。",
                409,
            )

    async def _validate_audio_materials(
        self,
        module: NewcomerPathModuleConfig,
        config: dict[str, Any],
    ) -> None:
        audio = config.get("audio")
        purpose = audio.get("purpose") if isinstance(audio, dict) else None
        materials = config.get("materials")
        bindings = materials.get("bindings") if isinstance(materials, dict) else None
        requires_material = (
            module.module_key == "ppt_explanation"
            or purpose == "ppt_pitch"
            or bool(module.material_id)
        )
        if not requires_material:
            return
        if not isinstance(bindings, list) or not bindings:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_MODULE_BINDING_MISSING]",
                f"{module.title} 缺少已发布训练材料。",
                409,
            )
        for raw_binding in bindings:
            if not isinstance(raw_binding, dict):
                continue
            material_id = raw_binding.get("material_id")
            if not material_id:
                continue
            material = await self._db.get(SalesTrainerMaterial, str(material_id))
            if material is None or material.status != "published":
                raise SalesTrainerPathConfigError(
                    "[NEWCOMER_MODULE_CONFIG_INVALID]",
                    f"{module.title} 绑定的训练材料不存在或未发布。",
                    409,
                )
            version_id = raw_binding.get("locked_version_id") or material.current_version_id
            if not version_id:
                raise SalesTrainerPathConfigError(
                    "[NEWCOMER_MODULE_CONFIG_INVALID]",
                    f"{module.title} 绑定的训练材料缺少已发布版本。",
                    409,
                )
            version = await self._db.get(SalesTrainerMaterialVersion, str(version_id))
            if (
                version is None
                or version.material_id != material.material_id
                or version.status != "published"
            ):
                raise SalesTrainerPathConfigError(
                    "[NEWCOMER_MODULE_CONFIG_INVALID]",
                    f"{module.title} 绑定的训练材料版本不存在或未发布。",
                    409,
                )
            return
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_MODULE_BINDING_MISSING]",
            f"{module.title} 缺少已发布训练材料。",
            409,
        )

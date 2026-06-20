from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
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
)
from sales_trainer.services.path_config_operations import (
    get_path_revision,
    load_published_path_units,
    record_path_config_event,
    units_by_id,
)


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
        source: Literal["active_revision", "unit_backfill"] = "active_revision"
        if active is None:
            path = await self._backfill_payload()
            source = "unit_backfill"
        else:
            path = payload_from_revision(active)
        return {
            "source": source,
            "path": path.model_dump(mode="json"),
            "active_revision_id": str(active.revision_id) if active else None,
            "active_revision_no": active.revision_no if active else None,
            "working_revision_id": str(working.revision_id) if working else None,
            "working_revision_no": working.revision_no if working else None,
            "has_unpublished_revision": working is not None,
        }

    async def active_projection(self) -> PathProjection | None:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if active is None:
            return None
        payload = payload_from_revision(active)
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
        path_payload = NewcomerPathConfigPayload.model_validate(
            payload.model_dump(mode="json", exclude={"reason"})
        )
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
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        publish_payload = (
            await self._backfill_payload()
            if working is None
            else payload_from_revision(working)
        )
        await self._validate_publish_payload(publish_payload)
        try:
            if working is None:
                result = await self._revisions.create_published_revision(
                    resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                    logical_id=NEWCOMER_PATH_LOGICAL_ID,
                    payload=publish_payload.model_dump(mode="json"),
                    actor=actor,
                    change_class="binding",
                    reason=reason,
                    trace_id=trace_id,
                )
            else:
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
            config = unit.config or {}
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

    async def _validate_publish_payload(
        self,
        payload: NewcomerPathConfigPayload,
    ) -> None:
        units = await units_by_id(self._db, self._publish_unit_ids(payload))
        for module in payload.modules:
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
        config = merge_audio_path_config(unit.config or {}, path_config)
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
            config = merge_audio_path_config(unit.config or {}, path_config)
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

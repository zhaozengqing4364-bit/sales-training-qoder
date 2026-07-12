from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.cos.signing import CosConfigError, get_cos_signing_service
from common.db.models import User
from common.monitoring.logger import get_trace_id
from common.oss.signing import OssConfigError, get_oss_signing_service
from sales_trainer.models import (
    NewcomerTrainingEnrollment,
    SalesTrainerAssetRevision,
    SalesTrainerAudioSubmission,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.revision_service import (
    PATH_LOGICAL_ID,
    PATH_RESOURCE_TYPE,
)
from sales_trainer.permissions import (
    can_manage_sales_trainer,
    is_sales_trainer_manager,
    is_sales_trainer_ops,
)
from sales_trainer.schemas import (
    SalesTrainerAudioScoreOutputSchema,
    SalesTrainerLearnerRubric,
    SalesTrainerMaterialBindingConfig,
    SalesTrainerMaterialCreate,
    SalesTrainerMaterialUpdate,
    SalesTrainerMaterialVersionCreate,
    SalesTrainerTaskBriefConfig,
    SalesTrainerUnitMaterialsConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audio_evaluation_scenarios import (
    resolve_audio_evaluation_scenario_from_config,
)
from sales_trainer.services.material_metadata_update import (
    material_metadata_snapshot,
    record_material_metadata_update,
)
from sales_trainer.services.material_publish_workflow import (
    MaterialPublishWorkflowError,
    publish_material_version,
)
from sales_trainer.services.operation_log_service import OperationLogService

DEFAULT_MATERIAL_FILE_URL_EXPIRES_SECONDS = 3600


class MaterialServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MaterialFileAccess:
    def __init__(
        self,
        *,
        mode: str,
        path: Path | None,
        redirect_url: str | None,
        media_type: str,
        filename: str,
    ) -> None:
        self.mode = mode
        self.path = path
        self.redirect_url = redirect_url
        self.media_type = media_type
        self.filename = filename


class SalesTrainerMaterialService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)

    async def list_materials(
        self,
        *,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerMaterial], int]:
        stmt = select(SalesTrainerMaterial)
        count_stmt = select(func.count()).select_from(SalesTrainerMaterial)
        if not include_archived:
            stmt = stmt.where(SalesTrainerMaterial.status != "archived")
            count_stmt = count_stmt.where(SalesTrainerMaterial.status != "archived")
        result = await self._db.execute(
            stmt.order_by(SalesTrainerMaterial.updated_at.desc()).offset(offset).limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def get_material(self, material_id: str) -> SalesTrainerMaterial | None:
        return await self._db.get(SalesTrainerMaterial, material_id)

    async def get_version(self, version_id: str) -> SalesTrainerMaterialVersion | None:
        return await self._db.get(SalesTrainerMaterialVersion, version_id)

    async def create_material(
        self,
        payload: SalesTrainerMaterialCreate,
        *,
        actor: User,
    ) -> SalesTrainerMaterial:
        material_key = _validate_material_key(payload.material_key)
        await self._ensure_material_key_available(material_key)
        material = SalesTrainerMaterial(
            material_key=material_key,
            name=payload.name,
            material_type=payload.material_type,
            description=payload.description,
            purpose=payload.purpose,
            created_by=str(actor.user_id),
            updated_by=str(actor.user_id),
        )
        self._db.add(material)
        await self._db.flush()
        await self._logs.record(
            actor=actor,
            action="material_created",
            target_type="sales_trainer_material",
            target_id=str(material.material_id),
            metadata={
                "material_key": str(material.material_key),
                "material_type": str(material.material_type),
            },
        )
        await self._db.commit()
        await self._db.refresh(material)
        return material

    async def update_material(
        self,
        material: SalesTrainerMaterial,
        payload: SalesTrainerMaterialUpdate,
        *,
        actor: User,
    ) -> SalesTrainerMaterial:
        if material.status == "archived":
            raise MaterialServiceError(
                "[SALES_TRAINER_MATERIAL_ARCHIVED]",
                "已归档材料不能修改。",
                status_code=409,
            )
        trace_id = get_trace_id()
        before_snapshot = material_metadata_snapshot(material)
        data = payload.model_dump(exclude_unset=True)
        next_key = data.get("material_key")
        if next_key and next_key != material.material_key:
            data["material_key"] = _validate_material_key(str(next_key))
            await self._ensure_material_key_available(str(data["material_key"]))
        for key, value in data.items():
            setattr(material, key, value)
        setattr(material, "updated_by", str(actor.user_id))
        await record_material_metadata_update(
            self._logs,
            material=material,
            actor=actor,
            before=before_snapshot,
            after=material_metadata_snapshot(material),
            trace_id=trace_id,
        )
        await self._db.commit()
        await self._db.refresh(material)
        return material

    async def archive_material(
        self,
        material: SalesTrainerMaterial,
        *,
        actor: User,
    ) -> SalesTrainerMaterial:
        blockers = await self._path_reference_blockers(material)
        if blockers:
            raise MaterialServiceError(
                "[MATERIAL_ARCHIVE_ACTIVE_REFERENCE]",
                "材料仍被 active 或 working 新人训练路径引用，禁止归档。",
                status_code=409,
            )
        setattr(material, "status", "archived")
        setattr(material, "updated_by", str(actor.user_id))
        await self._logs.record(
            actor=actor,
            action="material_archived",
            target_type="sales_trainer_material",
            target_id=str(material.material_id),
            metadata={
                "trace_id": get_trace_id(),
                "active_or_working_path_refs": blockers,
                "historical_replay_preserved": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(material)
        return material

    async def create_version(
        self,
        material: SalesTrainerMaterial,
        payload: SalesTrainerMaterialVersionCreate,
        *,
        actor: User,
    ) -> SalesTrainerMaterialVersion:
        if material.status == "archived":
            raise MaterialServiceError(
                "[SALES_TRAINER_MATERIAL_ARCHIVED]",
                "已归档材料不能新增版本。",
                status_code=409,
            )
        existing = await self._db.execute(
            select(SalesTrainerMaterialVersion).where(
                SalesTrainerMaterialVersion.material_id == material.material_id,
                SalesTrainerMaterialVersion.version_label == payload.version_label,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise MaterialServiceError(
                "[MATERIAL_VERSION_LABEL_EXISTS]",
                "该材料版本号已存在。",
                status_code=409,
            )
        version = SalesTrainerMaterialVersion(
            material_id=material.material_id,
            version_label=payload.version_label,
            title=payload.title,
            file_name=payload.file_name,
            content_type=payload.content_type,
            file_size_bytes=payload.file_size_bytes,
            storage_key=payload.storage_key,
            file_hash=payload.file_hash,
            release_notes=payload.release_notes,
            created_by=str(actor.user_id),
        )
        self._db.add(version)
        await self._db.flush()
        await self._logs.record(
            actor=actor,
            action="material_version_created",
            target_type="sales_trainer_material_version",
            target_id=str(version.version_id),
            metadata={
                "material_id": str(material.material_id),
                "version_label": str(version.version_label),
            },
        )
        await self._db.commit()
        await self._db.refresh(version)
        return version

    async def publish_version(
        self,
        version: SalesTrainerMaterialVersion,
        *,
        actor: User,
    ) -> SalesTrainerMaterialVersion:
        try:
            return await publish_material_version(
                self._db,
                self._logs,
                version,
                actor=actor,
            )
        except MaterialPublishWorkflowError as exc:
            raise MaterialServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

    async def preview_version_rollback(
        self,
        material: SalesTrainerMaterial,
        *,
        target_version_id: str,
    ) -> dict[str, Any]:
        target = await self._material_rollback_target(material, target_version_id)
        refs = await self._path_reference_blockers(material)
        return {
            "action": "material_version.rollback",
            "permission": "sales_trainer.manage_modules",
            "requires_reason": True,
            "future_only": True,
            "mutates_history": False,
            "target_material_id": str(material.material_id),
            "current_version_id": material.current_version_id,
            "target_version": _serialize_version(target),
            "future_material_current_version_changed": (
                str(material.current_version_id or "") != str(target.version_id)
            ),
            "historical_submissions_changed": False,
            "historical_replay_preserved": True,
            "active_or_working_path_refs": refs,
            "rollback_plan": {
                "apply_endpoint": (
                    f"/api/v1/admin/sales-trainer/materials/"
                    f"{material.material_id}/versions/rollback"
                ),
                "rollback_endpoint": (
                    f"/api/v1/admin/sales-trainer/materials/"
                    f"{material.material_id}/versions/rollback/preview"
                ),
                "strategy": "restore_existing_material_version_as_current",
            },
        }

    async def rollback_version(
        self,
        material: SalesTrainerMaterial,
        *,
        target_version_id: str,
        reason: str,
        actor: User,
    ) -> SalesTrainerMaterialVersion:
        if material.status == "archived":
            raise MaterialServiceError(
                "[SALES_TRAINER_MATERIAL_ARCHIVED]",
                "已归档材料不能回滚版本。",
                status_code=409,
            )
        trace_id = get_trace_id()
        target = await self._material_rollback_target(material, target_version_id)
        previous_current_version_id = str(material.current_version_id or "") or None
        previous = await self._db.execute(
            select(SalesTrainerMaterialVersion).where(
                SalesTrainerMaterialVersion.material_id == material.material_id,
                SalesTrainerMaterialVersion.status == "published",
                SalesTrainerMaterialVersion.version_id != target.version_id,
            )
        )
        archived_version_ids: list[str] = []
        for item in previous.scalars().all():
            setattr(item, "status", "archived")
            archived_version_ids.append(str(item.version_id))
        target_published_at = cast(datetime | None, target.published_at)
        target_published_by = cast(str | None, target.published_by)
        target_version_id_str = str(target.version_id)
        setattr(target, "status", "published")
        setattr(target, "published_at", target_published_at or datetime.now(UTC))
        setattr(target, "published_by", target_published_by or str(actor.user_id))
        setattr(material, "status", "published")
        setattr(material, "current_version_id", target_version_id_str)
        setattr(material, "updated_by", str(actor.user_id))
        await self._logs.record(
            actor=actor,
            action="material_version_rolled_back",
            target_type="sales_trainer_material_version",
            target_id=target_version_id_str,
            request_id=trace_id,
            metadata={
                "material_id": str(material.material_id),
                "before_version_id": previous_current_version_id,
                "after_version_id": target_version_id_str,
                "archived_version_ids": archived_version_ids,
                "reason": reason,
                "trace_id": trace_id,
                "future_only": True,
                "historical_submissions_changed": False,
                "historical_replay_preserved": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(target)
        return target

    async def list_versions(self, material_id: str) -> list[SalesTrainerMaterialVersion]:
        result = await self._db.execute(
            select(SalesTrainerMaterialVersion)
            .where(SalesTrainerMaterialVersion.material_id == material_id)
            .order_by(SalesTrainerMaterialVersion.created_at.desc())
        )
        return list(result.scalars().all())

    async def _material_rollback_target(
        self,
        material: SalesTrainerMaterial,
        target_version_id: str,
    ) -> SalesTrainerMaterialVersion:
        target = await self._db.get(SalesTrainerMaterialVersion, target_version_id)
        if target is None or target.material_id != material.material_id:
            raise MaterialServiceError(
                "[MATERIAL_VERSION_NOT_FOUND]",
                "目标材料版本不存在或不属于当前材料。",
                status_code=404,
            )
        if target.status not in {"published", "archived"}:
            raise MaterialServiceError(
                "[MATERIAL_VERSION_NOT_ROLLBACKABLE]",
                "只能回滚到已发布或已归档的材料版本。",
                status_code=409,
            )
        return target

    async def serialize_material(
        self,
        material: SalesTrainerMaterial,
        *,
        include_versions: bool = True,
    ) -> dict[str, Any]:
        material_id = str(material.material_id)
        versions = await self.list_versions(material_id) if include_versions else []
        current_version = None
        if material.current_version_id:
            current_version = await self._db.get(
                SalesTrainerMaterialVersion,
                material.current_version_id,
            )
        return {
            "material_id": material.material_id,
            "material_key": material.material_key,
            "name": material.name,
            "material_type": material.material_type,
            "description": material.description,
            "purpose": material.purpose,
            "status": material.status,
            "current_version_id": material.current_version_id,
            "created_by": material.created_by,
            "updated_by": material.updated_by,
            "created_at": material.created_at,
            "updated_at": material.updated_at,
            "current_version": _serialize_version(current_version) if current_version else None,
            "versions": [_serialize_version(version) for version in versions],
        }

    async def resolve_unit_brief(
        self,
        unit: SalesTrainerUnit,
        *,
        config_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config_override if config_override is not None else _unit_config(unit)
        task_brief = _resolve_task_brief(unit, config_override=config)
        material_items = await self.resolve_unit_material_items(
            unit,
            learner_visible=True,
            config_override=config,
        )
        score_scheme = await self.resolve_score_scheme(unit, config_override=config)
        return {
            "task_brief": task_brief,
            "materials": material_items,
            "score_scheme": score_scheme,
        }

    async def resolve_unit_material_items(
        self,
        unit: SalesTrainerUnit,
        *,
        learner_visible: bool,
        config_override: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raw_config = config_override if config_override is not None else _unit_config(unit)
        config = _validate_materials_config(raw_config or {})
        items: list[dict[str, Any]] = []
        for binding in sorted(config.bindings, key=lambda item: item.display_order):
            material = await self._db.get(SalesTrainerMaterial, binding.material_id)
            if material is None:
                if binding.required:
                    raise MaterialServiceError(
                        "[SALES_TRAINER_MATERIAL_NOT_FOUND]",
                        "训练任务绑定的材料不存在。",
                        status_code=404,
                    )
                continue
            if learner_visible and material.status != "published":
                if binding.required:
                    raise MaterialServiceError(
                        "[SALES_TRAINER_MATERIAL_NOT_PUBLISHED]",
                        "训练任务绑定的材料未发布。",
                        status_code=409,
                    )
                continue
            version = await self._resolve_binding_version(binding, material)
            if version is None:
                if binding.required:
                    raise MaterialServiceError(
                        "[MATERIAL_VERSION_REQUIRED]",
                        "训练任务绑定的材料缺少可用版本。",
                        status_code=409,
                    )
                continue
            if learner_visible and version.status != "published":
                raise MaterialServiceError(
                    "[MATERIAL_VERSION_NOT_PUBLISHED]",
                    "训练任务绑定的材料版本未发布。",
                    status_code=409,
                )
            items.append(
                {
                    "material_id": material.material_id,
                    "material_key": material.material_key,
                    "name": material.name,
                    "material_type": material.material_type,
                    "description": material.description,
                    "purpose": material.purpose,
                    "required": binding.required,
                    "confirmation_required": binding.confirmation_required,
                    "learner_note": binding.learner_note,
                    "display_order": binding.display_order,
                    "current_version": _serialize_version(version),
                }
            )
        return items

    async def resolve_score_scheme(
        self,
        unit: SalesTrainerUnit,
        *,
        config_override: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        raw_config = config_override if config_override is not None else _unit_config(unit)
        prompt_id = ((raw_config or {}).get("audio") or {}).get("scoring_prompt_id")
        if not prompt_id:
            return None
        from sales_trainer.models import SalesTrainerAudioScorePrompt
        from sales_trainer.rules import resolve_audio_pass_threshold

        prompt = await self._db.get(SalesTrainerAudioScorePrompt, str(prompt_id))
        if prompt is None:
            return None
        from sales_trainer.services.prompt_revision_payloads import (
            prompt_lifecycle_snapshot,
        )

        rubric: dict[str, Any] = normalize_learner_rubric(prompt.learner_rubric)
        threshold = resolve_audio_pass_threshold(raw_config or {})
        if isinstance(rubric, dict) and "pass_threshold" not in rubric:
            rubric = {**rubric, "pass_threshold": threshold}
        return {
            "prompt_id": prompt.prompt_id,
            "name": prompt.name,
            "purpose": prompt.purpose,
            "version": int(prompt.version),
            "status": prompt.status,
            "learner_rubric": rubric,
            "pass_threshold": threshold,
            "prompt_snapshot": prompt_lifecycle_snapshot(prompt),
        }

    async def freeze_submission_snapshots(
        self,
        unit: SalesTrainerUnit,
        *,
        confirmed_material_version_id: str | None,
        config_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config_override if config_override is not None else _unit_config(unit)
        task_brief = _resolve_task_brief(unit, config_override=config)
        material_items = await self.resolve_unit_material_items(
            unit,
            learner_visible=True,
            config_override=config,
        )
        required_confirmations = [
            item
            for item in material_items
            if item.get("required") and item.get("confirmation_required")
        ]
        if required_confirmations:
            if not confirmed_material_version_id:
                raise MaterialServiceError(
                    "[MATERIAL_VERSION_CONFIRMATION_REQUIRED]",
                    "提交前必须确认最新版训练材料。",
                    status_code=409,
                )
            allowed_ids = {
                str(item["current_version"]["version_id"])
                for item in required_confirmations
            }
            if confirmed_material_version_id not in allowed_ids:
                raise MaterialServiceError(
                    "[MATERIAL_VERSION_CONFIRMATION_OUTDATED]",
                    "确认的训练材料版本已不是当前要求版本，请重新下载并确认。",
                    status_code=409,
                )
        score_scheme = await self.resolve_score_scheme(unit, config_override=config)
        return {
            "material_snapshot": {
                "version": 1,
                "items": material_items,
                "confirmed_material_version_id": confirmed_material_version_id,
                "frozen_at": datetime.now(UTC).isoformat(),
            },
            "score_scheme_snapshot": score_scheme,
            "task_brief_snapshot": task_brief,
        }

    async def resolve_file_access(
        self,
        version_id: str,
        *,
        actor: User,
    ) -> MaterialFileAccess:
        version = await self._db.get(SalesTrainerMaterialVersion, version_id)
        if version is None or version.status != "published":
            raise MaterialServiceError(
                "[MATERIAL_VERSION_NOT_PUBLISHED]",
                "训练材料版本不存在或未发布。",
                status_code=404,
            )
        await self._ensure_actor_can_access_file(version, actor=actor)
        return self._file_access_from_version(version)

    async def resolve_historical_file_access(
        self,
        version_id: str,
        *,
        record_type: str,
        record_id: str,
        viewer: User,
        team_department: str | None,
    ) -> MaterialFileAccess:
        if record_type != "audio_submission":
            raise MaterialServiceError(
                "[TRAINING_RECORD_MATERIAL_REPLAY_UNSUPPORTED]",
                "当前训练记录类型没有可回放材料文件。",
                status_code=400,
            )
        from sales_trainer.services.training_record_service import TrainingRecordService

        record = await TrainingRecordService(self._db).get_record_for_viewer(
            record_type,
            record_id,
            viewer=viewer,
            team_department=team_department,
        )
        if record is None:
            raise MaterialServiceError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "训练记录不存在或无权查看。",
                status_code=404,
            )
        version = await self._db.get(SalesTrainerMaterialVersion, version_id)
        if version is None or version.status not in {"published", "archived"}:
            raise MaterialServiceError(
                "[MATERIAL_VERSION_NOT_PUBLISHED]",
                "历史训练材料版本不存在或不可回放。",
                status_code=404,
            )
        submission = await self._db.get(SalesTrainerAudioSubmission, record_id)
        if (
            submission is None
            or str(submission.confirmed_material_version_id or "") != version_id
        ):
            raise MaterialServiceError(
                "[MATERIAL_HISTORY_REFERENCE_NOT_FOUND]",
                "训练记录未引用该材料版本，禁止历史回放。",
                status_code=404,
            )
        return self._file_access_from_version(version)

    async def _ensure_actor_can_access_file(
        self,
        version: SalesTrainerMaterialVersion,
        *,
        actor: User,
    ) -> None:
        if can_manage_sales_trainer(actor) or is_sales_trainer_ops(actor):
            return
        if is_sales_trainer_manager(actor):
            raise MaterialServiceError(
                "[PERMISSION_DENIED]",
                "当前账号无权访问训练材料文件。",
                status_code=403,
            )
        if not await self._learner_can_access_active_material_version(
            actor=actor,
            version=version,
        ):
            raise MaterialServiceError(
                "[MATERIAL_FILE_NOT_FOUND]",
                "训练材料文件不存在。",
                status_code=404,
            )

    async def _learner_can_access_active_material_version(
        self,
        *,
        actor: User,
        version: SalesTrainerMaterialVersion,
    ) -> bool:
        enrollment = await self._db.scalar(
            select(NewcomerTrainingEnrollment).where(
                NewcomerTrainingEnrollment.learner_id == str(actor.user_id),
                NewcomerTrainingEnrollment.path_id == PATH_LOGICAL_ID,
                NewcomerTrainingEnrollment.status == "active",
            )
        )
        if enrollment is None:
            return False
        revision = await self._db.get(
            SalesTrainerAssetRevision, str(enrollment.path_revision_id)
        )
        if revision is None:
            return False
        payload = TrainingPathPayload.model_validate(revision.payload_json)
        target_version_id = str(version.version_id)
        for phase in payload.phases:
            for module in phase.modules:
                for activity in module.activities:
                    if activity.type != "audio_assessment":
                        continue
                    if activity.config.material_id != str(version.material_id):
                        continue
                    material = await self._db.get(
                        SalesTrainerMaterial, str(version.material_id)
                    )
                    if material is not None and str(material.current_version_id) == target_version_id:
                        return True
        return False

    async def _path_reference_blockers(
        self,
        material: SalesTrainerMaterial,
    ) -> list[dict[str, Any]]:
        version_ids_result = await self._db.execute(
            select(SalesTrainerMaterialVersion.version_id).where(
                SalesTrainerMaterialVersion.material_id == material.material_id
            )
        )
        version_ids = {str(value) for value in version_ids_result.scalars().all()}
        revisions: list[SalesTrainerAssetRevision] = []
        revisions_service = SalesTrainerAssetRevisionService(self._db)
        active = await revisions_service.active_revision(
            resource_type=PATH_RESOURCE_TYPE,
            logical_id=PATH_LOGICAL_ID,
        )
        working = await revisions_service.latest_working_revision(
            resource_type=PATH_RESOURCE_TYPE,
            logical_id=PATH_LOGICAL_ID,
        )
        for revision in (active, working):
            if revision is None:
                continue
            if all(existing.revision_id != revision.revision_id for existing in revisions):
                revisions.append(revision)

        blockers: list[dict[str, Any]] = []
        for revision in revisions:
            payload = TrainingPathPayload.model_validate(revision.payload_json)
            for phase in payload.phases:
                for module in phase.modules:
                    for activity in module.activities:
                        if activity.type != "audio_assessment":
                            continue
                        if activity.config.material_id != str(material.material_id):
                            continue
                        blockers.append(
                            {
                                "source": "active_revision"
                                if revision is active
                                else "working_revision",
                                "revision_id": str(revision.revision_id),
                                "revision_no": int(revision.revision_no),
                                "phase_id": phase.phase_id,
                                "module_id": module.module_id,
                                "activity_id": activity.activity_id,
                                "material_id": activity.config.material_id,
                                "material_version_ids": sorted(version_ids),
                            }
                        )
        return blockers

    def _file_access_from_version(
        self,
        version: SalesTrainerMaterialVersion,
    ) -> MaterialFileAccess:
        storage_key = str(version.storage_key or "")
        local_path = Path(storage_key)
        if local_path.exists():
            resolved_path = local_path.resolve()
            storage_root = Path(
                os.getenv(
                    "SALES_TRAINER_MATERIAL_STORAGE_PATH",
                    "./data/sales_trainer_materials",
                )
            ).resolve()
            if storage_root not in (resolved_path, *resolved_path.parents):
                raise MaterialServiceError(
                    "[MATERIAL_FILE_ACCESS_DENIED]",
                    "训练材料文件不在允许的存储目录内。",
                    status_code=403,
                )
            if not resolved_path.is_file():
                raise MaterialServiceError(
                    "[MATERIAL_FILE_NOT_FOUND]",
                    "训练材料文件不存在。",
                    status_code=404,
                )
            return MaterialFileAccess(
                mode="local",
                path=resolved_path,
                redirect_url=None,
                media_type=str(version.content_type or "application/octet-stream"),
                filename=str(version.file_name or resolved_path.name),
            )
        if _is_object_storage_key(storage_key):
            try:
                signed_url = _generate_object_storage_get_url(storage_key)
            except OssConfigError as exc:
                raise MaterialServiceError("[OSS_NOT_CONFIGURED]", str(exc), status_code=503) from exc
            except CosConfigError as exc:
                raise MaterialServiceError("[COS_NOT_CONFIGURED]", str(exc), status_code=503) from exc
            return MaterialFileAccess(
                mode="redirect",
                path=None,
                redirect_url=signed_url,
                media_type=str(version.content_type or "application/octet-stream"),
                filename=str(version.file_name or "material"),
            )
        raise MaterialServiceError(
            "[MATERIAL_FILE_NOT_FOUND]",
            "训练材料文件不存在。",
            status_code=404,
        )

    async def _ensure_material_key_available(self, material_key: str) -> None:
        result = await self._db.execute(
            select(SalesTrainerMaterial).where(
                SalesTrainerMaterial.material_key == material_key
            )
        )
        if result.scalar_one_or_none() is not None:
            raise MaterialServiceError(
                "[MATERIAL_KEY_EXISTS]",
                "训练材料标识已存在。",
                status_code=409,
            )

    async def _resolve_binding_version(
        self,
        binding: SalesTrainerMaterialBindingConfig,
        material: SalesTrainerMaterial,
    ) -> SalesTrainerMaterialVersion | None:
        if binding.version_policy == "locked_version":
            if not binding.locked_version_id:
                return None
            version = await self._db.get(
                SalesTrainerMaterialVersion,
                binding.locked_version_id,
            )
            if version is None or version.material_id != material.material_id:
                return None
            return version
        if not material.current_version_id:
            return None
        return await self._db.get(
            SalesTrainerMaterialVersion,
            material.current_version_id,
        )


def _unit_config(unit: SalesTrainerUnit) -> dict[str, Any] | None:
    return cast(dict[str, Any] | None, unit.config)


def _validate_materials_config(config: dict[str, Any]) -> SalesTrainerUnitMaterialsConfig:
    raw = config.get("materials")
    if raw is None:
        return SalesTrainerUnitMaterialsConfig()
    if not isinstance(raw, dict):
        raise MaterialServiceError(
            "[SALES_TRAINER_MATERIAL_BINDING_INVALID]",
            "训练任务材料绑定配置必须是对象。",
            status_code=422,
        )
    try:
        return cast(
            SalesTrainerUnitMaterialsConfig,
            SalesTrainerUnitMaterialsConfig.model_validate(raw),
        )
    except ValueError as exc:
        raise MaterialServiceError(
            "[SALES_TRAINER_MATERIAL_BINDING_INVALID]",
            "训练任务材料绑定配置不合法。",
            status_code=422,
        ) from exc


def _resolve_task_brief(
    unit: SalesTrainerUnit,
    *,
    config_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config_override if config_override is not None else _unit_config(unit)
    raw = (config or {}).get("task_brief")
    if raw is None:
        return {
            "enabled": True,
            "title": unit.name,
            "purpose": unit.description,
            "scenario": None,
            "instructions": [],
            "success_criteria": [],
            "common_mistakes": [],
            "upload_guidance": None,
        }
    if not isinstance(raw, dict):
        raise MaterialServiceError(
            "[SALES_TRAINER_TASK_BRIEF_INVALID]",
            "训练任务简报配置必须是对象。",
            status_code=422,
        )
    try:
        brief = cast(
            dict[str, Any],
            SalesTrainerTaskBriefConfig.model_validate(raw).model_dump(),
        )
    except ValueError as exc:
        raise MaterialServiceError(
            "[SALES_TRAINER_TASK_BRIEF_INVALID]",
            "训练任务简报配置不合法。",
            status_code=422,
        ) from exc
    if not brief.get("title"):
        brief["title"] = unit.name
    if not brief.get("purpose"):
        brief["purpose"] = unit.description
    return brief


def validate_unit_material_and_brief_config(config: dict[str, Any]) -> None:
    _validate_materials_config(config)
    raw_brief = config.get("task_brief")
    if raw_brief is not None:
        if not isinstance(raw_brief, dict):
            raise MaterialServiceError(
                "[SALES_TRAINER_TASK_BRIEF_INVALID]",
                "训练任务简报配置必须是对象。",
                status_code=422,
            )
        try:
            SalesTrainerTaskBriefConfig.model_validate(raw_brief)
        except ValueError as exc:
            raise MaterialServiceError(
                "[SALES_TRAINER_TASK_BRIEF_INVALID]",
                "训练任务简报配置不合法。",
                status_code=422,
            ) from exc
    scenario = resolve_audio_evaluation_scenario_from_config(config)
    if scenario is not None and scenario.requires_confirmed_material:
        materials = _validate_materials_config(config)
        required_bindings = [
            binding
            for binding in materials.bindings
            if binding.required and binding.confirmation_required
        ]
        if not required_bindings:
            raise MaterialServiceError(
                scenario.material_error_code,
                f"{scenario.display_name}任务必须绑定至少一个需要学员确认的训练材料。",
                status_code=422,
            )


def serialize_material_version(version: SalesTrainerMaterialVersion) -> dict[str, Any]:
    return _serialize_version(version)


def _validate_material_key(value: str) -> str:
    material_key = value.strip()
    if not material_key:
        raise MaterialServiceError(
            "[MATERIAL_KEY_INVALID]",
            "训练材料标识不能为空。",
            status_code=422,
        )
    if not material_key.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise MaterialServiceError(
            "[MATERIAL_KEY_INVALID]",
            "训练材料标识只能包含字母、数字、下划线、中划线和点。",
            status_code=422,
        )
    return material_key


def _serialize_version(version: SalesTrainerMaterialVersion) -> dict[str, Any]:
    return {
        "version_id": version.version_id,
        "material_id": version.material_id,
        "version_label": version.version_label,
        "title": version.title,
        "file_name": version.file_name,
        "content_type": version.content_type,
        "file_size_bytes": int(version.file_size_bytes),
        "storage_key": version.storage_key,
        "file_hash": version.file_hash,
        "release_notes": version.release_notes,
        "status": version.status,
        "published_at": _datetime_to_json(cast(datetime | None, version.published_at)),
        "published_by": version.published_by,
        "created_by": version.created_by,
        "created_at": _datetime_to_json(cast(datetime | None, version.created_at)),
        "updated_at": _datetime_to_json(cast(datetime | None, version.updated_at)),
    }


def _datetime_to_json(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def normalize_learner_rubric(value: Any) -> dict[str, Any]:
    if isinstance(value, SalesTrainerLearnerRubric):
        return cast(dict[str, Any], value.model_dump())
    if value is None:
        return cast(dict[str, Any], SalesTrainerLearnerRubric().model_dump())
    if not isinstance(value, dict):
        return cast(dict[str, Any], SalesTrainerLearnerRubric().model_dump())
    try:
        return cast(
            dict[str, Any],
            SalesTrainerLearnerRubric.model_validate(value).model_dump(),
        )
    except ValueError:
        return cast(dict[str, Any], SalesTrainerLearnerRubric().model_dump())


def normalize_audio_score_output_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, SalesTrainerAudioScoreOutputSchema):
        return cast(dict[str, Any], value.model_dump(by_alias=True))
    if value is None:
        return cast(
            dict[str, Any], SalesTrainerAudioScoreOutputSchema().model_dump(by_alias=True)
        )
    if not isinstance(value, dict):
        return cast(dict[str, Any], SalesTrainerAudioScoreOutputSchema().model_dump())
    try:
        return cast(
            dict[str, Any],
            SalesTrainerAudioScoreOutputSchema.model_validate(value).model_dump(
                by_alias=True
            ),
        )
    except ValueError:
        return cast(
            dict[str, Any], SalesTrainerAudioScoreOutputSchema().model_dump(by_alias=True)
        )


def _is_object_storage_key(storage_key: str) -> bool:
    return (
        storage_key.startswith("oss://")
        or storage_key.startswith("cos://")
        or storage_key.startswith("sales-trainer/")
    )


def _normalize_object_storage_key(storage_key: str) -> str:
    if storage_key.startswith("oss://"):
        return storage_key.removeprefix("oss://")
    if storage_key.startswith("cos://"):
        return storage_key.removeprefix("cos://")
    return storage_key


def _resolve_object_storage_backend(storage_key: str) -> str:
    if storage_key.startswith("cos://"):
        return "cos"
    if storage_key.startswith("oss://"):
        return "oss"
    return os.getenv("SALES_TRAINER_MATERIAL_STORAGE_BACKEND", "local").strip().lower()


def _generate_object_storage_get_url(storage_key: str) -> str:
    object_key = _normalize_object_storage_key(storage_key)
    backend = _resolve_object_storage_backend(storage_key)
    expires = _resolve_file_url_expires_seconds()
    if backend == "cos":
        return cast(
            str,
            get_cos_signing_service().generate_get_url(object_key, expires=expires),
        )
    return cast(str, get_oss_signing_service().generate_get_url(object_key, expires=expires))


def _resolve_file_url_expires_seconds() -> int:
    raw_value = os.getenv(
        "SALES_TRAINER_MATERIAL_FILE_URL_EXPIRES_SECONDS",
        str(DEFAULT_MATERIAL_FILE_URL_EXPIRES_SECONDS),
    )
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise MaterialServiceError(
            "[MATERIAL_FILE_URL_EXPIRES_CONFIG_INVALID]",
            "训练材料访问链接有效期配置非法。",
            status_code=500,
        ) from exc
    if value <= 0:
        raise MaterialServiceError(
            "[MATERIAL_FILE_URL_EXPIRES_CONFIG_INVALID]",
            "训练材料访问链接有效期配置非法。",
            status_code=500,
        )
    return value

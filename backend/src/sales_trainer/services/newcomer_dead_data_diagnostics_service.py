from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audio_submission_lineage import submission_lineage_fields
from sales_trainer.services.curriculum_practice_adapter import (
    get_learning_content,
    list_learning_chapters,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    SalesTrainerPathConfigError,
    payload_from_revision,
)
from sales_trainer.services.prompt_revision_payloads import PROMPT_RESOURCE_TYPE

IssueSeverity = Literal["info", "warning", "error"]


class NewcomerDeadDataDiagnosticsService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        audio_scan_limit: int = 500,
        material_scan_limit: int = 1000,
    ) -> None:
        self._db = db
        self._audio_scan_limit = audio_scan_limit
        self._material_scan_limit = material_scan_limit
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def build_report(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        referenced: dict[str, set[str]] = {
            "material_ids": set(),
            "material_version_ids": set(),
        }
        scanned_revisions = await self._scan_revisions(
            active=active,
            working=working,
            issues=issues,
            referenced=referenced,
        )
        scanned_audio = await self._scan_audio_submissions(issues)
        referenced["material_version_ids"].update(scanned_audio.pop("material_version_ids"))
        scanned_materials = await self._scan_material_inventory(
            issues,
            referenced_material_ids=referenced["material_ids"],
            referenced_version_ids=referenced["material_version_ids"],
        )
        candidate_actions = _build_candidate_actions(issues)
        manual_decisions = _build_manual_decisions(issues)
        return {
            "mode": "dry_run",
            "mutates_history": False,
            "requires_manual_approval": True,
            "permission": "sales_trainer.manage_modules",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "total": len(issues),
                "error": sum(1 for issue in issues if issue["severity"] == "error"),
                "warning": sum(1 for issue in issues if issue["severity"] == "warning"),
                "info": sum(1 for issue in issues if issue["severity"] == "info"),
            },
            "scanned": {
                "active_revision_id": str(active.revision_id) if active else None,
                "working_revision_id": str(working.revision_id) if working else None,
                "revisions": scanned_revisions,
                "audio_submissions": scanned_audio,
                "materials": scanned_materials,
                "audio_scan_limit": self._audio_scan_limit,
                "material_scan_limit": self._material_scan_limit,
            },
            "issues": issues,
            "candidate_actions": candidate_actions,
            "manual_decisions": manual_decisions,
            "rollback_plan": {
                "required": False,
                "reason": "diagnostics_only_no_mutation",
                "apply_endpoint": None,
                "rollback_endpoint": None,
            },
        }

    async def _scan_revisions(
        self,
        *,
        active: SalesTrainerAssetRevision | None,
        working: SalesTrainerAssetRevision | None,
        issues: list[dict[str, Any]],
        referenced: dict[str, set[str]],
    ) -> list[dict[str, Any]]:
        revisions: list[tuple[str, SalesTrainerAssetRevision]] = []
        if active is not None:
            revisions.append(("active_revision", active))
        else:
            _append_issue(
                issues,
                severity="warning",
                code="ACTIVE_REVISION_MISSING",
                source="path_config",
                revision=None,
                module_key=None,
                resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                resource_id=NEWCOMER_PATH_LOGICAL_ID,
                message="新人训练路径缺少 active revision，learner 路径和 Journey 将 fail-closed。",
                metadata={"legacy_snapshot_only": True},
            )
        if working is not None and (
            active is None or working.revision_id != active.revision_id
        ):
            revisions.append(("working_revision", working))
        for source, revision in revisions:
            try:
                payload = payload_from_revision(revision)
            except SalesTrainerPathConfigError as exc:
                _append_issue(
                    issues,
                    severity="error",
                    code="PATH_REVISION_PAYLOAD_INVALID",
                    source=source,
                    revision=revision,
                    module_key=None,
                    resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                    resource_id=str(revision.revision_id),
                    message=exc.message,
                    metadata={"error_code": exc.code},
                )
                continue
            for module in payload.modules:
                await self._scan_module_refs(
                    source=source,
                    revision=revision,
                    module=module.model_dump(mode="json"),
                    issues=issues,
                    referenced=referenced,
                )
        return [
            {
                "source": source,
                "revision_id": str(revision.revision_id),
                "revision_no": int(revision.revision_no),
                "status": str(revision.status),
            }
            for source, revision in revisions
        ]

    async def _scan_module_refs(
        self,
        *,
        source: str,
        revision: SalesTrainerAssetRevision,
        module: dict[str, Any],
        issues: list[dict[str, Any]],
        referenced: dict[str, set[str]],
    ) -> None:
        module_key = str(module.get("module_key") or "")
        module_type = str(module.get("module_type") or "")
        unit = await self._scan_unit_ref(
            source=source,
            revision=revision,
            module=module,
            issues=issues,
        )
        await self._scan_article_refs(
            source=source,
            revision=revision,
            module=module,
            issues=issues,
        )
        await self._scan_material_refs(
            source=source,
            revision=revision,
            module=module,
            issues=issues,
            referenced=referenced,
        )
        if module_type in {"audio_scoring", "audio_scoring_group"}:
            await self._scan_prompt_ref(
                source=source,
                revision=revision,
                module_key=module_key,
                prompt_id=_module_audio_prompt_id(module, unit),
                issues=issues,
            )
        if module_type == "audio_scoring_group":
            await self._scan_duration_options(
                source=source,
                revision=revision,
                module=module,
                issues=issues,
            )

    async def _scan_unit_ref(
        self,
        *,
        source: str,
        revision: SalesTrainerAssetRevision,
        module: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> SalesTrainerUnit | None:
        unit_id = str(module.get("target_unit_id") or "").strip()
        if not unit_id:
            return None
        unit = await self._db.get(SalesTrainerUnit, unit_id)
        if unit is None or unit.status != "published":
            _append_issue(
                issues,
                severity="error",
                code="TARGET_UNIT_NOT_PUBLISHED",
                source=source,
                revision=revision,
                module_key=str(module.get("module_key") or ""),
                resource_type="sales_trainer_unit",
                resource_id=unit_id,
                message="路径模块绑定的训练单元不存在或未发布。",
                metadata={"expected_status": "published"},
            )
            return unit
        return unit

    async def _scan_article_refs(
        self,
        *,
        source: str,
        revision: SalesTrainerAssetRevision,
        module: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> None:
        if str(module.get("module_type") or "") != "article_exam":
            return
        module_key = str(module.get("module_key") or "")
        content_id = str(module.get("learning_content_id") or "").strip()
        paper_id = str(module.get("exam_paper_id") or "").strip()
        if not content_id:
            _append_issue(
                issues,
                severity="error",
                code="LEARNING_CONTENT_BINDING_MISSING",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="learning_content",
                resource_id=None,
                message="文章考试模块缺少学习内容绑定。",
            )
        else:
            content = await get_learning_content(self._db, content_id)
            if content is None or content.status != "published":
                _append_issue(
                    issues,
                    severity="error",
                    code="LEARNING_CONTENT_NOT_PUBLISHED",
                    source=source,
                    revision=revision,
                    module_key=module_key,
                    resource_type="learning_content",
                    resource_id=content_id,
                    message="文章考试模块绑定的学习内容不存在或未发布。",
                    metadata={"status": getattr(content, "status", None)},
                )
            else:
                chapters = await list_learning_chapters(self._db, content_id)
                if not chapters:
                    _append_issue(
                        issues,
                        severity="warning",
                        code="LEARNING_CONTENT_CHAPTERS_MISSING",
                        source=source,
                        revision=revision,
                        module_key=module_key,
                        resource_type="learning_content",
                        resource_id=content_id,
                        message="文章考试模块绑定的学习内容已发布，但没有章节，学员学习页不可完整回放。",
                    )
        if not paper_id:
            _append_issue(
                issues,
                severity="error",
                code="EXAM_PAPER_BINDING_MISSING",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="sales_trainer_exam_paper",
                resource_id=None,
                message="文章考试模块缺少考试卷绑定。",
            )
            return
        paper = await self._db.get(SalesTrainerExamPaper, paper_id)
        if paper is None or paper.status != "published":
            _append_issue(
                issues,
                severity="error",
                code="EXAM_PAPER_NOT_PUBLISHED",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="sales_trainer_exam_paper",
                resource_id=paper_id,
                message="文章考试模块绑定的考试卷不存在或未发布。",
                metadata={"status": getattr(paper, "status", None)},
            )

    async def _scan_material_refs(
        self,
        *,
        source: str,
        revision: SalesTrainerAssetRevision,
        module: dict[str, Any],
        issues: list[dict[str, Any]],
        referenced: dict[str, set[str]],
    ) -> None:
        module_key = str(module.get("module_key") or "")
        material_id = str(module.get("material_id") or "").strip()
        version_id = str(module.get("material_version_id") or "").strip()
        material = None
        if material_id:
            referenced["material_ids"].add(material_id)
            material = await self._db.get(SalesTrainerMaterial, material_id)
            if material is None or material.status == "archived":
                _append_issue(
                    issues,
                    severity="error",
                    code="MATERIAL_NOT_ACTIVE",
                    source=source,
                    revision=revision,
                    module_key=module_key,
                    resource_type="sales_trainer_material",
                    resource_id=material_id,
                    message="路径模块绑定的材料不存在或已归档。",
                    metadata={"status": getattr(material, "status", None)},
                )
        if not version_id:
            return
        referenced["material_version_ids"].add(version_id)
        version = await self._db.get(SalesTrainerMaterialVersion, version_id)
        if version is None or version.status != "published":
            _append_issue(
                issues,
                severity="error",
                code="MATERIAL_VERSION_NOT_PUBLISHED",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="sales_trainer_material_version",
                resource_id=version_id,
                message="路径模块绑定的材料版本不存在或未发布。",
                metadata={"status": getattr(version, "status", None)},
            )
            return
        if material_id and str(version.material_id) != material_id:
            _append_issue(
                issues,
                severity="error",
                code="MATERIAL_VERSION_MISMATCH",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="sales_trainer_material_version",
                resource_id=version_id,
                message="路径模块绑定的材料版本不属于绑定材料。",
                metadata={"material_id": material_id, "version_material_id": version.material_id},
            )

    async def _scan_prompt_ref(
        self,
        *,
        source: str,
        revision: SalesTrainerAssetRevision,
        module_key: str,
        prompt_id: str | None,
        issues: list[dict[str, Any]],
    ) -> None:
        if not prompt_id:
            _append_issue(
                issues,
                severity="error",
                code="AUDIO_SCORING_PROMPT_MISSING",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="sales_trainer_audio_score_prompt",
                resource_id=None,
                message="音频训练模块缺少录音评分 Prompt 绑定。",
            )
            return
        prompt = await self._db.get(SalesTrainerAudioScorePrompt, prompt_id)
        if prompt is None or prompt.status != "published":
            _append_issue(
                issues,
                severity="error",
                code="AUDIO_SCORING_PROMPT_NOT_PUBLISHED",
                source=source,
                revision=revision,
                module_key=module_key,
                resource_type="sales_trainer_audio_score_prompt",
                resource_id=prompt_id,
                message="音频训练模块绑定的录音评分 Prompt 不存在或未发布。",
                metadata={"status": getattr(prompt, "status", None)},
            )

    async def _scan_duration_options(
        self,
        *,
        source: str,
        revision: SalesTrainerAssetRevision,
        module: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> None:
        for option in module.get("duration_options") or []:
            if not isinstance(option, dict):
                continue
            target_unit_id = str(option.get("target_unit_id") or "").strip()
            if not target_unit_id:
                continue
            unit = await self._db.get(SalesTrainerUnit, target_unit_id)
            await self._scan_prompt_ref(
                source=source,
                revision=revision,
                module_key=str(module.get("module_key") or ""),
                prompt_id=_unit_audio_prompt_id(unit),
                issues=issues,
            )

    async def _scan_audio_submissions(
        self,
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total = await self._db.scalar(select(func.count()).select_from(SalesTrainerAudioSubmission))
        result = await self._db.execute(
            select(SalesTrainerAudioSubmission)
            .order_by(SalesTrainerAudioSubmission.created_at.desc())
            .limit(self._audio_scan_limit)
        )
        submissions = list(result.scalars().all())
        referenced_version_ids: set[str] = set()
        for submission in submissions:
            snapshot_version_ids = _material_version_ids_from_snapshot(
                submission.material_snapshot
            )
            referenced_version_ids.update(snapshot_version_ids)
            if submission.confirmed_material_version_id:
                referenced_version_ids.add(str(submission.confirmed_material_version_id))
            score_snapshot = (
                submission.score_scheme_snapshot
                if isinstance(submission.score_scheme_snapshot, dict)
                else None
            )
            if score_snapshot is None:
                _append_issue(
                    issues,
                    severity="warning",
                    code="AUDIO_SCORE_SCHEME_SNAPSHOT_MISSING",
                    source="audio_submission",
                    revision=None,
                    module_key=_snapshot_module_key(submission.task_brief_snapshot),
                    resource_type="sales_trainer_audio_submission",
                    resource_id=str(submission.submission_id),
                    message="音频提交缺少评分方案快照，历史解释和重评只能按 legacy 配置回退。",
                    metadata={
                        "legacy_snapshot_only": True,
                        "regrade_unavailable": True,
                    },
                )
            elif not _has_complete_prompt_snapshot(score_snapshot):
                _append_issue(
                    issues,
                    severity="warning",
                    code="AUDIO_PROMPT_SNAPSHOT_MISSING",
                    source="audio_submission",
                    revision=None,
                    module_key=_snapshot_module_key(submission.task_brief_snapshot),
                    resource_type="sales_trainer_audio_submission",
                    resource_id=str(submission.submission_id),
                    message="音频提交缺少完整评分 Prompt 快照，历史重评只能按 legacy 发布 Prompt 回退。",
                    metadata={
                        "prompt_id": score_snapshot.get("prompt_id"),
                        "legacy_snapshot_only": True,
                        "regrade_unavailable": True,
                    },
                )
            if str(submission.status) == "scored":
                latest_score = await self._latest_score(str(submission.submission_id))
                if latest_score is None:
                    _append_issue(
                        issues,
                        severity="error",
                        code="AUDIO_SCORE_RESULT_MISSING",
                        source="audio_submission",
                        revision=None,
                        module_key=_snapshot_module_key(submission.task_brief_snapshot),
                        resource_type="sales_trainer_audio_submission",
                        resource_id=str(submission.submission_id),
                        message="音频提交状态为 scored，但缺少评分结果。",
                        metadata={"regrade_unavailable": True},
                    )
                elif not str(latest_score.transcript_snapshot or "").strip():
                    _append_issue(
                        issues,
                        severity="warning",
                        code="AUDIO_SCORE_TRANSCRIPT_SNAPSHOT_MISSING",
                        source="audio_submission",
                        revision=None,
                        module_key=_snapshot_module_key(submission.task_brief_snapshot),
                        resource_type="sales_trainer_audio_submission",
                        resource_id=str(submission.submission_id),
                        message="音频评分结果缺少 transcript_snapshot，历史重评不可用。",
                        metadata={"regrade_unavailable": True},
                    )
            await self._scan_audio_lineage(submission, issues)
            await self._scan_audio_prompt_revision(submission, score_snapshot, issues)
            if submission.confirmed_material_version_id and not isinstance(
                submission.material_snapshot,
                dict,
            ):
                _append_issue(
                    issues,
                    severity="warning",
                    code="MATERIAL_SNAPSHOT_MISSING",
                    source="audio_submission",
                    revision=None,
                    module_key=_snapshot_module_key(submission.task_brief_snapshot),
                    resource_type="sales_trainer_audio_submission",
                    resource_id=str(submission.submission_id),
                    message="音频提交引用了材料版本，但缺少材料快照，历史回放只能依赖冻结 version_id。",
                    metadata={
                        "confirmed_material_version_id": submission.confirmed_material_version_id,
                        "legacy_snapshot_only": True,
                    },
                )
            if not submission.confirmed_material_version_id and snapshot_version_ids:
                _append_issue(
                    issues,
                    severity="warning",
                    code="HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE",
                    source="audio_submission",
                    revision=None,
                    module_key=_snapshot_module_key(submission.task_brief_snapshot),
                    resource_type="sales_trainer_audio_submission",
                    resource_id=str(submission.submission_id),
                    message=(
                        "音频提交材料快照包含材料版本，但缺少 confirmed_material_version_id，"
                        "历史材料文件回放无法完成对象级引用确认。"
                    ),
                    metadata={
                        "material_version_ids": sorted(snapshot_version_ids),
                        "legacy_snapshot_only": True,
                    },
                )
            await self._scan_historical_material_file(submission, issues)
        return {
            "scanned": len(submissions),
            "total": int(total or 0),
            "material_version_ids": referenced_version_ids,
        }

    async def _scan_historical_material_file(
        self,
        submission: SalesTrainerAudioSubmission,
        issues: list[dict[str, Any]],
    ) -> None:
        version_id = str(submission.confirmed_material_version_id or "").strip()
        if not version_id:
            return
        version = await self._db.get(SalesTrainerMaterialVersion, version_id)
        if version is None or str(version.status) not in {"published", "archived"}:
            return
        storage_key = str(version.storage_key or "").strip()
        if not storage_key or _is_object_storage_key(storage_key):
            return
        path = Path(storage_key)
        if path.exists() and path.is_file():
            return
        _append_issue(
            issues,
            severity="warning",
            code="HISTORICAL_MATERIAL_REPLAY_MISSING_FILE",
            source="audio_submission",
            revision=None,
            module_key=_snapshot_module_key(submission.task_brief_snapshot),
            resource_type="sales_trainer_audio_submission",
            resource_id=str(submission.submission_id),
            message="音频提交引用的历史材料版本文件不存在，历史材料回放将 fail-closed。",
            metadata={
                "confirmed_material_version_id": version_id,
                "storage_backend": "local",
                "legacy_snapshot_only": True,
            },
        )

    async def _scan_audio_lineage(
        self,
        submission: SalesTrainerAudioSubmission,
        issues: list[dict[str, Any]],
    ) -> None:
        lineage = submission_lineage_fields(
            submission.task_brief_snapshot
            if isinstance(submission.task_brief_snapshot, dict)
            else None
        )
        module_key = lineage["module_key"] or _snapshot_module_key(
            submission.task_brief_snapshot
        )
        if (
            lineage["legacy_snapshot_only"]
            or not lineage["path_revision_id"]
            or not lineage["module_key"]
        ):
            _append_issue(
                issues,
                severity="warning",
                code="AUDIO_SUBMISSION_LINEAGE_MISSING",
                source="audio_submission",
                revision=None,
                module_key=module_key,
                resource_type="sales_trainer_audio_submission",
                resource_id=str(submission.submission_id),
                message=(
                    "音频提交缺少完整 active path lineage，历史 Journey 回放只能按 legacy "
                    "只读证据解释。"
                ),
                metadata={
                    "path_revision_id": lineage["path_revision_id"],
                    "module_key": lineage["module_key"],
                    "legacy_snapshot_only": True,
                    "regrade_unavailable": True,
                },
            )
            return
        revision = await self._revisions.revision_by_id(lineage["path_revision_id"])
        if revision is None:
            _append_issue(
                issues,
                severity="error",
                code="AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND",
                source="audio_submission",
                revision=None,
                module_key=module_key,
                resource_type="sales_trainer_audio_submission",
                resource_id=str(submission.submission_id),
                message="音频提交冻结的 path_revision_id 不存在，历史 Journey 回放无法证明真源。",
                metadata={
                    "path_revision_id": lineage["path_revision_id"],
                    "legacy_snapshot_only": True,
                    "regrade_unavailable": True,
                },
            )

    async def _scan_audio_prompt_revision(
        self,
        submission: SalesTrainerAudioSubmission,
        score_snapshot: dict[str, Any] | None,
        issues: list[dict[str, Any]],
    ) -> None:
        if score_snapshot is None:
            return
        prompt_snapshot = score_snapshot.get("prompt_snapshot")
        if not isinstance(prompt_snapshot, dict):
            return
        prompt_id = str(
            prompt_snapshot.get("prompt_id") or score_snapshot.get("prompt_id") or ""
        ).strip()
        revision_id = str(prompt_snapshot.get("revision_id") or "").strip()
        if not prompt_id and not revision_id:
            return
        module_key = _snapshot_module_key(submission.task_brief_snapshot)
        if not revision_id:
            _append_issue(
                issues,
                severity="warning",
                code="AUDIO_SCORE_PROMPT_REVISION_MISSING",
                source="audio_submission",
                revision=None,
                module_key=module_key,
                resource_type="sales_trainer_audio_submission",
                resource_id=str(submission.submission_id),
                message=(
                    "音频提交评分快照缺少 Prompt revision_id，历史重评无法指定可复盘的"
                    "发布修订。"
                ),
                metadata={
                    "prompt_id": prompt_id or None,
                    "revision_id": None,
                    "legacy_snapshot_only": True,
                    "regrade_unavailable": True,
                },
            )
            return
        revision = await self._revisions.revision_by_id(revision_id)
        if (
            revision is None
            or revision.resource_type != PROMPT_RESOURCE_TYPE
            or (prompt_id and revision.logical_id != prompt_id)
        ):
            _append_issue(
                issues,
                severity="error",
                code="AUDIO_SCORE_PROMPT_REVISION_NOT_FOUND",
                source="audio_submission",
                revision=None,
                module_key=module_key,
                resource_type="sales_trainer_audio_submission",
                resource_id=str(submission.submission_id),
                message="音频提交评分快照引用的 Prompt revision 不存在或不属于该 Prompt。",
                metadata={
                    "prompt_id": prompt_id or None,
                    "revision_id": revision_id,
                    "legacy_snapshot_only": True,
                    "regrade_unavailable": True,
                },
            )

    async def _latest_score(
        self,
        submission_id: str,
    ) -> SalesTrainerAudioScoreResult | None:
        result = await self._db.execute(
            select(SalesTrainerAudioScoreResult)
            .where(SalesTrainerAudioScoreResult.submission_id == submission_id)
            .order_by(SalesTrainerAudioScoreResult.created_at.desc())
        )
        return result.scalars().first()

    async def _scan_material_inventory(
        self,
        issues: list[dict[str, Any]],
        *,
        referenced_material_ids: set[str],
        referenced_version_ids: set[str],
    ) -> dict[str, int]:
        material_total = await self._db.scalar(
            select(func.count()).select_from(SalesTrainerMaterial)
        )
        version_total = await self._db.scalar(
            select(func.count()).select_from(SalesTrainerMaterialVersion)
        )
        materials_result = await self._db.execute(
            select(SalesTrainerMaterial)
            .order_by(SalesTrainerMaterial.updated_at.desc())
            .limit(self._material_scan_limit)
        )
        materials = list(materials_result.scalars().all())
        versions_result = await self._db.execute(
            select(SalesTrainerMaterialVersion)
            .order_by(SalesTrainerMaterialVersion.updated_at.desc())
            .limit(self._material_scan_limit)
        )
        versions = list(versions_result.scalars().all())
        versions_by_id = {str(version.version_id): version for version in versions}
        referenced_material_ids_from_versions = await self._material_ids_for_versions(
            referenced_version_ids=referenced_version_ids,
            versions_by_id=versions_by_id,
        )
        for material in materials:
            material_id = str(material.material_id)
            if str(material.status) == "published":
                current_version_id = str(material.current_version_id or "").strip()
                current_version = versions_by_id.get(current_version_id)
                if current_version is None and current_version_id:
                    current_version = await self._db.get(
                        SalesTrainerMaterialVersion,
                        current_version_id,
                    )
                if not current_version_id or current_version is None:
                    _append_issue(
                        issues,
                        severity="error",
                        code="MATERIAL_CURRENT_VERSION_MISSING",
                        source="material_inventory",
                        revision=None,
                        module_key=None,
                        resource_type="sales_trainer_material",
                        resource_id=material_id,
                        message="已发布材料缺少当前版本，学员无法获得稳定训练资产。",
                    )
                elif str(current_version.status) != "published":
                    _append_issue(
                        issues,
                        severity="error",
                        code="MATERIAL_CURRENT_VERSION_NOT_PUBLISHED",
                        source="material_inventory",
                        revision=None,
                        module_key=None,
                        resource_type="sales_trainer_material_version",
                        resource_id=current_version_id,
                        message="已发布材料的当前版本不是 published 状态。",
                        metadata={"status": current_version.status},
                    )
            if (
                material_id not in referenced_material_ids
                and material_id not in referenced_material_ids_from_versions
                and not any(
                    str(version.material_id) == material_id
                    and str(version.version_id) in referenced_version_ids
                    for version in versions
                )
            ):
                _append_issue(
                    issues,
                    severity="info",
                    code="ORPHAN_MATERIAL",
                    source="material_inventory",
                    revision=None,
                    module_key=None,
                    resource_type="sales_trainer_material",
                    resource_id=material_id,
                    message="材料未被 active/working 路径或已扫描历史提交引用，可作为人工清理候选。",
                )
        for version in versions:
            version_id = str(version.version_id)
            linked_material: SalesTrainerMaterial | None = await self._db.get(
                SalesTrainerMaterial,
                version.material_id,
            )
            if (
                version_id not in referenced_version_ids
                and (
                    linked_material is None
                    or str(linked_material.current_version_id or "") != version_id
                )
            ):
                _append_issue(
                    issues,
                    severity="info",
                    code="ORPHAN_MATERIAL_VERSION",
                    source="material_inventory",
                    revision=None,
                    module_key=None,
                    resource_type="sales_trainer_material_version",
                    resource_id=version_id,
                    message="材料版本不是当前版本，也未被 active/working 路径或已扫描历史提交引用，可作为人工清理候选。",
                    metadata={"status": version.status},
                )
        return {
            "materials": len(materials),
            "versions": len(versions),
            "total_materials": int(material_total or 0),
            "total_versions": int(version_total or 0),
            "limit": self._material_scan_limit,
            "truncated": bool(
                int(material_total or 0) > len(materials)
                or int(version_total or 0) > len(versions)
            ),
        }

    async def _material_ids_for_versions(
        self,
        *,
        referenced_version_ids: set[str],
        versions_by_id: dict[str, SalesTrainerMaterialVersion],
    ) -> set[str]:
        material_ids = {
            str(version.material_id)
            for version_id, version in versions_by_id.items()
            if version_id in referenced_version_ids
        }
        missing_version_ids = [
            version_id
            for version_id in referenced_version_ids
            if version_id not in versions_by_id
        ]
        if not missing_version_ids:
            return material_ids
        result = await self._db.execute(
            select(SalesTrainerMaterialVersion).where(
                SalesTrainerMaterialVersion.version_id.in_(missing_version_ids)
            )
        )
        for version in result.scalars().all():
            material_ids.add(str(version.material_id))
        return material_ids


def _append_issue(
    issues: list[dict[str, Any]],
    *,
    severity: IssueSeverity,
    code: str,
    source: str,
    revision: SalesTrainerAssetRevision | None,
    module_key: str | None,
    resource_type: str,
    resource_id: str | None,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    issues.append(
        {
            "severity": severity,
            "code": code,
            "source": source,
            "revision_id": str(revision.revision_id) if revision else None,
            "revision_no": int(revision.revision_no) if revision else None,
            "module_key": module_key,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "message": message,
            "metadata": metadata or {},
        }
    )


def _build_candidate_actions(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for issue in issues:
        action, reason = _candidate_action_for_issue(issue)
        actions.append(
            {
                "issue_code": issue["code"],
                "source": issue["source"],
                "resource_type": issue["resource_type"],
                "resource_id": issue["resource_id"],
                "action": action,
                "reason": reason,
                "mutates_history": False,
                "safe_to_apply_automatically": False,
                "requires_manual_approval": True,
            }
        )
    return actions


def _candidate_action_for_issue(issue: dict[str, Any]) -> tuple[str, str]:
    code = str(issue["code"])
    if code in {"ACTIVE_REVISION_MISSING", "PATH_REVISION_PAYLOAD_INVALID"}:
        return (
            "repair_path_revision_before_publish",
            "路径 revision 是 learner 真源，必须先修复或重新发布，不能从 catalog fallback。",
        )
    if code in {
        "TARGET_UNIT_NOT_PUBLISHED",
        "LEARNING_CONTENT_BINDING_MISSING",
        "LEARNING_CONTENT_NOT_PUBLISHED",
        "LEARNING_CONTENT_CHAPTERS_MISSING",
        "EXAM_PAPER_BINDING_MISSING",
        "EXAM_PAPER_NOT_PUBLISHED",
        "MATERIAL_NOT_ACTIVE",
        "MATERIAL_VERSION_NOT_PUBLISHED",
        "MATERIAL_VERSION_MISMATCH",
        "AUDIO_SCORING_PROMPT_MISSING",
        "AUDIO_SCORING_PROMPT_NOT_PUBLISHED",
    }:
        return (
            "restore_or_replace_asset_reference",
            "先恢复已发布资产或发布新的 revision 绑定，不得修改历史训练记录。",
        )
    if code in {
        "AUDIO_PROMPT_SNAPSHOT_MISSING",
        "AUDIO_SCORE_SCHEME_SNAPSHOT_MISSING",
        "AUDIO_SCORE_RESULT_MISSING",
        "AUDIO_SCORE_TRANSCRIPT_SNAPSHOT_MISSING",
        "AUDIO_SCORE_PROMPT_REVISION_MISSING",
        "AUDIO_SCORE_PROMPT_REVISION_NOT_FOUND",
        "AUDIO_SUBMISSION_LINEAGE_MISSING",
        "AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND",
        "HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE",
        "HISTORICAL_MATERIAL_REPLAY_MISSING_FILE",
        "MATERIAL_SNAPSHOT_MISSING",
    }:
        return (
            "preserve_read_only_replay_and_mark_legacy",
            "历史证据不足时只允许只读回放或 legacy 标记，不允许自动重评或补写依据。",
        )
    if code in {
        "MATERIAL_CURRENT_VERSION_MISSING",
        "MATERIAL_CURRENT_VERSION_NOT_PUBLISHED",
    }:
        return (
            "repair_material_inventory",
            "材料当前版本会影响后续训练资产选择，需人工确认后修复材料配置。",
        )
    if code in {"ORPHAN_MATERIAL", "ORPHAN_MATERIAL_VERSION"}:
        return (
            "review_archive_candidate",
            "孤儿资产只能作为清理候选，归档前必须确认未被未扫描历史记录引用。",
        )
    return (
        "manual_review_required",
        "该问题没有自动修复策略，必须人工复核后再决定是否写入。",
    )


def _build_manual_decisions(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    issue_codes = {str(issue["code"]) for issue in issues}
    if any(_is_legacy_history_issue(issue) for issue in issues):
        decisions.append(
            {
                "decision_key": "legacy_history_backfill_policy",
                "owner": "product_ops",
                "required_before": "production_backfill",
                "issue_codes": sorted(
                    code
                    for code in issue_codes
                    if code.startswith("AUDIO_")
                    or code.startswith("HISTORICAL_MATERIAL_REPLAY_")
                ),
                "reason": "历史录音、Prompt、材料快照缺口无法由代码可靠推断，需确认哪些记录可回填，哪些只能 legacy 只读。",
            }
        )
    if issue_codes.intersection({"ORPHAN_MATERIAL", "ORPHAN_MATERIAL_VERSION"}):
        decisions.append(
            {
                "decision_key": "orphan_asset_retention_policy",
                "owner": "product_ops",
                "required_before": "archive_or_delete_assets",
                "issue_codes": sorted(
                    code
                    for code in issue_codes
                    if code in {"ORPHAN_MATERIAL", "ORPHAN_MATERIAL_VERSION"}
                ),
                "reason": "诊断只扫描 active/working revision 和有限历史提交，归档前需确认保留周期和完整历史引用范围。",
            }
        )
    if any(issue["severity"] == "error" for issue in issues):
        decisions.append(
            {
                "decision_key": "active_path_repair_policy",
                "owner": "training_admin",
                "required_before": "next_publish_or_learner_release",
                "issue_codes": sorted(
                    code
                    for code in issue_codes
                    if code
                    not in {
                        "ORPHAN_MATERIAL",
                        "ORPHAN_MATERIAL_VERSION",
                    }
                ),
                "reason": "error 级问题会导致 learner fail-closed 或训练资产不可用，必须发布修复后的 active revision。",
            }
        )
    return decisions


def _is_legacy_history_issue(issue: dict[str, Any]) -> bool:
    metadata = issue.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return bool(
        issue.get("source") == "audio_submission"
        or metadata.get("legacy_snapshot_only")
        or metadata.get("regrade_unavailable")
    )


def _module_audio_prompt_id(
    module: dict[str, Any],
    unit: SalesTrainerUnit | None,
) -> str | None:
    value = module.get("scoring_prompt_id")
    if value:
        return str(value)
    return _unit_audio_prompt_id(unit)


def _unit_audio_prompt_id(unit: SalesTrainerUnit | None) -> str | None:
    if unit is None or not isinstance(unit.config, dict):
        return None
    audio = unit.config.get("audio")
    if not isinstance(audio, dict):
        return None
    value = audio.get("scoring_prompt_id")
    return str(value) if value else None


def _snapshot_module_key(snapshot: Any) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get("module_key")
    return str(value) if value else None


def _material_version_ids_from_snapshot(snapshot: Any) -> set[str]:
    if not isinstance(snapshot, dict):
        return set()
    version_ids: set[str] = set()
    confirmed = snapshot.get("confirmed_material_version_id")
    if isinstance(confirmed, str) and confirmed.strip():
        version_ids.add(confirmed.strip())
    top_level_version_id = snapshot.get("version_id")
    if isinstance(top_level_version_id, str) and top_level_version_id.strip():
        version_ids.add(top_level_version_id.strip())
    for item in snapshot.get("items") or []:
        if not isinstance(item, dict):
            continue
        current_version = item.get("current_version")
        if not isinstance(current_version, dict):
            continue
        version_id = current_version.get("version_id")
        if isinstance(version_id, str) and version_id.strip():
            version_ids.add(version_id.strip())
    return version_ids


def _is_object_storage_key(storage_key: str) -> bool:
    return (
        storage_key.startswith("oss://")
        or storage_key.startswith("cos://")
        or storage_key.startswith("sales-trainer/")
    )


def _has_complete_prompt_snapshot(score_snapshot: dict[str, Any]) -> bool:
    prompt_snapshot = score_snapshot.get("prompt_snapshot")
    if not isinstance(prompt_snapshot, dict):
        return False
    return all(
        str(prompt_snapshot.get(field) or "").strip()
        for field in ("prompt_id", "system_prompt", "scoring_template")
    )

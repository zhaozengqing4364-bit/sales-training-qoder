from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.cos.signing import (
    CosConfigError,
    get_cos_signing_service,
)
from common.db.models import User
from common.oss.signing import (
    OssConfigError,
    get_oss_signing_service,
)
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioTranscript,
    SalesTrainerUnit,
)
from sales_trainer.rules import resolve_audio_pass_threshold
from sales_trainer.schemas import AudioSubmissionCreate
from sales_trainer.services.audio_submission_lineage import (
    freeze_submission_context,
    submission_lineage_fields,
)
from sales_trainer.services.deucate_scoring_service import DeucateScoringService
from sales_trainer.services.effective_audio_training_config import (
    EffectiveAudioTrainingConfigResolver,
)
from sales_trainer.services.material_service import (
    MaterialServiceError,
    SalesTrainerMaterialService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_attempt_context_service import (
    PathRuntimeContextPayload,
)
from sales_trainer.services.transcription_service import TranscriptionService

DEFAULT_ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/mp4",
    "audio/x-m4a",
}
DEFAULT_MAX_AUDIO_MB = 200
DEFAULT_AUDIO_FILE_URL_EXPIRES_SECONDS = 3600


@dataclass(frozen=True)
class AudioFileAccess:
    mode: str
    path: Path | None
    redirect_url: str | None
    media_type: str
    filename: str


class AudioSubmissionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AudioSubmissionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        transcription_service: TranscriptionService | None = None,
        scoring_service: DeucateScoringService | None = None,
    ) -> None:
        self._db = db
        self._transcription = transcription_service or TranscriptionService()
        self._scoring = scoring_service or DeucateScoringService()
        self._logs = OperationLogService(db)
        self._materials = SalesTrainerMaterialService(db)

    def generate_upload_url(
        self,
        *,
        filename: str,
        content_type: str,
        actor: User,
    ) -> dict[str, Any]:
        self._validate_content_type(content_type)
        object_key = self._build_storage_key(str(actor.user_id), filename)
        backend = os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local").lower()
        if backend == "oss":
            try:
                signer = get_oss_signing_service()
            except OssConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[OSS_NOT_CONFIGURED]",
                    str(exc),
                    status_code=503,
                ) from exc
            presigned = signer.generate_put_url(object_key, content_type=content_type)
            return {
                "upload_url": presigned.url,
                "storage_key": f"oss://{presigned.object_key}",
                "expires_at": presigned.expires_at,
                "content_type": content_type,
                "storage_backend": "oss",
            }
        if backend == "cos":
            try:
                signer = get_cos_signing_service()
            except CosConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[COS_NOT_CONFIGURED]",
                    str(exc),
                    status_code=503,
                ) from exc
            presigned = signer.generate_put_url(object_key, content_type=content_type)
            return {
                "upload_url": presigned.url,
                "storage_key": f"cos://{presigned.object_key}",
                "expires_at": presigned.expires_at,
                "content_type": content_type,
                "storage_backend": "cos",
            }

        expires_at = (datetime.now(UTC) + timedelta(minutes=15)).isoformat()
        return {
            "upload_url": f"local://{object_key}",
            "storage_key": object_key,
            "expires_at": expires_at,
            "content_type": content_type,
            "storage_backend": "local",
        }

    async def save_uploaded_file(
        self,
        *,
        file: UploadFile,
        unit_id: str | None,
        purpose: str,
        source_page: str | None,
        confirmed_material_version_id: str | None,
        actor: User,
        auto_process: bool = True,
    ) -> SalesTrainerAudioSubmission:
        content_type = file.content_type or "application/octet-stream"
        self._validate_content_type(content_type)
        raw = await file.read()
        if not raw:
            raise AudioSubmissionServiceError(
                "[AUDIO_FILE_EMPTY]",
                "上传音频不能为空。",
                status_code=422,
            )
        self._validate_file_size(len(raw))

        storage_key = self._store_uploaded_bytes(
            user_id=str(actor.user_id),
            filename=file.filename or "audio",
            content_type=content_type,
            raw=raw,
        )
        file_hash = sha256(raw).hexdigest()

        submission = await self.create_submission(
            AudioSubmissionCreate(
                unit_id=unit_id,
                purpose=purpose,
                original_filename=file.filename or Path(storage_key).name,
                content_type=content_type,
                size_bytes=len(raw),
                storage_key=storage_key,
                file_hash=file_hash,
                source_page=source_page,
                confirmed_material_version_id=confirmed_material_version_id,
                auto_process=auto_process,
            ),
            actor=actor,
        )
        return submission

    async def create_submission(
        self,
        payload: AudioSubmissionCreate,
        *,
        actor: User,
    ) -> SalesTrainerAudioSubmission:
        self._validate_content_type(payload.content_type)
        self._validate_file_size(payload.size_bytes)
        unit = None
        snapshots: dict[str, Any] = {}
        submission_context: PathRuntimeContextPayload | None = None
        if payload.unit_id is not None:
            unit = await self._db.get(SalesTrainerUnit, payload.unit_id)
            if unit is None or unit.status != "published":
                raise AudioSubmissionServiceError(
                    "[SALES_TRAINER_UNIT_NOT_FOUND]",
                    "训练单元不存在或未发布。",
                    status_code=404,
                )
            if unit.unit_type != "audio_scoring":
                raise AudioSubmissionServiceError(
                    "[SALES_TRAINER_UNIT_TYPE_MISMATCH]",
                    "该训练单元不是音频评分模块。",
                )
            effective = await EffectiveAudioTrainingConfigResolver(
                self._db
            ).resolve_for_unit(unit)
            try:
                self._require_material_binding_for_ppt(
                    unit,
                    payload.purpose,
                    config_override=effective.config,
                )
                snapshots = await self._materials.freeze_submission_snapshots(
                    unit,
                    confirmed_material_version_id=payload.confirmed_material_version_id,
                    config_override=effective.config,
                )
            except MaterialServiceError as exc:
                raise AudioSubmissionServiceError(
                    exc.code,
                    exc.message,
                    status_code=exc.status_code,
                ) from exc
            submission_context = cast(PathRuntimeContextPayload, effective.context)
            task_brief_snapshot = snapshots.get("task_brief_snapshot")
            snapshots["task_brief_snapshot"] = freeze_submission_context(
                task_brief_snapshot if isinstance(task_brief_snapshot, dict) else None,
                submission_context,
            )
        self._validate_direct_object_if_needed(
            payload.storage_key,
            expected_size_bytes=payload.size_bytes,
        )

        submission = SalesTrainerAudioSubmission(
            unit_id=payload.unit_id,
            user_id=str(actor.user_id),
            purpose=payload.purpose,
            original_filename=payload.original_filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            storage_key=payload.storage_key,
            file_hash=payload.file_hash,
            duration_seconds=payload.duration_seconds,
            source_page=payload.source_page,
            confirmed_material_version_id=payload.confirmed_material_version_id,
            confirmed_material_at=datetime.now(UTC)
            if payload.confirmed_material_version_id
            else None,
            material_snapshot=snapshots.get("material_snapshot"),
            score_scheme_snapshot=snapshots.get("score_scheme_snapshot"),
            task_brief_snapshot=snapshots.get("task_brief_snapshot"),
            status="uploaded",
        )
        self._db.add(submission)
        await self._db.flush()
        await self._logs.record(
            actor=actor,
            action="audio_uploaded",
            target_type="sales_trainer_audio_submission",
            target_id=submission.submission_id,
            metadata={
                "unit_id": payload.unit_id,
                "purpose": payload.purpose,
                "content_type": payload.content_type,
                "size_bytes": payload.size_bytes,
                "source_page": payload.source_page,
                "confirmed_material_version_id": payload.confirmed_material_version_id,
                "submission_context": submission_context,
            },
        )
        await self._db.commit()
        await self._db.refresh(submission)
        if payload.auto_process:
            await self.process_submission(submission.submission_id, actor=actor)
            refreshed = await self._db.get(
                SalesTrainerAudioSubmission, submission.submission_id
            )
            if refreshed is not None:
                return refreshed
        return submission

    async def process_submission(
        self,
        submission_id: str,
        *,
        actor: User | None,
    ) -> SalesTrainerAudioSubmission:
        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            raise AudioSubmissionServiceError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "音频提交不存在。",
                status_code=404,
            )
        await self._transcribe(submission, actor=actor)
        await self._score(submission, actor=actor)
        await self._db.commit()
        await self._db.refresh(submission)
        return submission

    async def retry_transcription(
        self, submission_id: str, *, actor: User
    ) -> SalesTrainerAudioSubmission:
        return await self.transcribe_submission(submission_id, actor=actor)

    async def transcribe_submission(
        self, submission_id: str, *, actor: User | None
    ) -> SalesTrainerAudioSubmission:
        submission = await self._require_submission(submission_id)
        await self._transcribe(submission, actor=actor)
        await self._db.commit()
        await self._db.refresh(submission)
        return submission

    async def retry_scoring(
        self, submission_id: str, *, actor: User
    ) -> SalesTrainerAudioSubmission:
        submission = await self._require_submission(submission_id)
        transcript = await self._get_transcript(submission.submission_id)
        if transcript is None or not transcript.transcript_text.strip():
            raise AudioSubmissionServiceError(
                "[AUDIO_TRANSCRIPT_REQUIRED]",
                "音频尚无可用于评分的转写结果，请先重试转写。",
                409,
            )
        submission.status = "transcribed"
        submission.error_code = None
        submission.error_message = None
        await self._db.flush()
        return await self.score_submission(submission_id, actor=actor)

    async def score_submission(
        self, submission_id: str, *, actor: User | None
    ) -> SalesTrainerAudioSubmission:
        submission = await self._require_submission(submission_id)
        await self._score(submission, actor=actor)
        await self._db.commit()
        await self._db.refresh(submission)
        return submission

    async def get_submission(
        self,
        submission_id: str,
        *,
        actor: User,
        allow_admin: bool = False,
        team_department: str | None = None,
    ) -> SalesTrainerAudioSubmission | None:
        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            return None
        if allow_admin:
            return submission
        if team_department is not None and await self._submission_in_department(
            submission,
            team_department,
        ):
            return submission
        if submission.user_id != str(actor.user_id):
            raise AudioSubmissionServiceError("[ACCESS_DENIED]", "无权查看该音频。", 403)
        return submission

    async def resolve_audio_file_access(
        self,
        submission_id: str,
        *,
        actor: User,
        allow_admin: bool = False,
        team_department: str | None = None,
    ) -> AudioFileAccess:
        submission = await self.get_submission(
            submission_id,
            actor=actor,
            allow_admin=allow_admin,
            team_department=team_department,
        )
        if submission is None:
            raise AudioSubmissionServiceError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "音频提交不存在。",
                status_code=404,
            )

        storage_key = str(submission.storage_key or "")
        local_path = Path(storage_key)
        if local_path.exists():
            resolved_path = local_path.resolve()
            storage_root = Path(
                os.getenv(
                    "SALES_TRAINER_AUDIO_STORAGE_PATH",
                    "./data/sales_trainer_audio",
                )
            ).resolve()
            if storage_root not in (resolved_path, *resolved_path.parents):
                raise AudioSubmissionServiceError(
                    "[AUDIO_FILE_ACCESS_DENIED]",
                    "音频文件不在允许的存储目录内。",
                    status_code=403,
                )
            if not resolved_path.is_file():
                raise AudioSubmissionServiceError(
                    "[AUDIO_FILE_NOT_FOUND]",
                    "音频文件不存在。",
                    status_code=404,
                )
            return AudioFileAccess(
                mode="local",
                path=resolved_path,
                redirect_url=None,
                media_type=str(submission.content_type or "application/octet-stream"),
                filename=str(submission.original_filename or resolved_path.name),
            )

        if _is_object_storage_key(storage_key):
            try:
                signed_url = _generate_object_storage_get_url(storage_key)
            except OssConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[OSS_NOT_CONFIGURED]",
                    str(exc),
                    status_code=503,
                ) from exc
            except CosConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[COS_NOT_CONFIGURED]",
                    str(exc),
                    status_code=503,
                ) from exc
            return AudioFileAccess(
                mode="redirect",
                path=None,
                redirect_url=signed_url,
                media_type=str(submission.content_type or "application/octet-stream"),
                filename=str(submission.original_filename or "audio"),
            )

        raise AudioSubmissionServiceError(
            "[AUDIO_FILE_NOT_FOUND]",
            "音频文件不存在。",
            status_code=404,
        )

    async def list_submissions(
        self,
        *,
        user_id: str | None = None,
        team_department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerAudioSubmission], int]:
        stmt = select(SalesTrainerAudioSubmission)
        count_stmt = select(func.count()).select_from(SalesTrainerAudioSubmission)
        if user_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerAudioSubmission.user_id == User.user_id)
            count_stmt = count_stmt.join(
                User,
                SalesTrainerAudioSubmission.user_id == User.user_id,
            )
            stmt = stmt.where(User.department == team_department)
            count_stmt = count_stmt.where(User.department == team_department)
        result = await self._db.execute(
            stmt.order_by(SalesTrainerAudioSubmission.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def list_score_results(
        self,
        *,
        user_id: str | None = None,
        submission_id: str | None = None,
        team_department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerAudioScoreResult], int]:
        stmt = select(SalesTrainerAudioScoreResult).join(
            SalesTrainerAudioSubmission,
            SalesTrainerAudioScoreResult.submission_id
            == SalesTrainerAudioSubmission.submission_id,
        )
        count_stmt = select(func.count()).select_from(SalesTrainerAudioScoreResult).join(
            SalesTrainerAudioSubmission,
            SalesTrainerAudioScoreResult.submission_id
            == SalesTrainerAudioSubmission.submission_id,
        )
        if user_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
        if submission_id:
            stmt = stmt.where(
                SalesTrainerAudioScoreResult.submission_id == submission_id
            )
            count_stmt = count_stmt.where(
                SalesTrainerAudioScoreResult.submission_id == submission_id
            )
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerAudioSubmission.user_id == User.user_id)
            count_stmt = count_stmt.join(
                User,
                SalesTrainerAudioSubmission.user_id == User.user_id,
            )
            stmt = stmt.where(User.department == team_department)
            count_stmt = count_stmt.where(User.department == team_department)

        result = await self._db.execute(
            stmt.order_by(SalesTrainerAudioScoreResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def serialize_submission(
        self, submission: SalesTrainerAudioSubmission
    ) -> dict[str, Any]:
        transcript = await self._get_transcript(submission.submission_id)
        score = await self._get_latest_score(submission.submission_id)
        user = await self._db.get(User, submission.user_id)
        task_brief_snapshot = (
            submission.task_brief_snapshot
            if isinstance(submission.task_brief_snapshot, dict)
            else None
        )
        lineage = submission_lineage_fields(task_brief_snapshot)
        return {
            "submission_id": submission.submission_id,
            "unit_id": submission.unit_id,
            "user_id": submission.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_department": user.department if user else None,
            "purpose": submission.purpose,
            "original_filename": submission.original_filename,
            "content_type": submission.content_type,
            "size_bytes": int(submission.size_bytes),
            "storage_key": submission.storage_key,
            "file_hash": submission.file_hash,
            "duration_seconds": float(submission.duration_seconds)
            if submission.duration_seconds is not None
            else None,
            "source_page": submission.source_page,
            "confirmed_material_version_id": submission.confirmed_material_version_id,
            "confirmed_material_at": submission.confirmed_material_at,
            "material_snapshot": submission.material_snapshot,
            "score_scheme_snapshot": submission.score_scheme_snapshot,
            "task_brief_snapshot": submission.task_brief_snapshot,
            "path_key": lineage["path_key"],
            "path_revision_id": lineage["path_revision_id"],
            "path_revision_no": lineage["path_revision_no"],
            "module_key": lineage["module_key"],
            "legacy_snapshot_only": lineage["legacy_snapshot_only"],
            "status": submission.status,
            "error_code": submission.error_code,
            "error_message": submission.error_message,
            "created_at": submission.created_at,
            "updated_at": submission.updated_at,
            "transcript": _serialize_transcript(transcript) if transcript else None,
            "score_result": _serialize_score_with_lineage(score, task_brief_snapshot)
            if score
            else None,
        }

    def _require_material_binding_for_ppt(
        self,
        unit: SalesTrainerUnit,
        purpose: str,
        *,
        config_override: dict[str, Any] | None = None,
    ) -> None:
        config = config_override if config_override is not None else unit.config
        unit_purpose = ((config or {}).get("audio") or {}).get("purpose")
        resolved_purpose = str(unit_purpose or purpose or "")
        if resolved_purpose != "ppt_pitch":
            return
        materials_config = (config or {}).get("materials")
        bindings = (
            materials_config.get("bindings")
            if isinstance(materials_config, dict)
            else None
        )
        if not isinstance(bindings, list) or not bindings:
            raise AudioSubmissionServiceError(
                "[PPT_MATERIAL_BINDING_REQUIRED]",
                "PPT 演练任务必须先绑定已发布训练材料。",
                status_code=409,
            )

    async def serialize_score_result(
        self,
        score: SalesTrainerAudioScoreResult,
    ) -> dict[str, Any]:
        submission = await self._db.get(SalesTrainerAudioSubmission, score.submission_id)
        task_brief_snapshot = (
            submission.task_brief_snapshot
            if submission is not None and isinstance(submission.task_brief_snapshot, dict)
            else None
        )
        return _serialize_score_with_lineage(score, task_brief_snapshot)

    async def _transcribe(
        self,
        submission: SalesTrainerAudioSubmission,
        *,
        actor: User | None,
    ) -> None:
        submission.status = "transcribing"
        submission.error_code = None
        submission.error_message = None
        await self._logs.record(
            actor=actor,
            action="audio_transcription_started",
            target_type="sales_trainer_audio_submission",
            target_id=submission.submission_id,
        )
        await self._db.flush()
        started_at = datetime.now(UTC)
        try:
            result = await self._transcription.transcribe_file(str(submission.storage_key))
        except RuntimeError as exc:
            code = str(exc) if str(exc).startswith("[") else "[TRANSCRIPTION_FAILED]"
            submission.status = "transcription_failed"
            submission.error_code = code
            submission.error_message = str(exc)
            await self._logs.record(
                actor=actor,
                action="audio_transcription_failed",
                target_type="sales_trainer_audio_submission",
                target_id=submission.submission_id,
                metadata={"error_code": code},
            )
            return

        if not result.transcript_text.strip():
            submission.status = "transcription_failed"
            submission.error_code = "[TRANSCRIPT_EMPTY]"
            submission.error_message = "转写文本为空。"
            await self._logs.record(
                actor=actor,
                action="audio_transcription_failed",
                target_type="sales_trainer_audio_submission",
                target_id=submission.submission_id,
                metadata={"error_code": "[TRANSCRIPT_EMPTY]"},
            )
            return

        existing = await self._get_transcript(submission.submission_id)
        if existing is None:
            self._db.add(
                SalesTrainerAudioTranscript(
                    submission_id=submission.submission_id,
                    provider=result.provider,
                    transcript_text=result.transcript_text,
                    raw_payload=result.raw_payload,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                )
            )
        else:
            existing.provider = result.provider
            existing.transcript_text = result.transcript_text
            existing.raw_payload = result.raw_payload
            existing.started_at = started_at
            existing.completed_at = datetime.now(UTC)
        submission.status = "transcribed"
        await self._logs.record(
            actor=actor,
            action="audio_transcription_succeeded",
            target_type="sales_trainer_audio_submission",
            target_id=submission.submission_id,
        )

    async def _score(
        self,
        submission: SalesTrainerAudioSubmission,
        *,
        actor: User | None,
    ) -> None:
        if submission.status != "transcribed":
            return
        transcript = await self._get_transcript(submission.submission_id)
        if transcript is None:
            return
        unit = (
            await self._db.get(SalesTrainerUnit, submission.unit_id)
            if submission.unit_id
            else None
        )
        score_scheme_snapshot = (
            submission.score_scheme_snapshot
            if isinstance(submission.score_scheme_snapshot, dict)
            else None
        )
        prompt_id = _resolve_scoring_prompt_id_from_snapshot(score_scheme_snapshot)
        effective_config = None
        if unit is not None and not prompt_id:
            effective_config = (
                await EffectiveAudioTrainingConfigResolver(self._db).resolve_for_unit(
                    unit
                )
            ).config
            prompt_id = _resolve_scoring_prompt_id(unit, config_override=effective_config)
        if not prompt_id:
            submission.status = "scoring_failed"
            submission.error_code = "[SCORING_PROMPT_REQUIRED]"
            submission.error_message = "缺少录音评分标准。"
            await self._logs.record(
                actor=actor,
                action="audio_scoring_failed",
                target_type="sales_trainer_audio_submission",
                target_id=submission.submission_id,
                metadata={"error_code": "[SCORING_PROMPT_REQUIRED]"},
            )
            return
        prompt = await self._db.get(SalesTrainerAudioScorePrompt, prompt_id)
        if prompt is None or prompt.status != "published":
            submission.status = "scoring_failed"
            submission.error_code = "[SCORING_PROMPT_NOT_PUBLISHED]"
            submission.error_message = "录音评分标准不存在或未发布。"
            await self._logs.record(
                actor=actor,
                action="audio_scoring_failed",
                target_type="sales_trainer_audio_submission",
                target_id=submission.submission_id,
                metadata={"error_code": "[SCORING_PROMPT_NOT_PUBLISHED]"},
            )
            return

        submission.status = "scoring"
        await self._logs.record(
            actor=actor,
            action="audio_scoring_started",
            target_type="sales_trainer_audio_submission",
            target_id=submission.submission_id,
            metadata={"prompt_id": prompt.prompt_id, "prompt_version": prompt.version},
        )
        threshold = _resolve_pass_threshold_from_snapshot(score_scheme_snapshot)
        if threshold is None:
            if effective_config is None and unit is not None:
                effective_config = (
                    await EffectiveAudioTrainingConfigResolver(self._db).resolve_for_unit(
                        unit
                    )
                ).config
            threshold = resolve_audio_pass_threshold(effective_config if unit else None)
        outcome = await self._scoring.score_audio(
            submission=submission,
            prompt=prompt,
            transcript_text=transcript.transcript_text,
            unit_name=unit.name if unit else None,
            pass_threshold=threshold,
        )
        self._db.add(
            SalesTrainerAudioScoreResult(
                submission_id=submission.submission_id,
                prompt_id=prompt.prompt_id,
                prompt_version=int(prompt.version),
                prompt_hash=outcome.prompt_hash,
                deucate_model=outcome.deucate_model,
                transcript_snapshot=transcript.transcript_text,
                total_score=outcome.total_score,
                passed=outcome.passed,
                summary=outcome.summary,
                strengths=outcome.strengths,
                improvements=outcome.improvements,
                dimension_scores=outcome.dimension_scores,
                raw_response=outcome.raw_response,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
                latency_ms=outcome.latency_ms,
            )
        )
        if outcome.error_code:
            submission.status = "scoring_failed"
            submission.error_code = outcome.error_code
            submission.error_message = outcome.error_message
            action = "audio_scoring_failed"
        else:
            submission.status = "scored"
            submission.error_code = None
            submission.error_message = None
            action = "audio_scoring_succeeded"
        await self._logs.record(
            actor=actor,
            action=action,
            target_type="sales_trainer_audio_submission",
            target_id=submission.submission_id,
            metadata={"error_code": outcome.error_code},
        )

    async def _require_submission(
        self, submission_id: str
    ) -> SalesTrainerAudioSubmission:
        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            raise AudioSubmissionServiceError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "音频提交不存在。",
                404,
            )
        return submission

    async def _get_transcript(
        self, submission_id: str
    ) -> SalesTrainerAudioTranscript | None:
        result = await self._db.execute(
            select(SalesTrainerAudioTranscript).where(
                SalesTrainerAudioTranscript.submission_id == submission_id
            )
        )
        return result.scalar_one_or_none()

    async def _get_latest_score(
        self, submission_id: str
    ) -> SalesTrainerAudioScoreResult | None:
        result = await self._db.execute(
            select(SalesTrainerAudioScoreResult)
            .where(SalesTrainerAudioScoreResult.submission_id == submission_id)
            .order_by(SalesTrainerAudioScoreResult.created_at.desc())
        )
        return result.scalars().first()

    async def _submission_in_department(
        self,
        submission: SalesTrainerAudioSubmission,
        department: str,
    ) -> bool:
        result = await self._db.execute(
            select(User.department).where(User.user_id == submission.user_id)
        )
        return result.scalar_one_or_none() == department

    def _validate_content_type(self, content_type: str) -> None:
        allowed = {
            item.strip()
            for item in os.getenv(
                "SALES_TRAINER_AUDIO_ALLOWED_MIME_TYPES",
                ",".join(DEFAULT_ALLOWED_MIME_TYPES),
            ).split(",")
            if item.strip()
        }
        if content_type not in allowed:
            raise AudioSubmissionServiceError(
                "[AUDIO_TYPE_NOT_ALLOWED]",
                "不支持的音频格式。",
                status_code=422,
            )

    def _validate_file_size(self, size_bytes: int) -> None:
        raw_max_mb = os.getenv(
            "SALES_TRAINER_AUDIO_MAX_FILE_SIZE_MB", str(DEFAULT_MAX_AUDIO_MB)
        )
        try:
            max_mb = int(raw_max_mb)
        except ValueError as exc:
            raise AudioSubmissionServiceError(
                "[AUDIO_SIZE_CONFIG_INVALID]",
                "音频文件大小上限配置非法。",
                status_code=500,
            ) from exc
        if max_mb <= 0:
            raise AudioSubmissionServiceError(
                "[AUDIO_SIZE_CONFIG_INVALID]",
                "音频文件大小上限配置非法。",
                status_code=500,
            )
        if size_bytes > max_mb * 1024 * 1024:
            raise AudioSubmissionServiceError(
                "[AUDIO_FILE_TOO_LARGE]",
                "音频文件超过配置大小上限。",
                status_code=413,
            )

    def _validate_direct_object_if_needed(
        self,
        storage_key: str,
        *,
        expected_size_bytes: int,
    ) -> None:
        if not _is_explicit_object_storage_key(storage_key):
            return
        try:
            remote_size = _get_object_storage_size(storage_key)
        except FileNotFoundError as exc:
            raise AudioSubmissionServiceError(
                "[AUDIO_OBJECT_NOT_FOUND]",
                "音频对象不存在或尚未上传完成。",
                status_code=404,
            ) from exc
        except OssConfigError as exc:
            raise AudioSubmissionServiceError(
                "[OSS_NOT_CONFIGURED]",
                str(exc),
                status_code=503,
            ) from exc
        except CosConfigError as exc:
            raise AudioSubmissionServiceError(
                "[COS_NOT_CONFIGURED]",
                str(exc),
                status_code=503,
            ) from exc
        except Exception as exc:
            raise AudioSubmissionServiceError(
                "[AUDIO_OBJECT_HEAD_FAILED]",
                "音频对象校验失败。",
                status_code=502,
            ) from exc
        if remote_size != expected_size_bytes:
            raise AudioSubmissionServiceError(
                "[AUDIO_OBJECT_SIZE_MISMATCH]",
                "音频对象大小与提交信息不一致。",
                status_code=409,
            )

    def _build_storage_key(self, user_id: str, filename: str) -> str:
        extension = _safe_extension(filename)
        return f"sales-trainer/audio/{user_id}/{uuid.uuid4().hex}{extension}"

    def _store_uploaded_bytes(
        self,
        *,
        user_id: str,
        filename: str,
        content_type: str,
        raw: bytes,
    ) -> str:
        backend = os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local").lower()
        if backend == "cos":
            object_key = self._build_storage_key(user_id, filename)
            try:
                stored_key = get_cos_signing_service().upload_object(
                    object_key,
                    raw,
                    content_type=content_type,
                )
            except CosConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[COS_NOT_CONFIGURED]",
                    str(exc),
                    status_code=503,
                ) from exc
            except Exception as exc:
                raise AudioSubmissionServiceError(
                    "[COS_UPLOAD_FAILED]",
                    "音频上传到 COS 失败。",
                    status_code=502,
                ) from exc
            return f"cos://{stored_key}"

        storage_path = self._local_storage_path(user_id, filename)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(raw)
        return str(storage_path)

    def _local_storage_path(self, user_id: str, filename: str) -> Path:
        base = Path(os.getenv("SALES_TRAINER_AUDIO_STORAGE_PATH", "./data/sales_trainer_audio"))
        return base / user_id / f"{uuid.uuid4().hex}{_safe_extension(filename)}"


def _resolve_scoring_prompt_id(
    unit: SalesTrainerUnit | None,
    *,
    config_override: dict[str, Any] | None = None,
) -> str | None:
    if unit is None:
        return None
    config = config_override if config_override is not None else unit.config
    audio_config = (config or {}).get("audio") or {}
    value = audio_config.get("scoring_prompt_id")
    return str(value) if value else None


def _resolve_scoring_prompt_id_from_snapshot(
    snapshot: dict[str, Any] | None,
) -> str | None:
    if snapshot is None:
        return None
    value = snapshot.get("prompt_id")
    return str(value) if value else None


def _resolve_pass_threshold_from_snapshot(snapshot: dict[str, Any] | None) -> int | None:
    if snapshot is None:
        return None
    value = snapshot.get("pass_threshold")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _safe_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix or ""):
        return suffix
    return ".webm"


def _is_object_storage_key(storage_key: str) -> bool:
    return (
        storage_key.startswith("oss://")
        or storage_key.startswith("cos://")
        or storage_key.startswith("sales-trainer/")
        or storage_key.startswith("audio/")
    )


def _is_explicit_object_storage_key(storage_key: str) -> bool:
    return storage_key.startswith("oss://") or storage_key.startswith("cos://")


def _normalize_object_storage_key(storage_key: str) -> str:
    if storage_key.startswith("oss://"):
        return storage_key.removeprefix("oss://")
    if storage_key.startswith("cos://"):
        return storage_key.removeprefix("cos://")
    return storage_key


def _generate_object_storage_get_url(storage_key: str) -> str:
    object_key = _normalize_object_storage_key(storage_key)
    backend = _resolve_object_storage_backend(storage_key)
    if backend == "cos":
        return get_cos_signing_service().generate_get_url(
            object_key,
            expires=_resolve_file_url_expires_seconds(),
        )
    return get_oss_signing_service().generate_get_url(
        object_key,
        expires=_resolve_file_url_expires_seconds(),
    )


def _get_object_storage_size(storage_key: str) -> int:
    object_key = _normalize_object_storage_key(storage_key)
    backend = _resolve_object_storage_backend(storage_key)
    if backend == "cos":
        return get_cos_signing_service().get_object_size(object_key)
    if backend == "oss":
        return get_oss_signing_service().get_object_size(object_key)
    raise RuntimeError("Object storage backend is not configured.")


def _resolve_object_storage_backend(storage_key: str) -> str:
    if storage_key.startswith("cos://"):
        return "cos"
    if storage_key.startswith("oss://"):
        return "oss"
    return os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local").strip().lower()


def _resolve_file_url_expires_seconds() -> int:
    raw_value = os.getenv(
        "SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS",
        str(DEFAULT_AUDIO_FILE_URL_EXPIRES_SECONDS),
    )
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise AudioSubmissionServiceError(
            "[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]",
            "音频文件访问链接有效期配置非法。",
            status_code=500,
        ) from exc
    if value <= 0:
        raise AudioSubmissionServiceError(
            "[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]",
            "音频文件访问链接有效期配置非法。",
            status_code=500,
        )
    return value


def _serialize_transcript(
    transcript: SalesTrainerAudioTranscript,
) -> dict[str, Any]:
    return {
        "transcript_id": transcript.transcript_id,
        "provider": transcript.provider,
        "transcript_text": transcript.transcript_text,
        "raw_payload": transcript.raw_payload,
        "started_at": transcript.started_at,
        "completed_at": transcript.completed_at,
        "created_at": transcript.created_at,
    }


def _serialize_score(score: SalesTrainerAudioScoreResult) -> dict[str, Any]:
    return {
        "score_id": score.score_id,
        "submission_id": score.submission_id,
        "prompt_id": score.prompt_id,
        "prompt_version": score.prompt_version,
        "prompt_hash": score.prompt_hash,
        "deucate_model": score.deucate_model,
        "transcript_snapshot": score.transcript_snapshot,
        "total_score": float(score.total_score)
        if score.total_score is not None
        else None,
        "passed": score.passed,
        "summary": score.summary,
        "strengths": score.strengths or [],
        "improvements": score.improvements or [],
        "dimension_scores": score.dimension_scores or {},
        "raw_response": score.raw_response,
        "error_code": score.error_code,
        "error_message": score.error_message,
        "latency_ms": score.latency_ms,
        "created_at": score.created_at,
    }


def _serialize_score_with_lineage(
    score: SalesTrainerAudioScoreResult,
    task_brief_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    lineage = submission_lineage_fields(task_brief_snapshot)
    return {
        **_serialize_score(score),
        "path_key": lineage["path_key"],
        "path_revision_id": lineage["path_revision_id"],
        "path_revision_no": lineage["path_revision_no"],
        "module_key": lineage["module_key"],
        "legacy_snapshot_only": lineage["legacy_snapshot_only"],
    }

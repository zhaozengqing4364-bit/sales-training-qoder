"""Audio/assignment run orchestration and resumable upload commands."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from audio_assessment.contracts import (
    ASSIGNMENT_SEGMENTS,
    AudioMaterialSnapshot,
    AudioRunnerProjection,
    AudioScenarioSnapshot,
    AudioScoringSchemeSnapshot,
    AudioSubmissionState,
    ConfirmUploadPartInput,
    CreateUploadSessionInput,
    FinalizeUploadInput,
    SubmissionCommandInput,
    UploadPartProjection,
    UploadSessionProjection,
    UploadSessionState,
)
from audio_assessment.errors import AudioAssessmentError
from audio_assessment.models import (
    AudioActivityResourceRevision,
    AudioActivityRun,
    AudioQualityReport,
    AudioScoreOutcomeVersion,
    AudioSubmission,
    AudioTranscriptRevision,
    AudioUploadPart,
    AudioUploadSession,
)
from audio_assessment.ports import AudioObjectStoragePort
from audio_assessment.storage import AudioStorageError
from task_runtime.contracts import ActorContext, TaskCommand, TaskState
from task_runtime.errors import TaskRuntimeError
from task_runtime.repository import SQLAlchemyTaskRuntime

AUDIO_PIPELINE_TASK_TYPE = "audio_assessment.pipeline.process"


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class AudioRuntimeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: str
    version: int
    task_id: str | None
    runner: dict[str, Any]
    available_commands: tuple[str, ...]


class AudioRuntimeService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        task_runtime: SQLAlchemyTaskRuntime,
        storage: AudioObjectStoragePort,
    ) -> None:
        self._session = session
        self._tasks = task_runtime
        self._storage = storage

    async def start(
        self,
        *,
        organization_id: str,
        learner_id: str,
        enrollment_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        attempt_id: str,
        config: dict[str, Any],
        competency_keys: tuple[str, ...],
        idempotency_key: str,
    ) -> AudioRuntimeResult:
        if activity_type not in {"audio_assessment", "assignment"}:
            self._unsupported()
        fingerprint = _canonical_hash(
            {
                "attempt_id": attempt_id,
                "activity_type": activity_type,
                "config": config,
                "competency_keys": competency_keys,
            }
        )
        existing = await self._session.scalar(
            select(AudioActivityRun)
            .where(AudioActivityRun.attempt_id == attempt_id)
            .limit(1)
        )
        if existing is not None:
            if (
                existing.idempotency_key_hash != _secret_hash(idempotency_key)
                or existing.command_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return await self._project(existing)

        snapshot = await self._freeze_config(
            organization_id=organization_id,
            activity_type=activity_type,
            config=config,
        )
        run = AudioActivityRun(
            run_id=_id(),
            organization_id=organization_id,
            learner_id=learner_id,
            enrollment_id=enrollment_id,
            path_revision_id=path_revision_id,
            activity_id=activity_id,
            activity_type=activity_type,
            attempt_id=attempt_id,
            status="draft",
            version=1,
            config_snapshot_json=snapshot,
            competency_keys_json=list(competency_keys),
            idempotency_key_hash=_secret_hash(idempotency_key),
            command_fingerprint=fingerprint,
        )
        self._session.add(run)
        await self._session.flush([run])
        segment_ids = (
            ASSIGNMENT_SEGMENTS if activity_type == "assignment" else ("primary",)
        )
        submissions = [
            AudioSubmission(
                submission_id=_id(),
                run_id=run.run_id,
                organization_id=organization_id,
                learner_id=learner_id,
                segment_id=segment_id,
                state=AudioSubmissionState.DRAFT.value,
                version=1,
            )
            for segment_id in segment_ids
        ]
        self._session.add_all(submissions)
        await self._session.flush(submissions)
        return await self._project(run)

    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str | None,
    ) -> AudioRuntimeResult | None:
        if attempt_id is None:
            return None
        run = await self._session.scalar(
            select(AudioActivityRun)
            .where(AudioActivityRun.attempt_id == attempt_id)
            .limit(1)
        )
        if (
            run is None
            or run.organization_id != organization_id
            or run.learner_id != learner_id
        ):
            return None
        return await self._project(run)

    async def create_upload_session(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        payload: CreateUploadSessionInput,
        idempotency_key: str,
    ) -> AudioRuntimeResult:
        run = await self._load_run(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if run.status in {"completed", "cancelled", "invalidated"}:
            raise AudioAssessmentError(
                "[AUDIO_RUN_STATE_CONFLICT]",
                "当前录音任务已经结束，不能创建新的上传。",
                409,
            )
        scoring = AudioScoringSchemeSnapshot.model_validate(
            run.config_snapshot_json["scoring_scheme"]
        )
        capture = scoring.capture
        if payload.recording_mode not in capture.allowed_recording_modes:
            raise AudioAssessmentError(
                "[AUDIO_RECORDING_MODE_UNSUPPORTED]",
                "当前任务不支持这种录音方式。",
                422,
            )
        if payload.content_type not in set(capture.allowed_content_types):
            raise AudioAssessmentError(
                "[AUDIO_CONTENT_TYPE_UNSUPPORTED]",
                "当前任务不支持这种录音格式，请重新录制或选择受支持的音频。",
                422,
            )
        if payload.size_bytes > capture.max_size_bytes:
            raise AudioAssessmentError(
                "[AUDIO_SIZE_LIMIT_EXCEEDED]",
                (
                    "录音超过当前任务允许的 "
                    f"{capture.max_size_bytes / (1024 * 1024):g}MB 上限。"
                ),
                422,
            )
        if payload.duration_seconds > capture.max_duration_seconds:
            raise AudioAssessmentError(
                "[AUDIO_DURATION_LIMIT_EXCEEDED]",
                (
                    "录音超过当前任务允许的 "
                    f"{capture.max_duration_seconds / 60:g} 分钟上限。"
                ),
                422,
            )
        expected_part_count = (
            payload.size_bytes + capture.part_size_bytes - 1
        ) // capture.part_size_bytes
        if len(payload.parts) != expected_part_count or any(
            item.size_bytes
            != (
                capture.part_size_bytes
                if item.part_number < expected_part_count
                else payload.size_bytes
                - capture.part_size_bytes * (expected_part_count - 1)
            )
            for item in payload.parts
        ):
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_PART_LAYOUT_INVALID]",
                "录音分片大小与当前任务的上传规则不一致，请重新准备上传。",
                422,
            )
        submission = await self._load_submission_for_run(run, payload.segment_id)
        if run.activity_type == "assignment":
            ordered = {
                item.segment_id: item
                for item in await self._submissions(run.run_id, for_update=True)
            }
            segment_index = ASSIGNMENT_SEGMENTS.index(payload.segment_id)
            if any(
                ordered[segment_id].state != AudioSubmissionState.COMPLETED.value
                for segment_id in ASSIGNMENT_SEGMENTS[:segment_index]
            ):
                raise AudioAssessmentError(
                    "[AUDIO_ASSIGNMENT_SEGMENT_LOCKED]",
                    "请先完成上一段客户场景回答。",
                    409,
                )
        if submission.state not in {
            AudioSubmissionState.DRAFT.value,
            AudioSubmissionState.UPLOADING.value,
            AudioSubmissionState.EXPIRED.value,
        }:
            raise AudioAssessmentError(
                "[AUDIO_SUBMISSION_STATE_CONFLICT]",
                "当前录音已经进入处理，不能重新创建上传会话。",
                409,
            )
        fingerprint = _canonical_hash(payload.model_dump(mode="json"))
        replay = await self._session.scalar(
            select(AudioUploadSession)
            .where(AudioUploadSession.submission_id == submission.submission_id)
            .where(
                AudioUploadSession.idempotency_key_hash == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.command_fingerprint != fingerprint:
                self._idempotency_conflict()
            return await self._project(run, active_upload_id=replay.upload_session_id)
        self._require_version(run.version, expected_version)

        active = await self._session.scalar(
            select(AudioUploadSession)
            .join(
                AudioSubmission,
                AudioSubmission.submission_id == AudioUploadSession.submission_id,
            )
            .where(AudioSubmission.run_id == run.run_id)
            .where(AudioUploadSession.state == UploadSessionState.UPLOADING.value)
            .order_by(desc(AudioUploadSession.created_at))
            .limit(1)
        )
        if active is not None and _aware(active.expires_at) > _now():
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_SESSION_ACTIVE]",
                "当前任务已有可继续的录音上传，请先恢复或取消该上传。",
                409,
                details={"upload_session_id": active.upload_session_id},
            )
        if active is not None:
            active.state = UploadSessionState.EXPIRED.value
            active.version += 1

        session_id = _id()
        org_scope = _secret_hash(organization_id)[:16]
        object_prefix = (
            f"audio-assessment/{org_scope}/{run.run_id}/"
            f"{submission.submission_id}/{session_id}"
        )
        upload = AudioUploadSession(
            upload_session_id=session_id,
            submission_id=submission.submission_id,
            organization_id=organization_id,
            learner_id=learner_id,
            state=UploadSessionState.UPLOADING.value,
            version=1,
            original_filename=payload.original_filename,
            content_type=payload.content_type,
            declared_size_bytes=payload.size_bytes,
            declared_duration_seconds=payload.duration_seconds,
            declared_manifest_sha256=payload.manifest_sha256,
            part_size_bytes=capture.part_size_bytes,
            expected_part_count=len(payload.parts),
            storage_backend=self._storage.backend_name,
            object_prefix=object_prefix,
            upload_token_hash=_secret_hash(secrets.token_urlsafe(32)),
            idempotency_key_hash=_secret_hash(idempotency_key),
            command_fingerprint=fingerprint,
            expires_at=_now() + timedelta(seconds=capture.upload_ttl_seconds),
        )
        self._session.add(upload)
        # Flush the upload parent before its parts.  The models intentionally do not
        # expose an ORM relationship, so SQLAlchemy cannot infer the FK insert order
        # when a constrained PostgreSQL database flushes both object types together.
        await self._session.flush([upload])
        parts = [
            AudioUploadPart(
                part_id=_id(),
                upload_session_id=session_id,
                organization_id=organization_id,
                part_number=item.part_number,
                object_key=f"{object_prefix}/part-{item.part_number:05d}",
                declared_size_bytes=item.size_bytes,
                declared_sha256=item.sha256,
            )
            for item in payload.parts
        ]
        self._session.add_all(parts)
        submission.state = AudioSubmissionState.UPLOADING.value
        submission.version += 1
        submission.failed_stage = None
        submission.error_classification = None
        submission.error_retryable = None
        submission.safe_error_message = None
        run.status = "in_progress"
        run.version += 1
        await self._session.flush([submission, run, *parts])
        return await self._project(run, active_upload_id=session_id)

    async def confirm_upload_part(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        payload: ConfirmUploadPartInput,
    ) -> AudioRuntimeResult:
        run = await self._load_run(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        upload = await self._load_upload(
            run, payload.upload_session_id, for_update=True
        )
        self._require_active_upload(upload)
        part = await self._session.scalar(
            select(AudioUploadPart)
            .where(AudioUploadPart.upload_session_id == upload.upload_session_id)
            .where(AudioUploadPart.part_number == payload.part_number)
            .with_for_update()
            .limit(1)
        )
        if part is None:
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_PART_NOT_FOUND]",
                "上传分片不属于当前录音，请刷新后重试。",
                404,
            )
        if (
            part.declared_size_bytes != payload.size_bytes
            or part.declared_sha256 != payload.sha256
        ):
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_PART_MISMATCH]",
                "上传分片与本地草稿不一致，请重新上传该分片。",
                409,
            )
        if part.registered_at is not None:
            return await self._project(
                run,
                active_upload_id=upload.upload_session_id,
            )
        self._require_version(run.version, expected_version)
        if part.registered_at is None:
            part.registered_at = _now()
            run.version += 1
            await self._session.flush([part, run])
        return await self._project(run, active_upload_id=upload.upload_session_id)

    async def finalize_upload(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        payload: FinalizeUploadInput,
        idempotency_key: str,
        trace_id: str | None,
    ) -> AudioRuntimeResult:
        run = await self._load_run(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        upload = await self._load_upload(
            run, payload.upload_session_id, for_update=True
        )
        submission = await self._session.get(AudioSubmission, upload.submission_id)
        assert submission is not None
        if upload.state == UploadSessionState.FINALIZED.value:
            if submission.task_id is None:
                raise AudioAssessmentError(
                    "[AUDIO_PIPELINE_TASK_MISSING]",
                    "录音已保存，但处理任务尚未建立，请稍后重试。",
                    503,
                )
            return await self._project(run)
        self._require_version(run.version, expected_version)
        self._require_active_upload(upload)
        parts = (
            (
                await self._session.execute(
                    select(AudioUploadPart)
                    .where(
                        AudioUploadPart.upload_session_id == upload.upload_session_id
                    )
                    .order_by(AudioUploadPart.part_number)
                )
            )
            .scalars()
            .all()
        )
        if len(parts) != upload.expected_part_count or any(
            part.registered_at is None for part in parts
        ):
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_INCOMPLETE]",
                "仍有录音分片未上传完成，请继续上传后再提交。",
                409,
                details={
                    "uploaded_part_count": sum(
                        1 for part in parts if part.registered_at is not None
                    ),
                    "expected_part_count": upload.expected_part_count,
                },
            )
        upload.state = UploadSessionState.FINALIZED.value
        upload.version += 1
        upload.finalized_at = _now()
        submission.state = AudioSubmissionState.UPLOADED.value
        submission.version += 1
        run.status = "processing"
        run.version += 1
        task = await self._tasks.enqueue(
            TaskCommand(
                task_type=AUDIO_PIPELINE_TASK_TYPE,
                schema_version=1,
                organization_id=organization_id,
                actor_id=learner_id,
                resource_type="audio_submission",
                resource_id=submission.submission_id,
                idempotency_key=idempotency_key,
                input_payload={
                    "submission_id": submission.submission_id,
                    "mode": "initial",
                    "requested_by": learner_id,
                },
                correlation_id=attempt_id,
                causation_id=upload.upload_session_id,
                trace_id=trace_id,
                data_classification="confidential",
            )
        )
        submission.task_id = task.task_id
        await self._session.flush([upload, submission, run])
        return await self._project(run)

    async def retry_stage(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        payload: SubmissionCommandInput,
        idempotency_key: str,
        trace_id: str | None,
    ) -> AudioRuntimeResult:
        run = await self._load_run(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        self._require_version(run.version, expected_version)
        submission = await self._load_submission(
            run, payload.submission_id, for_update=True
        )
        if submission.state != AudioSubmissionState.FAILED_RECOVERABLE.value:
            raise AudioAssessmentError(
                "[AUDIO_STAGE_NOT_RETRYABLE]",
                "当前录音没有可重试的处理步骤。",
                409,
            )
        submission.processing_generation += 1
        submission.state = self._retry_state(submission.failed_stage)
        submission.error_classification = None
        submission.error_retryable = None
        submission.safe_error_message = None
        run.status = "processing"
        run.version += 1
        task = await self._tasks.enqueue(
            TaskCommand(
                task_type=AUDIO_PIPELINE_TASK_TYPE,
                schema_version=1,
                organization_id=organization_id,
                actor_id=learner_id,
                resource_type="audio_submission",
                resource_id=submission.submission_id,
                idempotency_key=idempotency_key,
                input_payload={
                    "submission_id": submission.submission_id,
                    "mode": "retry",
                    "requested_by": learner_id,
                },
                correlation_id=attempt_id,
                causation_id=submission.task_id,
                trace_id=trace_id,
                data_classification="confidential",
            )
        )
        submission.task_id = task.task_id
        await self._session.flush([submission, run])
        return await self._project(run)

    async def cancel_run(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        idempotency_key: str,
    ) -> AudioRuntimeResult:
        run = await self._load_run(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if run.status in {"completed", "cancelled", "invalidated"}:
            return await self._project(run)
        self._require_version(run.version, expected_version)
        submissions = await self._submissions(run.run_id, for_update=True)
        now = _now()
        for submission in submissions:
            if submission.state not in {
                AudioSubmissionState.COMPLETED.value,
                AudioSubmissionState.CANCELLED.value,
                AudioSubmissionState.INVALIDATED.value,
                AudioSubmissionState.EXPIRED.value,
            }:
                submission.state = AudioSubmissionState.CANCELLED.value
                submission.version += 1
                submission.cancelled_at = now
                if submission.task_id:
                    await self._tasks.request_cancel(
                        submission.task_id,
                        ActorContext(
                            organization_id=organization_id,
                            actor_id=learner_id,
                            capabilities=frozenset(),
                        ),
                        idempotency_key=f"{idempotency_key}:{submission.submission_id}",
                    )
        uploads = (
            (
                await self._session.execute(
                    select(AudioUploadSession)
                    .where(
                        AudioUploadSession.submission_id.in_(
                            tuple(item.submission_id for item in submissions)
                        )
                    )
                    .where(
                        AudioUploadSession.state == UploadSessionState.UPLOADING.value
                    )
                )
            )
            .scalars()
            .all()
        )
        for upload in uploads:
            upload.state = UploadSessionState.CANCELLED.value
            upload.version += 1
            upload.cancelled_at = now
        run.status = "cancelled"
        run.version += 1
        await self._session.flush([run, *submissions, *uploads])
        return await self._project(run)

    async def expire_uploads(self, *, limit: int = 100) -> int:
        rows = (
            (
                await self._session.execute(
                    select(AudioUploadSession)
                    .where(
                        AudioUploadSession.state == UploadSessionState.UPLOADING.value
                    )
                    .where(AudioUploadSession.expires_at <= _now())
                    .order_by(AudioUploadSession.expires_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for upload in rows:
            upload.state = UploadSessionState.EXPIRED.value
            upload.version += 1
            submission = await self._session.get(AudioSubmission, upload.submission_id)
            if (
                submission is not None
                and submission.state == AudioSubmissionState.UPLOADING.value
            ):
                submission.state = AudioSubmissionState.EXPIRED.value
                submission.version += 1
        await self._session.flush()
        return len(rows)

    async def _freeze_config(
        self,
        *,
        organization_id: str,
        activity_type: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            scoring_id = str(config["scoring_scheme_revision_id"])
            if activity_type == "audio_assessment":
                content_id = str(config["audio_material_revision_id"])
                content_type = "audio_material"
            else:
                content_id = str(config["scenario_revision_id"])
                content_type = "scenario"
        except (KeyError, TypeError, ValueError) as exc:
            raise AudioAssessmentError(
                "[AUDIO_ACTIVITY_CONFIG_INVALID]",
                "录音任务配置不完整，请联系培训负责人。",
                422,
            ) from exc
        content = await self._require_resource(
            organization_id=organization_id,
            revision_id=content_id,
            resource_type=content_type,
        )
        scoring = await self._require_resource(
            organization_id=organization_id,
            revision_id=scoring_id,
            resource_type="scoring_scheme",
        )
        try:
            score_snapshot = AudioScoringSchemeSnapshot.model_validate(
                scoring.snapshot_json
            )
            content_snapshot: BaseModel
            if activity_type == "audio_assessment":
                content_snapshot = AudioMaterialSnapshot.model_validate(
                    content.snapshot_json
                )
            else:
                content_snapshot = AudioScenarioSnapshot.model_validate(
                    content.snapshot_json
                )
        except ValueError as exc:
            raise AudioAssessmentError(
                "[AUDIO_RESOURCE_CONTRACT_INVALID]",
                "录音任务引用的已发布资源不符合当前合同。",
                422,
            ) from exc
        activity_max_size = int(
            config.get("max_size_bytes", score_snapshot.capture.max_size_bytes)
        )
        activity_max_duration = int(
            config.get(
                "max_duration_seconds",
                score_snapshot.capture.max_duration_seconds,
            )
        )
        if (
            activity_max_size > score_snapshot.capture.max_size_bytes
            or activity_max_duration > score_snapshot.capture.max_duration_seconds
        ):
            raise AudioAssessmentError(
                "[AUDIO_ACTIVITY_POLICY_CONFLICT]",
                "录音任务限制不能放宽已发布评分方案的安全上限。",
                422,
            )
        frozen_score = score_snapshot.model_copy(
            update={
                "capture": score_snapshot.capture.model_copy(
                    update={
                        "max_size_bytes": activity_max_size,
                        "max_duration_seconds": activity_max_duration,
                        "allowed_recording_modes": tuple(
                            config.get(
                                "allowed_recording_modes",
                                score_snapshot.capture.allowed_recording_modes,
                            )
                        ),
                    }
                ),
                "language": str(config.get("language", score_snapshot.language)),
            }
        )
        return {
            "activity_config": config,
            "content_revision": {
                "revision_id": content.revision_id,
                "resource_type": content.resource_type,
                "content_hash": content.content_hash,
                "snapshot": content_snapshot.model_dump(mode="json"),
            },
            "scoring_scheme_revision": {
                "revision_id": scoring.revision_id,
                "content_hash": scoring.content_hash,
            },
            "scoring_scheme": frozen_score.model_dump(mode="json"),
        }

    async def _require_resource(
        self,
        *,
        organization_id: str,
        revision_id: str,
        resource_type: str,
    ) -> AudioActivityResourceRevision:
        row = await self._session.get(AudioActivityResourceRevision, revision_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.resource_type != resource_type
            or row.status not in {"published", "archived"}
        ):
            raise AudioAssessmentError(
                "[AUDIO_ACTIVITY_RESOURCE_UNPUBLISHED]",
                "录音任务引用了未发布或不可访问的资源。",
                422,
                details={"resource_type": resource_type},
            )
        return row

    async def _project(
        self,
        run: AudioActivityRun,
        *,
        active_upload_id: str | None = None,
    ) -> AudioRuntimeResult:
        submissions = await self._submissions(run.run_id)
        active_upload = None
        if active_upload_id is None:
            active_upload = await self._session.scalar(
                select(AudioUploadSession)
                .where(
                    AudioUploadSession.submission_id.in_(
                        tuple(item.submission_id for item in submissions)
                    )
                )
                .where(AudioUploadSession.state == UploadSessionState.UPLOADING.value)
                .where(AudioUploadSession.expires_at > _now())
                .order_by(desc(AudioUploadSession.created_at))
                .limit(1)
            )
        else:
            active_upload = await self._session.get(
                AudioUploadSession, active_upload_id
            )
        upload_projection = (
            await self._upload_projection(active_upload)
            if active_upload is not None
            else None
        )
        content = run.config_snapshot_json["content_revision"]["snapshot"]
        segment_context: dict[str, dict[str, Any]] = {}
        if run.activity_type == "assignment":
            segment_context = {
                str(item["segment_id"]): dict(item)
                for item in content.get("segments", [])
            }
        else:
            segment_context["primary"] = {
                "segment_id": "primary",
                "title": content.get("title", "录音讲解"),
                "prompt": content.get("task_prompt", "完成本次录音讲解"),
                "preparation_hints": content.get("preparation_hints", []),
            }
        scoring = AudioScoringSchemeSnapshot.model_validate(
            run.config_snapshot_json["scoring_scheme"]
        )
        dimension_labels = {item.key: item.label for item in scoring.dimensions}
        transcript_ids = tuple(
            item.current_transcript_revision_id
            for item in submissions
            if item.current_transcript_revision_id
        )
        transcripts_by_id = (
            {
                row.revision_id: row
                for row in (
                    await self._session.execute(
                        select(AudioTranscriptRevision).where(
                            AudioTranscriptRevision.revision_id.in_(transcript_ids)
                        )
                    )
                ).scalars()
            }
            if transcript_ids
            else {}
        )
        qualities_by_transcript_id = (
            {
                row.transcript_revision_id: row
                for row in (
                    await self._session.execute(
                        select(AudioQualityReport).where(
                            AudioQualityReport.transcript_revision_id.in_(
                                transcript_ids
                            )
                        )
                    )
                ).scalars()
            }
            if transcript_ids
            else {}
        )
        score_ids = tuple(
            item.current_score_outcome_version_id
            for item in submissions
            if item.current_score_outcome_version_id
        )
        scores_by_id = (
            {
                row.outcome_version_id: row
                for row in (
                    await self._session.execute(
                        select(AudioScoreOutcomeVersion).where(
                            AudioScoreOutcomeVersion.outcome_version_id.in_(score_ids)
                        )
                    )
                ).scalars()
            }
            if score_ids
            else {}
        )
        segments: list[dict[str, Any]] = []
        for submission in submissions:
            score = None
            quality_projection = None
            transcript = transcripts_by_id.get(
                submission.current_transcript_revision_id or ""
            )
            transcript_projection = (
                {
                    "text": transcript.transcript_text,
                    "segments": transcript.segments_json,
                    "confidence": float(transcript.confidence),
                    "language": transcript.language,
                }
                if transcript is not None
                else None
            )
            quality = qualities_by_transcript_id.get(
                submission.current_transcript_revision_id or ""
            )
            if quality is not None:
                quality_projection = {
                    "scorable": quality.scorable,
                    "flags": quality.quality_flags_json,
                    "metrics": quality.metrics_json,
                }
            score_row = scores_by_id.get(
                submission.current_score_outcome_version_id or ""
            )
            if score_row is not None:
                score = {
                    "score": float(score_row.total_score),
                    "passed": score_row.passed,
                    "dimension_scores": [
                        {
                            **item,
                            "label": dimension_labels.get(
                                str(item.get("dimension_key")),
                                str(item.get("dimension_key", "评分项")),
                            ),
                        }
                        for item in score_row.dimension_scores_json
                    ],
                    "evidence_spans": score_row.evidence_spans_json,
                    "missing_points": score_row.missing_points_json,
                    "feedback": score_row.feedback_json,
                    "remediation": score_row.remediation_json,
                    "critical_flags": score_row.critical_flags_json,
                    "uncertainty": float(score_row.uncertainty),
                }
            context = segment_context.get(submission.segment_id, {})
            segments.append(
                {
                    "submission_id": submission.submission_id,
                    "segment_id": submission.segment_id,
                    "title": context.get("title", submission.segment_id),
                    "prompt": context.get("prompt", "完成本段录音"),
                    "customer_context": context.get("customer_context"),
                    "preparation_hints": context.get("preparation_hints", []),
                    "state": submission.state,
                    "version": submission.version,
                    "task_id": submission.task_id,
                    "error": (
                        None
                        if submission.safe_error_message is None
                        else {
                            "retryable": submission.error_retryable is True,
                            "message": submission.safe_error_message,
                            "failed_stage": submission.failed_stage,
                        }
                    ),
                    "transcript": transcript_projection,
                    "quality": quality_projection,
                    "result": score,
                }
            )
        completed_scores = [
            item["result"]["score"] for item in segments if item["result"] is not None
        ]
        runner = AudioRunnerProjection(
            kind=run.activity_type,
            run_id=run.run_id,
            status=run.status,
            version=run.version,
            rules={
                "allowed_recording_modes": list(
                    scoring.capture.allowed_recording_modes
                ),
                "allowed_content_types": list(scoring.capture.allowed_content_types),
                "max_duration_seconds": scoring.capture.max_duration_seconds,
                "max_size_bytes": scoring.capture.max_size_bytes,
                "part_size_bytes": scoring.capture.part_size_bytes,
                "local_draft_ttl_seconds": scoring.capture.local_draft_ttl_seconds,
                "language": scoring.language,
                "pass_score": scoring.pass_score,
            },
            segments=tuple(segments),
            active_upload=upload_projection,
            result=(
                {
                    "score": sum(completed_scores) / len(completed_scores),
                    "passed": all(
                        bool(item["result"] and item["result"]["passed"])
                        for item in segments
                    ),
                }
                if len(completed_scores) == len(segments) and segments
                else None
            ),
        )
        active_task = next(
            (
                item.task_id
                for item in submissions
                if item.task_id
                and item.state
                not in {
                    AudioSubmissionState.COMPLETED.value,
                    AudioSubmissionState.CANCELLED.value,
                    AudioSubmissionState.INVALIDATED.value,
                }
            ),
            None,
        )
        if active_task is not None:
            try:
                task = await self._tasks.get(
                    active_task,
                    ActorContext(
                        organization_id=run.organization_id,
                        actor_id=run.learner_id,
                        capabilities=frozenset(),
                    ),
                )
                if task.state in {
                    TaskState.CANCELLED,
                    TaskState.SUCCEEDED,
                    TaskState.DEAD_LETTER,
                }:
                    active_task = None
            except TaskRuntimeError:
                active_task = None
        return AudioRuntimeResult(
            run_id=run.run_id,
            status=run.status,
            version=run.version,
            task_id=active_task,
            runner=runner.model_dump(mode="json"),
            available_commands=self._available_commands(run, submissions),
        )

    async def _upload_projection(
        self, upload: AudioUploadSession
    ) -> UploadSessionProjection:
        parts = (
            (
                await self._session.execute(
                    select(AudioUploadPart)
                    .where(
                        AudioUploadPart.upload_session_id == upload.upload_session_id
                    )
                    .order_by(AudioUploadPart.part_number)
                )
            )
            .scalars()
            .all()
        )
        expires_seconds = max(
            60,
            min(900, int((_aware(upload.expires_at) - _now()).total_seconds())),
        )
        projected: list[UploadPartProjection] = []
        for part in parts:
            try:
                signed = self._storage.presign_part(
                    upload_session_id=upload.upload_session_id,
                    part_number=part.part_number,
                    object_key=part.object_key,
                    content_type=upload.content_type,
                    size_bytes=part.declared_size_bytes,
                    sha256=part.declared_sha256,
                    expires_seconds=expires_seconds,
                )
            except AudioStorageError as exc:
                raise AudioAssessmentError(
                    f"[{exc.code.upper()}]",
                    exc.safe_message,
                    503 if exc.retryable else 422,
                ) from exc
            projected.append(
                UploadPartProjection(
                    part_number=part.part_number,
                    upload_url=signed.upload_url,
                    required_headers=signed.required_headers,
                    uploaded=part.registered_at is not None,
                    size_bytes=part.declared_size_bytes,
                    sha256=part.declared_sha256,
                )
            )
        return UploadSessionProjection(
            upload_session_id=upload.upload_session_id,
            submission_id=upload.submission_id,
            state=UploadSessionState(upload.state),
            expires_at=upload.expires_at,
            part_size_bytes=upload.part_size_bytes,
            expected_part_count=upload.expected_part_count,
            uploaded_part_count=sum(1 for item in parts if item.registered_at),
            parts=tuple(projected),
        )

    async def _load_run(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        for_update: bool,
    ) -> AudioActivityRun:
        query = select(AudioActivityRun).where(
            AudioActivityRun.attempt_id == attempt_id
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if (
            row is None
            or row.organization_id != organization_id
            or row.learner_id != learner_id
        ):
            raise AudioAssessmentError(
                "[AUDIO_RUN_NOT_FOUND]",
                "录音任务不存在或不可访问。",
                404,
            )
        return row

    async def _load_submission_for_run(
        self, run: AudioActivityRun, segment_id: str
    ) -> AudioSubmission:
        row = await self._session.scalar(
            select(AudioSubmission)
            .where(AudioSubmission.run_id == run.run_id)
            .where(AudioSubmission.segment_id == segment_id)
            .with_for_update()
            .limit(1)
        )
        if row is None:
            raise AudioAssessmentError(
                "[AUDIO_SEGMENT_NOT_FOUND]",
                "录音分段不属于当前任务。",
                404,
            )
        return row

    async def _load_submission(
        self, run: AudioActivityRun, submission_id: str, *, for_update: bool
    ) -> AudioSubmission:
        query = select(AudioSubmission).where(
            AudioSubmission.submission_id == submission_id
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None or row.run_id != run.run_id:
            raise AudioAssessmentError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "录音提交不存在或不可访问。",
                404,
            )
        return row

    async def _load_upload(
        self, run: AudioActivityRun, upload_session_id: str, *, for_update: bool
    ) -> AudioUploadSession:
        query = select(AudioUploadSession).where(
            AudioUploadSession.upload_session_id == upload_session_id
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None:
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_SESSION_NOT_FOUND]",
                "上传会话不存在或已失效。",
                404,
            )
        submission = await self._session.get(AudioSubmission, row.submission_id)
        if submission is None or submission.run_id != run.run_id:
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_SESSION_NOT_FOUND]",
                "上传会话不存在或已失效。",
                404,
            )
        return row

    async def _submissions(
        self, run_id: str, *, for_update: bool = False
    ) -> list[AudioSubmission]:
        query = (
            select(AudioSubmission)
            .where(AudioSubmission.run_id == run_id)
            .order_by(AudioSubmission.created_at)
        )
        if for_update:
            query = query.with_for_update()
        return list((await self._session.execute(query)).scalars().all())

    @staticmethod
    def _available_commands(
        run: AudioActivityRun, submissions: list[AudioSubmission]
    ) -> tuple[str, ...]:
        if run.status in {"completed", "cancelled", "invalidated"}:
            return ()
        commands = ["cancel"]
        active_upload = any(
            item.state == AudioSubmissionState.UPLOADING.value for item in submissions
        )
        if active_upload:
            commands.extend(("confirm_upload_part", "finalize_upload"))
        elif run.activity_type == "assignment":
            by_segment = {item.segment_id: item for item in submissions}
            for index, segment_id in enumerate(ASSIGNMENT_SEGMENTS):
                current = by_segment[segment_id]
                if current.state == AudioSubmissionState.COMPLETED.value:
                    continue
                if current.state in {
                    AudioSubmissionState.DRAFT.value,
                    AudioSubmissionState.EXPIRED.value,
                } and all(
                    by_segment[prior].state == AudioSubmissionState.COMPLETED.value
                    for prior in ASSIGNMENT_SEGMENTS[:index]
                ):
                    commands.insert(0, "create_upload_session")
                break
        elif submissions and submissions[0].state in {
            AudioSubmissionState.DRAFT.value,
            AudioSubmissionState.EXPIRED.value,
        }:
            commands.insert(0, "create_upload_session")
        if any(
            item.state == AudioSubmissionState.FAILED_RECOVERABLE.value
            for item in submissions
        ):
            commands.append("retry_stage")
        return tuple(commands)

    @staticmethod
    def _retry_state(failed_stage: str | None) -> str:
        return {
            "validation": AudioSubmissionState.UPLOADED.value,
            "normalization": AudioSubmissionState.NORMALIZING.value,
            "transcription": AudioSubmissionState.TRANSCRIBING.value,
            "scoring": AudioSubmissionState.SCORING.value,
            "reconciliation": AudioSubmissionState.RECONCILING.value,
        }.get(failed_stage or "", AudioSubmissionState.UPLOADED.value)

    @staticmethod
    def _require_active_upload(upload: AudioUploadSession) -> None:
        if upload.state != UploadSessionState.UPLOADING.value:
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_STATE_CONFLICT]",
                "当前上传会话已经结束。",
                409,
            )
        if _aware(upload.expires_at) <= _now():
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_SESSION_EXPIRED]",
                "上传会话已过期，本地草稿仍保留，可重新开始上传。",
                409,
            )

    @staticmethod
    def _require_version(actual: int, expected: int) -> None:
        if actual != expected:
            raise AudioAssessmentError(
                "[AUDIO_VERSION_CONFLICT]",
                "录音任务已更新，请刷新后继续。",
                412,
                details={"expected_version": expected, "actual_version": actual},
            )

    @staticmethod
    def _idempotency_conflict() -> None:
        raise AudioAssessmentError(
            "[AUDIO_IDEMPOTENCY_CONFLICT]",
            "相同幂等键对应了不同的录音命令。",
            409,
        )

    @staticmethod
    def _unsupported() -> None:
        raise AudioAssessmentError(
            "[AUDIO_ACTIVITY_TYPE_UNSUPPORTED]",
            "当前活动不是可用的录音任务。",
            422,
        )


__all__ = [
    "AUDIO_PIPELINE_TASK_TYPE",
    "AudioRuntimeResult",
    "AudioRuntimeService",
]

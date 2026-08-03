"""Idempotent stage processor for the durable full-file audio pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform import (
    AIInvocationPort,
    PromptCompilationService,
    PromptPreviewRequest,
)
from ai_platform.contracts import (
    AIErrorClassification,
    AIInvocationResult,
    AIInvocationStatus,
    AIWorkloadKind,
    BudgetScope,
    DataClassification,
    GovernedAIRequest,
)
from ai_platform.errors import AIPlatformError
from audio_assessment.contracts import (
    AudioPipelineTaskInput,
    AudioPipelineTaskResult,
    AudioScoringAIInput,
    AudioScoringAIOutput,
    AudioScoringSchemeSnapshot,
    AudioSubmissionState,
    AudioTranscriptAIOutput,
    TranscriptSegment,
)
from audio_assessment.errors import AudioAssessmentError
from audio_assessment.models import (
    AudioActivityResourceRevision,
    AudioActivityRun,
    AudioArtifact,
    AudioQualityReport,
    AudioScoreOutcomeVersion,
    AudioSubmission,
    AudioTranscriptRevision,
    AudioUploadPart,
    AudioUploadSession,
)
from audio_assessment.ports import (
    AudioMediaInspection,
    AudioMediaToolPort,
    AudioObjectStoragePort,
    AudioOutcomePayload,
    AudioOutcomeWriterPort,
)
from audio_assessment.storage import AudioStorageError
from task_runtime.contracts import TaskCompletion, TaskResultKind
from task_runtime.errors import TaskExecutionError, TaskFailureKind


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


@dataclass(frozen=True, slots=True)
class _SubmissionContext:
    submission_id: str
    run_id: str
    organization_id: str
    learner_id: str
    attempt_id: str
    activity_type: str
    segment_id: str
    task_id: str
    state: str
    failed_stage: str | None
    config_snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ValidationPlan:
    context: _SubmissionContext
    upload_session_id: str
    object_keys: tuple[str, ...]
    declared_parts: tuple[tuple[int, int, str], ...]
    declared_total_size: int
    declared_duration: float
    content_type: str


@dataclass(frozen=True, slots=True)
class _NormalizationPlan:
    context: _SubmissionContext
    original_artifact_id: str
    object_keys: tuple[str, ...]
    content_type: str
    max_duration_seconds: int


@dataclass(frozen=True, slots=True)
class _TranscriptionPlan:
    context: _SubmissionContext
    normalized_artifact_id: str
    request: GovernedAIRequest


@dataclass(frozen=True, slots=True)
class _ScoringPlan:
    context: _SubmissionContext
    transcript_revision_id: str
    quality_report_id: str
    scoring_scheme: AudioScoringSchemeSnapshot
    scoring_scheme_revision_id: str
    request: GovernedAIRequest


class AudioPipelineProcessor:
    def __init__(
        self,
        session: AsyncSession,
        *,
        ai: AIInvocationPort,
        outcomes: AudioOutcomeWriterPort,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session = session
        self._ai = ai
        self._outcomes = outcomes
        self._prompt_compiler = prompt_compiler

    async def context(
        self,
        *,
        submission_id: str,
        task_id: str,
        allow_completed: bool = False,
    ) -> _SubmissionContext:
        submission = await self._session.get(AudioSubmission, submission_id)
        if submission is None:
            self._not_found()
        assert submission is not None
        run = await self._session.get(AudioActivityRun, submission.run_id)
        if run is None:
            self._not_found()
        assert run is not None
        if submission.task_id != task_id:
            raise AudioAssessmentError(
                "[AUDIO_TASK_MISMATCH]",
                "录音处理任务与当前提交不匹配。",
                409,
            )
        if submission.state in {
            AudioSubmissionState.CANCELLED.value,
            AudioSubmissionState.INVALIDATED.value,
            AudioSubmissionState.EXPIRED.value,
        }:
            raise AudioAssessmentError(
                "[AUDIO_SUBMISSION_STATE_CONFLICT]",
                "当前录音不能继续处理。",
                409,
            )
        if (
            not allow_completed
            and submission.state == AudioSubmissionState.COMPLETED.value
        ):
            raise AudioAssessmentError(
                "[AUDIO_SUBMISSION_STATE_CONFLICT]",
                "当前录音已经处理完成。",
                409,
            )
        return _SubmissionContext(
            submission_id=submission.submission_id,
            run_id=run.run_id,
            organization_id=run.organization_id,
            learner_id=run.learner_id,
            attempt_id=run.attempt_id,
            activity_type=run.activity_type,
            segment_id=submission.segment_id,
            task_id=task_id,
            state=submission.state,
            failed_stage=submission.failed_stage,
            config_snapshot=dict(run.config_snapshot_json),
        )

    async def prepare_validation(
        self, *, submission_id: str, task_id: str
    ) -> _ValidationPlan:
        context = await self.context(submission_id=submission_id, task_id=task_id)
        if context.state == AudioSubmissionState.NORMALIZING.value:
            raise AudioAssessmentError(
                "[AUDIO_STAGE_ALREADY_COMPLETED]", "录音校验已经完成。", 409
            )
        if not (
            context.state
            in {
                AudioSubmissionState.UPLOADED.value,
                AudioSubmissionState.VALIDATING.value,
            }
            or (
                context.state == AudioSubmissionState.FAILED_RECOVERABLE.value
                and context.failed_stage == "validation"
            )
        ):
            self._state_conflict("校验")
        submission = await self._locked_submission(context.submission_id)
        upload = await self._session.scalar(
            select(AudioUploadSession)
            .where(AudioUploadSession.submission_id == submission.submission_id)
            .where(AudioUploadSession.state == "finalized")
            .order_by(desc(AudioUploadSession.finalized_at))
            .limit(1)
        )
        if upload is None:
            raise AudioAssessmentError(
                "[AUDIO_FINALIZED_UPLOAD_MISSING]",
                "录音上传尚未完成。",
                409,
            )
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
        if len(parts) != upload.expected_part_count:
            raise AudioAssessmentError(
                "[AUDIO_UPLOAD_INCOMPLETE]",
                "录音分片清单不完整。",
                409,
            )
        submission.state = AudioSubmissionState.VALIDATING.value
        submission.failed_stage = None
        submission.error_classification = None
        submission.error_retryable = None
        submission.safe_error_message = None
        submission.version += 1
        await self._session.flush([submission])
        return _ValidationPlan(
            context=context,
            upload_session_id=upload.upload_session_id,
            object_keys=tuple(item.object_key for item in parts),
            declared_parts=tuple(
                (
                    item.part_number,
                    item.declared_size_bytes,
                    item.declared_sha256,
                )
                for item in parts
            ),
            declared_total_size=upload.declared_size_bytes,
            declared_duration=float(upload.declared_duration_seconds),
            content_type=upload.content_type,
        )

    async def apply_validation(
        self,
        *,
        plan: _ValidationPlan,
        actual_parts: tuple[tuple[int, int, str], ...],
        full_sha256: str,
        full_size_bytes: int,
    ) -> str:
        submission = await self._locked_submission(plan.context.submission_id)
        if submission.original_artifact_id:
            artifact = await self._session.get(
                AudioArtifact, submission.original_artifact_id
            )
            if artifact is not None:
                return artifact.artifact_id
        if submission.state != AudioSubmissionState.VALIDATING.value:
            self._state_conflict("保存校验结果")
        if actual_parts != plan.declared_parts:
            raise AudioAssessmentError(
                "[AUDIO_OBJECT_INTEGRITY_MISMATCH]",
                "服务器校验发现上传分片与本地草稿不一致，请重新上传。",
                422,
            )
        if full_size_bytes != plan.declared_total_size:
            raise AudioAssessmentError(
                "[AUDIO_OBJECT_SIZE_MISMATCH]",
                "服务器校验发现录音大小不一致，请重新上传。",
                422,
            )
        parts = (
            (
                await self._session.execute(
                    select(AudioUploadPart)
                    .where(AudioUploadPart.upload_session_id == plan.upload_session_id)
                    .order_by(AudioUploadPart.part_number)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        now = datetime_now()
        for row, actual in zip(parts, actual_parts, strict=True):
            _, size_bytes, sha256 = actual
            row.actual_size_bytes = size_bytes
            row.actual_sha256 = sha256
            row.verified_at = now
        artifact_id = new_id()
        artifact = AudioArtifact(
            artifact_id=artifact_id,
            submission_id=submission.submission_id,
            organization_id=plan.context.organization_id,
            kind="original",
            artifact_ref=f"artifact://audio/manifest/{artifact_id}",
            storage_backend="multipart-manifest",
            manifest_json={
                "upload_session_id": plan.upload_session_id,
                "object_keys": list(plan.object_keys),
            },
            content_sha256=full_sha256,
            size_bytes=full_size_bytes,
            content_type=plan.content_type,
            duration_seconds=plan.declared_duration,
            created_by=plan.context.learner_id,
        )
        self._session.add(artifact)
        submission.original_artifact_id = artifact.artifact_id
        submission.state = AudioSubmissionState.NORMALIZING.value
        submission.version += 1
        await self._session.flush([artifact, submission, *parts])
        return artifact.artifact_id

    async def prepare_normalization(
        self, *, submission_id: str, task_id: str
    ) -> _NormalizationPlan:
        context = await self.context(submission_id=submission_id, task_id=task_id)
        if not (
            context.state == AudioSubmissionState.NORMALIZING.value
            or (
                context.state == AudioSubmissionState.FAILED_RECOVERABLE.value
                and context.failed_stage == "normalization"
            )
        ):
            self._state_conflict("标准化")
        submission = await self._locked_submission(context.submission_id)
        if not submission.original_artifact_id:
            raise AudioAssessmentError(
                "[AUDIO_ORIGINAL_ARTIFACT_MISSING]",
                "录音原始文件引用缺失。",
                409,
            )
        original = await self._session.get(
            AudioArtifact, submission.original_artifact_id
        )
        if original is None:
            raise AudioAssessmentError(
                "[AUDIO_ORIGINAL_ARTIFACT_MISSING]",
                "录音原始文件引用缺失。",
                409,
            )
        object_keys = tuple(
            str(item) for item in original.manifest_json.get("object_keys", [])
        )
        if not object_keys:
            raise AudioAssessmentError(
                "[AUDIO_ORIGINAL_MANIFEST_INVALID]",
                "录音原始分片清单无效。",
                409,
            )
        scoring = AudioScoringSchemeSnapshot.model_validate(
            context.config_snapshot["scoring_scheme"]
        )
        submission.state = AudioSubmissionState.NORMALIZING.value
        submission.failed_stage = None
        submission.version += 1
        await self._session.flush([submission])
        return _NormalizationPlan(
            context=context,
            original_artifact_id=original.artifact_id,
            object_keys=object_keys,
            content_type=original.content_type,
            max_duration_seconds=scoring.capture.max_duration_seconds,
        )

    async def apply_normalization(
        self,
        *,
        plan: _NormalizationPlan,
        stored: Any,
        inspection: AudioMediaInspection,
        tool_version: str,
    ) -> str:
        submission = await self._locked_submission(plan.context.submission_id)
        if submission.normalized_artifact_id:
            artifact = await self._session.get(
                AudioArtifact, submission.normalized_artifact_id
            )
            if artifact is not None:
                return artifact.artifact_id
        if submission.state != AudioSubmissionState.NORMALIZING.value:
            self._state_conflict("保存标准化结果")
        artifact = AudioArtifact(
            artifact_id=new_id(),
            submission_id=submission.submission_id,
            organization_id=plan.context.organization_id,
            kind="normalized",
            artifact_ref=stored.artifact_ref,
            storage_backend=stored.artifact_ref.split("/")[3],
            manifest_json={
                "object_key": stored.object_key,
                "inspection": inspection.model_dump(mode="json"),
            },
            content_sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            content_type=stored.content_type,
            duration_seconds=inspection.duration_seconds,
            sample_rate_hz=16_000,
            channels=1,
            tool_version=tool_version,
            created_by="audio-pipeline",
        )
        self._session.add(artifact)
        submission.normalized_artifact_id = artifact.artifact_id
        submission.state = AudioSubmissionState.TRANSCRIBING.value
        submission.version += 1
        await self._session.flush([artifact, submission])
        return artifact.artifact_id

    async def prepare_transcription(
        self, *, submission_id: str, task_id: str, mode: str
    ) -> _TranscriptionPlan | AudioTranscriptRevision:
        context = await self.context(
            submission_id=submission_id,
            task_id=task_id,
            allow_completed=mode in {"retranscribe", "regrade"},
        )
        submission = await self._locked_submission(context.submission_id)
        if (
            mode not in {"retranscribe"}
            and submission.current_transcript_revision_id is not None
        ):
            existing = await self._session.get(
                AudioTranscriptRevision,
                submission.current_transcript_revision_id,
            )
            if existing is not None:
                return existing
        if not submission.normalized_artifact_id:
            raise AudioAssessmentError(
                "[AUDIO_NORMALIZED_ARTIFACT_MISSING]",
                "录音标准化文件引用缺失。",
                409,
            )
        artifact = await self._session.get(
            AudioArtifact, submission.normalized_artifact_id
        )
        if artifact is None:
            raise AudioAssessmentError(
                "[AUDIO_NORMALIZED_ARTIFACT_MISSING]",
                "录音标准化文件引用缺失。",
                409,
            )
        if not (
            submission.state
            in {
                AudioSubmissionState.TRANSCRIBING.value,
                AudioSubmissionState.TRANSCRIPT_READY.value,
                AudioSubmissionState.COMPLETED.value,
            }
            or (
                submission.state == AudioSubmissionState.FAILED_RECOVERABLE.value
                and submission.failed_stage == "transcription"
            )
        ):
            self._state_conflict("转写")
        scoring = AudioScoringSchemeSnapshot.model_validate(
            context.config_snapshot["scoring_scheme"]
        )
        asr = scoring.asr
        submission.state = AudioSubmissionState.TRANSCRIBING.value
        submission.failed_stage = None
        submission.version += 1
        await self._session.flush([submission])
        return _TranscriptionPlan(
            context=context,
            normalized_artifact_id=artifact.artifact_id,
            request=GovernedAIRequest(
                business_purpose=asr.business_purpose,
                task_id=task_id,
                workload_kind=AIWorkloadKind.ASR,
                organization_id=context.organization_id,
                actor_id=context.learner_id,
                object_type="audio_submission",
                object_id=context.submission_id,
                asr_profile_revision_id=asr.model_routing_revision_id,
                input_artifact_ref=artifact.artifact_ref,
                model_routing_profile_id=asr.model_routing_profile_id,
                model_routing_revision_id=asr.model_routing_revision_id,
                input_schema_version=asr.input_schema_version,
                output_schema_version=asr.output_schema_version,
                input_payload={
                    "audio_artifact_ref": artifact.artifact_ref,
                    "language": scoring.language,
                },
                idempotency_key=(
                    f"audio-transcript:{context.submission_id}:"
                    f"{submission.processing_generation}"
                ),
                data_classification=DataClassification.CONFIDENTIAL,
                trace_id=task_id,
                correlation_id=context.attempt_id,
                causation_id=artifact.artifact_id,
                runtime_consumer="audio_assessment.transcription.v1",
                timeout_policy_ref=asr.timeout_policy_ref,
                retry_policy_ref=asr.retry_policy_ref,
                budget_scope=BudgetScope.ORGANIZATION,
                formal_scoring=False,
                allow_fallback=True,
            ),
        )

    async def apply_transcription(
        self,
        *,
        plan: _TranscriptionPlan,
        result: AIInvocationResult,
        source: str,
    ) -> tuple[AudioTranscriptRevision, AudioQualityReport]:
        self._require_ai_success(result, stage="transcription")
        assert result.validated_output is not None
        try:
            output = AudioTranscriptAIOutput.model_validate(result.validated_output)
        except ValidationError as exc:
            raise AudioAssessmentError(
                "[AUDIO_TRANSCRIPTION_SCHEMA_INVALID]",
                "转写服务返回内容暂时无法使用，录音已经保留，可稍后重试。",
                503,
                details={
                    "retryable": True,
                    "classification": "schema_validation",
                },
            ) from exc
        submission = await self._locked_submission(plan.context.submission_id)
        replay = await self._session.scalar(
            select(AudioTranscriptRevision)
            .where(AudioTranscriptRevision.submission_id == submission.submission_id)
            .where(AudioTranscriptRevision.ai_invocation_id == result.invocation_id)
            .limit(1)
        )
        if replay is not None:
            quality = await self._session.scalar(
                select(AudioQualityReport)
                .where(AudioQualityReport.transcript_revision_id == replay.revision_id)
                .limit(1)
            )
            assert quality is not None
            return replay, quality
        artifact = await self._session.get(AudioArtifact, plan.normalized_artifact_id)
        if artifact is None:
            raise AudioAssessmentError(
                "[AUDIO_NORMALIZED_ARTIFACT_MISSING]",
                "录音标准化文件引用缺失。",
                409,
            )
        segments = output.segments
        if not segments:
            segments = (
                TranscriptSegment(
                    sequence=1,
                    start_ms=0,
                    end_ms=int(float(artifact.duration_seconds) * 1_000),
                    text=output.transcript,
                    confidence=output.confidence,
                ),
            )
        revision_no = (
            int(
                await self._session.scalar(
                    select(func.count(AudioTranscriptRevision.revision_id)).where(
                        AudioTranscriptRevision.submission_id
                        == submission.submission_id
                    )
                )
                or 0
            )
            + 1
        )
        prior_id = submission.current_transcript_revision_id
        revision = AudioTranscriptRevision(
            revision_id=new_id(),
            submission_id=submission.submission_id,
            organization_id=plan.context.organization_id,
            revision_no=revision_no,
            source=source,
            artifact_id=artifact.artifact_id,
            transcript_text=output.transcript,
            segments_json=[item.model_dump(mode="json") for item in segments],
            confidence=output.confidence,
            language=output.language,
            provider_summary_json={
                "provider": result.provider,
                "model": result.model,
                "finish_reason": result.finish_reason,
                "degradations": list(result.degradations),
            },
            ai_invocation_id=result.invocation_id,
            status="valid",
            supersedes_revision_id=prior_id,
            created_by="audio-pipeline",
        )
        self._session.add(revision)
        # Persist the transcript before creating records that reference it.  These
        # models have no ORM relationship, so PostgreSQL cannot rely on SQLAlchemy
        # to order the parent and child inserts during autoflush.
        await self._session.flush([revision])
        scoring = AudioScoringSchemeSnapshot.model_validate(
            plan.context.config_snapshot["scoring_scheme"]
        )
        inspection = AudioMediaInspection.model_validate(
            artifact.manifest_json["inspection"]
        )
        flags = self._quality_flags(
            scoring=scoring,
            inspection=inspection,
            transcript=output,
        )
        quality = AudioQualityReport(
            report_id=new_id(),
            submission_id=submission.submission_id,
            transcript_revision_id=revision.revision_id,
            organization_id=plan.context.organization_id,
            metrics_json={
                **inspection.model_dump(mode="json"),
                "asr_confidence": output.confidence,
                "language": output.language,
            },
            quality_flags_json=flags,
            scorable=not flags,
            algorithm_version="audio-quality-v1",
        )
        self._session.add(quality)
        submission.current_transcript_revision_id = revision.revision_id
        submission.state = (
            AudioSubmissionState.TRANSCRIPT_READY.value
            if quality.scorable
            else AudioSubmissionState.NEEDS_REVIEW.value
        )
        submission.error_classification = None if quality.scorable else "audio_quality"
        submission.error_retryable = False if not quality.scorable else None
        submission.safe_error_message = (
            None
            if quality.scorable
            else "录音质量或转写置信度不足，已保留录音，请重录或申请人工处理。"
        )
        submission.version += 1
        run = await self._session.get(AudioActivityRun, submission.run_id)
        assert run is not None
        if not quality.scorable:
            run.status = "needs_review"
            run.version += 1
        await self._session.flush([quality, submission, run])
        return revision, quality

    async def prepare_scoring(
        self,
        *,
        submission_id: str,
        task_id: str,
        target_transcript_revision_id: str | None = None,
        target_scoring_scheme_revision_id: str | None = None,
    ) -> _ScoringPlan | AudioScoreOutcomeVersion:
        context = await self.context(
            submission_id=submission_id,
            task_id=task_id,
            allow_completed=True,
        )
        submission = await self._locked_submission(context.submission_id)
        transcript_id = (
            target_transcript_revision_id or submission.current_transcript_revision_id
        )
        if not transcript_id:
            raise AudioAssessmentError(
                "[AUDIO_TRANSCRIPT_REQUIRED]",
                "录音尚无可评分的转写修订。",
                409,
            )
        transcript = await self._session.get(AudioTranscriptRevision, transcript_id)
        if (
            transcript is None
            or transcript.submission_id != submission.submission_id
            or transcript.status != "valid"
        ):
            raise AudioAssessmentError(
                "[AUDIO_TRANSCRIPT_UNAVAILABLE]",
                "指定转写修订不可用于评分。",
                409,
            )
        quality = await self._session.scalar(
            select(AudioQualityReport)
            .where(AudioQualityReport.transcript_revision_id == transcript.revision_id)
            .limit(1)
        )
        if quality is None or not quality.scorable:
            raise AudioAssessmentError(
                "[AUDIO_NOT_SCORABLE]",
                "录音质量不足，不能按能力未达标计分。",
                409,
            )
        if (
            target_transcript_revision_id is None
            and target_scoring_scheme_revision_id is None
            and submission.state == AudioSubmissionState.COMPLETED.value
            and submission.current_score_outcome_version_id is not None
        ):
            current = await self._session.get(
                AudioScoreOutcomeVersion,
                submission.current_score_outcome_version_id,
            )
            if (
                current is not None
                and current.status == "valid"
                and current.transcript_revision_id == transcript.revision_id
            ):
                return current
        scoring_revision_id = str(
            context.config_snapshot["scoring_scheme_revision"]["revision_id"]
        )
        scoring = AudioScoringSchemeSnapshot.model_validate(
            context.config_snapshot["scoring_scheme"]
        )
        if target_scoring_scheme_revision_id is not None:
            revision = await self._session.get(
                AudioActivityResourceRevision,
                target_scoring_scheme_revision_id,
            )
            if (
                revision is None
                or revision.organization_id != context.organization_id
                or revision.resource_type != "scoring_scheme"
                or revision.status not in {"published", "archived"}
            ):
                raise AudioAssessmentError(
                    "[AUDIO_SCORING_SCHEME_UNAVAILABLE]",
                    "指定评分方案不可用于本次重评。",
                    422,
                )
            scoring = AudioScoringSchemeSnapshot.model_validate(revision.snapshot_json)
            scoring_revision_id = revision.revision_id
        contract = scoring.scoring
        submission.state = AudioSubmissionState.SCORING.value
        submission.failed_stage = None
        submission.version += 1
        await self._session.flush([submission])
        content = context.config_snapshot["content_revision"]["snapshot"]
        scenario: dict[str, Any]
        if context.activity_type == "assignment":
            scenario = next(
                dict(item)
                for item in content["segments"]
                if item["segment_id"] == context.segment_id
            )
        else:
            scenario = dict(content)
        scoring_input = AudioScoringAIInput(
            submission_id=submission.submission_id,
            activity_type=context.activity_type,
            segment_id=context.segment_id,
            scenario=scenario,
            transcript_revision_id=transcript.revision_id,
            transcript=transcript.transcript_text,
            transcript_segments=tuple(
                TranscriptSegment.model_validate(item)
                for item in transcript.segments_json
            ),
            quality_summary=dict(quality.metrics_json),
            dimensions=tuple(
                item.model_dump(mode="json") for item in scoring.dimensions
            ),
            allowed_knowledge=scoring.allowed_knowledge,
        )
        input_payload = scoring_input.model_dump(mode="json")
        assert contract.prompt_template_id is not None
        assert contract.prompt_revision_id is not None
        prompt_variables = {
            "submission_id": context.submission_id,
            "activity_type": context.activity_type,
            "segment_id": context.segment_id,
            "scenario_json": _canonical_json(scenario),
            "transcript": transcript.transcript_text,
            "segments_json": _canonical_json(transcript.segments_json),
            "quality_json": _canonical_json(quality.metrics_json),
            "dimensions_json": _canonical_json(input_payload["dimensions"]),
            "allowed_knowledge_json": _canonical_json(
                input_payload["allowed_knowledge"]
            ),
        }
        try:
            compiled = await self._prompt_compiler.preview(
                PromptPreviewRequest(
                    template_id=contract.prompt_template_id,
                    revision_id=contract.prompt_revision_id,
                    business_purpose=contract.business_purpose,
                    input_schema_version=contract.input_schema_version,
                    output_schema_version=contract.output_schema_version,
                    variables=prompt_variables,
                    runtime_consumer="audio_assessment.scoring.v1",
                    model_routing_revision_id=contract.model_routing_revision_id,
                )
            )
        except AIPlatformError as exc:
            raise AudioAssessmentError(
                "[AUDIO_SCORING_PROMPT_UNAVAILABLE]",
                "评分规则暂时无法编译，录音和转写已经保留，可由管理员修复后重试。",
                503,
                details={
                    "retryable": True,
                    "classification": exc.classification.value,
                },
            ) from exc
        request = GovernedAIRequest(
            business_purpose=contract.business_purpose,
            task_id=task_id,
            organization_id=context.organization_id,
            actor_id=context.learner_id,
            object_type="audio_submission",
            object_id=context.submission_id,
            prompt_template_id=contract.prompt_template_id,
            prompt_revision_id=contract.prompt_revision_id,
            prompt_contract_hash=compiled.contract_hash,
            model_routing_profile_id=contract.model_routing_profile_id,
            model_routing_revision_id=contract.model_routing_revision_id,
            input_schema_version=contract.input_schema_version,
            output_schema_version=contract.output_schema_version,
            input_payload=input_payload,
            prompt_variables=prompt_variables,
            idempotency_key=(
                f"audio-score:{context.submission_id}:{transcript.revision_id}:"
                f"{submission.processing_generation}"
            ),
            data_classification=DataClassification.CONFIDENTIAL,
            trace_id=task_id,
            correlation_id=context.attempt_id,
            causation_id=transcript.revision_id,
            runtime_consumer="audio_assessment.scoring.v1",
            timeout_policy_ref=contract.timeout_policy_ref,
            retry_policy_ref=contract.retry_policy_ref,
            budget_scope=BudgetScope.ORGANIZATION,
            formal_scoring=True,
            allow_fallback=True,
        )
        return _ScoringPlan(
            context=context,
            transcript_revision_id=transcript.revision_id,
            quality_report_id=quality.report_id,
            scoring_scheme=scoring,
            scoring_scheme_revision_id=scoring_revision_id,
            request=request,
        )

    async def apply_scoring(
        self,
        *,
        plan: _ScoringPlan,
        result: AIInvocationResult,
        requested_by: str,
    ) -> AudioScoreOutcomeVersion:
        self._require_ai_success(result, stage="scoring")
        assert result.validated_output is not None
        try:
            output = AudioScoringAIOutput.model_validate(result.validated_output)
        except ValidationError as exc:
            raise AudioAssessmentError(
                "[AUDIO_SCORING_SCHEMA_INVALID]",
                "评分服务返回内容暂时无法使用，录音和转写已经保留，可稍后重试。",
                503,
                details={
                    "retryable": True,
                    "classification": "schema_validation",
                },
            ) from exc
        submission = await self._locked_submission(plan.context.submission_id)
        replay = await self._session.scalar(
            select(AudioScoreOutcomeVersion)
            .where(AudioScoreOutcomeVersion.submission_id == submission.submission_id)
            .where(AudioScoreOutcomeVersion.ai_invocation_id == result.invocation_id)
            .limit(1)
        )
        if replay is not None:
            return replay
        transcript = await self._session.get(
            AudioTranscriptRevision, plan.transcript_revision_id
        )
        assert transcript is not None
        scoring = plan.scoring_scheme
        expected_dimensions = {item.key: item for item in scoring.dimensions}
        received = {item.dimension_key: item for item in output.dimension_scores}
        if set(received) != set(expected_dimensions):
            raise AudioAssessmentError(
                "[AUDIO_SCORING_DIMENSIONS_INVALID]",
                "评分结果维度与已发布评分方案不一致。",
                503,
                details={"retryable": True},
            )
        if any(
            span.quote not in transcript.transcript_text
            for span in output.evidence_spans
        ):
            raise AudioAssessmentError(
                "[AUDIO_SCORING_EVIDENCE_INVALID]",
                "评分证据无法追溯到当前转写修订。",
                503,
                details={"retryable": True},
            )
        total = sum(
            received[key].score * dimension.weight
            for key, dimension in expected_dimensions.items()
        )
        dimension_pass = all(
            dimension.minimum_score is None
            or received[key].score >= dimension.minimum_score
            for key, dimension in expected_dimensions.items()
        )
        passed = (
            total >= scoring.pass_score and dimension_pass and not output.critical_flags
        )
        version_no = (
            int(
                await self._session.scalar(
                    select(
                        func.count(AudioScoreOutcomeVersion.outcome_version_id)
                    ).where(
                        AudioScoreOutcomeVersion.submission_id
                        == submission.submission_id
                    )
                )
                or 0
            )
            + 1
        )
        prior = submission.current_score_outcome_version_id
        contract = scoring.scoring
        assert contract.prompt_revision_id is not None
        assert plan.request.prompt_contract_hash is not None
        version = AudioScoreOutcomeVersion(
            outcome_version_id=new_id(),
            submission_id=submission.submission_id,
            organization_id=plan.context.organization_id,
            version_no=version_no,
            transcript_revision_id=transcript.revision_id,
            scoring_scheme_revision_id=plan.scoring_scheme_revision_id,
            prompt_revision_id=contract.prompt_revision_id,
            prompt_contract_hash=plan.request.prompt_contract_hash,
            model_routing_revision_id=contract.model_routing_revision_id,
            ai_invocation_id=result.invocation_id,
            dimension_scores_json=[
                item.model_dump(mode="json") for item in output.dimension_scores
            ],
            evidence_spans_json=[
                item.model_dump(mode="json") for item in output.evidence_spans
            ],
            missing_points_json=list(output.missing_points),
            feedback_json=list(output.feedback),
            remediation_json=list(output.recommended_remediation),
            critical_flags_json=list(output.critical_flags),
            deterministic_metrics_json={
                "weighted_total": total,
                "pass_score": scoring.pass_score,
                "dimension_minimums_met": dimension_pass,
            },
            total_score=total,
            passed=passed,
            uncertainty=output.uncertainty,
            status="valid",
            supersedes_outcome_version_id=prior,
            review_trace_json={
                "requested_by": requested_by,
                "task_id": plan.context.task_id,
                "mode": "regrade" if prior else "initial",
            },
            created_by=requested_by,
        )
        self._session.add(version)
        submission.current_score_outcome_version_id = version.outcome_version_id
        submission.state = AudioSubmissionState.RECONCILING.value
        submission.version += 1
        await self._session.flush([version, submission])
        return version

    async def reconcile(
        self,
        *,
        submission_id: str,
        task_id: str,
        requested_by: str,
    ) -> tuple[AudioPipelineTaskResult, bool]:
        context = await self.context(
            submission_id=submission_id,
            task_id=task_id,
            allow_completed=True,
        )
        submission = await self._locked_submission(context.submission_id)
        if not submission.current_score_outcome_version_id:
            raise AudioAssessmentError(
                "[AUDIO_SCORE_VERSION_REQUIRED]",
                "录音评分结果尚未生成。",
                409,
            )
        current_score = await self._session.get(
            AudioScoreOutcomeVersion,
            submission.current_score_outcome_version_id,
        )
        if current_score is None or current_score.status != "valid":
            raise AudioAssessmentError(
                "[AUDIO_SCORE_VERSION_UNAVAILABLE]",
                "录音评分结果不可用于对账。",
                409,
            )
        now = datetime_now()
        submission_changed = (
            submission.state != AudioSubmissionState.COMPLETED.value
            or submission.completed_at is None
            or submission.failed_stage is not None
            or submission.error_classification is not None
            or submission.error_retryable is not None
            or submission.safe_error_message is not None
        )
        submission.state = AudioSubmissionState.COMPLETED.value
        submission.completed_at = submission.completed_at or now
        submission.failed_stage = None
        submission.error_classification = None
        submission.error_retryable = None
        submission.safe_error_message = None
        if submission_changed:
            submission.version += 1
        run = await self._session.scalar(
            select(AudioActivityRun)
            .where(AudioActivityRun.run_id == submission.run_id)
            .with_for_update()
            .limit(1)
        )
        assert run is not None
        siblings = (
            (
                await self._session.execute(
                    select(AudioSubmission)
                    .where(AudioSubmission.run_id == run.run_id)
                    .order_by(AudioSubmission.created_at)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        ready = all(item.current_score_outcome_version_id for item in siblings)
        if not ready:
            if run.status != "processing":
                run.status = "processing"
                run.version += 1
            await self._session.flush([submission, run])
            return (
                AudioPipelineTaskResult(
                    submission_id=submission.submission_id,
                    run_id=run.run_id,
                    state=submission.state,
                    transcript_revision_id=submission.current_transcript_revision_id,
                    score_outcome_version_id=current_score.outcome_version_id,
                ),
                False,
            )
        scores: list[AudioScoreOutcomeVersion] = []
        transcripts: list[AudioTranscriptRevision] = []
        for item in siblings:
            score = await self._session.get(
                AudioScoreOutcomeVersion,
                item.current_score_outcome_version_id,
            )
            transcript = await self._session.get(
                AudioTranscriptRevision,
                item.current_transcript_revision_id,
            )
            if score is None or transcript is None or score.status != "valid":
                raise AudioAssessmentError(
                    "[AUDIO_RECONCILIATION_LINEAGE_INVALID]",
                    "录音结果引用不完整，已保留结果等待修复。",
                    503,
                    details={"retryable": True},
                )
            scores.append(score)
            transcripts.append(transcript)
        average = sum(float(item.total_score) for item in scores) / len(scores)
        baseline_only = bool(
            run.config_snapshot_json["activity_config"].get("baseline_only", False)
        )
        passed = None if baseline_only else all(item.passed for item in scores)
        assessment_result = (
            "not_applicable"
            if baseline_only
            else ("passed" if passed else "not_passed")
        )
        generic_outcome_id = await self._outcomes.record(
            AudioOutcomePayload(
                organization_id=run.organization_id,
                actor_id=requested_by,
                attempt_id=run.attempt_id,
                result_type="audio_assessment_run",
                result_id=run.run_id,
                score=average,
                max_score=100,
                passed=passed,
                assessment_result=assessment_result,
                source_refs=tuple(
                    {
                        "resource_type": "audio_transcript_revision",
                        "resource_id": transcript.revision_id,
                    }
                    for transcript in transcripts
                ),
                lineage={
                    "path_revision_id": run.path_revision_id,
                    "audio_run_id": run.run_id,
                    "score_outcome_version_ids": [
                        item.outcome_version_id for item in scores
                    ],
                    "transcript_revision_ids": [
                        item.revision_id for item in transcripts
                    ],
                    "scoring_scheme_revision_ids": list(
                        dict.fromkeys(
                            item.scoring_scheme_revision_id for item in scores
                        )
                    ),
                    "competency_keys": list(run.competency_keys_json),
                    "baseline_only": baseline_only,
                    "regraded": any(item.version_no > 1 for item in scores),
                },
                confidence=max(
                    0.0,
                    min(1.0, 1 - max(float(item.uncertainty) for item in scores)),
                ),
                critical_flags=tuple(
                    dict.fromkeys(
                        flag for item in scores for flag in item.critical_flags_json
                    )
                ),
                next_action=(
                    None
                    if baseline_only or passed
                    else {
                        "type": "remediation",
                        "competency_keys": list(run.competency_keys_json),
                    }
                ),
                idempotency_key=(
                    f"audio-outcome:{run.run_id}:"
                    f"{':'.join(item.outcome_version_id for item in scores)}"
                ),
                trace_id=task_id,
            )
        )
        for sibling in siblings:
            sibling_changed = (
                sibling.state != AudioSubmissionState.COMPLETED.value
                or sibling.completed_at is None
                or sibling.failed_stage is not None
                or sibling.error_classification is not None
                or sibling.error_retryable is not None
                or sibling.safe_error_message is not None
            )
            if sibling_changed:
                sibling.version += 1
            sibling.state = AudioSubmissionState.COMPLETED.value
            sibling.completed_at = sibling.completed_at or now
            sibling.failed_stage = None
            sibling.error_classification = None
            sibling.error_retryable = None
            sibling.safe_error_message = None
        if run.status != "completed" or run.completed_at is None:
            run.status = "completed"
            run.completed_at = run.completed_at or now
            run.version += 1
        await self._session.flush([submission, run, *siblings])
        return (
            AudioPipelineTaskResult(
                submission_id=submission.submission_id,
                run_id=run.run_id,
                state=AudioSubmissionState.COMPLETED.value,
                transcript_revision_id=submission.current_transcript_revision_id,
                score_outcome_version_id=current_score.outcome_version_id,
                generic_outcome_id=generic_outcome_id,
            ),
            True,
        )

    async def mark_failed(
        self,
        *,
        submission_id: str,
        task_id: str,
        stage: str,
        classification: str,
        retryable: bool,
        safe_message: str,
    ) -> None:
        context = await self.context(
            submission_id=submission_id,
            task_id=task_id,
            allow_completed=True,
        )
        submission = await self._locked_submission(context.submission_id)
        if submission.state in {
            AudioSubmissionState.COMPLETED.value,
            AudioSubmissionState.CANCELLED.value,
            AudioSubmissionState.INVALIDATED.value,
        }:
            return
        submission.state = (
            AudioSubmissionState.FAILED_RECOVERABLE.value
            if retryable
            else AudioSubmissionState.FAILED_TERMINAL.value
        )
        submission.failed_stage = stage
        submission.error_classification = classification
        submission.error_retryable = retryable
        submission.safe_error_message = safe_message
        submission.version += 1
        run = await self._session.get(AudioActivityRun, submission.run_id)
        assert run is not None
        run.status = "processing" if retryable else "failed"
        run.version += 1
        await self._session.flush([submission, run])

    @staticmethod
    def _quality_flags(
        *,
        scoring: AudioScoringSchemeSnapshot,
        inspection: AudioMediaInspection,
        transcript: AudioTranscriptAIOutput,
    ) -> list[str]:
        policy = scoring.quality
        flags: list[str] = []
        if transcript.confidence < policy.minimum_asr_confidence:
            flags.append("low_asr_confidence")
        if inspection.speech_ratio < policy.minimum_speech_ratio:
            flags.append("insufficient_speech")
        if inspection.silence_ratio > policy.maximum_silence_ratio:
            flags.append("excessive_silence")
        if inspection.clipping_ratio > policy.maximum_clipping_ratio:
            flags.append("audio_clipping")
        if inspection.mean_volume_db < policy.minimum_mean_volume_db:
            flags.append("volume_too_low")
        if transcript.language.lower() != scoring.language.lower():
            flags.append("language_mismatch")
        return flags

    @staticmethod
    def _require_ai_success(result: AIInvocationResult, *, stage: str) -> None:
        if result.status in {AIInvocationStatus.SUCCEEDED, AIInvocationStatus.PARTIAL}:
            return
        failure = result.failure
        retryable = bool(failure and failure.retryable)
        classification = (
            failure.classification.value
            if failure is not None
            else AIErrorClassification.UNKNOWN.value
        )
        raise AudioAssessmentError(
            f"[AUDIO_{stage.upper()}_AI_FAILED]",
            (
                "转写服务暂时不可用，录音已经保留，可稍后重试。"
                if stage == "transcription"
                else "评分服务暂时不可用，录音和转写已经保留，可稍后重试。"
            ),
            503 if retryable else 422,
            details={"retryable": retryable, "classification": classification},
        )

    async def _locked_submission(self, submission_id: str) -> AudioSubmission:
        row = await self._session.scalar(
            select(AudioSubmission)
            .where(AudioSubmission.submission_id == submission_id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )
        if row is None:
            self._not_found()
        assert row is not None
        return row

    @staticmethod
    def _not_found() -> None:
        raise AudioAssessmentError(
            "[AUDIO_SUBMISSION_NOT_FOUND]",
            "录音提交不存在或不可访问。",
            404,
        )

    @staticmethod
    def _state_conflict(stage: str) -> None:
        raise AudioAssessmentError(
            "[AUDIO_SUBMISSION_STATE_CONFLICT]",
            f"当前录音不能进入{stage}步骤。",
            409,
        )


class AudioPipelineTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ai_factory: Callable[[], AIInvocationPort],
        outcome_writer_factory: Callable[[AsyncSession], AudioOutcomeWriterPort],
        prompt_compiler: PromptCompilationService,
        storage: AudioObjectStoragePort,
        media: AudioMediaToolPort,
    ) -> None:
        self._session_factory = session_factory
        self._ai_factory = ai_factory
        self._outcome_writer_factory = outcome_writer_factory
        self._prompt_compiler = prompt_compiler
        self._storage = storage
        self._media = media

    async def execute(self, context: Any, payload: BaseModel) -> TaskCompletion:
        if not isinstance(payload, AudioPipelineTaskInput):
            raise TypeError("audio pipeline payload type mismatch")
        await context.report_progress(
            current=0,
            total=5,
            stage="validating",
            label="正在校验录音",
        )
        ai = self._ai_factory()
        try:
            result = await self._run(context, payload, ai)
        except (AudioAssessmentError, AudioStorageError) as exc:
            await self._persist_failure(context, payload, exc)
            retryable = self._retryable(exc)
            if retryable:
                raise TaskExecutionError(
                    code=self._safe_code(exc),
                    message=self._safe_message(exc),
                    kind=TaskFailureKind.PROVIDER_TEMPORARY,
                ) from exc
            return TaskCompletion(
                structured_payload=AudioPipelineTaskResult(
                    submission_id=payload.submission_id,
                    run_id=await self._run_id(payload.submission_id),
                    state=AudioSubmissionState.FAILED_TERMINAL.value,
                ).model_dump(mode="json"),
                result_kind=TaskResultKind.PARTIAL_SUCCESS,
                resource_type="audio_submission",
                resource_id=payload.submission_id,
                location=await self._location(payload.submission_id),
            )
        return TaskCompletion(
            structured_payload=result.model_dump(mode="json"),
            result_kind=(
                TaskResultKind.WAITING_INPUT
                if result.state == AudioSubmissionState.NEEDS_REVIEW.value
                else TaskResultKind.COMPLETE
            ),
            resource_type="audio_submission",
            resource_id=payload.submission_id,
            location=await self._location(payload.submission_id),
        )

    async def _run(
        self,
        context: Any,
        payload: AudioPipelineTaskInput,
        ai: AIInvocationPort,
    ) -> AudioPipelineTaskResult:
        task_id = str(context.claim.task_id)
        current = await self._context(
            payload.submission_id,
            task_id,
            ai,
        )
        if current.state in {
            AudioSubmissionState.UPLOADED.value,
            AudioSubmissionState.VALIDATING.value,
        } or (
            current.state == AudioSubmissionState.FAILED_RECOVERABLE.value
            and current.failed_stage == "validation"
        ):
            await self._validate(context, payload, ai)
        await context.report_progress(
            current=1, total=5, stage="normalizing", label="正在准备音频"
        )
        current = await self._context(payload.submission_id, task_id, ai)
        if current.state == AudioSubmissionState.NORMALIZING.value or (
            current.state == AudioSubmissionState.FAILED_RECOVERABLE.value
            and current.failed_stage == "normalization"
        ):
            await self._normalize(context, payload, ai)
        await context.report_progress(
            current=2, total=5, stage="transcribing", label="正在转写录音"
        )
        current = await self._context(payload.submission_id, task_id, ai)
        if (
            payload.mode == "retranscribe"
            or current.state == AudioSubmissionState.TRANSCRIBING.value
            or (
                current.state == AudioSubmissionState.FAILED_RECOVERABLE.value
                and current.failed_stage == "transcription"
            )
        ):
            await self._transcribe(context, payload, ai)
        current = await self._context(payload.submission_id, task_id, ai)
        if current.state == AudioSubmissionState.NEEDS_REVIEW.value:
            return AudioPipelineTaskResult(
                submission_id=payload.submission_id,
                run_id=current.run_id,
                state=current.state,
            )
        await context.report_progress(
            current=3, total=5, stage="scoring", label="正在分析表现"
        )
        current = await self._context(payload.submission_id, task_id, ai)
        if current.state in {
            AudioSubmissionState.TRANSCRIPT_READY.value,
            AudioSubmissionState.SCORING.value,
            AudioSubmissionState.COMPLETED.value,
        } or (
            current.state == AudioSubmissionState.FAILED_RECOVERABLE.value
            and current.failed_stage == "scoring"
        ):
            await self._score(context, payload, ai)
        await context.report_progress(
            current=4, total=5, stage="reconciling", label="正在保存训练结果"
        )
        await context.checkpoint()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            try:
                result, _ = await processor.reconcile(
                    submission_id=payload.submission_id,
                    task_id=task_id,
                    requested_by=payload.requested_by,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await context.report_progress(
            current=5, total=5, stage="completed", label="处理完成"
        )
        return result

    async def _validate(
        self, context: Any, payload: AudioPipelineTaskInput, ai: AIInvocationPort
    ) -> None:
        task_id = str(context.claim.task_id)
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            plan = await processor.prepare_validation(
                submission_id=payload.submission_id,
                task_id=task_id,
            )
            await session.commit()
        await context.checkpoint()
        actual_parts: list[tuple[int, int, str]] = []
        for part_number, size_bytes, sha256 in plan.declared_parts:
            metadata = await self._storage.head(plan.object_keys[part_number - 1])
            actual_parts.append((part_number, metadata.size_bytes, metadata.sha256))
            if metadata.size_bytes != size_bytes or metadata.sha256 != sha256:
                raise AudioStorageError(
                    "audio_object_integrity_mismatch",
                    "服务器校验发现上传分片不完整，请重新上传该分片。",
                    retryable=False,
                )
        with TemporaryDirectory(prefix="audio-validate-") as directory:
            raw_path = Path(directory) / "source.audio"
            await self._storage.materialize(plan.object_keys, raw_path)
            full_hash = await asyncio_to_thread(_sha256_file, raw_path)
            full_size = raw_path.stat().st_size
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            await processor.apply_validation(
                plan=plan,
                actual_parts=tuple(actual_parts),
                full_sha256=full_hash,
                full_size_bytes=full_size,
            )
            await session.commit()

    async def _normalize(
        self, context: Any, payload: AudioPipelineTaskInput, ai: AIInvocationPort
    ) -> None:
        task_id = str(context.claim.task_id)
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            plan = await processor.prepare_normalization(
                submission_id=payload.submission_id,
                task_id=task_id,
            )
            await session.commit()
        await context.checkpoint()
        with TemporaryDirectory(prefix="audio-normalize-") as directory:
            raw_path = Path(directory) / "source.audio"
            normalized_path = Path(directory) / "normalized.wav"
            await self._storage.materialize(plan.object_keys, raw_path)
            normalized = await self._media.inspect_and_normalize(
                source=raw_path,
                destination=normalized_path,
                declared_content_type=plan.content_type,
                max_duration_seconds=plan.max_duration_seconds,
            )
            normalized_hash = await asyncio_to_thread(_sha256_file, normalized.path)
            stored = await self._storage.store_file(
                object_key=(
                    f"audio-assessment/{_scope(plan.context.organization_id)}/"
                    f"{plan.context.submission_id}/normalized-v1.wav"
                ),
                source=normalized.path,
                content_type=normalized.content_type,
                sha256=normalized_hash,
            )
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            await processor.apply_normalization(
                plan=plan,
                stored=stored,
                inspection=normalized.inspection,
                tool_version=normalized.inspection.tool_version,
            )
            await session.commit()

    async def _transcribe(
        self, context: Any, payload: AudioPipelineTaskInput, ai: AIInvocationPort
    ) -> None:
        task_id = str(context.claim.task_id)
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            plan = await processor.prepare_transcription(
                submission_id=payload.submission_id,
                task_id=task_id,
                mode=payload.mode,
            )
            await session.commit()
        if isinstance(plan, AudioTranscriptRevision):
            return
        invocation = await ai.invoke(plan.request)
        await context.checkpoint()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            await processor.apply_transcription(
                plan=plan,
                result=invocation,
                source=(
                    "retranscription" if payload.mode == "retranscribe" else "automatic"
                ),
            )
            await session.commit()

    async def _score(
        self, context: Any, payload: AudioPipelineTaskInput, ai: AIInvocationPort
    ) -> None:
        task_id = str(context.claim.task_id)
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            plan = await processor.prepare_scoring(
                submission_id=payload.submission_id,
                task_id=task_id,
                target_transcript_revision_id=payload.target_transcript_revision_id,
                target_scoring_scheme_revision_id=(
                    payload.target_scoring_scheme_revision_id
                ),
            )
            await session.commit()
        if isinstance(plan, AudioScoreOutcomeVersion):
            return
        invocation = await ai.invoke(plan.request)
        await context.checkpoint()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            await processor.apply_scoring(
                plan=plan,
                result=invocation,
                requested_by=payload.requested_by,
            )
            await session.commit()

    async def _persist_failure(
        self,
        context: Any,
        payload: AudioPipelineTaskInput,
        exc: AudioAssessmentError | AudioStorageError,
    ) -> None:
        stage = await self._current_stage(payload.submission_id)
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            processor = AudioPipelineProcessor(
                session,
                ai=self._ai_factory(),
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            try:
                await processor.mark_failed(
                    submission_id=payload.submission_id,
                    task_id=str(context.claim.task_id),
                    stage=stage,
                    classification=self._classification(exc),
                    retryable=self._retryable(exc),
                    safe_message=self._safe_message(exc),
                )
                await session.commit()
            except AudioAssessmentError:
                await session.rollback()

    async def _context(
        self, submission_id: str, task_id: str, ai: AIInvocationPort
    ) -> _SubmissionContext:
        async with self._session_factory() as session:
            processor = AudioPipelineProcessor(
                session,
                ai=ai,
                outcomes=self._outcome_writer_factory(session),
                prompt_compiler=self._prompt_compiler,
            )
            result = await processor.context(
                submission_id=submission_id,
                task_id=task_id,
                allow_completed=True,
            )
            await session.rollback()
            return result

    async def _current_stage(self, submission_id: str) -> str:
        async with self._session_factory() as session:
            row = await session.get(AudioSubmission, submission_id)
            if row is None:
                return "validation"
            return {
                AudioSubmissionState.UPLOADED.value: "validation",
                AudioSubmissionState.VALIDATING.value: "validation",
                AudioSubmissionState.NORMALIZING.value: "normalization",
                AudioSubmissionState.TRANSCRIBING.value: "transcription",
                AudioSubmissionState.TRANSCRIPT_READY.value: "scoring",
                AudioSubmissionState.SCORING.value: "scoring",
                AudioSubmissionState.RECONCILING.value: "reconciliation",
            }.get(row.state, row.failed_stage or "validation")

    async def _run_id(self, submission_id: str) -> str:
        async with self._session_factory() as session:
            row = await session.get(AudioSubmission, submission_id)
            return row.run_id if row is not None else "unavailable"

    async def _location(self, submission_id: str) -> str:
        async with self._session_factory() as session:
            row = await session.get(AudioSubmission, submission_id)
            if row is None:
                return "/newcomer-training"
            run = await session.get(AudioActivityRun, row.run_id)
            return (
                f"/newcomer-training/activities/{run.activity_id}"
                if run is not None
                else "/newcomer-training"
            )

    @staticmethod
    def _retryable(exc: AudioAssessmentError | AudioStorageError) -> bool:
        if isinstance(exc, AudioStorageError):
            return exc.retryable
        return bool(exc.details and exc.details.get("retryable") is True) or (
            exc.status_code == 503
        )

    @staticmethod
    def _classification(exc: AudioAssessmentError | AudioStorageError) -> str:
        if isinstance(exc, AudioStorageError):
            return exc.code
        if exc.details and exc.details.get("classification"):
            return str(exc.details["classification"])
        return exc.code.strip("[]").lower()

    @staticmethod
    def _safe_code(exc: AudioAssessmentError | AudioStorageError) -> str:
        return (
            exc.code.strip("[]").lower()
            if isinstance(exc, AudioAssessmentError)
            else exc.code
        )

    @staticmethod
    def _safe_message(exc: AudioAssessmentError | AudioStorageError) -> str:
        return (
            exc.message if isinstance(exc, AudioAssessmentError) else exc.safe_message
        )


def datetime_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


async def asyncio_to_thread(function: Any, *args: Any) -> Any:
    return await asyncio.to_thread(function, *args)


def _scope(organization_id: str) -> str:
    return hashlib.sha256(organization_id.encode("utf-8")).hexdigest()[:16]


__all__ = ["AudioPipelineProcessor", "AudioPipelineTaskHandler"]

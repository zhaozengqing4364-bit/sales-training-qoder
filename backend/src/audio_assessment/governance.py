"""Audited transcript correction, regrade, and invalidation governance."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from audio_assessment.contracts import (
    AudioPipelineTaskInput,
    AudioScoringSchemeSnapshot,
    AudioSubmissionState,
    TranscriptSegment,
)
from audio_assessment.errors import AudioAssessmentError
from audio_assessment.models import (
    AudioActivityResourceRevision,
    AudioActivityRun,
    AudioArtifact,
    AudioChangePreview,
    AudioCommandAudit,
    AudioQualityReport,
    AudioScoreOutcomeVersion,
    AudioSubmission,
    AudioTranscriptRevision,
)
from audio_assessment.ports import (
    AudioAttemptInvalidationPort,
    AudioGovernanceActor,
)
from audio_assessment.runtime import AUDIO_PIPELINE_TASK_TYPE
from task_runtime.contracts import TaskCommand, TaskReference, TaskRuntimePort


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _hash(value: str) -> str:
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


class AudioChangePreviewResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    preview_token: str
    impact_hash: str
    expires_at: datetime
    change_type: Literal["transcript_correction", "regrade", "invalidation"]
    summary: dict[str, Any]


class AudioGovernanceResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: str
    run_id: str
    state: str
    task_id: str | None = None
    transcript_revision_id: str | None = None
    score_outcome_version_id: str | None = None


class AudioQueueItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    submission_id: str
    run_id: str
    activity_id: str
    learner_id: str
    segment_id: str
    state: str
    failed_stage: str | None
    retryable: bool | None
    safe_message: str | None
    updated_at: datetime


class AudioGovernanceService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        task_runtime: TaskRuntimePort,
        attempt_invalidator: AudioAttemptInvalidationPort,
    ) -> None:
        self._session = session
        self._tasks = task_runtime
        self._attempt_invalidator = attempt_invalidator

    async def list_queue(
        self,
        *,
        actor: AudioGovernanceActor,
        limit: int = 100,
    ) -> tuple[AudioQueueItem, ...]:
        self._require(actor, "newcomer.audio.review")
        rows = (
            await self._session.execute(
                select(AudioSubmission, AudioActivityRun)
                .join(
                    AudioActivityRun, AudioActivityRun.run_id == AudioSubmission.run_id
                )
                .where(AudioSubmission.organization_id == actor.organization_id)
                .where(
                    AudioSubmission.state.in_(
                        (
                            AudioSubmissionState.VALIDATING.value,
                            AudioSubmissionState.NORMALIZING.value,
                            AudioSubmissionState.TRANSCRIBING.value,
                            AudioSubmissionState.SCORING.value,
                            AudioSubmissionState.RECONCILING.value,
                            AudioSubmissionState.FAILED_RECOVERABLE.value,
                            AudioSubmissionState.FAILED_TERMINAL.value,
                            AudioSubmissionState.NEEDS_REVIEW.value,
                        )
                    )
                )
                .order_by(desc(AudioSubmission.updated_at))
                .limit(limit)
            )
        ).all()
        return tuple(
            AudioQueueItem(
                submission_id=submission.submission_id,
                run_id=run.run_id,
                activity_id=run.activity_id,
                learner_id=run.learner_id,
                segment_id=submission.segment_id,
                state=submission.state,
                failed_stage=submission.failed_stage,
                retryable=submission.error_retryable,
                safe_message=submission.safe_error_message,
                updated_at=submission.updated_at,
            )
            for submission, run in rows
        )

    async def repair_pipeline(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        reason: str,
        idempotency_key: str,
    ) -> AudioGovernanceResult:
        self._require(actor, "newcomer.audio.review")
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            self._reason_required()
        submission, run = await self._load(actor, submission_id, for_update=True)
        impact_hash = _canonical_hash(
            {
                "submission_id": submission_id,
                "command": "repair_audio_pipeline",
                "reason": cleaned_reason,
            }
        )
        replay = await self._audit_replay(
            actor=actor,
            submission_id=submission_id,
            command="repair_audio_pipeline",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
        )
        if replay is not None:
            return replay
        if submission.state == AudioSubmissionState.FAILED_RECOVERABLE.value:
            submission.state = {
                "validation": AudioSubmissionState.UPLOADED.value,
                "normalization": AudioSubmissionState.NORMALIZING.value,
                "transcription": AudioSubmissionState.TRANSCRIBING.value,
                "scoring": AudioSubmissionState.SCORING.value,
                "reconciliation": AudioSubmissionState.RECONCILING.value,
            }.get(submission.failed_stage or "", AudioSubmissionState.UPLOADED.value)
        elif submission.state != AudioSubmissionState.RECONCILING.value:
            raise AudioAssessmentError(
                "[AUDIO_PIPELINE_NOT_REPAIRABLE]",
                "当前录音没有可重试或对账的处理步骤。",
                409,
            )
        submission.processing_generation += 1
        submission.failed_stage = None
        submission.error_classification = None
        submission.error_retryable = None
        submission.safe_error_message = None
        submission.version += 1
        run.status = "processing"
        run.version += 1
        task = await self._enqueue(
            actor=actor,
            submission=submission,
            run=run,
            mode="retry",
            idempotency_key=idempotency_key,
            target_transcript_revision_id=None,
            target_scoring_scheme_revision_id=None,
        )
        submission.task_id = task.task_id
        await self._audit(
            actor=actor,
            submission=submission,
            command="repair_audio_pipeline",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
            reason=cleaned_reason,
            details={"task_id": task.task_id},
        )
        await self._session.flush([submission, run])
        return self._result(submission, run)

    async def preview_regrade(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        mode: Literal["regrade", "retranscribe"],
        target_scoring_scheme_revision_id: str | None,
        reason: str,
    ) -> AudioChangePreviewResult:
        self._require(actor, "newcomer.audio.regrade")
        submission, run = await self._load(actor, submission_id)
        if not reason.strip():
            self._reason_required()
        if mode == "regrade" and submission.current_transcript_revision_id is None:
            raise AudioAssessmentError(
                "[AUDIO_TRANSCRIPT_REQUIRED]",
                "当前录音尚无可用于重评的转写修订。",
                409,
            )
        if target_scoring_scheme_revision_id is not None:
            await self._require_scoring_scheme(
                actor.organization_id,
                target_scoring_scheme_revision_id,
            )
        request = {
            "mode": mode,
            "target_scoring_scheme_revision_id": (target_scoring_scheme_revision_id),
            "reason": reason.strip(),
        }
        return await self._create_preview(
            actor=actor,
            submission=submission,
            run=run,
            change_type="regrade",
            request=request,
            summary={
                "affected_submission_count": 1,
                "creates_new_score_version": True,
                "preserves_historical_result": True,
                "mode": mode,
            },
        )

    async def confirm_regrade(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        preview_token: str,
        impact_hash: str,
        idempotency_key: str,
    ) -> AudioGovernanceResult:
        self._require(actor, "newcomer.audio.regrade")
        replay = await self._audit_replay(
            actor=actor,
            submission_id=submission_id,
            command="regrade_audio_submission",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
        )
        if replay is not None:
            return replay
        submission, run = await self._load(actor, submission_id, for_update=True)
        preview = await self._consume_preview(
            actor=actor,
            submission=submission,
            run=run,
            change_type="regrade",
            preview_token=preview_token,
            impact_hash=impact_hash,
        )
        mode = str(preview.request_json["mode"])
        target_scheme = preview.request_json.get("target_scoring_scheme_revision_id")
        submission.processing_generation += 1
        submission.state = (
            AudioSubmissionState.TRANSCRIBING.value
            if mode == "retranscribe"
            else AudioSubmissionState.SCORING.value
        )
        submission.failed_stage = None
        submission.error_classification = None
        submission.error_retryable = None
        submission.safe_error_message = None
        submission.version += 1
        run.status = "processing"
        run.version += 1
        task = await self._enqueue(
            actor=actor,
            submission=submission,
            run=run,
            mode=mode,
            idempotency_key=idempotency_key,
            target_transcript_revision_id=(
                submission.current_transcript_revision_id if mode == "regrade" else None
            ),
            target_scoring_scheme_revision_id=(
                str(target_scheme) if target_scheme else None
            ),
        )
        submission.task_id = task.task_id
        await self._audit(
            actor=actor,
            submission=submission,
            command="regrade_audio_submission",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
            reason=str(preview.request_json["reason"]),
            details={"mode": mode, "task_id": task.task_id},
        )
        await self._session.flush([submission, run, preview])
        return self._result(submission, run)

    async def preview_transcript_correction(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        transcript: str,
        reason: str,
    ) -> AudioChangePreviewResult:
        self._require(actor, "newcomer.audio.transcript.correct")
        submission, run = await self._load(actor, submission_id)
        cleaned = transcript.strip()
        if not cleaned:
            raise AudioAssessmentError(
                "[AUDIO_TRANSCRIPT_REQUIRED]",
                "修订后的转写内容不能为空。",
                422,
            )
        if not reason.strip():
            self._reason_required()
        current = await self._current_transcript(submission)
        quality = await self._quality(current.revision_id)
        remaining_flags = [
            flag
            for flag in quality.quality_flags_json
            if flag not in {"low_asr_confidence", "language_mismatch"}
        ]
        if remaining_flags:
            raise AudioAssessmentError(
                "[AUDIO_MANUAL_CORRECTION_NOT_SCORABLE]",
                "录音本身仍存在质量问题，修订文字后也不能直接进入评分。",
                409,
            )
        return await self._create_preview(
            actor=actor,
            submission=submission,
            run=run,
            change_type="transcript_correction",
            request={"transcript": cleaned, "reason": reason.strip()},
            summary={
                "current_revision_id": current.revision_id,
                "creates_new_transcript_revision": True,
                "triggers_new_score_version": True,
            },
        )

    async def confirm_transcript_correction(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        preview_token: str,
        impact_hash: str,
        idempotency_key: str,
    ) -> AudioGovernanceResult:
        self._require(actor, "newcomer.audio.transcript.correct")
        replay = await self._audit_replay(
            actor=actor,
            submission_id=submission_id,
            command="correct_audio_transcript",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
        )
        if replay is not None:
            return replay
        submission, run = await self._load(actor, submission_id, for_update=True)
        preview = await self._consume_preview(
            actor=actor,
            submission=submission,
            run=run,
            change_type="transcript_correction",
            preview_token=preview_token,
            impact_hash=impact_hash,
        )
        current = await self._current_transcript(submission)
        quality = await self._quality(current.revision_id)
        artifact = await self._session.get(AudioArtifact, current.artifact_id)
        assert artifact is not None
        revision_no = current.revision_no + 1
        revision = AudioTranscriptRevision(
            revision_id=_id(),
            submission_id=submission.submission_id,
            organization_id=actor.organization_id,
            revision_no=revision_no,
            source="manual_correction",
            artifact_id=current.artifact_id,
            transcript_text=str(preview.request_json["transcript"]),
            segments_json=[
                TranscriptSegment(
                    sequence=1,
                    start_ms=0,
                    end_ms=int(float(artifact.duration_seconds) * 1_000),
                    text=str(preview.request_json["transcript"]),
                    confidence=1.0,
                ).model_dump(mode="json")
            ],
            confidence=1.0,
            language=current.language,
            provider_summary_json={"source": "human_review"},
            ai_invocation_id=None,
            status="valid",
            supersedes_revision_id=current.revision_id,
            reason=str(preview.request_json["reason"]),
            created_by=actor.actor_id,
        )
        report = AudioQualityReport(
            report_id=_id(),
            submission_id=submission.submission_id,
            transcript_revision_id=revision.revision_id,
            organization_id=actor.organization_id,
            metrics_json={**quality.metrics_json, "asr_confidence": 1.0},
            quality_flags_json=[],
            scorable=True,
            algorithm_version="audio-quality-manual-correction-v1",
        )
        self._session.add_all([revision, report])
        submission.current_transcript_revision_id = revision.revision_id
        submission.processing_generation += 1
        submission.state = AudioSubmissionState.SCORING.value
        submission.version += 1
        run.status = "processing"
        run.version += 1
        task = await self._enqueue(
            actor=actor,
            submission=submission,
            run=run,
            mode="regrade",
            idempotency_key=idempotency_key,
            target_transcript_revision_id=revision.revision_id,
            target_scoring_scheme_revision_id=None,
        )
        submission.task_id = task.task_id
        await self._audit(
            actor=actor,
            submission=submission,
            command="correct_audio_transcript",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
            reason=str(preview.request_json["reason"]),
            details={
                "transcript_revision_id": revision.revision_id,
                "task_id": task.task_id,
            },
        )
        await self._session.flush([submission, run, revision, report, preview])
        return self._result(submission, run)

    async def preview_invalidation(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        reason: str,
    ) -> AudioChangePreviewResult:
        self._require(actor, "newcomer.activity.invalidate")
        submission, run = await self._load(actor, submission_id)
        if not reason.strip():
            self._reason_required()
        return await self._create_preview(
            actor=actor,
            submission=submission,
            run=run,
            change_type="invalidation",
            request={"reason": reason.strip()},
            summary={
                "invalidates_run": True,
                "historical_versions_preserved": True,
            },
        )

    async def confirm_invalidation(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        preview_token: str,
        impact_hash: str,
        idempotency_key: str,
    ) -> AudioGovernanceResult:
        self._require(actor, "newcomer.activity.invalidate")
        replay = await self._audit_replay(
            actor=actor,
            submission_id=submission_id,
            command="invalidate_audio_run",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
        )
        if replay is not None:
            return replay
        submission, run = await self._load(actor, submission_id, for_update=True)
        preview = await self._consume_preview(
            actor=actor,
            submission=submission,
            run=run,
            change_type="invalidation",
            preview_token=preview_token,
            impact_hash=impact_hash,
        )
        siblings = (
            (
                await self._session.execute(
                    select(AudioSubmission)
                    .where(AudioSubmission.run_id == run.run_id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        now = _now()
        for sibling in siblings:
            if sibling.current_score_outcome_version_id:
                score = await self._session.get(
                    AudioScoreOutcomeVersion,
                    sibling.current_score_outcome_version_id,
                )
                if score is not None:
                    score.status = "invalidated"
            sibling.state = AudioSubmissionState.INVALIDATED.value
            sibling.invalidated_at = now
            sibling.version += 1
        run.status = "invalidated"
        run.invalidated_at = now
        run.version += 1
        await self._attempt_invalidator.invalidate(
            actor=actor,
            attempt_id=run.attempt_id,
            reason=str(preview.request_json["reason"]),
            idempotency_key=f"{idempotency_key}:attempt",
        )
        await self._audit(
            actor=actor,
            submission=submission,
            command="invalidate_audio_run",
            idempotency_key=idempotency_key,
            impact_hash=impact_hash,
            reason=str(preview.request_json["reason"]),
            details={"invalidated_submission_count": len(siblings)},
        )
        await self._session.flush([run, preview, *siblings])
        return self._result(submission, run)

    async def _create_preview(
        self,
        *,
        actor: AudioGovernanceActor,
        submission: AudioSubmission,
        run: AudioActivityRun,
        change_type: Literal["transcript_correction", "regrade", "invalidation"],
        request: dict[str, Any],
        summary: dict[str, Any],
    ) -> AudioChangePreviewResult:
        token = secrets.token_urlsafe(32)
        impact_hash = self._impact(submission, run, request)
        expires_at = _now() + timedelta(minutes=15)
        preview = AudioChangePreview(
            preview_id=_id(),
            organization_id=actor.organization_id,
            submission_id=submission.submission_id,
            change_type=change_type,
            requested_by=actor.actor_id,
            preview_token_hash=_hash(token),
            impact_hash=impact_hash,
            request_json=request,
            expires_at=expires_at,
        )
        self._session.add(preview)
        await self._session.flush([preview])
        return AudioChangePreviewResult(
            preview_token=token,
            impact_hash=impact_hash,
            expires_at=expires_at,
            change_type=change_type,
            summary=summary,
        )

    async def _consume_preview(
        self,
        *,
        actor: AudioGovernanceActor,
        submission: AudioSubmission,
        run: AudioActivityRun,
        change_type: str,
        preview_token: str,
        impact_hash: str,
    ) -> AudioChangePreview:
        preview = await self._session.scalar(
            select(AudioChangePreview)
            .where(AudioChangePreview.preview_token_hash == _hash(preview_token))
            .with_for_update()
            .limit(1)
        )
        if (
            preview is None
            or preview.organization_id != actor.organization_id
            or preview.submission_id != submission.submission_id
            or preview.requested_by != actor.actor_id
            or preview.change_type != change_type
            or preview.consumed_at is not None
            or _aware(preview.expires_at) <= _now()
        ):
            raise AudioAssessmentError(
                "[AUDIO_PREVIEW_INVALID]",
                "确认信息已失效，请重新预览后再执行。",
                409,
            )
        actual_impact = self._impact(submission, run, preview.request_json)
        if preview.impact_hash != impact_hash or actual_impact != impact_hash:
            raise AudioAssessmentError(
                "[AUDIO_PREVIEW_STALE]",
                "录音结果已更新，请重新预览后再执行。",
                412,
            )
        preview.consumed_at = _now()
        return preview

    async def _enqueue(
        self,
        *,
        actor: AudioGovernanceActor,
        submission: AudioSubmission,
        run: AudioActivityRun,
        mode: str,
        idempotency_key: str,
        target_transcript_revision_id: str | None,
        target_scoring_scheme_revision_id: str | None,
    ) -> TaskReference:
        payload = AudioPipelineTaskInput(
            submission_id=submission.submission_id,
            mode=mode,
            requested_by=actor.actor_id,
            target_transcript_revision_id=target_transcript_revision_id,
            target_scoring_scheme_revision_id=(target_scoring_scheme_revision_id),
        )
        return await self._tasks.enqueue(
            TaskCommand(
                task_type=AUDIO_PIPELINE_TASK_TYPE,
                schema_version=1,
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                resource_type="audio_submission",
                resource_id=submission.submission_id,
                idempotency_key=idempotency_key,
                input_payload=payload.model_dump(mode="json"),
                correlation_id=run.attempt_id,
                causation_id=submission.task_id,
                trace_id=actor.trace_id,
                data_classification="confidential",
            )
        )

    async def _audit_replay(
        self,
        *,
        actor: AudioGovernanceActor,
        submission_id: str,
        command: str,
        idempotency_key: str,
        impact_hash: str,
    ) -> AudioGovernanceResult | None:
        row = await self._session.scalar(
            select(AudioCommandAudit)
            .where(AudioCommandAudit.organization_id == actor.organization_id)
            .where(AudioCommandAudit.object_id == submission_id)
            .where(AudioCommandAudit.command == command)
            .where(AudioCommandAudit.idempotency_key_hash == _hash(idempotency_key))
            .limit(1)
        )
        if row is None:
            return None
        if row.impact_hash != impact_hash:
            raise AudioAssessmentError(
                "[AUDIO_IDEMPOTENCY_CONFLICT]",
                "相同幂等键对应了不同的管理命令。",
                409,
            )
        submission, run = await self._load(actor, submission_id)
        return self._result(submission, run)

    async def _audit(
        self,
        *,
        actor: AudioGovernanceActor,
        submission: AudioSubmission,
        command: str,
        idempotency_key: str,
        impact_hash: str,
        reason: str,
        details: dict[str, Any],
    ) -> None:
        row = AudioCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=(
                "newcomer.activity.invalidate"
                if command == "invalidate_audio_run"
                else (
                    "newcomer.audio.transcript.correct"
                    if command == "correct_audio_transcript"
                    else (
                        "newcomer.audio.review"
                        if command == "repair_audio_pipeline"
                        else "newcomer.audio.regrade"
                    )
                )
            ),
            object_type="audio_submission",
            object_id=submission.submission_id,
            command=command,
            before_version=submission.version - 1,
            after_version=submission.version,
            idempotency_key_hash=_hash(idempotency_key),
            expected_version=None,
            actual_version=submission.version,
            reason=reason,
            preview_token_hash=None,
            impact_hash=impact_hash,
            trace_id=actor.trace_id,
            result="succeeded",
            details_json=details,
            occurred_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])

    async def _load(
        self,
        actor: AudioGovernanceActor,
        submission_id: str,
        *,
        for_update: bool = False,
    ) -> tuple[AudioSubmission, AudioActivityRun]:
        query = select(AudioSubmission).where(
            AudioSubmission.submission_id == submission_id
        )
        if for_update:
            query = query.with_for_update()
        submission = await self._session.scalar(query.limit(1))
        if submission is None or submission.organization_id != actor.organization_id:
            raise AudioAssessmentError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "录音提交不存在或不可访问。",
                404,
            )
        run = await self._session.get(AudioActivityRun, submission.run_id)
        if run is None or run.organization_id != actor.organization_id:
            raise AudioAssessmentError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "录音提交不存在或不可访问。",
                404,
            )
        return submission, run

    async def _current_transcript(
        self,
        submission: AudioSubmission,
    ) -> AudioTranscriptRevision:
        row = (
            await self._session.get(
                AudioTranscriptRevision,
                submission.current_transcript_revision_id,
            )
            if submission.current_transcript_revision_id
            else None
        )
        if row is None or row.status != "valid":
            raise AudioAssessmentError(
                "[AUDIO_TRANSCRIPT_REQUIRED]",
                "当前录音尚无可修订的转写内容。",
                409,
            )
        return row

    async def _quality(self, revision_id: str) -> AudioQualityReport:
        row = await self._session.scalar(
            select(AudioQualityReport)
            .where(AudioQualityReport.transcript_revision_id == revision_id)
            .limit(1)
        )
        if row is None:
            raise AudioAssessmentError(
                "[AUDIO_QUALITY_REPORT_REQUIRED]",
                "当前转写缺少质量报告，不能执行人工修订。",
                409,
            )
        return row

    async def _require_scoring_scheme(
        self,
        organization_id: str,
        revision_id: str,
    ) -> None:
        row = await self._session.get(AudioActivityResourceRevision, revision_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.resource_type != "scoring_scheme"
            or row.status != "published"
        ):
            raise AudioAssessmentError(
                "[AUDIO_SCORING_SCHEME_UNAVAILABLE]",
                "指定评分方案不存在或尚未发布。",
                422,
            )
        AudioScoringSchemeSnapshot.model_validate(row.snapshot_json)

    @staticmethod
    def _impact(
        submission: AudioSubmission,
        run: AudioActivityRun,
        request: dict[str, Any],
    ) -> str:
        return _canonical_hash(
            {
                "submission_id": submission.submission_id,
                "submission_version": submission.version,
                "run_version": run.version,
                "transcript_revision_id": submission.current_transcript_revision_id,
                "score_outcome_version_id": (
                    submission.current_score_outcome_version_id
                ),
                "request": request,
            }
        )

    @staticmethod
    def _result(
        submission: AudioSubmission,
        run: AudioActivityRun,
    ) -> AudioGovernanceResult:
        return AudioGovernanceResult(
            submission_id=submission.submission_id,
            run_id=run.run_id,
            state=submission.state,
            task_id=submission.task_id,
            transcript_revision_id=submission.current_transcript_revision_id,
            score_outcome_version_id=(submission.current_score_outcome_version_id),
        )

    @staticmethod
    def _require(actor: AudioGovernanceActor, capability: str) -> None:
        if capability not in actor.capabilities:
            raise AudioAssessmentError(
                "[AUDIO_PERMISSION_DENIED]",
                "没有执行此录音管理操作的权限。",
                403,
            )

    @staticmethod
    def _reason_required() -> None:
        raise AudioAssessmentError(
            "[AUDIO_REASON_REQUIRED]",
            "请填写执行原因。",
            422,
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


__all__ = [
    "AudioChangePreviewResult",
    "AudioGovernanceResult",
    "AudioGovernanceService",
    "AudioQueueItem",
]

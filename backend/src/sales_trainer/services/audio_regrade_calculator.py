from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioTranscript,
    SalesTrainerUnit,
)
from sales_trainer.rules import resolve_audio_pass_threshold
from sales_trainer.services.deucate_scoring_service import DeucateScoringService


@dataclass(frozen=True, slots=True)
class AudioRegradePreview:
    target_type: str
    target_id: str
    target_revision_id: str
    impact_scope: dict[str, Any]
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]


async def build_audio_regrade_preview(
    db: AsyncSession,
    submission: SalesTrainerAudioSubmission,
    score: SalesTrainerAudioScoreResult,
    target_revision: SalesTrainerAssetRevision,
    *,
    scoring_service: DeucateScoringService,
) -> AudioRegradePreview:
    transcript_text = await _transcript_text(db, score)
    unit = (
        await db.get(SalesTrainerUnit, submission.unit_id)
        if submission.unit_id is not None
        else None
    )
    prompt = _prompt_from_revision(target_revision)
    threshold = resolve_audio_pass_threshold(unit.config if unit is not None else None)
    outcome = await scoring_service.score_audio(
        submission=submission,
        prompt=prompt,
        transcript_text=transcript_text,
        unit_name=unit.name if unit is not None else None,
        pass_threshold=threshold,
    )
    before_snapshot = _score_snapshot(score)
    after_snapshot = {
        "submission_id": submission.submission_id,
        "source_score_id": score.score_id,
        "source_prompt_id": score.prompt_id,
        "source_prompt_version": score.prompt_version,
        "source_prompt_hash": score.prompt_hash,
        "target_revision_id": target_revision.revision_id,
        "target_revision_no": target_revision.revision_no,
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
        "prompt_hash": outcome.prompt_hash,
        "deucate_model": outcome.deucate_model,
        "transcript_snapshot": transcript_text,
        "total_score": outcome.total_score,
        "passed": outcome.passed,
        "summary": outcome.summary,
        "strengths": outcome.strengths,
        "improvements": outcome.improvements,
        "dimension_scores": outcome.dimension_scores,
        "raw_response": outcome.raw_response,
        "error_code": outcome.error_code,
        "error_message": outcome.error_message,
        "latency_ms": outcome.latency_ms,
    }
    return AudioRegradePreview(
        target_type="audio_submission",
        target_id=submission.submission_id,
        target_revision_id=target_revision.revision_id,
        impact_scope=_impact_scope(submission.submission_id, score.score_id),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


def _score_snapshot(score: SalesTrainerAudioScoreResult) -> dict[str, Any]:
    return {
        "score_id": score.score_id,
        "submission_id": score.submission_id,
        "prompt_id": score.prompt_id,
        "prompt_version": score.prompt_version,
        "prompt_hash": score.prompt_hash,
        "deucate_model": score.deucate_model,
        "transcript_snapshot": score.transcript_snapshot,
        "total_score": _float_value(score.total_score),
        "passed": score.passed,
        "summary": score.summary,
        "strengths": score.strengths or [],
        "improvements": score.improvements or [],
        "dimension_scores": score.dimension_scores or {},
        "raw_response": score.raw_response,
        "error_code": score.error_code,
        "error_message": score.error_message,
        "latency_ms": score.latency_ms,
        "created_at": score.created_at.isoformat() if score.created_at else None,
    }


async def _transcript_text(
    db: AsyncSession,
    score: SalesTrainerAudioScoreResult,
) -> str:
    if score.transcript_snapshot and score.transcript_snapshot.strip():
        return score.transcript_snapshot
    result = await db.execute(
        select(SalesTrainerAudioTranscript)
        .where(SalesTrainerAudioTranscript.submission_id == score.submission_id)
        .limit(1)
    )
    transcript = result.scalar_one_or_none()
    if transcript is not None and transcript.transcript_text.strip():
        return transcript.transcript_text
    return ""


def _prompt_from_revision(
    revision: SalesTrainerAssetRevision,
) -> SalesTrainerAudioScorePrompt:
    payload = revision.payload_json if isinstance(revision.payload_json, dict) else {}
    return SalesTrainerAudioScorePrompt(
        prompt_id=str(payload.get("prompt_id") or revision.logical_id),
        name=str(payload.get("name") or "音频评分标准"),
        purpose=str(payload.get("purpose") or "general_audio_scoring"),
        system_prompt=str(payload.get("system_prompt") or ""),
        scoring_template=str(payload.get("scoring_template") or "{transcript}"),
        output_schema=dict(payload.get("output_schema") or {}),
        learner_rubric=dict(payload.get("learner_rubric") or {}),
        version=int(revision.revision_no),
        status="published",
    )


def _impact_scope(submission_id: str, score_id: str) -> dict[str, Any]:
    return {
        "record_count": 1,
        "affected_submission_ids": [submission_id],
        "source_score_result_ids": [score_id],
        "future_records_changed": False,
        "history_overwrite": False,
        "requires_reason": True,
    }


def _float_value(value: int | float | Decimal | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return None

"""Practice route application seams and low-risk helper services.

This module names the responsibility clusters that still live under
``common.api.practice`` and exposes a narrow bundle so route handlers can depend
on stable seams before the heavier extractions land.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import PracticeSession, SessionAudioSegment
from common.db.schemas import ScenarioType, SessionResponse
from common.db.session_lifecycle import SessionLifecycleService
from common.db.voice_policy_snapshot import build_voice_policy_snapshot_ref
from common.oss.signing import get_oss_signing_service
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from training_runtime.service import build_training_runtime_descriptor

if TYPE_CHECKING:
    from common.db.schemas import AudioAuditPayloadSchema

PRACTICE_APPLICATION_SEAMS: tuple[str, ...] = (
    "session_create_policy",
    "session_lifecycle",
    "session_report_read_model",
    "audio_audit_and_signing",
    "runtime_descriptor",
)


class PracticeRuntimeDescriptorService:
    """Assemble runtime-aware session payloads without route glue."""

    @staticmethod
    def build_session_response(
        session: PracticeSession,
        scenario_type: str | None = None,
    ) -> SessionResponse:
        payload = SessionResponse.model_validate(session)
        resolved_scenario_type = scenario_type
        if not resolved_scenario_type and getattr(session, "scenario", None) is not None:
            resolved_scenario_type = getattr(session.scenario, "scenario_type", None)

        try:
            payload.scenario_type = ScenarioType(resolved_scenario_type or "sales")
        except ValueError:
            payload.scenario_type = ScenarioType.SALES

        runtime_descriptor = build_training_runtime_descriptor(
            session,
            scenario_type=payload.scenario_type.value,
        )
        payload.runtime_subject = runtime_descriptor.subject
        payload.runtime_descriptor = runtime_descriptor
        runtime_profile_id = getattr(session, "voice_runtime_profile_id", None)
        payload.runtime_profile_id = (
            uuid.UUID(str(runtime_profile_id)) if runtime_profile_id else None
        )
        payload.voice_policy_snapshot_ref = build_voice_policy_snapshot_ref(
            payload.voice_policy_snapshot
        )
        return payload


class PracticeAudioAuditService:
    """Build the shared audio-audit read model used by report and replay."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_session_audio_audit(
        self,
        *,
        session_id: str,
        session: PracticeSession,
    ) -> "AudioAuditPayloadSchema | None":
        from common.db.schemas import (
            AudioAuditPayloadSchema,
            AudioAuditSegmentSchema,
            AudioAuditSummarySchema,
        )

        seg_result = await self.db.execute(
            select(SessionAudioSegment)
            .where(SessionAudioSegment.session_id == session_id)
            .order_by(SessionAudioSegment.segment_sequence)
        )
        segments = list(seg_result.scalars().all())
        if not segments:
            return None

        voice_policy = session.voice_policy_snapshot or {}
        runtime_metrics = (
            voice_policy.get("runtime_metrics") if isinstance(voice_policy, dict) else None
        )
        audio_audit_raw: dict[str, Any] = {}
        if isinstance(runtime_metrics, dict):
            raw = runtime_metrics.get("audio_audit")
            if isinstance(raw, dict):
                audio_audit_raw = raw

        uploaded_count = 0
        failed_count = 0
        pending_count = 0
        total_bytes = 0
        latest_sequence: int | None = None
        last_uploaded_at: str | None = None
        segment_schemas: list[AudioAuditSegmentSchema] = []

        for seg in segments:
            if seg.upload_status == "uploaded":
                uploaded_count += 1
                total_bytes += seg.size_bytes or 0
                if latest_sequence is None or seg.segment_sequence > latest_sequence:
                    latest_sequence = seg.segment_sequence
                if seg.created_at is not None:
                    last_uploaded_at = seg.created_at.isoformat()
            elif seg.upload_status == "failed":
                failed_count += 1
            elif seg.upload_status == "pending":
                pending_count += 1

            playback_path = None
            if seg.upload_status == "uploaded":
                playback_path = (
                    f"/api/v1/sessions/{session_id}/audio-segments/{seg.segment_sequence}"
                )

            segment_schemas.append(
                AudioAuditSegmentSchema(
                    segment_sequence=seg.segment_sequence,
                    created_at=seg.created_at.isoformat() if seg.created_at else None,
                    duration_ms=seg.duration_ms,
                    size_bytes=seg.size_bytes,
                    upload_status=seg.upload_status,
                    playback_path=playback_path,
                    error_message=seg.error_message,
                )
            )

        total_segments = len(segments)
        if uploaded_count > 0 and uploaded_count == total_segments:
            learner_status = "available"
        elif uploaded_count > 0:
            learner_status = "partial"
        else:
            learner_status = "missing"

        degraded_reasons: list[str] = []
        if failed_count > 0:
            degraded_reasons.append("upload_failed")
        if pending_count > 0:
            degraded_reasons.append("segments_pending")

        summary = AudioAuditSummarySchema(
            recording_status=audio_audit_raw.get("recording_status", "active"),
            total_segments=total_segments,
            uploaded_segments=uploaded_count,
            failed_segments=failed_count,
            total_bytes=total_bytes,
            latest_segment_sequence=latest_sequence,
            storage_prefix=audio_audit_raw.get("storage_prefix", f"audio/{session_id}/"),
            last_uploaded_at=last_uploaded_at,
            learner_status=learner_status,
            degraded_reasons=degraded_reasons,
        )

        return AudioAuditPayloadSchema(summary=summary, segments=segment_schemas)


@dataclass(slots=True)
class PracticeRouteServices:
    """Minimal seam bundle consumed by practice routes during extraction."""

    runtime_policy: VoiceRuntimePolicyService
    lifecycle: SessionLifecycleService
    evidence: SessionEvidenceService
    audio_audit: PracticeAudioAuditService
    runtime_descriptor: PracticeRuntimeDescriptorService
    get_oss_signing_service: Callable[[], Any]
    seam_names: tuple[str, ...] = PRACTICE_APPLICATION_SEAMS


def build_practice_route_services(db: AsyncSession) -> PracticeRouteServices:
    return PracticeRouteServices(
        runtime_policy=VoiceRuntimePolicyService(db),
        lifecycle=SessionLifecycleService(db),
        evidence=SessionEvidenceService(db),
        audio_audit=PracticeAudioAuditService(db),
        runtime_descriptor=PracticeRuntimeDescriptorService(),
        get_oss_signing_service=get_oss_signing_service,
    )


__all__ = [
    "PRACTICE_APPLICATION_SEAMS",
    "PracticeAudioAuditService",
    "PracticeRouteServices",
    "PracticeRuntimeDescriptorService",
    "build_practice_route_services",
]

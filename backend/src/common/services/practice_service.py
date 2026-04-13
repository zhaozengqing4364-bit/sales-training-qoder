"""Practice route application seam bundle.

Keeps a stable route-facing import surface while deeper session/report logic lives in
specialized application-service modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.session_evidence import SessionEvidenceService
from common.db.session_lifecycle import SessionLifecycleService
from common.oss.signing import get_oss_signing_service
from common.services.practice_report_service import (
    PracticeAudioAuditService,
    PracticeAudioSegmentService,
    PracticeReportService,
)
from common.services.practice_session_service import (
    PracticeRetryEntryAssembler,
    PracticeRuntimeDescriptorService,
    PracticeServiceError,
    PracticeSessionCreateService,
    PracticeSessionLifecycleApplicationService,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

PRACTICE_APPLICATION_SEAMS: tuple[str, ...] = (
    "session_create_policy",
    "session_lifecycle",
    "session_report_read_model",
    "audio_audit_and_signing",
    "runtime_descriptor",
)


@dataclass(slots=True)
class PracticeRouteServices:
    """Minimal seam bundle consumed by practice routes during extraction."""

    runtime_policy: VoiceRuntimePolicyService
    lifecycle: SessionLifecycleService
    evidence: SessionEvidenceService
    audio_audit: PracticeAudioAuditService
    runtime_descriptor: PracticeRuntimeDescriptorService
    get_oss_signing_service: Callable[[], Any]
    session_create: PracticeSessionCreateService
    session_lifecycle: PracticeSessionLifecycleApplicationService
    session_report: PracticeReportService
    audio_segments: PracticeAudioSegmentService
    seam_names: tuple[str, ...] = PRACTICE_APPLICATION_SEAMS


def build_practice_route_services(db: AsyncSession) -> PracticeRouteServices:
    runtime_policy_service = VoiceRuntimePolicyService(db)
    lifecycle_service = SessionLifecycleService(db)
    evidence_service = SessionEvidenceService(db)
    audio_audit_service = PracticeAudioAuditService(db)
    runtime_descriptor_service = PracticeRuntimeDescriptorService()

    return PracticeRouteServices(
        runtime_policy=runtime_policy_service,
        lifecycle=lifecycle_service,
        evidence=evidence_service,
        audio_audit=audio_audit_service,
        runtime_descriptor=runtime_descriptor_service,
        get_oss_signing_service=get_oss_signing_service,
        session_create=PracticeSessionCreateService(
            db,
            runtime_policy_service=runtime_policy_service,
        ),
        session_lifecycle=PracticeSessionLifecycleApplicationService(
            db,
            lifecycle_service=lifecycle_service,
        ),
        session_report=PracticeReportService(
            db,
            evidence_service=evidence_service,
            audio_audit_service=audio_audit_service,
        ),
        audio_segments=PracticeAudioSegmentService(
            db,
            get_signing_service=get_oss_signing_service,
        ),
    )


__all__ = [
    "PRACTICE_APPLICATION_SEAMS",
    "PracticeAudioAuditService",
    "PracticeAudioSegmentService",
    "PracticeReportService",
    "PracticeRetryEntryAssembler",
    "PracticeRouteServices",
    "PracticeRuntimeDescriptorService",
    "PracticeServiceError",
    "PracticeSessionCreateService",
    "PracticeSessionLifecycleApplicationService",
    "build_practice_route_services",
]

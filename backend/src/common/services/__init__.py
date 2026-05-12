"""Common service helpers."""

from typing import TYPE_CHECKING, Any

from common.services.password_reset import (
    ConsoleEmailService,
    EmailService,
    InvalidResetPasswordTokenError,
    PasswordResetService,
)

_PRACTICE_SERVICE_EXPORTS = {
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
}

if TYPE_CHECKING:
    from common.services.practice_service import (
        PRACTICE_APPLICATION_SEAMS,
        PracticeAudioAuditService,
        PracticeAudioSegmentService,
        PracticeReportService,
        PracticeRetryEntryAssembler,
        PracticeRouteServices,
        PracticeRuntimeDescriptorService,
        PracticeServiceError,
        PracticeSessionCreateService,
        PracticeSessionLifecycleApplicationService,
        build_practice_route_services,
    )


def __getattr__(name: str) -> Any:
    if name not in _PRACTICE_SERVICE_EXPORTS:
        raise AttributeError(name)
    from common.services import practice_service

    value = getattr(practice_service, name)
    globals()[name] = value
    return value

__all__ = [
    "ConsoleEmailService",
    "EmailService",
    "InvalidResetPasswordTokenError",
    "PasswordResetService",
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

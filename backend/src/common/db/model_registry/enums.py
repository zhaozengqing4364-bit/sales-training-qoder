"""Stable enum contracts shared by the grouped ORM declarations."""

import enum


class ScenarioType(str, enum.Enum):
    PRESENTATION = "presentation"
    SALES = "sales"


class PresentationStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionStatus(str, enum.Enum):
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    SCORING = "scoring"


class TrainingTaskStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ReportGenerationStatus(str, enum.Enum):
    """Status of report generation for a session."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationRunStatus(str, enum.Enum):
    """Status of one persisted evaluation run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NON_EVALUABLE = "non_evaluable"
    FAILED = "failed"


class InterruptionType(str, enum.Enum):
    FORBIDDEN_WORD = "forbidden_word"
    MISSING_POINT = "missing_point"
    VAGUE_RESPONSE = "vague_response"


class ManagerInterventionDueState(str, enum.Enum):
    PENDING = "pending"
    DUE = "due"
    RESOLVED = "resolved"


class ManagerInterventionReminderStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    SENT = "sent"


class SystemLogStatus(str, enum.Enum):
    """System log status types"""

    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"


class VerificationCheckType(str, enum.Enum):
    """Types of verification checks for release gates"""

    MIGRATION = "migration"
    UNIT_TESTS = "unit_tests"
    COVERAGE = "coverage"
    INTEGRATION_TESTS = "integration_tests"
    CONTRACT = "contract"
    PERFORMANCE = "performance"
    HEALTH = "health"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    MANUAL = "manual"


class VerificationStatus(str, enum.Enum):
    """Status of a verification check"""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class UploadStatus(str, enum.Enum):
    """Audio-segment upload state."""

    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"


__all__ = [
    "EvaluationRunStatus",
    "InterruptionType",
    "ManagerInterventionDueState",
    "ManagerInterventionReminderStatus",
    "PresentationStatus",
    "ReportGenerationStatus",
    "ScenarioType",
    "SessionStatus",
    "SystemLogStatus",
    "TrainingTaskStatus",
    "UploadStatus",
    "VerificationCheckType",
    "VerificationStatus",
]

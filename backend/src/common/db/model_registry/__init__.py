"""Physical SQLAlchemy model registry with one shared metadata."""

from .base import Base as Base
from .enums import (
    EvaluationRunStatus as EvaluationRunStatus,
)
from .enums import (
    InterruptionType as InterruptionType,
)
from .enums import (
    ManagerInterventionDueState as ManagerInterventionDueState,
)
from .enums import (
    ManagerInterventionReminderStatus as ManagerInterventionReminderStatus,
)
from .enums import (
    PresentationStatus as PresentationStatus,
)
from .enums import (
    ReportGenerationStatus as ReportGenerationStatus,
)
from .enums import (
    ScenarioType as ScenarioType,
)
from .enums import (
    SessionStatus as SessionStatus,
)
from .enums import (
    SystemLogStatus as SystemLogStatus,
)
from .enums import (
    TrainingTaskStatus as TrainingTaskStatus,
)
from .enums import (
    UploadStatus as UploadStatus,
)
from .enums import (
    VerificationCheckType as VerificationCheckType,
)
from .enums import (
    VerificationStatus as VerificationStatus,
)
from .evaluation import (
    ComprehensiveReport as ComprehensiveReport,
)
from .evaluation import (
    EvaluationRun as EvaluationRun,
)
from .evaluation import (
    RetrainingTask as RetrainingTask,
)
from .evaluation import (
    StagedEvaluationResult as StagedEvaluationResult,
)
from .evaluation import (
    SupervisorReview as SupervisorReview,
)
from .evaluation import (
    SupervisorScoreCalibration as SupervisorScoreCalibration,
)
from .evaluation import (
    TrainingReportSnapshot as TrainingReportSnapshot,
)
from .governance import (
    BusinessRuleConfig as BusinessRuleConfig,
)
from .governance import (
    BusinessRuleConfigAuditLog as BusinessRuleConfigAuditLog,
)
from .governance import (
    ConfigBundle as ConfigBundle,
)
from .governance import (
    ConfigBundleAuditLog as ConfigBundleAuditLog,
)
from .governance import (
    ConfigVersion as ConfigVersion,
)
from .governance import (
    PromptTemplate as PromptTemplate,
)
from .governance import (
    ScenarioPrompt as ScenarioPrompt,
)
from .governance import (
    ScoringRuleset as ScoringRuleset,
)
from .identity import (
    AdminRolePermission as AdminRolePermission,
)
from .identity import (
    PasswordResetToken as PasswordResetToken,
)
from .identity import (
    User as User,
)
from .identity import (
    UserPresentationProgress as UserPresentationProgress,
)
from .identity import (
    UserTrainingPreference as UserTrainingPreference,
)
from .knowledge import (
    KnowledgeAnswerabilityProfile as KnowledgeAnswerabilityProfile,
)
from .knowledge import (
    KnowledgeAnswerRun as KnowledgeAnswerRun,
)
from .knowledge import (
    KnowledgeAnswerRunStep as KnowledgeAnswerRunStep,
)
from .knowledge import (
    KnowledgeChunkingPreset as KnowledgeChunkingPreset,
)
from .knowledge import (
    KnowledgeConfigVersion as KnowledgeConfigVersion,
)
from .knowledge import (
    KnowledgeEntityAlias as KnowledgeEntityAlias,
)
from .knowledge import (
    KnowledgeIntentRule as KnowledgeIntentRule,
)
from .knowledge import (
    KnowledgeQueryProfile as KnowledgeQueryProfile,
)
from .knowledge import (
    KnowledgeRankingProfile as KnowledgeRankingProfile,
)
from .platform import (
    Achievement as Achievement,
)
from .platform import (
    LeaderboardEntry as LeaderboardEntry,
)
from .platform import (
    ManagerIntervention as ManagerIntervention,
)
from .platform import (
    Notification as Notification,
)
from .platform import (
    ReleaseVerificationRecord as ReleaseVerificationRecord,
)
from .platform import (
    ReleaseVerificationSummary as ReleaseVerificationSummary,
)
from .platform import (
    SessionAudioSegment as SessionAudioSegment,
)
from .platform import (
    SystemLog as SystemLog,
)
from .platform import (
    UserAchievement as UserAchievement,
)
from .platform import (
    UserGoal as UserGoal,
)
from .training import (
    ConversationMessage as ConversationMessage,
)
from .training import (
    ForbiddenWord as ForbiddenWord,
)
from .training import (
    HighlightReview as HighlightReview,
)
from .training import (
    HighlightReviewItem as HighlightReviewItem,
)
from .training import (
    HighlightReviewShare as HighlightReviewShare,
)
from .training import (
    HighlightReviewShareAccessLog as HighlightReviewShareAccessLog,
)
from .training import (
    InterruptionEvent as InterruptionEvent,
)
from .training import (
    Page as Page,
)
from .training import (
    PracticeSession as PracticeSession,
)
from .training import (
    Presentation as Presentation,
)
from .training import (
    RequiredTalkingPoint as RequiredTalkingPoint,
)
from .training import (
    Scenario as Scenario,
)
from .training import (
    TrainingTask as TrainingTask,
)

__all__ = [
    "Base",
    "ScenarioType",
    "PresentationStatus",
    "SessionStatus",
    "TrainingTaskStatus",
    "ReportGenerationStatus",
    "EvaluationRunStatus",
    "InterruptionType",
    "ManagerInterventionDueState",
    "ManagerInterventionReminderStatus",
    "SystemLogStatus",
    "VerificationCheckType",
    "VerificationStatus",
    "UploadStatus",
    "User",
    "AdminRolePermission",
    "UserTrainingPreference",
    "UserPresentationProgress",
    "PasswordResetToken",
    "BusinessRuleConfig",
    "BusinessRuleConfigAuditLog",
    "ConfigBundle",
    "ConfigVersion",
    "ConfigBundleAuditLog",
    "PromptTemplate",
    "ScenarioPrompt",
    "ScoringRuleset",
    "Scenario",
    "Presentation",
    "Page",
    "RequiredTalkingPoint",
    "ForbiddenWord",
    "PracticeSession",
    "TrainingTask",
    "ConversationMessage",
    "HighlightReview",
    "HighlightReviewItem",
    "HighlightReviewShare",
    "HighlightReviewShareAccessLog",
    "InterruptionEvent",
    "EvaluationRun",
    "TrainingReportSnapshot",
    "StagedEvaluationResult",
    "ComprehensiveReport",
    "SupervisorReview",
    "RetrainingTask",
    "SupervisorScoreCalibration",
    "Achievement",
    "UserAchievement",
    "Notification",
    "UserGoal",
    "ManagerIntervention",
    "LeaderboardEntry",
    "SystemLog",
    "ReleaseVerificationRecord",
    "ReleaseVerificationSummary",
    "SessionAudioSegment",
    "KnowledgeConfigVersion",
    "KnowledgeQueryProfile",
    "KnowledgeIntentRule",
    "KnowledgeEntityAlias",
    "KnowledgeRankingProfile",
    "KnowledgeChunkingPreset",
    "KnowledgeAnswerabilityProfile",
    "KnowledgeAnswerRun",
    "KnowledgeAnswerRunStep",
]

for _public_name in __all__:
    getattr(
        __import__(__name__, fromlist=[_public_name]), _public_name
    ).__module__ = "common.db.models"

del _public_name

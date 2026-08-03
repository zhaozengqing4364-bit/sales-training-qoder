"""Compatibility imports for the physically grouped SQLAlchemy model registry.

New persistence adapters should import the owning model_registry module. Existing
callers may keep this stable facade until Gate 6 proves their compatibility imports
can be retired.
"""

from common.db.model_registry import (
    Achievement as Achievement,
)
from common.db.model_registry import (
    AdminRolePermission as AdminRolePermission,
)
from common.db.model_registry import (
    Base as Base,
)
from common.db.model_registry import (
    BusinessRuleConfig as BusinessRuleConfig,
)
from common.db.model_registry import (
    BusinessRuleConfigAuditLog as BusinessRuleConfigAuditLog,
)
from common.db.model_registry import (
    ComprehensiveReport as ComprehensiveReport,
)
from common.db.model_registry import (
    ConfigBundle as ConfigBundle,
)
from common.db.model_registry import (
    ConfigBundleAuditLog as ConfigBundleAuditLog,
)
from common.db.model_registry import (
    ConfigVersion as ConfigVersion,
)
from common.db.model_registry import (
    ConversationMessage as ConversationMessage,
)
from common.db.model_registry import (
    EvaluationRun as EvaluationRun,
)
from common.db.model_registry import (
    EvaluationRunStatus as EvaluationRunStatus,
)
from common.db.model_registry import (
    ForbiddenWord as ForbiddenWord,
)
from common.db.model_registry import (
    HighlightReview as HighlightReview,
)
from common.db.model_registry import (
    HighlightReviewItem as HighlightReviewItem,
)
from common.db.model_registry import (
    HighlightReviewShare as HighlightReviewShare,
)
from common.db.model_registry import (
    HighlightReviewShareAccessLog as HighlightReviewShareAccessLog,
)
from common.db.model_registry import (
    InterruptionEvent as InterruptionEvent,
)
from common.db.model_registry import (
    InterruptionType as InterruptionType,
)
from common.db.model_registry import (
    KnowledgeAnswerabilityProfile as KnowledgeAnswerabilityProfile,
)
from common.db.model_registry import (
    KnowledgeAnswerRun as KnowledgeAnswerRun,
)
from common.db.model_registry import (
    KnowledgeAnswerRunStep as KnowledgeAnswerRunStep,
)
from common.db.model_registry import (
    KnowledgeChunkingPreset as KnowledgeChunkingPreset,
)
from common.db.model_registry import (
    KnowledgeConfigVersion as KnowledgeConfigVersion,
)
from common.db.model_registry import (
    KnowledgeEntityAlias as KnowledgeEntityAlias,
)
from common.db.model_registry import (
    KnowledgeIntentRule as KnowledgeIntentRule,
)
from common.db.model_registry import (
    KnowledgeQueryProfile as KnowledgeQueryProfile,
)
from common.db.model_registry import (
    KnowledgeRankingProfile as KnowledgeRankingProfile,
)
from common.db.model_registry import (
    LeaderboardEntry as LeaderboardEntry,
)
from common.db.model_registry import (
    ManagerIntervention as ManagerIntervention,
)
from common.db.model_registry import (
    ManagerInterventionDueState as ManagerInterventionDueState,
)
from common.db.model_registry import (
    ManagerInterventionReminderStatus as ManagerInterventionReminderStatus,
)
from common.db.model_registry import (
    Notification as Notification,
)
from common.db.model_registry import (
    Page as Page,
)
from common.db.model_registry import (
    PasswordResetToken as PasswordResetToken,
)
from common.db.model_registry import (
    PracticeSession as PracticeSession,
)
from common.db.model_registry import (
    Presentation as Presentation,
)
from common.db.model_registry import (
    PresentationStatus as PresentationStatus,
)
from common.db.model_registry import (
    PromptTemplate as PromptTemplate,
)
from common.db.model_registry import ProvisioningBatch as ProvisioningBatch
from common.db.model_registry import ProvisioningRow as ProvisioningRow
from common.db.model_registry import (
    ProvisioningTeamExecution as ProvisioningTeamExecution,
)
from common.db.model_registry import (
    ReleaseVerificationRecord as ReleaseVerificationRecord,
)
from common.db.model_registry import (
    ReleaseVerificationSummary as ReleaseVerificationSummary,
)
from common.db.model_registry import (
    ReportGenerationStatus as ReportGenerationStatus,
)
from common.db.model_registry import (
    RequiredTalkingPoint as RequiredTalkingPoint,
)
from common.db.model_registry import (
    RetrainingTask as RetrainingTask,
)
from common.db.model_registry import (
    Scenario as Scenario,
)
from common.db.model_registry import (
    ScenarioPrompt as ScenarioPrompt,
)
from common.db.model_registry import (
    ScenarioType as ScenarioType,
)
from common.db.model_registry import (
    ScoringRuleset as ScoringRuleset,
)
from common.db.model_registry import (
    SessionAudioSegment as SessionAudioSegment,
)
from common.db.model_registry import (
    SessionStatus as SessionStatus,
)
from common.db.model_registry import (
    StagedEvaluationResult as StagedEvaluationResult,
)
from common.db.model_registry import (
    SupervisorReview as SupervisorReview,
)
from common.db.model_registry import (
    SupervisorScoreCalibration as SupervisorScoreCalibration,
)
from common.db.model_registry import (
    SystemLog as SystemLog,
)
from common.db.model_registry import (
    SystemLogStatus as SystemLogStatus,
)
from common.db.model_registry import Team as Team
from common.db.model_registry import TeamLeaderAssignment as TeamLeaderAssignment
from common.db.model_registry import TeamMembership as TeamMembership
from common.db.model_registry import (
    TrainingReportSnapshot as TrainingReportSnapshot,
)
from common.db.model_registry import (
    TrainingTask as TrainingTask,
)
from common.db.model_registry import (
    TrainingTaskStatus as TrainingTaskStatus,
)
from common.db.model_registry import (
    UploadStatus as UploadStatus,
)
from common.db.model_registry import (
    User as User,
)
from common.db.model_registry import (
    UserAchievement as UserAchievement,
)
from common.db.model_registry import (
    UserGoal as UserGoal,
)
from common.db.model_registry import (
    UserPresentationProgress as UserPresentationProgress,
)
from common.db.model_registry import (
    UserTrainingPreference as UserTrainingPreference,
)
from common.db.model_registry import (
    VerificationCheckType as VerificationCheckType,
)
from common.db.model_registry import (
    VerificationStatus as VerificationStatus,
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
    "Team",
    "TeamMembership",
    "TeamLeaderAssignment",
    "ProvisioningBatch",
    "ProvisioningTeamExecution",
    "ProvisioningRow",
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

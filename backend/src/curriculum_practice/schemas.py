from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

from curriculum_practice.asset_ref_schemas import (
    AssetRef as AssetRef,
)
from curriculum_practice.asset_ref_schemas import (
    CurriculumAssetType as CurriculumAssetType,
)
from curriculum_practice.asset_ref_schemas import (
    CurriculumVersionRef as CurriculumVersionRef,
)
from curriculum_practice.asset_ref_schemas import (
    LearningContentRef as LearningContentRef,
)
from curriculum_practice.asset_ref_schemas import (
    PublishedAssetRef as PublishedAssetRef,
)
from curriculum_practice.asset_ref_schemas import (
    PublishedAssetRefSchema as PublishedAssetRefSchema,
)
from curriculum_practice.asset_ref_schemas import (
    PublishedTemplateRef as PublishedTemplateRef,
)
from curriculum_practice.asset_ref_schemas import (
    SnapshotLabel as SnapshotLabel,
)
from curriculum_practice.asset_ref_schemas import (
    TestBankRef as TestBankRef,
)
from curriculum_practice.content_asset_schemas import (
    CaseItemBase as CaseItemBase,
)
from curriculum_practice.content_asset_schemas import (
    CaseItemCreate as CaseItemCreate,
)
from curriculum_practice.content_asset_schemas import (
    CaseItemListResponse as CaseItemListResponse,
)
from curriculum_practice.content_asset_schemas import (
    CaseItemResponse as CaseItemResponse,
)
from curriculum_practice.content_asset_schemas import (
    RoleProfileBase as RoleProfileBase,
)
from curriculum_practice.content_asset_schemas import (
    RoleProfileCreate as RoleProfileCreate,
)
from curriculum_practice.content_asset_schemas import (
    RoleProfileListResponse as RoleProfileListResponse,
)
from curriculum_practice.content_asset_schemas import (
    RoleProfileResponse as RoleProfileResponse,
)
from curriculum_practice.content_asset_schemas import (
    RoleProfileVoiceCloneRequest as RoleProfileVoiceCloneRequest,
)
from curriculum_practice.content_asset_schemas import (
    RoleProfileVoiceCloneResponse as RoleProfileVoiceCloneResponse,
)
from curriculum_practice.content_asset_schemas import (
    TemplateReferenceItem as TemplateReferenceItem,
)
from curriculum_practice.content_asset_schemas import (
    TemplateReferenceListResponse as TemplateReferenceListResponse,
)
from curriculum_practice.content_asset_schemas import (
    UnpublishAcknowledgeRequest as UnpublishAcknowledgeRequest,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumCompletionPolicy as CurriculumCompletionPolicy,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumPlanSchema as CurriculumPlanSchema,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumPlanStage as CurriculumPlanStage,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumRuntimeRef as CurriculumRuntimeRef,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumRuntimeSnapshot as CurriculumRuntimeSnapshot,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumStagePrerequisite as CurriculumStagePrerequisite,
)
from curriculum_practice.curriculum_runtime_schemas import (
    CurriculumTrainingTaskRef as CurriculumTrainingTaskRef,
)
from curriculum_practice.curriculum_runtime_schemas import (
    TemplateStageSnapshot as TemplateStageSnapshot,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerAgentCreate as ExaminerAgentCreate,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerAgentListResponse as ExaminerAgentListResponse,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerAgentResponse as ExaminerAgentResponse,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerAgentSimulationRequest as ExaminerAgentSimulationRequest,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerAgentSimulationResponse as ExaminerAgentSimulationResponse,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerAgentUpdate as ExaminerAgentUpdate,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerLearnerLevelStrategy as ExaminerLearnerLevelStrategy,
)
from curriculum_practice.examiner_agent_schemas import (
    ExaminerTimeoutConfig as ExaminerTimeoutConfig,
)
from curriculum_practice.learner_schemas import (
    ChapterCompleteResponse as ChapterCompleteResponse,
)
from curriculum_practice.learner_schemas import (
    LearnerAdminOverrideRequest as LearnerAdminOverrideRequest,
)
from curriculum_practice.learner_schemas import (
    LearnerProfileResponse as LearnerProfileResponse,
)
from curriculum_practice.learner_schemas import (
    LearnerSelfAssessmentRequest as LearnerSelfAssessmentRequest,
)
from curriculum_practice.learner_schemas import (
    LearnerStudyContentResponse as LearnerStudyContentResponse,
)
from curriculum_practice.learner_schemas import (
    LearningProgressResponse as LearningProgressResponse,
)
from curriculum_practice.learning_content_schemas import (
    LearningChapterCreate as LearningChapterCreate,
)
from curriculum_practice.learning_content_schemas import (
    LearningChapterReorderRequest as LearningChapterReorderRequest,
)
from curriculum_practice.learning_content_schemas import (
    LearningChapterResponse as LearningChapterResponse,
)
from curriculum_practice.learning_content_schemas import (
    LearningChapterUpdate as LearningChapterUpdate,
)
from curriculum_practice.learning_content_schemas import (
    LearningContentCreate as LearningContentCreate,
)
from curriculum_practice.learning_content_schemas import (
    LearningContentListResponse as LearningContentListResponse,
)
from curriculum_practice.learning_content_schemas import (
    LearningContentResponse as LearningContentResponse,
)
from curriculum_practice.learning_content_schemas import (
    LearningContentRevisionState as LearningContentRevisionState,
)
from curriculum_practice.learning_content_schemas import (
    LearningContentUpdate as LearningContentUpdate,
)
from curriculum_practice.practice_template_schemas import (
    PracticeTemplateCreate as PracticeTemplateCreate,
)
from curriculum_practice.practice_template_schemas import (
    PracticeTemplateListResponse as PracticeTemplateListResponse,
)
from curriculum_practice.practice_template_schemas import (
    PracticeTemplatePublishCandidate as PracticeTemplatePublishCandidate,
)
from curriculum_practice.practice_template_schemas import (
    PracticeTemplateResponse as PracticeTemplateResponse,
)
from curriculum_practice.practice_template_schemas import (
    PracticeTemplateUpdate as PracticeTemplateUpdate,
)
from curriculum_practice.publish_gate_schemas import (
    GateResult as GateResult,
)
from curriculum_practice.publish_gate_schemas import (
    PublishGateDecision as PublishGateDecision,
)
from curriculum_practice.question_bank_schemas import (
    QuestionCategoryCreate as QuestionCategoryCreate,
)
from curriculum_practice.question_bank_schemas import (
    QuestionCategoryListResponse as QuestionCategoryListResponse,
)
from curriculum_practice.question_bank_schemas import (
    QuestionCategoryResponse as QuestionCategoryResponse,
)
from curriculum_practice.question_bank_schemas import (
    QuestionCategoryUpdate as QuestionCategoryUpdate,
)
from curriculum_practice.question_bank_schemas import (
    QuestionGenerationConfirmRequest as QuestionGenerationConfirmRequest,
)
from curriculum_practice.question_bank_schemas import (
    QuestionGenerationConfirmResponse as QuestionGenerationConfirmResponse,
)
from curriculum_practice.question_bank_schemas import (
    QuestionGenerationDraft as QuestionGenerationDraft,
)
from curriculum_practice.question_bank_schemas import (
    QuestionGenerationPreviewRequest as QuestionGenerationPreviewRequest,
)
from curriculum_practice.question_bank_schemas import (
    QuestionGenerationPreviewResponse as QuestionGenerationPreviewResponse,
)
from curriculum_practice.question_bank_schemas import (
    QuestionItemCreate as QuestionItemCreate,
)
from curriculum_practice.question_bank_schemas import (
    QuestionItemListResponse as QuestionItemListResponse,
)
from curriculum_practice.question_bank_schemas import (
    QuestionItemResponse as QuestionItemResponse,
)
from curriculum_practice.question_bank_schemas import (
    QuestionItemUpdate as QuestionItemUpdate,
)
from curriculum_practice.question_bank_schemas import (
    TestBankImportErrorResponse as TestBankImportErrorResponse,
)
from curriculum_practice.question_bank_schemas import (
    TestBankImportJobResponse as TestBankImportJobResponse,
)
from curriculum_practice.question_bank_schemas import (
    TestBankImportResultResponse as TestBankImportResultResponse,
)
from curriculum_practice.runtime_dossier_schemas import (
    PracticeTemplateRuntimeDossierPreview as PracticeTemplateRuntimeDossierPreview,
)
from curriculum_practice.runtime_dossier_schemas import (
    RuntimeDossierConsistency as RuntimeDossierConsistency,
)
from curriculum_practice.runtime_dossier_schemas import (
    RuntimeDossierConsistencyCheck as RuntimeDossierConsistencyCheck,
)
from curriculum_practice.runtime_dossier_schemas import (
    RuntimeDossierProbeResult as RuntimeDossierProbeResult,
)
from curriculum_practice.schema_types import (
    ContentAssetStatus as ContentAssetStatus,
)
from curriculum_practice.schema_types import (
    CurriculumStageType as CurriculumStageType,
)
from curriculum_practice.schema_types import (
    ExaminerAgentStatus as ExaminerAgentStatus,
)
from curriculum_practice.schema_types import (
    GateStatus as GateStatus,
)
from curriculum_practice.schema_types import (
    LearnerLevel as LearnerLevel,
)
from curriculum_practice.schema_types import (
    LearningContentStatus as LearningContentStatus,
)
from curriculum_practice.schema_types import (
    PracticeTemplateMode as PracticeTemplateMode,
)
from curriculum_practice.schema_types import (
    PracticeTemplateScenarioType as PracticeTemplateScenarioType,
)
from curriculum_practice.schema_types import (
    PracticeTemplateStatus as PracticeTemplateStatus,
)
from curriculum_practice.schema_types import (
    PracticeTemplateVoiceMode as PracticeTemplateVoiceMode,
)
from curriculum_practice.schema_types import (
    QuestionDifficulty as QuestionDifficulty,
)
from curriculum_practice.schema_types import (
    QuestionLifecycleStatus as QuestionLifecycleStatus,
)
from curriculum_practice.schema_types import (
    RoleProfilePressureLevel as RoleProfilePressureLevel,
)
from curriculum_practice.schema_types import (
    RuntimeDossierStatus as RuntimeDossierStatus,
)
from curriculum_practice.schema_types import (
    TestBankImportStatus as TestBankImportStatus,
)


class ReferenceReader(Protocol):
    def __call__(
        self, asset_type: str, asset_id: str
    ) -> object | Awaitable[object | None] | None: ...

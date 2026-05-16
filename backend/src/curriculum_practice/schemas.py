from __future__ import annotations

from collections.abc import Awaitable
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

PracticeTemplateStatus = Literal["draft", "published", "archived"]
ExaminerAgentStatus = Literal["draft", "published", "archived"]
ContentAssetStatus = Literal["draft", "published", "archived"]
LearningContentStatus = Literal["draft", "published", "archived"]
CurriculumStageType = Literal["study", "exam", "practice", "report"]
QuestionDifficulty = Literal["easy", "medium", "hard"]
QuestionLifecycleStatus = Literal["draft", "published", "archived"]
TestBankImportStatus = Literal["pending", "processing", "completed", "failed"]
RoleProfilePressureLevel = Literal["low", "medium", "high"]
PracticeTemplateScenarioType = Literal["sales", "presentation"]
PracticeTemplateVoiceMode = Literal["legacy", "stepfun_realtime"]
LearnerLevel = Literal["conservative", "beginner", "intermediate", "advanced"]
PracticeTemplateMode = Literal[
    "learning",
    "expert_qa",
    "examiner",
    "customer_roleplay",
    "mixed_path",
]
GateStatus = Literal["passed", "failed", "warning"]
CurriculumAssetType = Literal[
    "practice_template",
    "curriculum",
    "lesson",
    "knowledge_point",
    "question_bank",
    "question_item",
    "case_item",
    "role_profile",
    "rubric_set",
    "scoring_ruleset",
    "knowledge_base",
    "prompt_contract",
    "model_config",
    "learning_content",
    "examiner_agent",
    ]
SnapshotLabel = Literal["published", "superseded", "legacy_unversioned"]
AssetTypeT = TypeVar("AssetTypeT", bound=str)
AssetVersionT = TypeVar("AssetVersionT", int, str, int | str)
SnapshotLabelT = TypeVar("SnapshotLabelT", bound=str)


class PracticeTemplatePublishCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    scenario_type: PracticeTemplateScenarioType
    mode: PracticeTemplateMode
    agent_id: str = Field(..., min_length=1, max_length=36)
    persona_id: str = Field(..., min_length=1, max_length=36)
    runtime_profile_id: str = Field(..., min_length=1, max_length=36)
    voice_mode: PracticeTemplateVoiceMode = "stepfun_realtime"
    scoring_ruleset_id: str = Field(..., min_length=1, max_length=36)
    knowledge_base_refs: list[str] = Field(default_factory=list)
    case_item_id: str | None = Field(None, min_length=1, max_length=36)
    role_profile_id: str | None = Field(None, min_length=1, max_length=36)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    examiner_agent_id: str | None = Field(None, min_length=1, max_length=36)
    target_learner_level: LearnerLevel | None = None
    timeout_config: dict[str, object] | None = None
    curriculum_plan: CurriculumPlanSchema | None = None
    max_stage_duration_seconds: int | None = Field(None, ge=1, le=1500)


class GateResult(BaseModel):
    gate_name: str
    status: GateStatus
    reason_code: str
    message: str


class PublishGateDecision(BaseModel):
    can_publish: bool
    results: list[GateResult]


class ExaminerLearnerLevelStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_level: LearnerLevel = "conservative"
    allowed_levels: list[LearnerLevel] = Field(
        default_factory=lambda: ["conservative", "beginner", "intermediate", "advanced"],
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_default_is_allowed(self) -> ExaminerLearnerLevelStrategy:
        if self.default_level not in self.allowed_levels:
            raise ValueError("default_level must be included in allowed_levels")
        return self


class ExaminerTimeoutConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_seconds: int = Field(..., ge=1, le=1500)


class ExaminerAgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    question_source_ids: list[str] = Field(default_factory=list)
    learner_level_strategy: ExaminerLearnerLevelStrategy = Field(
        default_factory=ExaminerLearnerLevelStrategy
    )
    scoring_policy_id: str = Field(..., min_length=1, max_length=36)
    timeout_config: ExaminerTimeoutConfig
    safety_config: dict[str, object] = Field(default_factory=dict)
    prompt_config: dict[str, object] = Field(default_factory=dict)
    simulation_config: dict[str, object] = Field(default_factory=dict)


class ExaminerAgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    question_source_ids: list[str] | None = None
    learner_level_strategy: ExaminerLearnerLevelStrategy | None = None
    scoring_policy_id: str | None = Field(None, min_length=1, max_length=36)
    timeout_config: ExaminerTimeoutConfig | None = None
    safety_config: dict[str, object] | None = None
    prompt_config: dict[str, object] | None = None
    simulation_config: dict[str, object] | None = None


class ExaminerAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    examiner_agent_id: str
    name: str
    description: str | None = None
    question_source_ids: list[str]
    learner_level_strategy: dict[str, object]
    scoring_policy_id: str
    timeout_config: dict[str, object]
    safety_config: dict[str, object]
    prompt_config: dict[str, object]
    simulation_config: dict[str, object]
    status: ExaminerAgentStatus
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class ExaminerAgentListResponse(BaseModel):
    items: list[ExaminerAgentResponse]
    total: int


class ExaminerAgentSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_level: LearnerLevel | None = None
    sample_answer: str = Field(..., min_length=1, max_length=8000)
    question_id: str | None = Field(None, min_length=1, max_length=36)


class ExaminerAgentSimulationResponse(BaseModel):
    mode: Literal["dry_run"] = "dry_run"
    mutates_records: bool = False
    examiner_agent_id: str
    selected_question_id: str
    learner_level: LearnerLevel
    scoring_policy_id: str
    timeout_seconds: int
    result: dict[str, object]


class AssetRef(BaseModel, Generic[AssetTypeT, AssetVersionT, SnapshotLabelT]):
    asset_type: AssetTypeT
    asset_id: str
    version: AssetVersionT
    hash: str
    snapshot_label: SnapshotLabelT


class PublishedTemplateRef(
    AssetRef[Literal["practice_template"], int, Literal["published"]]
):
    asset_type: Literal["practice_template"] = "practice_template"
    version: int
    snapshot_label: Literal["published"] = "published"


class CurriculumVersionRef(AssetRef[CurriculumAssetType, int | str, SnapshotLabel]):
    asset_type: CurriculumAssetType
    snapshot_label: SnapshotLabel


class LearningContentRef(
    AssetRef[Literal["learning_content"], int, Literal["published"]]
):
    asset_type: Literal["learning_content"] = "learning_content"
    version: int
    snapshot_label: Literal["published"] = "published"


class TestBankRef(AssetRef[Literal["question_item"], int, Literal["published"]]):
    asset_type: Literal["question_item"] = "question_item"
    version: int
    snapshot_label: Literal["published"] = "published"


class CurriculumTrainingTaskRef(BaseModel):
    id: str
    scenario_type: str


class CurriculumRuntimeRef(BaseModel):
    agent_id: str
    persona_id: str
    runtime_profile_id: str
    voice_policy_snapshot_hash: str
    instruction_contract_hash: str


class CurriculumStagePrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_stage_key: str = Field(..., min_length=1, max_length=80)
    required_result: Literal["completed"] = "completed"


class CurriculumCompletionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_score: float = Field(..., ge=0.0, le=10.0)
    min_rounds: int = Field(..., ge=0)
    max_duration_seconds: int = Field(..., ge=1, le=1500)


class CurriculumPlanStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_stage_key: str = Field(..., min_length=1, max_length=80)
    stage_type: CurriculumStageType = "practice"
    order: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=200)
    template_ref: CurriculumVersionRef
    completion_policy: CurriculumCompletionPolicy
    failure_policy: Literal[
        "retry_current", "fallback_to_previous", "allow_skip"
    ] = "retry_current"
    prerequisites: list[CurriculumStagePrerequisite] = Field(default_factory=list)


class CurriculumPlanSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    max_stage_duration_seconds: int | None = Field(None, ge=1, le=1500)
    stages: list[CurriculumPlanStage] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_stage_graph(self) -> CurriculumPlanSchema:
        stage_keys = [stage.template_stage_key for stage in self.stages]
        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError("template_stage_key values must be unique")
        known_stage_keys = set(stage_keys)
        graph: dict[str, list[str]] = {}
        for stage in self.stages:
            if (
                self.max_stage_duration_seconds is not None
                and stage.completion_policy.max_duration_seconds
                > self.max_stage_duration_seconds
            ):
                raise ValueError(
                    "stage duration exceeds max_stage_duration_seconds"
                )
            graph[stage.template_stage_key] = [
                prerequisite.template_stage_key
                for prerequisite in stage.prerequisites
            ]
            for prerequisite_key in graph[stage.template_stage_key]:
                if prerequisite_key not in known_stage_keys:
                    raise ValueError(
                        f"prerequisite stage {prerequisite_key!r} does not exist"
                    )
                if prerequisite_key == stage.template_stage_key:
                    raise ValueError(
                        f"curriculum stage {stage.template_stage_key!r} is unreachable"
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(stage_key: str) -> None:
            if stage_key in visited:
                return
            if stage_key in visiting:
                raise ValueError("curriculum plan cycle detected")
            visiting.add(stage_key)
            for prerequisite_key in graph[stage_key]:
                visit(prerequisite_key)
            visiting.remove(stage_key)
            visited.add(stage_key)

        for stage_key in stage_keys:
            visit(stage_key)
        return self


class TemplateStageSnapshot(BaseModel):
    template_ref: CurriculumVersionRef
    runtime_payload: dict[str, object]
    content_assets: list[CurriculumVersionRef] = Field(default_factory=list)
    rubric: CurriculumVersionRef | None = None
    runtime: CurriculumRuntimeRef | None = None


class CurriculumRuntimeSnapshot(BaseModel):
    schema_version: int = 1
    snapshot_hash: str
    created_at: str
    trace_id: str | None = None
    training_task: CurriculumTrainingTaskRef
    practice_template: CurriculumVersionRef
    content_assets: list[CurriculumVersionRef] = Field(default_factory=list)
    rubric: CurriculumVersionRef
    runtime: CurriculumRuntimeRef
    role_profile_voice_id: str | None = None
    learner_level: LearnerLevel = "conservative"
    stage_snapshots: dict[str, TemplateStageSnapshot] = Field(default_factory=dict)
    llm_nodes: list[dict[str, object]] = Field(default_factory=list)


class CaseItemBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    industry: str = Field(..., min_length=1, max_length=120)
    company_profile: str = Field(..., min_length=1, max_length=4000)
    customer_role: str = Field(..., min_length=1, max_length=120)
    pain_points: list[str] = Field(..., min_length=1)
    objections: list[str] = Field(..., min_length=1)
    hidden_information: str = Field(..., min_length=1, max_length=4000)
    success_criteria: list[str] = Field(..., min_length=1)
    allowed_disclosure_policy: dict[str, object]
    content_hash: str = Field(..., min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_allowed_disclosure_policy(self) -> CaseItemBase:
        phases = self.allowed_disclosure_policy.get("phases")
        if not isinstance(phases, list) or not phases:
            raise ValueError("allowed_disclosure_policy.phases must contain at least one phase")
        return self


class CaseItemCreate(CaseItemBase):
    pass


class CaseItemResponse(CaseItemBase):
    model_config = ConfigDict(from_attributes=True)

    case_item_id: str
    version: int
    status: ContentAssetStatus
    published_at: object | None = None
    created_at: object
    updated_at: object


class CaseItemListResponse(BaseModel):
    items: list[CaseItemResponse]
    total: int


class RoleProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_type: Literal["customer"]
    role_name: str = Field(..., min_length=1, max_length=160)
    persona_ref: str | None = Field(None, min_length=1, max_length=36)
    communication_style: str = Field(..., min_length=1, max_length=2000)
    pressure_level: RoleProfilePressureLevel
    knowledge_boundary: list[str] = Field(..., min_length=1)
    behavior_rules: list[str] = Field(..., min_length=1)
    voice_style_hint: str = Field(..., min_length=1, max_length=300)
    content_hash: str = Field(..., min_length=1, max_length=80)


class RoleProfileCreate(RoleProfileBase):
    pass


class RoleProfileResponse(RoleProfileBase):
    model_config = ConfigDict(from_attributes=True)

    role_profile_id: str
    voice_id: str | None = Field(None, min_length=1, max_length=64)
    voice_sample_url: str | None = Field(None, min_length=1, max_length=512)
    version: int
    status: ContentAssetStatus
    published_at: object | None = None
    created_at: object
    updated_at: object


class RoleProfileListResponse(BaseModel):
    items: list[RoleProfileResponse]
    total: int


class RoleProfileVoiceCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_name: str = Field(..., min_length=1, max_length=160)
    audio_base64: str = Field(..., min_length=1)
    content_type: str = Field(..., min_length=1, max_length=120)
    voice_sample_url: str = Field(..., min_length=1, max_length=512)


class RoleProfileVoiceCloneResponse(BaseModel):
    voice_id: str | None = None
    voice_sample_url: str | None = None
    fallback_voice: str | None = None
    reason_code: str | None = None
    retryable: bool = False


class LearningContentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=4000)
    owner: str | None = Field(None, min_length=1, max_length=120)
    source: str | None = Field(None, min_length=1, max_length=300)
    safety_flagged: bool = False


class LearningContentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=4000)
    owner: str | None = Field(None, min_length=1, max_length=120)
    source: str | None = Field(None, min_length=1, max_length=300)
    safety_flagged: bool | None = None


class LearningChapterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    order_index: int | None = Field(None, ge=1)


class LearningChapterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)
    order_index: int | None = Field(None, ge=1)


class LearningChapterReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_ids: list[str] = Field(..., min_length=1)


class LearningChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chapter_id: str
    learning_content_id: str
    title: str
    content: str
    order_index: int
    created_at: object
    updated_at: object


class LearningContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    learning_content_id: str
    title: str
    summary: str | None = None
    owner: str | None = None
    source: str | None = None
    status: LearningContentStatus
    safety_flagged: bool
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object
    chapters: list[LearningChapterResponse] = Field(default_factory=list)


class LearningContentListResponse(BaseModel):
    items: list[LearningContentResponse]
    total: int


class QuestionCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=160)
    parent_id: str | None = Field(None, min_length=1, max_length=36)
    description: str | None = Field(None, max_length=2000)
    order_index: int = Field(1, ge=1)


class QuestionCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=160)
    parent_id: str | None = Field(None, min_length=1, max_length=36)
    description: str | None = Field(None, max_length=2000)
    order_index: int | None = Field(None, ge=1)


class QuestionCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: str
    parent_id: str | None = None
    name: str
    description: str | None = None
    order_index: int
    created_at: object
    updated_at: object


class QuestionCategoryListResponse(BaseModel):
    items: list[QuestionCategoryResponse]
    total: int


class QuestionItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(..., min_length=1, max_length=36)
    title: str = Field(..., min_length=1, max_length=200)
    stem: str = Field(..., min_length=1)
    reference_answer: str | None = Field(None, max_length=8000)
    scoring_criteria: dict[str, object] = Field(default_factory=dict)
    scoring_dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: QuestionDifficulty = "medium"
    safety_flagged: bool = False
    department: str | None = Field(None, min_length=1, max_length=120)


class QuestionItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str | None = Field(None, min_length=1, max_length=36)
    title: str | None = Field(None, min_length=1, max_length=200)
    stem: str | None = Field(None, min_length=1)
    reference_answer: str | None = Field(None, max_length=8000)
    scoring_criteria: dict[str, object] | None = None
    scoring_dimensions: list[str] | None = None
    tags: list[str] | None = None
    difficulty: QuestionDifficulty | None = None
    safety_flagged: bool | None = None
    department: str | None = Field(None, min_length=1, max_length=120)


class QuestionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    category_id: str
    title: str
    stem: str
    reference_answer: str | None = None
    scoring_criteria: dict[str, object]
    scoring_dimensions: list[str]
    tags: list[str]
    difficulty: QuestionDifficulty
    status: QuestionLifecycleStatus
    safety_flagged: bool
    department: str | None = None
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class QuestionItemListResponse(BaseModel):
    items: list[QuestionItemResponse]
    total: int


class QuestionGenerationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_content_id: str = Field(..., min_length=1, max_length=36)
    chapter_id: str = Field(..., min_length=1, max_length=36)


class QuestionGenerationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    stem: str = Field(..., min_length=1)
    reference_answer: str = Field(..., min_length=1, max_length=8000)
    scoring_criteria: dict[str, object]
    scoring_dimensions: list[str] = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    difficulty: QuestionDifficulty = "medium"
    source_learning_content_id: str = Field(..., min_length=1, max_length=36)
    source_chapter_id: str = Field(..., min_length=1, max_length=36)


class QuestionGenerationPreviewResponse(BaseModel):
    drafts: list[QuestionGenerationDraft]


class QuestionGenerationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(..., min_length=1, max_length=36)
    drafts: list[QuestionGenerationDraft] = Field(..., min_length=1, max_length=5)


class QuestionGenerationConfirmResponse(BaseModel):
    items: list[QuestionItemResponse]
    total: int


class TestBankImportErrorResponse(BaseModel):
    row: int
    field: str
    message: str


class TestBankImportResultResponse(BaseModel):
    imported: int
    failed: int
    errors: list[TestBankImportErrorResponse]


class TestBankImportJobResponse(BaseModel):
    task_id: str
    status: TestBankImportStatus
    result: TestBankImportResultResponse


class LearningProgressResponse(BaseModel):
    completed_chapter_ids: list[str]
    completed_count: int
    total_chapters: int
    is_completed: bool
    state: Literal["not_started", "in_progress", "completed"]
    primary_cta: Literal["continue learning", "start exam"]


class LearnerStudyContentResponse(BaseModel):
    learning_content_id: str
    title: str
    summary: str | None = None
    owner: str | None = None
    source: str | None = None
    chapters: list[LearningChapterResponse]
    progress: LearningProgressResponse


class ChapterCompleteResponse(BaseModel):
    chapter_id: str
    already_completed: bool
    progress: LearningProgressResponse


class LearnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    self_assessed_level: LearnerLevel | None = None
    admin_overridden_level: LearnerLevel | None = None
    effective_level: LearnerLevel
    self_assessed_at: object | None = None
    overridden_by: str | None = None
    overridden_at: object | None = None


class LearnerSelfAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: LearnerLevel


class LearnerAdminOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: LearnerLevel


class ReferenceReader(Protocol):
    def __call__(
        self, asset_type: str, asset_id: str
    ) -> object | Awaitable[object | None] | None: ...


class PracticeTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    scenario_type: PracticeTemplateScenarioType
    mode: PracticeTemplateMode
    agent_id: str = Field(..., min_length=1, max_length=36)
    persona_id: str = Field(..., min_length=1, max_length=36)
    runtime_profile_id: str = Field(..., min_length=1, max_length=36)
    voice_mode: PracticeTemplateVoiceMode = "stepfun_realtime"
    scoring_ruleset_id: str = Field(..., min_length=1, max_length=36)
    knowledge_base_refs: list[str] = Field(default_factory=list)
    case_item_id: str | None = Field(None, min_length=1, max_length=36)
    role_profile_id: str | None = Field(None, min_length=1, max_length=36)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    examiner_agent_id: str | None = Field(None, min_length=1, max_length=36)
    target_learner_level: LearnerLevel | None = None
    timeout_config: dict[str, object] | None = None
    curriculum_plan: CurriculumPlanSchema | None = None
    max_stage_duration_seconds: int | None = Field(None, ge=1, le=1500)


class PracticeTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    scenario_type: PracticeTemplateScenarioType | None = None
    mode: PracticeTemplateMode | None = None
    agent_id: str | None = Field(None, min_length=1, max_length=36)
    persona_id: str | None = Field(None, min_length=1, max_length=36)
    runtime_profile_id: str | None = Field(None, min_length=1, max_length=36)
    voice_mode: PracticeTemplateVoiceMode | None = None
    scoring_ruleset_id: str | None = Field(None, min_length=1, max_length=36)
    knowledge_base_refs: list[str] | None = None
    case_item_id: str | None = Field(None, min_length=1, max_length=36)
    role_profile_id: str | None = Field(None, min_length=1, max_length=36)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    examiner_agent_id: str | None = Field(None, min_length=1, max_length=36)
    target_learner_level: LearnerLevel | None = None
    timeout_config: dict[str, object] | None = None
    curriculum_plan: CurriculumPlanSchema | None = None
    max_stage_duration_seconds: int | None = Field(None, ge=1, le=1500)


class PracticeTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: str
    name: str
    description: str | None = None
    scenario_type: str
    mode: str
    agent_id: str
    persona_id: str
    runtime_profile_id: str
    voice_mode: str
    scoring_ruleset_id: str
    knowledge_base_refs: list[str]
    case_item_id: str | None = None
    role_profile_id: str | None = None
    learning_content_id: str | None = None
    examiner_agent_id: str | None = None
    target_learner_level: str | None = None
    timeout_config: dict[str, object] | None = None
    curriculum_plan: CurriculumPlanSchema | None = None
    max_stage_duration_seconds: int | None = None
    status: str
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class PracticeTemplateListResponse(BaseModel):
    items: list[PracticeTemplateResponse]
    total: int

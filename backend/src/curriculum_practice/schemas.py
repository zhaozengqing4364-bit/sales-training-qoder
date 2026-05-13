from __future__ import annotations

from collections.abc import Awaitable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

PracticeTemplateStatus = Literal["draft", "published", "archived"]
ContentAssetStatus = Literal["draft", "published", "archived"]
RoleProfilePressureLevel = Literal["low", "medium", "high"]
PracticeTemplateScenarioType = Literal["sales", "presentation"]
PracticeTemplateVoiceMode = Literal["legacy", "stepfun_realtime"]
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
]
SnapshotLabel = Literal["published", "superseded", "legacy_unversioned"]


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


class PublishedTemplateRef(BaseModel):
    asset_type: Literal["practice_template"] = "practice_template"
    asset_id: str
    version: int
    hash: str
    snapshot_label: Literal["published"] = "published"


class CurriculumVersionRef(BaseModel):
    asset_type: CurriculumAssetType
    asset_id: str
    version: int | str
    hash: str
    snapshot_label: SnapshotLabel


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
    rubric: CurriculumVersionRef
    runtime: CurriculumRuntimeRef


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

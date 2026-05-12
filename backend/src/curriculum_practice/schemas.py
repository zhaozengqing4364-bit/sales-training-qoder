from __future__ import annotations

from collections.abc import Awaitable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

PracticeTemplateStatus = Literal["draft", "published", "archived"]
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
    llm_nodes: list[dict[str, object]] = Field(default_factory=list)


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
    status: str
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class PracticeTemplateListResponse(BaseModel):
    items: list[PracticeTemplateResponse]
    total: int

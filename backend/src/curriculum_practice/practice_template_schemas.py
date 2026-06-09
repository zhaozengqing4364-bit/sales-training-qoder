from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from curriculum_practice.curriculum_runtime_schemas import CurriculumPlanSchema
from curriculum_practice.schema_types import (
    LearnerLevel,
    PracticeTemplateMode,
    PracticeTemplateScenarioType,
    PracticeTemplateVoiceMode,
)


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
    situation_pack_code: str | None = Field(None, min_length=1, max_length=60)


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
    situation_pack_code: str | None = Field(None, min_length=1, max_length=60)


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
    situation_pack_code: str | None = Field(None, min_length=1, max_length=60)


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
    curriculum_plan: dict[str, Any] | None = None
    max_stage_duration_seconds: int | None = None
    situation_pack_code: str | None = None
    published_asset_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status: str
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class PracticeTemplateListResponse(BaseModel):
    items: list[PracticeTemplateResponse]
    total: int

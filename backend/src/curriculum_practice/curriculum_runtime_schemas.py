from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum_practice.asset_ref_schemas import CurriculumVersionRef
from curriculum_practice.schema_types import CurriculumStageType, LearnerLevel


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
                raise ValueError("stage duration exceeds max_stage_duration_seconds")
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
    roleplay_contract: dict[str, object] | None = None
    role_profile_voice_id: str | None = None
    learner_level: LearnerLevel = "conservative"
    asset_resolution: dict[str, object] | None = None
    legacy_warnings: list[str] = Field(default_factory=list)
    stage_snapshots: dict[str, TemplateStageSnapshot] = Field(default_factory=dict)
    llm_nodes: list[dict[str, object]] = Field(default_factory=list)

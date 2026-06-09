from __future__ import annotations

from pydantic import BaseModel, Field

from curriculum_practice.schema_types import RuntimeDossierStatus


class RuntimeDossierConsistencyCheck(BaseModel):
    key: str
    status: RuntimeDossierStatus
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class RuntimeDossierConsistency(BaseModel):
    status: RuntimeDossierStatus
    checks: list[RuntimeDossierConsistencyCheck]


class RuntimeDossierProbeResult(BaseModel):
    key: str
    prompt: str
    expected_behavior: str
    status: RuntimeDossierStatus
    matched_evidence: list[str] = Field(default_factory=list)
    source_assets: list[str] = Field(default_factory=list)


class PracticeTemplateRuntimeDossierPreview(BaseModel):
    template_id: str
    name: str
    generated_at: str
    summary: dict[str, object]
    sections: dict[str, dict[str, object]]
    consistency: RuntimeDossierConsistency
    probes: list[RuntimeDossierProbeResult]

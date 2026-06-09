from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum_practice.schema_types import (
    ContentAssetStatus,
    RoleProfilePressureLevel,
)


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
            raise ValueError(
                "allowed_disclosure_policy.phases must contain at least one phase"
            )
        return self


class CaseItemCreate(CaseItemBase):
    pass


class CaseItemResponse(CaseItemBase):
    model_config = ConfigDict(from_attributes=True)

    case_item_id: str
    status: ContentAssetStatus
    version: int
    published_at: object | None = None
    created_at: object
    updated_at: object


class CaseItemListResponse(BaseModel):
    items: list[CaseItemResponse]
    total: int


class TemplateReferenceItem(BaseModel):
    template_id: str
    name: str
    status: str


class TemplateReferenceListResponse(BaseModel):
    items: list[TemplateReferenceItem]
    total: int


class UnpublishAcknowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledge: bool = False


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

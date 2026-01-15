"""
Pydantic Schemas for Model Configuration API

Request/Response schemas for AI Model Configuration management.
Uses Pydantic v2 with ConfigDict(from_attributes=True).

References:
- Requirements: R2 (CRUD API), R3 (Validation)
- Design: model-config-management/design.md
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from common.ai.models import ModelProvider, ModelType


# ========== Request Schemas ==========

class CreateModelConfigRequest(BaseModel):
    """Request schema for creating a model configuration"""
    name: str = Field(..., max_length=100, description="Display name")
    model_type: ModelType = Field(..., description="Model type: llm/embedding/asr/tts")
    provider: ModelProvider = Field(..., description="Provider: openai/azure/alibaba/local")
    base_url: str = Field(..., max_length=500, description="API endpoint URL")
    api_key: str = Field(..., description="API key (will be encrypted)")
    model_name: str = Field(..., max_length=100, description="Model name, e.g., gpt-4o")
    extra_config: dict[str, Any] = Field(default_factory=dict, description="Provider-specific config")
    is_default: bool = Field(default=False, description="Set as default for this type")


class UpdateModelConfigRequest(BaseModel):
    """Request schema for updating a model configuration (partial update)"""
    name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, description="New API key (will be encrypted)")
    model_name: str | None = Field(None, max_length=100)
    extra_config: dict[str, Any] | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class TestModelConfigRequest(BaseModel):
    """Request schema for testing a model configuration before saving"""
    model_type: ModelType
    provider: ModelProvider
    base_url: str
    api_key: str
    model_name: str
    extra_config: dict[str, Any] = Field(default_factory=dict)


# ========== Response Schemas ==========

class ModelConfigResponse(BaseModel):
    """Full model configuration response (with masked API key)"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    model_type: str
    provider: str
    base_url: str
    api_key_masked: str = Field(..., description="Masked API key, e.g., sk-...xxxx")
    model_name: str
    extra_config: dict[str, Any]
    is_default: bool
    is_active: bool
    last_tested_at: datetime | None
    last_test_status: str | None
    created_at: datetime
    updated_at: datetime


class ModelConfigListItem(BaseModel):
    """Model configuration list item"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    model_type: str
    provider: str
    model_name: str
    is_default: bool
    is_active: bool
    last_test_status: str | None


class ModelConfigListResponse(BaseModel):
    """Grouped model configuration list response"""
    llm: list[ModelConfigListItem] = Field(default_factory=list)
    embedding: list[ModelConfigListItem] = Field(default_factory=list)
    asr: list[ModelConfigListItem] = Field(default_factory=list)
    tts: list[ModelConfigListItem] = Field(default_factory=list)
    total: int


class TestConfigResponse(BaseModel):
    """Response for configuration test"""
    success: bool
    message: str
    latency_ms: int | None = None
    details: dict[str, Any] | None = None


class ModelConfigCreateResponse(BaseModel):
    """Response after creating a model configuration"""
    id: str
    name: str
    model_type: str
    provider: str
    model_name: str
    is_default: bool
    created_at: datetime


# ========== API Response Wrappers ==========

class ModelConfigSuccessResponse(BaseModel):
    """Success response wrapper"""
    success: bool = True
    data: ModelConfigResponse | ModelConfigListResponse | ModelConfigCreateResponse | None = None
    trace_id: str | None = None


class TestConfigSuccessResponse(BaseModel):
    """Success response wrapper for test endpoint"""
    success: bool = True
    data: TestConfigResponse | None = None
    trace_id: str | None = None


class ModelConfigErrorResponse(BaseModel):
    """Error response wrapper"""
    success: bool = False
    error: str
    error_code: str
    trace_id: str | None = None

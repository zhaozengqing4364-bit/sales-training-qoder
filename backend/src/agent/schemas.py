"""
Pydantic Schemas for Agent, Persona, and AgentPersona

Request/Response schemas for Agent Platform APIs.
Uses Pydantic v2 with ConfigDict(from_attributes=True).

References:
- Requirements: R1-R4 (Agent/Persona management)
- Design: Section 13-15 (Data Models)
- API Contract: docs/api-contract/agents.md, docs/api-contract/personas.md
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ========== Enums as Literals for API ==========
# Using Literal types for cleaner API documentation

AgentStatusType = str  # "draft" | "published" | "archived"
AgentCategoryType = str  # "sales" | "presentation" | "interview" | "customer_service"
PersonaCategoryType = str  # "customer" | "interviewer" | "coach" | "examiner"
PersonaDifficultyType = str  # "easy" | "medium" | "hard"
PersonaStatusType = str  # "active" | "inactive"


# ========== TTS Config Schema ==========
class TTSConfigSchema(BaseModel):
    """TTS configuration for voice synthesis"""

    voice: str = Field(
        default="zh-CN-XiaoxiaoNeural",
        description="Voice name (e.g., zh-CN-XiaoxiaoNeural)",
    )
    rate: str = Field(default="+0%", description="Speech rate (e.g., +0%, +20%, -10%)")
    volume: str = Field(default="+0%", description="Volume (e.g., +0%, +20%, -10%)")
    pitch: str = Field(default="+0Hz", description="Pitch (e.g., +0Hz, +10Hz, -5Hz)")


# ========== Behavior Config Schema ==========
class BehaviorConfigSchema(BaseModel):
    """Persona behavior configuration - R3.8"""

    response_length: str = Field(
        default="medium", description="Response length: short|medium|long"
    )
    challenge_frequency: float = Field(
        default=0.5, ge=0, le=1, description="Challenge frequency 0-1"
    )
    interruption_triggers: list[str] = Field(
        default_factory=list, description="Words that trigger interruption"
    )
    typical_questions: list[str] = Field(
        default_factory=list, description="Typical questions this persona asks"
    )


# ========== Scoring Dimension Schema ==========
class ScoringDimensionSchema(BaseModel):
    """Scoring dimension with weight"""

    name: str = Field(..., description="Dimension name")
    weight: float = Field(..., ge=0, le=1, description="Weight 0-1")


# ========== Agent Schemas ==========


class AgentBase(BaseModel):
    """Base Agent fields for create/update"""

    name: str = Field(..., max_length=100, description="Agent name")
    description: str | None = Field(
        None, max_length=500, description="Agent description"
    )
    icon: str | None = Field(None, max_length=50, description="Icon URL or emoji")
    category: AgentCategoryType = Field(
        ..., description="Category: sales|presentation|interview|customer_service"
    )


class CreateAgentRequest(AgentBase):
    """Request schema for creating an Agent - R1.1"""

    system_prompt: str | None = Field(None, description="System prompt for AI")
    welcome_message: str | None = Field(None, description="Welcome message for users")
    capabilities_config: dict[str, Any] = Field(
        default_factory=dict, description="Capability module configurations"
    )
    default_knowledge_base_ids: list[str] = Field(
        default_factory=list, description="Default knowledge base IDs"
    )


class UpdateAgentRequest(BaseModel):
    """Request schema for updating an Agent - R1.4 (partial update)"""

    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=50)
    category: AgentCategoryType | None = None
    system_prompt: str | None = None
    welcome_message: str | None = None
    capabilities_config: dict[str, Any] | None = None
    default_knowledge_base_ids: list[str] | None = None


class AgentResponse(AgentBase):
    """Full Agent response for admin - R1.3"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_prompt: str | None = None
    welcome_message: str | None = None
    capabilities_config: dict[str, Any] = Field(default_factory=dict)
    default_knowledge_base_ids: list[str] = Field(default_factory=list)
    status: AgentStatusType
    version: int
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class AgentListItem(BaseModel):
    """Agent list item for listing - R1.2"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    category: AgentCategoryType
    status: AgentStatusType
    persona_count: int = 0
    knowledge_base_count: int = 0


class AgentListResponse(BaseModel):
    """Paginated Agent list response"""

    agents: list[AgentListItem]
    total: int
    page: int
    page_size: int


class AgentUserResponse(BaseModel):
    """Agent response for users (without system_prompt) - R2.2"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    category: AgentCategoryType
    welcome_message: str | None = None
    capabilities: list[str] = Field(
        default_factory=list, description="List of enabled capability names"
    )


class AgentCreateResponse(BaseModel):
    """Response after creating an Agent"""

    id: str
    name: str
    status: AgentStatusType
    created_at: datetime


class AgentPublishResponse(BaseModel):
    """Response after publishing an Agent"""

    id: str
    status: AgentStatusType
    published_at: datetime


# ========== Persona Schemas ==========


class PersonaBase(BaseModel):
    """Base Persona fields for create/update"""

    name: str = Field(..., max_length=100, description="Persona name")
    description: str | None = Field(
        None, max_length=500, description="Persona description"
    )
    icon: str | None = Field(None, max_length=50, description="Icon emoji or name")
    category: PersonaCategoryType = Field(
        ..., description="Category: customer|interviewer|coach|examiner"
    )
    difficulty: PersonaDifficultyType = Field(
        default="medium", description="Difficulty: easy|medium|hard"
    )


class CreatePersonaRequest(PersonaBase):
    """Request schema for creating a Persona - R3.1"""

    system_prompt: str = Field(..., description="System prompt for AI character")
    traits: dict[str, str] = Field(
        default_factory=dict,
        description="Character traits e.g. {'性格': '怀疑', '关注点': '证据'}",
    )
    knowledge_base_ids: list[str] = Field(
        default_factory=list, description="Persona-specific knowledge base IDs"
    )
    behavior_config: BehaviorConfigSchema = Field(
        default_factory=BehaviorConfigSchema, description="Behavior configuration"
    )
    scoring_weights: dict[str, float] | None = Field(
        None, description="Scoring weights to override Agent defaults"
    )
    tts_config: TTSConfigSchema | None = Field(
        None, description="TTS configuration (overrides system default)"
    )
    is_public: bool = Field(default=True, description="Whether publicly visible")


class UpdatePersonaRequest(BaseModel):
    """Request schema for updating a Persona - R3.4 (partial update)"""

    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=50)
    category: PersonaCategoryType | None = None
    difficulty: PersonaDifficultyType | None = None
    system_prompt: str | None = None
    traits: dict[str, str] | None = None
    knowledge_base_ids: list[str] | None = None
    behavior_config: BehaviorConfigSchema | None = None
    scoring_weights: dict[str, float] | None = None
    tts_config: TTSConfigSchema | None = None
    is_public: bool | None = None
    status: PersonaStatusType | None = None


class PersonaResponse(PersonaBase):
    """Full Persona response for admin - R3.3"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_prompt: str
    traits: dict[str, str] = Field(default_factory=dict)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    behavior_config: dict[str, Any] = Field(default_factory=dict)
    scoring_weights: dict[str, float] | None = None
    tts_config: dict[str, Any] | None = None
    is_public: bool
    status: PersonaStatusType
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PersonaListItem(BaseModel):
    """Persona list item for listing - R3.2"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    category: PersonaCategoryType
    difficulty: PersonaDifficultyType
    status: PersonaStatusType
    is_public: bool
    usage_count: int = 0
    agent_count: int = 0


class PersonaListResponse(BaseModel):
    """Paginated Persona list response"""

    personas: list[PersonaListItem]
    total: int
    page: int
    page_size: int


class PersonaCreateResponse(BaseModel):
    """Response after creating a Persona"""

    id: str
    name: str
    status: PersonaStatusType
    created_at: datetime


class PersonaUserListItem(BaseModel):
    """Persona list item for users (in Agent context) - R2.3"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    difficulty: PersonaDifficultyType
    is_default: bool = False


# ========== AgentPersona Schemas ==========


class CreateAgentPersonaRequest(BaseModel):
    """Request schema for linking Persona to Agent - R4.1"""

    persona_id: str = Field(..., description="Persona ID to link")
    display_order: int = Field(default=0, ge=0, description="Display order")
    is_default: bool = Field(
        default=False, description="Whether this is the default persona"
    )
    override_config: dict[str, Any] | None = Field(
        None, description="Configuration overrides for this association"
    )


class UpdateAgentPersonaRequest(BaseModel):
    """Request schema for updating Agent-Persona association - R4.3"""

    display_order: int | None = Field(None, ge=0)
    is_default: bool | None = None
    override_config: dict[str, Any] | None = None


class AgentPersonaResponse(BaseModel):
    """AgentPersona association response - R4.2"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    persona_id: str
    display_order: int
    is_default: bool
    override_config: dict[str, Any] | None = None
    created_at: datetime


class AgentPersonaWithDetails(AgentPersonaResponse):
    """AgentPersona with embedded Persona details"""

    persona: PersonaListItem


class AgentPersonaListResponse(BaseModel):
    """List of Agent-Persona associations"""

    personas: list[AgentPersonaWithDetails]


# ========== API Response Wrappers ==========
# Following Result[T] pattern from common/error_handling/result.py


class SuccessResponse(BaseModel):
    """Generic success response wrapper"""

    success: bool = True
    data: Any
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    """Error response wrapper"""

    success: bool = False
    error: str
    error_code: str
    trace_id: str | None = None

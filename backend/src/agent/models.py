"""
Agent Platform SQLAlchemy Models

Models for Agent, Persona, and AgentPersona entities.
Uses String(36) for UUID storage to maintain compatibility with SQLite and PostgreSQL.

References:
- Requirements: R1-R4 (Agent/Persona management)
- Design: Section 13-15 (Data Models)
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from common.db.models import Base


class AgentStatus(str, enum.Enum):
    """Agent lifecycle status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AgentCategory(str, enum.Enum):
    """Agent training scenario categories"""
    SALES = "sales"
    PRESENTATION = "presentation"
    INTERVIEW = "interview"
    CUSTOMER_SERVICE = "customer_service"


class PersonaCategory(str, enum.Enum):
    """Persona role categories"""
    CUSTOMER = "customer"
    INTERVIEWER = "interviewer"
    COACH = "coach"
    EXAMINER = "examiner"


class PersonaDifficulty(str, enum.Enum):
    """Persona difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class PersonaStatus(str, enum.Enum):
    """Persona status"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Agent(Base):
    """
    Agent - Configurable AI training scenario

    An Agent represents a training scenario (e.g., Sales Coach, Presentation Coach)
    with specific capabilities and behavior configurations.

    Requirements: R1, R2
    Design: Section 13
    """
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon = Column(String(50))
    category = Column(String(50), nullable=False)  # sales|presentation|interview|customer_service

    # AI Configuration
    system_prompt = Column(Text)
    welcome_message = Column(Text)
    capabilities_config = Column(JSON, default=dict)  # Capability module configurations
    default_knowledge_base_ids = Column(JSON, default=list)  # Default knowledge bases

    # Lifecycle
    status = Column(String(20), default="draft", index=True)
    version = Column(Integer, default=1)

    # Audit
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_agent_status"
        ),
        CheckConstraint(
            "category IN ('sales', 'presentation', 'interview', 'customer_service')",
            name="ck_agent_category"
        ),
        Index("idx_agents_status", "status"),
        Index("idx_agents_category", "category"),
        Index("idx_agents_created_at", "created_at"),
    )

    # Relationships
    personas = relationship(
        "AgentPersona",
        back_populates="agent",
        cascade="all, delete-orphan"
    )
    # Sessions using this Agent (R12: Session Management Enhancement)
    sessions = relationship(
        "PracticeSession",
        back_populates="agent",
        foreign_keys="PracticeSession.agent_id"
    )
    voice_policy = relationship(
        "AgentVoicePolicy",
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Persona(Base):
    """
    Persona - AI character for practice interactions

    A Persona represents an AI character (e.g., Skeptical Buyer, Impatient CEO)
    that users interact with during practice sessions.

    Requirements: R3
    Design: Section 14
    """
    __tablename__ = "personas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon = Column(String(50))
    category = Column(String(50), nullable=False)  # customer|interviewer|coach|examiner
    difficulty = Column(String(20), default="medium")  # easy|medium|hard

    # AI Configuration
    system_prompt = Column(Text, nullable=False)
    traits = Column(JSON, default=dict)  # {"性格": "怀疑", "关注点": "证据"}
    knowledge_base_ids = Column(JSON, default=list)  # Persona-specific knowledge bases
    behavior_config = Column(JSON, default=dict)  # BehaviorConfig
    scoring_weights = Column(JSON, nullable=True)  # Override Agent default weights

    # TTS Configuration (overrides system default)
    # {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%", "volume": "+0%", "pitch": "+0Hz"}
    tts_config = Column(JSON, nullable=True)

    # Visibility
    is_public = Column(Boolean, default=True)
    status = Column(String(20), default="active")  # active|inactive

    # Audit
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_persona_status"
        ),
        CheckConstraint(
            "category IN ('customer', 'interviewer', 'coach', 'examiner')",
            name="ck_persona_category"
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_persona_difficulty"
        ),
        Index("idx_personas_category", "category"),
        Index("idx_personas_difficulty", "difficulty"),
        Index("idx_personas_status", "status"),
    )

    # Relationships
    agent_personas = relationship(
        "AgentPersona",
        back_populates="persona"
    )
    # Sessions using this Persona (R12: Session Management Enhancement)
    sessions = relationship(
        "PracticeSession",
        back_populates="persona",
        foreign_keys="PracticeSession.persona_id"
    )


class AgentPersona(Base):
    """
    AgentPersona - Association between Agent and Persona

    Links Personas to Agents with display order and optional configuration overrides.
    Each Agent can have multiple Personas, but only one can be the default.

    Requirements: R4
    Design: Section 15
    """
    __tablename__ = "agent_personas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False
    )
    persona_id = Column(
        String(36),
        ForeignKey("personas.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Display configuration
    display_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    override_config = Column(JSON, nullable=True)  # Override Persona configuration

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("agent_id", "persona_id", name="uq_agent_persona"),
        Index("idx_agent_personas_agent", "agent_id"),
        Index("idx_agent_personas_persona", "persona_id"),
    )

    # Relationships
    agent = relationship("Agent", back_populates="personas")
    persona = relationship("Persona", back_populates="agent_personas")


class VoiceRuntimeProfile(Base):
    """
    VoiceRuntimeProfile - Realtime voice runtime profile

    Stores reusable runtime presets for voice mode routing, StepFun model
    parameters, and tool policies (web search / internal retrieval).
    """
    __tablename__ = "voice_runtime_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)

    # Lifecycle
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Runtime mode and model settings
    voice_mode = Column(String(32), nullable=False, default="stepfun_realtime")
    model_name = Column(String(100), nullable=False, default="step-audio-2")
    voice_name = Column(String(100), nullable=False, default="qingchunshaonv")
    temperature = Column(Float, nullable=False, default=0.7)
    input_audio_format = Column(String(20), nullable=False, default="pcm16")
    output_audio_format = Column(String(20), nullable=False, default="pcm16")
    output_sample_rate = Column(Integer, nullable=False, default=24000)
    turn_detection = Column(String(32), nullable=True, default=None)  # null | server_vad

    # Prompt/tool policies
    system_instruction_template = Column(Text, nullable=True)
    tool_policy = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_voice_runtime_profile_mode",
        ),
        CheckConstraint(
            "temperature >= 0 AND temperature <= 2",
            name="ck_voice_runtime_profile_temperature",
        ),
        CheckConstraint(
            "output_sample_rate > 0",
            name="ck_voice_runtime_profile_sample_rate",
        ),
        Index("idx_voice_runtime_profiles_default", "is_default"),
        Index("idx_voice_runtime_profiles_active", "is_active"),
        Index("idx_voice_runtime_profiles_mode", "voice_mode"),
    )

    agent_policies = relationship(
        "AgentVoicePolicy",
        back_populates="runtime_profile",
    )


class AgentVoicePolicy(Base):
    """
    AgentVoicePolicy - Per-agent runtime policy overrides

    Defines which runtime profile the Agent uses by default and optional
    per-agent overrides for voice mode, model params, and tool policies.
    """
    __tablename__ = "agent_voice_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    runtime_profile_id = Column(
        String(36),
        ForeignKey("voice_runtime_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    enabled = Column(Boolean, nullable=False, default=True)
    voice_mode_override = Column(String(32), nullable=True)
    model_override = Column(String(100), nullable=True)
    voice_override = Column(String(100), nullable=True)
    temperature_override = Column(Float, nullable=True)
    instructions_override = Column(Text, nullable=True)
    tool_policy_override = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "voice_mode_override IS NULL OR voice_mode_override IN ('legacy', 'stepfun_realtime')",
            name="ck_agent_voice_policy_mode",
        ),
        CheckConstraint(
            "temperature_override IS NULL OR (temperature_override >= 0 AND temperature_override <= 2)",
            name="ck_agent_voice_policy_temperature",
        ),
        Index("idx_agent_voice_policy_agent", "agent_id"),
        Index("idx_agent_voice_policy_profile", "runtime_profile_id"),
    )

    agent = relationship("Agent", back_populates="voice_policy")
    runtime_profile = relationship("VoiceRuntimeProfile", back_populates="agent_policies")


class PresentationAIPolicy(Base):
    """
    PresentationAIPolicy - Scope-based AI policy for PPT coaching.

    Scope priority:
    global < scenario < presentation
    """

    __tablename__ = "presentation_ai_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope_type = Column(String(20), nullable=False, default="global")
    scope_id = Column(String(64), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)

    # Prompt-first configuration (template binding)
    prompt_config = Column(JSON, nullable=False, default=dict)
    # Rule engine configuration (thresholds/cooldowns)
    rule_config = Column(JSON, nullable=False, default=dict)
    # Hard guardrail fallback toggles
    fallback_config = Column(JSON, nullable=False, default=dict)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('global', 'scenario', 'presentation')",
            name="ck_presentation_ai_policy_scope_type",
        ),
        CheckConstraint(
            "((scope_type = 'global' AND scope_id IS NULL) "
            "OR (scope_type IN ('scenario', 'presentation') AND scope_id IS NOT NULL))",
            name="ck_presentation_ai_policy_scope_id",
        ),
        UniqueConstraint(
            "scope_type",
            "scope_id",
            name="uq_presentation_ai_policy_scope",
        ),
        Index(
            "idx_presentation_ai_policy_scope",
            "scope_type",
            "scope_id",
        ),
        Index("idx_presentation_ai_policy_enabled", "enabled"),
    )

    updater = relationship("User", foreign_keys=[updated_by])

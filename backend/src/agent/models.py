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
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("agent_id", "persona_id", name="uq_agent_persona"),
        Index("idx_agent_personas_agent", "agent_id"),
        Index("idx_agent_personas_persona", "persona_id"),
    )

    # Relationships
    agent = relationship("Agent", back_populates="personas")
    persona = relationship("Persona", back_populates="agent_personas")

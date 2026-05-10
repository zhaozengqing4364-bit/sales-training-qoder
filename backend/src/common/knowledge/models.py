"""
Knowledge Base SQLAlchemy Models

Models for KnowledgeBase and KnowledgeDocument entities.
Uses String(36) for UUID storage to maintain compatibility with SQLite and PostgreSQL.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 16-17 (Data Models)
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
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
from sqlalchemy.orm import relationship

from common.db.models import Base


class KnowledgeBaseCategory(str, enum.Enum):
    """Knowledge base categories"""

    PRODUCT = "product"
    COMPETITOR = "competitor"
    FAQ = "faq"
    POLICY = "policy"


class KnowledgeBaseStatus(str, enum.Enum):
    """Knowledge base status"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentStatus(str, enum.Enum):
    """Document processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentFileType(str, enum.Enum):
    """Supported document file types"""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    XLSX = "xlsx"
    XLS = "xls"


class KnowledgeDictionaryEntryStatus(str, enum.Enum):
    """Knowledge-base scoped dictionary entry lifecycle."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class KnowledgeBase(Base):
    """
    KnowledgeBase - Document collection for AI context

    A KnowledgeBase represents a collection of documents that can be used
    to provide context and information for AI conversations.

    Requirements: R5
    Design: Section 16
    """

    __tablename__ = "knowledge_bases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    category = Column(String(50), nullable=False)  # product|competitor|faq|policy

    # Vector store configuration
    vector_collection = Column(String(100), nullable=False)  # ChromaDB collection name
    embedding_model = Column(String(100), default="text-embedding-ada-002")

    # Statistics
    document_count = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)

    # Lifecycle
    status = Column(String(20), default="active", index=True)

    # Configuration (JSON: chunking, semantic cache, etc.)
    settings = Column(Text, nullable=True)

    # RAG profile reference (unified config management)
    rag_profile_id = Column(
        String(36),
        ForeignKey("rag_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Chunking preset key referencing active config version's chunking_presets
    chunking_preset_key = Column(String(100), nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')", name="ck_knowledge_base_status"
        ),
        CheckConstraint(
            "category IN ('product', 'competitor', 'faq', 'policy')",
            name="ck_knowledge_base_category",
        ),
        Index("idx_knowledge_bases_status", "status"),
        Index("idx_knowledge_bases_category", "category"),
        Index("idx_knowledge_bases_created_at", "created_at"),
    )

    # Relationships
    documents = relationship(
        "KnowledgeDocument",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    dictionary_entries = relationship(
        "KnowledgeDictionaryEntry",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    rag_profile = relationship(
        "RagProfile",
        back_populates="knowledge_bases",
    )


class KnowledgeDocument(Base):
    """
    KnowledgeDocument - Document within a knowledge base

    A KnowledgeDocument represents a single document (PDF, DOCX, TXT, MD, XLSX, XLS)
    that has been uploaded to a knowledge base for processing and vectorization.

    Requirements: R5
    Design: Section 17
    """

    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id = Column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )

    # Document metadata
    title = Column(String(200), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf|docx|txt|md|xlsx|xls
    file_url = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    content_hash = Column(String(64), nullable=True, index=True)

    # Processing status
    status = Column(
        String(20), default="pending", index=True
    )  # pending|processing|ready|failed
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_knowledge_document_status",
        ),
        CheckConstraint(
            "file_type IN ('pdf', 'docx', 'txt', 'md', 'xlsx', 'xls')",
            name="ck_knowledge_document_file_type",
        ),
        UniqueConstraint(
            "knowledge_base_id",
            "content_hash",
            name="uq_knowledge_document_kb_content_hash",
        ),
        Index("idx_knowledge_documents_status", "status"),
        Index("idx_knowledge_documents_knowledge_base", "knowledge_base_id"),
        Index("idx_knowledge_documents_created_at", "created_at"),
    )

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")


class KnowledgeDictionaryEntry(Base):
    """KB-scoped canonical term and ASR/search alias dictionary entry."""

    __tablename__ = "knowledge_dictionary_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id = Column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    canonical_term = Column(String(255), nullable=False)
    aliases_json = Column(Text, nullable=False, default="[]")
    term_type = Column(String(50), nullable=False, default="other")
    status = Column(String(20), nullable=False, default="draft", index=True)
    confidence = Column(Integer, nullable=False, default=95)
    source = Column(String(50), nullable=False, default="manual")
    evidence_count = Column(Integer, nullable=False, default=0)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_knowledge_dictionary_entry_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_knowledge_dictionary_entry_confidence",
        ),
        UniqueConstraint(
            "knowledge_base_id",
            "canonical_term",
            name="uq_knowledge_dictionary_entry_kb_canonical",
        ),
        Index("idx_knowledge_dictionary_entries_kb", "knowledge_base_id"),
        Index("idx_knowledge_dictionary_entries_status", "status"),
    )

    knowledge_base = relationship(
        "KnowledgeBase", back_populates="dictionary_entries"
    )


# ── Late import to register RagProfile in SQLAlchemy metadata ──
# KnowledgeBase.rag_profile relationship references RagProfile by string name.
# SQLAlchemy needs the class to be imported into the same registry at mapper
# configuration time. Importing here ensures it happens when this module loads.
from common.knowledge.rag_profile_models import RagProfile  # noqa: E402, F401

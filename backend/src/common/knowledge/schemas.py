"""
Pydantic Schemas for KnowledgeBase and KnowledgeDocument

Request/Response schemas for Knowledge Management APIs.
Uses Pydantic v2 with ConfigDict(from_attributes=True).

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 16-17 (Data Models)
- API Contract: docs/api-contract/knowledge.md
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ========== Type Aliases for API ==========
KnowledgeBaseCategoryType = str  # "product" | "competitor" | "faq" | "policy"
KnowledgeBaseStatusType = str  # "active" | "archived"
DocumentStatusType = str  # "pending" | "processing" | "ready" | "failed"
DocumentFileTypeType = str  # "pdf" | "docx" | "txt" | "md"


# ========== KnowledgeBase Schemas ==========


class KnowledgeBaseBase(BaseModel):
    """Base KnowledgeBase fields for create/update"""

    name: str = Field(..., max_length=100, description="Knowledge base name")
    description: str | None = Field(
        None, max_length=500, description="Knowledge base description"
    )
    category: KnowledgeBaseCategoryType = Field(
        ..., description="Category: product|competitor|faq|policy"
    )


class CreateKnowledgeBaseRequest(KnowledgeBaseBase):
    """Request schema for creating a KnowledgeBase - R5.1"""

    pass


class UpdateKnowledgeBaseRequest(BaseModel):
    """Request schema for updating a KnowledgeBase - R5.3 (partial update)"""

    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    category: KnowledgeBaseCategoryType | None = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    """Full KnowledgeBase response for admin - R5.3"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    vector_collection: str = Field(..., description="ChromaDB collection name")
    embedding_model: str = Field(
        default="text-embedding-ada-002", description="Embedding model"
    )
    document_count: int = Field(default=0, description="Number of documents")
    total_chunks: int = Field(default=0, description="Total number of chunks")
    status: KnowledgeBaseStatusType
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListItem(BaseModel):
    """KnowledgeBase list item for listing - R5.2"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    category: KnowledgeBaseCategoryType
    document_count: int = 0
    total_chunks: int = 0
    status: KnowledgeBaseStatusType
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    """Paginated KnowledgeBase list response"""

    knowledge_bases: list[KnowledgeBaseListItem]
    total: int
    page: int
    page_size: int


class KnowledgeBaseCreateResponse(BaseModel):
    """Response after creating a KnowledgeBase"""

    id: str
    name: str
    category: KnowledgeBaseCategoryType
    vector_collection: str
    document_count: int = 0
    status: KnowledgeBaseStatusType
    created_at: datetime


# ========== KnowledgeDocument Schemas ==========


class KnowledgeDocumentBase(BaseModel):
    """Base KnowledgeDocument fields"""

    title: str = Field(..., max_length=200, description="Document title")


class CreateKnowledgeDocumentRequest(KnowledgeDocumentBase):
    """Request schema for uploading a document - R5.3

    Note: The actual file is handled separately as multipart/form-data.
    This schema is for the metadata portion of the request.
    """

    pass


class KnowledgeDocumentResponse(KnowledgeDocumentBase):
    """Full KnowledgeDocument response - R5.3"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    file_type: DocumentFileTypeType = Field(
        ..., description="File type: pdf|docx|txt|md"
    )
    file_url: str = Field(..., description="File storage URL")
    file_size: int = Field(..., description="File size in bytes")
    status: DocumentStatusType = Field(..., description="Processing status")
    chunk_count: int = Field(default=0, description="Number of chunks")
    error_message: str | None = Field(
        None, description="Error message if processing failed"
    )
    created_at: datetime


class KnowledgeDocumentListItem(BaseModel):
    """KnowledgeDocument list item for listing"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    file_type: DocumentFileTypeType
    file_size: int
    status: DocumentStatusType
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    """Paginated KnowledgeDocument list response"""

    documents: list[KnowledgeDocumentListItem]
    total: int
    page: int
    page_size: int


class KnowledgeDocumentUploadResponse(BaseModel):
    """Response after uploading a document (202 Accepted) - R5.3"""

    id: str
    title: str
    file_type: DocumentFileTypeType
    file_size: int
    status: DocumentStatusType = "pending"
    created_at: datetime


# ========== Document Preview Schemas ==========


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk"""

    page: int | None = Field(None, description="Page number (for PDF)")
    page_end: int | None = Field(None, description="Last page number covered by the chunk")
    section: str | None = Field(None, description="Section name")
    start_char: int | None = Field(None, description="Start character position")
    end_char: int | None = Field(None, description="End character position")
    source_mode: str | None = Field(None, description="Chunk source mode")
    element_types: list[str] | None = Field(
        None, description="Structured element types included in the chunk"
    )
    parser_version: str | None = Field(None, description="Parser version used to build the chunk")
    warning_codes: list[str] | None = Field(
        None, description="Warnings observed while parsing the source document"
    )


class DocumentChunk(BaseModel):
    """A single chunk from a document"""

    index: int = Field(..., description="Chunk index")
    content: str = Field(..., description="Chunk content")
    metadata: ChunkMetadata | dict = Field(default_factory=dict)


class DocumentPreviewResponse(BaseModel):
    """Response for document preview - R5.5"""

    chunks: list[DocumentChunk]
    total_chunks: int


# ========== Knowledge Search Schemas ==========


class KnowledgeSearchRequest(BaseModel):
    """Request schema for knowledge search (internal API)"""

    query: str = Field(..., description="Search query")
    top_k: int = Field(
        default=3, ge=1, le=20, description="Number of results to return"
    )
    similarity_threshold: float = Field(
        default=0.7, ge=0, le=1, description="Minimum similarity score"
    )


class SearchResultMetadata(BaseModel):
    """Metadata for a search result"""

    document_id: str
    document_title: str
    chunk_index: int


class SearchResult(BaseModel):
    """A single search result"""

    content: str = Field(..., description="Matched content")
    score: float = Field(..., description="Similarity score")
    metadata: SearchResultMetadata


class KnowledgeSearchResponse(BaseModel):
    """Response for knowledge search"""

    results: list[SearchResult]
    total: int = Field(default=0, description="Total result count")


# ========== API Response Wrappers ==========
# Following Result[T] pattern from common/error_handling/result.py


class KnowledgeBaseSuccessResponse(BaseModel):
    """Success response wrapper for KnowledgeBase operations"""

    success: bool = True
    data: (
        KnowledgeBaseResponse
        | KnowledgeBaseCreateResponse
        | KnowledgeBaseListResponse
        | None
    ) = None
    trace_id: str | None = None


class KnowledgeDocumentSuccessResponse(BaseModel):
    """Success response wrapper for KnowledgeDocument operations"""

    success: bool = True
    data: (
        KnowledgeDocumentResponse
        | KnowledgeDocumentUploadResponse
        | KnowledgeDocumentListResponse
        | DocumentPreviewResponse
        | None
    ) = None
    trace_id: str | None = None


class KnowledgeSearchSuccessResponse(BaseModel):
    """Success response wrapper for knowledge search"""

    success: bool = True
    data: KnowledgeSearchResponse | None = None
    trace_id: str | None = None


class KnowledgeErrorResponse(BaseModel):
    """Error response wrapper for knowledge operations"""

    success: bool = False
    error: str
    error_code: str
    trace_id: str | None = None

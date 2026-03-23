"""
Knowledge API - Admin endpoints for Knowledge Base management

Implements CRUD operations for KnowledgeBase and KnowledgeDocument.
Includes file upload, background processing, and preview.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 6 (Knowledge Service)
- API Contract: docs/api-contract/knowledge.md
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger
from common.storage.document import get_document_storage_service

from .models import DocumentStatus
from .processor import get_document_processor
from .schemas import (
    CreateKnowledgeBaseRequest,
    DocumentChunk,
    DocumentPreviewResponse,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUploadResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    SearchResult,
    SearchResultMetadata,
    UpdateKnowledgeBaseRequest,
)
from .service import KnowledgeService
from .vector_store import get_knowledge_vector_store

logger = get_logger(__name__)

admin_router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])

ALLOWED_FILE_TYPES = {"pdf", "docx", "txt", "md", "xlsx", "xls"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def _commit_or_error(
    db: AsyncSession, detail: str = "[DATABASE_COMMIT_FAILED]"
) -> JSONResponse | None:
    """Commit current transaction and return standardized 500 response on failure."""
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Knowledge API database commit failed: {e}")
        return build_server_error(
            detail,
            message="Database commit failed",
            exc=e,
        )
    return None


def _format_search_results(rows: list[dict[str, Any]]) -> list[SearchResult]:
    """Normalize vector search rows into API schema objects."""
    formatted_results: list[SearchResult] = []
    for row in rows:
        metadata = row.get("metadata", {})
        formatted_results.append(
            SearchResult(
                content=row.get("content", ""),
                score=row.get("score", 0.0),
                metadata=SearchResultMetadata(
                    document_id=metadata.get("document_id", ""),
                    document_title=metadata.get("document_title", ""),
                    chunk_index=metadata.get("chunk_index", 0),
                ),
            )
        )
    return formatted_results


def _search_failure_status_code(detail: str | None) -> int:
    normalized_detail = str(detail or "").strip()
    if "[KNOWLEDGE_BASE_NOT_FOUND]" in normalized_detail:
        return 404
    if "[KNOWLEDGE_SEARCH_UNAVAILABLE]" in normalized_detail:
        return 503
    return 400


async def process_document_background(
    doc_id: str,
    file_path: str,
    file_type: str,
    document_title: str,
    knowledge_base_id: str,
    vector_collection: str,
    db_url: str,
) -> None:
    """Background task to process uploaded document."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = None
    try:
        # Create new database session for background task
        engine = create_async_engine(db_url)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Update status to processing
            service = KnowledgeService(session)
            await service.update_document_status(
                doc_id=doc_id, status=DocumentStatus.PROCESSING.value
            )
            await session.commit()

            # Process document
            processor = get_document_processor()
            result = await processor.process_document(
                doc_id=doc_id,
                file_path=file_path,
                file_type=file_type,
                document_title=document_title,
                knowledge_base_id=knowledge_base_id,
                vector_collection=vector_collection,
            )

            # Update final status
            await service.update_document_status(
                doc_id=doc_id,
                status=result["status"],
                chunk_count=result["chunk_count"],
                error_message=result.get("error_message"),
            )
            await session.commit()

            logger.info(
                "Document processing completed",
                document_id=doc_id,
                status=result["status"],
                chunk_count=result.get("chunk_count", 0),
                phase_timings=result.get("phase_timings", {}),
                parse_metrics=result.get("parse_metrics", {}),
                parse_warnings=result.get("parse_warnings", []),
                artifact_path=result.get("artifact_path"),
            )

    except (RuntimeError, ValueError, OSError) as e:
        logger.error(f"Background document processing failed: {e}")
        # Try to mark document as failed
        if engine:
            try:
                async_session = sessionmaker(
                    engine, class_=AsyncSession, expire_on_commit=False
                )
                async with async_session() as session:
                    service = KnowledgeService(session)
                    await service.update_document_status(
                        doc_id=doc_id,
                        status=DocumentStatus.FAILED.value,
                        error_message=f"Processing error: {str(e)}",
                    )
                    await session.commit()
            except (RuntimeError, ValueError, OSError) as inner_e:
                logger.error(f"Failed to update document status after error: {inner_e}")

    finally:
        if engine:
            await engine.dispose()


@admin_router.post("", response_model=dict, status_code=201)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new KnowledgeBase - R5.1"""
    service = KnowledgeService(db)
    result = await service.create(request)

    if not result.is_success:
        raise HTTPException(status_code=400, detail=result.fallback)

    kb = result.value
    commit_error = await _commit_or_error(db)
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": KnowledgeBaseCreateResponse(
            id=kb.id,
            name=kb.name,
            category=kb.category,
            vector_collection=kb.vector_collection,
            document_count=kb.document_count,
            status=kb.status,
            created_at=kb.created_at,
        ).model_dump(),
    }


@admin_router.get("", response_model=dict)
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get paginated KnowledgeBase list - R5.2"""
    service = KnowledgeService(db)
    items, total = await service.list(page=page, page_size=page_size, category=category)

    return {
        "success": True,
        "data": KnowledgeBaseListResponse(
            knowledge_bases=items, total=total, page=page, page_size=page_size
        ).model_dump(),
    }


@admin_router.get("/{kb_id}", response_model=dict)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get KnowledgeBase details - R5.3"""
    service = KnowledgeService(db)
    result = await service.get_by_id(kb_id)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    kb = result.value
    return {
        "success": True,
        "data": KnowledgeBaseResponse.model_validate(kb).model_dump(),
    }


@admin_router.put("/{kb_id}", response_model=dict)
async def update_knowledge_base(
    kb_id: str,
    request: UpdateKnowledgeBaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update KnowledgeBase - R5.3"""
    service = KnowledgeService(db)
    result = await service.update(kb_id, request)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    kb = result.value
    commit_error = await _commit_or_error(db)
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": KnowledgeBaseResponse.model_validate(kb).model_dump(),
    }


@admin_router.delete("/{kb_id}", response_model=dict)
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete KnowledgeBase - R5.4"""
    service = KnowledgeService(db)

    # Get KB first to delete files
    kb_result = await service.get_by_id(kb_id)
    if kb_result.is_success:
        # Delete all document files
        storage = get_document_storage_service()
        await storage.delete_knowledge_base_documents(kb_id)

    result = await service.delete(kb_id)

    if not result.is_success:
        if "[KNOWLEDGE_BASE_IN_USE]" in (result.fallback or ""):
            raise HTTPException(status_code=400, detail=result.fallback)
        raise HTTPException(status_code=404, detail=result.fallback)

    commit_error = await _commit_or_error(db)
    if commit_error is not None:
        return commit_error
    return {"success": True, "data": {"deleted": True}}


# ========== Document Endpoints ==========


@admin_router.post("/{kb_id}/documents", response_model=dict, status_code=202)
async def upload_document(
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload a document to KnowledgeBase - R5.3"""
    import uuid

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="[INVALID_FILE]")

    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail="[UNSUPPORTED_FILE_TYPE]")

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="[FILE_TOO_LARGE]")

    if file_size == 0:
        raise HTTPException(status_code=400, detail="[EMPTY_FILE]")

    # Validate file content (basic magic bytes check)
    if not _validate_file_content(content, file_ext):
        raise HTTPException(status_code=400, detail="[INVALID_FILE_CONTENT]")

    # Check KB exists and get vector_collection
    service = KnowledgeService(db)
    kb_result = await service.get_by_id(kb_id)
    if not kb_result.is_success:
        raise HTTPException(status_code=404, detail="[KNOWLEDGE_BASE_NOT_FOUND]")

    kb = kb_result.value
    content_hash = hashlib.sha256(content).hexdigest()

    # Deduplicate by content hash in same KB.
    existing_doc = await service.get_document_by_content_hash(kb_id, content_hash)
    if existing_doc is not None:
        logger.info(
            "Skipped duplicate knowledge document upload",
            kb_id=kb_id,
            existing_doc_id=existing_doc.id,
            content_hash=content_hash,
        )
        return {
            "success": True,
            "data": KnowledgeDocumentUploadResponse(
                id=existing_doc.id,
                title=existing_doc.title,
                file_type=existing_doc.file_type,
                file_size=existing_doc.file_size,
                status=existing_doc.status,
                created_at=existing_doc.created_at,
            ).model_dump(),
        }

    # Generate document ID first
    doc_id = str(uuid.uuid4())

    # Save file to storage
    storage = get_document_storage_service()
    file_path = await storage.save_document(
        knowledge_base_id=kb_id,
        document_id=doc_id,
        file_data=content,
        file_type=file_ext,
    )

    if not file_path:
        return build_server_error(
            "[FILE_SAVE_FAILED]",
            message="Failed to save document file",
            kb_id=kb_id,
        )

    # Create document record with pre-generated ID
    doc_title = title or file.filename
    result = await service.create_document_with_id(
        doc_id=doc_id,
        kb_id=kb_id,
        title=doc_title,
        file_type=file_ext,
        file_url=file_path,
        file_size=file_size,
        content_hash=content_hash,
    )

    if not result.is_success:
        # Cleanup file on failure
        await storage.delete_document(kb_id, doc_id, file_ext)
        raise HTTPException(status_code=400, detail=result.fallback)

    doc = result.value
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        await storage.delete_document(kb_id, doc_id, file_ext)
        logger.error(
            f"Document upload commit failed, rolled back and cleaned file: {e}"
        )
        return build_server_error(
            "[DOCUMENT_SAVE_FAILED]",
            message="Failed to persist uploaded document",
            exc=e,
            kb_id=kb_id,
            doc_id=doc_id,
        )

    # Get database URL for background task
    from common.db.session import get_database_url

    db_url = get_database_url()

    # Schedule background processing
    background_tasks.add_task(
        process_document_background,
        doc_id=doc.id,
        file_path=file_path,
        file_type=file_ext,
        document_title=doc_title,
        knowledge_base_id=kb_id,
        vector_collection=kb.vector_collection,
        db_url=db_url,
    )

    return {
        "success": True,
        "data": KnowledgeDocumentUploadResponse(
            id=doc.id,
            title=doc.title,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            created_at=doc.created_at,
        ).model_dump(),
    }


def _validate_file_content(content: bytes, file_ext: str) -> bool:
    """Validate file content matches expected type (basic magic bytes check)."""
    if len(content) < 4:
        return False

    magic_bytes = {
        "pdf": b"%PDF",
        "docx": b"PK\x03\x04",  # ZIP format (DOCX is a ZIP)
        "xlsx": b"PK\x03\x04",  # ZIP format (XLSX is a ZIP)
        "xls": b"\xD0\xCF\x11\xE0",  # Compound File Binary Format
        # txt and md don't have magic bytes, accept any content
    }

    if file_ext in ("txt", "md"):
        # For text files, try to decode as UTF-8
        try:
            content[:1000].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    expected = magic_bytes.get(file_ext)
    if expected:
        return content[: len(expected)] == expected

    return True


@admin_router.get("/{kb_id}/documents", response_model=dict)
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get documents in a KnowledgeBase"""
    service = KnowledgeService(db)
    result = await service.list_documents(kb_id, page, page_size)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    items, total = result.value
    return {
        "success": True,
        "data": KnowledgeDocumentListResponse(
            documents=items, total=total, page=page, page_size=page_size
        ).model_dump(),
    }


@admin_router.get("/{kb_id}/documents/{doc_id}", response_model=dict)
async def get_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get document details"""
    service = KnowledgeService(db)
    result = await service.get_document(kb_id, doc_id)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    doc = result.value
    return {
        "success": True,
        "data": KnowledgeDocumentResponse.model_validate(doc).model_dump(),
    }


@admin_router.delete("/{kb_id}/documents/{doc_id}", response_model=dict)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete document"""
    service = KnowledgeService(db)

    # Get document first to delete file
    doc_result = await service.get_document(kb_id, doc_id)
    if doc_result.is_success:
        doc = doc_result.value
        storage = get_document_storage_service()
        await storage.delete_document(kb_id, doc_id, doc.file_type)

    result = await service.delete_document(kb_id, doc_id)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    commit_error = await _commit_or_error(db)
    if commit_error is not None:
        return commit_error
    return {"success": True, "data": {"deleted": True}}


@admin_router.get("/{kb_id}/documents/{doc_id}/preview", response_model=dict)
async def preview_document(
    kb_id: str,
    doc_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Preview document chunks - R5.5"""
    service = KnowledgeService(db)
    result = await service.get_document_chunks(kb_id, doc_id, page, page_size)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    chunks, total = result.value

    # Format chunks for response
    formatted_chunks = [
        DocumentChunk(
            index=c["index"], content=c["content"], metadata=c.get("metadata", {})
        )
        for c in chunks
    ]

    return {
        "success": True,
        "data": DocumentPreviewResponse(
            chunks=formatted_chunks, total_chunks=total
        ).model_dump(),
    }


# ========== Search Endpoint (Internal) ==========

internal_router = APIRouter(prefix="/internal/knowledge", tags=["internal-knowledge"])


@admin_router.post("/{kb_id}/search", response_model=dict)
async def search_knowledge_base_admin(
    kb_id: str,
    request: KnowledgeSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search knowledge base for admin tooling."""
    service = KnowledgeService(db)
    result = await service.search(
        kb_id=kb_id,
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )

    if not result.is_success:
        detail = result.fallback or "[KNOWLEDGE_SEARCH_UNAVAILABLE]"
        raise HTTPException(
            status_code=_search_failure_status_code(detail),
            detail=detail,
        )

    search_results = _format_search_results(result.value or [])
    payload = KnowledgeSearchResponse(
        results=search_results,
        total=len(search_results),
    ).model_dump()

    return {
        "success": True,
        "data": payload,
    }


@internal_router.post("/{kb_id}/search", response_model=dict)
async def search_knowledge_base_internal(
    kb_id: str,
    request: KnowledgeSearchRequest,
    current_user: User = Depends(get_current_user),  # Add authentication
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search knowledge base - Internal API (requires authentication)"""
    service = KnowledgeService(db)
    result = await service.search(
        kb_id=kb_id,
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )

    if not result.is_success:
        detail = result.fallback or "[KNOWLEDGE_SEARCH_UNAVAILABLE]"
        raise HTTPException(
            status_code=_search_failure_status_code(detail),
            detail=detail,
        )

    search_results = _format_search_results(result.value or [])
    payload = KnowledgeSearchResponse(
        results=search_results,
        total=len(search_results),
    ).model_dump()

    return {"success": True, "data": payload}


# ========== Document Reprocessing ==========


@admin_router.post(
    "/{kb_id}/documents/{doc_id}/reprocess", response_model=dict, status_code=202
)
async def reprocess_document(
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reprocess a failed or pending document"""
    service = KnowledgeService(db)

    # Get document
    doc_result = await service.get_document(kb_id, doc_id)
    if not doc_result.is_success:
        raise HTTPException(status_code=404, detail=doc_result.fallback)

    doc = doc_result.value

    # Only allow reprocessing of failed or pending documents
    if doc.status not in (DocumentStatus.FAILED.value, DocumentStatus.PENDING.value):
        raise HTTPException(
            status_code=400,
            detail=f"[INVALID_STATUS] Cannot reprocess document with status: {doc.status}",
        )

    # Get KB for vector collection
    kb_result = await service.get_by_id(kb_id)
    if not kb_result.is_success:
        raise HTTPException(status_code=404, detail="[KNOWLEDGE_BASE_NOT_FOUND]")

    kb = kb_result.value

    # Delete existing vectors if any
    vector_store = get_knowledge_vector_store()
    await vector_store.delete_document_chunks(kb.vector_collection, doc_id)

    storage = get_document_storage_service()
    storage.delete_parse_artifact(doc.file_url)

    # Reset status
    await service.update_document_status(
        doc_id=doc_id,
        status=DocumentStatus.PENDING.value,
        chunk_count=0,
        error_message=None,
    )
    commit_error = await _commit_or_error(db)
    if commit_error is not None:
        return commit_error

    # Get database URL for background task
    from common.db.session import get_database_url

    db_url = get_database_url()

    # Schedule background processing
    background_tasks.add_task(
        process_document_background,
        doc_id=doc.id,
        file_path=doc.file_url,
        file_type=doc.file_type,
        document_title=doc.title,
        knowledge_base_id=kb_id,
        vector_collection=kb.vector_collection,
        db_url=db_url,
    )

    return {
        "success": True,
        "data": {"message": "Document reprocessing started", "document_id": doc_id},
    }

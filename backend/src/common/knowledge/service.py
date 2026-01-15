"""
Knowledge Service - Business logic for Knowledge Base management

Implements CRUD operations for KnowledgeBase and KnowledgeDocument.
Includes vector search, reference checking, and cleanup.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 6, 27 (Knowledge Service)
- API Contract: docs/api-contract/knowledge.md
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.embedding_service import get_embedding_service
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

from .models import (
    DocumentStatus,
    KnowledgeBase,
    KnowledgeBaseStatus,
    KnowledgeDocument,
)
from .schemas import (
    CreateKnowledgeBaseRequest,
    KnowledgeBaseListItem,
    KnowledgeDocumentListItem,
    UpdateKnowledgeBaseRequest,
)
from .vector_store import get_knowledge_vector_store

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class KnowledgeService:
    """Knowledge Base management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== KnowledgeBase CRUD ==========

    async def create(
        self,
        data: CreateKnowledgeBaseRequest
    ) -> Result[KnowledgeBase]:
        """Create a new KnowledgeBase - R5.1"""
        try:
            kb_id = str(uuid.uuid4())
            vector_collection = f"kb_{kb_id.replace('-', '_')}"

            kb = KnowledgeBase(
                id=kb_id,
                name=data.name,
                description=data.description,
                category=data.category,
                vector_collection=vector_collection,
                embedding_model="text-embedding-3-small",
                document_count=0,
                total_chunks=0,
                status=KnowledgeBaseStatus.ACTIVE.value,
            )

            self.db.add(kb)
            await self.db.flush()
            await self.db.refresh(kb)

            logger.info(f"Created KnowledgeBase: {kb.id} - {kb.name}")
            return Result.ok(kb)

        except Exception as e:
            logger.error(f"Failed to create KnowledgeBase: {e}")
            return Result.fail(f"[KNOWLEDGE_BASE_CREATE_FAILED] {str(e)}")

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        status: str | None = None
    ) -> tuple[list[KnowledgeBaseListItem], int]:
        """Get paginated KnowledgeBase list - R5.2"""
        # 参数边界校验
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        stmt = select(KnowledgeBase)

        if category:
            stmt = stmt.where(KnowledgeBase.category == category)
        if status:
            stmt = stmt.where(KnowledgeBase.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(KnowledgeBase.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        kbs = result.scalars().all()

        items = [
            KnowledgeBaseListItem(
                id=kb.id,
                name=kb.name,
                description=kb.description,
                category=kb.category,
                document_count=kb.document_count,
                total_chunks=kb.total_chunks,
                status=kb.status,
                updated_at=kb.updated_at
            )
            for kb in kbs
        ]

        return items, total

    async def get_by_id(self, kb_id: str) -> Result[KnowledgeBase]:
        """Get KnowledgeBase by ID - R5.3"""
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        result = await self.db.execute(stmt)
        kb = result.scalar_one_or_none()

        if not kb:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        return Result.ok(kb)

    async def update(
        self,
        kb_id: str,
        data: UpdateKnowledgeBaseRequest
    ) -> Result[KnowledgeBase]:
        """Update KnowledgeBase - R5.3"""
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        result = await self.db.execute(stmt)
        kb = result.scalar_one_or_none()

        if not kb:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(kb, field, value)

        kb.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(kb)

        logger.info(f"Updated KnowledgeBase: {kb.id}")
        return Result.ok(kb)

    async def delete(self, kb_id: str) -> Result[bool]:
        """Delete KnowledgeBase - R5.4"""
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        result = await self.db.execute(stmt)
        kb = result.scalar_one_or_none()

        if not kb:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        # Check if referenced by Agent/Persona
        ref_check = await self._check_references(kb_id)
        if ref_check:
            return Result.fail(f"[KNOWLEDGE_BASE_IN_USE] {ref_check}")

        # Delete vector collection
        vector_store = get_knowledge_vector_store()
        await vector_store.delete_collection(kb.vector_collection)

        # Delete from database (cascades to documents)
        await self.db.delete(kb)
        await self.db.flush()

        logger.info(f"Deleted KnowledgeBase: {kb_id}")
        return Result.ok(True)

    async def _check_references(self, kb_id: str) -> str | None:
        """
        Check if knowledge base is referenced by any Agent or Persona.

        Returns:
            Error message if referenced, None if safe to delete
        """
        try:
            # Import here to avoid circular imports
            from agent.models import Agent, Persona

            # Check Agents - use text search for JSON compatibility across databases
            # This works for both SQLite and PostgreSQL
            agent_stmt = select(Agent)
            agent_result = await self.db.execute(agent_stmt)
            agents = agent_result.scalars().all()

            # Filter in Python for JSON array contains (database-agnostic)
            referencing_agents = [
                a for a in agents
                if a.default_knowledge_base_ids and kb_id in a.default_knowledge_base_ids
            ]

            if referencing_agents:
                names = ", ".join(a.name for a in referencing_agents[:3])
                return f"Referenced by Agents: {names}"

            # Check Personas
            persona_stmt = select(Persona)
            persona_result = await self.db.execute(persona_stmt)
            personas = persona_result.scalars().all()

            referencing_personas = [
                p for p in personas
                if p.knowledge_base_ids and kb_id in p.knowledge_base_ids
            ]

            if referencing_personas:
                names = ", ".join(p.name for p in referencing_personas[:3])
                return f"Referenced by Personas: {names}"

            return None

        except Exception as e:
            logger.warning(f"Reference check failed (continuing): {e}")
            return None

    # ========== Document Operations ==========

    async def create_document(
        self,
        kb_id: str,
        title: str,
        file_type: str,
        file_url: str,
        file_size: int
    ) -> Result[KnowledgeDocument]:
        """Create a document record (called after file upload) - R5.3"""
        doc_id = str(uuid.uuid4())
        return await self.create_document_with_id(
            doc_id=doc_id,
            kb_id=kb_id,
            title=title,
            file_type=file_type,
            file_url=file_url,
            file_size=file_size
        )

    async def create_document_with_id(
        self,
        doc_id: str,
        kb_id: str,
        title: str,
        file_type: str,
        file_url: str,
        file_size: int
    ) -> Result[KnowledgeDocument]:
        """Create a document record with pre-generated ID - R5.3"""
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        try:
            doc = KnowledgeDocument(
                id=doc_id,
                knowledge_base_id=kb_id,
                title=title,
                file_type=file_type,
                file_url=file_url,
                file_size=file_size,
                status=DocumentStatus.PENDING.value,
                chunk_count=0,
            )

            self.db.add(doc)

            # Update document count
            kb = kb_result.value
            kb.document_count += 1

            await self.db.flush()
            await self.db.refresh(doc)

            logger.info(f"Created document: {doc.id} in KB {kb_id}")
            return Result.ok(doc)

        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            return Result.fail(f"[DOCUMENT_CREATE_FAILED] {str(e)}")

    async def list_documents(
        self,
        kb_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Result[tuple[list[KnowledgeDocumentListItem], int]]:
        """Get documents in a KnowledgeBase"""
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        # 参数边界校验
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_base_id == kb_id
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(KnowledgeDocument.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        docs = result.scalars().all()

        items = [
            KnowledgeDocumentListItem(
                id=doc.id,
                title=doc.title,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=doc.status,
                chunk_count=doc.chunk_count,
                created_at=doc.created_at
            )
            for doc in docs
        ]

        return Result.ok((items, total))

    async def get_document(
        self,
        kb_id: str,
        doc_id: str
    ) -> Result[KnowledgeDocument]:
        """Get document by ID"""
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.knowledge_base_id == kb_id
        )
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        return Result.ok(doc)

    async def delete_document(
        self,
        kb_id: str,
        doc_id: str
    ) -> Result[bool]:
        """Delete document and its vectors"""
        doc_result = await self.get_document(kb_id, doc_id)
        if not doc_result.is_success:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        doc = doc_result.value

        # Get KB for vector collection name
        kb_result = await self.get_by_id(kb_id)
        if kb_result.is_success:
            kb = kb_result.value

            # Delete vectors
            vector_store = get_knowledge_vector_store()
            await vector_store.delete_document_chunks(
                collection_name=kb.vector_collection,
                document_id=doc_id
            )

            # Update KB stats
            kb.document_count = max(0, kb.document_count - 1)
            kb.total_chunks = max(0, kb.total_chunks - doc.chunk_count)

        await self.db.delete(doc)
        await self.db.flush()

        logger.info(f"Deleted document: {doc_id}")
        return Result.ok(True)

    async def update_document_status(
        self,
        doc_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: str | None = None
    ) -> Result[KnowledgeDocument]:
        """Update document processing status (called by processor)"""
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        old_chunk_count = doc.chunk_count
        doc.status = status
        doc.chunk_count = chunk_count
        doc.error_message = error_message

        # Update KB total_chunks
        if status == DocumentStatus.READY.value:
            kb_result = await self.get_by_id(doc.knowledge_base_id)
            if kb_result.is_success:
                kb = kb_result.value
                # Adjust for any previous chunks
                kb.total_chunks = kb.total_chunks - old_chunk_count + chunk_count

        await self.db.flush()
        await self.db.refresh(doc)

        return Result.ok(doc)

    # ========== Vector Search ==========

    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.7
    ) -> Result[list[dict[str, Any]]]:
        """
        Search knowledge base using vector similarity.

        Args:
            kb_id: Knowledge base ID
            query: Search query text
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            Result with list of search results
        """
        # Get KB
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        kb = kb_result.value

        # Generate query embedding
        embedding_service = get_embedding_service()
        if not embedding_service.is_configured:
            logger.warning("Embedding service not configured")
            return Result.ok([])

        embed_result = await embedding_service.embed(query)
        if not embed_result.is_success:
            logger.error(f"Failed to embed query: {embed_result.error}")
            return Result.ok([])  # Graceful degradation

        # Search vector store
        vector_store = get_knowledge_vector_store()
        search_result = await vector_store.search(
            collection_name=kb.vector_collection,
            query_embedding=embed_result.value,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        if not search_result.is_success:
            return Result.ok([])

        logger.info(
            f"Search in KB {kb_id}: query='{query[:50]}...', results={len(search_result.value)}"
        )
        return Result.ok(search_result.value)

    async def search_multiple(
        self,
        kb_ids: list[str],
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.7
    ) -> Result[list[dict[str, Any]]]:
        """
        Search multiple knowledge bases.

        Args:
            kb_ids: List of knowledge base IDs
            query: Search query text
            top_k: Number of results per KB
            similarity_threshold: Minimum similarity score

        Returns:
            Result with merged and sorted results
        """
        if not kb_ids:
            return Result.ok([])

        # Generate query embedding once
        embedding_service = get_embedding_service()
        if not embedding_service.is_configured:
            return Result.ok([])

        embed_result = await embedding_service.embed(query)
        if not embed_result.is_success:
            return Result.ok([])

        query_embedding = embed_result.value
        all_results: list[dict[str, Any]] = []

        # Search each KB
        vector_store = get_knowledge_vector_store()
        for kb_id in kb_ids:
            kb_result = await self.get_by_id(kb_id)
            if not kb_result.is_success:
                continue

            kb = kb_result.value
            search_result = await vector_store.search(
                collection_name=kb.vector_collection,
                query_embedding=query_embedding,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

            if search_result.is_success:
                # Add KB info to results
                for r in search_result.value:
                    r["knowledge_base_id"] = kb_id
                    r["knowledge_base_name"] = kb.name
                all_results.extend(search_result.value)

        # Sort by score and take top_k
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return Result.ok(all_results[:top_k])

    # ========== Document Preview ==========

    async def get_document_chunks(
        self,
        kb_id: str,
        doc_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Result[tuple[list[dict[str, Any]], int]]:
        """
        Get document chunks for preview.

        Returns chunks stored in vector database.
        """
        doc_result = await self.get_document(kb_id, doc_id)
        if not doc_result.is_success:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        _doc = doc_result.value  # Validate document exists
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        kb = kb_result.value

        # Get chunks from vector store
        vector_store = get_knowledge_vector_store()
        collection = vector_store._get_collection(kb.vector_collection)

        if not collection:
            return Result.ok(([], 0))

        try:
            # Get all chunks for this document
            results = collection.get(
                where={"document_id": doc_id},
                include=["documents", "metadatas"]
            )

            if not results or not results["documents"]:
                return Result.ok(([], 0))

            # Format chunks
            chunks = []
            for i, doc_content in enumerate(results["documents"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                chunks.append({
                    "index": metadata.get("chunk_index", i),
                    "content": doc_content,
                    "metadata": {
                        "start_char": metadata.get("start_char"),
                        "end_char": metadata.get("end_char"),
                    }
                })

            # Sort by index
            chunks.sort(key=lambda x: x["index"])
            total = len(chunks)

            # Paginate
            start = (page - 1) * page_size
            end = start + page_size
            paginated = chunks[start:end]

            return Result.ok((paginated, total))

        except Exception as e:
            logger.error(f"Failed to get document chunks: {e}")
            return Result.ok(([], 0))

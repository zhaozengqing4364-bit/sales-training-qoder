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

import re
import uuid
from datetime import datetime, timezone
from hashlib import md5
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
from .processor import get_document_processor
from .vector_store import get_knowledge_vector_store

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


QUERY_EXPANSION_MAP: dict[str, list[str]] = {
    "价格": ["报价", "费用", "收费", "多少钱"],
    "实习": ["试用", "体验", "演练"],
    "实训": ["演练", "培训", "模拟"],
    "产品": ["方案", "服务", "功能"],
    "名录": ["清单", "列表", "目录"],
    "型号": ["版本", "规格", "配置"],
    "参数": ["规格", "配置", "能力"],
    "部署": ["上线", "实施", "落地"],
    "合同": ["协议", "签约"],
}

QUERY_STOPWORDS: set[str] = {
    "我们",
    "我们的",
    "公司",
    "这个",
    "那个",
    "请问",
    "一下",
    "一下子",
    "介绍",
    "说明",
    "什么",
    "哪些",
    "有哪些",
    "如何",
    "怎么",
    "吗",
    "呢",
    "呀",
    "和",
    "及",
    "与",
}

VERSION_TOKEN_RE = re.compile(r"\bv?\d+(?:\.\d+){0,2}[a-z]?\b", re.IGNORECASE)


class KnowledgeService:
    """Knowledge Base management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_search_health(self, kb_ids: list[str]) -> dict[str, int]:
        normalized_ids = [str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()]
        if not normalized_ids:
            return {
                "knowledge_base_count": 0,
                "ready_document_count": 0,
                "ready_chunk_count": 0,
                "vector_chunk_count": 0,
                "is_ready": False,
            }

        stmt = (
            select(
                func.count(KnowledgeDocument.id),
                func.coalesce(func.sum(KnowledgeDocument.chunk_count), 0),
            )
            .where(KnowledgeDocument.knowledge_base_id.in_(normalized_ids))
            .where(KnowledgeDocument.status == DocumentStatus.READY.value)
            .where(KnowledgeDocument.chunk_count > 0)
        )
        ready_doc_count, ready_chunk_count = (await self.db.execute(stmt)).one()

        vector_chunk_count = 0
        kb_stmt = select(KnowledgeBase.id, KnowledgeBase.vector_collection).where(
            KnowledgeBase.id.in_(normalized_ids)
        )
        kb_rows = (await self.db.execute(kb_stmt)).all()
        vector_store = get_knowledge_vector_store()
        for _, vector_collection in kb_rows:
            if not vector_collection:
                continue
            stats = await vector_store.get_collection_stats(str(vector_collection))
            if not isinstance(stats, dict):
                continue
            try:
                vector_chunk_count += max(0, int(stats.get("count") or 0))
            except (TypeError, ValueError):
                continue

        ready_document_count = int(ready_doc_count or 0)
        ready_chunk_count_value = int(ready_chunk_count or 0)
        is_ready = (
            ready_document_count > 0
            and ready_chunk_count_value > 0
            and vector_chunk_count > 0
        )

        return {
            "knowledge_base_count": len(normalized_ids),
            "ready_document_count": ready_document_count,
            "ready_chunk_count": ready_chunk_count_value,
            "vector_chunk_count": vector_chunk_count,
            "is_ready": is_ready,
        }

    async def _get_ready_document_ids_by_kb(
        self,
        kb_ids: list[str],
    ) -> dict[str, list[str]]:
        normalized_ids = [str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()]
        if not normalized_ids:
            return {}

        stmt = (
            select(KnowledgeDocument.knowledge_base_id, KnowledgeDocument.id)
            .where(KnowledgeDocument.knowledge_base_id.in_(normalized_ids))
            .where(KnowledgeDocument.status == DocumentStatus.READY.value)
            .where(KnowledgeDocument.chunk_count > 0)
        )
        rows = (await self.db.execute(stmt)).all()

        ready_docs: dict[str, list[str]] = {}
        for kb_id, doc_id in rows:
            ready_docs.setdefault(str(kb_id), []).append(str(doc_id))
        return ready_docs

    # ========== KnowledgeBase CRUD ==========

    async def create(self, data: CreateKnowledgeBaseRequest) -> Result[KnowledgeBase]:
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

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Failed to create KnowledgeBase: {e}")
            return Result.fail(f"[KNOWLEDGE_BASE_CREATE_FAILED] {str(e)}")

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        status: str | None = None,
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
                updated_at=kb.updated_at,
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
        self, kb_id: str, data: UpdateKnowledgeBaseRequest
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

        kb.updated_at = datetime.now(timezone.utc)

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
                a
                for a in agents
                if a.default_knowledge_base_ids
                and kb_id in a.default_knowledge_base_ids
            ]

            if referencing_agents:
                names = ", ".join(a.name for a in referencing_agents[:3])
                return f"Referenced by Agents: {names}"

            # Check Personas
            persona_stmt = select(Persona)
            persona_result = await self.db.execute(persona_stmt)
            personas = persona_result.scalars().all()

            referencing_personas = [
                p
                for p in personas
                if p.knowledge_base_ids and kb_id in p.knowledge_base_ids
            ]

            if referencing_personas:
                names = ", ".join(p.name for p in referencing_personas[:3])
                return f"Referenced by Personas: {names}"

            return None

        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Reference check failed (continuing): {e}")
            return None

    # ========== Document Operations ==========

    async def create_document(
        self, kb_id: str, title: str, file_type: str, file_url: str, file_size: int
    ) -> Result[KnowledgeDocument]:
        """Create a document record (called after file upload) - R5.3"""
        doc_id = str(uuid.uuid4())
        return await self.create_document_with_id(
            doc_id=doc_id,
            kb_id=kb_id,
            title=title,
            file_type=file_type,
            file_url=file_url,
            file_size=file_size,
        )

    async def create_document_with_id(
        self,
        doc_id: str,
        kb_id: str,
        title: str,
        file_type: str,
        file_url: str,
        file_size: int,
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

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Failed to create document: {e}")
            return Result.fail(f"[DOCUMENT_CREATE_FAILED] {str(e)}")

    async def list_documents(
        self, kb_id: str, page: int = 1, page_size: int = 20
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
                created_at=doc.created_at,
            )
            for doc in docs
        ]

        return Result.ok((items, total))

    async def get_document(self, kb_id: str, doc_id: str) -> Result[KnowledgeDocument]:
        """Get document by ID"""
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id, KnowledgeDocument.knowledge_base_id == kb_id
        )
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        return Result.ok(doc)

    async def delete_document(self, kb_id: str, doc_id: str) -> Result[bool]:
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
                collection_name=kb.vector_collection, document_id=doc_id
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
        error_message: str | None = None,
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
        similarity_threshold: float = 0.7,
        metadata_filter: dict[str, Any] | None = None,
        enable_hybrid: bool = True,
        keyword_candidate_limit: int = 32,
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
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        return await self.search_multiple(
            kb_ids=[kb_id],
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            metadata_filter=metadata_filter,
            enable_hybrid=enable_hybrid,
            keyword_candidate_limit=keyword_candidate_limit,
        )

    async def search_multiple(
        self,
        kb_ids: list[str],
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.7,
        metadata_filter: dict[str, Any] | None = None,
        enable_hybrid: bool = True,
        keyword_candidate_limit: int = 32,
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
        normalized_kb_ids = [
            str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()
        ]
        if not normalized_kb_ids:
            return Result.ok([])

        ready_document_ids_by_kb = await self._get_ready_document_ids_by_kb(
            normalized_kb_ids
        )
        searchable_kb_ids = [
            kb_id for kb_id in normalized_kb_ids if ready_document_ids_by_kb.get(kb_id)
        ]
        if not searchable_kb_ids:
            logger.warning(
                "No searchable ready documents in bound knowledge bases",
                knowledge_base_ids=normalized_kb_ids,
            )
            return Result.ok([])

        query_variants = self._build_query_variants(query)

        embedding_service = get_embedding_service()
        vector_results: list[dict[str, Any]] = []
        embedding_failure: str | None = None
        query_embeddings: list[tuple[str, list[float]]] = []

        kb_contexts: dict[str, Any] = {}
        for kb_id in searchable_kb_ids:
            kb_result = await self.get_by_id(kb_id)
            if not kb_result.is_success:
                continue
            kb_contexts[kb_id] = kb_result.value

        if not kb_contexts:
            return Result.ok([])

        if embedding_service.is_configured:
            for variant in query_variants:
                embed_result = await embedding_service.embed(variant)
                if embed_result.is_success and embed_result.value:
                    query_embeddings.append((variant, embed_result.value))
                    continue

                if embedding_failure is None:
                    embedding_failure = embed_result.fallback or "[EMBEDDING_FAILED]"

            if query_embeddings:
                vector_store = get_knowledge_vector_store()
                vector_top_k = max(6, top_k * 2)

                for kb_id, kb in kb_contexts.items():
                    ready_document_ids = ready_document_ids_by_kb.get(kb_id, [])
                    if not ready_document_ids:
                        continue

                    for variant, query_embedding in query_embeddings:
                        adaptive_threshold = self._adapt_similarity_threshold(
                            query=variant,
                            base_threshold=similarity_threshold,
                        )
                        search_result = await vector_store.search(
                            collection_name=kb.vector_collection,
                            query_embedding=query_embedding,
                            top_k=vector_top_k,
                            similarity_threshold=adaptive_threshold,
                            document_ids=ready_document_ids,
                            metadata_filter=metadata_filter,
                        )

                        if not search_result.is_success:
                            continue

                        for row in search_result.value:
                            row["knowledge_base_id"] = kb_id
                            row["knowledge_base_name"] = kb.name
                            row.setdefault("matched_query", variant)
                        vector_results.extend(search_result.value)
            elif embedding_failure:
                logger.warning(
                    "Embedding failed for multi-knowledge search, fallback to keyword matching",
                    reason=embedding_failure,
                )
        else:
            embedding_failure = "[EMBEDDING_NOT_CONFIGURED]"
            logger.warning(
                "Embedding service not configured, fallback to keyword matching"
            )

        keyword_results = await self._search_multiple_by_keywords(
            kb_ids=list(kb_contexts.keys()),
            query=query,
            top_k=max(6, top_k * 2),
            metadata_filter=metadata_filter,
            candidate_limit=max(8, min(128, int(keyword_candidate_limit))),
            query_variants=query_variants,
            ready_document_ids_by_kb=ready_document_ids_by_kb,
        )

        if enable_hybrid:
            fused_results = self._fuse_retrieval_results(
                vector_results=vector_results,
                keyword_results=keyword_results,
                top_k=top_k,
            )
            if fused_results:
                return Result.ok(fused_results)
        elif vector_results:
            deduped_rows: dict[str, dict[str, Any]] = {}
            for row in vector_results:
                key = self._build_result_key(row)
                existing = deduped_rows.get(key)
                if existing is None or float(row.get("score") or 0) > float(
                    existing.get("score") or 0
                ):
                    deduped_rows[key] = row
            sorted_rows = sorted(
                deduped_rows.values(),
                key=lambda item: float(item.get("score") or 0),
                reverse=True,
            )
            return Result.ok(sorted_rows[: max(1, top_k)])

        if keyword_results:
            return Result.ok(keyword_results[: max(1, top_k)])

        if embedding_failure:
            return Result.fail(f"[KNOWLEDGE_SEARCH_UNAVAILABLE] {embedding_failure}")

        return Result.ok([])

    @staticmethod
    def _build_keyword_candidates(query: str, candidate_limit: int = 32) -> list[str]:
        """Build coarse keywords for fallback retrieval without embeddings."""
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        expansion_terms = KnowledgeService._expand_query_terms(normalized_query)

        candidates: list[str] = []
        seen: set[str] = set()

        def add_candidate(token: str) -> None:
            value = token.strip().lower()
            if not value or value in seen:
                return
            if len(value) < 2:
                return
            seen.add(value)
            candidates.append(value)

        add_candidate(normalized_query)
        for term in expansion_terms:
            if len(candidates) >= candidate_limit:
                break
            add_candidate(term)

        compact_query = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", normalized_query))
        add_candidate(compact_query)

        for fragment in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized_query):
            if len(candidates) >= candidate_limit:
                break
            if re.fullmatch(r"[\u4e00-\u9fff]+", fragment):
                add_candidate(fragment)
                if len(fragment) >= 4:
                    for ngram_size in (4, 3, 2):
                        if len(candidates) >= candidate_limit:
                            break
                        if len(fragment) < ngram_size:
                            continue
                        for index in range(0, len(fragment) - ngram_size + 1):
                            add_candidate(fragment[index : index + ngram_size])
                            if len(candidates) >= candidate_limit:
                                break
            elif len(fragment) >= 2:
                add_candidate(fragment)

        return candidates[:candidate_limit]

    @staticmethod
    def _expand_query_terms(normalized_query: str) -> list[str]:
        """Expand query with lightweight Chinese synonyms for recall gain."""
        terms: list[str] = []
        seen: set[str] = set()

        def add_term(value: str) -> None:
            token = value.strip().lower()
            if not token or token in seen:
                return
            seen.add(token)
            terms.append(token)

        add_term(normalized_query)
        fragments = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized_query)
        for fragment in fragments:
            add_term(fragment)
            expansions = QUERY_EXPANSION_MAP.get(fragment)
            if expansions:
                for expanded in expansions:
                    add_term(expanded)

        for seed, expansions in QUERY_EXPANSION_MAP.items():
            if seed in normalized_query:
                for expanded in expansions:
                    add_term(expanded)
            for expanded in expansions:
                if expanded in normalized_query:
                    add_term(seed)

        return terms[:24]

    @staticmethod
    def _build_query_variants(query: str, max_variants: int = 3) -> list[str]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        variants: list[str] = []
        seen: set[str] = set()

        def add_variant(value: str) -> None:
            token = value.strip().lower()
            if not token or token in seen:
                return
            seen.add(token)
            variants.append(token)

        add_variant(normalized_query)

        fragments = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized_query)
        core_fragments = [
            fragment
            for fragment in fragments
            if fragment not in QUERY_STOPWORDS and len(fragment) >= 2
        ]
        compact_core = "".join(core_fragments)
        if compact_core:
            add_variant(compact_core)

        for token in core_fragments:
            if len(token) >= 3:
                add_variant(token)

        for version_token in VERSION_TOKEN_RE.findall(normalized_query):
            add_variant(version_token)

        for term in KnowledgeService._expand_query_terms(normalized_query):
            add_variant(term)
            if len(variants) >= max_variants * 2:
                break

        return variants[: max(1, max_variants)]

    @staticmethod
    def _adapt_similarity_threshold(query: str, base_threshold: float) -> float:
        compact_query = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", query.lower()))
        threshold = max(0.0, min(1.0, float(base_threshold)))

        if len(compact_query) <= 12 or VERSION_TOKEN_RE.search(compact_query):
            return max(0.45, round(threshold - 0.08, 4))
        if len(compact_query) >= 30:
            return max(0.5, round(threshold - 0.05, 4))
        return threshold

    @staticmethod
    def _build_result_key(row: dict[str, Any]) -> str:
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        kb_id = str(row.get("knowledge_base_id") or "")
        document_id = str(metadata.get("document_id") or "")
        chunk_index = metadata.get("chunk_index")
        if kb_id and document_id and chunk_index is not None:
            return f"{kb_id}:{document_id}:{chunk_index}"

        content = str(row.get("content") or "")
        digest = (
            md5(content.encode("utf-8"), usedforsecurity=False).hexdigest()
            if content
            else ""
        )
        return f"{kb_id}:{document_id}:{digest}"

    @staticmethod
    def _metadata_matches(
        metadata: dict[str, Any],
        metadata_filter: dict[str, Any] | None,
    ) -> bool:
        if not metadata_filter:
            return True

        for key, expected in metadata_filter.items():
            actual = metadata.get(key)
            if isinstance(expected, list):
                normalized_expected = {str(item).strip().lower() for item in expected}
                if str(actual).strip().lower() not in normalized_expected:
                    return False
            elif str(actual).strip().lower() != str(expected).strip().lower():
                return False
        return True

    @staticmethod
    def _fuse_retrieval_results(
        *,
        vector_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not vector_results and not keyword_results:
            return []

        combined: dict[str, dict[str, Any]] = {}

        for row in keyword_results:
            key = KnowledgeService._build_result_key(row)
            base = dict(row)
            keyword_score = max(0.0, min(1.0, float(base.get("score") or 0.0)))
            base["_vector_score"] = 0.0
            base["_keyword_score"] = keyword_score
            combined[key] = base

        for row in vector_results:
            key = KnowledgeService._build_result_key(row)
            vector_score = max(0.0, min(1.0, float(row.get("score") or 0.0)))
            existing = combined.get(key)
            if existing is None:
                base = dict(row)
                base["_vector_score"] = vector_score
                base["_keyword_score"] = 0.0
                combined[key] = base
                continue

            if not existing.get("content") and row.get("content"):
                existing["content"] = row.get("content")
            if not existing.get("source") and row.get("source"):
                existing["source"] = row.get("source")
            if not existing.get("metadata") and row.get("metadata"):
                existing["metadata"] = row.get("metadata")
            if not existing.get("knowledge_base_name") and row.get(
                "knowledge_base_name"
            ):
                existing["knowledge_base_name"] = row.get("knowledge_base_name")
            existing["_vector_score"] = max(
                existing.get("_vector_score", 0.0), vector_score
            )

        fused_rows: list[dict[str, Any]] = []
        for item in combined.values():
            vector_score = float(item.pop("_vector_score", 0.0) or 0.0)
            keyword_score = float(item.pop("_keyword_score", 0.0) or 0.0)
            has_vector = vector_score > 0
            has_keyword = keyword_score > 0

            if has_vector and has_keyword:
                fused = min(0.99, vector_score * 0.72 + keyword_score * 0.28 + 0.03)
                retrieval_mode = "hybrid"
            elif has_vector:
                fused = vector_score
                retrieval_mode = "vector"
            else:
                fused = keyword_score
                retrieval_mode = "keyword_fallback"

            item["score"] = round(fused, 4)
            item["retrieval_mode"] = retrieval_mode
            fused_rows.append(item)

        fused_rows.sort(key=lambda row: float(row.get("score") or 0), reverse=True)
        return fused_rows[: max(1, top_k)]

    @staticmethod
    def _keyword_match_score(
        normalized_content: str,
        normalized_query: str,
        candidates: list[str],
    ) -> float:
        """Score keyword overlap for fallback search."""
        if not normalized_content:
            return 0.0

        score = 0.0
        if normalized_query and normalized_query in normalized_content:
            score += 3.0

        matched_count = 0
        for candidate in candidates:
            if candidate and candidate in normalized_content:
                matched_count += 1
                if len(candidate) >= 6:
                    score += 1.4
                elif len(candidate) >= 4:
                    score += 1.1
                else:
                    score += 0.8

        if matched_count <= 0:
            return 0.0

        coverage = matched_count / max(1, len(candidates))
        return score + coverage

    async def _search_multiple_by_keywords(
        self,
        kb_ids: list[str],
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
        candidate_limit: int = 32,
        query_variants: list[str] | None = None,
        ready_document_ids_by_kb: dict[str, list[str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Fallback retrieval strategy that matches chunk text by keywords."""
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        variants = [variant for variant in (query_variants or []) if variant.strip()]
        if not variants:
            variants = self._build_query_variants(normalized_query)

        merged_candidates: list[str] = []
        seen_candidates: set[str] = set()

        for variant in variants:
            for candidate in self._build_keyword_candidates(
                variant,
                candidate_limit=max(8, int(candidate_limit or 32)),
            ):
                if candidate in seen_candidates:
                    continue
                seen_candidates.add(candidate)
                merged_candidates.append(candidate)
                if len(merged_candidates) >= max(8, int(candidate_limit or 32)):
                    break
            if len(merged_candidates) >= max(8, int(candidate_limit or 32)):
                break

        if not merged_candidates:
            return []

        vector_store = get_knowledge_vector_store()
        merged_results: list[dict[str, Any]] = []

        for kb_id in kb_ids:
            kb_result = await self.get_by_id(kb_id)
            if not kb_result.is_success:
                continue

            kb = kb_result.value
            ready_document_ids = None
            if isinstance(ready_document_ids_by_kb, dict):
                ready_document_ids = {
                    str(doc_id) for doc_id in ready_document_ids_by_kb.get(kb_id, [])
                }

            collection = vector_store._get_collection(kb.vector_collection)
            if collection is None:
                continue

            try:
                raw_chunks = collection.get(include=["documents", "metadatas"])
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Keyword fallback collection read failed",
                    knowledge_base_id=kb_id,
                    reason=str(exc),
                )
                continue

            documents = (
                raw_chunks.get("documents") if isinstance(raw_chunks, dict) else []
            )
            metadatas = (
                raw_chunks.get("metadatas") if isinstance(raw_chunks, dict) else []
            )

            if not isinstance(documents, list):
                continue

            for index, content in enumerate(documents):
                if not isinstance(content, str):
                    continue
                snippet_source = content.strip()
                if not snippet_source:
                    continue

                normalized_content = snippet_source.lower()
                raw_score = self._keyword_match_score(
                    normalized_content=normalized_content,
                    normalized_query=normalized_query,
                    candidates=merged_candidates,
                )
                if raw_score < 1.2:
                    continue

                metadata: dict[str, Any] = {}
                if isinstance(metadatas, list) and index < len(metadatas):
                    metadata_candidate = metadatas[index]
                    if isinstance(metadata_candidate, dict):
                        metadata = metadata_candidate

                if not self._metadata_matches(metadata, metadata_filter):
                    continue

                if ready_document_ids is not None:
                    document_id = str(metadata.get("document_id") or "").strip()
                    if not document_id or document_id not in ready_document_ids:
                        continue

                normalized_score = round(min(0.95, 0.45 + raw_score * 0.07), 4)

                merged_results.append(
                    {
                        "content": snippet_source,
                        "score": normalized_score,
                        "source": metadata.get("document_title", "未知来源"),
                        "metadata": {
                            "document_id": metadata.get("document_id"),
                            "document_title": metadata.get("document_title"),
                            "chunk_index": metadata.get("chunk_index"),
                        },
                        "knowledge_base_id": kb_id,
                        "knowledge_base_name": kb.name,
                        "retrieval_mode": "keyword_fallback",
                    }
                )

        merged_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged_results[: max(1, top_k)]

    # ========== Document Preview ==========

    async def get_document_chunks(
        self, kb_id: str, doc_id: str, page: int = 1, page_size: int = 10
    ) -> Result[tuple[list[dict[str, Any]], int]]:
        """
        Get document chunks for preview.

        Returns chunks stored in vector database.
        """
        doc_result = await self.get_document(kb_id, doc_id)
        if not doc_result.is_success:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        doc = doc_result.value  # Validate document exists
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        kb = kb_result.value

        # Get chunks from vector store
        vector_store = get_knowledge_vector_store()
        collection = vector_store._get_collection(kb.vector_collection)

        if not collection:
            logger.warning(
                "Vector collection unavailable, fallback to source document chunks",
                knowledge_base_id=kb_id,
                document_id=doc_id,
            )
            fallback = await self._get_document_chunks_from_source(doc, page, page_size)
            return Result.ok(fallback)

        try:
            # Get all chunks for this document
            results = collection.get(
                where={"document_id": doc_id}, include=["documents", "metadatas"]
            )

            if not results or not results["documents"]:
                logger.info(
                    "No vector chunks found for document, fallback to source document chunks",
                    knowledge_base_id=kb_id,
                    document_id=doc_id,
                )
                fallback = await self._get_document_chunks_from_source(
                    doc, page, page_size
                )
                return Result.ok(fallback)

            # Format chunks
            chunks = []
            for i, doc_content in enumerate(results["documents"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                chunks.append(
                    {
                        "index": metadata.get("chunk_index", i),
                        "content": doc_content,
                        "metadata": {
                            "start_char": metadata.get("start_char"),
                            "end_char": metadata.get("end_char"),
                        },
                    }
                )

            # Sort by index
            chunks.sort(key=lambda x: x["index"])
            total = len(chunks)

            # Paginate
            start = (page - 1) * page_size
            end = start + page_size
            paginated = chunks[start:end]

            return Result.ok((paginated, total))

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Failed to get document chunks: {e}")
            fallback = await self._get_document_chunks_from_source(doc, page, page_size)
            return Result.ok(fallback)

    async def _get_document_chunks_from_source(
        self,
        doc: KnowledgeDocument,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fallback preview by reading original source file and splitting into chunks."""
        try:
            processor = get_document_processor()
            content = await processor._read_document(doc.file_url, doc.file_type)  # noqa: SLF001
            if not content:
                return ([], 0)

            chunks = processor._split_into_chunks(content)  # noqa: SLF001
            if not chunks:
                return ([], 0)

            formatted = [
                {
                    "index": chunk.get("index", index),
                    "content": chunk.get("content", ""),
                    "metadata": chunk.get("metadata", {}),
                }
                for index, chunk in enumerate(chunks)
                if isinstance(chunk, dict)
            ]
            total = len(formatted)

            start = (page - 1) * page_size
            end = start + page_size
            return (formatted[start:end], total)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Fallback source preview failed: {exc}")
            return ([], 0)

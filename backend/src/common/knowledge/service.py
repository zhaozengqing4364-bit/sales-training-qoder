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

import asyncio
import builtins
import inspect
import json
import os
import re
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher
from hashlib import md5
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.embedding_service import get_embedding_service
from common.cache.redis_cache import get_cache
from common.error_handling.result import Result
from common.knowledge.bm25_index import get_bm25_index_manager
from common.knowledge.semantic_cache import get_semantic_search_cache
from common.monitoring.logger import get_logger
from common.storage import get_document_storage_service

from .models import (
    DocumentStatus,
    KnowledgeBase,
    KnowledgeBaseStatus,
    KnowledgeDictionaryEntry,
    KnowledgeDictionaryEntryStatus,
    KnowledgeDocument,
)
from .processor import get_document_processor
from .schemas import (
    CreateKnowledgeBaseRequest,
    CreateKnowledgeDictionaryEntryRequest,
    KnowledgeBaseListItem,
    KnowledgeDictionaryEntryResponse,
    KnowledgeDocumentListItem,
    UpdateKnowledgeBaseRequest,
    UpdateKnowledgeDictionaryEntryRequest,
)
from .vector_store import get_knowledge_vector_store

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


QUERY_EXPANSION_MAP: dict[str, builtins.list[str]] = {
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
SEARCH_TERM_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,12}")
DICTIONARY_TERM_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9._-]{1,30}|[\u4e00-\u9fff]{2,12}")
DICTIONARY_STOP_TERMS: set[str] = {
    "我们",
    "可以",
    "这个",
    "那个",
    "进行",
    "通过",
    "支持",
    "提供",
    "用户",
    "客户",
    "系统",
    "平台",
    "产品",
    "服务",
    "功能",
    "能力",
    "方案",
    "企业",
    "知识",
    "训练",
    "介绍",
    "使用",
}


def _resolve_cache_ttl_seconds(
    env_name: str,
    default_ms: int,
    *,
    min_ms: int = 0,
    max_ms: int = 60000,
) -> float:
    raw_value = os.getenv(env_name, str(default_ms))
    try:
        timeout_ms = int(raw_value)
    except (TypeError, ValueError):
        timeout_ms = default_ms
    timeout_ms = max(min_ms, min(max_ms, timeout_ms))
    return timeout_ms / 1000.0


def _resolve_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name, "true" if default else "false")
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _resolve_bounded_int_env(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


SEARCH_HEALTH_CACHE_TTL_SECONDS = _resolve_cache_ttl_seconds(
    "KNOWLEDGE_SEARCH_HEALTH_CACHE_TTL_MS",
    default_ms=8000,
)
READY_DOC_IDS_CACHE_TTL_SECONDS = _resolve_cache_ttl_seconds(
    "KNOWLEDGE_READY_DOC_IDS_CACHE_TTL_MS",
    default_ms=8000,
)
_runtime_cache_max_entries_raw = os.getenv("KNOWLEDGE_RUNTIME_CACHE_MAX_ENTRIES", "512")
try:
    _runtime_cache_max_entries = int(_runtime_cache_max_entries_raw)
except (TypeError, ValueError):
    _runtime_cache_max_entries = 512
RUNTIME_CACHE_MAX_ENTRIES = max(32, min(4096, _runtime_cache_max_entries))
KNOWLEDGE_VECTOR_SEARCH_CONCURRENCY = _resolve_bounded_int_env(
    "KNOWLEDGE_VECTOR_SEARCH_CONCURRENCY",
    default=4,
    minimum=1,
    maximum=16,
)
KNOWLEDGE_EMBED_BATCH_ENABLED = _resolve_bool_env(
    "KNOWLEDGE_EMBED_BATCH_ENABLED",
    default=True,
)
KNOWLEDGE_STRICT_KEYWORD_FALLBACK_ON_EMPTY_VECTOR = _resolve_bool_env(
    "KNOWLEDGE_STRICT_KEYWORD_FALLBACK_ON_EMPTY_VECTOR",
    default=True,
)


class KnowledgeService:
    """Knowledge Base management service."""

    _search_health_cache: dict[str, tuple[float, dict[str, int]]] = {}
    _ready_document_ids_cache: dict[
        str, tuple[float, dict[str, builtins.list[str]]]
    ] = {}

    def __init__(self, db: AsyncSession):
        self.db = db
        self._last_search_timing: dict[str, Any] = {}
        self._last_search_health_cache_hit = False
        self._last_ready_doc_ids_cache_hit = False

    @staticmethod
    def _build_kb_cache_key(kb_ids: builtins.list[str]) -> str:
        unique_ids = sorted(
            {str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()}
        )
        return ",".join(unique_ids)

    @staticmethod
    def _is_cache_valid(expires_at: float) -> bool:
        return expires_at > time.monotonic()

    def get_last_search_timing(self) -> dict[str, Any]:
        if not isinstance(self._last_search_timing, dict):
            return {}
        return dict(self._last_search_timing)

    @staticmethod
    def _orm_field(row: object, name: str) -> Any:
        return cast(Any, getattr(row, name))

    @staticmethod
    def _set_orm_field(row: object, name: str, value: object) -> None:
        setattr(row, name, value)

    @staticmethod
    def _orm_int(row: object, name: str, default: int = 0) -> int:
        try:
            return int(getattr(row, name, default) or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _orm_str(row: object, name: str, default: str = "") -> str:
        value = getattr(row, name, default)
        return str(value if value is not None else default)

    @staticmethod
    def _require_value(result: Result[Any]) -> Any:
        if result.value is None:
            raise ValueError("[RESULT_VALUE_REQUIRED]")
        return result.value

    async def get_search_health(self, kb_ids: builtins.list[str]) -> dict[str, int]:
        self._last_search_health_cache_hit = False
        normalized_ids = [str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()]
        if not normalized_ids:
            return {
                "knowledge_base_count": 0,
                "ready_document_count": 0,
                "ready_chunk_count": 0,
                "vector_chunk_count": 0,
                "is_ready": False,
            }

        cache_key = self._build_kb_cache_key(normalized_ids)
        if SEARCH_HEALTH_CACHE_TTL_SECONDS > 0:
            cached = self._search_health_cache.get(cache_key)
            if cached and self._is_cache_valid(cached[0]):
                self._last_search_health_cache_hit = True
                return dict(cached[1])

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

        payload = {
            "knowledge_base_count": len(normalized_ids),
            "ready_document_count": ready_document_count,
            "ready_chunk_count": ready_chunk_count_value,
            "vector_chunk_count": vector_chunk_count,
            "is_ready": is_ready,
        }
        if SEARCH_HEALTH_CACHE_TTL_SECONDS > 0:
            if len(self._search_health_cache) >= RUNTIME_CACHE_MAX_ENTRIES:
                self._search_health_cache.clear()
            self._search_health_cache[cache_key] = (
                time.monotonic() + SEARCH_HEALTH_CACHE_TTL_SECONDS,
                dict(payload),
            )
        return payload

    async def _get_ready_document_ids_by_kb(
        self,
        kb_ids: builtins.list[str],
    ) -> dict[str, builtins.list[str]]:
        self._last_ready_doc_ids_cache_hit = False
        normalized_ids = [str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()]
        if not normalized_ids:
            return {}

        cache_key = self._build_kb_cache_key(normalized_ids)
        if READY_DOC_IDS_CACHE_TTL_SECONDS > 0:
            cached = self._ready_document_ids_cache.get(cache_key)
            if cached and self._is_cache_valid(cached[0]):
                self._last_ready_doc_ids_cache_hit = True
                return {kb_id: list(doc_ids) for kb_id, doc_ids in cached[1].items()}

        stmt = (
            select(KnowledgeDocument.knowledge_base_id, KnowledgeDocument.id)
            .where(KnowledgeDocument.knowledge_base_id.in_(normalized_ids))
            .where(KnowledgeDocument.status == DocumentStatus.READY.value)
            .where(KnowledgeDocument.chunk_count > 0)
        )
        rows = (await self.db.execute(stmt)).all()

        ready_docs: dict[str, builtins.list[str]] = {}
        for kb_id, doc_id in rows:
            ready_docs.setdefault(str(kb_id), []).append(str(doc_id))
        if READY_DOC_IDS_CACHE_TTL_SECONDS > 0:
            if len(self._ready_document_ids_cache) >= RUNTIME_CACHE_MAX_ENTRIES:
                self._ready_document_ids_cache.clear()
            self._ready_document_ids_cache[cache_key] = (
                time.monotonic() + READY_DOC_IDS_CACHE_TTL_SECONDS,
                {kb_id: list(doc_ids) for kb_id, doc_ids in ready_docs.items()},
            )
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
    ) -> tuple[builtins.list[KnowledgeBaseListItem], int]:
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
        assert kb is not None

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
        assert kb is not None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                self._set_orm_field(kb, field, value)

        self._set_orm_field(kb, "updated_at", datetime.now(UTC))

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
        assert kb is not None

        # Check if referenced by Agent/Persona
        ref_check = await self._check_references(kb_id)
        if ref_check:
            return Result.fail(f"[KNOWLEDGE_BASE_IN_USE] {ref_check}")

        # Delete vector collection
        vector_store = get_knowledge_vector_store()
        await vector_store.delete_collection(self._orm_str(kb, "vector_collection"))

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
                if self._orm_field(a, "default_knowledge_base_ids")
                and kb_id in self._orm_field(a, "default_knowledge_base_ids")
            ]

            if referencing_agents:
                names = ", ".join(
                    self._orm_str(agent, "name") for agent in referencing_agents[:3]
                )
                return f"Referenced by Agents: {names}"

            # Check Personas
            persona_stmt = select(Persona)
            persona_result = await self.db.execute(persona_stmt)
            personas = persona_result.scalars().all()

            referencing_personas = [
                p
                for p in personas
                if self._orm_field(p, "knowledge_base_ids")
                and kb_id in self._orm_field(p, "knowledge_base_ids")
            ]

            if referencing_personas:
                names = ", ".join(
                    self._orm_str(persona, "name")
                    for persona in referencing_personas[:3]
                )
                return f"Referenced by Personas: {names}"

            return None

        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Reference check failed (continuing): {e}")
            return None

    # ========== Document Operations ==========

    async def create_document(
        self,
        kb_id: str,
        title: str,
        file_type: str,
        file_url: str,
        file_size: int,
        content_hash: str | None = None,
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
            content_hash=content_hash,
        )

    async def create_document_with_id(
        self,
        doc_id: str,
        kb_id: str,
        title: str,
        file_type: str,
        file_url: str,
        file_size: int,
        content_hash: str | None = None,
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
                content_hash=content_hash,
                status=DocumentStatus.PENDING.value,
                chunk_count=0,
            )

            self.db.add(doc)

            # Update document count
            kb = self._require_value(kb_result)
            self._set_orm_field(
                kb,
                "document_count",
                self._orm_int(kb, "document_count") + 1,
            )

            await self.db.flush()
            await self.db.refresh(doc)

            logger.info(f"Created document: {doc.id} in KB {kb_id}")
            return Result.ok(doc)

        except IntegrityError as e:
            await self.db.rollback()
            logger.warning(
                "Duplicate document content hash detected",
                kb_id=kb_id,
                content_hash=content_hash,
                error=str(e),
            )
            return Result.fail("[DOCUMENT_DUPLICATE_CONTENT]")
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Failed to create document: {e}")
            return Result.fail(f"[DOCUMENT_CREATE_FAILED] {str(e)}")

    async def get_document_by_content_hash(
        self,
        kb_id: str,
        content_hash: str,
    ) -> KnowledgeDocument | None:
        """Find existing document by content hash in the same knowledge base."""
        if not content_hash:
            return None

        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_base_id == kb_id,
            KnowledgeDocument.content_hash == content_hash,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self, kb_id: str, page: int = 1, page_size: int = 20
    ) -> Result[tuple[builtins.list[KnowledgeDocumentListItem], int]]:
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
                error_message=doc.error_message,
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

    # ========== Knowledge Dictionary ==========

    @staticmethod
    def _parse_aliases_json(value: Any) -> builtins.list[str]:
        if isinstance(value, list):
            raw_aliases = value
        else:
            try:
                raw_aliases = json.loads(str(value or "[]"))
            except json.JSONDecodeError:
                raw_aliases = []
        aliases: builtins.list[str] = []
        for item in raw_aliases if isinstance(raw_aliases, list) else []:
            alias = str(item or "").strip()
            if alias and alias not in aliases:
                aliases.append(alias)
        return aliases

    @classmethod
    def _dictionary_entry_response(
        cls, entry: KnowledgeDictionaryEntry
    ) -> KnowledgeDictionaryEntryResponse:
        return KnowledgeDictionaryEntryResponse(
            id=str(entry.id),
            knowledge_base_id=str(entry.knowledge_base_id),
            canonical_term=str(entry.canonical_term),
            aliases=cls._parse_aliases_json(entry.aliases_json),
            term_type=str(entry.term_type),
            status=str(entry.status),
            confidence=int(entry.confidence or 0),
            source=str(entry.source),
            evidence_count=int(entry.evidence_count or 0),
            notes=entry.notes,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    @staticmethod
    def _dictionary_integrity_error_code(error: IntegrityError) -> str:
        detail = str(error.orig if getattr(error, "orig", None) else error).lower()
        if (
            "uq_knowledge_dictionary_entry_kb_canonical" in detail
            or "unique" in detail
            or "duplicate" in detail
        ):
            return "[KNOWLEDGE_DICTIONARY_ENTRY_DUPLICATE]"
        return "[KNOWLEDGE_DICTIONARY_ENTRY_INVALID]"

    async def list_dictionary_entries(
        self,
        kb_id: str,
        *,
        status: str | None = None,
    ) -> Result[tuple[builtins.list[KnowledgeDictionaryEntryResponse], int]]:
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        stmt = select(KnowledgeDictionaryEntry).where(
            KnowledgeDictionaryEntry.knowledge_base_id == kb_id
        )
        if status:
            stmt = stmt.where(KnowledgeDictionaryEntry.status == status)
        stmt = stmt.order_by(
            KnowledgeDictionaryEntry.status.asc(),
            KnowledgeDictionaryEntry.evidence_count.desc(),
            KnowledgeDictionaryEntry.canonical_term.asc(),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        items = [self._dictionary_entry_response(row) for row in rows]
        return Result.ok((items, len(items)))

    async def create_dictionary_entry(
        self,
        kb_id: str,
        data: CreateKnowledgeDictionaryEntryRequest,
        *,
        source: str = "manual",
        evidence_count: int = 0,
    ) -> Result[KnowledgeDictionaryEntryResponse]:
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")
        canonical_term = data.canonical_term.strip()
        aliases = [alias for alias in data.aliases if alias != canonical_term]
        try:
            entry = KnowledgeDictionaryEntry(
                knowledge_base_id=kb_id,
                canonical_term=canonical_term,
                aliases_json=json.dumps(aliases, ensure_ascii=False),
                term_type=data.term_type.strip() or "other",
                status=data.status,
                confidence=data.confidence,
                source=source,
                evidence_count=max(0, int(evidence_count or 0)),
                notes=data.notes,
            )
            self.db.add(entry)
            await self.db.flush()
            await self.db.refresh(entry)
            return Result.ok(self._dictionary_entry_response(entry))
        except IntegrityError as exc:
            await self.db.rollback()
            return Result.fail(self._dictionary_integrity_error_code(exc))

    async def update_dictionary_entry(
        self,
        kb_id: str,
        entry_id: str,
        data: UpdateKnowledgeDictionaryEntryRequest,
    ) -> Result[KnowledgeDictionaryEntryResponse]:
        stmt = select(KnowledgeDictionaryEntry).where(
            KnowledgeDictionaryEntry.id == entry_id,
            KnowledgeDictionaryEntry.knowledge_base_id == kb_id,
        )
        entry = (await self.db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            return Result.fail("[KNOWLEDGE_DICTIONARY_ENTRY_NOT_FOUND]")
        update_data = data.model_dump(exclude_unset=True)
        if "canonical_term" in update_data and update_data["canonical_term"] is not None:
            entry.canonical_term = str(update_data["canonical_term"]).strip()
        if "aliases" in update_data and update_data["aliases"] is not None:
            aliases = [
                alias
                for alias in data.aliases or []
                if alias != str(entry.canonical_term)
            ]
            entry.aliases_json = json.dumps(aliases, ensure_ascii=False)
        for field_name in ("term_type", "status", "confidence", "notes"):
            if field_name in update_data:
                setattr(entry, field_name, update_data[field_name])
        try:
            await self.db.flush()
            await self.db.refresh(entry)
            return Result.ok(self._dictionary_entry_response(entry))
        except IntegrityError as exc:
            await self.db.rollback()
            return Result.fail(self._dictionary_integrity_error_code(exc))

    async def delete_dictionary_entry(self, kb_id: str, entry_id: str) -> Result[bool]:
        stmt = select(KnowledgeDictionaryEntry).where(
            KnowledgeDictionaryEntry.id == entry_id,
            KnowledgeDictionaryEntry.knowledge_base_id == kb_id,
        )
        entry = (await self.db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            return Result.fail("[KNOWLEDGE_DICTIONARY_ENTRY_NOT_FOUND]")
        await self.db.delete(entry)
        await self.db.flush()
        return Result.ok(True)

    async def active_dictionary_lexicon(
        self, kb_ids: builtins.list[str]
    ) -> builtins.list[dict[str, Any]]:
        normalized_ids = [str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()]
        if not normalized_ids:
            return []
        stmt = select(KnowledgeDictionaryEntry).where(
            KnowledgeDictionaryEntry.knowledge_base_id.in_(normalized_ids),
            KnowledgeDictionaryEntry.status == KnowledgeDictionaryEntryStatus.ACTIVE.value,
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        lexicon: builtins.list[dict[str, Any]] = []
        for row in rows:
            aliases = self._parse_aliases_json(row.aliases_json)
            if not aliases:
                continue
            lexicon.append(
                {
                    "canonical_term": str(row.canonical_term),
                    "aliases": aliases,
                    "entity_type": str(row.term_type or "other"),
                    "confidence": min(1.0, max(0.0, float(row.confidence or 0) / 100.0)),
                    "scope": f"knowledge_base:{row.knowledge_base_id}",
                }
            )
        return lexicon

    @staticmethod
    def _extract_dictionary_terms_from_text(text: str) -> Counter[str]:
        counter: Counter[str] = Counter()
        for match in DICTIONARY_TERM_RE.finditer(text):
            term = match.group(0).strip()
            if len(term) < 2 or term in DICTIONARY_STOP_TERMS:
                continue
            if len(set(term)) == 1:
                continue
            counter[term] += 1
        return counter

    async def generate_dictionary_drafts(
        self,
        kb_id: str,
        *,
        limit: int = 30,
    ) -> Result[tuple[builtins.list[KnowledgeDictionaryEntryResponse], int]]:
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")
        doc_stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_base_id == kb_id,
            KnowledgeDocument.status == DocumentStatus.READY.value,
        )
        docs = (await self.db.execute(doc_stmt)).scalars().all()
        if not docs:
            return Result.ok(([], 0))

        term_counts: Counter[str] = Counter()
        for doc in docs[:20]:
            chunk_result = await self.get_document_chunks(kb_id, str(doc.id), 1, 100)
            chunk_items = chunk_result.value[0] if chunk_result.is_success and chunk_result.value else []
            for chunk in chunk_items:
                term_counts.update(
                    self._extract_dictionary_terms_from_text(str(chunk.get("content") or ""))
                )

        existing_stmt = select(KnowledgeDictionaryEntry.canonical_term).where(
            KnowledgeDictionaryEntry.knowledge_base_id == kb_id
        )
        existing = {
            str(item)
            for item in (await self.db.execute(existing_stmt)).scalars().all()
        }

        created: builtins.list[KnowledgeDictionaryEntryResponse] = []
        skipped = 0
        for term, count in term_counts.most_common(max(1, min(limit, 100))):
            if count < 2 or term in existing:
                skipped += 1
                continue
            request = CreateKnowledgeDictionaryEntryRequest(
                canonical_term=term,
                aliases=[],
                term_type="auto",
                status=KnowledgeDictionaryEntryStatus.DRAFT.value,
                confidence=min(95, 60 + min(count, 7) * 5),
                notes="从知识库已就绪文档中自动抽取，需人工补充误识别别名后发布。",
            )
            result = await self.create_dictionary_entry(
                kb_id,
                request,
                source="auto_extract",
                evidence_count=count,
            )
            if result.is_success and result.value is not None:
                created.append(result.value)
                existing.add(term)
            else:
                skipped += 1
        return Result.ok((created, skipped))

    async def delete_document(self, kb_id: str, doc_id: str) -> Result[bool]:
        """Delete document and its vectors"""
        doc_result = await self.get_document(kb_id, doc_id)
        if not doc_result.is_success:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        doc = doc_result.value

        # Get KB for vector collection name
        kb_result = await self.get_by_id(kb_id)
        if kb_result.is_success:
            kb = self._require_value(kb_result)
            vector_collection = self._orm_str(kb, "vector_collection")

            # Delete vectors
            vector_store = get_knowledge_vector_store()
            await vector_store.delete_document_chunks(
                collection_name=vector_collection, document_id=doc_id
            )

            # Invalidate BM25 index for this collection
            get_bm25_index_manager().invalidate_collection(vector_collection)

            # Invalidate semantic cache for this KB
            try:
                await get_semantic_search_cache().invalidate_kb(get_cache(), kb_id)
            except Exception:  # noqa: BLE001
                logger.debug("Semantic cache invalidation failed, non-critical")

            # Update KB stats
            self._set_orm_field(
                kb,
                "document_count",
                max(0, self._orm_int(kb, "document_count") - 1),
            )
            self._set_orm_field(
                kb,
                "total_chunks",
                max(
                    0,
                    self._orm_int(kb, "total_chunks")
                    - self._orm_int(doc, "chunk_count"),
                ),
            )

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

        old_chunk_count = self._orm_int(doc, "chunk_count")
        self._set_orm_field(doc, "status", status)
        self._set_orm_field(doc, "chunk_count", chunk_count)
        self._set_orm_field(doc, "error_message", error_message)

        # Update KB total_chunks
        if status == DocumentStatus.READY.value:
            kb_result = await self.get_by_id(self._orm_str(doc, "knowledge_base_id"))
            if kb_result.is_success:
                kb = self._require_value(kb_result)
                # Adjust for any previous chunks
                self._set_orm_field(
                    kb,
                    "total_chunks",
                    self._orm_int(kb, "total_chunks") - old_chunk_count + chunk_count,
                )

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
        enable_rerank: bool = False,
        rerank_top_k: int = 8,
    ) -> Result[builtins.list[dict[str, Any]]]:
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
            enable_rerank=enable_rerank,
            rerank_top_k=rerank_top_k,
        )

    async def search_multiple(
        self,
        kb_ids: builtins.list[str],
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.7,
        metadata_filter: dict[str, Any] | None = None,
        enable_hybrid: bool = True,
        keyword_candidate_limit: int = 32,
        embedding_timeout_ms: int = 0,
        enable_rerank: bool = False,
        rerank_top_k: int = 8,
    ) -> Result[builtins.list[dict[str, Any]]]:
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
        # ── Semantic cache: early check ──
        sem_cache = get_semantic_search_cache()
        cache_mgr = get_cache()

        search_started_at = time.monotonic()
        embedding_ms = 0.0
        vector_ms = 0.0
        keyword_ms = 0.0
        self._last_search_timing = {}

        normalized_kb_ids = [
            str(kb_id).strip() for kb_id in kb_ids if str(kb_id).strip()
        ]
        if not normalized_kb_ids:
            self._last_search_timing = {
                "phase_total_ms": round(
                    (time.monotonic() - search_started_at) * 1000, 1
                ),
                "phase_embedding_ms": 0.0,
                "phase_vector_ms": 0.0,
                "phase_keyword_ms": 0.0,
                "cache_hit_health": self._last_search_health_cache_hit,
                "cache_hit_ready_docs": self._last_ready_doc_ids_cache_hit,
            }
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
            self._last_search_timing = {
                "phase_total_ms": round(
                    (time.monotonic() - search_started_at) * 1000, 1
                ),
                "phase_embedding_ms": 0.0,
                "phase_vector_ms": 0.0,
                "phase_keyword_ms": 0.0,
                "cache_hit_health": self._last_search_health_cache_hit,
                "cache_hit_ready_docs": self._last_ready_doc_ids_cache_hit,
            }
            return Result.ok([])

        query_variants = self._build_query_variants(query)
        resolved_embedding_timeout_ms = max(
            0, min(10000, int(embedding_timeout_ms or 0))
        )
        embedding_timeout_seconds = (
            resolved_embedding_timeout_ms / 1000.0
            if resolved_embedding_timeout_ms > 0
            else 0.0
        )

        embedding_service = get_embedding_service()
        vector_results: builtins.list[dict[str, Any]] = []
        embedding_failure: str | None = None
        query_embeddings: builtins.list[tuple[str, builtins.list[float]]] = []

        kb_contexts: dict[str, Any] = {}
        for kb_id in searchable_kb_ids:
            kb_result = await self.get_by_id(kb_id)
            if not kb_result.is_success:
                continue
            kb_contexts[kb_id] = kb_result.value

        if not kb_contexts:
            self._last_search_timing = {
                "phase_total_ms": round(
                    (time.monotonic() - search_started_at) * 1000, 1
                ),
                "phase_embedding_ms": 0.0,
                "phase_vector_ms": 0.0,
                "phase_keyword_ms": 0.0,
                "cache_hit_health": self._last_search_health_cache_hit,
                "cache_hit_ready_docs": self._last_ready_doc_ids_cache_hit,
            }
            return Result.ok([])

        if embedding_service.is_configured:
            embedding_started_at = time.monotonic()

            async def _collect_query_embeddings() -> tuple[
                builtins.list[tuple[str, builtins.list[float]]], str | None
            ]:
                collected_embeddings: builtins.list[tuple[str, builtins.list[float]]] = []
                failure_reason: str | None = None
                should_use_batch = KNOWLEDGE_EMBED_BATCH_ENABLED
                if should_use_batch:
                    embed_batch = getattr(embedding_service, "embed_batch", None)
                    if not callable(embed_batch):
                        should_use_batch = False
                    else:
                        batch_candidate = embed_batch(query_variants)
                        if not inspect.isawaitable(batch_candidate):
                            should_use_batch = False
                        else:
                            batch_result = await batch_candidate
                            if batch_result.is_success and isinstance(
                                batch_result.value, list
                            ):
                                for variant, embedding in zip(
                                    query_variants, batch_result.value
                                ):
                                    if isinstance(embedding, list) and embedding:
                                        collected_embeddings.append(
                                            (variant, embedding)
                                        )
                            else:
                                failure_reason = (
                                    batch_result.fallback or "[EMBEDDING_FAILED]"
                                )
                if not should_use_batch:
                    for variant in query_variants:
                        embed_result = await embedding_service.embed(variant)
                        if embed_result.is_success and embed_result.value:
                            collected_embeddings.append((variant, embed_result.value))
                            continue
                        if failure_reason is None:
                            failure_reason = (
                                embed_result.fallback or "[EMBEDDING_FAILED]"
                            )
                return collected_embeddings, failure_reason

            try:
                if embedding_timeout_seconds > 0:
                    query_embeddings, embedding_failure = await asyncio.wait_for(
                        _collect_query_embeddings(),
                        timeout=embedding_timeout_seconds,
                    )
                else:
                    (
                        query_embeddings,
                        embedding_failure,
                    ) = await _collect_query_embeddings()
            except TimeoutError:
                embedding_failure = "[EMBEDDING_TIMEOUT]"
                logger.warning(
                    "Embedding stage timeout in multi-knowledge search, fallback to keyword matching",
                    timeout_ms=resolved_embedding_timeout_ms,
                )
            embedding_ms = (time.monotonic() - embedding_started_at) * 1000

            # ── Semantic cache: check after embedding ──
            if (
                query_embeddings
                and len(query_embeddings) > 0
                and len(query_embeddings[0]) > 1
            ):
                first_embedding = query_embeddings[0][1]
                cached_results = await sem_cache.get(
                    cache_manager=cache_mgr,
                    kb_ids=list(kb_contexts.keys()),
                    query_embedding=first_embedding,
                    top_k=top_k,
                )
                if cached_results is not None:
                    self._last_search_timing.update(
                        {
                            "semantic_cache_hit": True,
                            "phase_total_ms": round(
                                (time.monotonic() - search_started_at) * 1000, 1
                            ),
                            "phase_embedding_ms": round(embedding_ms, 1),
                        }
                    )
                    return Result.ok(cached_results)

            if query_embeddings:
                vector_started_at = time.monotonic()
                vector_store = get_knowledge_vector_store()
                vector_top_k = max(6, top_k * 2)
                semaphore = asyncio.Semaphore(KNOWLEDGE_VECTOR_SEARCH_CONCURRENCY)

                async def _search_one_variant(
                    *,
                    kb_id: str,
                    kb: Any,
                    ready_document_ids: builtins.list[str],
                    variant: str,
                    query_embedding: builtins.list[float],
                ) -> builtins.list[dict[str, Any]]:
                    async with semaphore:
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
                        return []
                    if not isinstance(search_result.value, list):
                        return []

                    enriched_rows: builtins.list[dict[str, Any]] = []
                    for row in search_result.value:
                        normalized_row = dict(row)
                        normalized_row["knowledge_base_id"] = kb_id
                        normalized_row["knowledge_base_name"] = kb.name
                        normalized_row.setdefault("matched_query", variant)
                        enriched_rows.append(normalized_row)
                    return enriched_rows

                vector_tasks: builtins.list[asyncio.Task[builtins.list[dict[str, Any]]]] = []
                for kb_id, kb in kb_contexts.items():
                    ready_document_ids = ready_document_ids_by_kb.get(kb_id, [])
                    if not ready_document_ids:
                        continue
                    for variant, query_embedding in query_embeddings:
                        vector_tasks.append(
                            asyncio.create_task(
                                _search_one_variant(
                                    kb_id=kb_id,
                                    kb=kb,
                                    ready_document_ids=ready_document_ids,
                                    variant=variant,
                                    query_embedding=query_embedding,
                                )
                            )
                        )

                if vector_tasks:
                    vector_task_rows = await asyncio.gather(*vector_tasks)
                    for rows in vector_task_rows:
                        vector_results.extend(rows)
                vector_ms = (time.monotonic() - vector_started_at) * 1000
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

        keyword_results: builtins.list[dict[str, Any]] = []
        should_run_keyword_fallback = False
        if enable_hybrid:
            should_run_keyword_fallback = True
        elif not vector_results:
            should_run_keyword_fallback = (
                KNOWLEDGE_STRICT_KEYWORD_FALLBACK_ON_EMPTY_VECTOR
            )

        if should_run_keyword_fallback:
            keyword_started_at = time.monotonic()
            keyword_results = await self._search_multiple_by_keywords(
                kb_ids=list(kb_contexts.keys()),
                query=query,
                top_k=max(6, top_k * 2),
                metadata_filter=metadata_filter,
                candidate_limit=max(8, min(128, int(keyword_candidate_limit))),
                query_variants=query_variants,
                ready_document_ids_by_kb=ready_document_ids_by_kb,
            )
            keyword_ms = (time.monotonic() - keyword_started_at) * 1000

        self._last_search_timing = {
            "phase_total_ms": round((time.monotonic() - search_started_at) * 1000, 1),
            "phase_embedding_ms": round(embedding_ms, 1),
            "phase_vector_ms": round(vector_ms, 1),
            "phase_keyword_ms": round(keyword_ms, 1),
            "cache_hit_health": self._last_search_health_cache_hit,
            "cache_hit_ready_docs": self._last_ready_doc_ids_cache_hit,
            "vector_result_count": len(vector_results),
            "keyword_result_count": len(keyword_results),
        }

        candidate_top_k = max(1, max(top_k, rerank_top_k))
        final_results: builtins.list[dict[str, Any]] = []

        if enable_hybrid:
            fused_results = self._fuse_retrieval_results(
                vector_results=vector_results,
                keyword_results=keyword_results,
                top_k=candidate_top_k,
            )
            final_results = fused_results[: max(1, top_k)] if fused_results else []
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
            final_results = sorted_rows[: max(1, top_k)]

        if not final_results and keyword_results:
            final_results = keyword_results[:candidate_top_k][: max(1, top_k)]

        if not final_results and embedding_failure:
            return Result.fail(f"[KNOWLEDGE_SEARCH_UNAVAILABLE] {embedding_failure}")

        # ── Parent-child expansion: replace child hit content with parent ──
        if final_results:
            child_hits = [
                row
                for row in final_results
                if (row.get("metadata") or {}).get("chunk_type") == "child"
                and (row.get("metadata") or {}).get("parent_id")
            ]
            if child_hits:
                try:
                    vector_store = get_knowledge_vector_store()
                    # Collect unique (collection, parent_id) pairs
                    parent_id_map: dict[str, tuple[str, str]] = {}
                    for row in child_hits:
                        meta = row.get("metadata") or {}
                        kb_id = str(row.get("knowledge_base_id") or "")
                        parent_id = str(meta.get("parent_id") or "")
                        coll_name = ""
                        kb_ctx = kb_contexts.get(kb_id)
                        if kb_ctx:
                            coll_name = kb_ctx.vector_collection
                        if parent_id and coll_name:
                            parent_id_map[parent_id] = (coll_name, parent_id)

                    if parent_id_map:
                        # Batch-fetch all parent chunks
                        for pid, (coll_name, _raw_id) in parent_id_map.items():
                            parent_result = await vector_store.get_parent_chunks(
                                collection_name=coll_name,
                                parent_ids=[pid],
                            )
                            if parent_result.is_success and parent_result.value:
                                parent_data = parent_result.value[0]
                                parent_content = parent_data.get("content", "")
                                if parent_content:
                                    for row in final_results:
                                        meta = row.get("metadata") or {}
                                        if str(meta.get("parent_id") or "") == pid:
                                            row["_child_content"] = row.get(
                                                "content", ""
                                            )
                                            row["content"] = parent_content
                                            existing_mode = row.get(
                                                "retrieval_mode", ""
                                            )
                                            row["retrieval_mode"] = (
                                                f"{existing_mode}+parent_expansion"
                                                if existing_mode
                                                else "parent_expansion"
                                            )
                except Exception:  # noqa: BLE001
                    logger.debug("Parent-child expansion failed, using child content")

        # ── Cross-encoder scoring (writes cross_encoder_score for unified reranker) ──
        if final_results and os.getenv("CROSS_ENCODER_BACKEND", "").strip():
            try:
                from common.knowledge_engine.cross_encoder_reranker import (
                    get_cross_encoder_reranker,
                )

                ce_reranker = get_cross_encoder_reranker()
                if ce_reranker is not None:
                    ce_docs = [
                        {"content": row.get("content", ""), **row}
                        for row in final_results
                    ]
                    ce_results = await ce_reranker.rerank(
                        query=query,
                        documents=ce_docs,
                        top_k=len(final_results),
                    )
                    if ce_results:
                        # Map CE scores back to original rows by content matching
                        ce_score_map: dict[str, float] = {}
                        for ce_row in ce_results:
                            content_key = str(ce_row.get("content", ""))[:200]
                            ce_score_map[content_key] = float(
                                ce_row.get("score") or 0.0
                            )
                        for row in final_results:
                            content_key = str(row.get("content", ""))[:200]
                            row["cross_encoder_score"] = ce_score_map.get(
                                content_key, 0.0
                            )
                        logger.debug(
                            "Cross-encoder scores attached",
                            scored_count=len(ce_score_map),
                            total_count=len(final_results),
                        )
            except Exception:  # noqa: BLE001
                logger.debug("Cross-encoder scoring failed, skipping CE weights")

        # ── Semantic cache: write back ──
        if final_results and query_embeddings:
            try:
                first_embedding = query_embeddings[0][1]
                await sem_cache.put(
                    cache_manager=cache_mgr,
                    kb_ids=list(kb_contexts.keys()),
                    query_embedding=first_embedding,
                    top_k=top_k,
                    results=final_results,
                )
            except Exception:  # noqa: BLE001
                logger.debug("Semantic cache write failed, non-critical")

        return Result.ok(final_results)

    @staticmethod
    def _build_keyword_candidates(query: str, candidate_limit: int = 32) -> builtins.list[str]:
        """Build coarse keywords for fallback retrieval without embeddings."""
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        expansion_terms = KnowledgeService._expand_query_terms(normalized_query)

        candidates: builtins.list[str] = []
        seen: set[str] = set()

        def add_candidate(token: str) -> None:
            value = token.strip().lower()
            if not value or value in seen:
                return
            if len(value) < 2:
                return
            if value in QUERY_STOPWORDS:
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
    def _expand_query_terms(normalized_query: str) -> builtins.list[str]:
        """Expand query with lightweight Chinese synonyms for recall gain."""
        terms: builtins.list[str] = []
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
    def _build_query_variants(query: str, max_variants: int = 3) -> builtins.list[str]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        variants: builtins.list[str] = []
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
        vector_results: builtins.list[dict[str, Any]],
        keyword_results: builtins.list[dict[str, Any]],
        top_k: int,
    ) -> builtins.list[dict[str, Any]]:
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

        fused_rows: builtins.list[dict[str, Any]] = []
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
        candidates: builtins.list[str],
        hint_terms: builtins.list[str] | None = None,
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
            fuzzy_bonus = KnowledgeService._keyword_fuzzy_bonus(
                normalized_content=normalized_content,
                candidates=candidates,
                hint_terms=hint_terms,
            )
            if fuzzy_bonus <= 0:
                return 0.0
            score += fuzzy_bonus

        coverage = matched_count / max(1, len(candidates))
        return score + coverage

    @staticmethod
    def _extract_fuzzy_terms(text: str, max_terms: int = 48) -> builtins.list[str]:
        terms: builtins.list[str] = []
        seen: set[str] = set()
        for token in SEARCH_TERM_RE.findall(text.lower()):
            term = token.strip()
            if len(term) < 2:
                continue
            if term in seen:
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= max_terms:
                break
            if re.fullmatch(r"[\u4e00-\u9fff]+", term) and len(term) >= 4:
                for ngram_size in (4, 3, 2):
                    if len(term) < ngram_size:
                        continue
                    for index in range(0, len(term) - ngram_size + 1):
                        ngram = term[index : index + ngram_size]
                        if ngram in seen:
                            continue
                        seen.add(ngram)
                        terms.append(ngram)
                        if len(terms) >= max_terms:
                            break
                    if len(terms) >= max_terms:
                        break
        return terms

    @staticmethod
    def _levenshtein_distance_limited(a: str, b: str, max_distance: int) -> int:
        if a == b:
            return 0
        if abs(len(a) - len(b)) > max_distance:
            return max_distance + 1
        if not a or not b:
            return max(len(a), len(b))

        previous = list(range(len(b) + 1))
        for i, ca in enumerate(a, start=1):
            current = [i]
            row_min = i
            for j, cb in enumerate(b, start=1):
                substitution_cost = 0 if ca == cb else 1
                distance = min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + substitution_cost,
                )
                current.append(distance)
                if distance < row_min:
                    row_min = distance
            if row_min > max_distance:
                return max_distance + 1
            previous = current
        return previous[-1]

    @staticmethod
    def _is_fuzzy_term_match(candidate: str, term: str) -> bool:
        if not candidate or not term:
            return False
        if candidate == term:
            return True
        if abs(len(candidate) - len(term)) > 1:
            return False

        max_distance = 1 if min(len(candidate), len(term)) <= 6 else 2
        distance = KnowledgeService._levenshtein_distance_limited(
            candidate,
            term,
            max_distance=max_distance,
        )
        if distance <= max_distance:
            return True

        ratio = SequenceMatcher(None, candidate, term).ratio()
        return ratio >= 0.82

    @staticmethod
    def _keyword_fuzzy_bonus(
        *,
        normalized_content: str,
        candidates: builtins.list[str],
        hint_terms: builtins.list[str] | None = None,
    ) -> float:
        fuzzy_terms = KnowledgeService._extract_fuzzy_terms(
            normalized_content, max_terms=24
        )
        if isinstance(hint_terms, list):
            for term in hint_terms:
                value = str(term).strip().lower()
                if len(value) >= 2:
                    fuzzy_terms.append(value)
        if not fuzzy_terms:
            return 0.0

        unique_terms: builtins.list[str] = []
        seen_terms: set[str] = set()
        for term in fuzzy_terms:
            if term in seen_terms:
                continue
            seen_terms.add(term)
            unique_terms.append(term)
            if len(unique_terms) >= 48:
                break

        bonus = 0.0
        matched = 0
        for candidate in candidates:
            token = str(candidate).strip().lower()
            if len(token) < 2:
                continue
            for term in unique_terms:
                if not KnowledgeService._is_fuzzy_term_match(token, term):
                    continue
                matched += 1
                if len(token) <= 4:
                    bonus += 1.35
                elif len(token) <= 8:
                    bonus += 1.0
                else:
                    bonus += 0.7
                break

        if matched <= 0:
            return 0.0

        return bonus + matched / max(1, len(candidates))

    async def _search_multiple_by_keywords(
        self,
        kb_ids: builtins.list[str],
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
        candidate_limit: int = 32,
        query_variants: builtins.list[str] | None = None,
        ready_document_ids_by_kb: dict[str, builtins.list[str]] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """BM25-based sparse retrieval — replaces brute-force collection scan.

        Uses a lazily-built in-memory BM25 index per ChromaDB collection.
        Scores are normalized to the same range as the old keyword fallback
        to stay compatible with `_fuse_retrieval_results()`.
        """
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        # Also run expanded keyword search for very short queries
        variants = [variant for variant in (query_variants or []) if variant.strip()]
        if not variants:
            variants = self._build_query_variants(normalized_query)

        # Build a combined query string for BM25: original + variant keywords
        expanded_query = normalized_query
        merged_candidates: builtins.list[str] = []
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

        # Augment BM25 query with extracted keywords for better coverage
        if merged_candidates:
            expanded_query = normalized_query + " " + " ".join(merged_candidates)

        vector_store = get_knowledge_vector_store()
        bm25_manager = get_bm25_index_manager()
        merged_results: builtins.list[dict[str, Any]] = []

        for kb_id in kb_ids:
            kb_result = await self.get_by_id(kb_id)
            if not kb_result.is_success:
                continue

            kb = self._require_value(kb_result)
            vector_collection = self._orm_str(kb, "vector_collection")
            knowledge_base_name = self._orm_str(kb, "name")
            ready_document_ids = None
            if isinstance(ready_document_ids_by_kb, dict):
                ready_document_ids = {
                    str(doc_id) for doc_id in ready_document_ids_by_kb.get(kb_id, [])
                }

            collection = vector_store._get_collection(vector_collection)
            if collection is None:
                continue

            bm25_hits: builtins.list[tuple[str, float]] = []
            max_bm25_score = 0.0

            # Ensure BM25 index is built and fresh (lazy + auto-rebuild on stale)
            try:
                bm25_manager.ensure_index(
                    collection_name=vector_collection,
                    get_all_chunks=lambda c=collection: c.get(
                        include=["documents", "metadatas"]
                    ),
                    get_chunk_count=lambda c=collection: c.count(),
                )
                bm25_hits = bm25_manager.search(
                    collection_name=vector_collection,
                    query=expanded_query,
                    top_k=max(top_k, 20),
                )
                if bm25_hits:
                    max_bm25_score = bm25_hits[0][1]
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "BM25 index build failed, falling back to legacy scan",
                    knowledge_base_id=kb_id,
                    reason=str(exc),
                )

            if bm25_hits and max_bm25_score > 0:
                # Fetch metadata for hit chunk IDs
                hit_ids = [chunk_id for chunk_id, _ in bm25_hits]
                id_to_meta = bm25_manager.get_metadatas(vector_collection, hit_ids)

                for chunk_id, bm25_score in bm25_hits:
                    metadata = id_to_meta.get(chunk_id, {})

                    # Apply metadata filter
                    if not self._metadata_matches(metadata, metadata_filter):
                        continue

                    # Apply ready-document filter
                    if ready_document_ids is not None:
                        document_id = str(metadata.get("document_id") or "").strip()
                        if not document_id or document_id not in ready_document_ids:
                            continue

                    # Normalize BM25 score to [0.45, 0.95] range for fusion compatibility
                    # Formula mirrors the old: min(0.95, 0.45 + raw_score * 0.07)
                    normalized_score = round(min(0.95, 0.45 + bm25_score * 0.07), 4)

                    # Get content from collection for the matched chunk
                    try:
                        chunk_data = collection.get(
                            ids=[chunk_id], include=["documents"]
                        )
                        content = ""
                        if isinstance(chunk_data, dict):
                            docs = chunk_data.get("documents", [])
                            if docs and isinstance(docs[0], str):
                                content = docs[0]
                    except Exception:  # noqa: BLE001
                        content = ""

                    if not content.strip():
                        continue

                    merged_results.append(
                        {
                            "content": content.strip(),
                            "score": normalized_score,
                            "source": metadata.get("document_title", "未知来源"),
                            "metadata": {
                                "document_id": metadata.get("document_id"),
                                "document_title": metadata.get("document_title"),
                                "chunk_index": metadata.get("chunk_index"),
                            },
                            "knowledge_base_id": kb_id,
                            "knowledge_base_name": knowledge_base_name,
                            "retrieval_mode": "keyword_fallback",
                        }
                    )
                continue

            try:
                raw_chunks = collection.get(include=["documents", "metadatas"])
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Keyword legacy scan failed after BM25 fallback",
                    knowledge_base_id=kb_id,
                    reason=str(exc),
                )
                continue

            raw_ids_value = raw_chunks.get("ids", []) if isinstance(raw_chunks, dict) else []
            raw_docs_value = raw_chunks.get("documents", []) if isinstance(raw_chunks, dict) else []
            raw_metas_value = raw_chunks.get("metadatas", []) if isinstance(raw_chunks, dict) else []
            raw_ids = raw_ids_value if isinstance(raw_ids_value, list) else []
            raw_docs = raw_docs_value if isinstance(raw_docs_value, list) else []
            raw_metas = raw_metas_value if isinstance(raw_metas_value, list) else []

            for index, content in enumerate(raw_docs):
                if not isinstance(content, str) or not content.strip():
                    continue

                metadata = dict(
                    raw_metas[index]
                    if index < len(raw_metas) and isinstance(raw_metas[index], dict)
                    else {}
                )

                if not self._metadata_matches(metadata, metadata_filter):
                    continue

                if ready_document_ids is not None:
                    document_id = str(metadata.get("document_id") or "").strip()
                    if not document_id or document_id not in ready_document_ids:
                        continue

                score = self._keyword_match_score(
                    normalized_content=content.strip().lower(),
                    normalized_query=normalized_query,
                    candidates=merged_candidates,
                )
                if score <= 0:
                    continue

                chunk_index = metadata.get("chunk_index")
                chunk_id = str(raw_ids[index]) if index < len(raw_ids) else ""
                normalized_score = round(min(0.95, 0.45 + score * 0.07), 4)
                merged_results.append(
                    {
                        "content": content.strip(),
                        "score": normalized_score,
                        "source": metadata.get("document_title", "未知来源"),
                        "metadata": {
                            "document_id": metadata.get("document_id"),
                            "document_title": metadata.get("document_title"),
                            "chunk_index": chunk_index,
                            "chunk_id": chunk_id,
                        },
                        "knowledge_base_id": kb_id,
                            "knowledge_base_name": knowledge_base_name,
                        "retrieval_mode": "keyword_fallback",
                    }
                )

        merged_results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
        return merged_results[: max(1, top_k)]

    # ========== Document Preview ==========

    async def get_document_chunks(
        self, kb_id: str, doc_id: str, page: int = 1, page_size: int = 10
    ) -> Result[tuple[builtins.list[dict[str, Any]], int]]:
        """
        Get document chunks for preview.

        Returns chunks stored in vector database.
        """
        doc_result = await self.get_document(kb_id, doc_id)
        if not doc_result.is_success:
            return Result.fail("[DOCUMENT_NOT_FOUND]")

        doc = self._require_value(doc_result)  # Validate document exists
        kb_result = await self.get_by_id(kb_id)
        if not kb_result.is_success:
            return Result.fail("[KNOWLEDGE_BASE_NOT_FOUND]")

        kb = self._require_value(kb_result)

        artifact_preview = self._get_document_chunks_from_artifact(doc, page, page_size)
        if artifact_preview is not None:
            return Result.ok(artifact_preview)

        # Get chunks from vector store
        vector_store = get_knowledge_vector_store()
        collection = vector_store._get_collection(self._orm_str(kb, "vector_collection"))

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

            result_documents = results.get("documents") if isinstance(results, dict) else []
            result_metadatas = results.get("metadatas") if isinstance(results, dict) else []
            documents = result_documents if isinstance(result_documents, list) else []
            metadatas = result_metadatas if isinstance(result_metadatas, list) else []

            if not documents:
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
            chunks: builtins.list[dict[str, Any]] = []
            for i, doc_content in enumerate(documents):
                metadata = (
                    metadatas[i]
                    if i < len(metadatas) and isinstance(metadatas[i], dict)
                    else {}
                )
                chunks.append(
                    {
                        "index": metadata.get("chunk_index", i),
                        "content": doc_content,
                        "metadata": {
                            "start_char": metadata.get("start_char"),
                            "end_char": metadata.get("end_char"),
                            "element_types": metadata.get("element_types"),
                            "source_mode": metadata.get("source_mode"),
                            "page": metadata.get("page"),
                            "page_end": metadata.get("page_end"),
                            "parser_version": metadata.get("parser_version"),
                            "warning_codes": metadata.get("warning_codes"),
                        },
                    }
                )

            # Sort by index
            chunks.sort(key=lambda x: str(x.get("index", "")))
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
    ) -> tuple[builtins.list[dict[str, Any]], int]:
        """Fallback preview by reading original source file and splitting into chunks."""
        try:
            processor = get_document_processor()
            parse_result = await processor._parse_document(  # noqa: SLF001
                self._orm_str(doc, "file_url"),
                self._orm_str(doc, "file_type"),
            )
            if not parse_result:
                return ([], 0)

            chunks = processor._build_chunks_from_parse_result(parse_result)  # noqa: SLF001
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

    def _get_document_chunks_from_artifact(
        self,
        doc: KnowledgeDocument,
        page: int,
        page_size: int,
    ) -> tuple[builtins.list[dict[str, Any]], int] | None:
        """Primary preview path based on the stored structured parse artifact."""
        try:
            storage = get_document_storage_service()
            artifact = storage.load_parse_artifact(self._orm_str(doc, "file_url"))
            if not isinstance(artifact, dict):
                return None

            raw_chunks = artifact.get("chunks")
            if not isinstance(raw_chunks, list) or not raw_chunks:
                return None

            formatted = [
                {
                    "index": chunk.get("index", index),
                    "content": chunk.get("content", ""),
                    "metadata": chunk.get("metadata", {}),
                }
                for index, chunk in enumerate(raw_chunks)
                if isinstance(chunk, dict)
            ]
            if not formatted:
                return None

            total = len(formatted)
            start = (page - 1) * page_size
            end = start + page_size
            return (formatted[start:end], total)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Artifact preview failed: {exc}")
            return None

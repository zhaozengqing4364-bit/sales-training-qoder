"""
Admin API for RAG Profile Management

CRUD endpoints for managing reusable RAG configuration profiles.
Requires admin authentication.

References:
- Plan: unified RAG configuration management
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.session import get_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/rag-profiles",
    tags=["admin-rag-profiles"],
    dependencies=[Depends(get_current_admin_user)],
)


# ── Pydantic Schemas ──


class ChunkingSettings(BaseModel):
    strategy: str = Field(
        default="element_boundary",
        pattern="^(element_boundary|fixed_size|parent_child)$",
    )
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class SemanticCacheSettings(BaseModel):
    enabled: bool = True
    similarity_threshold: float = Field(default=0.95, ge=0.90, le=0.99)
    ttl_seconds: int = Field(default=300, ge=60, le=3600)


class CrossEncoderSettings(BaseModel):
    backend: str | None = Field(
        default=None,
        description="local | cohere | null (disabled)",
    )
    model: str | None = None
    device: str | None = None
    api_key: str | None = Field(
        default=None,
        description="Only accepted on write, never returned in responses",
    )


class CrossEncoderSettingsSafe(BaseModel):
    """Cross-encoder settings without API key for responses."""

    backend: str | None = None
    model: str | None = None
    device: str | None = None
    has_api_key: bool = False


class CreateRagProfileRequest(BaseModel):
    name: str = Field(..., max_length=100, min_length=1)
    description: str | None = Field(None, max_length=500)
    is_system_default: bool = False
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    semantic_cache: SemanticCacheSettings = Field(default_factory=SemanticCacheSettings)
    cross_encoder: CrossEncoderSettings = Field(default_factory=CrossEncoderSettings)


class UpdateRagProfileRequest(BaseModel):
    name: str | None = Field(None, max_length=100, min_length=1)
    description: str | None = Field(None, max_length=500)
    is_system_default: bool | None = None
    chunking: ChunkingSettings | None = None
    semantic_cache: SemanticCacheSettings | None = None
    cross_encoder: CrossEncoderSettings | None = None


class RagProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    is_system_default: bool = False
    chunking: ChunkingSettings
    semantic_cache: SemanticCacheSettings
    cross_encoder: CrossEncoderSettingsSafe
    applied_kb_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssignRagProfileRequest(BaseModel):
    rag_profile_id: str | None = None


# ── Helpers ──


def _row_to_response(row: Any, applied_kb_count: int = 0) -> dict[str, Any]:
    """Convert a RagProfile DB row to API response dict."""
    has_api_key = bool(row.cross_encoder_api_key and row.cross_encoder_api_key.strip())
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "is_system_default": bool(row.is_system_default),
        "chunking": {
            "strategy": row.chunking_strategy,
            "chunk_size": row.chunk_size,
            "chunk_overlap": row.chunk_overlap,
        },
        "semantic_cache": {
            "enabled": bool(row.semantic_cache_enabled),
            "similarity_threshold": row.semantic_cache_similarity_threshold,
            "ttl_seconds": row.semantic_cache_ttl_seconds,
        },
        "cross_encoder": {
            "backend": row.cross_encoder_backend,
            "model": row.cross_encoder_model,
            "device": row.cross_encoder_device,
            "has_api_key": has_api_key,
        },
        "applied_kb_count": applied_kb_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _apply_update_to_row(row: Any, data: UpdateRagProfileRequest) -> None:
    """Apply update request fields to a DB row."""
    if data.name is not None:
        row.name = data.name
    if data.description is not None:
        row.description = data.description
    if data.chunking is not None:
        row.chunking_strategy = data.chunking.strategy
        row.chunk_size = data.chunking.chunk_size
        row.chunk_overlap = data.chunking.chunk_overlap
    if data.semantic_cache is not None:
        row.semantic_cache_enabled = 1 if data.semantic_cache.enabled else 0
        row.semantic_cache_similarity_threshold = (
            data.semantic_cache.similarity_threshold
        )
        row.semantic_cache_ttl_seconds = data.semantic_cache.ttl_seconds
    if data.cross_encoder is not None:
        row.cross_encoder_backend = data.cross_encoder.backend
        row.cross_encoder_model = data.cross_encoder.model
        row.cross_encoder_device = data.cross_encoder.device
        if data.cross_encoder.api_key is not None:
            row.cross_encoder_api_key = data.cross_encoder.api_key


async def _get_applied_kb_counts(db: AsyncSession) -> dict[str, int]:
    """Get count of KBs using each profile."""
    from common.knowledge.models import KnowledgeBase

    result = await db.execute(
        select(
            KnowledgeBase.rag_profile_id,
            func.count(KnowledgeBase.id),
        )
        .where(KnowledgeBase.rag_profile_id.isnot(None))
        .group_by(KnowledgeBase.rag_profile_id)
    )
    return {row[0]: row[1] for row in result.all()}


# ── Endpoints ──


@router.post("", response_model=dict)
async def create_rag_profile(
    request: CreateRagProfileRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new RAG configuration profile."""
    from common.knowledge.rag_profile_models import RagProfile

    # If setting as system default, unset existing default first
    if request.is_system_default:
        await db.execute(
            update(RagProfile)
            .where(RagProfile.is_system_default == 1)
            .values(is_system_default=0)
        )

    profile = RagProfile(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        is_system_default=1 if request.is_system_default else 0,
        chunking_strategy=request.chunking.strategy,
        chunk_size=request.chunking.chunk_size,
        chunk_overlap=request.chunking.chunk_overlap,
        semantic_cache_enabled=1 if request.semantic_cache.enabled else 0,
        semantic_cache_similarity_threshold=(
            request.semantic_cache.similarity_threshold
        ),
        semantic_cache_ttl_seconds=request.semantic_cache.ttl_seconds,
        cross_encoder_backend=request.cross_encoder.backend,
        cross_encoder_model=request.cross_encoder.model,
        cross_encoder_device=request.cross_encoder.device,
        cross_encoder_api_key=request.cross_encoder.api_key,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return {"success": True, "data": _row_to_response(profile, 0)}


@router.get("", response_model=dict)
async def list_rag_profiles(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all RAG configuration profiles."""
    from common.knowledge.rag_profile_models import RagProfile

    result = await db.execute(
        select(RagProfile).order_by(
            RagProfile.is_system_default.desc(),
            RagProfile.created_at.asc(),
        )
    )
    profiles = result.scalars().all()
    kb_counts = await _get_applied_kb_counts(db)

    return {
        "success": True,
        "data": [_row_to_response(p, kb_counts.get(p.id, 0)) for p in profiles],
    }


@router.get("/{profile_id}", response_model=dict)
async def get_rag_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single RAG configuration profile."""
    from common.knowledge.rag_profile_models import RagProfile

    result = await db.execute(select(RagProfile).where(RagProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="RAG profile not found")

    kb_counts = await _get_applied_kb_counts(db)
    return {
        "success": True,
        "data": _row_to_response(profile, kb_counts.get(profile.id, 0)),
    }


@router.put("/{profile_id}", response_model=dict)
async def update_rag_profile(
    profile_id: str,
    request: UpdateRagProfileRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update a RAG configuration profile."""
    from common.knowledge.rag_profile_models import RagProfile

    result = await db.execute(select(RagProfile).where(RagProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="RAG profile not found")

    # Handle system default toggle
    if request.is_system_default and not profile.is_system_default:
        await db.execute(
            update(RagProfile)
            .where(RagProfile.is_system_default == 1)
            .values(is_system_default=0)
        )

    _apply_update_to_row(profile, request)
    await db.commit()
    await db.refresh(profile)

    kb_counts = await _get_applied_kb_counts(db)
    return {
        "success": True,
        "data": _row_to_response(profile, kb_counts.get(profile.id, 0)),
    }


@router.delete("/{profile_id}", response_model=dict)
async def delete_rag_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a RAG configuration profile (cannot delete if applied to KBs)."""
    from common.knowledge.models import KnowledgeBase
    from common.knowledge.rag_profile_models import RagProfile

    result = await db.execute(select(RagProfile).where(RagProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="RAG profile not found")

    if profile.is_system_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the system default profile",
        )

    # Check if any KBs use this profile
    kb_count_result = await db.execute(
        select(func.count(KnowledgeBase.id)).where(
            KnowledgeBase.rag_profile_id == profile_id
        )
    )
    kb_count = kb_count_result.scalar() or 0
    if kb_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {kb_count} knowledge base(s) use this profile. "
            "Reassign them first.",
        )

    await db.delete(profile)
    await db.commit()
    return {"success": True, "message": "Profile deleted"}


@router.post("/{profile_id}/set-default", response_model=dict)
async def set_default_rag_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Set a profile as the system default."""
    from common.knowledge.rag_profile_models import RagProfile

    result = await db.execute(select(RagProfile).where(RagProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="RAG profile not found")

    # Unset current default
    await db.execute(
        update(RagProfile)
        .where(RagProfile.is_system_default == 1)
        .values(is_system_default=0)
    )
    profile.is_system_default = 1
    await db.commit()
    await db.refresh(profile)

    kb_counts = await _get_applied_kb_counts(db)
    return {
        "success": True,
        "data": _row_to_response(profile, kb_counts.get(profile.id, 0)),
    }


@router.get("/{profile_id}/knowledge-bases", response_model=dict)
async def get_profile_knowledge_bases(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List knowledge bases using this profile."""
    from common.knowledge.models import KnowledgeBase
    from common.knowledge.rag_profile_models import RagProfile

    # Verify profile exists
    result = await db.execute(select(RagProfile).where(RagProfile.id == profile_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="RAG profile not found")

    kb_result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.rag_profile_id == profile_id)
        .order_by(KnowledgeBase.name)
    )
    kbs = kb_result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": kb.id,
                "name": kb.name,
                "category": kb.category,
                "document_count": kb.document_count,
                "status": kb.status,
            }
            for kb in kbs
        ],
    }

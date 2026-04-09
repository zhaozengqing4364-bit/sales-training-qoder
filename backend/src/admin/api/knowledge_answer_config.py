"""Knowledge answer configuration CRUD + debug trigger admin API."""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.models import (
    KnowledgeAnswerabilityProfile,
    KnowledgeChunkingPreset,
    KnowledgeConfigVersion,
    KnowledgeEntityAlias,
    KnowledgeIntentRule,
    KnowledgeQueryProfile,
    KnowledgeRankingProfile,
    User,
)
from common.db.session import get_db
from common.monitoring.logger import get_trace_id

router = APIRouter(
    prefix="/knowledge-answer",
    tags=["admin-knowledge-answer"],
    dependencies=[Depends(get_current_admin_user)],
)


# ─── Response helpers ───────────────────────────────────────


def success_response(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": get_trace_id()}


def error_response(
    error_code: str,
    *,
    status_code: int,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_code,
            "message": message or error_code,
            "trace_id": get_trace_id(),
        },
    )


# ═══════════════════════════════════════════════════════════
# Pydantic models — existing config read endpoints
# ═══════════════════════════════════════════════════════════


class KnowledgeAnswerActiveVersion(BaseModel):
    id: str
    version_name: str
    status: str
    enabled: bool
    updated_at: datetime


class KnowledgeAnswerConfigSummary(BaseModel):
    query_profile_count: int = 0
    intent_rule_count: int = 0
    entity_alias_count: int = 0
    ranking_profile_count: int = 0
    answerability_profile_count: int = 0


class KnowledgeAnswerSelectedProfiles(BaseModel):
    query_profile_keys: list[str] = Field(default_factory=list)
    ranking_profile_keys: list[str] = Field(default_factory=list)
    answerability_profile_keys: list[str] = Field(default_factory=list)


class KnowledgeAnswerAdminConfigResponse(BaseModel):
    active_version: KnowledgeAnswerActiveVersion | None = None
    profile_source: str | None = None
    summary: KnowledgeAnswerConfigSummary = Field(
        default_factory=KnowledgeAnswerConfigSummary
    )
    selected_profiles: KnowledgeAnswerSelectedProfiles = Field(
        default_factory=KnowledgeAnswerSelectedProfiles
    )


class KnowledgeAnswerConfigOption(BaseModel):
    id: str
    version_name: str
    status: str
    enabled: bool
    updated_at: datetime


class KnowledgeAnswerConfigOptionsResponse(BaseModel):
    versions: list[KnowledgeAnswerConfigOption] = Field(default_factory=list)


class KnowledgeAnswerConfigUpdateRequest(BaseModel):
    config_version_id: str


# ═══════════════════════════════════════════════════════════
# Pydantic models — config version CRUD
# ═══════════════════════════════════════════════════════════


class ConfigVersionCreateRequest(BaseModel):
    version_name: str = Field(..., min_length=1, max_length=120)
    notes: str | None = None
    enabled: bool = True


class ConfigVersionUpdateRequest(BaseModel):
    version_name: str | None = Field(None, min_length=1, max_length=120)
    status: str | None = None
    notes: str | None = None
    enabled: bool | None = None


class ConfigVersionResponse(BaseModel):
    id: str
    version_name: str
    status: str
    notes: str | None
    enabled: bool
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime


class ConfigVersionListResponse(BaseModel):
    items: list[ConfigVersionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ═══════════════════════════════════════════════════════════
# Pydantic models — profile CRUD
# ═══════════════════════════════════════════════════════════


# --- Query Profile ---
class QueryProfileCreateRequest(BaseModel):
    profile_key: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    rewrite_strategy: str = Field(..., min_length=1)
    max_rewrite_queries: int = 1
    stop_after_first_success: bool = False
    enabled: bool = True


class QueryProfileUpdateRequest(BaseModel):
    profile_key: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    rewrite_strategy: str | None = Field(None, min_length=1)
    max_rewrite_queries: int | None = None
    stop_after_first_success: bool | None = None
    enabled: bool | None = None


class QueryProfileResponse(BaseModel):
    id: str
    config_version_id: str
    profile_key: str
    description: str | None
    rewrite_strategy: str
    max_rewrite_queries: int
    stop_after_first_success: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- Intent Rule ---
class IntentRuleCreateRequest(BaseModel):
    intent_key: str = Field(..., min_length=1, max_length=100)
    priority: int = 100
    match_type: str = Field(..., min_length=1)
    pattern: str = Field(..., min_length=1)
    profile_key: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True


class IntentRuleUpdateRequest(BaseModel):
    intent_key: str | None = Field(None, min_length=1, max_length=100)
    priority: int | None = None
    match_type: str | None = Field(None, min_length=1)
    pattern: str | None = None
    profile_key: str | None = Field(None, min_length=1, max_length=100)
    enabled: bool | None = None


class IntentRuleResponse(BaseModel):
    id: str
    config_version_id: str
    intent_key: str
    priority: int
    match_type: str
    pattern: str
    profile_key: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- Entity Alias ---
class EntityAliasCreateRequest(BaseModel):
    canonical_entity: str = Field(..., min_length=1, max_length=255)
    alias: str = Field(..., min_length=1, max_length=255)
    entity_type: str = Field(..., min_length=1, max_length=50)
    confidence: float = 1.0
    enabled: bool = True


class EntityAliasUpdateRequest(BaseModel):
    canonical_entity: str | None = Field(None, min_length=1, max_length=255)
    alias: str | None = Field(None, min_length=1, max_length=255)
    entity_type: str | None = Field(None, min_length=1, max_length=50)
    confidence: float | None = None
    enabled: bool | None = None


class EntityAliasResponse(BaseModel):
    id: str
    config_version_id: str
    canonical_entity: str
    alias: str
    entity_type: str
    confidence: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- Ranking Profile ---
class RankingProfileCreateRequest(BaseModel):
    profile_key: str = Field(..., min_length=1, max_length=100)
    title_exact_boost: float = 0.0
    entity_match_boost: float = 0.0
    doc_type_weights: dict[str, float] = Field(default_factory=dict)
    section_weights: dict[str, float] = Field(default_factory=dict)
    min_pass_score: float = 0.0
    min_pass_score_keyword: float = 0.0
    # Unified scoring weights
    base_weight: float = 0.50
    coverage_weight: float = 0.20
    phrase_bonus: float = 0.15
    title_bonus_max: float = 0.10
    ratio_bonus_max: float = 0.05
    cross_encoder_weight: float = 0.0
    diversity_penalty: float = 0.12
    enabled: bool = True


class RankingProfileUpdateRequest(BaseModel):
    profile_key: str | None = Field(None, min_length=1, max_length=100)
    title_exact_boost: float | None = None
    entity_match_boost: float | None = None
    doc_type_weights: dict[str, float] | None = None
    section_weights: dict[str, float] | None = None
    min_pass_score: float | None = None
    min_pass_score_keyword: float | None = None
    # Unified scoring weights
    base_weight: float | None = None
    coverage_weight: float | None = None
    phrase_bonus: float | None = None
    title_bonus_max: float | None = None
    ratio_bonus_max: float | None = None
    cross_encoder_weight: float | None = None
    diversity_penalty: float | None = None
    enabled: bool | None = None


class RankingProfileResponse(BaseModel):
    id: str
    config_version_id: str
    profile_key: str
    title_exact_boost: float
    entity_match_boost: float
    doc_type_weights: dict[str, float]
    section_weights: dict[str, float]
    min_pass_score: float
    min_pass_score_keyword: float
    # Unified scoring weights
    base_weight: float = 0.50
    coverage_weight: float = 0.20
    phrase_bonus: float = 0.15
    title_bonus_max: float = 0.10
    ratio_bonus_max: float = 0.05
    cross_encoder_weight: float = 0.0
    diversity_penalty: float = 0.12
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- Answerability Profile ---
class AnswerabilityProfileCreateRequest(BaseModel):
    profile_key: str = Field(..., min_length=1, max_length=100)
    required_slots: list[str] = Field(default_factory=list)
    optional_slots: list[str] = Field(default_factory=list)
    sufficient_threshold: float = 1.0
    partial_threshold: float = 0.0
    enabled: bool = True


class AnswerabilityProfileUpdateRequest(BaseModel):
    profile_key: str | None = Field(None, min_length=1, max_length=100)
    required_slots: list[str] | None = None
    optional_slots: list[str] | None = None
    sufficient_threshold: float | None = None
    partial_threshold: float | None = None
    enabled: bool | None = None


class AnswerabilityProfileResponse(BaseModel):
    id: str
    config_version_id: str
    profile_key: str
    required_slots: list[str]
    optional_slots: list[str]
    sufficient_threshold: float
    partial_threshold: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- Chunking Preset ---
class ChunkingPresetCreateRequest(BaseModel):
    profile_key: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    chunking_strategy: str = "element_boundary"
    chunk_size: int = Field(500, ge=50, le=10000)
    chunk_overlap: int = Field(50, ge=0, le=2000)
    is_default: bool = False
    enabled: bool = True


class ChunkingPresetUpdateRequest(BaseModel):
    profile_key: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    chunking_strategy: str | None = None
    chunk_size: int | None = Field(None, ge=50, le=10000)
    chunk_overlap: int | None = Field(None, ge=0, le=2000)
    is_default: bool | None = None
    enabled: bool | None = None


class ChunkingPresetResponse(BaseModel):
    id: str
    config_version_id: str
    profile_key: str
    description: str | None
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    is_default: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- Debug Trigger ---
class DebugTriggerRequest(BaseModel):
    query: str = Field(..., min_length=1)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    runtime_options: dict[str, Any] = Field(default_factory=dict)
    strict_kb_mode: bool = False


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


async def _ensure_version(db: AsyncSession, version_id: str) -> KnowledgeConfigVersion:
    version = await db.get(KnowledgeConfigVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="[CONFIG_VERSION_NOT_FOUND]")
    return version


def _config_version_to_response(v: KnowledgeConfigVersion) -> ConfigVersionResponse:
    return ConfigVersionResponse(
        id=str(v.id),
        version_name=v.version_name,
        status=v.status,
        notes=v.notes,
        enabled=v.enabled,
        created_by=v.created_by,
        updated_by=v.updated_by,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


async def _archive_current_active(db: AsyncSession, user_id: str) -> None:
    stmt = select(KnowledgeConfigVersion).where(
        KnowledgeConfigVersion.status == "active",
        KnowledgeConfigVersion.enabled.is_(True),
    )
    result = await db.execute(stmt)
    for v in result.scalars().all():
        v.status = "archived"
        v.updated_by = user_id


# ═══════════════════════════════════════════════════════════
# Existing config read endpoints (unchanged)
# ═══════════════════════════════════════════════════════════


@router.get("/config")
async def get_admin_knowledge_answer_config(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from common.knowledge_engine.config_repo import KnowledgeAnswerConfigRepository

    active_version = await _get_active_version(db)
    snapshot = await db.run_sync(
        lambda sync_session: KnowledgeAnswerConfigRepository(
            sync_session
        ).get_active_config()
    )

    payload = KnowledgeAnswerAdminConfigResponse(
        active_version=(
            KnowledgeAnswerActiveVersion(
                id=str(active_version.id),
                version_name=str(active_version.version_name),
                status=str(active_version.status),
                enabled=bool(active_version.enabled),
                updated_at=active_version.updated_at,
            )
            if active_version is not None
            else None
        ),
        profile_source=(snapshot.profile_source if snapshot is not None else None),
        summary=KnowledgeAnswerConfigSummary(
            query_profile_count=len(snapshot.query_profiles) if snapshot else 0,
            intent_rule_count=len(snapshot.intent_rules) if snapshot else 0,
            entity_alias_count=len(snapshot.entity_aliases) if snapshot else 0,
            ranking_profile_count=len(snapshot.ranking_profiles) if snapshot else 0,
            answerability_profile_count=len(snapshot.answerability_profiles)
            if snapshot
            else 0,
        ),
        selected_profiles=KnowledgeAnswerSelectedProfiles(
            query_profile_keys=sorted(snapshot.query_profiles.keys())
            if snapshot
            else [],
            ranking_profile_keys=sorted(snapshot.ranking_profiles.keys())
            if snapshot
            else [],
            answerability_profile_keys=sorted(snapshot.answerability_profiles.keys())
            if snapshot
            else [],
        ),
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/config/options")
async def get_admin_knowledge_answer_config_options(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = list(
        (
            await db.execute(
                select(KnowledgeConfigVersion)
                .where(KnowledgeConfigVersion.enabled.is_(True))
                .order_by(
                    KnowledgeConfigVersion.updated_at.desc(),
                    KnowledgeConfigVersion.created_at.desc(),
                )
            )
        ).scalars()
    )
    payload = KnowledgeAnswerConfigOptionsResponse(
        versions=[
            KnowledgeAnswerConfigOption(
                id=str(row.id),
                version_name=str(row.version_name),
                status=str(row.status),
                enabled=bool(row.enabled),
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )
    return success_response(payload.model_dump(mode="json"))


@router.put("/config", response_model=None)
async def update_admin_knowledge_answer_config(
    request: KnowledgeAnswerConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    target = await db.get(KnowledgeConfigVersion, request.config_version_id)
    if target is None or not target.enabled:
        return error_response(
            "[KNOWLEDGE_CONFIG_NOT_FOUND]",
            status_code=404,
            message="Knowledge config version not found",
        )

    current_active = await _get_active_version(db)
    if current_active is not None and str(current_active.id) != str(target.id):
        current_active.status = "archived"
        current_active.updated_by = str(current_user.user_id)

    target.status = "active"
    target.updated_by = str(current_user.user_id)
    await db.commit()

    return await get_admin_knowledge_answer_config(db=db)


async def _get_active_version(db: AsyncSession) -> KnowledgeConfigVersion | None:
    statement = (
        select(KnowledgeConfigVersion)
        .where(
            KnowledgeConfigVersion.status == "active",
            KnowledgeConfigVersion.enabled.is_(True),
        )
        .order_by(
            KnowledgeConfigVersion.updated_at.desc(),
            KnowledgeConfigVersion.created_at.desc(),
            KnowledgeConfigVersion.id.desc(),
        )
        .limit(1)
    )
    return (await db.execute(statement)).scalar_one_or_none()


# ═══════════════════════════════════════════════════════════
# Config Version CRUD
# ═══════════════════════════════════════════════════════════


@router.post("/versions")
async def create_config_version(
    request: ConfigVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    version = KnowledgeConfigVersion(
        version_name=request.version_name,
        status="draft",
        notes=request.notes,
        enabled=request.enabled,
        created_by=str(current_user.user_id),
        updated_by=str(current_user.user_id),
    )
    db.add(version)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response(
            "[VERSION_NAME_DUPLICATE]",
            status_code=409,
            message=f"Version name '{request.version_name}' already exists",
        )
    await db.commit()
    await db.refresh(version)
    return success_response(
        _config_version_to_response(version).model_dump(mode="json")
    )


@router.get("/versions")
async def list_config_versions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    query = select(KnowledgeConfigVersion)
    count_query = select(func.count()).select_from(KnowledgeConfigVersion)
    if status:
        query = query.where(KnowledgeConfigVersion.status == status)
        count_query = count_query.where(KnowledgeConfigVersion.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    rows = list(
        (
            await db.execute(
                query.order_by(KnowledgeConfigVersion.updated_at.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).scalars()
    )
    has_more = offset + page_size < total
    return success_response(
        ConfigVersionListResponse(
            items=[_config_version_to_response(v) for v in rows],
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        ).model_dump(mode="json")
    )


@router.get("/versions/{version_id}")
async def get_config_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    version = await _ensure_version(db, version_id)
    return success_response(
        _config_version_to_response(version).model_dump(mode="json")
    )


@router.put("/versions/{version_id}")
async def update_config_version(
    version_id: str,
    request: ConfigVersionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    version = await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)

    if request.version_name is not None:
        version.version_name = request.version_name
    if request.notes is not None:
        version.notes = request.notes
    if request.enabled is not None:
        version.enabled = request.enabled
    if request.status == "active":
        await _archive_current_active(db, user_id)
        version.status = "active"
    elif request.status is not None:
        version.status = request.status
    version.updated_by = user_id

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response(
            "[VERSION_NAME_DUPLICATE]",
            status_code=409,
            message="Version name already exists",
        )
    await db.commit()
    await db.refresh(version)
    return success_response(
        _config_version_to_response(version).model_dump(mode="json")
    )


@router.delete("/versions/{version_id}")
async def delete_config_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    version = await _ensure_version(db, version_id)
    await db.delete(version)
    await db.commit()
    return success_response({"deleted": True, "id": version_id})


# ═══════════════════════════════════════════════════════════
# Profile CRUD — Query Profiles
# ═══════════════════════════════════════════════════════════


@router.get("/versions/{version_id}/query-profiles")
async def list_query_profiles(
    version_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    rows = list(
        (
            await db.execute(
                select(KnowledgeQueryProfile)
                .where(KnowledgeQueryProfile.config_version_id == version_id)
                .order_by(KnowledgeQueryProfile.profile_key)
            )
        ).scalars()
    )
    items = [
        QueryProfileResponse(
            id=str(r.id),
            config_version_id=str(r.config_version_id),
            profile_key=r.profile_key,
            description=r.description,
            rewrite_strategy=r.rewrite_strategy,
            max_rewrite_queries=r.max_rewrite_queries,
            stop_after_first_success=r.stop_after_first_success,
            enabled=r.enabled,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return success_response(
        {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.post("/versions/{version_id}/query-profiles")
async def create_query_profile(
    version_id: str,
    request: QueryProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)
    row = KnowledgeQueryProfile(
        config_version_id=version_id,
        profile_key=request.profile_key,
        description=request.description,
        rewrite_strategy=request.rewrite_strategy,
        max_rewrite_queries=request.max_rewrite_queries,
        stop_after_first_success=request.stop_after_first_success,
        enabled=request.enabled,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response(
            "[PROFILE_KEY_DUPLICATE]",
            status_code=409,
            message=f"Profile key '{request.profile_key}' already exists in this version",
        )
    await db.commit()
    await db.refresh(row)
    resp = QueryProfileResponse(
        id=str(row.id),
        config_version_id=str(row.config_version_id),
        profile_key=row.profile_key,
        description=row.description,
        rewrite_strategy=row.rewrite_strategy,
        max_rewrite_queries=row.max_rewrite_queries,
        stop_after_first_success=row.stop_after_first_success,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_response(resp.model_dump(mode="json"))


@router.put("/versions/{version_id}/query-profiles/{profile_id}")
async def update_query_profile(
    version_id: str,
    profile_id: str,
    request: QueryProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeQueryProfile, profile_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PROFILE_NOT_FOUND]", status_code=404)
    user_id = str(current_user.user_id)
    for field, val in [
        ("profile_key", request.profile_key),
        ("description", request.description),
        ("rewrite_strategy", request.rewrite_strategy),
        ("max_rewrite_queries", request.max_rewrite_queries),
        ("stop_after_first_success", request.stop_after_first_success),
        ("enabled", request.enabled),
    ]:
        if val is not None:
            setattr(row, field, val)
    row.updated_by = user_id
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PROFILE_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    resp = QueryProfileResponse(
        id=str(row.id),
        config_version_id=str(row.config_version_id),
        profile_key=row.profile_key,
        description=row.description,
        rewrite_strategy=row.rewrite_strategy,
        max_rewrite_queries=row.max_rewrite_queries,
        stop_after_first_success=row.stop_after_first_success,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_response(resp.model_dump(mode="json"))


@router.delete("/versions/{version_id}/query-profiles/{profile_id}")
async def delete_query_profile(
    version_id: str,
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeQueryProfile, profile_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PROFILE_NOT_FOUND]", status_code=404)
    await db.delete(row)
    await db.commit()
    return success_response({"deleted": True, "id": profile_id})


# ═══════════════════════════════════════════════════════════
# Profile CRUD — Intent Rules
# ═══════════════════════════════════════════════════════════


@router.get("/versions/{version_id}/intent-rules")
async def list_intent_rules(
    version_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    rows = list(
        (
            await db.execute(
                select(KnowledgeIntentRule)
                .where(KnowledgeIntentRule.config_version_id == version_id)
                .order_by(KnowledgeIntentRule.priority, KnowledgeIntentRule.intent_key)
            )
        ).scalars()
    )
    items = [
        IntentRuleResponse(
            id=str(r.id),
            config_version_id=str(r.config_version_id),
            intent_key=r.intent_key,
            priority=r.priority,
            match_type=r.match_type,
            pattern=r.pattern,
            profile_key=r.profile_key,
            enabled=r.enabled,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return success_response(
        {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.post("/versions/{version_id}/intent-rules")
async def create_intent_rule(
    version_id: str,
    request: IntentRuleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)
    row = KnowledgeIntentRule(
        config_version_id=version_id,
        intent_key=request.intent_key,
        priority=request.priority,
        match_type=request.match_type,
        pattern=request.pattern,
        profile_key=request.profile_key,
        enabled=request.enabled,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    resp = IntentRuleResponse(
        id=str(row.id),
        config_version_id=str(row.config_version_id),
        intent_key=row.intent_key,
        priority=row.priority,
        match_type=row.match_type,
        pattern=row.pattern,
        profile_key=row.profile_key,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_response(resp.model_dump(mode="json"))


@router.put("/versions/{version_id}/intent-rules/{rule_id}")
async def update_intent_rule(
    version_id: str,
    rule_id: str,
    request: IntentRuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeIntentRule, rule_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[RULE_NOT_FOUND]", status_code=404)
    user_id = str(current_user.user_id)
    for field, val in [
        ("intent_key", request.intent_key),
        ("priority", request.priority),
        ("match_type", request.match_type),
        ("pattern", request.pattern),
        ("profile_key", request.profile_key),
        ("enabled", request.enabled),
    ]:
        if val is not None:
            setattr(row, field, val)
    row.updated_by = user_id
    await db.commit()
    await db.refresh(row)
    resp = IntentRuleResponse(
        id=str(row.id),
        config_version_id=str(row.config_version_id),
        intent_key=row.intent_key,
        priority=row.priority,
        match_type=row.match_type,
        pattern=row.pattern,
        profile_key=row.profile_key,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_response(resp.model_dump(mode="json"))


@router.delete("/versions/{version_id}/intent-rules/{rule_id}")
async def delete_intent_rule(
    version_id: str, rule_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeIntentRule, rule_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[RULE_NOT_FOUND]", status_code=404)
    await db.delete(row)
    await db.commit()
    return success_response({"deleted": True, "id": rule_id})


# ═══════════════════════════════════════════════════════════
# Profile CRUD — Entity Aliases
# ═══════════════════════════════════════════════════════════


@router.get("/versions/{version_id}/entity-aliases")
async def list_entity_aliases(
    version_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    rows = list(
        (
            await db.execute(
                select(KnowledgeEntityAlias)
                .where(KnowledgeEntityAlias.config_version_id == version_id)
                .order_by(KnowledgeEntityAlias.alias)
            )
        ).scalars()
    )
    items = [
        EntityAliasResponse(
            id=str(r.id),
            config_version_id=str(r.config_version_id),
            canonical_entity=r.canonical_entity,
            alias=r.alias,
            entity_type=r.entity_type,
            confidence=r.confidence,
            enabled=r.enabled,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return success_response(
        {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.post("/versions/{version_id}/entity-aliases")
async def create_entity_alias(
    version_id: str,
    request: EntityAliasCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)
    row = KnowledgeEntityAlias(
        config_version_id=version_id,
        canonical_entity=request.canonical_entity,
        alias=request.alias,
        entity_type=request.entity_type,
        confidence=request.confidence,
        enabled=request.enabled,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response(
            "[ALIAS_DUPLICATE]",
            status_code=409,
            message=f"Alias '{request.alias}' already exists in this version",
        )
    await db.commit()
    await db.refresh(row)
    resp = EntityAliasResponse(
        id=str(row.id),
        config_version_id=str(row.config_version_id),
        canonical_entity=row.canonical_entity,
        alias=row.alias,
        entity_type=row.entity_type,
        confidence=row.confidence,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_response(resp.model_dump(mode="json"))


@router.put("/versions/{version_id}/entity-aliases/{alias_id}")
async def update_entity_alias(
    version_id: str,
    alias_id: str,
    request: EntityAliasUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeEntityAlias, alias_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[ALIAS_NOT_FOUND]", status_code=404)
    user_id = str(current_user.user_id)
    for field, val in [
        ("canonical_entity", request.canonical_entity),
        ("alias", request.alias),
        ("entity_type", request.entity_type),
        ("confidence", request.confidence),
        ("enabled", request.enabled),
    ]:
        if val is not None:
            setattr(row, field, val)
    row.updated_by = user_id
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[ALIAS_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    resp = EntityAliasResponse(
        id=str(row.id),
        config_version_id=str(row.config_version_id),
        canonical_entity=row.canonical_entity,
        alias=row.alias,
        entity_type=row.entity_type,
        confidence=row.confidence,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return success_response(resp.model_dump(mode="json"))


@router.delete("/versions/{version_id}/entity-aliases/{alias_id}")
async def delete_entity_alias(
    version_id: str, alias_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeEntityAlias, alias_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[ALIAS_NOT_FOUND]", status_code=404)
    await db.delete(row)
    await db.commit()
    return success_response({"deleted": True, "id": alias_id})


# ═══════════════════════════════════════════════════════════
# Profile CRUD — Ranking Profiles
# ═══════════════════════════════════════════════════════════


def _ranking_to_response(r: KnowledgeRankingProfile) -> RankingProfileResponse:
    return RankingProfileResponse(
        id=str(r.id),
        config_version_id=str(r.config_version_id),
        profile_key=r.profile_key,
        title_exact_boost=r.title_exact_boost,
        entity_match_boost=r.entity_match_boost,
        doc_type_weights=r.doc_type_weights_json or {},
        section_weights=r.section_weights_json or {},
        min_pass_score=r.min_pass_score,
        min_pass_score_keyword=r.min_pass_score_keyword,
        base_weight=getattr(r, "base_weight", 0.50),
        coverage_weight=getattr(r, "coverage_weight", 0.20),
        phrase_bonus=getattr(r, "phrase_bonus", 0.15),
        title_bonus_max=getattr(r, "title_bonus_max", 0.10),
        ratio_bonus_max=getattr(r, "ratio_bonus_max", 0.05),
        cross_encoder_weight=getattr(r, "cross_encoder_weight", 0.0),
        diversity_penalty=getattr(r, "diversity_penalty", 0.12),
        enabled=r.enabled,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("/versions/{version_id}/ranking-profiles")
async def list_ranking_profiles(
    version_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    rows = list(
        (
            await db.execute(
                select(KnowledgeRankingProfile)
                .where(KnowledgeRankingProfile.config_version_id == version_id)
                .order_by(KnowledgeRankingProfile.profile_key)
            )
        ).scalars()
    )
    items = [_ranking_to_response(r) for r in rows]
    return success_response(
        {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.post("/versions/{version_id}/ranking-profiles")
async def create_ranking_profile(
    version_id: str,
    request: RankingProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)
    row = KnowledgeRankingProfile(
        config_version_id=version_id,
        profile_key=request.profile_key,
        title_exact_boost=request.title_exact_boost,
        entity_match_boost=request.entity_match_boost,
        doc_type_weights_json=request.doc_type_weights,
        section_weights_json=request.section_weights,
        min_pass_score=request.min_pass_score,
        min_pass_score_keyword=request.min_pass_score_keyword,
        base_weight=request.base_weight,
        coverage_weight=request.coverage_weight,
        phrase_bonus=request.phrase_bonus,
        title_bonus_max=request.title_bonus_max,
        ratio_bonus_max=request.ratio_bonus_max,
        cross_encoder_weight=request.cross_encoder_weight,
        diversity_penalty=request.diversity_penalty,
        enabled=request.enabled,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PROFILE_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    return success_response(_ranking_to_response(row).model_dump(mode="json"))


@router.put("/versions/{version_id}/ranking-profiles/{profile_id}")
async def update_ranking_profile(
    version_id: str,
    profile_id: str,
    request: RankingProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeRankingProfile, profile_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PROFILE_NOT_FOUND]", status_code=404)
    user_id = str(current_user.user_id)
    if request.profile_key is not None:
        row.profile_key = request.profile_key
    if request.title_exact_boost is not None:
        row.title_exact_boost = request.title_exact_boost
    if request.entity_match_boost is not None:
        row.entity_match_boost = request.entity_match_boost
    if request.doc_type_weights is not None:
        row.doc_type_weights_json = request.doc_type_weights
    if request.section_weights is not None:
        row.section_weights_json = request.section_weights
    if request.min_pass_score is not None:
        row.min_pass_score = request.min_pass_score
    if request.min_pass_score_keyword is not None:
        row.min_pass_score_keyword = request.min_pass_score_keyword
    if request.enabled is not None:
        row.enabled = request.enabled
    # Unified scoring weights
    if request.base_weight is not None:
        row.base_weight = request.base_weight
    if request.coverage_weight is not None:
        row.coverage_weight = request.coverage_weight
    if request.phrase_bonus is not None:
        row.phrase_bonus = request.phrase_bonus
    if request.title_bonus_max is not None:
        row.title_bonus_max = request.title_bonus_max
    if request.ratio_bonus_max is not None:
        row.ratio_bonus_max = request.ratio_bonus_max
    if request.cross_encoder_weight is not None:
        row.cross_encoder_weight = request.cross_encoder_weight
    if request.diversity_penalty is not None:
        row.diversity_penalty = request.diversity_penalty
    row.updated_by = user_id
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PROFILE_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    return success_response(_ranking_to_response(row).model_dump(mode="json"))


@router.delete("/versions/{version_id}/ranking-profiles/{profile_id}")
async def delete_ranking_profile(
    version_id: str, profile_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeRankingProfile, profile_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PROFILE_NOT_FOUND]", status_code=404)
    await db.delete(row)
    await db.commit()
    return success_response({"deleted": True, "id": profile_id})


# ═══════════════════════════════════════════════════════════
# Profile CRUD — Answerability Profiles
# ═══════════════════════════════════════════════════════════


def _answerability_to_response(
    r: KnowledgeAnswerabilityProfile,
) -> AnswerabilityProfileResponse:
    return AnswerabilityProfileResponse(
        id=str(r.id),
        config_version_id=str(r.config_version_id),
        profile_key=r.profile_key,
        required_slots=r.required_slots_json or [],
        optional_slots=r.optional_slots_json or [],
        sufficient_threshold=r.sufficient_threshold,
        partial_threshold=r.partial_threshold,
        enabled=r.enabled,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("/versions/{version_id}/answerability-profiles")
async def list_answerability_profiles(
    version_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    rows = list(
        (
            await db.execute(
                select(KnowledgeAnswerabilityProfile)
                .where(KnowledgeAnswerabilityProfile.config_version_id == version_id)
                .order_by(KnowledgeAnswerabilityProfile.profile_key)
            )
        ).scalars()
    )
    items = [_answerability_to_response(r) for r in rows]
    return success_response(
        {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.post("/versions/{version_id}/answerability-profiles")
async def create_answerability_profile(
    version_id: str,
    request: AnswerabilityProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)
    row = KnowledgeAnswerabilityProfile(
        config_version_id=version_id,
        profile_key=request.profile_key,
        required_slots_json=request.required_slots,
        optional_slots_json=request.optional_slots,
        sufficient_threshold=request.sufficient_threshold,
        partial_threshold=request.partial_threshold,
        enabled=request.enabled,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PROFILE_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    return success_response(_answerability_to_response(row).model_dump(mode="json"))


@router.put("/versions/{version_id}/answerability-profiles/{profile_id}")
async def update_answerability_profile(
    version_id: str,
    profile_id: str,
    request: AnswerabilityProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeAnswerabilityProfile, profile_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PROFILE_NOT_FOUND]", status_code=404)
    user_id = str(current_user.user_id)
    if request.profile_key is not None:
        row.profile_key = request.profile_key
    if request.required_slots is not None:
        row.required_slots_json = request.required_slots
    if request.optional_slots is not None:
        row.optional_slots_json = request.optional_slots
    if request.sufficient_threshold is not None:
        row.sufficient_threshold = request.sufficient_threshold
    if request.partial_threshold is not None:
        row.partial_threshold = request.partial_threshold
    if request.enabled is not None:
        row.enabled = request.enabled
    row.updated_by = user_id
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PROFILE_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    return success_response(_answerability_to_response(row).model_dump(mode="json"))


@router.delete("/versions/{version_id}/answerability-profiles/{profile_id}")
async def delete_answerability_profile(
    version_id: str, profile_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeAnswerabilityProfile, profile_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PROFILE_NOT_FOUND]", status_code=404)
    await db.delete(row)
    await db.commit()
    return success_response({"deleted": True, "id": profile_id})


# ═══════════════════════════════════════════════════════════
# Profile CRUD — Chunking Presets
# ═══════════════════════════════════════════════════════════


def _chunking_preset_to_response(r: KnowledgeChunkingPreset) -> ChunkingPresetResponse:
    return ChunkingPresetResponse(
        id=str(r.id),
        config_version_id=str(r.config_version_id),
        profile_key=r.profile_key,
        description=r.description,
        chunking_strategy=r.chunking_strategy,
        chunk_size=r.chunk_size,
        chunk_overlap=r.chunk_overlap,
        is_default=r.is_default,
        enabled=r.enabled,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("/versions/{version_id}/chunking-presets")
async def list_chunking_presets(
    version_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    rows = list(
        (
            await db.execute(
                select(KnowledgeChunkingPreset)
                .where(KnowledgeChunkingPreset.config_version_id == version_id)
                .order_by(KnowledgeChunkingPreset.profile_key)
            )
        ).scalars()
    )
    items = [_chunking_preset_to_response(r) for r in rows]
    return success_response(
        {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.post("/versions/{version_id}/chunking-presets")
async def create_chunking_preset(
    version_id: str,
    request: ChunkingPresetCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    user_id = str(current_user.user_id)
    row = KnowledgeChunkingPreset(
        config_version_id=version_id,
        profile_key=request.profile_key,
        description=request.description,
        chunking_strategy=request.chunking_strategy,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        is_default=request.is_default,
        enabled=request.enabled,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PRESET_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    return success_response(_chunking_preset_to_response(row).model_dump(mode="json"))


@router.put("/versions/{version_id}/chunking-presets/{preset_id}")
async def update_chunking_preset(
    version_id: str,
    preset_id: str,
    request: ChunkingPresetUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeChunkingPreset, preset_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PRESET_NOT_FOUND]", status_code=404)
    user_id = str(current_user.user_id)
    if request.profile_key is not None:
        row.profile_key = request.profile_key
    if request.description is not None:
        row.description = request.description
    if request.chunking_strategy is not None:
        row.chunking_strategy = request.chunking_strategy
    if request.chunk_size is not None:
        row.chunk_size = request.chunk_size
    if request.chunk_overlap is not None:
        row.chunk_overlap = request.chunk_overlap
    if request.is_default is not None:
        row.is_default = request.is_default
    if request.enabled is not None:
        row.enabled = request.enabled
    row.updated_by = user_id
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return error_response("[PRESET_KEY_DUPLICATE]", status_code=409)
    await db.commit()
    await db.refresh(row)
    return success_response(_chunking_preset_to_response(row).model_dump(mode="json"))


@router.delete("/versions/{version_id}/chunking-presets/{preset_id}")
async def delete_chunking_preset(
    version_id: str, preset_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeChunkingPreset, preset_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PRESET_NOT_FOUND]", status_code=404)
    await db.delete(row)
    await db.commit()
    return success_response({"deleted": True, "id": preset_id})


@router.post("/versions/{version_id}/chunking-presets/{preset_id}/set-default")
async def set_default_chunking_preset(
    version_id: str,
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    await _ensure_version(db, version_id)
    row = await db.get(KnowledgeChunkingPreset, preset_id)
    if row is None or str(row.config_version_id) != version_id:
        return error_response("[PRESET_NOT_FOUND]", status_code=404)
    # Clear existing defaults for this version
    existing_defaults = list(
        (
            await db.execute(
                select(KnowledgeChunkingPreset).where(
                    KnowledgeChunkingPreset.config_version_id == version_id,
                    KnowledgeChunkingPreset.is_default.is_(True),
                )
            )
        ).scalars()
    )
    for existing in existing_defaults:
        existing.is_default = False
    row.is_default = True
    row.updated_by = str(current_user.user_id)
    await db.commit()
    await db.refresh(row)
    return success_response(_chunking_preset_to_response(row).model_dump(mode="json"))


# ═══════════════════════════════════════════════════════════
# Debug Trigger
# ═══════════════════════════════════════════════════════════


@router.post("/debug/trigger")
async def debug_trigger_knowledge_answer(
    request: DebugTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    from common.knowledge.service import KnowledgeService
    from common.knowledge_engine.compat import execute_knowledge_answer_engine
    from common.knowledge_engine.config_repo import KnowledgeAnswerConfigRepository

    # 1. Load active config snapshot
    snapshot = await db.run_sync(
        lambda sync_session: KnowledgeAnswerConfigRepository(
            sync_session
        ).get_active_config()
    )
    if snapshot is None:
        return error_response(
            "[KNOWLEDGE_NO_ACTIVE_CONFIG]",
            status_code=422,
            message="No active config version found. Create and activate a config version first.",
        )

    # 2. Create KnowledgeService for search_multiple
    knowledge_service = KnowledgeService(db)

    # 3. Execute engine
    try:
        outcome = await execute_knowledge_answer_engine(
            db=db,
            config_snapshot=snapshot,
            search_multiple=knowledge_service.search_multiple,
            request_query=request.query,
            session_id=None,
            knowledge_base_ids=request.knowledge_base_ids,
            entrypoint="debug_trigger",
            runtime_options=request.runtime_options
            or {
                "top_k": 5,
                "similarity_threshold": 0.58,
                "enable_hybrid": True,
                "keyword_candidate_limit": 32,
                "embedding_timeout_ms": 0,
                "enable_rerank": False,
                "rerank_top_k": 8,
                "metadata_filter": {},
            },
            strict_kb_mode=request.strict_kb_mode,
        )
    except Exception as e:
        return error_response(
            "[ENGINE_EXECUTION_ERROR]",
            status_code=500,
            message=f"Knowledge answer engine error: {e!s}\n{traceback.format_exc()}",
        )

    # 4. Return full payload
    return success_response(outcome.payload)

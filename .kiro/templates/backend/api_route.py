"""
{模块名} API
{模块描述}

使用方法:
1. 复制此文件到 backend/src/{module}/api/
2. 替换 {Resource}, {resource}, {module} 等占位符
3. 实现 Service 层逻辑
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user, require_admin
from common.db.session import get_db
from common.monitoring.logger import get_logger

from .schemas import CreateRequest, UpdateRequest, Response, PaginatedResponse
from .service import {Resource}Service

logger = get_logger(__name__)
router = APIRouter(prefix="/{resource}s", tags=["{resource}s"])


@router.post("", response_model=Response)
async def create(
    request: CreateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建资源"""
    service = {Resource}Service(db)
    result = await service.create(
        data=request.model_dump(),
        user_id=current_user.user_id
    )
    
    if not result.is_success:
        return {"success": False, "error": result.fallback}
    
    return {"success": True, "data": result.value}


@router.get("", response_model=PaginatedResponse)
async def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取列表 (分页)"""
    service = {Resource}Service(db)
    items, total = await service.list(
        page=page,
        page_size=page_size,
        status=status
    )
    
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": (page * page_size) < total
        }
    }


@router.get("/{id}", response_model=Response)
async def get_by_id(
    id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取详情"""
    service = {Resource}Service(db)
    result = await service.get_by_id(str(id))
    
    if not result.is_success:
        return {"success": False, "error": result.fallback}
    
    return {"success": True, "data": result.value}


@router.put("/{id}", response_model=Response)
async def update(
    id: UUID,
    request: UpdateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新资源"""
    service = {Resource}Service(db)
    result = await service.update(str(id), request.model_dump(exclude_unset=True))
    
    if not result.is_success:
        return {"success": False, "error": result.fallback}
    
    return {"success": True, "data": result.value}


@router.delete("/{id}")
async def delete(
    id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除资源"""
    service = {Resource}Service(db)
    result = await service.delete(str(id))
    
    if not result.is_success:
        return {"success": False, "error": result.fallback}
    
    return {"success": True}

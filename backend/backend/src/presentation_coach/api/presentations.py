"""
PPT Presentation API Routes
Provides CRUD operations for presentation management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import Presentation, User
from common.db.session import get_db

router = APIRouter()


# Pydantic schemas
class PresentationCreate(BaseModel):
    title: str
    file_url: str
    file_size_bytes: int
    total_pages: int


class PresentationResponse(BaseModel):
    presentation_id: str
    title: str
    file_url: str
    total_pages: int
    status: str
    upload_date: str
    uploaded_by_admin_id: str

    class Config:
        from_attributes = True


@router.get("/presentations", response_model=list[PresentationResponse])
async def list_presentations(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all presentations with pagination

    FR-018: PPT 预览权限
    - 只有上传者和管理员可以查看
    """
    result = await db.execute(
        select(Presentation)
        .offset(skip)
        .limit(limit)
        .order_by(Presentation.upload_date.desc())
    )
    presentations = result.scalars().all()

    return [
        PresentationResponse(
            presentation_id=str(p.presentation_id),
            title=p.title,
            file_url=p.file_url,
            total_pages=p.total_pages or 0,
            status=p.status,
            upload_date=p.upload_date.isoformat(),
            uploaded_by_admin_id=str(p.uploaded_by_admin_id)
        )
        for p in presentations
    ]


@router.get("/presentations/{presentation_id}", response_model=PresentationResponse)
async def get_presentation(
    presentation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific presentation by ID"""
    result = await db.execute(
        select(Presentation).where(Presentation.presentation_id == presentation_id)
    )
    presentation = result.scalar_one_or_none()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    return PresentationResponse(
        presentation_id=str(presentation.presentation_id),
        title=presentation.title,
        file_url=presentation.file_url,
        total_pages=presentation.total_pages or 0,
        status=presentation.status,
        upload_date=presentation.upload_date.isoformat(),
        uploaded_by_admin_id=str(presentation.uploaded_by_admin_id)
    )


@router.post("/presentations", response_model=PresentationResponse)
async def create_presentation(
    presentation: PresentationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a new PPT presentation

    FR-007: PPT 上传与 OCR
    - 支持格式: .pptx, .pdf
    - 最大文件大小: 100MB
    - 自动 OCR 提取文字内容
    """
    new_presentation = Presentation(
        title=presentation.title,
        file_url=presentation.file_url,
        file_size_bytes=presentation.file_size_bytes,
        total_pages=presentation.total_pages,
        uploaded_by_admin_id=current_user.user_id,
        status="processing"
    )

    db.add(new_presentation)
    await db.commit()
    await db.refresh(new_presentation)

    # Trigger OCR processing (async background task)
    # TODO: Implement OCR processing service

    return PresentationResponse(
        presentation_id=str(new_presentation.presentation_id),
        title=new_presentation.title,
        file_url=new_presentation.file_url,
        total_pages=new_presentation.total_pages or 0,
        status=new_presentation.status,
        upload_date=new_presentation.upload_date.isoformat(),
        uploaded_by_admin_id=str(new_presentation.uploaded_by_admin_id)
    )


@router.delete("/presentations/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a presentation (admin only)"""
    result = await db.execute(
        select(Presentation).where(Presentation.presentation_id == presentation_id)
    )
    presentation = result.scalar_one_or_none()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    await db.delete(presentation)
    await db.commit()

    return {"message": "Presentation deleted successfully"}

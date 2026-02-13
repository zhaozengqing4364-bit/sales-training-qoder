"""
Admin API - CRUD operations for presentations, pages, talking points, forbidden words

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Efficient operations
"""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import (
    ForbiddenWord,
    Page,
    Presentation,
    RequiredTalkingPoint,
    User,
)
from common.db.session import get_db
from common.knowledge.ingestion_service import ingestion_service
from common.monitoring.logger import get_logger
from common.ppt.ocr_processor import ocr_processor
from presentation_coach.services.point_extraction import point_extraction_service

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Schemas
class PresentationCreate(BaseModel):
    title: str
    description: str | None = None


class PageUpdate(BaseModel):
    title: str
    content: str | None = None


class TalkingPointCreate(BaseModel):
    point_text: str
    order: int = 0


class ForbiddenWordCreate(BaseModel):
    word: str | None = None
    phrase: str | None = None
    pattern_type: str = "literal"  # literal or regex
    suggested_alternative: str | None = None


# Presentations CRUD
@router.post("/admin/presentations")
async def create_presentation(
    data: PresentationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new presentation (without file upload)"""
    try:
        presentation = Presentation(
            presentation_id=uuid.uuid4(),
            user_id=current_user.user_id,
            title=data.title,
            description=data.description,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        db.add(presentation)
        await db.commit()
        await db.refresh(presentation)

        return presentation
    except SQLAlchemyError as e:
        logger.error(f"Failed to create presentation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create presentation")


@router.post("/admin/presentations/upload")
async def upload_presentation(
    file: UploadFile = File(...),
    title: str = None,
    description: str = None,
    extract_points: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a PPT file and extract content

    If extract_points=True, uses AI to automatically extract talking points
    """
    try:
        # Save uploaded file
        upload_dir = "/data/uploads"
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, file.filename)

        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Create presentation record
        presentation = Presentation(
            presentation_id=uuid.uuid4(),
            user_id=current_user.user_id,
            title=title or file.filename,
            description=description,
            file_url=file_path,
            total_pages=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        db.add(presentation)
        await db.commit()
        await db.refresh(presentation)

        # Extract text from PPT
        extraction_result = await ocr_processor.extract_text(
            file_path=file_path,
            presentation_id=presentation.presentation_id,
            filename=file.filename
        )

        if not extraction_result.is_success:
            logger.warning("OCR extraction failed, creating empty presentation")
            return presentation

        extraction = extraction_result.value

        # Create page records
        for page_data in extraction.pages:
            page = Page(
                page_id=uuid.uuid4(),
                presentation_id=presentation.presentation_id,
                page_number=page_data.page_number,
                title=page_data.title,
                content=page_data.content,
                image_count=page_data.image_count,
            )
            db.add(page)

        presentation.total_pages = extraction.total_pages
        await db.commit()

        # Ingest into vector store
        await ingestion_service.ingest_presentation(extraction)

        # Auto-extract talking points if requested
        if extract_points:
            points_result = await point_extraction_service.extract_points_for_presentation(
                extraction.pages
            )

            if points_result.is_success:
                for page_num, points in points_result.value.items():
                    # Add required talking points to database
                    for i, point_text in enumerate(points.required_points):
                        talking_point = RequiredTalkingPoint(
                            point_id=uuid.uuid4(),
                            presentation_id=presentation.presentation_id,
                            page_number=page_num,
                            point_text=point_text,
                            point_order=i,
                            created_at=datetime.now(),
                        )
                        db.add(talking_point)

                await db.commit()

        return presentation

    except (SQLAlchemyError, OSError, ValueError) as e:
        logger.error(f"Failed to upload presentation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload presentation")


@router.get("/admin/presentations")
async def list_presentations(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all presentations"""
    try:
        result = await db.execute(
            select(Presentation)
            .order_by(Presentation.upload_date.desc())
            .limit(limit)
        )
        presentations = result.scalars().all()

        return {"presentations": presentations, "total": len(presentations)}
    except SQLAlchemyError as e:
        logger.error(f"Failed to list presentations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list presentations")


@router.get("/admin/presentations/{presentation_id}")
async def get_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get presentation details"""
    try:
        result = await db.execute(
            select(Presentation).where(Presentation.presentation_id == uuid.UUID(presentation_id))
        )
        presentation = result.scalar_one_or_none()

        if not presentation:
            raise HTTPException(status_code=404, detail="Presentation not found")

        return presentation
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to get presentation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get presentation")


@router.delete("/admin/presentations/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a presentation"""
    try:
        # Get presentation
        result = await db.execute(
            select(Presentation).where(Presentation.presentation_id == uuid.UUID(presentation_id))
        )
        presentation = result.scalar_one_or_none()

        if not presentation:
            raise HTTPException(status_code=404, detail="Presentation not found")

        # Delete from vector store
        await ingestion_service.delete_presentation(presentation.presentation_id)

        # Delete from database (cascade will handle pages, talking points, etc.)
        await db.delete(presentation)
        await db.commit()

        return {"deleted": True}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to delete presentation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete presentation")


# Pages CRUD
@router.get("/admin/presentations/{presentation_id}/pages")
async def list_pages(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all pages in a presentation"""
    try:
        result = await db.execute(
            select(Page)
            .where(Page.presentation_id == uuid.UUID(presentation_id))
            .order_by(Page.page_number)
        )
        pages = result.scalars().all()

        return {"pages": pages, "total": len(pages)}
    except SQLAlchemyError as e:
        logger.error(f"Failed to list pages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list pages")


@router.put("/admin/presentations/{presentation_id}/pages/{page_number}")
async def update_page(
    presentation_id: str,
    page_number: int,
    data: PageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update page content"""
    try:
        result = await db.execute(
            select(Page).where(
                Page.presentation_id == uuid.UUID(presentation_id),
                Page.page_number == page_number
            )
        )
        page = result.scalar_one_or_none()

        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        page.title = data.title
        page.content = data.content
        page.updated_at = datetime.now()

        await db.commit()
        await db.refresh(page)

        # Update in vector store
        await ingestion_service.update_page(
            presentation_id=uuid.UUID(presentation_id),
            page_number=page_number,
            title=data.title,
            content=data.content or "",
            filename=""
        )

        return page
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to update page: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update page")


# Talking Points CRUD
@router.post("/admin/presentations/{presentation_id}/pages/{page_number}/talking-points")
async def create_talking_point(
    presentation_id: str,
    page_number: int,
    data: TalkingPointCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a required talking point for a page"""
    try:
        talking_point = RequiredTalkingPoint(
            point_id=uuid.uuid4(),
            presentation_id=uuid.UUID(presentation_id),
            page_number=page_number,
            point_text=data.point_text,
            point_order=data.order,
            created_at=datetime.now(),
        )

        db.add(talking_point)
        await db.commit()
        await db.refresh(talking_point)

        return talking_point
    except SQLAlchemyError as e:
        logger.error(f"Failed to create talking point: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create talking point")


@router.get("/admin/presentations/{presentation_id}/pages/{page_number}/talking-points")
async def list_talking_points(
    presentation_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List talking points for a page"""
    try:
        result = await db.execute(
            select(RequiredTalkingPoint).where(
                RequiredTalkingPoint.presentation_id == uuid.UUID(presentation_id),
                RequiredTalkingPoint.page_number == page_number
            ).order_by(RequiredTalkingPoint.point_order)
        )
        points = result.scalars().all()

        return {"points": points, "total": len(points)}
    except SQLAlchemyError as e:
        logger.error(f"Failed to list talking points: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list talking points")


@router.delete("/admin/talking-points/{point_id}")
async def delete_talking_point(
    point_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a talking point"""
    try:
        result = await db.execute(
            select(RequiredTalkingPoint).where(
                RequiredTalkingPoint.point_id == uuid.UUID(point_id)
            )
        )
        point = result.scalar_one_or_none()

        if not point:
            raise HTTPException(status_code=404, detail="Talking point not found")

        await db.delete(point)
        await db.commit()

        return {"deleted": True}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to delete talking point: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete talking point")


# Forbidden Words CRUD
@router.post("/admin/presentations/{presentation_id}/forbidden-words", status_code=201)
async def create_forbidden_word(
    presentation_id: str,
    data: ForbiddenWordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a forbidden word for a presentation"""
    try:
        phrase_value = (data.phrase or data.word or "").strip()
        if not phrase_value:
            raise HTTPException(status_code=400, detail="Forbidden phrase is required")

        forbidden_word = ForbiddenWord(
            word_id=str(uuid.uuid4()),
            presentation_id=presentation_id,
            page_id=None,
            phrase=phrase_value,
            suggested_alternative=data.suggested_alternative,
            is_regex=(data.pattern_type == "regex"),
        )

        db.add(forbidden_word)
        await db.commit()
        await db.refresh(forbidden_word)

        return forbidden_word
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to create forbidden word: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create forbidden word")


@router.get("/admin/presentations/{presentation_id}/forbidden-words")
async def list_forbidden_words(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List forbidden words for a presentation"""
    try:
        result = await db.execute(
            select(ForbiddenWord).where(
                ForbiddenWord.presentation_id == uuid.UUID(presentation_id)
            )
        )
        words = result.scalars().all()

        return {"words": words, "total": len(words)}
    except SQLAlchemyError as e:
        logger.error(f"Failed to list forbidden words: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list forbidden words")


@router.delete("/admin/forbidden-words/{word_id}")
async def delete_forbidden_word(
    word_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a forbidden word"""
    try:
        result = await db.execute(
            select(ForbiddenWord).where(
                ForbiddenWord.word_id == uuid.UUID(word_id)
            )
        )
        word = result.scalar_one_or_none()

        if not word:
            raise HTTPException(status_code=404, detail="Forbidden word not found")

        await db.delete(word)
        await db.commit()

        return {"deleted": True}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to delete forbidden word: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete forbidden word")

"""
Admin API - CRUD operations for presentations, pages, talking points, forbidden words

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Efficient operations
"""

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user
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

ALLOWED_PRESENTATION_EXTENSIONS = {".ppt", ".pptx"}
ALLOWED_PRESENTATION_CONTENT_TYPES = {
    "application/octet-stream",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _safe_presentation_upload_path(
    filename: str | None, upload_root: str
) -> tuple[Path, str]:
    """Return a server-owned upload path for a validated PPT filename."""
    raw_filename = (filename or "").strip()
    if not raw_filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    if "/" in raw_filename or "\\" in raw_filename or ".." in raw_filename.split("/"):
        raise HTTPException(
            status_code=400, detail="Nested or traversal paths are not allowed"
        )

    original_name = Path(raw_filename).name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_PRESENTATION_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Only .ppt and .pptx files are allowed"
        )

    root = Path(upload_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / f"{uuid.uuid4().hex}{extension}").resolve()
    if root != target.parent:
        raise HTTPException(
            status_code=400, detail="Resolved upload path is outside upload root"
        )
    return target, original_name


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
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new presentation (without file upload)"""
    try:
        presentation = Presentation(
            presentation_id=str(uuid.uuid4()),
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
        return build_server_error(
            "[ADMIN_PRESENTATION_CREATE_FAILED]",
            message="Failed to create presentation",
            exc=e,
        )


@router.post("/admin/presentations/upload")
async def upload_presentation(
    file: UploadFile = File(...),
    title: str | None = None,
    description: str | None = None,
    extract_points: bool = True,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PPT file and extract content

    If extract_points=True, uses AI to automatically extract talking points
    """
    try:
        # Save uploaded file under a server-generated name. The original filename
        # is display metadata only and never controls the storage path.
        upload_dir = os.getenv("PPT_UPLOAD_DIR", "/data/uploads")
        content_type = (file.content_type or "application/octet-stream").lower()
        if content_type not in ALLOWED_PRESENTATION_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported upload MIME type: {content_type}",
            )
        upload_path, original_filename = _safe_presentation_upload_path(
            file.filename, upload_dir
        )

        content = await file.read()
        with open(upload_path, "wb") as buffer:
            buffer.write(content)

        # Create presentation record
        presentation = Presentation(
            presentation_id=str(uuid.uuid4()),
            title=title or original_filename,
            file_url=str(upload_path),
            file_size_bytes=len(content),
            uploaded_by_admin_id=current_user.user_id,
            total_pages=0,
            upload_date=datetime.now(),
        )

        db.add(presentation)
        await db.commit()
        await db.refresh(presentation)

        # Extract text from PPT
        extraction_result = await ocr_processor.extract_text(
            file_path=str(upload_path),
            presentation_id=presentation.presentation_id,
            filename=original_filename,
        )

        if not extraction_result.is_success:
            logger.warning("OCR extraction failed, creating empty presentation")
            return presentation

        extraction = extraction_result.value
        if extraction is None:
            logger.warning("OCR extraction returned no presentation payload")
            return presentation

        # Create page records using the current Presentation/Page schema.
        pages_by_number: dict[int, Page] = {}
        for page_data in extraction.pages:
            text_parts = [
                part
                for part in (
                    getattr(page_data, "title", None),
                    getattr(page_data, "content", None),
                )
                if part
            ]
            page = Page(
                page_id=str(uuid.uuid4()),
                presentation_id=str(presentation.presentation_id),
                page_number=page_data.page_number,
                ocr_extracted_text="\n\n".join(text_parts),
                extraction_confidence=None,
                needs_manual_review=False,
            )
            pages_by_number[page_data.page_number] = page
            db.add(page)

        presentation.total_pages = extraction.total_pages
        await db.commit()

        # Ingest into vector store
        await ingestion_service.ingest_presentation(extraction)

        # Auto-extract talking points if requested
        if extract_points:
            points_result = (
                await point_extraction_service.extract_points_for_presentation(
                    extraction.pages
                )
            )

            if points_result.is_success and points_result.value is not None:
                for page_num, points in points_result.value.items():
                    # Add required talking points to database
                    page = pages_by_number.get(page_num)
                    if page is None:
                        continue
                    for point_text in points.required_points:
                        talking_point = RequiredTalkingPoint(
                            point_id=str(uuid.uuid4()),
                            page_id=page.page_id,
                            description=point_text,
                            created_by="ai",
                            is_ai_generated=True,
                            confirmed_by_admin=False,
                            created_at=datetime.now(),
                        )
                        db.add(talking_point)

                await db.commit()

        return presentation

    except HTTPException:
        raise
    except (SQLAlchemyError, OSError, ValueError) as e:
        logger.error(f"Failed to upload presentation: {str(e)}")
        return build_server_error(
            "[ADMIN_PRESENTATION_UPLOAD_FAILED]",
            message="Failed to upload presentation",
            exc=e,
        )


@router.get("/admin/presentations")
async def list_presentations(
    limit: int = 50,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all presentations"""
    try:
        result = await db.execute(
            select(Presentation).order_by(Presentation.upload_date.desc()).limit(limit)
        )
        presentations = result.scalars().all()

        return {"presentations": presentations, "total": len(presentations)}
    except SQLAlchemyError as e:
        logger.error(f"Failed to list presentations: {str(e)}")
        return build_server_error(
            "[ADMIN_PRESENTATION_LIST_FAILED]",
            message="Failed to list presentations",
            exc=e,
        )


@router.get("/admin/presentations/{presentation_id}")
async def get_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presentation details"""
    try:
        result = await db.execute(
            select(Presentation).where(
                Presentation.presentation_id == uuid.UUID(presentation_id)
            )
        )
        presentation = result.scalar_one_or_none()

        if not presentation:
            raise HTTPException(status_code=404, detail="Presentation not found")

        return presentation
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to get presentation: {str(e)}")
        return build_server_error(
            "[ADMIN_PRESENTATION_GET_FAILED]",
            message="Failed to get presentation",
            exc=e,
            presentation_id=presentation_id,
        )


@router.delete("/admin/presentations/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a presentation"""
    try:
        # Get presentation
        result = await db.execute(
            select(Presentation).where(
                Presentation.presentation_id == uuid.UUID(presentation_id)
            )
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
        return build_server_error(
            "[ADMIN_PRESENTATION_DELETE_FAILED]",
            message="Failed to delete presentation",
            exc=e,
            presentation_id=presentation_id,
        )


# Pages CRUD
@router.get("/admin/presentations/{presentation_id}/pages")
async def list_pages(
    presentation_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
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
        return build_server_error(
            "[ADMIN_PAGE_LIST_FAILED]",
            message="Failed to list pages",
            exc=e,
            presentation_id=presentation_id,
        )


@router.put("/admin/presentations/{presentation_id}/pages/{page_number}")
async def update_page(
    presentation_id: str,
    page_number: int,
    data: PageUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update page content"""
    try:
        result = await db.execute(
            select(Page).where(
                Page.presentation_id == uuid.UUID(presentation_id),
                Page.page_number == page_number,
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
            filename="",
        )

        return page
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to update page: {str(e)}")
        return build_server_error(
            "[ADMIN_PAGE_UPDATE_FAILED]",
            message="Failed to update page",
            exc=e,
            presentation_id=presentation_id,
            page_number=page_number,
        )


# Talking Points CRUD
@router.post(
    "/admin/presentations/{presentation_id}/pages/{page_number}/talking-points"
)
async def create_talking_point(
    presentation_id: str,
    page_number: int,
    data: TalkingPointCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
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
        return build_server_error(
            "[ADMIN_TALKING_POINT_CREATE_FAILED]",
            message="Failed to create talking point",
            exc=e,
            presentation_id=presentation_id,
            page_number=page_number,
        )


@router.get("/admin/presentations/{presentation_id}/pages/{page_number}/talking-points")
async def list_talking_points(
    presentation_id: str,
    page_number: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List talking points for a page"""
    try:
        result = await db.execute(
            select(RequiredTalkingPoint)
            .where(
                RequiredTalkingPoint.presentation_id == uuid.UUID(presentation_id),
                RequiredTalkingPoint.page_number == page_number,
            )
            .order_by(RequiredTalkingPoint.point_order)
        )
        points = result.scalars().all()

        return {"points": points, "total": len(points)}
    except SQLAlchemyError as e:
        logger.error(f"Failed to list talking points: {str(e)}")
        return build_server_error(
            "[ADMIN_TALKING_POINT_LIST_FAILED]",
            message="Failed to list talking points",
            exc=e,
            presentation_id=presentation_id,
            page_number=page_number,
        )


@router.delete("/admin/talking-points/{point_id}")
async def delete_talking_point(
    point_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
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
        return build_server_error(
            "[ADMIN_TALKING_POINT_DELETE_FAILED]",
            message="Failed to delete talking point",
            exc=e,
            point_id=point_id,
        )


# Forbidden Words CRUD
@router.post("/admin/presentations/{presentation_id}/forbidden-words", status_code=201)
async def create_forbidden_word(
    presentation_id: str,
    data: ForbiddenWordCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
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
        return build_server_error(
            "[ADMIN_FORBIDDEN_WORD_CREATE_FAILED]",
            message="Failed to create forbidden word",
            exc=e,
            presentation_id=presentation_id,
        )


@router.get("/admin/presentations/{presentation_id}/forbidden-words")
async def list_forbidden_words(
    presentation_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
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
        return build_server_error(
            "[ADMIN_FORBIDDEN_WORD_LIST_FAILED]",
            message="Failed to list forbidden words",
            exc=e,
            presentation_id=presentation_id,
        )


@router.delete("/admin/forbidden-words/{word_id}")
async def delete_forbidden_word(
    word_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a forbidden word"""
    try:
        result = await db.execute(
            select(ForbiddenWord).where(ForbiddenWord.word_id == uuid.UUID(word_id))
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
        return build_server_error(
            "[ADMIN_FORBIDDEN_WORD_DELETE_FAILED]",
            message="Failed to delete forbidden word",
            exc=e,
            word_id=word_id,
        )

"""
Presentations API - CRUD operations for PPT presentations
"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import (
    ForbiddenWord,
    Page,
    Presentation,
    RequiredTalkingPoint,
    User,
)
from common.db.schemas import (
    ForbiddenWordCreate,
    PresentationDetail,
    PresentationResponse,
    RequiredTalkingPointCreate,
)
from common.db.session import get_db
from common.monitoring.logger import get_logger
from presentation_coach.services.ppt_parser import get_ppt_parser

logger = get_logger(__name__)

router = APIRouter()


def _presentation_storage_root() -> Path:
    return Path(os.getenv("PPT_STORAGE_PATH", "./data/ppts"))


def _thumbnail_storage_root() -> Path:
    configured = os.getenv("PPT_THUMBNAIL_STORAGE_PATH")
    root = (
        Path(configured) if configured else _presentation_storage_root() / "thumbnails"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _thumbnail_file_path(presentation_id: str, page_number: int) -> Path:
    return _thumbnail_storage_root() / presentation_id / f"page-{page_number}.png"


def _thumbnail_api_url(presentation_id: str, page_number: int) -> str:
    return f"/api/v1/presentations/{presentation_id}/pages/{page_number}/thumbnail"


def _hydrate_page_thumbnail_url(page: Page, presentation_id: str) -> None:
    image_url = cast(str | None, getattr(page, "image_url", None))
    if image_url:
        return
    page_number = int(cast(int, getattr(page, "page_number", 0)) or 0)
    if page_number < 1:
        return
    thumbnail_path = _thumbnail_file_path(presentation_id, page_number)
    if thumbnail_path.exists():
        setattr(page, "image_url", _thumbnail_api_url(presentation_id, page_number))


def _atomic_write_bytes(file_path: Path, content: bytes) -> None:
    """Write file atomically to avoid partial/corrupted uploads."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=str(file_path.parent),
        prefix=f".{file_path.name}.",
    )
    try:
        tmp_file.write(content)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_file.close()
        os.replace(tmp_file.name, file_path)
    except Exception:
        try:
            tmp_file.close()
        except Exception:
            pass
        try:
            os.unlink(tmp_file.name)
        except OSError:
            pass
        raise


@router.get("/presentations", response_model=list[PresentationResponse])
async def list_presentations(
    status: str | None = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all presentations"""
    query = select(Presentation)

    if status:
        query = query.where(Presentation.status == status)

    query = query.limit(limit)

    result = await db.execute(query)
    presentations = result.scalars().all()

    return presentations


@router.post("/presentations", response_model=PresentationResponse)
async def upload_presentation(
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new PPT presentation with automatic parsing"""
    presentation: Presentation | None = None
    file_path: Path | None = None
    try:
        upload_dir = _presentation_storage_root()
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_id = str(uuid.uuid4())
        uploaded_name = file.filename
        if not isinstance(uploaded_name, str) or not uploaded_name:
            uploaded_name = f"upload-{file_id}.pptx"
        source_filename = uploaded_name
        if "." in source_filename:
            file_extension = source_filename.split(".")[-1]
        else:
            file_extension = "pptx"
        file_path = upload_dir / f"{file_id}.{file_extension}"

        content = await file.read()
        _atomic_write_bytes(file_path, content)

        # Create presentation record
        presentation = Presentation(
            title=title,
            file_url=str(file_path),
            file_size_bytes=len(content),
            uploaded_by_admin_id=current_user.user_id,
            status="processing",
        )

        db.add(presentation)
        await db.commit()
        await db.refresh(presentation)
        presentation_id_value = str(presentation.presentation_id)

        # Parse PPT and create page records
        parser = get_ppt_parser()
        parse_result = await parser.parse_presentation(content, source_filename)

        if parse_result.is_success and isinstance(parse_result.value, dict):
            parsed_data = cast(dict[str, Any], parse_result.value)

            # Update presentation with total pages
            setattr(presentation, "total_pages", int(parsed_data.get("total_pages", 0)))

            # Create page records
            thumbnail_output_dir = _thumbnail_storage_root() / presentation_id_value
            for page_data in parsed_data.get("pages", []):
                if not isinstance(page_data, dict):
                    continue
                page_number = page_data["page_number"]
                thumbnail_result = await parser.generate_thumbnail(
                    file_content=content,
                    page_number=page_number,
                    output_dir=str(thumbnail_output_dir),
                )

                image_url: str | None = None
                if thumbnail_result.is_success and thumbnail_result.value:
                    image_url = _thumbnail_api_url(
                        presentation_id_value,
                        page_number,
                    )
                elif thumbnail_result.fallback:
                    logger.warning(
                        "Thumbnail generation failed",
                        presentation_id=presentation_id_value,
                        page_number=page_number,
                        error=thumbnail_result.fallback,
                    )

                page = Page(
                    presentation_id=presentation_id_value,
                    page_number=page_number,
                    ocr_extracted_text=page_data.get("extracted_text", ""),
                    image_url=image_url,
                    extraction_confidence=0.95,  # PPT parsing has high confidence
                    needs_manual_review=False,
                )
                db.add(page)

            setattr(presentation, "status", "ready")
            await db.commit()

            logger.info(
                f"Presentation uploaded and parsed: {presentation_id_value} "
                f"with {presentation.total_pages} pages"
            )
        else:
            # Parsing failed, mark for manual review
            setattr(presentation, "status", "failed")
            await db.commit()
            logger.error(
                f"Failed to parse presentation {presentation_id_value}: "
                f"{parse_result.fallback}"
            )

        return presentation

    except (RuntimeError, ValueError, OSError) as e:
        logger.error(f"Failed to upload presentation: {str(e)}")
        await db.rollback()
        if presentation is not None:
            try:
                setattr(presentation, "status", "failed")
                db.add(presentation)
                await db.commit()
            except Exception as mark_error:
                await db.rollback()
                logger.error(
                    "Failed to mark presentation as failed after upload error",
                    error=str(mark_error),
                )
        elif file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        return build_server_error(
            "[PRESENTATION_UPLOAD_FAILED]",
            message="Upload failed",
            exc=e,
            title=title,
        )


@router.get("/presentations/{presentation_id}", response_model=PresentationDetail)
async def get_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presentation details"""
    result = await db.execute(
        select(Presentation)
        .options(selectinload(Presentation.pages))
        .where(Presentation.presentation_id == presentation_id)
    )
    presentation = result.scalar_one_or_none()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    for page in presentation.pages:
        _hydrate_page_thumbnail_url(page, str(presentation.presentation_id))

    return presentation


@router.delete("/presentations/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a presentation"""
    result = await db.execute(
        select(Presentation).where(Presentation.presentation_id == presentation_id)
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    is_uploader = presentation.uploaded_by_admin_id == current_user.user_id
    is_admin = getattr(current_user, "role", "") == "admin"
    if not is_uploader and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="No permission to delete this presentation",
        )

    await db.delete(presentation)
    await db.commit()

    return JSONResponse(status_code=204, content=None)


@router.get("/presentations/{presentation_id}/pages")
async def get_presentation_pages(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presentation pages"""
    result = await db.execute(
        select(Page)
        .where(Page.presentation_id == presentation_id)
        .order_by(Page.page_number)
    )
    pages = result.scalars().all()

    for page in pages:
        _hydrate_page_thumbnail_url(page, presentation_id)

    return pages


@router.get("/presentations/{presentation_id}/pages/{page_number}/thumbnail")
async def get_presentation_page_thumbnail(
    presentation_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user

    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id,
            Page.page_number == page_number,
        )
    )
    page = page_result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    thumbnail_path = _thumbnail_file_path(presentation_id, page_number)
    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    existing_url = cast(str | None, getattr(page, "image_url", None))
    if not existing_url:
        setattr(page, "image_url", _thumbnail_api_url(presentation_id, page_number))
        await db.commit()

    return FileResponse(path=thumbnail_path, media_type="image/png")


@router.get("/presentations/{presentation_id}/pages/{page_number}/talking-points")
async def get_talking_points(
    presentation_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get required talking points for a page"""
    # Get page
    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id, Page.page_number == page_number
        )
    )
    page = page_result.scalar_one_or_none()

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Get talking points
    points_result = await db.execute(
        select(RequiredTalkingPoint).where(
            RequiredTalkingPoint.page_id == page.page_id,
            RequiredTalkingPoint.confirmed_by_admin == True,
        )
    )
    points = points_result.scalars().all()

    return points


@router.post("/presentations/{presentation_id}/pages/{page_number}/talking-points")
async def add_talking_point(
    presentation_id: str,
    page_number: int,
    point: RequiredTalkingPointCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add required talking point to a page"""
    # Get page
    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id, Page.page_number == page_number
        )
    )
    page = page_result.scalar_one_or_none()

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Create talking point
    talking_point = RequiredTalkingPoint(
        page_id=page.page_id,
        description=point.description,
        created_by="admin",
        is_ai_generated=False,
        confirmed_by_admin=True,
    )

    db.add(talking_point)
    await db.commit()
    await db.refresh(talking_point)

    return talking_point


@router.get("/presentations/{presentation_id}/forbidden-words")
async def get_forbidden_words(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get forbidden words for presentation"""
    result = await db.execute(
        select(ForbiddenWord).where(
            (ForbiddenWord.presentation_id == presentation_id)
            | (ForbiddenWord.page_id == None)  # Global for presentation
        )
    )
    words = result.scalars().all()

    return words


@router.post("/presentations/{presentation_id}/forbidden-words", status_code=201)
async def add_forbidden_word(
    presentation_id: str,
    word: ForbiddenWordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add forbidden word to presentation"""
    forbidden_word = ForbiddenWord(
        presentation_id=presentation_id,
        phrase=word.phrase,
        suggested_alternative=word.suggested_alternative,
        page_id=word.page_id,
    )

    db.add(forbidden_word)
    await db.commit()
    await db.refresh(forbidden_word)

    return forbidden_word

"""
Presentations API - CRUD operations for PPT presentations
"""
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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


@router.get("/presentations", response_model=list[PresentationResponse])
async def list_presentations(
    status: str = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
):
    """Upload a new PPT presentation with automatic parsing"""
    try:
        # Save file
        upload_dir = os.getenv("PPT_STORAGE_PATH", "./data/ppts")
        os.makedirs(upload_dir, exist_ok=True)

        file_id = str(uuid.uuid4())
        file_extension = file.filename.split(".")[-1]
        file_path = os.path.join(upload_dir, f"{file_id}.{file_extension}")

        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Create presentation record
        presentation = Presentation(
            title=title,
            file_url=file_path,
            file_size_bytes=len(content),
            uploaded_by_admin_id=current_user.user_id,
            status="processing"
        )

        db.add(presentation)
        await db.commit()
        await db.refresh(presentation)

        # Parse PPT and create page records
        parser = get_ppt_parser()
        parse_result = await parser.parse_presentation(content, file.filename)

        if parse_result.is_success:
            parsed_data = parse_result.value

            # Update presentation with total pages
            presentation.total_pages = parsed_data.get("total_pages", 0)

            # Create page records
            for page_data in parsed_data.get("pages", []):
                page = Page(
                    presentation_id=presentation.presentation_id,
                    page_number=page_data["page_number"],
                    ocr_extracted_text=page_data.get("extracted_text", ""),
                    extraction_confidence=0.95,  # PPT parsing has high confidence
                    needs_manual_review=False,
                )
                db.add(page)

            presentation.status = "ready"
            await db.commit()

            logger.info(
                f"Presentation uploaded and parsed: {presentation.presentation_id} "
                f"with {presentation.total_pages} pages"
            )
        else:
            # Parsing failed, mark for manual review
            presentation.status = "failed"
            await db.commit()
            logger.error(
                f"Failed to parse presentation {presentation.presentation_id}: "
                f"{parse_result.error}"
            )

        return presentation

    except (RuntimeError, ValueError, OSError) as e:
        logger.error(f"Failed to upload presentation: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/presentations/{presentation_id}", response_model=PresentationDetail)
async def get_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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

    return presentation


@router.delete("/presentations/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a presentation"""
    result = await db.execute(
        delete(Presentation).where(Presentation.presentation_id == presentation_id)
    )
    await db.commit()

    return JSONResponse(status_code=204, content=None)


@router.get("/presentations/{presentation_id}/pages")
async def get_presentation_pages(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get presentation pages"""
    result = await db.execute(
        select(Page).where(Page.presentation_id == presentation_id)
        .order_by(Page.page_number)
    )
    pages = result.scalars().all()

    return pages


@router.get("/presentations/{presentation_id}/pages/{page_number}/talking-points")
async def get_talking_points(
    presentation_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get required talking points for a page"""
    # Get page
    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id,
            Page.page_number == page_number
        )
    )
    page = page_result.scalar_one_or_none()

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Get talking points
    points_result = await db.execute(
        select(RequiredTalkingPoint).where(
            RequiredTalkingPoint.page_id == page.page_id,
            RequiredTalkingPoint.confirmed_by_admin == True
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
    db: AsyncSession = Depends(get_db)
):
    """Add required talking point to a page"""
    # Get page
    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id,
            Page.page_number == page_number
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
        confirmed_by_admin=True
    )

    db.add(talking_point)
    await db.commit()
    await db.refresh(talking_point)

    return talking_point


@router.get("/presentations/{presentation_id}/forbidden-words")
async def get_forbidden_words(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get forbidden words for presentation"""
    result = await db.execute(
        select(ForbiddenWord).where(
            (ForbiddenWord.presentation_id == presentation_id) |
            (ForbiddenWord.page_id == None)  # Global for presentation
        )
    )
    words = result.scalars().all()

    return words


@router.post("/presentations/{presentation_id}/forbidden-words", status_code=201)
async def add_forbidden_word(
    presentation_id: str,
    word: ForbiddenWordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add forbidden word to presentation"""
    forbidden_word = ForbiddenWord(
        presentation_id=presentation_id,
        phrase=word.phrase,
        suggested_alternative=word.suggested_alternative,
        page_id=word.page_id
    )

    db.add(forbidden_word)
    await db.commit()
    await db.refresh(forbidden_word)

    return forbidden_word

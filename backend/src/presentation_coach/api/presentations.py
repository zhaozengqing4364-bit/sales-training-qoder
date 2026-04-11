"""
Presentations API - CRUD operations for PPT presentations
"""

import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import (
    ForbiddenWord,
    Page,
    PracticeSession,
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
from support.services.runtime_status_service import RuntimeStatusService

logger = get_logger(__name__)

router = APIRouter()

_NON_TERMINAL_PRESENTATION_STATUSES = ("preparing", "in_progress", "paused", "scoring")

# M016/S02/T01 error-contract inventory for this high-noise route family:
# - upload/replace 5xx failures already use build_server_error(...) -> {success:false,error,message,trace_id}.
# - the replace blocker 409 returns JSONResponse(error_response(...)) plus a nested details payload.
# - most not-found / permission branches still raise plain-string FastAPI detail payloads.
# This file therefore exposes three outward error shapes today and is a primary S02 collapse target.
#
# M017/S03/T01 upload/resource-race discovery inventory:
# - keep the race inventory next to the live upload/replace/delete authority instead of a separate audit doc.
# - distinguish what the active-session blocker already covers from surfaces that still only have suspicion or
#   database-dependent behavior.
PRESENTATION_RESOURCE_RACE_INVENTORY: tuple[dict[str, Any], ...] = (
    {
        "surface": "upload_new_presentation",
        "shared_resources": (
            "storage_file_path",
            "presentation_row",
            "page_rows",
            "thumbnail_directory",
        ),
        "active_session_blocker_coverage": "not_applicable",
        "current_guardrails": (
            "fresh storage key per upload",
            "atomic file replace prevents partial writes",
        ),
        "current_assessment": "new uploads mostly isolate themselves because each request gets a fresh presentation_id/storage key",
        "proof_state": "inventory_only",
        "next_proof": "defer until in-place mutation surfaces are retired",
    },
    {
        "surface": "replace_presentation_in_place",
        "shared_resources": (
            "stable presentation row",
            "version_number and file_url",
            "page_rows and page-scoped metadata",
            "thumbnail_directory",
            "practice_session references",
        ),
        "active_session_blocker_coverage": "covered_for_live_session_mutation_only",
        "current_guardrails": (
            "non-terminal active-session blocker",
            "atomic file replace per derived versioned path",
        ),
        "uncovered_race_windows": (
            "two replace requests can both pass the active-session preflight before either writer commits",
            "both writers can derive the same next_version and target the same versioned file path",
            "page delete-and-rebuild work has no compare-and-swap or lock once replace starts",
        ),
        "current_assessment": "focused proof confirmed a concurrent writer race: one replace can commit version 2 while a second concurrent writer falls into a page uniqueness failure during metadata rebuild",
        "proof_state": "confirmed_concurrent_writer_race",
        "next_proof": "concurrent_replace_without_active_sessions",
        "recommended_next_step": "serialize_in_place_replace_with_local_or_distributed_lock_before_multi-writer rollout",
    },
    {
        "surface": "delete_presentation",
        "shared_resources": (
            "presentation row",
            "page and forbidden-word rows",
            "practice_session references",
            "stored ppt artifact",
            "thumbnail_directory",
        ),
        "active_session_blocker_coverage": "not_covered",
        "current_guardrails": (
            "owner_or_admin_permission_check_only",
        ),
        "uncovered_race_windows": (
            "route has no practice-session preflight before deleting the presentation row",
            "stored ppt and thumbnail artifacts are not removed by the delete handler",
            "live sessions can lose their presentation link during delete because the route never retires or rehomes referencing sessions first",
        ),
        "current_assessment": "confirmed route-guard gap: delete succeeds without a live-session blocker and can detach session state from the presentation authority",
        "proof_state": "confirmed_route_guard_gap",
        "next_proof": "delete_while_session_references_presentation",
    },
)

PRESENTATION_RESOURCE_RACE_FOCUS: dict[str, str] = {
    "highest_priority_surface": "replace_presentation_in_place",
    "why": "focused proof now shows concurrent writers can both enter the version-2 replace path and the loser can explode during page rebuild, so in-place mutation must be serialized before broader rollout",
    "recommended_next_proof": "concurrent_replace_without_active_sessions",
    "recommended_next_step": "add compare-and-swap or lock around in-place replace before multi-writer rollout",
    "not_recommended_yet": "do not broaden the fix into upload_new_presentation or system-wide distributed locks until in-place replace is serialized first",
}


def _presentation_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    exc: Exception | None = None,
) -> JSONResponse:
    if status_code >= 500:
        return build_server_error(
            error_code,
            status_code=status_code,
            message=message,
            exc=exc,
            source="presentations_api",
        )

    payload = error_response(error_code, message=message)
    if details:
        payload["details"] = details

    return JSONResponse(status_code=status_code, content=payload)


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


def _normalize_source_filename(uploaded_name: str | None, fallback_key: str) -> str:
    if isinstance(uploaded_name, str) and uploaded_name.strip():
        return uploaded_name.strip()
    return f"upload-{fallback_key}.pptx"


def _storage_file_path(storage_key: str, source_filename: str) -> Path:
    upload_dir = _presentation_storage_root()
    upload_dir.mkdir(parents=True, exist_ok=True)
    extension = source_filename.rsplit(".", 1)[-1] if "." in source_filename else "pptx"
    return upload_dir / f"{storage_key}.{extension}"


async def _load_presentation_detail(
    db: AsyncSession,
    presentation_id: str,
) -> Presentation | None:
    result = await db.execute(
        select(Presentation)
        .options(selectinload(Presentation.pages))
        .where(Presentation.presentation_id == presentation_id)
    )
    presentation = result.scalar_one_or_none()
    if presentation:
        for page in presentation.pages:
            _hydrate_page_thumbnail_url(page, str(presentation.presentation_id))
    return presentation


async def _load_presentation_for_replace(
    db: AsyncSession,
    presentation_id: str,
) -> Presentation | None:
    result = await db.execute(
        select(Presentation)
        .options(
            selectinload(Presentation.pages).selectinload(Page.required_talking_points),
            selectinload(Presentation.pages).selectinload(Page.forbidden_words),
        )
        .where(Presentation.presentation_id == presentation_id)
    )
    return result.scalar_one_or_none()


async def _non_terminal_sessions_for_presentation(
    db: AsyncSession,
    presentation_id: str,
) -> list[PracticeSession]:
    result = await db.execute(
        select(PracticeSession).where(
            PracticeSession.presentation_id == presentation_id,
            PracticeSession.status.in_(_NON_TERMINAL_PRESENTATION_STATUSES),
        )
    )
    return list(result.scalars().all())


def _capture_page_level_metadata(
    pages: list[Page],
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    talking_points_by_page: dict[int, list[dict[str, Any]]] = {}
    forbidden_words_by_page: dict[int, list[dict[str, Any]]] = {}

    for page in pages:
        page_number = int(cast(int, getattr(page, "page_number", 0)) or 0)
        if page_number < 1:
            continue

        talking_points_by_page[page_number] = [
            {
                "description": point.description,
                "created_by": point.created_by,
                "is_ai_generated": bool(point.is_ai_generated),
                "confirmed_by_admin": bool(point.confirmed_by_admin),
            }
            for point in list(page.required_talking_points or [])
        ]

        forbidden_words_by_page[page_number] = [
            {
                "phrase": word.phrase,
                "suggested_alternative": word.suggested_alternative,
                "is_regex": bool(word.is_regex),
            }
            for word in list(page.forbidden_words or [])
        ]

    return talking_points_by_page, forbidden_words_by_page


async def _replace_pages_and_metadata(
    db: AsyncSession,
    presentation: Presentation,
    *,
    content: bytes,
    parsed_data: dict[str, Any],
    parser: Any,
) -> None:
    presentation_id = str(presentation.presentation_id)
    talking_points_by_page, forbidden_words_by_page = _capture_page_level_metadata(
        list(presentation.pages or [])
    )

    for page in list(presentation.pages or []):
        await db.delete(page)
    await db.flush()

    thumbnail_output_dir = _thumbnail_storage_root() / presentation_id
    if thumbnail_output_dir.exists():
        for stale_file in thumbnail_output_dir.glob("*"):
            if stale_file.is_file():
                stale_file.unlink()

    new_pages_by_number: dict[int, Page] = {}
    for page_data in parsed_data.get("pages", []):
        if not isinstance(page_data, dict):
            continue

        page_number = int(page_data.get("page_number", 0) or 0)
        if page_number < 1:
            continue

        thumbnail_result = await parser.generate_thumbnail(
            file_content=content,
            page_number=page_number,
            output_dir=str(thumbnail_output_dir),
        )

        image_url: str | None = None
        if thumbnail_result.is_success and thumbnail_result.value:
            image_url = _thumbnail_api_url(presentation_id, page_number)
        elif thumbnail_result.fallback:
            logger.warning(
                "Thumbnail generation failed during presentation replace",
                presentation_id=presentation_id,
                page_number=page_number,
                error=thumbnail_result.fallback,
            )

        page = Page(
            presentation_id=presentation_id,
            page_number=page_number,
            ocr_extracted_text=cast(str, page_data.get("extracted_text", "")),
            image_url=image_url,
            extraction_confidence=0.95,
            needs_manual_review=False,
        )
        db.add(page)
        new_pages_by_number[page_number] = page

    await db.flush()

    for page_number, page in new_pages_by_number.items():
        for point in talking_points_by_page.get(page_number, []):
            db.add(
                RequiredTalkingPoint(
                    page_id=page.page_id,
                    description=cast(str, point["description"]),
                    created_by=cast(str, point["created_by"]),
                    is_ai_generated=bool(point["is_ai_generated"]),
                    confirmed_by_admin=bool(point["confirmed_by_admin"]),
                )
            )

        for word in forbidden_words_by_page.get(page_number, []):
            db.add(
                ForbiddenWord(
                    page_id=page.page_id,
                    presentation_id=None,
                    phrase=cast(str, word["phrase"]),
                    suggested_alternative=cast(str | None, word["suggested_alternative"]),
                    is_regex=bool(word["is_regex"]),
                )
            )

    presentation.pages = list(new_pages_by_number.values())
    presentation.total_pages = int(parsed_data.get("total_pages", 0) or 0)
    presentation.ocr_progress = 1.0
    presentation.status = "ready"
    await db.commit()


@router.get("/presentations", response_model=list[PresentationResponse])
async def list_presentations(
    status: str | None = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all presentations"""
    _ = current_user
    query = select(Presentation)

    if status:
        query = query.where(Presentation.status == status)

    query = query.limit(limit)

    result = await db.execute(query)
    presentations = list(result.scalars().all())
    runtime_service = RuntimeStatusService(db)
    governance_indexes = await runtime_service.build_asset_governance_indexes()
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    for presentation in presentations:
        upload_date = RuntimeStatusService._coerce_datetime(presentation.upload_date)
        extra_anomalies: list[dict[str, Any]] = []
        if presentation.status == "failed":
            extra_anomalies.append(
                {
                    "source": "asset",
                    "kind": "presentation_failed",
                    "severity": "blocking",
                    "summary": "PPT 仍处于失败状态，需检查解析或替换链路。",
                    "detected_at": upload_date,
                    "session_id": None,
                }
            )
        elif presentation.status == "processing":
            extra_anomalies.append(
                {
                    "source": "asset",
                    "kind": "presentation_processing",
                    "severity": "warning",
                    "summary": "PPT 仍在处理中，内容尚未稳定可用。",
                    "detected_at": upload_date,
                    "session_id": None,
                }
            )

        latest_change_label = (
            f"PPT 已替换到 V{presentation.version_number}"
            if int(getattr(presentation, "version_number", 1) or 1) > 1
            else "PPT 已上传"
        )
        governance_summary = runtime_service.build_asset_governance_summary(
            governance_indexes.get("presentation", {}).get(str(presentation.presentation_id)),
            last_changed_at=upload_date,
            latest_change_type="presentation_uploaded",
            latest_change_label=latest_change_label,
            change_count_7d=1 if upload_date and upload_date >= seven_days_ago else 0,
            extra_anomalies=extra_anomalies,
        )
        setattr(presentation, "governance_summary", governance_summary)

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
        file_id = str(uuid.uuid4())
        source_filename = _normalize_source_filename(file.filename, file_id)
        file_path = _storage_file_path(file_id, source_filename)

        content = await file.read()
        _atomic_write_bytes(file_path, content)

        presentation = Presentation(
            title=title,
            file_url=str(file_path),
            file_size_bytes=len(content),
            uploaded_by_admin_id=current_user.user_id,
            status="processing",
            ocr_progress=0.0,
        )

        db.add(presentation)
        await db.commit()
        await db.refresh(presentation)
        presentation_id_value = str(presentation.presentation_id)

        parser = get_ppt_parser()
        parse_result = await parser.parse_presentation(content, source_filename)

        if parse_result.is_success and isinstance(parse_result.value, dict):
            parsed_data = cast(dict[str, Any], parse_result.value)

            setattr(presentation, "total_pages", int(parsed_data.get("total_pages", 0)))

            thumbnail_output_dir = _thumbnail_storage_root() / presentation_id_value
            for page_data in parsed_data.get("pages", []):
                if not isinstance(page_data, dict):
                    continue
                page_number = int(page_data.get("page_number", 0) or 0)
                if page_number < 1:
                    continue

                thumbnail_result = await parser.generate_thumbnail(
                    file_content=content,
                    page_number=page_number,
                    output_dir=str(thumbnail_output_dir),
                )

                image_url: str | None = None
                if thumbnail_result.is_success and thumbnail_result.value:
                    image_url = _thumbnail_api_url(presentation_id_value, page_number)
                elif thumbnail_result.fallback:
                    logger.warning(
                        "Thumbnail generation failed",
                        presentation_id=presentation_id_value,
                        page_number=page_number,
                        error=thumbnail_result.fallback,
                    )

                db.add(
                    Page(
                        presentation_id=presentation_id_value,
                        page_number=page_number,
                        ocr_extracted_text=cast(str, page_data.get("extracted_text", "")),
                        image_url=image_url,
                        extraction_confidence=0.95,
                        needs_manual_review=False,
                    )
                )

            setattr(presentation, "status", "ready")
            setattr(presentation, "ocr_progress", 1.0)
            await db.commit()

            logger.info(
                f"Presentation uploaded and parsed: {presentation_id_value} "
                f"with {presentation.total_pages} pages"
            )
        else:
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


@router.post(
    "/presentations/{presentation_id}/replace",
    response_model=PresentationDetail,
)
async def replace_presentation(
    presentation_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace a standard PPT in place while preserving presentation_id."""
    _ = current_user
    file_path: Path | None = None
    try:
        presentation = await _load_presentation_for_replace(db, presentation_id)
        if not presentation:
            return _presentation_error_response(
                status_code=404,
                error_code="[PRESENTATION_NOT_FOUND]",
                message="演示文稿不存在。",
            )

        active_sessions = await _non_terminal_sessions_for_presentation(db, presentation_id)
        if active_sessions:
            logger.warning(
                "Blocked in-place presentation replace because active sessions still reference it",
                presentation_id=presentation_id,
                active_session_count=len(active_sessions),
                active_session_ids=[session.session_id for session in active_sessions],
            )
            return JSONResponse(
                status_code=409,
                content={
                    **error_response(
                        "[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]",
                        message="当前有进行中的演练正在使用该标准PPT，请结束后再替换。",
                    ),
                    "details": {
                        "presentation_id": presentation_id,
                        "active_session_count": len(active_sessions),
                        "active_sessions": [
                            {
                                "session_id": session.session_id,
                                "status": session.status,
                            }
                            for session in active_sessions
                        ],
                    },
                },
            )

        content = await file.read()
        source_filename = _normalize_source_filename(
            file.filename,
            str(presentation.presentation_id),
        )
        next_version = int(cast(int | None, presentation.version_number) or 0) + 1
        file_path = _storage_file_path(
            f"{presentation.presentation_id}-v{next_version}",
            source_filename,
        )
        _atomic_write_bytes(file_path, content)

        if isinstance(title, str) and title.strip():
            presentation.title = title.strip()
        presentation.file_url = str(file_path)
        presentation.file_size_bytes = len(content)
        presentation.upload_date = datetime.now(timezone.utc)
        presentation.version_number = next_version
        presentation.status = "processing"
        presentation.ocr_progress = 0.0
        await db.commit()

        parser = get_ppt_parser()
        parse_result = await parser.parse_presentation(content, source_filename)

        if not parse_result.is_success or not isinstance(parse_result.value, dict):
            failed_presentation = await _load_presentation_detail(db, presentation_id)
            if failed_presentation:
                failed_presentation.status = "failed"
                failed_presentation.ocr_progress = 0.0
                await db.commit()
                failed_presentation = await _load_presentation_detail(db, presentation_id)
            logger.warning(
                "Presentation replace parse failed",
                presentation_id=presentation_id,
                version_number=next_version,
                error=parse_result.fallback,
            )
            if failed_presentation is not None:
                return failed_presentation
            return _presentation_error_response(
                status_code=404,
                error_code="[PRESENTATION_NOT_FOUND]",
                message="演示文稿不存在。",
            )

        refreshed = await _load_presentation_for_replace(db, presentation_id)
        if refreshed is None:
            return _presentation_error_response(
                status_code=404,
                error_code="[PRESENTATION_NOT_FOUND]",
                message="演示文稿不存在。",
            )

        await _replace_pages_and_metadata(
            db,
            refreshed,
            content=content,
            parsed_data=cast(dict[str, Any], parse_result.value),
            parser=parser,
        )

        logger.info(
            "Presentation replaced in place",
            presentation_id=presentation_id,
            version_number=next_version,
            total_pages=refreshed.total_pages,
        )
        detail = await _load_presentation_detail(db, presentation_id)
        if detail is None:
            return _presentation_error_response(
                status_code=404,
                error_code="[PRESENTATION_NOT_FOUND]",
                message="演示文稿不存在。",
            )
        return detail

    except HTTPException:
        raise
    except (RuntimeError, ValueError, OSError) as e:
        logger.error(
            "Failed to replace presentation in place",
            presentation_id=presentation_id,
            error=str(e),
        )
        await db.rollback()
        try:
            failed_presentation = await _load_presentation_detail(db, presentation_id)
            if failed_presentation is not None:
                failed_presentation.status = "failed"
                failed_presentation.ocr_progress = 0.0
                await db.commit()
        except Exception as mark_error:
            await db.rollback()
            logger.error(
                "Failed to mark presentation as failed after replace error",
                presentation_id=presentation_id,
                error=str(mark_error),
            )
        return build_server_error(
            "[PRESENTATION_REPLACE_FAILED]",
            message="Presentation replace failed",
            exc=e,
            presentation_id=presentation_id,
        )


@router.get("/presentations/{presentation_id}", response_model=PresentationDetail)
async def get_presentation(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presentation details"""
    _ = current_user
    presentation = await _load_presentation_detail(db, presentation_id)

    if not presentation:
        return _presentation_error_response(
            status_code=404,
            error_code="[PRESENTATION_NOT_FOUND]",
            message="演示文稿不存在。",
        )

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
        return _presentation_error_response(
            status_code=404,
            error_code="[PRESENTATION_NOT_FOUND]",
            message="演示文稿不存在。",
        )

    is_uploader = presentation.uploaded_by_admin_id == current_user.user_id
    is_admin = getattr(current_user, "role", "") == "admin"
    if not is_uploader and not is_admin:
        return _presentation_error_response(
            status_code=403,
            error_code="[PRESENTATION_DELETE_FORBIDDEN]",
            message="你没有权限删除该演示文稿。",
            details={
                "presentation_id": presentation_id,
                "current_user_id": str(current_user.user_id),
            },
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
    _ = current_user
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
        return _presentation_error_response(
            status_code=404,
            error_code="[PRESENTATION_PAGE_NOT_FOUND]",
            message="演示页不存在。",
        )

    thumbnail_path = _thumbnail_file_path(presentation_id, page_number)
    if not thumbnail_path.exists():
        return _presentation_error_response(
            status_code=404,
            error_code="[PRESENTATION_THUMBNAIL_NOT_FOUND]",
            message="演示页缩略图不存在。",
        )

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
    _ = current_user
    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id, Page.page_number == page_number
        )
    )
    page = page_result.scalar_one_or_none()

    if not page:
        return _presentation_error_response(
            status_code=404,
            error_code="[PRESENTATION_PAGE_NOT_FOUND]",
            message="演示页不存在。",
        )

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
    _ = current_user
    page_result = await db.execute(
        select(Page).where(
            Page.presentation_id == presentation_id, Page.page_number == page_number
        )
    )
    page = page_result.scalar_one_or_none()

    if not page:
        return _presentation_error_response(
            status_code=404,
            error_code="[PRESENTATION_PAGE_NOT_FOUND]",
            message="演示页不存在。",
        )

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
    _ = current_user
    result = await db.execute(
        select(ForbiddenWord).where(
            (ForbiddenWord.presentation_id == presentation_id)
            | (ForbiddenWord.page_id == None)
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
    _ = current_user
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

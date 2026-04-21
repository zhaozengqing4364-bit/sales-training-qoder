"""Per-user PPT progress service for G-05 resume prompts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import Presentation, UserPresentationProgress
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class UserPresentationProgressService:
    """Read and write the current user's last viewed/practiced PPT page."""

    @staticmethod
    def _payload(progress: UserPresentationProgress) -> dict[str, Any]:
        return {
            "source": "user_presentation_progress",
            "user_id": str(progress.user_id),
            "presentation_id": str(progress.presentation_id),
            "last_page_number": int(progress.last_page_number),
            "last_session_id": (
                str(progress.last_session_id) if progress.last_session_id else None
            ),
            "last_practice_at": progress.last_practice_at.isoformat()
            if progress.last_practice_at
            else None,
            "updated_at": progress.updated_at.isoformat()
            if progress.updated_at
            else None,
        }

    @staticmethod
    async def _load_presentation(
        db: AsyncSession,
        presentation_id: str,
    ) -> Presentation | None:
        result = await db.execute(
            select(Presentation).where(Presentation.presentation_id == presentation_id)
        )
        return result.scalar_one_or_none()

    async def get_progress(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        presentation_id: str,
    ) -> Result[dict[str, Any] | None]:
        try:
            result = await db.execute(
                select(UserPresentationProgress).where(
                    UserPresentationProgress.user_id == user_id,
                    UserPresentationProgress.presentation_id == presentation_id,
                )
            )
            progress = result.scalar_one_or_none()
            return Result.ok(self._payload(progress) if progress else None)
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            logger.error(
                "user_presentation_progress_get_failed",
                user_id=user_id,
                presentation_id=presentation_id,
                error=str(exc),
            )
            return Result.fail(f"[PRESENTATION_PROGRESS_GET_FAILED] {exc}")

    async def save_progress(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        presentation_id: str,
        last_page_number: int,
        session_id: str | None = None,
    ) -> Result[dict[str, Any]]:
        try:
            page_number = int(last_page_number)
            if page_number < 1:
                return Result.fail("[INVALID_PRESENTATION_PAGE] page must be >= 1")

            presentation = await self._load_presentation(db, presentation_id)
            if presentation is None:
                return Result.fail("[PRESENTATION_NOT_FOUND] Presentation not found")

            total_pages = int(getattr(presentation, "total_pages", 0) or 0)
            if total_pages > 0 and page_number > total_pages:
                logger.warning(
                    "user_presentation_progress_invalid_page",
                    user_id=user_id,
                    presentation_id=presentation_id,
                    page_number=page_number,
                    total_pages=total_pages,
                )
                return Result.fail(
                    "[INVALID_PRESENTATION_PAGE] page exceeds presentation total_pages"
                )

            result = await db.execute(
                select(UserPresentationProgress).where(
                    UserPresentationProgress.user_id == user_id,
                    UserPresentationProgress.presentation_id == presentation_id,
                )
            )
            progress = result.scalar_one_or_none()
            now = datetime.now(UTC)
            if progress is None:
                progress = UserPresentationProgress(
                    user_id=user_id,
                    presentation_id=presentation_id,
                    last_page_number=page_number,
                    last_session_id=session_id,
                    last_practice_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(progress)
            else:
                progress.last_page_number = page_number
                progress.last_session_id = session_id
                progress.last_practice_at = now
                progress.updated_at = now

            await db.commit()
            await db.refresh(progress)
            return Result.ok(self._payload(progress))
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            await db.rollback()
            logger.error(
                "user_presentation_progress_save_failed",
                user_id=user_id,
                presentation_id=presentation_id,
                page_number=last_page_number,
                error=str(exc),
            )
            return Result.fail(f"[PRESENTATION_PROGRESS_SAVE_FAILED] {exc}")

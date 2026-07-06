from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.schemas import SessionCreate
from common.services.practice_session_service import (
    PracticeServiceError,
    PracticeSessionCreateService,
)


class ExternalSessionStartError(Exception):
    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(message or error_code)


@dataclass(frozen=True, slots=True)
class ExternalSessionStartResult:
    session_id: str
    status: str
    voice_mode: str | None
    practice_template_id: str | None


class ExternalSessionStartService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        create_service: PracticeSessionCreateService | None = None,
    ) -> None:
        self._db = db
        self._create_service = create_service

    async def start(
        self,
        session_data: SessionCreate,
        *,
        current_user: User,
        external_binding: dict[str, Any] | None = None,
    ) -> ExternalSessionStartResult:
        try:
            create_service = self._create_service or PracticeSessionCreateService(self._db)
            result = await create_service.create_session(
                session_data,
                current_user=current_user,
                external_binding=external_binding,
            )
        except PracticeServiceError as exc:
            raise ExternalSessionStartError(
                exc.error_code,
                status_code=exc.status_code,
                message=exc.message,
                details=exc.details,
            ) from exc
        return ExternalSessionStartResult(
            session_id=str(result.session.session_id),
            status=str(result.session.status),
            voice_mode=(
                str(result.session.voice_mode) if result.session.voice_mode else None
            ),
            practice_template_id=(
                str(result.session.practice_template_id)
                if result.session.practice_template_id
                else None
            ),
        )

"""Bounded maintenance for expired or cancelled multipart uploads."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from audio_assessment.contracts import AudioSubmissionState, UploadSessionState
from audio_assessment.models import (
    AudioSubmission,
    AudioUploadPart,
    AudioUploadSession,
)
from audio_assessment.ports import AudioObjectStoragePort
from audio_assessment.storage import AudioStorageError
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class AudioUploadCleanupResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claimed_count: int = Field(ge=0)
    expired_count: int = Field(ge=0)
    cleaned_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class _CleanupClaim:
    upload_session_id: str
    claim_token: str
    object_keys: tuple[str, ...]


class AudioUploadMaintenanceService:
    """Clean terminal multipart objects without holding a DB transaction over IO."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        storage: AudioObjectStoragePort,
        stale_claim_seconds: int = 15 * 60,
    ) -> None:
        if stale_claim_seconds < 60:
            raise ValueError("stale_claim_seconds must be at least 60")
        self._session_factory = session_factory
        self._storage = storage
        self._stale_claim_seconds = stale_claim_seconds

    async def run_once(self, *, limit: int = 100) -> AudioUploadCleanupResult:
        if limit < 1 or limit > 1_000:
            raise ValueError("cleanup limit must be between 1 and 1000")
        claims, expired_count = await self._claim(limit=limit)
        cleaned_count = 0
        failed_count = 0
        for claim in claims:
            try:
                await self._storage.delete(claim.object_keys)
            except (AudioStorageError, OSError) as exc:
                failed_count += 1
                await self._release(claim)
                logger.warning(
                    "audio upload cleanup failed",
                    extra={
                        "upload_session_id": claim.upload_session_id,
                        "error_type": type(exc).__name__,
                    },
                )
                continue
            if await self._complete(claim):
                cleaned_count += 1
        return AudioUploadCleanupResult(
            claimed_count=len(claims),
            expired_count=expired_count,
            cleaned_count=cleaned_count,
            failed_count=failed_count,
        )

    async def _claim(self, *, limit: int) -> tuple[list[_CleanupClaim], int]:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=self._stale_claim_seconds)
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(AudioUploadSession)
                        .where(AudioUploadSession.cleanup_completed_at.is_(None))
                        .where(
                            or_(
                                AudioUploadSession.cleanup_started_at.is_(None),
                                AudioUploadSession.cleanup_started_at <= stale_before,
                            )
                        )
                        .where(
                            or_(
                                AudioUploadSession.state.in_(
                                    {
                                        UploadSessionState.CANCELLED.value,
                                        UploadSessionState.EXPIRED.value,
                                    }
                                ),
                                and_(
                                    AudioUploadSession.state
                                    == UploadSessionState.UPLOADING.value,
                                    AudioUploadSession.expires_at <= now,
                                ),
                            )
                        )
                        .order_by(AudioUploadSession.expires_at)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                await session.rollback()
                return [], 0

            expired_count = 0
            tokens: dict[str, str] = {}
            for row in rows:
                if row.state == UploadSessionState.UPLOADING.value:
                    row.state = UploadSessionState.EXPIRED.value
                    row.version += 1
                    expired_count += 1
                    submission = await session.get(
                        AudioSubmission,
                        row.submission_id,
                        with_for_update=True,
                    )
                    if (
                        submission is not None
                        and submission.state == AudioSubmissionState.UPLOADING.value
                    ):
                        submission.state = AudioSubmissionState.EXPIRED.value
                        submission.version += 1
                token = str(uuid.uuid4())
                row.cleanup_started_at = now
                row.cleanup_claim_token = token
                row.cleanup_attempts += 1
                tokens[row.upload_session_id] = token

            parts = (
                (
                    await session.execute(
                        select(AudioUploadPart)
                        .where(AudioUploadPart.upload_session_id.in_(tuple(tokens)))
                        .order_by(
                            AudioUploadPart.upload_session_id,
                            AudioUploadPart.part_number,
                        )
                    )
                )
                .scalars()
                .all()
            )
            keys: dict[str, list[str]] = {upload_id: [] for upload_id in tokens}
            for part in parts:
                keys[part.upload_session_id].append(part.object_key)
            await session.commit()
            return (
                [
                    _CleanupClaim(
                        upload_session_id=row.upload_session_id,
                        claim_token=tokens[row.upload_session_id],
                        object_keys=tuple(keys[row.upload_session_id]),
                    )
                    for row in rows
                ],
                expired_count,
            )

    async def _complete(self, claim: _CleanupClaim) -> bool:
        async with self._session_factory() as session:
            row = await session.get(
                AudioUploadSession,
                claim.upload_session_id,
                with_for_update=True,
            )
            if (
                row is None
                or row.cleanup_completed_at is not None
                or row.cleanup_claim_token != claim.claim_token
            ):
                await session.rollback()
                return False
            row.cleanup_completed_at = datetime.now(UTC)
            row.cleanup_claim_token = None
            await session.commit()
            return True

    async def _release(self, claim: _CleanupClaim) -> None:
        async with self._session_factory() as session:
            row = await session.get(
                AudioUploadSession,
                claim.upload_session_id,
                with_for_update=True,
            )
            if (
                row is not None
                and row.cleanup_completed_at is None
                and row.cleanup_claim_token == claim.claim_token
            ):
                row.cleanup_started_at = None
                row.cleanup_claim_token = None
                await session.commit()
            else:
                await session.rollback()


__all__ = ["AudioUploadCleanupResult", "AudioUploadMaintenanceService"]

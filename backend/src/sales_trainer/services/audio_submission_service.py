"""Read-only adapter for legacy Sales Trainer audio history.

New audio writes belong exclusively to ``audio_assessment``.  This adapter remains
only until the legacy history screens are retired; it cannot upload, transcribe,
score, retry, or mutate legacy submissions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.cos.signing import CosConfigError, get_cos_signing_service
from common.db.models import User
from common.oss.signing import OssConfigError, get_oss_signing_service
from common.teams.policy import TeamDataScope
from sales_trainer.models import (
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioTranscript,
)
from sales_trainer.services.audio_submission_lineage import submission_lineage_fields

DEFAULT_AUDIO_FILE_URL_EXPIRES_SECONDS = 3600
_OBJECT_STORAGE_UNAVAILABLE_MESSAGE = "对象存储暂不可用，请稍后重试或联系管理员。"


@dataclass(frozen=True)
class AudioFileAccess:
    mode: str
    path: Path | None
    redirect_url: str | None
    media_type: str
    filename: str


class AudioSubmissionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AudioSubmissionService:
    """Legacy history query service; intentionally exposes no write methods."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_submission(
        self,
        submission_id: str,
        *,
        actor: User,
        allow_admin: bool = False,
        team_scope: TeamDataScope | None = None,
    ) -> SalesTrainerAudioSubmission | None:
        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            return None
        if allow_admin:
            return submission
        if team_scope is not None and team_scope.allows_learner(submission.user_id):
            return submission
        if submission.user_id != str(actor.user_id):
            raise AudioSubmissionServiceError("[ACCESS_DENIED]", "无权查看该音频。", 403)
        return submission

    async def resolve_audio_file_access(
        self,
        submission_id: str,
        *,
        actor: User,
        allow_admin: bool = False,
        team_scope: TeamDataScope | None = None,
    ) -> AudioFileAccess:
        submission = await self.get_submission(
            submission_id,
            actor=actor,
            allow_admin=allow_admin,
            team_scope=team_scope,
        )
        if submission is None:
            raise AudioSubmissionServiceError(
                "[AUDIO_SUBMISSION_NOT_FOUND]",
                "音频提交不存在。",
                status_code=404,
            )

        storage_key = str(submission.storage_key or "")
        local_path = Path(storage_key)
        if local_path.exists():
            resolved_path = local_path.resolve()
            storage_root = Path(
                os.getenv(
                    "SALES_TRAINER_AUDIO_STORAGE_PATH",
                    "./data/sales_trainer_audio",
                )
            ).resolve()
            if storage_root not in (resolved_path, *resolved_path.parents):
                raise AudioSubmissionServiceError(
                    "[AUDIO_FILE_ACCESS_DENIED]",
                    "音频文件不在允许的存储目录内。",
                    status_code=403,
                )
            if not resolved_path.is_file():
                raise AudioSubmissionServiceError(
                    "[AUDIO_FILE_NOT_FOUND]",
                    "音频文件不存在。",
                    status_code=404,
                )
            return AudioFileAccess(
                mode="local",
                path=resolved_path,
                redirect_url=None,
                media_type=str(submission.content_type or "application/octet-stream"),
                filename=str(submission.original_filename or resolved_path.name),
            )

        if _is_object_storage_key(storage_key):
            try:
                signed_url = _generate_object_storage_get_url(storage_key)
            except OssConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[OSS_NOT_CONFIGURED]",
                    _OBJECT_STORAGE_UNAVAILABLE_MESSAGE,
                    status_code=503,
                ) from exc
            except CosConfigError as exc:
                raise AudioSubmissionServiceError(
                    "[COS_NOT_CONFIGURED]",
                    _OBJECT_STORAGE_UNAVAILABLE_MESSAGE,
                    status_code=503,
                ) from exc
            return AudioFileAccess(
                mode="redirect",
                path=None,
                redirect_url=signed_url,
                media_type=str(submission.content_type or "application/octet-stream"),
                filename=str(submission.original_filename or "audio"),
            )

        raise AudioSubmissionServiceError(
            "[AUDIO_FILE_NOT_FOUND]",
            "音频文件不存在。",
            status_code=404,
        )

    async def list_submissions(
        self,
        *,
        user_id: str | None = None,
        team_scope: TeamDataScope | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerAudioSubmission], int]:
        stmt = select(SalesTrainerAudioSubmission)
        count_stmt = select(func.count()).select_from(SalesTrainerAudioSubmission)
        if user_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
        if team_scope is not None and not team_scope.unrestricted:
            stmt = stmt.where(
                SalesTrainerAudioSubmission.user_id.in_(team_scope.learner_ids)
            )
            count_stmt = count_stmt.where(
                SalesTrainerAudioSubmission.user_id.in_(team_scope.learner_ids)
            )
        result = await self._db.execute(
            stmt.order_by(SalesTrainerAudioSubmission.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def list_score_results(
        self,
        *,
        user_id: str | None = None,
        submission_id: str | None = None,
        team_scope: TeamDataScope | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerAudioScoreResult], int]:
        stmt = select(SalesTrainerAudioScoreResult).join(
            SalesTrainerAudioSubmission,
            SalesTrainerAudioScoreResult.submission_id
            == SalesTrainerAudioSubmission.submission_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(SalesTrainerAudioScoreResult)
            .join(
                SalesTrainerAudioSubmission,
                SalesTrainerAudioScoreResult.submission_id
                == SalesTrainerAudioSubmission.submission_id,
            )
        )
        if user_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
        if submission_id:
            stmt = stmt.where(SalesTrainerAudioScoreResult.submission_id == submission_id)
            count_stmt = count_stmt.where(
                SalesTrainerAudioScoreResult.submission_id == submission_id
            )
        if team_scope is not None and not team_scope.unrestricted:
            stmt = stmt.where(
                SalesTrainerAudioSubmission.user_id.in_(team_scope.learner_ids)
            )
            count_stmt = count_stmt.where(
                SalesTrainerAudioSubmission.user_id.in_(team_scope.learner_ids)
            )
        result = await self._db.execute(
            stmt.order_by(SalesTrainerAudioScoreResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def serialize_submission(
        self, submission: SalesTrainerAudioSubmission
    ) -> dict[str, Any]:
        submission_id = str(submission.submission_id)
        transcript = await self._get_transcript(submission_id)
        score = await self._get_latest_score(submission_id)
        user = await self._db.get(User, submission.user_id)
        task_brief_snapshot = (
            submission.task_brief_snapshot
            if isinstance(submission.task_brief_snapshot, dict)
            else None
        )
        lineage = submission_lineage_fields(task_brief_snapshot)
        return {
            "submission_id": submission.submission_id,
            "unit_id": submission.unit_id,
            "user_id": submission.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "purpose": submission.purpose,
            "original_filename": submission.original_filename,
            "content_type": submission.content_type,
            "size_bytes": int(submission.size_bytes),
            "storage_key": submission.storage_key,
            "file_hash": submission.file_hash,
            "duration_seconds": (
                float(submission.duration_seconds)
                if submission.duration_seconds is not None
                else None
            ),
            "source_page": submission.source_page,
            "confirmed_material_version_id": submission.confirmed_material_version_id,
            "confirmed_material_at": submission.confirmed_material_at,
            "material_snapshot": submission.material_snapshot,
            "score_scheme_snapshot": submission.score_scheme_snapshot,
            "task_brief_snapshot": submission.task_brief_snapshot,
            "path_key": lineage["path_key"],
            "path_revision_id": lineage["path_revision_id"],
            "path_revision_no": lineage["path_revision_no"],
            "module_key": lineage["module_key"],
            "legacy_snapshot_only": lineage["legacy_snapshot_only"],
            "status": submission.status,
            "error_code": submission.error_code,
            "error_message": submission.error_message,
            "created_at": submission.created_at,
            "updated_at": submission.updated_at,
            "transcript": _serialize_transcript(transcript) if transcript else None,
            "score_result": (
                _serialize_score_with_lineage(score, task_brief_snapshot)
                if score
                else None
            ),
        }

    async def serialize_score_result(
        self,
        score: SalesTrainerAudioScoreResult,
    ) -> dict[str, Any]:
        submission = await self._db.get(
            SalesTrainerAudioSubmission, score.submission_id
        )
        task_brief_snapshot = (
            submission.task_brief_snapshot
            if submission is not None
            and isinstance(submission.task_brief_snapshot, dict)
            else None
        )
        return _serialize_score_with_lineage(score, task_brief_snapshot)

    async def _get_transcript(
        self, submission_id: str
    ) -> SalesTrainerAudioTranscript | None:
        result = await self._db.execute(
            select(SalesTrainerAudioTranscript).where(
                SalesTrainerAudioTranscript.submission_id == submission_id
            )
        )
        return result.scalar_one_or_none()

    async def _get_latest_score(
        self, submission_id: str
    ) -> SalesTrainerAudioScoreResult | None:
        result = await self._db.execute(
            select(SalesTrainerAudioScoreResult)
            .where(SalesTrainerAudioScoreResult.submission_id == submission_id)
            .order_by(SalesTrainerAudioScoreResult.created_at.desc())
        )
        return result.scalars().first()


def _is_object_storage_key(storage_key: str) -> bool:
    return (
        storage_key.startswith("oss://")
        or storage_key.startswith("cos://")
        or storage_key.startswith("sales-trainer/")
        or storage_key.startswith("audio/")
    )


def _normalize_object_storage_key(storage_key: str) -> str:
    if storage_key.startswith("oss://"):
        return storage_key.removeprefix("oss://")
    if storage_key.startswith("cos://"):
        return storage_key.removeprefix("cos://")
    return storage_key


def _resolve_object_storage_backend(storage_key: str) -> str:
    if storage_key.startswith("cos://"):
        return "cos"
    if storage_key.startswith("oss://"):
        return "oss"
    return os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local").strip().lower()


def _resolve_file_url_expires_seconds() -> int:
    raw_value = os.getenv(
        "SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS",
        str(DEFAULT_AUDIO_FILE_URL_EXPIRES_SECONDS),
    )
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise AudioSubmissionServiceError(
            "[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]",
            "音频文件访问链接有效期配置非法。",
            status_code=500,
        ) from exc
    if value <= 0:
        raise AudioSubmissionServiceError(
            "[AUDIO_FILE_URL_EXPIRES_CONFIG_INVALID]",
            "音频文件访问链接有效期配置非法。",
            status_code=500,
        )
    return value


def _generate_object_storage_get_url(storage_key: str) -> str:
    object_key = _normalize_object_storage_key(storage_key)
    backend = _resolve_object_storage_backend(storage_key)
    if backend == "cos":
        return str(
            get_cos_signing_service().generate_get_url(
                object_key,
                expires=_resolve_file_url_expires_seconds(),
            )
        )
    return str(
        get_oss_signing_service().generate_get_url(
            object_key,
            expires=_resolve_file_url_expires_seconds(),
        )
    )


def _serialize_transcript(
    transcript: SalesTrainerAudioTranscript,
) -> dict[str, Any]:
    return {
        "transcript_id": transcript.transcript_id,
        "provider": transcript.provider,
        "transcript_text": transcript.transcript_text,
        "raw_payload": transcript.raw_payload,
        "started_at": transcript.started_at,
        "completed_at": transcript.completed_at,
        "created_at": transcript.created_at,
    }


def _serialize_score(score: SalesTrainerAudioScoreResult) -> dict[str, Any]:
    return {
        "score_id": score.score_id,
        "submission_id": score.submission_id,
        "prompt_id": score.prompt_id,
        "prompt_version": score.prompt_version,
        "prompt_hash": score.prompt_hash,
        "deucate_model": score.deucate_model,
        "transcript_snapshot": score.transcript_snapshot,
        "total_score": float(score.total_score) if score.total_score is not None else None,
        "passed": score.passed,
        "summary": score.summary,
        "strengths": score.strengths or [],
        "improvements": score.improvements or [],
        "dimension_scores": score.dimension_scores or {},
        "raw_response": score.raw_response,
        "error_code": score.error_code,
        "error_message": score.error_message,
        "latency_ms": score.latency_ms,
        "created_at": score.created_at,
    }


def _serialize_score_with_lineage(
    score: SalesTrainerAudioScoreResult,
    task_brief_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    lineage = submission_lineage_fields(task_brief_snapshot)
    return {
        **_serialize_score(score),
        "path_key": lineage["path_key"],
        "path_revision_id": lineage["path_revision_id"],
        "path_revision_no": lineage["path_revision_no"],
        "module_key": lineage["module_key"],
        "legacy_snapshot_only": lineage["legacy_snapshot_only"],
    }


__all__ = [
    "AudioFileAccess",
    "AudioSubmissionService",
    "AudioSubmissionServiceError",
]

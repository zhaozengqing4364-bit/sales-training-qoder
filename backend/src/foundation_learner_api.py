"""Application-root learner HTTP adapter for the single training entry."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi import Path as ApiPath
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audio_assessment.models import (
    AudioArtifact,
    AudioCommandAudit,
    AudioSubmission,
    AudioUploadPart,
    AudioUploadSession,
)
from audio_assessment.ports import AudioObjectStoragePort
from audio_assessment.storage import (
    AudioStorageError,
    LocalAudioObjectStorage,
    build_audio_object_storage,
)
from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.storage import get_document_storage_service
from learning.content_access import verify_learner_source_asset_grant
from learning.models import LearningCommandAudit, LearningSourceDocumentRevision
from learning.multimedia import SUPPORTED_SOURCE_FILE_TYPES, preview_root
from learning.source_ingestion import (
    SourceFileType,
    source_document_file_path,
)
from newcomer_foundation_composition import (
    FoundationActivityRuntimeAdapter,
    SQLAlchemyFoundationNotificationReader,
)
from newcomer_training.activity_application import (
    ActivityApplicationService,
    ActivityCommandValue,
)
from newcomer_training.application import CommandActor
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.journey import JourneyQueryService
from newcomer_training.notifications import NotificationInboxQueryService
from sales_trainer.permissions import can_learn_newcomer_training_path
from task_runtime.composition import get_application_task_registry
from task_runtime.contracts import ActorContext, TaskProjection, TaskState
from task_runtime.errors import TaskRuntimeError
from task_runtime.registry import TaskRegistry
from task_runtime.repository import SQLAlchemyTaskRuntime

router = APIRouter(prefix="/newcomer-training", tags=["newcomer-training"])


def get_foundation_organization_id() -> str:
    return os.getenv("NEWCOMER_FOUNDATION_ORGANIZATION_ID", "default").strip() or (
        "default"
    )


async def get_learner_actor(
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_foundation_organization_id),
) -> CommandActor:
    capabilities = (
        frozenset({"newcomer.journey.read", "newcomer.activity.execute"})
        if can_learn_newcomer_training_path(current_user)
        else frozenset()
    )
    return CommandActor(
        organization_id=organization_id,
        actor_id=str(current_user.user_id),
        capabilities=capabilities,
    )


def get_foundation_task_registry() -> TaskRegistry:
    return get_application_task_registry()


@lru_cache(maxsize=1)
def get_audio_object_storage() -> AudioObjectStoragePort:
    return build_audio_object_storage()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _success(value: object) -> JSONResponse:
    return JSONResponse(content=jsonable_encoder(success_response(value)))


def _error(exc: NewcomerTrainingError | TaskRuntimeError) -> JSONResponse:
    status = getattr(exc, "status_code", 409)
    if isinstance(exc, TaskRuntimeError):
        status_by_code = {
            "[TASK_NOT_FOUND]": 404,
            "[TASK_ACCESS_DENIED]": 404,
            "[IDEMPOTENCY_KEY_REUSED]": 409,
            "[TASK_STATE_TRANSITION_INVALID]": 409,
        }
        status = status_by_code.get(exc.code, 422)
    return JSONResponse(
        status_code=int(status),
        content=error_response(
            exc.code,
            message=exc.message,
            details=getattr(exc, "details", None),
        ),
    )


@router.get("/journey", response_model=None)
async def get_journey(
    expected_enrollment_version: int | None = None,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        projection = await JourneyQueryService(db).get_my_journey(
            actor=actor,
            expected_enrollment_version=expected_enrollment_version,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(projection)


@router.get("/activities/{activity_id}", response_model=None)
async def get_activity_workspace(
    activity_id: str,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        workspace = await ActivityApplicationService(
            db,
            runtime=FoundationActivityRuntimeAdapter(
                db,
                task_registry=registry,
                audio_storage=get_audio_object_storage(),
            ),
        ).get_workspace(actor=actor, activity_id=activity_id)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(workspace)


@router.post("/activities/{activity_id}/commands", response_model=None)
async def execute_activity_command(
    activity_id: str,
    command: ActivityCommandValue,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=200),
    ],
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        workspace = await ActivityApplicationService(
            db,
            runtime=FoundationActivityRuntimeAdapter(
                db,
                task_registry=registry,
                audio_storage=get_audio_object_storage(),
            ),
        ).execute(
            actor=actor,
            activity_id=activity_id,
            command=command,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        await db.rollback()
        return _error(exc)
    return _success(workspace)


@router.get(
    "/activities/{activity_id}/assets/{asset_token}/preview/pages/{page}",
    response_model=None,
)
async def get_lesson_asset_preview_page(
    activity_id: str,
    asset_token: str,
    page: Annotated[int, ApiPath(ge=1, le=10_000)],
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> Response:
    return await _serve_learner_source_asset(
        activity_id=activity_id,
        asset_token=asset_token,
        actor=actor,
        db=db,
        registry=registry,
        mode="preview",
        page=page,
    )


@router.get(
    "/activities/{activity_id}/assets/{asset_token}/playback",
    response_model=None,
)
async def get_lesson_asset_playback(
    activity_id: str,
    asset_token: str,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> Response:
    return await _serve_learner_source_asset(
        activity_id=activity_id,
        asset_token=asset_token,
        actor=actor,
        db=db,
        registry=registry,
        mode="playback",
    )


@router.get(
    "/activities/{activity_id}/assets/{asset_token}/download",
    response_model=None,
)
async def download_lesson_asset(
    activity_id: str,
    asset_token: str,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> Response:
    return await _serve_learner_source_asset(
        activity_id=activity_id,
        asset_token=asset_token,
        actor=actor,
        db=db,
        registry=registry,
        mode="download",
    )


@router.put(
    "/audio-upload-sessions/{upload_session_id}/parts/{part_number}/content",
    response_model=None,
)
async def upload_local_audio_part(
    upload_session_id: str,
    part_number: int,
    request: Request,
    x_audio_sha256: Annotated[
        str,
        Header(alias="X-Audio-Sha256", pattern=r"^[0-9a-f]{64}$"),
    ],
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
) -> Response:
    storage = get_audio_object_storage()
    if not isinstance(storage, LocalAudioObjectStorage):
        return _error(
            NewcomerTrainingError(
                "[AUDIO_DIRECT_UPLOAD_REQUIRED]",
                "当前环境应使用对象存储直传地址。",
                409,
            )
        )
    upload = await db.get(AudioUploadSession, upload_session_id)
    part = await db.scalar(
        select(AudioUploadPart)
        .where(AudioUploadPart.upload_session_id == upload_session_id)
        .where(AudioUploadPart.part_number == part_number)
        .limit(1)
    )
    if (
        upload is None
        or part is None
        or upload.organization_id != actor.organization_id
        or upload.learner_id != actor.actor_id
        or "newcomer.activity.execute" not in actor.capabilities
    ):
        await _audit_audio_access(
            db,
            actor=actor,
            object_type="audio_upload_session",
            object_id=upload_session_id,
            command="upload_audio_part",
            result="denied",
        )
        await db.commit()
        return _error(
            NewcomerTrainingError(
                "[AUDIO_UPLOAD_SESSION_NOT_FOUND]",
                "上传会话不存在或不可访问。",
                404,
            )
        )
    if upload.state != "uploading" or _aware(upload.expires_at) <= datetime.now(UTC):
        return _error(
            NewcomerTrainingError(
                "[AUDIO_UPLOAD_SESSION_EXPIRED]",
                "上传会话已结束，本地草稿仍保留，可重新开始上传。",
                409,
            )
        )
    if (
        x_audio_sha256 != part.declared_sha256
        or request.headers.get("content-type", "").split(";", 1)[0]
        != upload.content_type
    ):
        return _error(
            NewcomerTrainingError(
                "[AUDIO_UPLOAD_PART_MISMATCH]",
                "上传分片与本地草稿不一致。",
                409,
            )
        )
    object_key = part.object_key
    declared_size_bytes = part.declared_size_bytes
    declared_sha256 = part.declared_sha256
    await db.rollback()
    try:
        await storage.write_part_stream(
            object_key=object_key,
            chunks=request.stream(),
            expected_size_bytes=declared_size_bytes,
            expected_sha256=declared_sha256,
        )
    except AudioStorageError as exc:
        return _error(
            NewcomerTrainingError(
                f"[{exc.code.upper()}]",
                exc.safe_message,
                503 if exc.retryable else 422,
            )
        )
    await _audit_audio_access(
        db,
        actor=actor,
        object_type="audio_upload_session",
        object_id=upload_session_id,
        command="upload_audio_part",
        result="succeeded",
    )
    await db.commit()
    return Response(status_code=204)


@router.get("/audio-artifacts/{artifact_id}/playback", response_model=None)
async def get_audio_artifact_playback(
    artifact_id: str,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
) -> Response:
    artifact = await db.get(AudioArtifact, artifact_id)
    submission = (
        await db.get(AudioSubmission, artifact.submission_id)
        if artifact is not None
        else None
    )
    if (
        artifact is None
        or submission is None
        or artifact.organization_id != actor.organization_id
        or submission.learner_id != actor.actor_id
        or "newcomer.activity.execute" not in actor.capabilities
    ):
        await _audit_audio_access(
            db,
            actor=actor,
            object_type="audio_artifact",
            object_id=artifact_id,
            command="listen_audio_artifact",
            result="denied",
        )
        await db.commit()
        return _error(
            NewcomerTrainingError(
                "[AUDIO_ARTIFACT_NOT_FOUND]",
                "录音不存在或不可访问。",
                404,
            )
        )
    object_key = str(artifact.manifest_json.get("object_key") or "")
    if artifact.kind != "normalized" or not object_key:
        return _error(
            NewcomerTrainingError(
                "[AUDIO_ARTIFACT_NOT_READY]",
                "录音试听文件尚未准备完成。",
                409,
            )
        )
    storage = get_audio_object_storage()
    if isinstance(storage, LocalAudioObjectStorage):
        path = (storage.root / object_key).resolve()
        if storage.root not in path.parents or not path.is_file():
            await _audit_audio_access(
                db,
                actor=actor,
                object_type="audio_artifact",
                object_id=artifact_id,
                command="listen_audio_artifact",
                result="failed",
            )
            await db.commit()
            return _error(
                NewcomerTrainingError(
                    "[AUDIO_ARTIFACT_NOT_READY]",
                    "录音试听文件暂时不可用。",
                    409,
                )
            )
        await _audit_audio_access(
            db,
            actor=actor,
            object_type="audio_artifact",
            object_id=artifact_id,
            command="listen_audio_artifact",
            result="succeeded",
        )
        await db.commit()
        return FileResponse(
            path,
            media_type=artifact.content_type,
            filename="training-recording.wav",
        )
    try:
        url = storage.signed_get_url(object_key, expires_seconds=300)
    except AudioStorageError as exc:
        await _audit_audio_access(
            db,
            actor=actor,
            object_type="audio_artifact",
            object_id=artifact_id,
            command="listen_audio_artifact",
            result="failed",
        )
        await db.commit()
        return _error(
            NewcomerTrainingError(
                f"[{exc.code.upper()}]",
                exc.safe_message,
                503 if exc.retryable else 422,
            )
        )
    await _audit_audio_access(
        db,
        actor=actor,
        object_type="audio_artifact",
        object_id=artifact_id,
        command="listen_audio_artifact",
        result="succeeded",
    )
    await db.commit()
    return RedirectResponse(url=url, status_code=307)


@router.get("/notifications", response_model=None)
async def list_notifications(
    read_state: Literal["all", "unread", "read"] = "all",
    notification_type: Literal[
        "system", "tip", "reminder", "achievement", "ai_coach"
    ]
    | None = None,
    created_from: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["-created_at", "created_at"] = "-created_at",
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await NotificationInboxQueryService(
            SQLAlchemyFoundationNotificationReader(db)
        ).get_my_notifications(
            actor=actor,
            read_state=read_state,
            notification_type=notification_type,
            created_from=created_from,
            page=page,
            page_size=page_size,
            sort=sort,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/tasks", response_model=None)
async def list_task_statuses(
    state: TaskState | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    if "newcomer.journey.read" not in actor.capabilities:
        return _error(
            NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有查看训练任务的权限。", 403
            )
        )
    runtime = SQLAlchemyTaskRuntime(db, registry=registry)
    page_result = await runtime.list_for_actor(
        _task_actor(actor),
        page=page,
        page_size=page_size,
        state=state,
    )
    return _success(
        {
            "contract_version": "task_status_page_v1",
            "items": [_task_status(task) for task in page_result.items],
            "total": page_result.total,
            "page": page_result.page,
            "page_size": page_result.page_size,
            "has_more": page_result.has_more,
        }
    )


@router.get("/tasks/{task_id}", response_model=None)
async def get_task_status(
    task_id: str,
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    runtime = SQLAlchemyTaskRuntime(db, registry=registry)
    try:
        task = await runtime.get(task_id, _task_actor(actor))
    except TaskRuntimeError as exc:
        return _error(exc)
    return _success(_task_status(task))


@router.post("/tasks/{task_id}/commands/request-cancel", response_model=None)
async def request_task_cancel(
    task_id: str,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=200),
    ],
    actor: CommandActor = Depends(get_learner_actor),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    runtime = SQLAlchemyTaskRuntime(db, registry=registry)
    try:
        task = await runtime.request_cancel(
            task_id,
            _task_actor(actor),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except TaskRuntimeError as exc:
        await db.rollback()
        return _error(exc)
    return _success(_task_status(task))


def _task_actor(actor: CommandActor) -> ActorContext:
    return ActorContext(
        organization_id=actor.organization_id,
        actor_id=actor.actor_id,
        capabilities=frozenset(),
    )


async def _serve_learner_source_asset(
    *,
    activity_id: str,
    asset_token: str,
    actor: CommandActor,
    db: AsyncSession,
    registry: TaskRegistry,
    mode: Literal["preview", "playback", "download"],
    page: int | None = None,
) -> Response:
    grant = verify_learner_source_asset_grant(asset_token)
    if (
        grant is None
        or grant.organization_id != actor.organization_id
        or grant.activity_id != activity_id
        or "newcomer.activity.execute" not in actor.capabilities
    ):
        return _learner_asset_not_found()
    try:
        workspace = await ActivityApplicationService(
            db,
            runtime=FoundationActivityRuntimeAdapter(
                db,
                task_registry=registry,
                audio_storage=get_audio_object_storage(),
            ),
        ).get_workspace(actor=actor, activity_id=activity_id)
    except NewcomerTrainingError:
        return _learner_asset_not_found()
    blocks = workspace.runner.get("content_blocks")
    blocks = blocks if isinstance(blocks, list) else []
    block = next(
        (
            item
            for item in blocks
            if isinstance(item, dict) and item.get("block_id") == grant.block_id
        ),
        None,
    )
    if block is None:
        return _learner_asset_not_found()
    access = block.get("access")
    access = access if isinstance(access, dict) else {}
    allowed_path: object
    if mode == "preview":
        template = access.get("preview_page_template")
        allowed_path = (
            str(template).replace("{page}", str(page))
            if isinstance(template, str) and page is not None
            else None
        )
    else:
        allowed_path = access.get(mode)
    if not isinstance(allowed_path, str) or asset_token not in allowed_path:
        return _learner_asset_not_found()

    revision = await db.get(
        LearningSourceDocumentRevision,
        grant.source_revision_id,
    )
    if (
        revision is None
        or revision.organization_id != actor.organization_id
        or revision.status not in {"published", "archived"}
        or revision.source_type != "file"
        or revision.file_extension not in SUPPORTED_SOURCE_FILE_TYPES
    ):
        return _learner_asset_not_found()
    file_type = cast(SourceFileType, revision.file_extension)
    original = source_document_file_path(
        storage=get_document_storage_service(),
        organization_id=actor.organization_id,
        document_id=revision.document_id,
        file_hash=revision.file_hash,
        file_type=file_type,
    )
    path = original
    media_type = revision.trusted_mime_type or "application/octet-stream"
    filename = revision.original_filename or f"training-material.{file_type}"
    if mode == "preview":
        pages = revision.preview_manifest_json.get("pages", [])
        if page is None or not any(
            isinstance(item, dict)
            and item.get("page") == page
            and item.get("status") == "ready"
            for item in (pages if isinstance(pages, list) else [])
        ):
            path = original.with_name("missing-preview")
        else:
            path = preview_root(original) / f"page-{page}.png"
        media_type = "image/png"
        filename = f"slide-{page or 0}.png"
    elif mode == "playback":
        if revision.content_kind not in {"demo_video", "example_audio"}:
            path = original.with_name("missing-playback")
        else:
            path = preview_root(original) / f"playback.{file_type}"
        filename = f"training-media.{file_type}"
    available = path.is_file()
    db.add(
        LearningCommandAudit(
            audit_id=str(uuid.uuid4()),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability="newcomer.activity.execute",
            object_type="learning_source_asset",
            object_id=revision.revision_id,
            command=f"learner_{mode}_source_asset",
            before_version=revision.version,
            after_version=revision.version,
            idempotency_key_hash=hashlib.sha256(
                f"{actor.actor_id}:{activity_id}:{uuid.uuid4()}".encode()
            ).hexdigest(),
            reason=None,
            result="succeeded" if available else "failed",
            trace_id=actor.trace_id,
            details_json={"activity_id": activity_id, "block_id": grant.block_id},
            occurred_at=datetime.now(UTC),
        )
    )
    await db.commit()
    if not available:
        return _error(
            NewcomerTrainingError(
                "[LEARNING_ASSET_NOT_READY]",
                "训练材料暂时不可用，请返回活动刷新；你的学习进度不会丢失。",
                409,
            )
        )
    return FileResponse(path, media_type=media_type, filename=filename)


def _learner_asset_not_found() -> JSONResponse:
    return _error(
        NewcomerTrainingError(
            "[LEARNING_ASSET_NOT_FOUND]",
            "训练材料不存在或不可访问。",
            404,
        )
    )


def _task_status(task: TaskProjection) -> dict[str, Any]:
    labels = {
        TaskState.QUEUED: "等待处理",
        TaskState.RUNNING: "处理中",
        TaskState.RETRY_WAIT: "等待重试",
        TaskState.CANCEL_REQUESTED: "正在取消",
        TaskState.CANCELLED: "已取消",
        TaskState.SUCCEEDED: "已完成",
        TaskState.DEAD_LETTER: "处理未完成",
    }
    return {
        "contract_version": "task_status_v1",
        "task_id": task.task_id,
        "title": _task_title(task),
        "state": task.state,
        "state_label": labels[task.state],
        "progress": (
            None
            if task.progress is None
            else {
                "current": task.progress.current,
                "total": task.progress.total,
                "label": task.progress.label or "正在处理",
            }
        ),
        "can_cancel": task.state
        not in {TaskState.CANCELLED, TaskState.SUCCEEDED, TaskState.DEAD_LETTER},
        "retry_after": task.next_run_at if task.state is TaskState.RETRY_WAIT else None,
        "result_location": task.result_location,
        "result_path": _task_result_path(task.result_location),
        "error": (
            None
            if task.error is None
            else {
                "retryable": task.error.retryable,
                "message": task.error.message,
            }
        ),
        "updated_at": task.updated_at,
    }


def _task_title(task: TaskProjection) -> str:
    if task.resource_type in {"audio_submission", "audio_activity_run"}:
        return "录音评估"
    if task.resource_type in {"coach_session", "coach_turn"}:
        return "教练训练"
    if task.resource_type in {"quiz_attempt", "quiz_answer"}:
        return "测验评分"
    if task.resource_type in {"question_generation_batch", "question_candidate"}:
        return "题目生成"
    return "训练任务"


def _task_result_path(location: str | None) -> str | None:
    if not location:
        return None
    candidate = location.removeprefix("/api/v1")
    if candidate.startswith("/newcomer-training"):
        return candidate
    return None


async def _audit_audio_access(
    db: AsyncSession,
    *,
    actor: CommandActor,
    object_type: str,
    object_id: str,
    command: str,
    result: str,
) -> None:
    row = AudioCommandAudit(
        audit_id=str(uuid.uuid4()),
        organization_id=actor.organization_id,
        actor_id=actor.actor_id,
        capability="newcomer.activity.execute",
        object_type=object_type,
        object_id=object_id,
        command=command,
        before_version=None,
        after_version=None,
        idempotency_key_hash=None,
        expected_version=None,
        actual_version=None,
        reason=None,
        preview_token_hash=None,
        impact_hash=None,
        trace_id=actor.trace_id,
        result=result,
        details_json={},
        occurred_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush([row])


__all__ = [
    "get_foundation_organization_id",
    "get_foundation_task_registry",
    "get_audio_object_storage",
    "get_learner_actor",
    "router",
]

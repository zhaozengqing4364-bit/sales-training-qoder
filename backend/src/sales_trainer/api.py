from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.permissions import (
    can_manage_sales_trainer,
    can_manage_sales_trainer_questions,
    can_retry_sales_trainer_jobs,
    can_view_sales_trainer_global_records,
    can_view_sales_trainer_logs,
    can_view_sales_trainer_records,
    can_view_sales_trainer_settings,
    is_sales_trainer_admin,
    sales_trainer_admin_capability_projection,
    team_scope_department,
)
from sales_trainer.schemas import (
    AudioScorePromptCreate,
    AudioScorePromptResponse,
    AudioScorePromptUpdate,
    AudioScoreResultListResponse,
    AudioScoreResultResponse,
    AudioSubmissionCreate,
    AudioSubmissionListResponse,
    AudioSubmissionResponse,
    AudioUploadUrlRequest,
    AudioUploadUrlResponse,
    OperationLogListResponse,
    OperationLogResponse,
    QuizAttemptCreate,
    QuizAttemptListResponse,
    QuizAttemptResponse,
    SalesTrainerManagerDashboardResponse,
    SalesTrainerMaterialCreate,
    SalesTrainerMaterialListResponse,
    SalesTrainerMaterialResponse,
    SalesTrainerMaterialUpdate,
    SalesTrainerMaterialVersionCreate,
    SalesTrainerMaterialVersionResponse,
    SalesTrainerPathListResponse,
    SalesTrainerPathResponse,
    SalesTrainerQuestionCategoryCreate,
    SalesTrainerQuestionCategoryListResponse,
    SalesTrainerQuestionCategoryResponse,
    SalesTrainerQuestionCategoryUpdate,
    SalesTrainerQuestionCreate,
    SalesTrainerQuestionListResponse,
    SalesTrainerQuestionResponse,
    SalesTrainerQuestionUpdate,
    SalesTrainerSettingsResponse,
    SalesTrainerTrainingRecordListResponse,
    SalesTrainerTrainingRecordResponse,
    SalesTrainerUnitBriefResponse,
    SalesTrainerUnitCreate,
    SalesTrainerUnitListResponse,
    SalesTrainerUnitResponse,
    SalesTrainerUnitUpdate,
)
from sales_trainer.services.audio_submission_service import (
    AudioSubmissionService,
    AudioSubmissionServiceError,
)
from sales_trainer.services.effective_audio_training_config import (
    EffectiveAudioTrainingConfigResolver,
)
from sales_trainer.services.material_service import (
    MaterialServiceError,
    SalesTrainerMaterialService,
    serialize_material_version,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.phase2_dashboard_service import (
    SalesTrainerPhase2DashboardService,
)
from sales_trainer.services.phase2_policy import resolve_phase2_policy
from sales_trainer.services.prompt_service import (
    AudioScorePromptService,
    PromptServiceError,
)
from sales_trainer.services.question_bank import (
    SalesTrainerQuestionService,
    SalesTrainerQuestionServiceError,
    serialize_sales_trainer_category,
    serialize_sales_trainer_question,
)
from sales_trainer.services.quiz_service import QuizService, QuizServiceError
from sales_trainer.services.training_record_service import TrainingRecordService
from sales_trainer.services.unit_public_payloads import learner_safe_unit_payload
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService
from sales_trainer.tasks.process_audio import process_audio_submission_background

router = APIRouter(prefix="/sales-trainer", tags=["sales-trainer"])
admin_router = APIRouter(prefix="/admin/sales-trainer", tags=["admin-sales-trainer"])


def _api_error(code: str, *, status_code: int = 400, message: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code),
    )


def _require_manager(user: User) -> JSONResponse | None:
    if can_manage_sales_trainer(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足。")


def _require_question_manager(user: User) -> JSONResponse | None:
    if can_manage_sales_trainer_questions(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足。")


def _require_records_viewer(user: User) -> JSONResponse | None:
    if can_view_sales_trainer_records(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号无权查看学员记录。")


def _require_job_retry(user: User) -> JSONResponse | None:
    if can_retry_sales_trainer_jobs(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号无权重试转写或评分任务。")


def _require_ops_viewer(user: User) -> JSONResponse | None:
    if can_view_sales_trainer_logs(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号无权查看运维诊断。")


def _require_settings_viewer(user: User) -> JSONResponse | None:
    if can_view_sales_trainer_settings(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号无权查看配置健康。")


def _team_scope(user: User) -> str | None:
    department = team_scope_department(user)
    return department if not is_sales_trainer_admin(user) else None


def _as_unit_response(payload: dict[str, Any]) -> dict[str, Any]:
    return SalesTrainerUnitResponse.model_validate(payload).model_dump()


def _as_learner_unit_response(payload: dict[str, Any]) -> dict[str, Any]:
    return _as_unit_response(learner_safe_unit_payload(payload))


def _as_operation_log_response(log: Any) -> OperationLogResponse:
    return OperationLogResponse.model_validate(
        {
            "log_id": log.log_id,
            "actor_id": log.actor_id,
            "actor_role": log.actor_role,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "request_id": log.request_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "metadata": log.metadata_json or {},
            "created_at": log.created_at,
        }
    )


def _schedule_audio_processing(
    background_tasks: BackgroundTasks,
    *,
    submission_id: str,
    actor: User,
) -> None:
    background_tasks.add_task(
        process_audio_submission_background,
        submission_id,
        actor_id=str(actor.user_id),
    )


async def _sales_trainer_settings_payload(db: AsyncSession) -> dict[str, Any]:
    _, phase2_policy = await resolve_phase2_policy(db)
    storage_backend = os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "local").lower()
    cos_configured = _all_env_present(
        "TENCENT_COS_SECRET_ID",
        "TENCENT_COS_SECRET_KEY",
        "TENCENT_COS_BUCKET",
        "TENCENT_COS_REGION",
    )
    oss_configured = _all_env_present(
        "ALI_OSS_ACCESS_KEY_ID",
        "ALI_OSS_ACCESS_KEY_SECRET",
        "ALI_OSS_BUCKET",
        "ALI_OSS_ENDPOINT",
    )
    allowed_mime_types = [
        item.strip()
        for item in os.getenv(
            "SALES_TRAINER_AUDIO_ALLOWED_MIME_TYPES",
            "audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/webm,audio/mp4,audio/x-m4a",
        ).split(",")
        if item.strip()
    ]
    return {
        "storage_backend": storage_backend,
        "direct_upload_supported": (storage_backend == "cos" and cos_configured)
        or (storage_backend == "oss" and oss_configured),
        "cos_configured": cos_configured,
        "cos_public_read": _env_truthy(os.getenv("TENCENT_COS_PUBLIC_READ", "false")),
        "oss_configured": oss_configured,
        "asr_mode": os.getenv("SALES_TRAINER_ASR_MODE", "mock"),
        "asr_model": os.getenv("SALES_TRAINER_ASR_MODEL", "fun-asr"),
        "dashscope_configured": bool(os.getenv("DASHSCOPE_API_KEY")),
        "deucate_configured": bool(
            os.getenv("DEUCATE_BASE_URL") and os.getenv("DEUCATE_API_KEY")
        ),
        "deucate_model": os.getenv("DEUCATE_MODEL"),
        "max_file_size_mb": _int_env("SALES_TRAINER_AUDIO_MAX_FILE_SIZE_MB", 200),
        "allowed_mime_types": allowed_mime_types,
        "file_url_expires_seconds": _int_env(
            "SALES_TRAINER_AUDIO_FILE_URL_EXPIRES_SECONDS",
            3600,
        ),
        "phase2_policy": phase2_policy,
    }


def _all_env_present(*keys: str) -> bool:
    return all(bool(os.getenv(key)) for key in keys)


def _env_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(key: str, default: int) -> int:
    try:
        value = int(os.getenv(key, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


@admin_router.get("/capabilities")
async def admin_get_capabilities(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return success_response(sales_trainer_admin_capability_projection(current_user))


@router.get("/units")
async def list_published_units(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    units, total = await UnitService(db).list_units(published_only=True)
    service = UnitService(db)
    payload = [
        _as_learner_unit_response(await service.serialize_unit(unit))
        for unit in units
    ]
    return success_response(SalesTrainerUnitListResponse(items=payload, total=total))


@router.get("/paths")
async def list_training_paths(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    paths = await SalesTrainerPathService(db).list_paths_for_user(
        str(current_user.user_id)
    )
    payload = [
        SalesTrainerPathResponse.model_validate(path).model_dump()
        for path in paths
    ]
    return success_response(SalesTrainerPathListResponse(items=payload, total=len(payload)))


@router.get("/units/{unit_id}")
async def get_published_unit(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None or unit.status != "published":
        return _api_error(
            "[SALES_TRAINER_UNIT_NOT_FOUND]",
            status_code=404,
            message="训练单元不存在或未发布。",
        )
    return success_response(_as_learner_unit_response(await service.serialize_unit(unit)))


@router.get("/units/{unit_id}/brief")
async def get_published_unit_brief(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None or unit.status != "published":
        return _api_error(
            "[SALES_TRAINER_UNIT_NOT_FOUND]",
            status_code=404,
            message="训练单元不存在或未发布。",
        )
    try:
        effective = await EffectiveAudioTrainingConfigResolver(db).resolve_for_unit(unit)
        brief = await SalesTrainerMaterialService(db).resolve_unit_brief(
            unit,
            config_override=effective.config,
        )
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    payload = {
        "unit": _as_learner_unit_response(await service.serialize_unit(unit)),
        "task_brief": brief["task_brief"],
        "materials": brief["materials"],
        "score_scheme": brief["score_scheme"],
    }
    return success_response(SalesTrainerUnitBriefResponse.model_validate(payload).model_dump())


@router.get("/materials/versions/{version_id}/file", response_model=None)
async def get_sales_trainer_material_version_file(
    version_id: str,
    disposition: str = Query("attachment", pattern="^(attachment|inline)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    try:
        access = await SalesTrainerMaterialService(db).resolve_file_access(version_id)
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if access.mode == "redirect" and access.redirect_url:
        return RedirectResponse(url=access.redirect_url)
    if access.path is not None:
        return FileResponse(
            access.path,
            media_type=access.media_type,
            filename=access.filename,
            content_disposition_type=disposition,
        )
    return _api_error("[MATERIAL_FILE_NOT_FOUND]", status_code=404)


@router.post("/quiz-attempts")
async def submit_quiz_attempt(
    payload: QuizAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = QuizService(db)
    try:
        attempt = await service.submit_attempt(payload, actor=current_user)
    except QuizServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        QuizAttemptResponse.model_validate(
            await service.serialize_attempt(attempt)
        ).model_dump()
    )


@router.get("/quiz-attempts/{attempt_id}")
async def get_quiz_attempt(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = QuizService(db)
    try:
        attempt = await service.get_attempt(attempt_id, actor=current_user)
    except QuizServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if attempt is None:
        return _api_error("[QUIZ_ATTEMPT_NOT_FOUND]", status_code=404)
    return success_response(
        QuizAttemptResponse.model_validate(
            await service.serialize_attempt(attempt)
        ).model_dump()
    )


@router.post("/audio-submissions/upload-url")
async def create_audio_upload_url(
    payload: AudioUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ = db
    service = AudioSubmissionService(db)
    try:
        result = service.generate_upload_url(
            filename=payload.filename,
            content_type=payload.content_type,
            actor=current_user,
        )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(AudioUploadUrlResponse.model_validate(result).model_dump())


@router.post("/audio-submissions/upload")
async def upload_audio_file(
    background_tasks: BackgroundTasks,
    unit_id: str | None = Form(None),
    purpose: str = Form("general_audio_scoring"),
    source_page: str | None = Form(None),
    confirmed_material_version_id: str | None = Form(None),
    auto_process: bool = Form(True),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioSubmissionService(db)
    try:
        submission = await service.save_uploaded_file(
            file=file,
            unit_id=unit_id,
            purpose=purpose,
            source_page=source_page.strip() if source_page and source_page.strip() else None,
            confirmed_material_version_id=confirmed_material_version_id.strip()
            if confirmed_material_version_id and confirmed_material_version_id.strip()
            else None,
            actor=current_user,
            auto_process=False,
        )
        if auto_process:
            _schedule_audio_processing(
                background_tasks,
                submission_id=submission.submission_id,
                actor=current_user,
            )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
    )


@router.post("/audio-submissions")
async def register_audio_submission(
    payload: AudioSubmissionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioSubmissionService(db)
    try:
        should_process = payload.auto_process
        submission = await service.create_submission(
            payload.model_copy(update={"auto_process": False}),
            actor=current_user,
        )
        if should_process:
            _schedule_audio_processing(
                background_tasks,
                submission_id=submission.submission_id,
                actor=current_user,
            )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
    )


@router.get("/audio-submissions/{submission_id}")
async def get_my_audio_submission(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioSubmissionService(db)
    try:
        submission = await service.get_submission(submission_id, actor=current_user)
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if submission is None:
        return _api_error("[AUDIO_SUBMISSION_NOT_FOUND]", status_code=404)
    return success_response(
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
    )


@router.get("/audio-submissions/{submission_id}/file", response_model=None)
async def get_my_audio_submission_file(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioSubmissionService(db)
    try:
        access = await service.resolve_audio_file_access(
            submission_id,
            actor=current_user,
        )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if access.mode == "redirect" and access.redirect_url:
        return RedirectResponse(url=access.redirect_url)
    if access.path is not None:
        return FileResponse(
            access.path,
            media_type=access.media_type,
            filename=access.filename,
        )
    return _api_error("[AUDIO_FILE_NOT_FOUND]", status_code=404)


@admin_router.get("/units")
async def admin_list_units(
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    units, total = await service.list_units(
        include_archived=include_archived, limit=limit, offset=offset
    )
    payload = [_as_unit_response(await service.serialize_unit(unit)) for unit in units]
    return success_response(SalesTrainerUnitListResponse(items=payload, total=total))


@admin_router.post("/units")
async def admin_create_unit(
    payload: SalesTrainerUnitCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    try:
        unit = await service.create_unit(payload, actor=current_user)
    except SalesTrainerUnitError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(unit)))


@admin_router.put("/units/{unit_id}")
async def admin_update_unit(
    unit_id: str,
    payload: SalesTrainerUnitUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    try:
        updated = await service.update_unit(unit, payload, actor=current_user)
    except SalesTrainerUnitError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(updated)))


@admin_router.post("/units/{unit_id}/publish")
async def admin_publish_unit(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    try:
        published = await service.publish_unit(unit, actor=current_user)
    except SalesTrainerUnitError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(published)))


@admin_router.post("/units/{unit_id}/archive")
async def admin_archive_unit(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    archived = await service.archive_unit(unit, actor=current_user)
    return success_response(_as_unit_response(await service.serialize_unit(archived)))


@admin_router.get("/materials")
async def admin_list_materials(
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerMaterialService(db)
    materials, total = await service.list_materials(
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    payload = [
        SalesTrainerMaterialResponse.model_validate(
            await service.serialize_material(material)
        ).model_dump()
        for material in materials
    ]
    return success_response(SalesTrainerMaterialListResponse(items=payload, total=total))


@admin_router.post("/materials")
async def admin_create_material(
    payload: SalesTrainerMaterialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerMaterialService(db)
    try:
        material = await service.create_material(payload, actor=current_user)
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerMaterialResponse.model_validate(
            await service.serialize_material(material)
        ).model_dump()
    )


@admin_router.put("/materials/{material_id}")
async def admin_update_material(
    material_id: str,
    payload: SalesTrainerMaterialUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerMaterialService(db)
    material = await service.get_material(material_id)
    if material is None:
        return _api_error("[SALES_TRAINER_MATERIAL_NOT_FOUND]", status_code=404)
    try:
        updated = await service.update_material(material, payload, actor=current_user)
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerMaterialResponse.model_validate(
            await service.serialize_material(updated)
        ).model_dump()
    )


@admin_router.post("/materials/{material_id}/archive")
async def admin_archive_material(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerMaterialService(db)
    material = await service.get_material(material_id)
    if material is None:
        return _api_error("[SALES_TRAINER_MATERIAL_NOT_FOUND]", status_code=404)
    archived = await service.archive_material(material, actor=current_user)
    return success_response(
        SalesTrainerMaterialResponse.model_validate(
            await service.serialize_material(archived)
        ).model_dump()
    )


@admin_router.post("/materials/{material_id}/versions")
async def admin_create_material_version(
    material_id: str,
    payload: SalesTrainerMaterialVersionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerMaterialService(db)
    material = await service.get_material(material_id)
    if material is None:
        return _api_error("[SALES_TRAINER_MATERIAL_NOT_FOUND]", status_code=404)
    try:
        version = await service.create_version(material, payload, actor=current_user)
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerMaterialVersionResponse.model_validate(
            serialize_material_version(version)
        ).model_dump()
    )


@admin_router.post("/materials/versions/{version_id}/publish")
async def admin_publish_material_version(
    version_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerMaterialService(db)
    version = await service.get_version(version_id)
    if version is None:
        return _api_error("[MATERIAL_VERSION_NOT_FOUND]", status_code=404)
    try:
        published = await service.publish_version(version, actor=current_user)
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerMaterialVersionResponse.model_validate(
            serialize_material_version(published)
        ).model_dump()
    )


@admin_router.get("/question-categories")
async def admin_list_sales_trainer_question_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        categories, total = await SalesTrainerQuestionService(db).list_categories()
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [
        SalesTrainerQuestionCategoryResponse.model_validate(
            serialize_sales_trainer_category(category)
        ).model_dump()
        for category in categories
    ]
    return success_response(
        SalesTrainerQuestionCategoryListResponse(items=items, total=total)
    )


@admin_router.post("/question-categories")
async def admin_create_sales_trainer_question_category(
    payload: SalesTrainerQuestionCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        category = await SalesTrainerQuestionService(db).create_category(
            payload,
            actor_id=str(current_user.user_id),
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionCategoryResponse.model_validate(
            serialize_sales_trainer_category(category)
        ).model_dump()
    )


@admin_router.put("/question-categories/{category_id}")
async def admin_update_sales_trainer_question_category(
    category_id: str,
    payload: SalesTrainerQuestionCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        category = await SalesTrainerQuestionService(db).update_category(
            category_id,
            payload,
            actor_id=str(current_user.user_id),
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionCategoryResponse.model_validate(
            serialize_sales_trainer_category(category)
        ).model_dump()
    )


@admin_router.get("/questions")
async def admin_list_sales_trainer_questions(
    category_id: str | None = None,
    difficulty: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        questions, total = await SalesTrainerQuestionService(db).list_questions(
            category_id=category_id,
            difficulty=difficulty,
            status=status,
            tag=tag,
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [
        SalesTrainerQuestionResponse.model_validate(
            serialize_sales_trainer_question(question)
        ).model_dump()
        for question in questions
    ]
    return success_response(SalesTrainerQuestionListResponse(items=items, total=total))


@admin_router.post("/questions")
async def admin_create_sales_trainer_question(
    payload: SalesTrainerQuestionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        question = await SalesTrainerQuestionService(db).create_question(
            payload,
            actor_id=str(current_user.user_id),
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionResponse.model_validate(
            serialize_sales_trainer_question(question)
        ).model_dump()
    )


@admin_router.get("/questions/{question_id}")
async def admin_get_sales_trainer_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        question = await SalesTrainerQuestionService(db).get_question(question_id)
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionResponse.model_validate(
            serialize_sales_trainer_question(question)
        ).model_dump()
    )


@admin_router.put("/questions/{question_id}")
async def admin_update_sales_trainer_question(
    question_id: str,
    payload: SalesTrainerQuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_question_manager(current_user):
        return error
    try:
        question = await SalesTrainerQuestionService(db).update_question(
            question_id,
            payload,
            actor_id=str(current_user.user_id),
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionResponse.model_validate(
            serialize_sales_trainer_question(question)
        ).model_dump()
    )


@admin_router.post("/questions/{question_id}/publish")
async def admin_publish_sales_trainer_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    try:
        question = await SalesTrainerQuestionService(db).publish_question(
            question_id,
            actor_id=str(current_user.user_id),
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionResponse.model_validate(
            serialize_sales_trainer_question(question)
        ).model_dump()
    )


@admin_router.post("/questions/{question_id}/archive")
async def admin_archive_sales_trainer_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    try:
        question = await SalesTrainerQuestionService(db).archive_question(
            question_id,
            actor_id=str(current_user.user_id),
        )
    except SalesTrainerQuestionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerQuestionResponse.model_validate(
            serialize_sales_trainer_question(question)
        ).model_dump()
    )


@admin_router.get("/audio-submissions")
async def admin_list_audio_submissions(
    user_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = AudioSubmissionService(db)
    submissions, total = await service.list_submissions(
        user_id=user_id,
        team_department=_team_scope(current_user),
        limit=limit,
        offset=offset,
    )
    payload = [
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
        for submission in submissions
    ]
    return success_response(AudioSubmissionListResponse(items=payload, total=total))


@admin_router.get("/audio-submissions/{submission_id}")
async def admin_get_audio_submission(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = AudioSubmissionService(db)
    try:
        submission = await service.get_submission(
            submission_id,
            actor=current_user,
            allow_admin=can_view_sales_trainer_global_records(current_user),
            team_department=_team_scope(current_user),
        )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if submission is None:
        return _api_error("[AUDIO_SUBMISSION_NOT_FOUND]", status_code=404)
    return success_response(
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
    )


@admin_router.get("/audio-submissions/{submission_id}/file", response_model=None)
async def admin_get_audio_submission_file(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = AudioSubmissionService(db)
    try:
        access = await service.resolve_audio_file_access(
            submission_id,
            actor=current_user,
            allow_admin=can_view_sales_trainer_global_records(current_user),
            team_department=_team_scope(current_user),
        )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if access.mode == "redirect" and access.redirect_url:
        return RedirectResponse(url=access.redirect_url)
    if access.path is not None:
        return FileResponse(
            access.path,
            media_type=access.media_type,
            filename=access.filename,
        )
    return _api_error("[AUDIO_FILE_NOT_FOUND]", status_code=404)


@admin_router.post("/audio-submissions/{submission_id}/retry-transcription")
async def admin_retry_transcription(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_job_retry(current_user):
        return error
    service = AudioSubmissionService(db)
    try:
        await service.get_submission(
            submission_id,
            actor=current_user,
            allow_admin=can_view_sales_trainer_global_records(current_user),
            team_department=_team_scope(current_user),
        )
        submission = await service.retry_transcription(submission_id, actor=current_user)
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
    )


@admin_router.post("/audio-submissions/{submission_id}/retry-scoring")
async def admin_retry_scoring(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_job_retry(current_user):
        return error
    service = AudioSubmissionService(db)
    try:
        await service.get_submission(
            submission_id,
            actor=current_user,
            allow_admin=can_view_sales_trainer_global_records(current_user),
            team_department=_team_scope(current_user),
        )
        submission = await service.retry_scoring(submission_id, actor=current_user)
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        AudioSubmissionResponse.model_validate(
            await service.serialize_submission(submission)
        ).model_dump()
    )


@admin_router.get("/score-results")
async def admin_list_score_results(
    user_id: str | None = None,
    submission_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = AudioSubmissionService(db)
    results, total = await service.list_score_results(
        user_id=user_id,
        submission_id=submission_id,
        team_department=_team_scope(current_user),
        limit=limit,
        offset=offset,
    )
    payload = [
        AudioScoreResultResponse.model_validate(
            await service.serialize_score_result(result)
        )
        for result in results
    ]
    return success_response(AudioScoreResultListResponse(items=payload, total=total))


@admin_router.get("/training-records")
async def admin_list_training_records(
    user_id: str | None = None,
    unit_id: str | None = None,
    material_version_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = TrainingRecordService(db)
    records, total = await service.list_records(
        user_id=user_id,
        unit_id=unit_id,
        material_version_id=material_version_id,
        team_department=_team_scope(current_user),
        limit=limit,
        offset=offset,
    )
    return success_response(
        SalesTrainerTrainingRecordListResponse(
            items=[
                SalesTrainerTrainingRecordResponse.model_validate(record).model_dump()
                for record in records
            ],
            total=total,
        )
    )


@admin_router.get("/manager-dashboard")
async def admin_get_manager_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    payload = await SalesTrainerPhase2DashboardService(db).get_dashboard(
        team_department=_team_scope(current_user),
    )
    return success_response(
        SalesTrainerManagerDashboardResponse.model_validate(payload).model_dump()
    )


@admin_router.get("/training-records/audio/{submission_id}")
async def admin_get_audio_training_record(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    audio_service = AudioSubmissionService(db)
    try:
        submission = await audio_service.get_submission(
            submission_id,
            actor=current_user,
            allow_admin=can_view_sales_trainer_global_records(current_user),
            team_department=_team_scope(current_user),
        )
    except AudioSubmissionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if submission is None:
        return _api_error("[AUDIO_SUBMISSION_NOT_FOUND]", status_code=404)
    record = await TrainingRecordService(db).get_audio_record(submission_id)
    if record is None:
        return _api_error("[TRAINING_RECORD_NOT_FOUND]", status_code=404)
    return success_response(SalesTrainerTrainingRecordResponse.model_validate(record).model_dump())


@admin_router.get("/training-records/detail/{record_type}/{record_id}")
async def admin_get_training_record_detail(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    if record_type not in {"audio_submission", "quiz_attempt", "ai_coach_session"}:
        return _api_error("[TRAINING_RECORD_TYPE_INVALID]", status_code=400)
    record = await TrainingRecordService(db).get_record(record_type, record_id)
    if record is None:
        return _api_error("[TRAINING_RECORD_NOT_FOUND]", status_code=404)
    team_department = _team_scope(current_user)
    if (
        team_department is not None
        and record.get("user_department") != team_department
    ):
        return _api_error("[TRAINING_RECORD_NOT_FOUND]", status_code=404)
    return success_response(
        SalesTrainerTrainingRecordResponse.model_validate(record).model_dump()
    )


@admin_router.get("/quiz-attempts")
async def admin_list_quiz_attempts(
    user_id: str | None = None,
    unit_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = QuizService(db)
    attempts, total = await service.list_attempts(
        user_id=user_id,
        unit_id=unit_id,
        team_department=_team_scope(current_user),
        limit=limit,
        offset=offset,
    )
    payload = [
        QuizAttemptResponse.model_validate(await service.serialize_attempt(attempt))
        for attempt in attempts
    ]
    return success_response(QuizAttemptListResponse(items=payload, total=total))


@admin_router.get("/quiz-attempts/{attempt_id}")
async def admin_get_quiz_attempt(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_records_viewer(current_user):
        return error
    service = QuizService(db)
    try:
        attempt = await service.get_admin_attempt(
            attempt_id,
            actor=current_user,
            allow_admin=can_view_sales_trainer_global_records(current_user),
            team_department=_team_scope(current_user),
        )
    except QuizServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    if attempt is None:
        return _api_error("[QUIZ_ATTEMPT_NOT_FOUND]", status_code=404)
    return success_response(
        QuizAttemptResponse.model_validate(
            await service.serialize_attempt(attempt)
        ).model_dump()
    )


@admin_router.get("/audio-score-prompts")
async def admin_list_audio_score_prompts(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    prompts, total = await AudioScorePromptService(db).list_prompts(
        include_archived=include_archived
    )
    return success_response(
        {
            "items": [
                AudioScorePromptResponse.model_validate(prompt).model_dump()
                for prompt in prompts
            ],
            "total": total,
        }
    )


@admin_router.post("/audio-score-prompts")
async def admin_create_audio_score_prompt(
    payload: AudioScorePromptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    prompt = await AudioScorePromptService(db).create_prompt(payload, actor=current_user)
    return success_response(AudioScorePromptResponse.model_validate(prompt).model_dump())


@admin_router.put("/audio-score-prompts/{prompt_id}")
async def admin_update_audio_score_prompt(
    prompt_id: str,
    payload: AudioScorePromptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = AudioScorePromptService(db)
    prompt = await service.get_prompt(prompt_id)
    if prompt is None:
        return _api_error("[SCORING_PROMPT_NOT_FOUND]", status_code=404)
    try:
        updated = await service.update_prompt(prompt, payload, actor=current_user)
    except PromptServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(AudioScorePromptResponse.model_validate(updated).model_dump())


@admin_router.post("/audio-score-prompts/{prompt_id}/publish")
async def admin_publish_audio_score_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_manager(current_user):
        return error
    service = AudioScorePromptService(db)
    prompt = await service.get_prompt(prompt_id)
    if prompt is None:
        return _api_error("[SCORING_PROMPT_NOT_FOUND]", status_code=404)
    try:
        published = await service.publish_prompt(prompt, actor=current_user)
    except PromptServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(AudioScorePromptResponse.model_validate(published).model_dump())


@admin_router.get("/settings")
async def admin_get_sales_trainer_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_settings_viewer(current_user):
        return error
    return success_response(
        SalesTrainerSettingsResponse.model_validate(
            await _sales_trainer_settings_payload(db)
        ).model_dump()
    )


@admin_router.get("/operation-logs")
async def admin_list_operation_logs(
    actor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if error := _require_ops_viewer(current_user):
        return error
    logs, total = await OperationLogService(db).list_logs(
        actor_id=actor_id,
        actor_department=_team_scope(current_user),
        target_type=target_type,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return success_response(
        OperationLogListResponse(
            items=[_as_operation_log_response(log) for log in logs],
            total=total,
        )
    )

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from sales_trainer.ai_coach_policy import (
    changed_ai_coach_high_risk_fields,
    changed_ai_coach_high_risk_fields_for_publish,
    changed_ai_coach_high_risk_fields_for_rollback,
)
from sales_trainer.permissions import (
    can_manage_sales_trainer,
    can_manage_sales_trainer_prompts,
)
from sales_trainer.schemas import (
    CustomerFaqGenerateDraftRequest,
    CustomerFaqImportParseRequest,
    CustomerFaqImportParseResponse,
    NewcomerDeadDataDiagnosticsResponse,
    NewcomerLearningTopicRevisionSummary,
    NewcomerLearningTopicsActionRequest,
    NewcomerLearningTopicsConfigResponse,
    NewcomerLearningTopicsGenerateDraftRequest,
    NewcomerLearningTopicsPreviewResponse,
    NewcomerLearningTopicsRevisionListResponse,
    NewcomerLearningTopicsRollbackPreviewRequest,
    NewcomerLearningTopicsSaveRequest,
    NewcomerPathConfigActionRequest,
    NewcomerPathConfigResponse,
    NewcomerPathConfigSaveRequest,
    NewcomerPathPublishPreviewResponse,
    NewcomerPathRevisionListResponse,
    NewcomerPathRevisionSummary,
    NewcomerPathRollbackPreviewRequest,
    NewcomerPathRollbackPreviewResponse,
)
from sales_trainer.services.customer_faq_parser import parse_customer_faq_material
from sales_trainer.services.learning_topic_config_service import (
    LearningTopicConfigError,
    NewcomerLearningTopicConfigService,
    changed_learning_topic_ai_coach_high_risk_fields,
)
from sales_trainer.services.newcomer_dead_data_diagnostics_service import (
    NewcomerDeadDataDiagnosticsService,
)
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

newcomer_admin_path_config_router = APIRouter(
    prefix="/admin/newcomer-training",
    tags=["admin-newcomer-training-path-config"],
)


def _api_error(
    code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
    trace_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code, trace_id=trace_id),
    )


def _require_manager(user: User) -> JSONResponse | None:
    if can_manage_sales_trainer(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足。")


_changed_ai_coach_high_risk_fields = changed_ai_coach_high_risk_fields


def _high_risk_ai_permission_error(
    fields: set[str],
    *,
    trace_id: str | None = None,
) -> JSONResponse:
    return _api_error(
        "[PERMISSION_DENIED]",
        status_code=403,
        message="无权修改以下 AI 教练高风险字段：" + ", ".join(sorted(fields)),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.get("/path-config", response_model=None)
async def get_path_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        payload = await SalesTrainerPathConfigService(db).get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        NewcomerPathConfigResponse.model_validate(payload).model_dump()
    )


@newcomer_admin_path_config_router.put("/path-config", response_model=None)
async def save_path_config(
    payload: NewcomerPathConfigSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error

    # Field-level RBAC for the embedded ``ai_coach`` config. Without this
    # gate, a content_admin could rewrite mastery_threshold, prompt
    # bindings, scoring policy, etc. through the generic path-config
    # endpoint and bypass the dedicated ``/admin/.../ai-coach/config``
    # route's stricter checks. We diff against the currently-persisted
    # payload to detect only changed fields.
    service = SalesTrainerPathConfigService(db)
    try:
        current_response = await service.get_config()
        changed_high_risk = _changed_ai_coach_high_risk_fields(
            current_response.get("path"),
            payload,
        )
    except ValidationError:
        return _api_error(
            "[AI_COACH_CONFIG_RBAC_CHECK_FAILED]",
            status_code=500,
            message="AI 教练配置权限校验失败，已拒绝保存。",
        )
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message=(
                "无权通过通用 path-config 修改以下 AI 教练高风险字段："
                + ", ".join(sorted(changed_high_risk))
            ),
        )
    trace_id = get_trace_id()
    try:
        await service.save_config(payload, actor=current_user, trace_id=trace_id)
        response = await service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post(
    "/path-config/publish/preview", response_model=None
)
async def preview_path_config_publish(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await changed_ai_coach_high_risk_fields_for_publish(db)
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _api_error(
                "[PERMISSION_DENIED]",
                status_code=403,
                message=(
                    "无权预览发布以下 AI 教练高风险字段："
                    + ", ".join(sorted(changed_high_risk))
                ),
                trace_id=trace_id,
            )
        preview = await service.publish_preview()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathPublishPreviewResponse.model_validate(preview).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post("/path-config/publish", response_model=None)
async def publish_path_config(
    payload: NewcomerPathConfigActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await changed_ai_coach_high_risk_fields_for_publish(db)
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _api_error(
                "[PERMISSION_DENIED]",
                status_code=403,
                message=(
                    "无权发布以下 AI 教练高风险字段："
                    + ", ".join(sorted(changed_high_risk))
                ),
                trace_id=trace_id,
            )
        await service.publish_config(
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.get("/path-config/revisions", response_model=None)
async def list_path_config_revisions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        revisions = await SalesTrainerPathConfigService(db).list_revisions()
    except SalesTrainerPathConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [
        NewcomerPathRevisionSummary.model_validate(item).model_dump()
        for item in revisions
    ]
    return success_response(
        NewcomerPathRevisionListResponse(items=items, total=len(items))
    )


@newcomer_admin_path_config_router.get(
    "/path-config/dead-data-diagnostics",
    response_model=None,
)
async def get_path_config_dead_data_diagnostics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    report = await NewcomerDeadDataDiagnosticsService(db).build_report()
    return success_response(
        NewcomerDeadDataDiagnosticsResponse.model_validate(report).model_dump()
    )


@newcomer_admin_path_config_router.get("/learning-topics/config", response_model=None)
async def get_learning_topics_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        payload = await NewcomerLearningTopicConfigService(db).get_config()
    except LearningTopicConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        NewcomerLearningTopicsConfigResponse.model_validate(payload).model_dump()
    )


@newcomer_admin_path_config_router.put("/learning-topics/config", response_model=None)
async def save_learning_topics_config(
    payload: NewcomerLearningTopicsSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = NewcomerLearningTopicConfigService(db)
    try:
        current_response = await service.get_config()
        current_payload = NewcomerLearningTopicsConfigResponse.model_validate(
            current_response
        ).payload
        changed_high_risk = changed_learning_topic_ai_coach_high_risk_fields(
            current_payload,
            payload,
        )
    except (LearningTopicConfigError, ValueError, ValidationError) as exc:
        code = getattr(exc, "code", "[LEARNING_TOPIC_CONFIG_INVALID]")
        message = getattr(exc, "message", "学习专题配置权限校验失败。")
        status_code = getattr(exc, "status_code", 422)
        return _api_error(code, status_code=status_code, message=message)
    if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
        return _high_risk_ai_permission_error(changed_high_risk)
    trace_id = get_trace_id()
    try:
        await service.save_config(payload, actor=current_user, trace_id=trace_id)
        response = await service.get_config()
    except LearningTopicConfigError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post(
    "/learning-topics/business-etiquette/generate-draft",
    response_model=None,
)
async def generate_business_etiquette_learning_topic_draft(
    payload: NewcomerLearningTopicsGenerateDraftRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    request = payload or NewcomerLearningTopicsGenerateDraftRequest()
    service = NewcomerLearningTopicConfigService(db)
    try:
        await service.generate_business_etiquette_draft(
            actor=current_user,
            overwrite_working=request.overwrite_working,
            reason=request.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except LearningTopicConfigError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post(
    "/learning-topics/customer-faq/parse",
    response_model=None,
)
async def parse_customer_faq_learning_topic_material(
    payload: CustomerFaqImportParseRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    result = parse_customer_faq_material(payload.raw_text)
    return success_response(
        CustomerFaqImportParseResponse.model_validate(result).model_dump(mode="json")
    )


@newcomer_admin_path_config_router.post(
    "/learning-topics/customer-faq/generate-draft",
    response_model=None,
)
async def generate_customer_faq_learning_topic_draft(
    payload: CustomerFaqGenerateDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    service = NewcomerLearningTopicConfigService(db)
    try:
        await service.generate_customer_faq_draft(
            raw_text=payload.raw_text,
            actor=current_user,
            overwrite_working=payload.overwrite_working,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except LearningTopicConfigError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post(
    "/learning-topics/publish/preview",
    response_model=None,
)
async def preview_learning_topics_publish(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = NewcomerLearningTopicConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await service.changed_high_risk_fields_for_publish()
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _high_risk_ai_permission_error(changed_high_risk, trace_id=trace_id)
        preview = await service.publish_preview()
    except LearningTopicConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsPreviewResponse.model_validate(preview).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post("/learning-topics/publish", response_model=None)
async def publish_learning_topics_config(
    payload: NewcomerLearningTopicsActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = NewcomerLearningTopicConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await service.changed_high_risk_fields_for_publish()
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _high_risk_ai_permission_error(changed_high_risk, trace_id=trace_id)
        await service.publish_config(
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except LearningTopicConfigError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.get(
    "/learning-topics/revisions", response_model=None
)
async def list_learning_topics_revisions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        revisions = await NewcomerLearningTopicConfigService(db).list_revisions()
    except LearningTopicConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [
        NewcomerLearningTopicRevisionSummary.model_validate(item).model_dump()
        for item in revisions
    ]
    return success_response(
        NewcomerLearningTopicsRevisionListResponse(items=items, total=len(items))
    )


@newcomer_admin_path_config_router.post(
    "/learning-topics/rollback/preview",
    response_model=None,
)
async def preview_learning_topics_rollback(
    payload: NewcomerLearningTopicsRollbackPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = NewcomerLearningTopicConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await service.changed_high_risk_fields_for_rollback(
            payload.revision_id
        )
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _high_risk_ai_permission_error(changed_high_risk, trace_id=trace_id)
        preview = await service.rollback_preview(payload.revision_id)
    except LearningTopicConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsPreviewResponse.model_validate(preview).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post(
    "/learning-topics/rollback", response_model=None
)
async def rollback_learning_topics_config(
    payload: NewcomerLearningTopicsActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    if not payload.revision_id:
        return _api_error(
            "[LEARNING_TOPIC_REVISION_REQUIRED]",
            status_code=422,
            message="请选择要回滚的学习专题历史版本。",
        )
    service = NewcomerLearningTopicConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await service.changed_high_risk_fields_for_rollback(
            payload.revision_id
        )
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _high_risk_ai_permission_error(changed_high_risk, trace_id=trace_id)
        await service.rollback_config(
            revision_id=payload.revision_id,
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except LearningTopicConfigError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerLearningTopicsConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post(
    "/path-config/rollback/preview",
    response_model=None,
)
async def preview_path_config_rollback(
    payload: NewcomerPathRollbackPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await changed_ai_coach_high_risk_fields_for_rollback(
            db,
            payload.revision_id,
        )
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _api_error(
                "[PERMISSION_DENIED]",
                status_code=403,
                message=(
                    "无权预览回滚以下 AI 教练高风险字段："
                    + ", ".join(sorted(changed_high_risk))
                ),
                trace_id=trace_id,
            )
        preview = await service.rollback_preview(payload.revision_id)
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathRollbackPreviewResponse.model_validate(preview).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post("/path-config/rollback", response_model=None)
async def rollback_path_config(
    payload: NewcomerPathConfigActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    if not payload.revision_id:
        return _api_error(
            "[NEWCOMER_PATH_REVISION_REQUIRED]",
            status_code=422,
            message="请选择要回滚的新人训练路径历史版本。",
        )
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        changed_high_risk = await changed_ai_coach_high_risk_fields_for_rollback(
            db,
            payload.revision_id,
        )
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _api_error(
                "[PERMISSION_DENIED]",
                status_code=403,
                message=(
                    "无权回滚以下 AI 教练高风险字段："
                    + ", ".join(sorted(changed_high_risk))
                ),
                trace_id=trace_id,
            )
        await service.rollback_config(
            revision_id=payload.revision_id,
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )

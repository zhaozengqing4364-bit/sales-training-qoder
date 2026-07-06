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
from sales_trainer.ai_coach_policy import (
    AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS,
    changed_ai_coach_high_risk_fields_for_publish,
    changed_ai_coach_high_risk_fields_for_rollback,
    requires_manage_prompts,
)
from sales_trainer.permissions import (
    can_manage_sales_trainer_modules,
    can_manage_sales_trainer_prompts,
)
from sales_trainer.schemas import (
    AI_COACH_INTERACTION_SCHEMA_VERSION,
    AiCoachConfig,
)
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

router = APIRouter(
    prefix="/admin/newcomer-training/modules",
    tags=["admin-newcomer-training-ai-coach"],
)


def _api_error(
    code: str, *, status_code: int = 400, message: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code),
    )


def _path_service_error_response(exc: SalesTrainerPathConfigError) -> JSONResponse:
    return _api_error(exc.code, status_code=exc.status_code, message=exc.message)


@router.get("/{module_key}/ai-coach/config")
async def get_ai_coach_config(
    module_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Get AI coach config for a module."""
    if not can_manage_sales_trainer_modules(current_user):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message="无权查看 AI 教练配置。",
        )

    path_service = SalesTrainerPathConfigService(db)
    try:
        path_response = await path_service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _path_service_error_response(exc)
    path_payload = path_response.get("path")

    if path_payload is None:
        return _api_error(
            "[NEWCOMER_PATH_CONFIG_NOT_FOUND]",
            status_code=404,
            message="新人训练路径配置不存在。",
        )

    from sales_trainer.schemas import NewcomerPathConfigPayload

    try:
        payload = NewcomerPathConfigPayload.model_validate(path_payload)
    except ValidationError:
        return _api_error(
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            status_code=500,
            message="新人训练路径配置格式错误。",
        )

    module_config = next(
        (module for module in payload.modules if module.module_key == module_key),
        None,
    )
    if module_config is None:
        return _api_error(
            "[NEWCOMER_MODULE_NOT_FOUND]",
            status_code=404,
            message="模块不存在。",
        )

    ai_coach_config = dict(
        module_config.ai_coach.model_dump(mode="json")
        if module_config.ai_coach
        else AiCoachConfig().model_dump(mode="json")
    )
    ai_coach_config["output_schema_version"] = AI_COACH_INTERACTION_SCHEMA_VERSION
    ai_coach_config["prompt_contract_hash"] = None
    ai_coach_config["scoring_contract_hash"] = None

    return JSONResponse(
        status_code=200,
        content=success_response(
            data={
                "module_key": module_key,
                "ai_coach": ai_coach_config,
            },
        ),
    )


@router.put("/{module_key}/ai-coach/config")
async def save_ai_coach_config(
    module_key: str,
    payload: AiCoachConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Save AI coach config for a module."""
    # Admin config read: can_manage_sales_trainer_modules
    if not can_manage_sales_trainer_modules(current_user):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message="无权修改 AI 教练配置。",
        )

    # Admin config save (含 prompt): can_manage_sales_trainer_prompts
    # Hard trigger: any non-empty prompt binding requires manage_prompts.
    if (
        payload.prompt_template_id or payload.scoring_prompt_template_id
    ) and not can_manage_sales_trainer_prompts(current_user):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message="无权修改 AI 教练 Prompt 配置。",
        )

    # Field-level RBAC: any other admin field in
    # ``AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS`` also requires
    # ``manage_prompts`` (e.g. mastery_threshold, min/max_turns, coach_mode,
    # allowed_interaction_types, retry_policy, failure_behavior, model
    # selection). This closes the gap where a content_admin could
    # previously rewrite scoring rules without manage_prompts.
    submitted_fields = set(payload.model_fields_set or set())
    high_risk_overlap = submitted_fields & set(
        AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS
    )
    if (
        high_risk_overlap
        and not can_manage_sales_trainer_prompts(current_user)
    ):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message=(
                "无权修改以下高风险 AI 教练字段："
                + ", ".join(sorted(high_risk_overlap))
            ),
        )

    pinned_schema = AI_COACH_INTERACTION_SCHEMA_VERSION
    if payload.output_schema_version != pinned_schema:
        return _api_error(
            "[AI_COACH_SCHEMA_VERSION_MISMATCH]",
            status_code=409,
            message=(
                "output_schema_version 由后端固定为 "
                f"{pinned_schema}，admin 不能提交其他值。"
            ),
        )

    path_service = SalesTrainerPathConfigService(db)
    path_response = await path_service.get_config()
    path_payload = path_response.get("path")

    if path_payload is None:
        return _api_error(
            "[NEWCOMER_PATH_CONFIG_NOT_FOUND]",
            status_code=404,
            message="新人训练路径配置不存在。",
        )

    from sales_trainer.schemas import (
        NewcomerPathConfigPayload,
        NewcomerPathConfigSaveRequest,
        NewcomerPathModuleConfig,
    )

    try:
        existing_payload = NewcomerPathConfigPayload.model_validate(path_payload)
    except Exception:
        return _api_error(
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            status_code=500,
            message="新人训练路径配置格式错误。",
        )

    # Find and update the module
    updated_modules: list[NewcomerPathModuleConfig] = []
    module_found = False
    for module in existing_payload.modules:
        if module.module_key == module_key:
            module_found = True
            persisted_payload = payload.model_dump(mode="json")
            persisted_payload["prompt_contract_hash"] = None
            persisted_payload["scoring_contract_hash"] = None
            persisted_payload["output_schema_version"] = pinned_schema
            updated_modules.append(
                NewcomerPathModuleConfig(
                    **{
                        **module.model_dump(mode="json"),
                        "ai_coach": persisted_payload,
                    }
                )
            )
        else:
            updated_modules.append(module)

    if not module_found:
        return _api_error(
            "[NEWCOMER_MODULE_NOT_FOUND]",
            status_code=404,
            message="模块不存在。",
        )

    save_request = NewcomerPathConfigSaveRequest(
        path_key=existing_payload.path_key,
        title=existing_payload.title,
        goal_title=existing_payload.goal_title,
        description=existing_payload.description,
        enabled=existing_payload.enabled,
        modules=updated_modules,
        reason=f"更新模块 {module_key} 的 AI 教练配置",
    )

    try:
        revision = await path_service.save_config(
            save_request,
            actor=current_user,
        )
    except Exception as exc:
        if isinstance(exc, SalesTrainerPathConfigError):
            return _api_error(
                exc.code, status_code=exc.status_code, message=exc.message
            )
        return _api_error(
            "[AI_COACH_CONFIG_SAVE_FAILED]",
            status_code=500,
            message="保存 AI 教练配置失败。",
        )

    response_payload = payload.model_dump(mode="json")
    response_payload["output_schema_version"] = pinned_schema
    response_payload["prompt_contract_hash"] = None
    response_payload["scoring_contract_hash"] = None

    return JSONResponse(
        status_code=200,
        content=success_response(
            data={
                "module_key": module_key,
                "ai_coach": response_payload,
                "revision_id": str(revision.revision_id),
                "revision_no": revision.revision_no,
            },
            message="AI 教练配置保存成功。",
        ),
    )


@router.post("/{module_key}/ai-coach/config/publish")
async def publish_ai_coach_config(
    module_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Publish the latest working path-config revision (which may contain the AI 教练 config).

    The AI 教练 config is stored as a nested field of NewcomerPathModuleConfig and
    therefore ships via the existing path_config publish workflow (NewcomerPathConfigService.publish_config).
    This endpoint simply exposes a shortcut so admins can publish from the AI 教练 tab
    without navigating back to the path-config center.

    NOTE: callers cannot supply an arbitrary ``revision_id`` here — the
    publish workflow always promotes the latest working revision. Any
    external rollback must go through the dedicated
    ``POST /admin/newcomer-training/path-config/rollback`` endpoint and
    is constrained to published revisions by the path-config service.
    """
    if not can_manage_sales_trainer_modules(current_user):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message="无权发布 AI 教练配置。",
        )

    path_service = SalesTrainerPathConfigService(db)
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
            )
        result = await path_service.publish_config(
            actor=current_user,
            reason=f"发布商务技巧 AI 教练配置（模块 {module_key}）",
        )
    except Exception as exc:
        if isinstance(exc, SalesTrainerPathConfigError):
            return _api_error(
                exc.code, status_code=exc.status_code, message=exc.message
            )
        return _api_error(
            "[AI_COACH_CONFIG_PUBLISH_FAILED]",
            status_code=500,
            message="发布 AI 教练配置失败。",
        )

    return JSONResponse(
        status_code=200,
        content=success_response(
            data={
                "module_key": module_key,
                "active_revision_id": str(result.revision.revision_id),
                "active_revision_no": result.revision.revision_no,
                "previous_revision_id": result.previous_revision_id,
                "change_class": str(result.revision.change_class),
                "impact_scope": "future_learners_only",
            },
            message="AI 教练配置已发布，只影响后续学员。",
        ),
    )


@router.post("/{module_key}/ai-coach/config/rollback")
async def rollback_ai_coach_config(
    module_key: str,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Roll back the AI 教练 (path) config to a previously published revision.

    Enforces that ``revision_id`` refers to a *published* revision. Working
    revisions cannot be the target of a rollback; admins must publish them
    first via the dedicated ``publish`` endpoint. This matches the
    path-config rollback workflow and keeps the audit trail consistent.
    """
    if not can_manage_sales_trainer_modules(current_user):
        return _api_error(
            "[PERMISSION_DENIED]",
            status_code=403,
            message="无权回滚 AI 教练配置。",
        )

    revision_id = (payload or {}).get("revision_id")
    reason = (payload or {}).get("reason") or f"回滚 {module_key} AI 教练配置"
    if not isinstance(revision_id, str) or not revision_id:
        return _api_error(
            "[AI_COACH_REVISION_ID_REQUIRED]",
            status_code=400,
            message="rollback 必须提供 revision_id。",
        )

    path_service = SalesTrainerPathConfigService(db)
    try:
        changed_high_risk = await changed_ai_coach_high_risk_fields_for_rollback(
            db,
            revision_id,
        )
        if changed_high_risk and not can_manage_sales_trainer_prompts(current_user):
            return _api_error(
                "[PERMISSION_DENIED]",
                status_code=403,
                message=(
                    "无权回滚以下 AI 教练高风险字段："
                    + ", ".join(sorted(changed_high_risk))
                ),
            )
        result = await path_service.rollback_config(
            revision_id=revision_id,
            actor=current_user,
            reason=reason,
        )
    except Exception as exc:
        if isinstance(exc, SalesTrainerPathConfigError):
            return _api_error(
                exc.code, status_code=exc.status_code, message=exc.message
            )
        return _api_error(
            "[AI_COACH_CONFIG_ROLLBACK_FAILED]",
            status_code=500,
            message="回滚 AI 教练配置失败。",
        )

    return JSONResponse(
        status_code=200,
        content=success_response(
            data={
                "module_key": module_key,
                "active_revision_id": str(result.revision.revision_id),
                "active_revision_no": result.revision.revision_no,
                "previous_revision_id": result.previous_revision_id,
                "change_class": str(result.revision.change_class),
                "impact_scope": "future_learners_only",
            },
            message="AI 教练配置已回滚到指定 published revision。",
        ),
    )


__all__ = [
    "router",
    "requires_manage_prompts",
    "AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS",
]

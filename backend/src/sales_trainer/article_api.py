from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from sales_trainer.permissions import can_manage_sales_trainer
from sales_trainer.schemas import (
    NewcomerArticleBinding,
    NewcomerArticleBindingUpdate,
    NewcomerArticleResponse,
)
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)

newcomer_article_router = APIRouter(
    prefix="/newcomer-training",
    tags=["newcomer-training-articles"],
)
newcomer_admin_article_router = APIRouter(
    prefix="/admin/newcomer-training",
    tags=["admin-newcomer-training-articles"],
)


def _api_error(
    code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code),
    )


def _require_manager(user: User) -> JSONResponse | None:
    if can_manage_sales_trainer(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足。")


@newcomer_article_router.get(
    "/modules/{module_key}/article",
    response_model=None,
)
async def get_newcomer_module_article(
    module_key: str,
    learning_content_id: str | None = Query(None, min_length=1, max_length=36),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    _ = current_user
    try:
        article = await ArticleBindingService(db).resolve_module_article(
            NewcomerArticleBinding(
                module_key=module_key,
                learning_content_id=learning_content_id,
            )
        )
    except ArticleBindingServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        NewcomerArticleResponse.model_validate(article).model_dump()
    )


@newcomer_admin_article_router.put(
    "/modules/{module_key}/article-binding",
    response_model=None,
)
async def bind_newcomer_module_article(
    module_key: str,
    payload: NewcomerArticleBindingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        binding = await ArticleBindingService(db).bind_module_article(
            NewcomerArticleBinding(
                module_key=module_key,
                learning_content_id=payload.learning_content_id,
            ),
            path_key=payload.path_key,
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
    except ArticleBindingServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(binding.model_dump(), trace_id=trace_id)

from __future__ import annotations

from typing import Any, cast

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
    LearningContentBindingImpactResponse,
    NewcomerArticleBinding,
    NewcomerArticleBindingUpdate,
    NewcomerArticleProgressRequest,
    NewcomerArticleProgressResponse,
    NewcomerArticleResponse,
)
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)
from sales_trainer.services.curriculum_practice_adapter import (
    LearningProgressAdapter,
    LearningProgressChapterRef,
)
from sales_trainer.services.learner_unit_access import (
    LearnerUnitAccessError,
    require_learner_active_path_module_access,
)
from sales_trainer.services.learning_content_binding_impact_service import (
    LearningContentBindingImpactService,
    LearningContentBindingImpactServiceError,
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
            ),
            require_active_binding=True,
        )
        await require_learner_active_path_module_access(
            db,
            actor=current_user,
            module_key=module_key,
        )
    except ArticleBindingServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    except LearnerUnitAccessError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        NewcomerArticleResponse.model_validate(article).model_dump()
    )


@newcomer_article_router.get(
    "/modules/{module_key}/article-progress",
    response_model=None,
)
async def get_newcomer_module_article_progress(
    module_key: str,
    learning_content_id: str | None = Query(None, min_length=1, max_length=36),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        article_service = ArticleBindingService(db)
        article = await article_service.resolve_module_article(
            NewcomerArticleBinding(
                module_key=module_key,
                learning_content_id=learning_content_id,
            ),
            require_active_binding=True,
        )
        await require_learner_active_path_module_access(
            db,
            actor=current_user,
            module_key=module_key,
        )
    except ArticleBindingServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    except LearnerUnitAccessError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)

    learning_content_id = str(article["learning_content_id"])
    raw_chapters = cast(list[dict[str, Any]], article.get("chapters", []))

    progress_service = LearningProgressAdapter(db)
    progress_result = await progress_service.progress_for_user(
        user_id=str(current_user.user_id),
        content_id=learning_content_id,
        chapters=[
            LearningProgressChapterRef(chapter_id=str(ch["chapter_id"]))
            for ch in raw_chapters
        ],
    )
    if not progress_result.is_success or progress_result.value is None:
        return _api_error(
            "[NEWCOMER_MODULE_PROGRESS_ERROR]",
            status_code=500,
            message="读取阅读进度失败。",
        )

    progress = progress_result.value
    return success_response(
        NewcomerArticleProgressResponse(
            module_key=module_key,
            learning_content_id=learning_content_id,
            completed_chapter_ids=progress.completed_chapter_ids,
            total_chapters=progress.total_chapters,
            is_completed=progress.is_completed,
        ).model_dump()
    )


@newcomer_article_router.post(
    "/modules/{module_key}/article-progress",
    response_model=None,
)
async def complete_newcomer_module_article_chapter(
    module_key: str,
    payload: NewcomerArticleProgressRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        article_service = ArticleBindingService(db)
        article = await article_service.resolve_module_article(
            NewcomerArticleBinding(
                module_key=module_key,
                learning_content_id=payload.learning_content_id,
            ),
            require_active_binding=True,
        )
        await require_learner_active_path_module_access(
            db,
            actor=current_user,
            module_key=module_key,
        )
    except ArticleBindingServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    except LearnerUnitAccessError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)

    learning_content_id = str(article["learning_content_id"])

    # If the caller pinned a specific learning_content_id, it must match
    # the module's current binding. This guards against stale clients
    # writing progress against a version the path-config has since
    # replaced.
    if (
        payload.learning_content_id is not None
        and str(payload.learning_content_id) != learning_content_id
    ):
        return _api_error(
            "[LEARNING_CONTENT_MISMATCH]",
            status_code=409,
            message=(
                "请求的 learning_content_id 与模块当前绑定的学习内容不一致。"
            ),
        )

    progress_service = LearningProgressAdapter(db)
    complete_result = await progress_service.complete_chapter(
        user_id=str(current_user.user_id),
        content_id=learning_content_id,
        chapter_id=payload.chapter_id,
    )
    if not complete_result.is_success or complete_result.value is None:
        return _api_error(
            "[NEWCOMER_MODULE_PROGRESS_ERROR]",
            status_code=500,
            message="记录阅读进度失败。",
        )

    completed = complete_result.value
    return success_response(
        NewcomerArticleProgressResponse(
            module_key=module_key,
            learning_content_id=learning_content_id,
            completed_chapter_ids=completed.progress.completed_chapter_ids,
            total_chapters=completed.progress.total_chapters,
            is_completed=completed.progress.is_completed,
        ).model_dump()
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


@newcomer_admin_article_router.get(
    "/learning-contents/{content_id}/binding-impact",
    response_model=None,
)
async def get_learning_content_binding_impact(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        impact = await LearningContentBindingImpactService(db).get_impact(content_id)
    except LearningContentBindingImpactServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        LearningContentBindingImpactResponse.model_validate(impact).model_dump()
    )

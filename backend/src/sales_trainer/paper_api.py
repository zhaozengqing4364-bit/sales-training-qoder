from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.paper_route_registration import (
    add_paper_admin_routes,
    add_paper_learner_routes,
)
from sales_trainer.permissions import can_manage_sales_trainer
from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperListResponse,
    ExamPaperResponse,
    ExamPaperRevisionListResponse,
    ExamPaperRevisionResponse,
    ExamPaperUpdate,
    PaperAttemptCreate,
    PaperAttemptResponse,
    PaperRollbackRequest,
)
from sales_trainer.services.exam_paper_serializers import (
    ExamPaperSerializationError,
)
from sales_trainer.services.exam_paper_service import (
    ExamPaperService,
    ExamPaperServiceError,
)

sales_trainer_paper_router = APIRouter(
    prefix="/sales-trainer", tags=["sales-trainer-papers"]
)
sales_trainer_admin_paper_router = APIRouter(
    prefix="/admin/sales-trainer", tags=["admin-sales-trainer-papers"]
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


async def _admin_list_exam_papers(
    include_archived: bool,
    limit: int,
    offset: int,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    papers, total = await service.list_papers(
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    try:
        items = [
            ExamPaperResponse.model_validate(
                await service.serialize_paper(paper)
            ).model_dump()
            for paper in papers
        ]
    except ExamPaperSerializationError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperListResponse(items=items, total=total))


async def _admin_create_exam_paper(
    payload: ExamPaperCreate,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    try:
        paper = await service.create_paper(payload, actor=current_user)
        serialized = await service.serialize_paper(paper)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperResponse.model_validate(serialized).model_dump())


async def _admin_update_exam_paper(
    paper_id: str,
    payload: ExamPaperUpdate,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    try:
        paper = await service.update_paper(paper_id, payload, actor=current_user)
        serialized = await service.serialize_paper(paper)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperResponse.model_validate(serialized).model_dump())


async def _admin_list_exam_paper_revisions(
    paper_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    try:
        revisions = await service.list_paper_revisions(paper_id)
    except ExamPaperServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [
        ExamPaperRevisionResponse.model_validate(item).model_dump()
        for item in revisions
    ]
    return success_response(
        ExamPaperRevisionListResponse(items=items, total=len(items))
    )


async def _admin_publish_exam_paper(
    paper_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    try:
        paper = await service.publish_paper(paper_id, actor=current_user)
        serialized = await service.serialize_paper(paper)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperResponse.model_validate(serialized).model_dump())


async def _admin_archive_exam_paper(
    paper_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    try:
        paper = await service.archive_paper(paper_id, actor=current_user)
        serialized = await service.serialize_paper(paper)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperResponse.model_validate(serialized).model_dump())


async def _admin_rollback_exam_paper(
    paper_id: str,
    payload: PaperRollbackRequest,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = ExamPaperService(db)
    try:
        paper = await service.rollback_paper(paper_id, payload, actor=current_user)
        serialized = await service.serialize_paper(paper)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperResponse.model_validate(serialized).model_dump())


async def _learner_get_exam_paper(
    paper_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    _ = current_user
    service = ExamPaperService(db)
    try:
        paper = await service.get_published_paper(paper_id)
        serialized = await service.serialize_paper(paper)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(ExamPaperResponse.model_validate(serialized).model_dump())


async def _learner_submit_exam_paper_attempt(
    payload: PaperAttemptCreate,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    service = ExamPaperService(db)
    try:
        attempt = await service.submit_paper_attempt(payload, actor=current_user)
        serialized = await service.serialize_attempt(attempt)
    except (ExamPaperServiceError, ExamPaperSerializationError) as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        PaperAttemptResponse.model_validate(serialized).model_dump()
    )


async def admin_list_exam_papers(
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_list_exam_papers(
        include_archived,
        limit,
        offset,
        current_user,
        db,
    )


async def admin_create_exam_paper(
    payload: ExamPaperCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_create_exam_paper(payload, current_user, db)


async def admin_update_exam_paper(
    paper_id: str,
    payload: ExamPaperUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_update_exam_paper(paper_id, payload, current_user, db)


async def admin_list_exam_paper_revisions(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_list_exam_paper_revisions(paper_id, current_user, db)


async def admin_publish_exam_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_publish_exam_paper(paper_id, current_user, db)


async def admin_archive_exam_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_archive_exam_paper(paper_id, current_user, db)


async def admin_rollback_exam_paper(
    paper_id: str,
    payload: PaperRollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _admin_rollback_exam_paper(paper_id, payload, current_user, db)


async def get_exam_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _learner_get_exam_paper(paper_id, current_user, db)


async def submit_exam_paper_attempt(
    payload: PaperAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _learner_submit_exam_paper_attempt(payload, current_user, db)


add_paper_admin_routes(
    sales_trainer_admin_paper_router,
    list_handler=admin_list_exam_papers,
    create_handler=admin_create_exam_paper,
    update_handler=admin_update_exam_paper,
    revisions_handler=admin_list_exam_paper_revisions,
    publish_handler=admin_publish_exam_paper,
    archive_handler=admin_archive_exam_paper,
    rollback_handler=admin_rollback_exam_paper,
)

add_paper_learner_routes(
    sales_trainer_paper_router,
    get_handler=get_exam_paper,
    submit_handler=submit_exam_paper_attempt,
)

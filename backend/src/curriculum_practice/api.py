from __future__ import annotations

import base64
import binascii
import os
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import CaseItem, RoleProfile
from curriculum_practice.permissions import can_manage_practice_templates
from curriculum_practice.schemas import (
    CaseItemCreate,
    CaseItemListResponse,
    CaseItemResponse,
    PracticeTemplateCreate,
    PracticeTemplateListResponse,
    PracticeTemplateUpdate,
    RoleProfileCreate,
    RoleProfileListResponse,
    RoleProfileResponse,
    RoleProfileVoiceCloneRequest,
    RoleProfileVoiceCloneResponse,
)
from curriculum_practice.services.content_assets import (
    ContentAssetNotEditableError,
    ContentAssetPublishError,
    ContentAssetService,
)
from curriculum_practice.services.practice_templates import (
    PracticeTemplateNotEditableError,
    PracticeTemplateService,
    published_ref,
    serialize_template,
)
from curriculum_practice.services.voice_clone import VoiceCloneService

ALLOWED_VOICE_AUDIO_CONTENT_TYPES = frozenset(
    {"audio/wav", "audio/mpeg", "audio/webm", "audio/mp4"}
)
MAX_VOICE_AUDIO_BYTES = 10 * 1024 * 1024

router = APIRouter(
    prefix="/admin/curriculum-practice", tags=["admin-curriculum-practice"]
)


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": get_trace_id()}


def _api_error(
    error_code: str, *, status_code: int = 400, message: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(error_code, message=message or error_code),
    )


def _require_admin(current_user: User) -> JSONResponse | None:
    if can_manage_practice_templates(current_user):
        return None
    return _api_error(
        "[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足，无法执行该操作。"
    )


def _not_found() -> JSONResponse:
    return _api_error(
        "[PRACTICE_TEMPLATE_NOT_FOUND]",
        status_code=404,
        message="PracticeTemplate 不存在。",
    )


def _case_item_not_found() -> JSONResponse:
    return _api_error(
        "[CASE_ITEM_NOT_FOUND]",
        status_code=404,
        message="CaseItem 不存在。",
    )


def _role_profile_not_found() -> JSONResponse:
    return _api_error(
        "[ROLE_PROFILE_NOT_FOUND]",
        status_code=404,
        message="RoleProfile 不存在。",
    )


def _serialize_case_item(item: CaseItem) -> CaseItemResponse:
    return CaseItemResponse.model_validate(item)


def _serialize_role_profile(item: RoleProfile) -> RoleProfileResponse:
    return RoleProfileResponse.model_validate(item)


def _decode_voice_audio(payload: RoleProfileVoiceCloneRequest) -> bytes | JSONResponse:
    content_type = payload.content_type.strip().lower()
    if content_type not in ALLOWED_VOICE_AUDIO_CONTENT_TYPES:
        return _api_error(
            "[ROLE_PROFILE_VOICE_CONTENT_TYPE_UNSUPPORTED]",
            status_code=400,
            message="Voice sample content_type must be a supported audio format.",
        )
    encoded_size_limit = ((MAX_VOICE_AUDIO_BYTES + 2) // 3) * 4
    if len(payload.audio_base64) > encoded_size_limit:
        return _api_error(
            "[ROLE_PROFILE_VOICE_AUDIO_TOO_LARGE]",
            status_code=400,
            message="Voice sample is too large.",
        )
    try:
        audio_bytes = base64.b64decode(payload.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        return _api_error(
            "[ROLE_PROFILE_VOICE_AUDIO_INVALID]",
            status_code=400,
            message="Voice sample must be valid base64 audio.",
        )
    if len(audio_bytes) > MAX_VOICE_AUDIO_BYTES:
        return _api_error(
            "[ROLE_PROFILE_VOICE_AUDIO_TOO_LARGE]",
            status_code=400,
            message="Voice sample is too large.",
        )
    if not _looks_like_audio(audio_bytes, content_type):
        return _api_error(
            "[ROLE_PROFILE_VOICE_AUDIO_INVALID]",
            status_code=400,
            message="Voice sample does not look like supported audio content.",
        )
    return audio_bytes


def _looks_like_audio(audio_bytes: bytes, content_type: str) -> bool:
    if content_type == "audio/wav":
        return audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]
    if content_type == "audio/mpeg":
        return audio_bytes.startswith(b"ID3") or audio_bytes.startswith((b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"))
    if content_type in {"audio/webm", "audio/mp4"}:
        return bool(audio_bytes)
    return False


@router.get("/templates", response_model=None)
async def list_practice_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    items = await service.list_templates()
    payload = PracticeTemplateListResponse(
        items=[serialize_template(item) for item in items],
        total=len(items),
    )
    return _success(payload)


@router.post("/templates", response_model=None)
async def create_practice_template(
    payload: PracticeTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    try:
        template = await service.create_template(
            payload, actor_id=str(current_user.user_id)
        )
        return _success(serialize_template(template))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_CREATE_FAILED]",
            message="PracticeTemplate 创建失败。",
            exc=exc,
        )


@router.get("/templates/{template_id}", response_model=None)
async def get_practice_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        return _not_found()
    return _success(serialize_template(template))


@router.put("/templates/{template_id}", response_model=None)
async def update_practice_template(
    template_id: str,
    payload: PracticeTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        return _not_found()
    try:
        updated = await service.update_template(
            template, payload, actor_id=str(current_user.user_id)
        )
        return _success(serialize_template(updated))
    except PracticeTemplateNotEditableError:
        await db.rollback()
        return _api_error(
            "[PRACTICE_TEMPLATE_NOT_EDITABLE]",
            status_code=409,
            message="Only draft PracticeTemplate records can be edited.",
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_UPDATE_FAILED]",
            message="PracticeTemplate 更新失败。",
            exc=exc,
        )


@router.post("/templates/{template_id}/archive", response_model=None)
async def archive_practice_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        return _not_found()
    try:
        archived = await service.archive_template(
            template, actor_id=str(current_user.user_id)
        )
        return _success(serialize_template(archived))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_ARCHIVE_FAILED]",
            message="PracticeTemplate 归档失败。",
            exc=exc,
        )


@router.post("/templates/{template_id}/publish", response_model=None)
async def publish_practice_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        return _not_found()
    try:
        published, decision = await service.publish_template(
            template, actor_id=str(current_user.user_id)
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_PUBLISH_FAILED]",
            message="PracticeTemplate 发布失败。",
            exc=exc,
        )
    if published is None:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[PRACTICE_TEMPLATE_PUBLISH_GATE_FAILED]",
                message="PracticeTemplate 发布门禁未通过。",
            )
            | {
                "details": {
                    "gate_results": [item.model_dump() for item in decision.results]
                }
            },
        )
    data = serialize_template(published).model_dump()
    data["published_ref"] = published_ref(published).model_dump()
    return _success(data)


@router.get("/case-items", response_model=None)
async def list_case_items(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    items = await service.list_case_items()
    return _success(
        CaseItemListResponse(
            items=[_serialize_case_item(item) for item in items], total=len(items)
        )
    )


@router.post("/case-items", response_model=None)
async def create_case_item(
    payload: CaseItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    try:
        item = await service.create_case_item(payload, actor_id=str(current_user.user_id))
        return _success(_serialize_case_item(item))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[CASE_ITEM_CREATE_FAILED]",
            message="CaseItem 创建失败。",
            exc=exc,
        )


@router.get("/case-items/{case_item_id}", response_model=None)
async def get_case_item(
    case_item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    item = await ContentAssetService(db).get_case_item(case_item_id)
    if item is None:
        return _case_item_not_found()
    return _success(_serialize_case_item(item))


@router.put("/case-items/{case_item_id}", response_model=None)
async def update_case_item(
    case_item_id: str,
    payload: CaseItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_case_item(case_item_id)
    if item is None:
        return _case_item_not_found()
    try:
        updated = await service.update_case_item(
            item, payload, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_case_item(updated))
    except ContentAssetNotEditableError:
        await db.rollback()
        return _api_error(
            "[CASE_ITEM_NOT_EDITABLE]",
            status_code=409,
            message="Only draft CaseItem records can be edited.",
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[CASE_ITEM_UPDATE_FAILED]",
            message="CaseItem 更新失败。",
            exc=exc,
        )


@router.post("/case-items/{case_item_id}/publish", response_model=None)
async def publish_case_item(
    case_item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_case_item(case_item_id)
    if item is None:
        return _case_item_not_found()
    try:
        published = await service.publish_case_item(
            item, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_case_item(published))
    except ContentAssetPublishError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[CASE_ITEM_PUBLISH_FAILED]",
                message=str(exc),
            )
            | {"details": {"reason_code": exc.reason_code}},
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[CASE_ITEM_PUBLISH_FAILED]",
            message="CaseItem 发布失败。",
            exc=exc,
        )


@router.post("/case-items/{case_item_id}/archive", response_model=None)
async def archive_case_item(
    case_item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_case_item(case_item_id)
    if item is None:
        return _case_item_not_found()
    try:
        archived = await service.archive_case_item(
            item, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_case_item(archived))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[CASE_ITEM_ARCHIVE_FAILED]",
            message="CaseItem 归档失败。",
            exc=exc,
        )


@router.get("/role-profiles", response_model=None)
async def list_role_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    items = await service.list_role_profiles()
    return _success(
        RoleProfileListResponse(
            items=[_serialize_role_profile(item) for item in items], total=len(items)
        )
    )


@router.post("/role-profiles", response_model=None)
async def create_role_profile(
    payload: RoleProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    try:
        item = await service.create_role_profile(
            payload, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_role_profile(item))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_CREATE_FAILED]",
            message="RoleProfile 创建失败。",
            exc=exc,
        )


@router.get("/role-profiles/{role_profile_id}", response_model=None)
async def get_role_profile(
    role_profile_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    item = await ContentAssetService(db).get_role_profile(role_profile_id)
    if item is None:
        return _role_profile_not_found()
    return _success(_serialize_role_profile(item))


@router.put("/role-profiles/{role_profile_id}", response_model=None)
async def update_role_profile(
    role_profile_id: str,
    payload: RoleProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_role_profile(role_profile_id)
    if item is None:
        return _role_profile_not_found()
    try:
        updated = await service.update_role_profile(
            item, payload, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_role_profile(updated))
    except ContentAssetNotEditableError:
        await db.rollback()
        return _api_error(
            "[ROLE_PROFILE_NOT_EDITABLE]",
            status_code=409,
            message="Only draft RoleProfile records can be edited.",
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_UPDATE_FAILED]",
            message="RoleProfile 更新失败。",
            exc=exc,
        )


@router.post("/role-profiles/{role_profile_id}/publish", response_model=None)
async def publish_role_profile(
    role_profile_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_role_profile(role_profile_id)
    if item is None:
        return _role_profile_not_found()
    try:
        published = await service.publish_role_profile(
            item, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_role_profile(published))
    except ContentAssetPublishError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[ROLE_PROFILE_PUBLISH_FAILED]",
                message=str(exc),
            )
            | {"details": {"reason_code": exc.reason_code}},
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_PUBLISH_FAILED]",
            message="RoleProfile 发布失败。",
            exc=exc,
        )


@router.post("/role-profiles/{role_profile_id}/voice-clone", response_model=None)
async def clone_role_profile_voice(
    role_profile_id: str,
    payload: RoleProfileVoiceCloneRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_role_profile(role_profile_id)
    if item is None:
        return _role_profile_not_found()
    audio_bytes_or_error = _decode_voice_audio(payload)
    if isinstance(audio_bytes_or_error, JSONResponse):
        return audio_bytes_or_error
    audio_bytes = audio_bytes_or_error
    voice_service = getattr(request.app.state, "voice_clone_service", None)
    if voice_service is None:
        voice_service = VoiceCloneService(
            transport=None,
            endpoint_url=os.getenv("STEPFUN_VOICE_CLONE_ENDPOINT"),
            fallback_voice=os.getenv("STEPFUN_DEFAULT_VOICE", "default_voice"),
        )
    try:
        result = await service.register_role_profile_voice(
            item,
            voice_service=voice_service,
            voice_name=payload.voice_name,
            audio_bytes=audio_bytes,
            content_type=payload.content_type,
            voice_sample_url=payload.voice_sample_url,
            actor_id=str(current_user.user_id),
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_VOICE_CLONE_FAILED]",
            message="RoleProfile voice clone failed.",
            exc=exc,
        )
    except ContentAssetNotEditableError:
        await db.rollback()
        return _api_error(
            "[ROLE_PROFILE_NOT_EDITABLE]",
            status_code=409,
            message="Only draft RoleProfile records can be edited.",
        )
    response = RoleProfileVoiceCloneResponse(
        voice_id=result.voice_id,
        voice_sample_url=payload.voice_sample_url if result.ok else None,
        fallback_voice=result.fallback_voice,
        reason_code=result.reason_code,
        retryable=result.retryable,
    )
    return _success(response)


@router.post("/role-profiles/{role_profile_id}/archive", response_model=None)
async def archive_role_profile(
    role_profile_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    item = await service.get_role_profile(role_profile_id)
    if item is None:
        return _role_profile_not_found()
    try:
        archived = await service.archive_role_profile(
            item, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_role_profile(archived))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_ARCHIVE_FAILED]",
            message="RoleProfile 归档失败。",
            exc=exc,
        )

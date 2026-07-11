from __future__ import annotations

import base64
import binascii
import os
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import (
    CaseItem,
    ExaminerAgent,
    RoleProfile,
)
from curriculum_practice.permissions import can_manage_practice_templates
from curriculum_practice.schemas import (
    CaseItemCreate,
    CaseItemListResponse,
    CaseItemResponse,
    ExaminerAgentCreate,
    ExaminerAgentListResponse,
    ExaminerAgentResponse,
    ExaminerAgentSimulationRequest,
    ExaminerAgentUpdate,
    LearnerAdminOverrideRequest,
    LearnerProfileResponse,
    LearnerSelfAssessmentRequest,
    LearningChapterCreate,
    LearningChapterReorderRequest,
    LearningChapterUpdate,
    LearningContentCreate,
    LearningContentListResponse,
    LearningContentUpdate,
    PracticeTemplateCreate,
    PracticeTemplateListResponse,
    PracticeTemplateUpdate,
    PublishGateDecision,
    QuestionCategoryCreate,
    QuestionCategoryListResponse,
    QuestionCategoryUpdate,
    QuestionGenerationConfirmRequest,
    QuestionGenerationConfirmResponse,
    QuestionGenerationPreviewRequest,
    QuestionGenerationPreviewResponse,
    QuestionItemCreate,
    QuestionItemListResponse,
    QuestionItemUpdate,
    RoleProfileCreate,
    RoleProfileListResponse,
    RoleProfileResponse,
    RoleProfileVoiceCloneRequest,
    RoleProfileVoiceCloneResponse,
    TemplateReferenceListResponse,
    UnpublishAcknowledgeRequest,
)
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.content_assets import (
    ContentAssetAlreadyDraftError,
    ContentAssetNotEditableError,
    ContentAssetPublishError,
    ContentAssetReferencedByTemplatesError,
    ContentAssetService,
)
from curriculum_practice.services.examiner_agents import (
    ExaminerAgentService,
    serialize_examiner_agent,
)
from curriculum_practice.services.examiner_report_service import ExaminerReportService
from curriculum_practice.services.learner_profiles import LearnerProfileService
from curriculum_practice.services.learning_content_serializers import (
    serialize_chapter,
    serialize_learning_content,
)
from curriculum_practice.services.learning_contents import (
    SERVER_ERROR as LEARNING_CONTENT_SERVICE_FAILED,
)
from curriculum_practice.services.learning_contents import LearningContentService
from curriculum_practice.services.learning_path import LearningPathService
from curriculum_practice.services.learning_progress_service import (
    SERVER_ERROR as LEARNING_PROGRESS_SERVICE_FAILED,
)
from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from curriculum_practice.services.practice_templates import (
    PracticeTemplateNotEditableError,
    PracticeTemplateService,
    published_ref,
    serialize_template,
)
from curriculum_practice.services.question_generation import QuestionGenerationService
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.roleplay_contracts import (
    RoleplaySituationPackAdminService,
    build_roleplay_contract_compiler,
)
from curriculum_practice.services.roleplay_runtime_dossier_preview import (
    RoleplayRuntimeDossierPreviewService,
)
from curriculum_practice.services.test_bank import (
    SERVER_ERROR as TEST_BANK_SERVICE_FAILED,
)
from curriculum_practice.services.test_bank import (
    TestBankService,
    serialize_category,
    serialize_import_job,
    serialize_question,
)
from curriculum_practice.services.test_bank_importer import IMPORT_MAX_BYTES
from curriculum_practice.services.voice_clone import (
    VoiceCloneHTTPTransport,
    VoiceCloneService,
)
from roleplay.compiler import RoleplayContractCompileError

ALLOWED_VOICE_AUDIO_CONTENT_TYPES = frozenset(
    {"audio/wav", "audio/mpeg", "audio/webm", "audio/mp4"}
)
MAX_VOICE_AUDIO_BYTES = 10 * 1024 * 1024

router = APIRouter(
    prefix="/admin/curriculum-practice", tags=["admin-curriculum-practice"]
)
learner_router = APIRouter(
    prefix="/curriculum-practice/learning-path", tags=["curriculum-practice-learning-path"]
)
study_router = APIRouter(
    prefix="/curriculum-practice/study", tags=["curriculum-practice-study"]
)
learning_content_router = APIRouter(
    prefix="/curriculum/learning-contents", tags=["admin-learning-contents"]
)
test_bank_router = APIRouter(
    prefix="/curriculum/test-bank", tags=["admin-test-bank"]
)


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": get_trace_id()}


@learner_router.get("/me", response_model=None)
async def get_my_learning_path(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        path = await LearningPathService(db).build_for_user(str(current_user.user_id))
        return _success(path)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[LEARNING_PATH_FETCH_FAILED]",
            message="学习路径暂时无法读取。",
            exc=exc,
        )


@learner_router.get("/me/next-task", response_model=None)
async def get_my_learning_path_next_task(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        next_task = await LearningPathService(db).next_task_for_user(
            str(current_user.user_id)
        )
        return _success(next_task)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[LEARNING_PATH_NEXT_TASK_FETCH_FAILED]",
            message="下一步训练暂时无法读取。",
            exc=exc,
        )


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


def _examiner_agent_not_found() -> JSONResponse:
    return _api_error(
        "[EXAMINER_AGENT_NOT_FOUND]",
        status_code=404,
        message="ExaminerAgent 不存在。",
    )


def _learning_content_not_found() -> JSONResponse:
    return _api_error(
        "[LEARNING_CONTENT_NOT_FOUND]",
        status_code=404,
        message="LearningContent 不存在。",
    )


def _learning_chapter_not_found() -> JSONResponse:
    return _api_error(
        "[LEARNING_CHAPTER_NOT_FOUND]",
        status_code=404,
        message="LearningChapter 不存在。",
    )


def _learning_progress_result_error(fallback: str | None) -> JSONResponse:
    if fallback == "[LEARNING_CONTENT_NOT_FOUND]":
        return _learning_content_not_found()
    if fallback == "[LEARNING_CHAPTER_NOT_FOUND]":
        return _learning_chapter_not_found()
    if fallback == LEARNING_PROGRESS_SERVICE_FAILED:
        return _api_error(
            "[LEARNING_PROGRESS_FAILED]",
            status_code=500,
            message="学习进度暂时无法读取。",
        )
    return _api_error(fallback or "[LEARNING_PROGRESS_FAILED]", status_code=400)


def _test_bank_result_error(
    fallback: str | None,
    *,
    server_error_code: str,
    server_message: str,
) -> JSONResponse:
    error_code = fallback or server_error_code
    if error_code in {"[QUESTION_CATEGORY_NOT_FOUND]", "[QUESTION_ITEM_NOT_FOUND]"}:
        return _api_error(error_code, status_code=404, message=error_code)
    if error_code in {
        "[QUESTION_CATEGORY_HAS_CHILDREN]",
        "[QUESTION_CATEGORY_HAS_QUESTIONS]",
        "[QUESTION_ITEM_NOT_EDITABLE]",
    }:
        return _api_error(error_code, status_code=409, message=error_code)
    if error_code == TEST_BANK_SERVICE_FAILED:
        return _api_error(server_error_code, status_code=500, message=server_message)
    return _api_error(error_code, status_code=400)


def _question_generation_result_error(fallback: str | None) -> JSONResponse:
    error_code = fallback or "[QUESTION_GENERATION_FAILED]"
    if error_code == "[LEARNING_CHAPTER_NOT_FOUND]":
        return _learning_chapter_not_found()
    return _api_error(error_code, status_code=400, message=error_code)


def _question_generation_service(
    request: Request, db: AsyncSession
) -> QuestionGenerationService:
    generator = getattr(request.app.state, "question_generation_generator", None)
    return QuestionGenerationService(db, generator=generator)


def _learner_profile_service_error(fallback: str | None) -> JSONResponse:
    return _api_error(fallback or "[LEARNER_PROFILE_FAILED]", status_code=400)


def _examiner_agent_result_error(fallback: str | None) -> JSONResponse:
    error_code = fallback or "[EXAMINER_AGENT_FAILED]"
    if error_code == "[EXAMINER_AGENT_NOT_FOUND]":
        return _examiner_agent_not_found()
    if error_code == "[EXAMINER_AGENT_NOT_EDITABLE]":
        return _api_error(
            error_code,
            status_code=409,
            message="Only draft ExaminerAgent records can be edited.",
        )
    if error_code == "[EXAMINER_AGENT_SERVICE_FAILED]":
        return _api_error(
            "[EXAMINER_AGENT_FAILED]",
            status_code=500,
            message="ExaminerAgent 操作失败。",
        )
    return _api_error(error_code, status_code=400, message=error_code)


def _examiner_agent_publish_gate_error(decision: object) -> JSONResponse:
    if not isinstance(decision, PublishGateDecision):
        decision = PublishGateDecision(can_publish=False, results=[])
    return JSONResponse(
        status_code=400,
        content=error_response(
            "[EXAMINER_AGENT_PUBLISH_GATE_FAILED]",
            message="ExaminerAgent 发布门禁未通过。",
        )
        | {
            "details": {
                "gate_results": [item.model_dump() for item in decision.results]
            }
        },
    )


def _serialize_examiner_agent(item: ExaminerAgent) -> ExaminerAgentResponse:
    return serialize_examiner_agent(item)


@learner_router.get("/me/profile", response_model=None)
async def get_my_learner_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    result = await LearnerProfileService(db).get_or_create_for_user(
        str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _learner_profile_service_error(result.fallback)
    return _success(LearnerProfileResponse.model_validate(result.value))


@learner_router.post("/me/profile/self-assessment", response_model=None)
async def self_assess_learner_profile(
    payload: LearnerSelfAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    result = await LearnerProfileService(db).record_self_assessment(
        str(current_user.user_id), payload.level
    )
    if not result.is_success or result.value is None:
        return _learner_profile_service_error(result.fallback)
    return _success(LearnerProfileResponse.model_validate(result.value))


@study_router.get("/learning-contents/{content_id}", response_model=None)
async def get_my_study_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    service = LearningProgressService(db)
    result = await service.get_study_content(
        user_id=str(current_user.user_id), content_id=content_id
    )
    if not result.is_success or result.value is None:
        return _learning_progress_result_error(result.fallback)
    return _success(result.value)


@study_router.post(
    "/learning-contents/{content_id}/chapters/{chapter_id}/complete",
    response_model=None,
)
async def complete_my_study_chapter(
    content_id: str,
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    service = LearningProgressService(db)
    result = await service.complete_chapter(
        user_id=str(current_user.user_id),
        content_id=content_id,
        chapter_id=chapter_id,
    )
    if not result.is_success or result.value is None:
        return _learning_progress_result_error(result.fallback)
    return _success(result.value)


@study_router.post("/learning-contents/{content_id}/start-exam", response_model=None)
async def start_my_study_exam(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    progress_service = LearningProgressService(db)
    content_result = await progress_service.get_study_content(
        user_id=str(current_user.user_id), content_id=content_id
    )
    if not content_result.is_success or content_result.value is None:
        return _learning_progress_result_error(content_result.fallback)

    if not content_result.value.progress.is_completed:
        return _api_error(
            "[LEARNING_CONTENT_NOT_COMPLETED]",
            status_code=409,
            message="请先完成全部讲义章节，再开始 AI 考核。",
        )

    from curriculum_practice.services.examiner_session_assembler import (
        ExaminerSessionAssembler,
    )

    try:
        create_result = await ExaminerSessionAssembler(db).create_study_exam_session(
            user_id=str(current_user.user_id),
            learning_content_id=content_id,
        )
    except ValueError as exc:
        error_code = str(exc)
        if error_code == "[TEMPLATE_EXAMINER_NOT_BOUND]":
            return _api_error(
                error_code,
                status_code=409,
                message="该学习内容未绑定已发布的课程模板或 AI 考官，请联系管理员配置。",
            )
        if error_code == "[TEMPLATE_EXAMINER_AMBIGUOUS]":
            return _api_error(
                error_code,
                status_code=409,
                message="该学习内容绑定了多个已发布考核模板，请联系管理员保留唯一模板。",
            )
        if error_code == "[EXAMINER_AGENT_NOT_FOUND]":
            return _api_error(
                error_code,
                status_code=409,
                message="课程模板绑定的 AI 考官不存在或未发布，请联系管理员检查配置。",
            )
        if error_code == "[EXAMINER_AGENT_NOT_AVAILABLE]":
            return _api_error(
                error_code,
                status_code=409,
                message="暂无已发布 AI 考官，请联系管理员发布考官。",
            )
        if error_code == "[EXAM_QUESTION_BANK_EMPTY]":
            return _api_error(
                error_code,
                status_code=409,
                message="AI 考官绑定的题目不可用，请联系管理员检查题库。",
            )
        raise

    return _success(
        {
            "session_id": str(create_result.session.session_id),
            "examiner_agent_id": str(create_result.examiner_agent.examiner_agent_id),
        }
    )


@study_router.get("/exam-sessions/{session_id}/report", response_model=None)
async def get_my_exam_session_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    result = await ExaminerReportService(db).get_report_for_user(
        session_id=session_id,
        user_id=str(current_user.user_id),
    )
    if not result.is_success or result.value is None:
        fallback = result.fallback or "[EXAMINER_REPORT_NOT_FOUND]"
        status_code = 404
        if fallback == "[ACCESS_DENIED]":
            status_code = 403
        return _api_error(fallback, status_code=status_code)
    return _success(result.value)


@router.get("/learner-profiles/{user_id}", response_model=None)
async def get_admin_learner_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await LearnerProfileService(db).get_or_create_for_user(user_id)
    if not result.is_success or result.value is None:
        return _learner_profile_service_error(result.fallback)
    return _success(LearnerProfileResponse.model_validate(result.value))


def _learning_content_result_error(
    fallback: str | None,
    *,
    server_error_code: str,
    server_message: str,
) -> JSONResponse:
    error_code = fallback or server_error_code
    if error_code == "[LEARNING_CONTENT_NOT_FOUND]":
        return _learning_content_not_found()
    if error_code == "[LEARNING_CHAPTER_NOT_FOUND]":
        return _learning_chapter_not_found()
    if error_code == "[LEARNING_CONTENT_NOT_EDITABLE]":
        return _api_error(
            "[LEARNING_CONTENT_NOT_EDITABLE]",
            status_code=409,
            message="Archived LearningContent records cannot be changed.",
        )
    if error_code == "[LEARNING_CONTENT_BOUND_TO_NEWCOMER_PATH]":
        return _api_error(
            "[LEARNING_CONTENT_BOUND_TO_NEWCOMER_PATH]",
            status_code=409,
            message=(
                "该学习内容正在被新人训练路径引用。请先替换绑定并发布路径配置，"
                "再归档学习内容。"
            ),
        )
    if error_code == "[LEARNING_CHAPTER_REORDER_INVALID]":
        return _api_error(
            "[LEARNING_CHAPTER_REORDER_INVALID]",
            status_code=400,
            message="chapter_ids must include every chapter exactly once.",
        )
    if error_code == LEARNING_CONTENT_SERVICE_FAILED:
        return _api_error(
            server_error_code,
            status_code=500,
            message=server_message,
        )
    return _api_error(error_code, status_code=400)


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


def _build_default_voice_clone_service() -> VoiceCloneService:
    endpoint_url = os.getenv("STEPFUN_VOICE_CLONE_ENDPOINT")
    transport = VoiceCloneHTTPTransport() if endpoint_url else None
    return VoiceCloneService(
        transport=transport,
        endpoint_url=endpoint_url,
        fallback_voice=os.getenv("STEPFUN_DEFAULT_VOICE", "default_voice"),
    )


@test_bank_router.get("/categories", response_model=None)
async def list_question_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = TestBankService(db)
    result = await service.list_categories()
    if not result.is_success:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_CATEGORY_LIST_FAILED]",
            server_message="QuestionCategory 列表读取失败。",
        )
    items = result.value or []
    return _success(
        QuestionCategoryListResponse(
            items=[serialize_category(item) for item in items],
            total=len(items),
        )
    )


@test_bank_router.post("/generation/preview", response_model=None)
async def preview_question_generation(
    payload: QuestionGenerationPreviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await _question_generation_service(request, db).preview_from_chapter(
        learning_content_id=payload.learning_content_id,
        chapter_id=payload.chapter_id,
    )
    if not result.is_success or result.value is None:
        return _question_generation_result_error(result.fallback)
    return _success(QuestionGenerationPreviewResponse(drafts=result.value))


@test_bank_router.post("/generation/confirm", response_model=None)
async def confirm_question_generation(
    payload: QuestionGenerationConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await _question_generation_service(request, db).save_drafts(
        payload.drafts,
        category_id=payload.category_id,
        actor_id=str(current_user.user_id),
    )
    if not result.is_success or result.value is None:
        return _question_generation_result_error(result.fallback)
    items = [serialize_question(item) for item in result.value]
    return _success(QuestionGenerationConfirmResponse(items=items, total=len(items)))


@test_bank_router.post("/imports", response_model=None)
async def create_test_bank_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    raw = await file.read()
    if len(raw) > IMPORT_MAX_BYTES:
        return _api_error(
            "[TEST_BANK_IMPORT_FILE_TOO_LARGE]",
            status_code=413,
            message="TestBank import file must be 10MB or smaller.",
        )
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return _api_error(
            "[TEST_BANK_IMPORT_ENCODING_INVALID]",
            status_code=400,
            message="TestBank import file must be UTF-8 encoded.",
        )

    service = TestBankService(db)
    job_result = await service.create_import_job(
        filename=file.filename or "questions.jsonl",
        actor_id=str(current_user.user_id),
    )
    if not job_result.is_success or job_result.value is None:
        return _test_bank_result_error(
            job_result.fallback,
            server_error_code="[TEST_BANK_IMPORT_CREATE_FAILED]",
            server_message="TestBank import job 创建失败。",
        )
    run_result = await service.run_import_job(
        job_result.value,
        raw=raw,
        actor_id=str(current_user.user_id),
    )
    if not run_result.is_success or run_result.value is None:
        return _test_bank_result_error(
            run_result.fallback,
            server_error_code="[TEST_BANK_IMPORT_RUN_FAILED]",
            server_message="TestBank import job 执行失败。",
        )
    return _success(serialize_import_job(run_result.value))


@test_bank_router.get("/imports/{task_id}", response_model=None)
async def get_test_bank_import(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await TestBankService(db).get_import_job(task_id)
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[TEST_BANK_IMPORT_FETCH_FAILED]",
            server_message="TestBank import job 读取失败。",
        )
    return _success(serialize_import_job(result.value))


@test_bank_router.post("/categories", response_model=None)
async def create_question_category(
    payload: QuestionCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await TestBankService(db).create_category(
        payload, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_CATEGORY_CREATE_FAILED]",
            server_message="QuestionCategory 创建失败。",
        )
    return _success(serialize_category(result.value))


@test_bank_router.put("/categories/{category_id}", response_model=None)
async def update_question_category(
    category_id: str,
    payload: QuestionCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = TestBankService(db)
    category_result = await service.get_category(category_id)
    if not category_result.is_success or category_result.value is None:
        return _test_bank_result_error(
            category_result.fallback,
            server_error_code="[QUESTION_CATEGORY_UPDATE_FAILED]",
            server_message="QuestionCategory 更新失败。",
        )
    result = await service.update_category(
        category_result.value, payload, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_CATEGORY_UPDATE_FAILED]",
            server_message="QuestionCategory 更新失败。",
        )
    return _success(serialize_category(result.value))


@test_bank_router.delete("/categories/{category_id}", response_model=None)
async def delete_question_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = TestBankService(db)
    category_result = await service.get_category(category_id)
    if not category_result.is_success or category_result.value is None:
        return _test_bank_result_error(
            category_result.fallback,
            server_error_code="[QUESTION_CATEGORY_DELETE_FAILED]",
            server_message="QuestionCategory 删除失败。",
        )
    result = await service.delete_category(category_result.value)
    if not result.is_success:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_CATEGORY_DELETE_FAILED]",
            server_message="QuestionCategory 删除失败。",
        )
    return _success({"deleted": True})


@test_bank_router.get("/questions", response_model=None)
async def list_questions(
    category_id: str | None = None,
    difficulty: str | None = Query(default=None, pattern="^(easy|medium|hard)$"),
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    tag: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await TestBankService(db).list_questions(
        category_id=category_id,
        difficulty=difficulty,
        status=status,
        tag=tag,
    )
    if not result.is_success:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_LIST_FAILED]",
            server_message="QuestionItem 列表读取失败。",
        )
    items = result.value or []
    return _success(
        QuestionItemListResponse(
            items=[serialize_question(item) for item in items],
            total=len(items),
        )
    )


@test_bank_router.post("/questions", response_model=None)
async def create_question(
    payload: QuestionItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await TestBankService(db).create_question(
        payload, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_CREATE_FAILED]",
            server_message="QuestionItem 创建失败。",
        )
    return _success(serialize_question(result.value))


@test_bank_router.get("/questions/{question_id}", response_model=None)
async def get_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await TestBankService(db).get_question(question_id)
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_FETCH_FAILED]",
            server_message="QuestionItem 读取失败。",
        )
    return _success(serialize_question(result.value))


@test_bank_router.put("/questions/{question_id}", response_model=None)
async def update_question(
    question_id: str,
    payload: QuestionItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = TestBankService(db)
    question_result = await service.get_question(question_id)
    if not question_result.is_success or question_result.value is None:
        return _test_bank_result_error(
            question_result.fallback,
            server_error_code="[QUESTION_ITEM_UPDATE_FAILED]",
            server_message="QuestionItem 更新失败。",
        )
    result = await service.update_question(
        question_result.value, payload, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_UPDATE_FAILED]",
            server_message="QuestionItem 更新失败。",
        )
    return _success(serialize_question(result.value))


@test_bank_router.post("/questions/{question_id}/publish", response_model=None)
async def publish_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = TestBankService(db)
    question_result = await service.get_question(question_id)
    if not question_result.is_success or question_result.value is None:
        return _test_bank_result_error(
            question_result.fallback,
            server_error_code="[QUESTION_ITEM_PUBLISH_FAILED]",
            server_message="QuestionItem 发布失败。",
        )
    result = await service.publish_question(
        question_result.value, actor_id=str(current_user.user_id)
    )
    if not result.is_success:
        if result.fallback == "[QUESTION_ITEM_PUBLISH_GATE_FAILED]":
            decision = result.value
            if not isinstance(decision, PublishGateDecision):
                decision = PublishGateDecision(can_publish=False, results=[])
            return JSONResponse(
                status_code=400,
                content=error_response(
                    "[QUESTION_ITEM_PUBLISH_GATE_FAILED]",
                    message="QuestionItem 发布门禁未通过。",
                )
                | {
                    "details": {
                        "gate_results": [
                            item.model_dump() for item in decision.results
                        ]
                    }
                },
            )
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_PUBLISH_FAILED]",
            server_message="QuestionItem 发布失败。",
        )
    if result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_PUBLISH_FAILED]",
            server_message="QuestionItem 发布失败。",
        )
    published_question = result.value
    if isinstance(published_question, PublishGateDecision):
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_PUBLISH_FAILED]",
            server_message="QuestionItem 发布失败。",
        )
    return _success(serialize_question(published_question))


@test_bank_router.post("/questions/{question_id}/archive", response_model=None)
async def archive_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = TestBankService(db)
    question_result = await service.get_question(question_id)
    if not question_result.is_success or question_result.value is None:
        return _test_bank_result_error(
            question_result.fallback,
            server_error_code="[QUESTION_ITEM_ARCHIVE_FAILED]",
            server_message="QuestionItem 归档失败。",
        )
    result = await service.archive_question(
        question_result.value, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _test_bank_result_error(
            result.fallback,
            server_error_code="[QUESTION_ITEM_ARCHIVE_FAILED]",
            server_message="QuestionItem 归档失败。",
        )
    return _success(serialize_question(result.value))


@learning_content_router.get("", response_model=None)
async def list_learning_contents(
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    items_result = await service.list_contents(status=status)
    if not items_result.is_success:
        return _learning_content_result_error(
            items_result.fallback,
            server_error_code="[LEARNING_CONTENT_LIST_FAILED]",
            server_message="LearningContent 列表读取失败。",
        )
    items = items_result.value or []
    serialized_items = []
    for item in items:
        serialized_result = await serialize_learning_content(service, item)
        if not serialized_result.is_success or serialized_result.value is None:
            return _learning_content_result_error(
                serialized_result.fallback,
                server_error_code="[LEARNING_CONTENT_LIST_FAILED]",
                server_message="LearningContent 列表读取失败。",
            )
        serialized_items.append(serialized_result.value)
    payload = LearningContentListResponse(
        items=serialized_items,
        total=len(items),
    )
    return _success(payload)


@learning_content_router.post("", response_model=None)
async def create_learning_content(
    payload: LearningContentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.create_content(
        payload, actor_id=str(current_user.user_id)
    )
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CONTENT_CREATE_FAILED]",
            server_message="LearningContent 创建失败。",
        )
    serialized_result = await serialize_learning_content(service, content_result.value)
    if not serialized_result.is_success or serialized_result.value is None:
        return _learning_content_result_error(
            serialized_result.fallback,
            server_error_code="[LEARNING_CONTENT_CREATE_FAILED]",
            server_message="LearningContent 创建失败。",
        )
    return _success(serialized_result.value)


@learning_content_router.get("/{content_id}", response_model=None)
async def get_learning_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CONTENT_FETCH_FAILED]",
            server_message="LearningContent 读取失败。",
        )
    serialized_result = await serialize_learning_content(service, content_result.value)
    if not serialized_result.is_success or serialized_result.value is None:
        return _learning_content_result_error(
            serialized_result.fallback,
            server_error_code="[LEARNING_CONTENT_FETCH_FAILED]",
            server_message="LearningContent 读取失败。",
        )
    return _success(serialized_result.value)


@learning_content_router.put("/{content_id}", response_model=None)
async def update_learning_content(
    content_id: str,
    payload: LearningContentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CONTENT_UPDATE_FAILED]",
            server_message="LearningContent 更新失败。",
        )
    updated_result = await service.update_content(
        content_result.value, payload, actor_id=str(current_user.user_id)
    )
    if not updated_result.is_success or updated_result.value is None:
        return _learning_content_result_error(
            updated_result.fallback,
            server_error_code="[LEARNING_CONTENT_UPDATE_FAILED]",
            server_message="LearningContent 更新失败。",
        )
    serialized_result = await serialize_learning_content(service, updated_result.value)
    if not serialized_result.is_success or serialized_result.value is None:
        return _learning_content_result_error(
            serialized_result.fallback,
            server_error_code="[LEARNING_CONTENT_UPDATE_FAILED]",
            server_message="LearningContent 更新失败。",
        )
    return _success(serialized_result.value)


@learning_content_router.delete("/{content_id}", response_model=None)
async def delete_learning_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CONTENT_DELETE_FAILED]",
            server_message="LearningContent 删除失败。",
        )
    delete_result = await service.delete_content(content_result.value)
    if not delete_result.is_success:
        return _learning_content_result_error(
            delete_result.fallback,
            server_error_code="[LEARNING_CONTENT_DELETE_FAILED]",
            server_message="LearningContent 删除失败。",
        )
    return _success({"deleted": True})


@learning_content_router.post("/{content_id}/chapters", response_model=None)
async def add_learning_chapter(
    content_id: str,
    payload: LearningChapterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CHAPTER_CREATE_FAILED]",
            server_message="LearningChapter 创建失败。",
        )
    chapter_result = await service.add_chapter(
        content_result.value, payload, actor_id=str(current_user.user_id)
    )
    if not chapter_result.is_success or chapter_result.value is None:
        return _learning_content_result_error(
            chapter_result.fallback,
            server_error_code="[LEARNING_CHAPTER_CREATE_FAILED]",
            server_message="LearningChapter 创建失败。",
        )
    return _success(serialize_chapter(chapter_result.value))


@learning_content_router.put("/{content_id}/chapters/reorder", response_model=None)
async def reorder_learning_chapters(
    content_id: str,
    payload: LearningChapterReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CHAPTER_REORDER_FAILED]",
            server_message="LearningChapter 排序失败。",
        )
    chapters_result = await service.reorder_chapters(
        content_result.value, payload.chapter_ids, actor_id=str(current_user.user_id)
    )
    if not chapters_result.is_success or chapters_result.value is None:
        return _learning_content_result_error(
            chapters_result.fallback,
            server_error_code="[LEARNING_CHAPTER_REORDER_FAILED]",
            server_message="LearningChapter 排序失败。",
        )
    return _success([serialize_chapter(chapter) for chapter in chapters_result.value])


@learning_content_router.put("/{content_id}/chapters/{chapter_id}", response_model=None)
async def update_learning_chapter(
    content_id: str,
    chapter_id: str,
    payload: LearningChapterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CHAPTER_UPDATE_FAILED]",
            server_message="LearningChapter 更新失败。",
        )
    chapter_result = await service.get_chapter(content_id, chapter_id)
    if not chapter_result.is_success or chapter_result.value is None:
        return _learning_content_result_error(
            chapter_result.fallback,
            server_error_code="[LEARNING_CHAPTER_UPDATE_FAILED]",
            server_message="LearningChapter 更新失败。",
        )
    updated_result = await service.update_chapter(
        content_result.value,
        chapter_result.value,
        payload,
        actor_id=str(current_user.user_id),
    )
    if not updated_result.is_success or updated_result.value is None:
        return _learning_content_result_error(
            updated_result.fallback,
            server_error_code="[LEARNING_CHAPTER_UPDATE_FAILED]",
            server_message="LearningChapter 更新失败。",
        )
    return _success(serialize_chapter(updated_result.value))


@learning_content_router.delete("/{content_id}/chapters/{chapter_id}", response_model=None)
async def delete_learning_chapter(
    content_id: str,
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CHAPTER_DELETE_FAILED]",
            server_message="LearningChapter 删除失败。",
        )
    chapter_result = await service.get_chapter(content_id, chapter_id)
    if not chapter_result.is_success or chapter_result.value is None:
        return _learning_content_result_error(
            chapter_result.fallback,
            server_error_code="[LEARNING_CHAPTER_DELETE_FAILED]",
            server_message="LearningChapter 删除失败。",
        )
    delete_result = await service.delete_chapter(
        content_result.value,
        chapter_result.value,
        actor_id=str(current_user.user_id),
    )
    if not delete_result.is_success:
        return _learning_content_result_error(
            delete_result.fallback,
            server_error_code="[LEARNING_CHAPTER_DELETE_FAILED]",
            server_message="LearningChapter 删除失败。",
        )
    return _success({"deleted": True})


@learning_content_router.post("/{content_id}/publish", response_model=None)
async def publish_learning_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CONTENT_PUBLISH_FAILED]",
            server_message="LearningContent 发布失败。",
        )
    publish_result = await service.publish_content(
        content_result.value, actor_id=str(current_user.user_id)
    )
    if not publish_result.is_success:
        if publish_result.fallback == "[LEARNING_CONTENT_PUBLISH_GATE_FAILED]":
            decision = publish_result.value
            if not isinstance(decision, PublishGateDecision):
                decision = PublishGateDecision(can_publish=False, results=[])
            return JSONResponse(
                status_code=400,
                content=error_response(
                    "[LEARNING_CONTENT_PUBLISH_GATE_FAILED]",
                    message="LearningContent 发布门禁未通过。",
                )
                | {
                    "details": {
                        "gate_results": [
                            item.model_dump() for item in decision.results
                        ]
                    }
                },
            )
        return _learning_content_result_error(
            publish_result.fallback,
            server_error_code="[LEARNING_CONTENT_PUBLISH_FAILED]",
            server_message="LearningContent 发布失败。",
        )
    if publish_result.value is None:
        return _learning_content_result_error(
            publish_result.fallback,
            server_error_code="[LEARNING_CONTENT_PUBLISH_FAILED]",
            server_message="LearningContent 发布失败。",
        )
    published_content = publish_result.value
    if isinstance(published_content, PublishGateDecision):
        return _learning_content_result_error(
            publish_result.fallback,
            server_error_code="[LEARNING_CONTENT_PUBLISH_FAILED]",
            server_message="LearningContent 发布失败。",
        )
    serialized_result = await serialize_learning_content(service, published_content)
    if not serialized_result.is_success or serialized_result.value is None:
        return _learning_content_result_error(
            serialized_result.fallback,
            server_error_code="[LEARNING_CONTENT_PUBLISH_FAILED]",
            server_message="LearningContent 发布失败。",
        )
    return _success(serialized_result.value)


@learning_content_router.post("/{content_id}/archive", response_model=None)
async def archive_learning_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = LearningContentService(db)
    content_result = await service.get_content(content_id)
    if not content_result.is_success or content_result.value is None:
        return _learning_content_result_error(
            content_result.fallback,
            server_error_code="[LEARNING_CONTENT_ARCHIVE_FAILED]",
            server_message="LearningContent 归档失败。",
        )
    archive_result = await service.archive_content(
        content_result.value, actor_id=str(current_user.user_id)
    )
    if not archive_result.is_success or archive_result.value is None:
        return _learning_content_result_error(
            archive_result.fallback,
            server_error_code="[LEARNING_CONTENT_ARCHIVE_FAILED]",
            server_message="LearningContent 归档失败。",
        )
    serialized_result = await serialize_learning_content(service, archive_result.value)
    if not serialized_result.is_success or serialized_result.value is None:
        return _learning_content_result_error(
            serialized_result.fallback,
            server_error_code="[LEARNING_CONTENT_ARCHIVE_FAILED]",
            server_message="LearningContent 归档失败。",
        )
    return _success(serialized_result.value)


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


@router.get("/examiner-agents", response_model=None)
async def list_examiner_agents(
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await ExaminerAgentService(db).list_agents(status=status)
    if not result.is_success:
        return _examiner_agent_result_error(result.fallback)
    items = result.value or []
    return _success(
        ExaminerAgentListResponse(
            items=[_serialize_examiner_agent(item) for item in items],
            total=len(items),
        )
    )


@router.post("/examiner-agents", response_model=None)
async def create_examiner_agent(
    payload: ExaminerAgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await ExaminerAgentService(db).create_agent(
        payload, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _examiner_agent_result_error(result.fallback)
    return _success(_serialize_examiner_agent(result.value))


@router.get("/examiner-agents/{examiner_agent_id}", response_model=None)
async def get_examiner_agent(
    examiner_agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await ExaminerAgentService(db).get_agent(examiner_agent_id)
    if not result.is_success or result.value is None:
        return _examiner_agent_result_error(result.fallback)
    return _success(_serialize_examiner_agent(result.value))


@router.put("/examiner-agents/{examiner_agent_id}", response_model=None)
async def update_examiner_agent(
    examiner_agent_id: str,
    payload: ExaminerAgentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    result = await service.update_agent(
        agent_result.value, payload, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _examiner_agent_result_error(result.fallback)
    return _success(_serialize_examiner_agent(result.value))


@router.post("/examiner-agents/{examiner_agent_id}/publish", response_model=None)
async def publish_examiner_agent(
    examiner_agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    result = await service.publish_agent(
        agent_result.value, actor_id=str(current_user.user_id)
    )
    if not result.is_success:
        if result.fallback == "[EXAMINER_AGENT_PUBLISH_GATE_FAILED]":
            return _examiner_agent_publish_gate_error(result.value)
        return _examiner_agent_result_error(result.fallback)
    if result.value is None or not isinstance(result.value, ExaminerAgent):
        return _examiner_agent_result_error(result.fallback)
    return _success(_serialize_examiner_agent(result.value))


@router.post("/examiner-agents/{examiner_agent_id}/archive", response_model=None)
async def archive_examiner_agent(
    examiner_agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    result = await service.archive_agent(
        agent_result.value, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _examiner_agent_result_error(result.fallback)
    return _success(_serialize_examiner_agent(result.value))


@router.get("/examiner-agents/{examiner_agent_id}/template-references", response_model=None)
async def get_examiner_agent_template_references(
    examiner_agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    references_result = await service.list_template_references(
        examiner_agent_id=examiner_agent_id
    )
    if not references_result.is_success or references_result.value is None:
        return _examiner_agent_result_error(references_result.fallback)
    payload = TemplateReferenceListResponse(
        items=references_result.value,
        total=len(references_result.value),
    )
    return _success(payload.model_dump())


@router.post("/examiner-agents/{examiner_agent_id}/duplicate", response_model=None)
async def duplicate_examiner_agent(
    examiner_agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    result = await service.duplicate_agent(
        agent_result.value, actor_id=str(current_user.user_id)
    )
    if not result.is_success or result.value is None:
        return _examiner_agent_result_error(result.fallback)
    return _success(_serialize_examiner_agent(result.value))


@router.post("/examiner-agents/{examiner_agent_id}/unpublish", response_model=None)
async def unpublish_examiner_agent(
    examiner_agent_id: str,
    payload: UnpublishAcknowledgeRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    result = await service.unpublish_agent(
        agent_result.value,
        actor_id=str(current_user.user_id),
        acknowledge=bool(payload and payload.acknowledge),
    )
    if result.is_success and isinstance(result.value, ExaminerAgent):
        return _success(_serialize_examiner_agent(result.value))
    if result.fallback == "[EXAMINER_AGENT_REFERENCED_BY_PUBLISHED_TEMPLATES]":
        references = result.value if isinstance(result.value, list) else []
        return JSONResponse(
            status_code=409,
            content=error_response(
                "[EXAMINER_AGENT_REFERENCED_BY_PUBLISHED_TEMPLATES]",
                message="ExaminerAgent is referenced by published templates.",
            )
            | {"details": {"referencing_templates": references}},
        )
    return _examiner_agent_result_error(result.fallback)


@router.post("/examiner-agents/{examiner_agent_id}/simulate", response_model=None)
async def simulate_examiner_agent(
    examiner_agent_id: str,
    payload: ExaminerAgentSimulationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ExaminerAgentService(db)
    agent_result = await service.get_agent(examiner_agent_id)
    if not agent_result.is_success or agent_result.value is None:
        return _examiner_agent_result_error(agent_result.fallback)
    result = await service.simulate_agent(agent_result.value, payload)
    if not result.is_success or result.value is None:
        return _examiner_agent_result_error(result.fallback)
    return _success(result.value)


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


@router.put("/learner-profiles/{user_id}/override", response_model=None)
async def override_learner_profile(
    user_id: str,
    payload: LearnerAdminOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    result = await LearnerProfileService(db).apply_admin_override(
        user_id,
        payload.level,
        actor_id=str(current_user.user_id),
    )
    if not result.is_success or result.value is None:
        return _learner_profile_service_error(result.fallback)
    return _success(LearnerProfileResponse.model_validate(result.value))


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


@router.get("/templates/{template_id}/runtime-dossier-preview", response_model=None)
async def get_practice_template_runtime_dossier_preview(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    try:
        preview = await RoleplayRuntimeDossierPreviewService(db).build_preview(
            template_id
        )
        reference_reader = CurriculumAssetReferenceReader(db).read_reference
        situation_packs = await SituationPackRepository.from_database(db)
        try:
            roleplay_contract = await build_roleplay_contract_compiler(
                reference_reader,
                situation_packs=situation_packs,
            ).compile_from_template(
                template_id,
                actor_id=str(current_user.user_id),
            )
            roleplay_gate_results: list[dict[str, Any]] = []
        except RoleplayContractCompileError as exc:
            roleplay_contract = None
            roleplay_gate_results = [
                item.model_dump() for item in exc.gate_results
            ]
    except SQLAlchemyError as exc:
        return build_server_error(
            "[PRACTICE_TEMPLATE_RUNTIME_DOSSIER_PREVIEW_FAILED]",
            message="PracticeTemplate runtime dossier 预览生成失败。",
            exc=exc,
        )
    if preview is None:
        return _not_found()
    preview_payload = preview.model_dump()
    preview_payload["roleplay_contract"] = roleplay_contract
    preview_payload["roleplay_gate_results"] = roleplay_gate_results
    return _success(preview_payload)


@router.get("/roleplay-situation-packs", response_model=None)
async def list_roleplay_situation_packs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    try:
        return _success(await RoleplaySituationPackAdminService(db).list_packs())
    except SQLAlchemyError as exc:
        return build_server_error(
            "[ROLEPLAY_SITUATION_PACKS_FETCH_FAILED]",
            message="Roleplay Situation Pack 暂时无法读取。",
            exc=exc,
        )


@router.get("/roleplay-situation-packs/{code}", response_model=None)
async def get_roleplay_situation_pack(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    try:
        pack = await RoleplaySituationPackAdminService(db).get_pack(code)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[ROLEPLAY_SITUATION_PACK_FETCH_FAILED]",
            message="Roleplay Situation Pack 暂时无法读取。",
            exc=exc,
        )
    if pack is None:
        return _api_error(
            "[ROLEPLAY_SITUATION_PACK_NOT_FOUND]",
            status_code=404,
            message="Roleplay Situation Pack 不存在。",
        )
    return _success(pack)


@router.get("/roleplay-situation-packs/{code}/resolve", response_model=None)
async def resolve_roleplay_situation_pack(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = RoleplaySituationPackAdminService(db)
    try:
        resolved = await service.resolve_published(code)
        if resolved is not None:
            return _success(resolved)
        publish_state = await service.pack_publish_state(code)
        if publish_state is None:
            return _api_error(
                "[ROLEPLAY_SITUATION_PACK_NOT_FOUND]",
                status_code=404,
                message="Roleplay Situation Pack 不存在。",
            )
        return _api_error(
            "[ROLEPLAY_SITUATION_PACK_NOT_PUBLISHED]",
            status_code=404,
            message="Roleplay Situation Pack 尚未发布。",
        )
    except SQLAlchemyError as exc:
        return build_server_error(
            "[ROLEPLAY_SITUATION_PACK_RESOLVE_FAILED]",
            message="Roleplay Situation Pack 解析暂时无法完成。",
            exc=exc,
        )


@router.get("/roleplay-situation-packs/{code}/references", response_model=None)
async def get_roleplay_situation_pack_references(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = RoleplaySituationPackAdminService(db)
    try:
        pack = await service.get_pack(code)
        if pack is None:
            return _api_error(
                "[ROLEPLAY_SITUATION_PACK_NOT_FOUND]",
                status_code=404,
                message="Roleplay Situation Pack 不存在。",
            )
        return _success(await service.references_for(code))
    except SQLAlchemyError as exc:
        return build_server_error(
            "[ROLEPLAY_SITUATION_PACK_REFERENCES_FETCH_FAILED]",
            message="Roleplay Situation Pack 引用关系暂时无法读取。",
            exc=exc,
        )


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
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    query: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    items = await service.list_case_items(status=status, query=query)
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


@router.get("/case-items/{case_item_id}/template-references", response_model=None)
async def get_case_item_template_references(
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
    references = await service.list_template_references(
        asset_type="case_item",
        asset_id=case_item_id,
    )
    payload = TemplateReferenceListResponse(
        items=references,
        total=len(references),
    )
    return _success(payload.model_dump())


@router.post("/case-items/{case_item_id}/duplicate", response_model=None)
async def duplicate_case_item(
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
        duplicate = await service.duplicate_case_item(
            item, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_case_item(duplicate))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[CASE_ITEM_DUPLICATE_FAILED]",
            message="CaseItem 复制失败。",
            exc=exc,
        )


@router.post("/case-items/{case_item_id}/unpublish", response_model=None)
async def unpublish_case_item(
    case_item_id: str,
    payload: UnpublishAcknowledgeRequest | None = None,
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
        unpublished = await service.unpublish_case_item(
            item,
            actor_id=str(current_user.user_id),
            acknowledge=bool(payload and payload.acknowledge),
        )
        return _success(_serialize_case_item(unpublished))
    except ContentAssetAlreadyDraftError:
        await db.rollback()
        return _api_error(
            "[CASE_ITEM_ALREADY_DRAFT]",
            status_code=409,
            message="Only published CaseItem records can be unpublished.",
        )
    except ContentAssetNotEditableError:
        await db.rollback()
        return _api_error(
            "[CASE_ITEM_NOT_EDITABLE]",
            status_code=409,
            message="Archived CaseItem records cannot be unpublished.",
        )
    except ContentAssetReferencedByTemplatesError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=409,
            content=error_response(
                "[CASE_ITEM_REFERENCED_BY_PUBLISHED_TEMPLATES]",
                message="CaseItem is referenced by published templates.",
            )
            | {"details": {"referencing_templates": exc.referencing_templates}},
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[CASE_ITEM_UNPUBLISH_FAILED]",
            message="CaseItem 退回草稿失败。",
            exc=exc,
        )


@router.get("/role-profiles", response_model=None)
async def list_role_profiles(
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    query: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = ContentAssetService(db)
    items = await service.list_role_profiles(status=status, query=query)
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
    except ContentAssetPublishError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[ROLE_PROFILE_CREATE_FAILED]",
                message=str(exc),
            )
            | {"details": {"reason_code": exc.reason_code}},
        )
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
    except ContentAssetPublishError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[ROLE_PROFILE_UPDATE_FAILED]",
                message=str(exc),
            )
            | {"details": {"reason_code": exc.reason_code}},
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
        voice_service = _build_default_voice_clone_service()
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


@router.get("/role-profiles/{role_profile_id}/template-references", response_model=None)
async def get_role_profile_template_references(
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
    references = await service.list_template_references(
        asset_type="role_profile",
        asset_id=role_profile_id,
    )
    payload = TemplateReferenceListResponse(
        items=references,
        total=len(references),
    )
    return _success(payload.model_dump())


@router.post("/role-profiles/{role_profile_id}/duplicate", response_model=None)
async def duplicate_role_profile(
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
        duplicate = await service.duplicate_role_profile(
            item, actor_id=str(current_user.user_id)
        )
        return _success(_serialize_role_profile(duplicate))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_DUPLICATE_FAILED]",
            message="RoleProfile 复制失败。",
            exc=exc,
        )


@router.post("/role-profiles/{role_profile_id}/unpublish", response_model=None)
async def unpublish_role_profile(
    role_profile_id: str,
    payload: UnpublishAcknowledgeRequest | None = None,
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
        unpublished = await service.unpublish_role_profile(
            item,
            actor_id=str(current_user.user_id),
            acknowledge=bool(payload and payload.acknowledge),
        )
        return _success(_serialize_role_profile(unpublished))
    except ContentAssetAlreadyDraftError:
        await db.rollback()
        return _api_error(
            "[ROLE_PROFILE_ALREADY_DRAFT]",
            status_code=409,
            message="Only published RoleProfile records can be unpublished.",
        )
    except ContentAssetNotEditableError:
        await db.rollback()
        return _api_error(
            "[ROLE_PROFILE_NOT_EDITABLE]",
            status_code=409,
            message="Archived RoleProfile records cannot be unpublished.",
        )
    except ContentAssetReferencedByTemplatesError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=409,
            content=error_response(
                "[ROLE_PROFILE_REFERENCED_BY_PUBLISHED_TEMPLATES]",
                message="RoleProfile is referenced by published templates.",
            )
            | {"details": {"referencing_templates": exc.referencing_templates}},
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[ROLE_PROFILE_UNPUBLISH_FAILED]",
            message="RoleProfile 退回草稿失败。",
            exc=exc,
        )

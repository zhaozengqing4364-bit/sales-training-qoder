"""Explicit durable-task contracts and handlers owned by learning."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform import AIInvocationPort
from learning.errors import LearningGovernanceError
from learning.ports import ActivityOutcomeWriterPort
from learning.question_generation import (
    QuestionGenerationProcessor,
    QuestionGenerationProcessResult,
)
from learning.quiz_runtime import QuizAttemptSummary, ShortAnswerScoringProcessor
from learning.source_ingestion import (
    SOURCE_DOCUMENT_PARSE_TASK_TYPE,
    SourceDocumentIngestionProcessor,
    SourceFileType,
    SourceIngestionError,
    parse_source_document,
)
from task_runtime import TaskDefinition, TaskRegistry
from task_runtime.contracts import (
    TaskCompletion,
    TaskPolicy,
    TaskResultItemRef,
    TaskResultKind,
)
from task_runtime.errors import TaskExecutionError, TaskFailureKind

QUESTION_GENERATION_TASK_TYPE = "learning.question_generation.generate"
SHORT_ANSWER_SCORING_TASK_TYPE = "learning.quiz.short_answer_score"

AIInvocationFactory = Callable[[], AIInvocationPort]
ActivityOutcomeWriterFactory = Callable[[AsyncSession], ActivityOutcomeWriterPort]


class QuestionGenerationTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str = Field(min_length=1, max_length=160)


class QuestionGenerationTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    invocation_id: str
    created_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


class ShortAnswerScoringTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str = Field(min_length=1, max_length=160)


class ShortAnswerScoringTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str
    status: str
    score: float | None
    max_score: float
    passed: bool | None


class SourceDocumentParseTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str = Field(min_length=1, max_length=160)
    file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    file_type: SourceFileType


class SourceDocumentParseTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    document_id: str
    parse_status: str
    processing_state: str
    chunk_count: int = Field(ge=0)
    artifact_available: bool
    anchor_count: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=1)
    duration_ms: int | None = Field(default=None, ge=1)
    missing_pages: tuple[int, ...] = ()


class QuestionGenerationTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ai_factory: AIInvocationFactory,
    ) -> None:
        self._session_factory = session_factory
        self._ai_factory = ai_factory

    async def execute(
        self,
        context: Any,
        payload: BaseModel,
    ) -> TaskCompletion:
        if not isinstance(payload, QuestionGenerationTaskInput):
            raise TypeError("question generation task payload type mismatch")
        await context.checkpoint()
        ai = self._ai_factory()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                prepared = await QuestionGenerationProcessor(
                    session, ai=ai
                ).prepare_batch(
                    batch_id=payload.batch_id,
                    task_id=str(context.claim.task_id),
                )
                await session.commit()
            except LearningGovernanceError as exc:
                await session.rollback()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise
        if isinstance(prepared, QuestionGenerationProcessResult):
            result = prepared
        else:
            invocation = await ai.invoke(prepared.request)
            await context.checkpoint()
            async with self._session_factory() as session:
                await context.fenced(session).assert_current()
                try:
                    result = await QuestionGenerationProcessor(
                        session, ai=ai
                    ).apply_result(plan=prepared, result=invocation)
                    await session.commit()
                except LearningGovernanceError as exc:
                    await session.commit()
                    raise _task_error(exc) from exc
                except Exception:
                    await session.rollback()
                    raise
        if isinstance(prepared, QuestionGenerationProcessResult):
            await context.checkpoint()
        structured = QuestionGenerationTaskResult(
            batch_id=result.batch_id,
            invocation_id=result.invocation_id,
            created_count=result.created_count,
            passed_count=result.passed_count,
            failed_count=result.failed_count,
        )
        return TaskCompletion(
            structured_payload=structured.model_dump(mode="json"),
            result_kind=TaskResultKind.COMPLETE,
            resource_type="question_generation_batch",
            resource_id=result.batch_id,
            location=(
                "/api/v1/admin/newcomer-training/question-candidates"
                f"?batch_id={result.batch_id}"
            ),
            saved_items=[
                TaskResultItemRef(
                    resource_type="question_candidate",
                    resource_id=candidate_id,
                )
                for candidate_id in result.candidate_ids
            ],
        )


class ShortAnswerScoringTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ai_factory: AIInvocationFactory,
        outcome_writer_factory: ActivityOutcomeWriterFactory,
    ) -> None:
        self._session_factory = session_factory
        self._ai_factory = ai_factory
        self._outcome_writer_factory = outcome_writer_factory

    async def execute(
        self,
        context: Any,
        payload: BaseModel,
    ) -> TaskCompletion:
        if not isinstance(payload, ShortAnswerScoringTaskInput):
            raise TypeError("short answer task payload type mismatch")
        await context.checkpoint()
        ai = self._ai_factory()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                prepared = await ShortAnswerScoringProcessor(
                    session,
                    ai=ai,
                    outcomes=self._outcome_writer_factory(session),
                ).prepare_attempt(
                    detail_id=payload.detail_id,
                    task_id=str(context.claim.task_id),
                )
                await session.commit()
            except LearningGovernanceError as exc:
                await session.rollback()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise
        if isinstance(prepared, QuizAttemptSummary):
            result = prepared
            await context.checkpoint()
        else:
            invocation = await ai.invoke(prepared.request)
            await context.checkpoint()
            async with self._session_factory() as session:
                await context.fenced(session).assert_current()
                try:
                    result = await ShortAnswerScoringProcessor(
                        session,
                        ai=ai,
                        outcomes=self._outcome_writer_factory(session),
                    ).apply_result(plan=prepared, result=invocation)
                    await session.commit()
                except LearningGovernanceError as exc:
                    await session.commit()
                    raise _task_error(exc) from exc
                except Exception:
                    await session.rollback()
                    raise
        structured = ShortAnswerScoringTaskResult(
            detail_id=result.detail_id,
            status=result.status,
            score=result.score,
            max_score=result.max_score,
            passed=result.passed,
        )
        return TaskCompletion(
            structured_payload=structured.model_dump(mode="json"),
            result_kind=TaskResultKind.COMPLETE,
            resource_type="quiz_attempt",
            resource_id=result.detail_id,
            location=f"/api/v1/newcomer-training/activities/{result.activity_id}",
        )


class SourceDocumentParseTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def execute(
        self,
        context: Any,
        payload: BaseModel,
    ) -> TaskCompletion:
        if not isinstance(payload, SourceDocumentParseTaskInput):
            raise TypeError("source document parse task payload type mismatch")
        await context.report_progress(
            current=0,
            total=2,
            stage="validating",
            label="正在校验材料文件",
        )
        try:
            async with self._session_factory() as session:
                await context.fenced(session).assert_current()
                plan = await SourceDocumentIngestionProcessor(session).prepare(
                    organization_id=context.claim.organization_id,
                    revision_id=payload.revision_id,
                    file_hash=payload.file_hash,
                    file_type=payload.file_type,
                )
                if plan.already_ready:
                    await session.rollback()
                else:
                    plan = await SourceDocumentIngestionProcessor(session).mark_processing(
                        plan=plan
                    )
                    await session.commit()
            if plan.already_ready:
                result = SourceDocumentIngestionProcessor(session).ready_outcome(plan)
            else:
                await context.report_progress(
                    current=1,
                    total=2,
                    stage="parsing",
                    label="正在解析材料内容",
                )
                parser_result = await parse_source_document(plan)
                await context.checkpoint()
                async with self._session_factory() as session:
                    await context.fenced(session).assert_current()
                    result = await SourceDocumentIngestionProcessor(session).apply(
                        plan=plan,
                        parser_result=parser_result,
                    )
                    await session.commit()
        except SourceIngestionError as exc:
            raise _source_task_error(exc.code, exc.message) from exc

        if result.processing_state == "failed":
            code = result.error_code or "source_document_parse_failed"
            raise _source_task_error(
                code,
                _source_parse_failure_message(code),
            )
        await context.report_progress(
            current=2,
            total=2,
            stage="completed",
            label=(
                "材料已部分处理，可重试缺失页面"
                if result.processing_state == "partial"
                else "材料解析完成"
            ),
        )
        structured = SourceDocumentParseTaskResult(
            revision_id=result.revision_id,
            document_id=result.document_id,
            parse_status=result.parse_status,
            processing_state=result.processing_state,
            chunk_count=result.chunk_count,
            artifact_available=result.artifact_available,
            anchor_count=result.anchor_count,
            page_count=result.page_count,
            duration_ms=result.duration_ms,
            missing_pages=result.missing_pages,
        )
        return TaskCompletion(
            structured_payload=structured.model_dump(mode="json"),
            result_kind=(
                TaskResultKind.PARTIAL_SUCCESS
                if result.processing_state == "partial"
                else TaskResultKind.COMPLETE
            ),
            resource_type="source_document_revision",
            resource_id=result.revision_id,
            location="/admin/newcomer-training/content",
            saved_items=[
                TaskResultItemRef(
                    resource_type="source_document",
                    resource_id=result.document_id,
                )
            ],
            remaining_items=[
                TaskResultItemRef(
                    resource_type="source_preview_page",
                    resource_id=f"{result.revision_id}:page-{page}",
                )
                for page in result.missing_pages[:100]
            ],
            retryable_items=[
                TaskResultItemRef(
                    resource_type="source_preview_page",
                    resource_id=f"{result.revision_id}:page-{page}",
                )
                for page in result.missing_pages[:100]
            ],
        )


def register_learning_task_definitions(
    registry: TaskRegistry,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    ai_factory: AIInvocationFactory | None = None,
    outcome_writer_factory: ActivityOutcomeWriterFactory | None = None,
) -> None:
    dependencies = (session_factory, ai_factory, outcome_writer_factory)
    if any(item is not None for item in dependencies) and not all(
        item is not None for item in dependencies
    ):
        raise ValueError(
            "Worker 注册必须同时提供 session、AI 和 ActivityOutcome 依赖。"
        )
    question_handler = None
    short_answer_handler = None
    source_document_handler = None
    if session_factory is not None and ai_factory is not None:
        assert outcome_writer_factory is not None
        question_handler = QuestionGenerationTaskHandler(
            session_factory,
            ai_factory=ai_factory,
        )
        short_answer_handler = ShortAnswerScoringTaskHandler(
            session_factory,
            ai_factory=ai_factory,
            outcome_writer_factory=outcome_writer_factory,
        )
        source_document_handler = SourceDocumentParseTaskHandler(session_factory)
    registry.register(
        TaskDefinition(
            task_type=SOURCE_DOCUMENT_PARSE_TASK_TYPE,
            schema_version=1,
            input_model=SourceDocumentParseTaskInput,
            result_model=SourceDocumentParseTaskResult,
            policy=TaskPolicy(
                timeout_seconds=300,
                max_attempts=2,
                initial_backoff_seconds=15,
                max_backoff_seconds=120,
                lease_seconds=60,
                retryable_error_codes=frozenset(
                    {
                        "source_document_artifact_store_failed",
                        "source_preview_store_failed",
                        "source_media_probe_failed",
                        "source_media_probe_unavailable",
                    }
                ),
                terminal_error_codes=frozenset(
                    {
                        "source_document_artifact_missing",
                        "source_document_content_empty",
                        "source_document_parse_failed",
                        "source_media_decode_failed",
                        "source_media_codec_unsupported",
                        "source_media_duration_invalid",
                        "source_slide_decode_failed",
                        "source_slide_render_failed",
                    }
                ),
            ),
            handler=source_document_handler,
            metric_tags=(("domain", "learning"), ("workload", "document_parse")),
            allowed_data_classifications=frozenset({"internal"}),
            max_payload_bytes=1_024,
        )
    )
    registry.register(
        TaskDefinition(
            task_type=QUESTION_GENERATION_TASK_TYPE,
            schema_version=1,
            input_model=QuestionGenerationTaskInput,
            result_model=QuestionGenerationTaskResult,
            policy=TaskPolicy(
                timeout_seconds=300,
                max_attempts=3,
                initial_backoff_seconds=15,
                max_backoff_seconds=300,
                lease_seconds=60,
                retryable_error_codes=frozenset(
                    {"question_generation_ai_failed"}
                ),
            ),
            handler=question_handler,
            metric_tags=(("domain", "learning"), ("workload", "generation")),
            allowed_data_classifications=frozenset({"internal"}),
            max_payload_bytes=1_024,
        )
    )
    registry.register(
        TaskDefinition(
            task_type=SHORT_ANSWER_SCORING_TASK_TYPE,
            schema_version=1,
            input_model=ShortAnswerScoringTaskInput,
            result_model=ShortAnswerScoringTaskResult,
            policy=TaskPolicy(
                timeout_seconds=180,
                max_attempts=3,
                initial_backoff_seconds=15,
                max_backoff_seconds=300,
                lease_seconds=60,
                retryable_error_codes=frozenset(
                    {"quiz_short_answer_scoring_failed"}
                ),
            ),
            handler=short_answer_handler,
            metric_tags=(("domain", "learning"), ("workload", "scoring")),
            allowed_data_classifications=frozenset({"internal"}),
            max_payload_bytes=1_024,
        )
    )


def _task_error(exc: LearningGovernanceError) -> TaskExecutionError:
    retryable = bool(exc.details and exc.details.get("retryable") is True)
    if retryable or exc.status_code == 503:
        kind = TaskFailureKind.PROVIDER_TEMPORARY
    elif exc.status_code == 403:
        kind = TaskFailureKind.PERMISSION_DENIED
    elif exc.status_code in {404, 422}:
        kind = TaskFailureKind.INVALID_INPUT
    else:
        kind = TaskFailureKind.BUSINESS_CONFLICT
    code = exc.code.strip("[]").lower()
    return TaskExecutionError(code=code, message=exc.message, kind=kind)


def _source_task_error(code: str, message: str) -> TaskExecutionError:
    kind = (
        TaskFailureKind.PROVIDER_TEMPORARY
        if code
        in {
            "source_document_artifact_store_failed",
            "source_preview_store_failed",
            "source_media_probe_failed",
            "source_media_probe_unavailable",
        }
        else TaskFailureKind.INVALID_INPUT
    )
    return TaskExecutionError(code=code, message=message, kind=kind)


def _source_parse_failure_message(code: str) -> str:
    if code == "source_document_artifact_store_failed":
        return "材料解析结果暂时无法保存，系统将按策略重试。"
    if code in {"source_preview_store_failed", "source_media_probe_failed"}:
        return "材料预览暂时无法生成，原文件已保留，系统将按策略重试。"
    if code == "source_media_probe_unavailable":
        return "媒体解码服务暂不可用，原文件已保留，可稍后重试。"
    if code == "source_media_codec_unsupported":
        return "媒体编码不受支持，请转换格式后重新上传。"
    if code == "source_document_content_empty":
        return "材料中没有可用于训练的正文，请检查文件后重新上传。"
    return "材料解析失败，请检查文件格式后重新上传。"


__all__ = [
    "ActivityOutcomeWriterFactory",
    "AIInvocationFactory",
    "QUESTION_GENERATION_TASK_TYPE",
    "QuestionGenerationTaskHandler",
    "QuestionGenerationTaskInput",
    "QuestionGenerationTaskResult",
    "SHORT_ANSWER_SCORING_TASK_TYPE",
    "SOURCE_DOCUMENT_PARSE_TASK_TYPE",
    "SourceDocumentParseTaskHandler",
    "SourceDocumentParseTaskInput",
    "SourceDocumentParseTaskResult",
    "ShortAnswerScoringTaskHandler",
    "ShortAnswerScoringTaskInput",
    "ShortAnswerScoringTaskResult",
    "register_learning_task_definitions",
]

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.storage import DocumentStorageService
from learning.errors import LearningGovernanceError
from learning.models import LearningSourceDocument, LearningSourceDocumentRevision
from learning.multimedia import PREVIEW_VERSION, SourceProcessingResult
from learning.question_generation import QuestionGenerationProcessResult
from learning.quiz_runtime import QuizAttemptSummary
from learning.source_ingestion import (
    source_document_artifact_uri,
    source_document_file_path,
)
from learning.task_definitions import (
    QuestionGenerationTaskHandler,
    QuestionGenerationTaskInput,
    ShortAnswerScoringTaskHandler,
    ShortAnswerScoringTaskInput,
    SourceDocumentParseTaskHandler,
    SourceDocumentParseTaskInput,
    register_learning_task_definitions,
)
from task_runtime import TaskRegistry
from task_runtime.contracts import TaskResultKind
from task_runtime.errors import TaskExecutionError, TaskFailureKind


class _Fence:
    def __init__(self) -> None:
        self.calls = 0

    async def assert_current(self) -> None:
        self.calls += 1


class _Context:
    def __init__(self, task_id: str, organization_id: str = "org-1") -> None:
        self.claim = SimpleNamespace(
            task_id=task_id,
            organization_id=organization_id,
        )
        self.fences: list[_Fence] = []
        self.checkpoints = 0
        self.progress: list[dict[str, object]] = []

    def fenced(self, session: AsyncSession) -> _Fence:
        del session
        fence = _Fence()
        self.fences.append(fence)
        return fence

    async def checkpoint(self) -> None:
        self.checkpoints += 1

    async def report_progress(self, **values: object) -> int:
        self.progress.append(values)
        return len(self.progress)


class _AI:
    async def invoke(self, request):
        return SimpleNamespace(request=request)


class _Outcomes:
    async def record(self, payload):  # pragma: no cover - processors are patched
        raise AssertionError(payload)


def _session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


def test_api_and_worker_registrations_share_contract_but_only_worker_executes(
    test_engine,
) -> None:
    api_registry = TaskRegistry()
    register_learning_task_definitions(api_registry)
    assert api_registry.resolve("learning.question_generation.generate", 1).handler is None
    assert api_registry.resolve("learning.quiz.short_answer_score", 1).handler is None
    assert api_registry.resolve("learning.source_document.parse", 1).handler is None

    worker_registry = TaskRegistry()
    register_learning_task_definitions(
        worker_registry,
        session_factory=_session_factory(test_engine),
        ai_factory=_AI,
        outcome_writer_factory=lambda session: _Outcomes(),
    )
    assert isinstance(
        worker_registry.resolve("learning.question_generation.generate", 1).handler,
        QuestionGenerationTaskHandler,
    )
    assert isinstance(
        worker_registry.resolve("learning.quiz.short_answer_score", 1).handler,
        ShortAnswerScoringTaskHandler,
    )
    assert isinstance(
        worker_registry.resolve("learning.source_document.parse", 1).handler,
        SourceDocumentParseTaskHandler,
    )


@pytest.mark.asyncio
async def test_source_document_parse_handler_persists_ready_revision(
    test_engine,
    monkeypatch,
    tmp_path,
) -> None:
    storage = DocumentStorageService(str(tmp_path))
    file_hash = "a" * 64
    document_id = "source-document-1"
    revision_id = "source-revision-1"
    file_path = source_document_file_path(
        storage=storage,
        organization_id="org-1",
        document_id=document_id,
        file_hash=file_hash,
        file_type="txt",
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("新人销售训练材料正文", encoding="utf-8")
    now = datetime.now(UTC)
    async with _session_factory(test_engine)() as session:
        session.add_all(
            [
                LearningSourceDocument(
                    document_id=document_id,
                    organization_id="org-1",
                    stable_key="source-one",
                    title="新人销售材料",
                    status="draft",
                    working_revision_id=revision_id,
                    version=1,
                    creation_idempotency_key_hash="b" * 64,
                    creation_fingerprint="c" * 64,
                    created_by="admin-1",
                    created_at=now,
                    updated_at=now,
                ),
                LearningSourceDocumentRevision(
                    revision_id=revision_id,
                    document_id=document_id,
                    organization_id="org-1",
                    revision_no=1,
                    revision_label="初始草稿",
                    status="working",
                    source_type="file",
                    source_uri=source_document_artifact_uri(
                        document_id=document_id,
                        file_hash=file_hash,
                        file_type="txt",
                    ),
                    file_hash=file_hash,
                    parser_version="pending-parser",
                    parse_status="pending",
                    content_hash="d" * 64,
                    version=1,
                    save_idempotency_key_hash="e" * 64,
                    save_fingerprint="f" * 64,
                    created_by="admin-1",
                    created_at=now,
                ),
            ]
        )
        await session.commit()

    monkeypatch.setattr(
        "learning.source_ingestion.get_document_storage_service",
        lambda: storage,
    )

    async def parse(plan):
        assert plan.file_path == file_path
        return SourceProcessingResult(
            processing_state="ready",
            chunk_count=2,
            artifact_available=True,
            manifest={
                "version": PREVIEW_VERSION,
                "kind": "document",
                "sections": [],
            },
            anchors=(),
        )

    monkeypatch.setattr("learning.task_definitions.parse_source_document", parse)
    context = _Context("source-task-1")
    completion = await SourceDocumentParseTaskHandler(
        _session_factory(test_engine)
    ).execute(
        context,
        SourceDocumentParseTaskInput(
            revision_id=revision_id,
            file_hash=file_hash,
            file_type="txt",
        ),
    )

    async with _session_factory(test_engine)() as session:
        revision = await session.scalar(
            select(LearningSourceDocumentRevision).where(
                LearningSourceDocumentRevision.revision_id == revision_id
            )
        )
        document = await session.get(LearningSourceDocument, document_id)

    assert revision is not None and revision.parse_status == "ready"
    # Entering the processing generation and applying its fenced result are two
    # independently observable state transitions.
    assert revision.version == 3
    assert document is not None and document.version == 3
    assert completion.structured_payload["chunk_count"] == 2
    assert completion.resource_id == revision_id
    assert [item["stage"] for item in context.progress] == [
        "validating",
        "parsing",
        "completed",
    ]


@pytest.mark.asyncio
async def test_question_generation_handler_returns_only_candidate_references(
    test_engine,
    monkeypatch,
) -> None:
    async def prepare(self, *, batch_id: str, task_id: str):
        assert batch_id == "batch-1"
        assert task_id == "task-1"
        return SimpleNamespace(request={"batch_id": batch_id})

    async def apply(self, *, plan, result):
        assert plan.request == {"batch_id": "batch-1"}
        assert result.request == plan.request
        return QuestionGenerationProcessResult(
            batch_id="batch-1",
            invocation_id="invocation-1",
            created_count=2,
            passed_count=1,
            failed_count=1,
            candidate_ids=("candidate-1", "candidate-2"),
        )

    monkeypatch.setattr(
        "learning.task_definitions.QuestionGenerationProcessor.prepare_batch",
        prepare,
    )
    monkeypatch.setattr(
        "learning.task_definitions.QuestionGenerationProcessor.apply_result",
        apply,
    )
    context = _Context("task-1")
    handler = QuestionGenerationTaskHandler(
        _session_factory(test_engine), ai_factory=_AI
    )

    result = await handler.execute(
        context, QuestionGenerationTaskInput(batch_id="batch-1")
    )

    assert result.result_kind is TaskResultKind.COMPLETE
    assert result.resource_type == "question_generation_batch"
    assert [item.resource_type for item in result.saved_items] == [
        "question_candidate",
        "question_candidate",
    ]
    assert context.checkpoints == 2
    assert sum(fence.calls for fence in context.fences) == 2


@pytest.mark.asyncio
async def test_short_answer_handler_maps_retryable_provider_failure(
    test_engine,
    monkeypatch,
) -> None:
    async def prepare(self, *, detail_id: str, task_id: str):
        del self
        return SimpleNamespace(request={"detail_id": detail_id, "task_id": task_id})

    async def apply(self, *, plan, result):
        del self, plan, result
        raise LearningGovernanceError(
            "[QUIZ_SHORT_ANSWER_SCORING_FAILED]",
            "评分暂未完成。",
            503,
            details={"retryable": True},
        )

    monkeypatch.setattr(
        "learning.task_definitions.ShortAnswerScoringProcessor.prepare_attempt",
        prepare,
    )
    monkeypatch.setattr(
        "learning.task_definitions.ShortAnswerScoringProcessor.apply_result",
        apply,
    )
    handler = ShortAnswerScoringTaskHandler(
        _session_factory(test_engine),
        ai_factory=_AI,
        outcome_writer_factory=lambda session: _Outcomes(),
    )

    with pytest.raises(TaskExecutionError) as caught:
        await handler.execute(
            _Context("task-short"),
            ShortAnswerScoringTaskInput(detail_id="quiz-attempt-1"),
        )

    assert caught.value.kind is TaskFailureKind.PROVIDER_TEMPORARY
    assert caught.value.code == "quiz_short_answer_scoring_failed"


@pytest.mark.asyncio
async def test_short_answer_handler_returns_learner_safe_result_reference(
    test_engine,
    monkeypatch,
) -> None:
    now = __import__("datetime").datetime.now(__import__("datetime").UTC)

    async def prepare(self, *, detail_id: str, task_id: str):
        del self
        assert detail_id == "quiz-attempt-1"
        assert task_id == "task-short"
        return SimpleNamespace(request={"detail_id": detail_id})

    async def apply(self, *, plan, result):
        del self, plan, result
        return QuizAttemptSummary(
            detail_id="quiz-attempt-1",
            attempt_id="attempt-1",
            organization_id="org-1",
            learner_id="learner-1",
            activity_id="quiz-1",
            quiz_revision_id="quiz-revision-1",
            status="scored",
            version=4,
            questions=(),
            rule_snapshot={},
            answers=(),
            score=1.0,
            max_score=1.0,
            passed=True,
            task_id="task-short",
            started_at=now,
            last_saved_at=now,
            submitted_at=now,
            completed_at=now,
        )

    monkeypatch.setattr(
        "learning.task_definitions.ShortAnswerScoringProcessor.prepare_attempt",
        prepare,
    )
    monkeypatch.setattr(
        "learning.task_definitions.ShortAnswerScoringProcessor.apply_result",
        apply,
    )
    handler = ShortAnswerScoringTaskHandler(
        _session_factory(test_engine),
        ai_factory=_AI,
        outcome_writer_factory=lambda session: _Outcomes(),
    )

    result = await handler.execute(
        _Context("task-short"),
        ShortAnswerScoringTaskInput(detail_id="quiz-attempt-1"),
    )

    assert result.structured_payload == {
        "detail_id": "quiz-attempt-1",
        "status": "scored",
        "score": 1.0,
        "max_score": 1.0,
        "passed": True,
    }
    assert result.location == "/api/v1/newcomer-training/activities/quiz-1"

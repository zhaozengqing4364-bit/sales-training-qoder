from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import orm_scalar
from sales_trainer.models import SalesTrainerExamPaper, SalesTrainerQuizAttempt
from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperUpdate,
    PaperAttemptCreate,
    PaperRollbackRequest,
    QuizAttemptCreate,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.exam_paper_config import ExamPaperServiceError
from sales_trainer.services.exam_paper_lifecycle_workflow import (
    ExamPaperLifecycleWorkflow,
)
from sales_trainer.services.exam_paper_publish_workflow import ExamPaperPublishWorkflow
from sales_trainer.services.exam_paper_revision_constants import PAPER_RESOURCE_TYPE
from sales_trainer.services.exam_paper_revision_history import (
    ExamPaperRevisionHistoryService,
)
from sales_trainer.services.exam_paper_revision_payloads import (
    paper_revision_has_question_snapshots,
)
from sales_trainer.services.exam_paper_revision_workflow import (
    ExamPaperRevisionWorkflow,
)
from sales_trainer.services.exam_paper_serializers import (
    serialize_exam_paper,
    serialize_paper_attempt,
)
from sales_trainer.services.exam_paper_store import (
    get_paper,
    require_paper,
    require_published_paper,
)
from sales_trainer.services.paper_snapshot_attempt_service import (
    PaperSnapshotAttemptError,
    PaperSnapshotAttemptService,
)
from sales_trainer.services.path_attempt_context_service import (
    PathAttemptContextService,
)
from sales_trainer.services.quiz_attempt_context_update import (
    attach_attempt_context_to_answers,
)
from sales_trainer.services.quiz_service import QuizService, QuizServiceError

if TYPE_CHECKING:
    from sales_trainer.orchestration.activities.base import ActivityExecutionContext
    from sales_trainer.services.path_attempt_context_service import PathAttemptContext


class ExamPaperService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_paper(
        self,
        payload: ExamPaperCreate,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        return await ExamPaperLifecycleWorkflow(self._db).create_paper(
            payload,
            actor=actor,
        )

    async def update_paper(
        self,
        paper_id: str,
        payload: ExamPaperUpdate,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        paper = await require_paper(self._db, paper_id)
        if paper.status == "published":
            return await ExamPaperRevisionWorkflow(
                self._db
            ).save_published_paper_revision(
                paper,
                payload,
                actor=actor,
            )
        if paper.status != "draft":
            raise ExamPaperServiceError(
                "[PAPER_NOT_EDITABLE]",
                "归档考卷不能修改；已发布考卷编辑会生成新修订并只影响后续学员。",
                409,
            )
        return await ExamPaperLifecycleWorkflow(self._db).update_draft_paper(
            paper,
            payload,
            actor=actor,
        )

    async def publish_paper(
        self, paper_id: str, *, actor: User
    ) -> SalesTrainerExamPaper:
        return await ExamPaperPublishWorkflow(self._db).publish_paper(
            paper_id,
            actor=actor,
        )

    async def archive_paper(
        self, paper_id: str, *, actor: User
    ) -> SalesTrainerExamPaper:
        return await ExamPaperLifecycleWorkflow(self._db).archive_paper(
            paper_id,
            actor=actor,
        )

    async def rollback_paper(
        self,
        paper_id: str,
        payload: PaperRollbackRequest,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        return await ExamPaperRevisionWorkflow(self._db).rollback_paper(
            paper_id,
            payload,
            actor=actor,
        )

    async def get_paper(self, paper_id: str) -> SalesTrainerExamPaper | None:
        return await get_paper(self._db, paper_id)

    async def get_published_paper(self, paper_id: str) -> SalesTrainerExamPaper:
        return await require_published_paper(self._db, paper_id)

    async def list_papers(
        self,
        *,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerExamPaper], int]:
        stmt = select(SalesTrainerExamPaper)
        count_stmt = select(func.count()).select_from(SalesTrainerExamPaper)
        if not include_archived:
            stmt = stmt.where(SalesTrainerExamPaper.status != "archived")
            count_stmt = count_stmt.where(SalesTrainerExamPaper.status != "archived")
        result = await self._db.execute(
            stmt.order_by(SalesTrainerExamPaper.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def list_paper_revisions(self, paper_id: str) -> list[dict[str, object]]:
        return await ExamPaperRevisionHistoryService(self._db).list_paper_revisions(
            paper_id
        )

    async def submit_paper_attempt(
        self,
        payload: PaperAttemptCreate,
        *,
        actor: User,
        execution_context: ActivityExecutionContext | None = None,
    ) -> SalesTrainerQuizAttempt:
        paper = await self.get_published_paper(payload.paper_id)
        if execution_context is not None:
            if (
                execution_context.activity.type != "quiz"
                or execution_context.activity.config.exam_paper_id != payload.paper_id
                or execution_context.learner_id != str(actor.user_id)
            ):
                raise ExamPaperServiceError(
                    "[NEWCOMER_QUIZ_CONTEXT_MISMATCH]",
                    "当前考试与训练活动不匹配。",
                    409,
                )
        revision = await SalesTrainerAssetRevisionService(self._db).active_revision(
            resource_type=PAPER_RESOURCE_TYPE,
            logical_id=orm_scalar(paper.paper_id, str),
        )
        revision_payload = revision.payload_json if revision is not None else {}
        if (
            revision is not None
            and isinstance(revision_payload, dict)
            and paper_revision_has_question_snapshots(revision_payload)
        ):
            path_context = (
                _activity_attempt_context(execution_context)
                if execution_context is not None
                else await PathAttemptContextService(self._db).resolve_for_paper(paper)
            )
            try:
                return await PaperSnapshotAttemptService(self._db).submit_attempt(
                    paper,
                    revision,
                    answers=payload.answers,
                    actor=actor,
                    attempt_context=path_context.with_paper_revision(
                        str(revision.revision_id)
                    ),
                    client_token=payload.client_token,
                )
            except PaperSnapshotAttemptError as exc:
                raise ExamPaperServiceError(
                    exc.code,
                    exc.message,
                    exc.status_code,
                ) from exc
        try:
            attempt = await QuizService(self._db).submit_attempt(
                QuizAttemptCreate(
                    unit_id=paper.unit_id,
                    answers=payload.answers,
                    client_token=payload.client_token,
                ),
                actor=actor,
            )
        except QuizServiceError as exc:
            raise ExamPaperServiceError(exc.code, exc.message, exc.status_code) from exc
        if revision is not None:
            attempt.paper_revision_id = revision.revision_id
            path_context = (
                _activity_attempt_context(execution_context)
                if execution_context is not None
                else await PathAttemptContextService(self._db).resolve_for_paper(paper)
            )
            await attach_attempt_context_to_answers(
                self._db,
                attempt_id=str(attempt.attempt_id),
                attempt_context=path_context.with_paper_revision(
                    str(revision.revision_id)
                ),
            )
            await self._db.commit()
            await self._db.refresh(attempt)
        return attempt

    async def serialize_attempt(
        self, attempt: SalesTrainerQuizAttempt
    ) -> dict[str, object]:
        return await serialize_paper_attempt(self._db, attempt)

    async def serialize_paper(self, paper: SalesTrainerExamPaper) -> dict[str, object]:
        return await serialize_exam_paper(self._db, paper)


def _activity_attempt_context(context: ActivityExecutionContext) -> PathAttemptContext:
    from sales_trainer.services.path_attempt_context_service import PathAttemptContext

    return PathAttemptContext(
        path_key="newcomer_training_path_orchestration",
        path_revision_id=context.path_revision_id,
        path_revision_no=None,
        module_key=context.module_id,
        module_type="activity_orchestrated",
        legacy_snapshot_only=False,
    )

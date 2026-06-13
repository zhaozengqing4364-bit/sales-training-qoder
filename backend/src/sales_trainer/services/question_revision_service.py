from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.schemas import SalesTrainerQuestionUpdate
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.curriculum_practice_adapter import QuestionItem
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.question_errors import SalesTrainerQuestionServiceError
from sales_trainer.services.question_payloads import (
    QUESTION_RESOURCE_TYPE,
    apply_question_revision_payload,
    question_change_class,
    question_lifecycle_metadata,
    question_lifecycle_snapshot,
    question_revision_payload_from_update,
)


class SalesTrainerQuestionRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def save_future_revision(
        self,
        question: QuestionItem,
        payload: SalesTrainerQuestionUpdate,
        *,
        actor: User,
    ) -> QuestionItem:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=QUESTION_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        previous_snapshot = _snapshot_from_revision(active, question)
        next_snapshot = question_revision_payload_from_update(question, payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=QUESTION_RESOURCE_TYPE,
                logical_id=str(question.question_id),
                payload=next_snapshot,
                actor=actor,
                change_class=question_change_class(previous_snapshot, next_snapshot),
                source_revision_id=str(active.revision_id) if active is not None else None,
                reason="save edited question revision",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerQuestionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="question_revision_saved",
            target_type="sales_trainer_question",
            target_id=str(question.question_id),
            request_id=trace_id,
            metadata={
                **question_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(question)
        return question

    async def publish_working_revision(
        self,
        question: QuestionItem,
        *,
        actor: User,
    ) -> bool:
        working = await self._revisions.latest_working_revision(
            resource_type=QUESTION_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        if working is None:
            return False
        trace_id = get_trace_id()
        previous_snapshot = question_lifecycle_snapshot(question)
        apply_question_revision_payload(
            question,
            _payload_dict(working.payload_json),
            actor_id=str(actor.user_id),
        )
        try:
            result = await self._revisions.publish_working_revision(
                working,
                actor=actor,
                reason="publish edited question revision",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerQuestionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        next_snapshot = question_lifecycle_snapshot(question)
        await self._logs.record(
            actor=actor,
            action="question_revision_published",
            target_type="sales_trainer_question",
            target_id=str(question.question_id),
            request_id=trace_id,
            metadata={
                **question_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(question)
        return True

    async def ensure_initial_published_revision(
        self,
        question: QuestionItem,
        *,
        actor: User,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=QUESTION_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = question_lifecycle_snapshot(question)
        try:
            result = await self._revisions.create_published_revision(
                resource_type=QUESTION_RESOURCE_TYPE,
                logical_id=str(question.question_id),
                payload=next_snapshot,
                actor=actor,
                change_class="scoring_high_risk",
                reason="initial question publish",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerQuestionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="question_published",
            target_type="sales_trainer_question",
            target_id=str(question.question_id),
            request_id=trace_id,
            metadata={
                **question_lifecycle_metadata(
                    previous_snapshot or next_snapshot,
                    next_snapshot,
                ),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(question)


def _snapshot_from_revision(
    revision: Any | None,
    question: QuestionItem,
) -> dict[str, Any]:
    if revision is None:
        return question_lifecycle_snapshot(question)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}

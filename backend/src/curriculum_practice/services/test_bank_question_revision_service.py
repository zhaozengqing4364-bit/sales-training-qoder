from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import QuestionItem
from curriculum_practice.schemas import QuestionItemUpdate
from curriculum_practice.services.test_bank_question_revision_payloads import (
    QUESTION_ITEM_RESOURCE_TYPE,
    QUESTION_ITEM_TARGET_TYPE,
    apply_question_item_revision_payload,
    question_item_change_class,
    question_item_lifecycle_metadata,
    question_item_lifecycle_snapshot,
    question_item_publish_decision_from_payload,
    question_item_revision_payload_from_update,
)
from curriculum_practice.services.sales_trainer_revision_adapter import (
    OperationLogService,
    SalesTrainerAssetRevision,
    SalesTrainerAssetRevisionService,
)


class TestBankQuestionRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def stage_future_revision(
        self,
        question: QuestionItem,
        payload: QuestionItemUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=QUESTION_ITEM_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        previous_snapshot = _snapshot_from_revision(active, question)
        next_snapshot = question_item_revision_payload_from_update(question, payload)
        revision = await self._revisions.save_working_revision(
            resource_type=QUESTION_ITEM_RESOURCE_TYPE,
            logical_id=str(question.question_id),
            payload=next_snapshot,
            actor=actor,
            change_class=question_item_change_class(
                previous_snapshot,
                next_snapshot,
            ),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason="save edited test bank question revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="test_bank_question_revision_saved",
            target_type=QUESTION_ITEM_TARGET_TYPE,
            target_id=str(question.question_id),
            request_id=trace_id,
            metadata={
                **question_item_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return revision

    async def stage_initial_published_revision(
        self,
        question: QuestionItem,
        *,
        actor: User,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=QUESTION_ITEM_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = question_item_lifecycle_snapshot(question)
        result = await self._revisions.create_published_revision(
            resource_type=QUESTION_ITEM_RESOURCE_TYPE,
            logical_id=str(question.question_id),
            payload=next_snapshot,
            actor=actor,
            change_class="scoring_high_risk",
            reason="initial test bank question publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="test_bank_question_published",
            target_type=QUESTION_ITEM_TARGET_TYPE,
            target_id=str(question.question_id),
            request_id=trace_id,
            metadata={
                **question_item_lifecycle_metadata(
                    previous_snapshot or next_snapshot,
                    next_snapshot,
                ),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )

    async def stage_publish_working_revision(
        self,
        question: QuestionItem,
        *,
        actor: User,
    ) -> Result[bool]:
        working = await self._revisions.latest_working_revision(
            resource_type=QUESTION_ITEM_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        if working is None:
            return Result.ok(False)
        payload = _payload_dict(working.payload_json)
        decision = question_item_publish_decision_from_payload(payload)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[QUESTION_ITEM_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=QUESTION_ITEM_RESOURCE_TYPE,
            logical_id=str(question.question_id),
        )
        previous_snapshot = _payload_dict(active.payload_json) if active else payload
        apply_question_item_revision_payload(
            question,
            payload,
            actor_id=str(actor.user_id),
        )
        result = await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason="publish edited test bank question revision",
            trace_id=trace_id,
        )
        next_snapshot = question_item_lifecycle_snapshot(question)
        await self._logs.record(
            actor=actor,
            action="test_bank_question_revision_published",
            target_type=QUESTION_ITEM_TARGET_TYPE,
            target_id=str(question.question_id),
            request_id=trace_id,
            metadata={
                **question_item_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return Result.ok(True)


def _snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    question: QuestionItem,
) -> dict[str, Any]:
    if revision is None:
        return question_item_lifecycle_snapshot(question)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import ExaminerAgent
from curriculum_practice.schemas import ExaminerAgentUpdate, PublishGateDecision
from curriculum_practice.services.examiner_agent_payloads import (
    apply_examiner_agent_revision_payload,
    examiner_agent_lifecycle_snapshot,
    examiner_agent_revision_payload_from_update,
)
from curriculum_practice.services.examiner_agent_publish_gates import (
    validate_examiner_agent_publish,
)
from curriculum_practice.services.examiner_agent_revision_metadata import (
    EXAMINER_AGENT_RESOURCE_TYPE,
    EXAMINER_AGENT_TARGET_TYPE,
    examiner_agent_change_class,
    examiner_agent_lifecycle_metadata,
)
from curriculum_practice.services.sales_trainer_revision_adapter import (
    OperationLogService,
    SalesTrainerAssetRevision,
    SalesTrainerAssetRevisionService,
)


class ExaminerAgentRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def stage_future_revision(
        self,
        agent: ExaminerAgent,
        payload: ExaminerAgentUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=EXAMINER_AGENT_RESOURCE_TYPE,
            logical_id=str(agent.examiner_agent_id),
        )
        previous_snapshot = _snapshot_from_revision(active, agent)
        next_snapshot = examiner_agent_revision_payload_from_update(agent, payload)
        revision = await self._revisions.save_working_revision(
            resource_type=EXAMINER_AGENT_RESOURCE_TYPE,
            logical_id=str(agent.examiner_agent_id),
            payload=next_snapshot,
            actor=actor,
            change_class=examiner_agent_change_class(previous_snapshot, next_snapshot),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason="save edited examiner agent revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="examiner_agent_revision_saved",
            target_type=EXAMINER_AGENT_TARGET_TYPE,
            target_id=str(agent.examiner_agent_id),
            request_id=trace_id,
            metadata={
                **examiner_agent_lifecycle_metadata(
                    previous_snapshot,
                    next_snapshot,
                ),
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
        agent: ExaminerAgent,
        *,
        actor: User,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=EXAMINER_AGENT_RESOURCE_TYPE,
            logical_id=str(agent.examiner_agent_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = examiner_agent_lifecycle_snapshot(agent)
        result = await self._revisions.create_published_revision(
            resource_type=EXAMINER_AGENT_RESOURCE_TYPE,
            logical_id=str(agent.examiner_agent_id),
            payload=next_snapshot,
            actor=actor,
            change_class="scoring_high_risk",
            reason="initial examiner agent publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="examiner_agent_published",
            target_type=EXAMINER_AGENT_TARGET_TYPE,
            target_id=str(agent.examiner_agent_id),
            request_id=trace_id,
            metadata={
                **examiner_agent_lifecycle_metadata(next_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )

    async def stage_publish_working_revision(
        self,
        agent: ExaminerAgent,
        *,
        actor: User,
    ) -> tuple[bool, PublishGateDecision]:
        working = await self._revisions.latest_working_revision(
            resource_type=EXAMINER_AGENT_RESOURCE_TYPE,
            logical_id=str(agent.examiner_agent_id),
        )
        ok_decision = PublishGateDecision(can_publish=True, results=[])
        if working is None:
            return False, ok_decision
        payload = _payload_dict(working.payload_json)
        decision = await validate_examiner_agent_publish(self._db, payload)
        if not decision.can_publish:
            return False, decision
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=EXAMINER_AGENT_RESOURCE_TYPE,
            logical_id=str(agent.examiner_agent_id),
        )
        previous_snapshot = _payload_dict(active.payload_json) if active else payload
        apply_examiner_agent_revision_payload(
            agent,
            payload,
            actor_id=str(actor.user_id),
            published_at=datetime.now(UTC),
        )
        result = await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason="publish edited examiner agent revision",
            trace_id=trace_id,
        )
        next_snapshot = examiner_agent_lifecycle_snapshot(agent)
        await self._logs.record(
            actor=actor,
            action="examiner_agent_revision_published",
            target_type=EXAMINER_AGENT_TARGET_TYPE,
            target_id=str(agent.examiner_agent_id),
            request_id=trace_id,
            metadata={
                **examiner_agent_lifecycle_metadata(
                    previous_snapshot,
                    next_snapshot,
                ),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return True, decision


def _snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    agent: ExaminerAgent,
) -> dict[str, Any]:
    if revision is None:
        return examiner_agent_lifecycle_snapshot(agent)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}

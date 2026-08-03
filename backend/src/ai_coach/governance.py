"""Organization-scoped human-help queue and append-only Coach intervention."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import CoachContextSnapshot, CoachHumanInterventionInput
from ai_coach.errors import AICoachError
from ai_coach.models import (
    CoachCardResponse,
    CoachCommandAudit,
    CoachHumanIntervention,
    CoachRemediationCycle,
    CoachSession,
    CoachTrainingCard,
)


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CoachReviewActor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    capabilities: frozenset[str] = Field(default_factory=frozenset)
    trace_id: str | None = Field(default=None, max_length=160)


class CoachHumanHelpQueueItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    learner_id: str
    activity_id: str
    checkpoint: int
    cycle: int
    reason: str
    attempted_cycles: int
    weakness_summaries: tuple[str, ...]
    updated_at: datetime


class CoachHumanHelpDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    learner_id: str
    activity_id: str
    status: str
    checkpoint: int
    cycle: int
    source_context: tuple[dict[str, Any], ...]
    weaknesses: tuple[dict[str, Any], ...]
    cycles: tuple[dict[str, Any], ...]
    responses: tuple[dict[str, Any], ...]
    interventions: tuple[dict[str, Any], ...]
    version: int


class CoachGovernanceService:
    CAPABILITY = "newcomer.coach.review"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_help_queue(
        self,
        *,
        actor: CoachReviewActor,
        limit: int = 100,
    ) -> tuple[CoachHumanHelpQueueItem, ...]:
        self._require(actor)
        rows = list(
            (
                await self._session.execute(
                    select(CoachSession)
                    .where(CoachSession.organization_id == actor.organization_id)
                    .where(CoachSession.status == "needs_human_help")
                    .where(
                        or_(
                            CoachSession.human_help_status.is_(None),
                            CoachSession.human_help_status == "open",
                        )
                    )
                    .order_by(desc(CoachSession.updated_at))
                    .limit(limit)
                )
            ).scalars()
        )
        result: list[CoachHumanHelpQueueItem] = []
        for row in rows:
            context = CoachContextSnapshot.model_validate(row.context_snapshot_json)
            cycles = list(
                (
                    await self._session.execute(
                        select(CoachRemediationCycle).where(
                            CoachRemediationCycle.session_id == row.session_id
                        )
                    )
                ).scalars()
            )
            result.append(
                CoachHumanHelpQueueItem(
                    session_id=row.session_id,
                    learner_id=row.learner_id,
                    activity_id=row.activity_id,
                    checkpoint=row.checkpoint_index + 1,
                    cycle=row.cycle_no,
                    reason=row.safe_error_message or "自动补练已到边界或证据不足",
                    attempted_cycles=len(cycles),
                    weakness_summaries=tuple(
                        item.summary for item in context.weaknesses
                    ),
                    updated_at=row.updated_at,
                )
            )
        return tuple(result)

    async def get_help_detail(
        self,
        *,
        actor: CoachReviewActor,
        session_id: str,
    ) -> CoachHumanHelpDetail:
        self._require(actor)
        row = await self._load(actor, session_id, for_update=False)
        context = CoachContextSnapshot.model_validate(row.context_snapshot_json)
        cycles = list(
            (
                await self._session.execute(
                    select(CoachRemediationCycle)
                    .where(CoachRemediationCycle.session_id == row.session_id)
                    .order_by(
                        CoachRemediationCycle.checkpoint_index,
                        CoachRemediationCycle.cycle_no,
                    )
                )
            ).scalars()
        )
        cards = {
            item.card_id: item
            for item in (
                await self._session.execute(
                    select(CoachTrainingCard).where(
                        CoachTrainingCard.session_id == row.session_id
                    )
                )
            ).scalars()
        }
        responses = list(
            (
                await self._session.execute(
                    select(CoachCardResponse)
                    .where(CoachCardResponse.session_id == row.session_id)
                    .order_by(CoachCardResponse.submitted_at)
                )
            ).scalars()
        )
        interventions = list(
            (
                await self._session.execute(
                    select(CoachHumanIntervention)
                    .where(CoachHumanIntervention.session_id == row.session_id)
                    .order_by(CoachHumanIntervention.created_at)
                )
            ).scalars()
        )
        return CoachHumanHelpDetail(
            session_id=row.session_id,
            learner_id=row.learner_id,
            activity_id=row.activity_id,
            status=row.status,
            checkpoint=row.checkpoint_index + 1,
            cycle=row.cycle_no,
            source_context=tuple(
                {
                    "ref_id": item.ref_id,
                    "resource_type": item.resource_type,
                    "label": item.label,
                    "revision_id": item.revision_id,
                }
                for item in context.references
            ),
            weaknesses=tuple(
                item.model_dump(mode="json") for item in context.weaknesses
            ),
            cycles=tuple(
                {
                    "cycle_id": item.cycle_id,
                    "checkpoint": item.checkpoint_index + 1,
                    "cycle": item.cycle_no,
                    "status": item.status,
                    "reason": item.reason,
                    "score_percent": (
                        float(item.score_percent)
                        if item.score_percent is not None
                        else None
                    ),
                    "maximum_uncertainty": (
                        float(item.maximum_uncertainty)
                        if item.maximum_uncertainty is not None
                        else None
                    ),
                    "result": item.result_summary_json,
                }
                for item in cycles
            ),
            responses=tuple(
                {
                    "response_id": item.response_id,
                    "card": (
                        cards[item.card_id].public_payload_json
                        if item.card_id in cards
                        else None
                    ),
                    "answer": item.raw_answer_json,
                    "status": item.status,
                    "score_percent": (
                        float(item.score_percent)
                        if item.score_percent is not None
                        else None
                    ),
                    "feedback": item.evaluation_json,
                    "source_ref_ids": item.source_ref_ids_json,
                    "evaluation_kind": item.evaluation_kind,
                    "invocation_id": item.invocation_id,
                    "prompt_revision_id": item.prompt_revision_id,
                    "model_routing_revision_id": item.model_routing_revision_id,
                }
                for item in responses
            ),
            interventions=tuple(
                {
                    "intervention_id": item.intervention_id,
                    "action": item.action,
                    "reason": item.reason,
                    "guidance": item.guidance,
                    "target_resource_id": item.target_resource_id,
                    "actor_id": item.actor_id,
                    "created_at": item.created_at,
                }
                for item in interventions
            ),
            version=row.version,
        )

    async def intervene(
        self,
        *,
        actor: CoachReviewActor,
        session_id: str,
        payload: CoachHumanInterventionInput,
        expected_version: int,
        idempotency_key: str,
    ) -> CoachHumanHelpDetail:
        self._require(actor)
        row = await self._load(actor, session_id, for_update=True)
        key_hash = _secret_hash(idempotency_key)
        replay = await self._session.scalar(
            select(CoachHumanIntervention)
            .where(CoachHumanIntervention.session_id == row.session_id)
            .where(CoachHumanIntervention.idempotency_key_hash == key_hash)
            .limit(1)
        )
        if replay is not None:
            if (
                replay.action != payload.action
                or replay.reason != payload.reason
                or replay.guidance != payload.guidance
                or replay.target_resource_id != payload.target_resource_id
            ):
                raise AICoachError(
                    "[COACH_IDEMPOTENCY_CONFLICT]",
                    "同一操作标识已用于不同内容。",
                    409,
                )
            return await self.get_help_detail(actor=actor, session_id=session_id)
        if row.version != expected_version:
            raise AICoachError(
                "[COACH_VERSION_CONFLICT]",
                "训练记录已更新，请刷新后继续。",
                412,
                details={
                    "expected_version": expected_version,
                    "actual_version": row.version,
                },
            )
        if row.status != "needs_human_help":
            raise AICoachError(
                "[COACH_HUMAN_HELP_STATE_CONFLICT]",
                "当前训练会话不在人工帮助队列中。",
                409,
            )
        before_version = row.version
        intervention = CoachHumanIntervention(
            intervention_id=_id(),
            session_id=row.session_id,
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=self.CAPABILITY,
            action=payload.action,
            reason=payload.reason,
            guidance=payload.guidance,
            target_resource_id=payload.target_resource_id,
            idempotency_key_hash=key_hash,
            trace_id=actor.trace_id,
            created_at=_now(),
        )
        self._session.add(intervention)
        if payload.action != "add_guidance":
            row.human_help_status = "resolved"
            row.human_help_next_action_json = {
                "type": payload.action,
                "target_resource_id": payload.target_resource_id,
                "guidance": payload.guidance,
            }
        else:
            row.human_help_status = "open"
            row.human_help_next_action_json = {
                "type": "review_guidance",
                "guidance": payload.guidance,
            }
        row.version += 1
        row.updated_at = _now()
        audit = CoachCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=self.CAPABILITY,
            object_type="coach_session",
            object_id=row.session_id,
            command=payload.action,
            before_version=before_version,
            after_version=row.version,
            idempotency_key_hash=key_hash,
            reason=payload.reason,
            trace_id=actor.trace_id,
            result="succeeded",
            details_json={"target_resource_id": payload.target_resource_id},
            occurred_at=_now(),
        )
        self._session.add(audit)
        await self._session.flush([intervention, row, audit])
        return await self.get_help_detail(actor=actor, session_id=session_id)

    async def _load(
        self,
        actor: CoachReviewActor,
        session_id: str,
        *,
        for_update: bool,
    ) -> CoachSession:
        query = select(CoachSession).where(CoachSession.session_id == session_id)
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None or row.organization_id != actor.organization_id:
            raise AICoachError(
                "[COACH_SESSION_NOT_FOUND]",
                "训练会话不存在或不可访问。",
                404,
            )
        return row

    @classmethod
    def _require(cls, actor: CoachReviewActor) -> None:
        if cls.CAPABILITY not in actor.capabilities:
            raise AICoachError(
                "[COACH_PERMISSION_DENIED]", "没有复核该训练会话的权限。", 403
            )


__all__ = [
    "CoachGovernanceService",
    "CoachHumanHelpDetail",
    "CoachHumanHelpQueueItem",
    "CoachReviewActor",
]

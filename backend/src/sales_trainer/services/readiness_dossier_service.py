"""Activity-native readiness projection without product/module-name authority."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.journey_service import NewcomerJourneyService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.training_record_service import TrainingRecordService

ReadinessDecision = Literal["approve", "reject", "retrain"]


class ReadinessDossierError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class ReadinessDossierService:
    def __init__(self, db: AsyncSession, **_: Any) -> None:
        self._db = db
        self._journeys = NewcomerJourneyService(db)
        self._records = TrainingRecordService(db)
        self._logs = OperationLogService(db)

    async def get_dossier(
        self,
        learner_id: str,
        *,
        viewer: User,
        team_department: str | None,
    ) -> dict[str, Any]:
        learner = await self._db.get(User, learner_id)
        if learner is None or (
            team_department is not None
            and str(learner.department or "") != team_department
        ):
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_LEARNER_NOT_FOUND]", "学员不存在或不在管理范围内。", 404
            )
        try:
            journey = await self._journeys.get_or_create_for_learner(learner=learner)
        except NewcomerOrchestrationError as exc:
            raise ReadinessDossierError(exc.code, exc.message, exc.status_code) from exc
        records, _ = await self._records.list_records(
            user_id=learner_id,
            team_department=team_department,
            viewer=viewer,
            limit=500,
        )
        activity_records = [
            item
            for item in records
            if item.get("record_type") == "newcomer_activity_attempt"
        ]
        failed = [item for item in activity_records if item.get("status") == "failed"]
        review_actions = await self._review_actions(learner_id)
        latest_review_action = review_actions[0] if review_actions else None
        base_status = (
            "not_passed"
            if failed
            else "pending_review"
            if journey.progress.completed
            else "in_training"
        )
        status = _reviewed_status(base_status, latest_review_action)
        return {
            "contract_version": "activity_readiness_v1",
            "generated_at": datetime.now(UTC),
            "learner": {
                "learner_id": str(learner.user_id),
                "name": learner.name,
                "department": learner.department,
            },
            "status": status,
            "journey": journey.model_dump(),
            "evidence": activity_records,
            "failed_activity_ids": [item.get("activity_id") for item in failed],
            "competencies": _aggregate_competencies(activity_records),
            "review_actions": review_actions,
            "latest_review_action": latest_review_action,
        }

    async def list_workbench(
        self,
        *,
        viewer: User,
        team_department: str | None,
        department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        effective_department = team_department or department
        statement = select(User).where(User.is_active.is_(True))
        if effective_department:
            statement = statement.where(User.department == effective_department)
        learners = list(
            (
                await self._db.scalars(
                    statement.order_by(User.created_at.asc()).offset(offset).limit(limit)
                )
            ).all()
        )
        items = [
            await self.get_dossier(
                str(learner.user_id),
                viewer=viewer,
                team_department=team_department,
            )
            for learner in learners
        ]
        return {
            "contract_version": "activity_readiness_v1",
            "generated_at": datetime.now(UTC),
            "items": items,
            "total": len(items),
            "filters": {"department": effective_department, "limit": limit, "offset": offset},
        }

    async def create_review_action(
        self,
        learner_id: str,
        *,
        actor: User,
        team_department: str | None,
        decision: ReadinessDecision,
        reason: str,
        capability_keys: list[str] | None = None,
        source_evidence_ids: list[str] | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        dossier = await self.get_dossier(
            learner_id, viewer=actor, team_department=team_department
        )
        if decision == "approve" and dossier["status"] != "pending_review":
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_NOT_READY]",
                "必修活动全部完成后才能确认达标。",
                409,
                {"required_status": "pending_review"},
            )
        known_ids = {
            str(item.get("evidence_id"))
            for item in dossier["evidence"]
            if item.get("evidence_id")
        }
        requested_ids = {str(value) for value in source_evidence_ids or []}
        if not requested_ids.issubset(known_ids):
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_EVIDENCE_INVALID]", "复核引用了不存在的活动证据。", 400
            )
        log = await self._logs.record(
            actor=actor,
            action="newcomer_activity.readiness_reviewed",
            target_type="newcomer_activity_readiness",
            target_id=learner_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "decision": decision,
                "reason": reason,
                "capability_keys": capability_keys or [],
                "source_evidence_ids": sorted(requested_ids),
            },
        )
        await self._db.commit()
        return {
            "action_id": str(log.log_id),
            "decision": decision,
            "reason": reason,
            "source_evidence_ids": sorted(requested_ids),
            "created_at": log.created_at,
        }

    async def _review_actions(self, learner_id: str) -> list[dict[str, Any]]:
        logs, _ = await self._logs.list_logs(
            target_type="newcomer_activity_readiness",
            target_id=learner_id,
            limit=100,
        )
        return [
            {
                "action_id": str(item.log_id),
                "actor_id": item.actor_id,
                "created_at": item.created_at,
                **dict(item.metadata_json or {}),
            }
            for item in logs
        ]


__all__ = ["ReadinessDossierError", "ReadinessDossierService"]


def _aggregate_competencies(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, float] = {}
    for record in reversed(records):
        for item in record.get("capability_scores") or []:
            key = str(item.get("capability_key") or "").strip()
            score = item.get("score")
            if key and isinstance(score, int | float):
                latest[key] = float(score)
    return [
        {"capability_key": key, "score": latest[key]}
        for key in sorted(latest)
    ]


def _reviewed_status(
    base_status: str, latest_action: dict[str, Any] | None
) -> str:
    if base_status != "pending_review" or latest_action is None:
        return base_status
    return {
        "approve": "approved",
        "reject": "not_passed",
        "retrain": "needs_retraining",
    }.get(str(latest_action.get("decision")), base_status)

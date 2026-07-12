from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.services.journey_read_repository import (
    JourneyLearnerProjection,
    JourneyReadRepository,
    JourneyViewer,
)
from sales_trainer.services.journey_sqlalchemy_adapter import (
    SqlAlchemyJourneyReadRepository,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.readiness_dossier_projection import (
    ReadinessDecision,
    ReadinessDossierError,
    ReadinessDossierProjection,
)
from sales_trainer.services.readiness_state import (
    CAPABILITY_KEYS,
    READINESS_CONTRACT_VERSION,
    READINESS_DOSSIER_TARGET_TYPE,
    REVIEW_ACTION_CREATED,
    decision_label,
    unique_non_empty,
)
from sales_trainer.services.training_journey_service import (
    TrainingJourneyError,
    TrainingJourneyService,
)
from sales_trainer.services.training_record_service import TrainingRecordService


class ReadinessDossierService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        read_repository: JourneyReadRepository | None = None,
        projection: ReadinessDossierProjection | None = None,
    ) -> None:
        self._db = db
        self._read_repository = read_repository or SqlAlchemyJourneyReadRepository(db)
        self._projection = projection or ReadinessDossierProjection()
        self._journeys = TrainingJourneyService(
            db, read_repository=self._read_repository
        )
        self._records = TrainingRecordService(db)
        self._logs = OperationLogService(db)

    async def get_dossier(
        self,
        learner_id: str,
        *,
        viewer: JourneyViewer,
        team_department: str | None,
    ) -> dict[str, Any]:
        generated_at = datetime.now(UTC)
        learner = await self._learner_for_viewer(
            learner_id,
            team_department=team_department,
        )
        try:
            journey = await self._journeys.get_admin_journey(
                learner_id,
                viewer=viewer,
                team_department=team_department,
            )
        except TrainingJourneyError as exc:
            if exc.code != "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
                raise ReadinessDossierError(
                    exc.code, exc.message, exc.status_code
                ) from exc
            journey = self._projection.blocked_journey(
                learner,
                code=exc.code,
                message=exc.message,
                generated_at=generated_at,
            )

        records, _ = await self._records.list_records(
            user_id=learner_id,
            team_department=team_department,
            viewer=cast(Any, viewer),
            limit=200,
            offset=0,
        )
        review_actions = await self._review_actions(learner_id)
        return self._projection.dossier_payload(
            journey,
            records=records,
            review_actions=review_actions,
            generated_at=generated_at,
        )

    async def list_workbench(
        self,
        *,
        viewer: JourneyViewer,
        team_department: str | None,
        department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        generated_at = datetime.now(UTC)
        try:
            payload = await self._journeys.list_admin_journeys(
                viewer=viewer,
                team_department=team_department,
                department=department,
                limit=limit,
                offset=offset,
            )
            journeys = [
                self._projection.dossier_payload(
                    journey,
                    records=[],
                    review_actions=await self._review_actions(
                        str(journey["learner_id"])
                    ),
                    evidence_limit=0,
                    generated_at=generated_at,
                )
                for journey in payload.get("items", [])
            ]
            total = int(payload.get("total") or len(journeys))
        except TrainingJourneyError as exc:
            if exc.code != "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
                raise ReadinessDossierError(
                    exc.code, exc.message, exc.status_code
                ) from exc
            learners, total = await self._learners_for_workbench(
                team_department=team_department,
                department=department,
                limit=limit,
                offset=offset,
            )
            journeys = [
                self._projection.dossier_payload(
                    self._projection.blocked_journey(
                        learner,
                        code=exc.code,
                        message=exc.message,
                        generated_at=generated_at,
                    ),
                    records=[],
                    review_actions=await self._review_actions(str(learner.user_id)),
                    evidence_limit=0,
                    generated_at=generated_at,
                )
                for learner in learners
            ]

        groups = self._projection.workbench_groups(journeys)
        return {
            "contract_version": READINESS_CONTRACT_VERSION,
            "generated_at": generated_at,
            "groups": groups,
            "summary": {
                "learner_count": total,
                "loaded_learner_count": len(journeys),
                "pending_review_count": len(groups["pending_review"]["items"]),
                "not_passed_count": len(groups["not_passed"]["items"]),
                "needs_retraining_count": len(groups["needs_retraining"]["items"]),
                "approved_count": len(groups["approved"]["items"]),
                "config_exception_count": len(groups["config_exception"]["items"]),
                "in_training_count": len(groups["in_training"]["items"]),
            },
            "filters": {
                "department": team_department or department,
                "limit": limit,
                "offset": offset,
            },
        }

    async def create_review_action(
        self,
        learner_id: str,
        *,
        actor: JourneyViewer,
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
            learner_id,
            viewer=actor,
            team_department=team_department,
        )
        normalized_capabilities = unique_non_empty(capability_keys or [])
        unknown_capabilities = sorted(set(normalized_capabilities) - CAPABILITY_KEYS)
        if unknown_capabilities:
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_CAPABILITY_INVALID]",
                "复核动作包含系统未识别的能力项。",
                400,
                details={"unknown_capability_keys": unknown_capabilities},
            )
        evidence_ids = unique_non_empty(source_evidence_ids or [])
        known_evidence_ids = {
            str(item.get("evidence_id"))
            for item in dossier.get("evidence", [])
            if item.get("evidence_id")
        }
        unknown_evidence_ids = sorted(set(evidence_ids) - known_evidence_ids)
        if unknown_evidence_ids:
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_EVIDENCE_INVALID]",
                "复核动作引用了不存在或无权访问的训练证据。",
                400,
                details={"unknown_evidence_ids": unknown_evidence_ids},
            )
        if decision == "approve":
            self._projection.validate_dossier_approval(dossier)
        if not evidence_ids:
            evidence_ids = self._projection.default_review_evidence_ids(dossier)
        if not normalized_capabilities:
            normalized_capabilities = self._projection.default_review_capability_keys(
                dossier
            )

        retraining_task = None
        if decision == "require_retraining":
            retraining_task = {
                "task_id": f"retraining:{learner_id}:{datetime.now(UTC).timestamp()}",
                "status": "pending",
                "source": "operation_log",
                "capability_keys": normalized_capabilities,
                "source_evidence_ids": evidence_ids,
                "target_learner_id": learner_id,
            }

        log = await self._logs.record(
            actor=cast(Any, actor),
            action=REVIEW_ACTION_CREATED,
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "contract_version": READINESS_CONTRACT_VERSION,
                "decision": decision,
                "decision_label": decision_label(decision),
                "reason": reason.strip(),
                "capability_keys": normalized_capabilities,
                "source_evidence_ids": evidence_ids,
                "retraining_task": retraining_task,
                "state_storage": "operation_log",
            },
        )
        await self._db.commit()
        return self._review_action_payload(log)

    async def _learner_for_viewer(
        self,
        learner_id: str,
        *,
        team_department: str | None,
    ) -> JourneyLearnerProjection:
        learner = await self._read_repository.learner(learner_id)
        if learner is None:
            raise ReadinessDossierError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        if (
            team_department is not None
            and str(learner.department or "") != team_department
        ):
            raise ReadinessDossierError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        return learner

    async def _learners_for_workbench(
        self,
        *,
        team_department: str | None,
        department: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[JourneyLearnerProjection], int]:
        page = await self._read_repository.learners(
            team_department=team_department,
            department=department,
            limit=limit,
            offset=offset,
            include_development_admin=False,
        )
        return list(page.items), page.total

    async def _review_actions(self, learner_id: str) -> list[dict[str, Any]]:
        logs, _ = await self._logs.list_logs(
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            limit=50,
        )
        return [
            self._review_action_payload(log)
            for log in logs
            if log.action == REVIEW_ACTION_CREATED
        ]

    @staticmethod
    def _review_action_payload(log: Any) -> dict[str, Any]:
        metadata = log.metadata_json if isinstance(log.metadata_json, dict) else {}
        decision = str(metadata.get("decision") or "mark_manual_follow_up")
        return {
            "action_id": str(log.log_id),
            "audit_log_id": str(log.log_id),
            "decision": decision,
            "decision_label": metadata.get("decision_label")
            or decision_label(decision),
            "reason": metadata.get("reason"),
            "capability_keys": unique_non_empty(metadata.get("capability_keys") or []),
            "source_evidence_ids": unique_non_empty(
                metadata.get("source_evidence_ids") or []
            ),
            "reviewer_id": str(log.actor_id) if log.actor_id else None,
            "reviewer_role": log.actor_role,
            "created_at": log.created_at,
            "retraining_task": metadata.get("retraining_task"),
            "state_storage": metadata.get("state_storage") or "operation_log",
        }

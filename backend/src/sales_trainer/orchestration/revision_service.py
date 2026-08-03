"""Governed draft/publish lifecycle for the activity-orchestrated training path."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.orchestration.contracts import (
    PathIssueResponse,
    PathValidationResponse,
    TrainingPathConfigResponse,
    TrainingPathPayload,
)
from sales_trainer.orchestration.errors import (
    NewcomerOrchestrationError,
    PathRevisionConflictError,
    PathValidationError,
)
from sales_trainer.orchestration.graph import PathIssue, validate_path_graph
from sales_trainer.orchestration.repository import EnrollmentRepository
from sales_trainer.orchestration.resource_validator import PathResourceValidator
from sales_trainer.services.asset_revision_service import (
    AssetPublishResult,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.realtime_binding_snapshot_service import (
    freeze_realtime_bindings,
    validate_realtime_binding_snapshots,
)

PATH_RESOURCE_TYPE = "newcomer_training_path_orchestration"
PATH_LOGICAL_ID = "default"


class ResourceValidator(Protocol):
    async def validate(self, payload: TrainingPathPayload) -> tuple[PathIssue, ...]: ...


class TrainingPathRevisionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        resource_validator: ResourceValidator | None = None,
    ) -> None:
        self._db = db
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._resources = resource_validator or PathResourceValidator(db)
        self._operations = OperationLogService(db)
        self._enrollments = EnrollmentRepository(db)

    async def active_revision(self) -> SalesTrainerAssetRevision | None:
        return await self._revisions.active_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )

    async def working_revision(self) -> SalesTrainerAssetRevision | None:
        return await self._revisions.latest_working_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )

    async def get_config(self) -> TrainingPathConfigResponse:
        active = await self.active_revision()
        working = await self.working_revision()
        source = working or active
        payload = (
            TrainingPathPayload.model_validate(source.payload_json)
            if source is not None
            else TrainingPathPayload(title="新人训练路径", phases=[])
        )
        return TrainingPathConfigResponse(
            active_revision_id=str(active.revision_id) if active else None,
            active_revision_no=int(active.revision_no) if active else None,
            working_revision_id=str(working.revision_id) if working else None,
            payload=payload,
        )

    async def save_draft(
        self,
        *,
        payload: TrainingPathPayload,
        actor: User,
        reason: str,
        trace_id: str | None = None,
        expected_revision_id: str | None = None,
        preserve_runtime_snapshots: bool = False,
    ) -> SalesTrainerAssetRevision:
        await self._assert_expected_revision(expected_revision_id)
        payload = await freeze_realtime_bindings(
            self._db,
            payload,
            refresh_existing=not preserve_runtime_snapshots,
        )
        issues = validate_path_graph(payload)
        if issues:
            raise PathValidationError(issues)
        revision = await self._revisions.save_working_revision(
            resource_type=PATH_RESOURCE_TYPE,
            logical_id=PATH_LOGICAL_ID,
            payload=payload.model_dump(mode="json"),
            actor=actor,
            change_class="semantic",
            reason=reason,
            trace_id=trace_id,
        )
        await self._operations.record(
            actor=actor,
            action="newcomer_path.draft_saved",
            target_type="newcomer_training_path",
            target_id=str(revision.revision_id),
            request_id=trace_id,
            metadata={"reason": reason, "revision_no": int(revision.revision_no)},
        )
        return revision

    async def validate_candidate(
        self, payload: TrainingPathPayload
    ) -> PathValidationResponse:
        payload = await freeze_realtime_bindings(self._db, payload)
        issues = await self._collect_issues(payload)
        return self._validation_response(issues)

    async def validate_draft(self) -> PathValidationResponse:
        working = await self.working_revision()
        if working is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_DRAFT_MISSING]", "当前没有可检查的草稿。", 404
            )
        payload = TrainingPathPayload.model_validate(working.payload_json)
        return await self.validate_candidate(payload)

    async def publish_candidate(
        self,
        *,
        payload: TrainingPathPayload,
        actor: User,
        reason: str,
        expected_revision_id: str | None,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        payload = await freeze_realtime_bindings(self._db, payload)
        issues = await self._collect_issues(payload)
        if issues:
            raise PathValidationError(issues)
        await self._assert_expected_revision(expected_revision_id)
        revision = await self.save_draft(
            payload=payload,
            actor=actor,
            reason=reason,
            trace_id=trace_id,
            expected_revision_id=expected_revision_id,
        )
        result = await self._revisions.publish_working_revision(
            revision, actor=actor, reason=reason, trace_id=trace_id
        )
        synced_enrollment_count = await self._enrollments.sync_active_path_revision(
            path_id=PATH_LOGICAL_ID,
            path_revision_id=str(result.revision.revision_id),
        )
        await self._operations.record(
            actor=actor,
            action="newcomer_path.published",
            target_type="newcomer_training_path",
            target_id=str(result.revision.revision_id),
            request_id=trace_id,
            metadata={
                "reason": reason,
                "candidate_publish": True,
                "rollout_scope": "all_active_learners",
                "synced_enrollment_count": synced_enrollment_count,
            },
        )
        return result

    async def publish(
        self, *, actor: User, reason: str, trace_id: str | None = None
    ) -> AssetPublishResult:
        working = await self.working_revision()
        if working is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_DRAFT_MISSING]", "当前没有可发布的草稿。", 404
            )
        payload = TrainingPathPayload.model_validate(working.payload_json)
        issues = await self._collect_issues(payload)
        if issues:
            raise PathValidationError(issues)
        result = await self._revisions.publish_working_revision(
            working, actor=actor, reason=reason, trace_id=trace_id
        )
        synced_enrollment_count = await self._enrollments.sync_active_path_revision(
            path_id=PATH_LOGICAL_ID,
            path_revision_id=str(result.revision.revision_id),
        )
        await self._operations.record(
            actor=actor,
            action="newcomer_path.published",
            target_type="newcomer_training_path",
            target_id=str(result.revision.revision_id),
            request_id=trace_id,
            metadata={
                "reason": reason,
                "rollout_scope": "all_active_learners",
                "synced_enrollment_count": synced_enrollment_count,
            },
        )
        return result

    async def restore_as_draft(
        self,
        *,
        revision_id: str,
        actor: User,
        reason: str,
        trace_id: str | None = None,
        expected_revision_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        source = await self._revisions.revision_by_id(revision_id)
        if (
            source is None
            or source.resource_type != PATH_RESOURCE_TYPE
            or source.logical_id != PATH_LOGICAL_ID
        ):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_REVISION_NOT_FOUND]", "训练路径历史版本不存在。", 404
            )
        restored = await self.save_draft(
            payload=TrainingPathPayload.model_validate(source.payload_json),
            actor=actor,
            reason=reason,
            trace_id=trace_id,
            expected_revision_id=expected_revision_id,
            preserve_runtime_snapshots=True,
        )
        await self._operations.record(
            actor=actor,
            action="newcomer_path.revision_restored",
            target_type="newcomer_training_path",
            target_id=str(restored.revision_id),
            request_id=trace_id,
            metadata={"source_revision_id": revision_id, "reason": reason},
        )
        return restored

    async def list_revisions(self) -> list[SalesTrainerAssetRevision]:
        return await self._revisions.list_revisions(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )

    async def delete_draft(self, *, actor: User, trace_id: str | None = None) -> None:
        working = await self.working_revision()
        if working is None:
            return
        setattr(working, "status", "archived")
        await self._db.flush()
        await self._operations.record(
            actor=actor,
            action="newcomer_path.draft_deleted",
            target_type="newcomer_training_path",
            target_id=str(working.revision_id),
            request_id=trace_id,
        )

    async def _assert_expected_revision(self, expected_revision_id: str | None) -> None:
        if expected_revision_id is None:
            return
        working = await self.working_revision()
        active = await self.active_revision()
        current = working or active
        if current is None or str(current.revision_id) != expected_revision_id:
            raise PathRevisionConflictError()

    async def _collect_issues(
        self, payload: TrainingPathPayload
    ) -> tuple[PathIssue, ...]:
        return (
            *validate_path_graph(payload),
            *await self._resources.validate(payload),
            *await validate_realtime_binding_snapshots(self._db, payload),
        )

    @staticmethod
    def _validation_response(issues: tuple[PathIssue, ...]) -> PathValidationResponse:
        return PathValidationResponse(
            can_publish=not issues,
            issues=[
                PathIssueResponse(
                    code=issue.code,
                    message=issue.message,
                    object_id=issue.object_id,
                    field_path=issue.field_path,
                    severity=issue.severity,
                )
                for issue in issues
            ],
        )


__all__ = [
    "PATH_LOGICAL_ID",
    "PATH_RESOURCE_TYPE",
    "TrainingPathRevisionService",
]

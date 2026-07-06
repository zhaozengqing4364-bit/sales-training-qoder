from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import SalesTrainerAudioScorePrompt
from sales_trainer.schemas import AudioScorePromptUpdate
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.prompt_revision_payloads import (
    PROMPT_RESOURCE_TYPE,
    apply_prompt_revision_payload,
    prompt_change_class,
    prompt_lifecycle_metadata,
    prompt_lifecycle_snapshot,
    prompt_revision_payload_from_update,
)


class PromptRevisionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AudioScorePromptRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def save_future_revision(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        payload: AudioScorePromptUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAudioScorePrompt:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        previous_snapshot = _snapshot_from_revision(active, prompt)
        next_snapshot = prompt_revision_payload_from_update(prompt, payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=PROMPT_RESOURCE_TYPE,
                logical_id=str(prompt.prompt_id),
                payload=next_snapshot,
                actor=actor,
                change_class=prompt_change_class(previous_snapshot, next_snapshot),
                source_revision_id=str(active.revision_id) if active is not None else None,
                reason="save edited audio score prompt revision",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise PromptRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_revision_saved",
            target_type="sales_trainer_audio_score_prompt",
            target_id=str(prompt.prompt_id),
            request_id=trace_id,
            metadata={
                **prompt_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(prompt)
        return prompt

    async def publish_working_revision(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        *,
        actor: User,
    ) -> bool:
        working = await self._revisions.latest_working_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        if working is None:
            return False
        trace_id = get_trace_id()
        previous_snapshot = prompt_lifecycle_snapshot(prompt)
        apply_prompt_revision_payload(
            prompt,
            _payload_dict(working.payload_json),
            actor_id=str(actor.user_id),
            revision_no=int(working.revision_no),
        )
        try:
            result = await self._revisions.publish_working_revision(
                working,
                actor=actor,
                reason="publish edited audio score prompt revision",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise PromptRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        next_snapshot = prompt_lifecycle_snapshot(prompt)
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_revision_published",
            target_type="sales_trainer_audio_score_prompt",
            target_id=str(prompt.prompt_id),
            request_id=trace_id,
            metadata={
                **prompt_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(prompt)
        return True

    async def ensure_initial_published_revision(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        *,
        actor: User,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = prompt_lifecycle_snapshot(prompt)
        try:
            result = await self._revisions.create_published_revision(
                resource_type=PROMPT_RESOURCE_TYPE,
                logical_id=str(prompt.prompt_id),
                payload=next_snapshot,
                actor=actor,
                change_class="scoring_high_risk",
                reason="initial audio score prompt publish",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise PromptRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_published",
            target_type="sales_trainer_audio_score_prompt",
            target_id=str(prompt.prompt_id),
            request_id=trace_id,
            metadata={
                **prompt_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(prompt)

    async def list_revisions(
        self,
        prompt: SalesTrainerAudioScorePrompt,
    ) -> list[dict[str, Any]]:
        active = await self._revisions.active_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        revisions = await self._revisions.list_revisions(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        active_revision_id = str(active.revision_id) if active is not None else None
        return [
            _revision_summary(revision, active_revision_id=active_revision_id)
            for revision in revisions
        ]

    async def preview_rollback(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        *,
        target_revision_id: str,
    ) -> dict[str, Any]:
        target_revision = await self._rollback_target(prompt, target_revision_id)
        active = await self._revisions.active_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        previous_snapshot = _snapshot_from_revision(active, prompt)
        next_snapshot = _payload_dict(target_revision.payload_json)
        return {
            "action": "audio_score_prompt.rollback",
            "permission": "sales_trainer.manage_modules",
            "requires_reason": True,
            "future_only": True,
            "mutates_history": False,
            "target_prompt_id": str(prompt.prompt_id),
            "current_revision_id": str(active.revision_id) if active is not None else None,
            "target_revision": _revision_summary(
                target_revision,
                active_revision_id=str(active.revision_id) if active is not None else None,
            ),
            "changed_fields": prompt_lifecycle_metadata(
                previous_snapshot,
                next_snapshot,
            )["changed_fields"],
            "historical_submissions_changed": False,
            "historical_regrade_required": False,
            "rollback_plan": {
                "apply_endpoint": (
                    f"/api/v1/admin/sales-trainer/audio-score-prompts/"
                    f"{prompt.prompt_id}/rollback"
                ),
                "rollback_endpoint": (
                    f"/api/v1/admin/sales-trainer/audio-score-prompts/"
                    f"{prompt.prompt_id}/rollback/preview"
                ),
                "strategy": "activate_existing_published_revision",
            },
        }

    async def rollback_prompt(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        *,
        target_revision_id: str,
        reason: str,
        actor: User,
    ) -> SalesTrainerAudioScorePrompt:
        if prompt.status == "archived":
            raise PromptRevisionServiceError(
                "[SCORING_PROMPT_ARCHIVED]",
                "已归档录音评分 Prompt 不能回滚。",
            )
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=str(prompt.prompt_id),
        )
        previous_snapshot = _snapshot_from_revision(active, prompt)
        target_revision = await self._rollback_target(prompt, target_revision_id)
        try:
            rollback_result = await self._revisions.rollback_to_revision(
                target_revision,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
                expected_resource_type=PROMPT_RESOURCE_TYPE,
                expected_logical_id=str(prompt.prompt_id),
            )
        except SalesTrainerAssetRevisionError as exc:
            raise PromptRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        next_snapshot = _payload_dict(target_revision.payload_json)
        apply_prompt_revision_payload(
            prompt,
            next_snapshot,
            actor_id=str(actor.user_id),
            revision_no=int(target_revision.revision_no),
        )
        await self._logs.record(
            actor=actor,
            action="audio_score_prompt_revision_rolled_back",
            target_type="sales_trainer_audio_score_prompt",
            target_id=str(prompt.prompt_id),
            request_id=trace_id,
            metadata={
                **prompt_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": rollback_result.previous_revision_id,
                "after_revision_id": target_revision.revision_id,
                "reason": reason,
                "trace_id": trace_id,
                "future_only": True,
                "historical_submissions_changed": False,
            },
        )
        await self._db.commit()
        await self._db.refresh(prompt)
        return prompt

    async def _rollback_target(
        self,
        prompt: SalesTrainerAudioScorePrompt,
        target_revision_id: str,
    ) -> Any:
        target_revision = await self._revisions.revision_by_id(target_revision_id)
        if (
            target_revision is None
            or target_revision.resource_type != PROMPT_RESOURCE_TYPE
            or target_revision.logical_id != str(prompt.prompt_id)
        ):
            raise PromptRevisionServiceError(
                "[SCORING_PROMPT_REVISION_NOT_FOUND]",
                "目标录音评分 Prompt 修订不存在或不属于当前 Prompt。",
                404,
            )
        if target_revision.status != "published":
            raise PromptRevisionServiceError(
                "[SCORING_PROMPT_REVISION_NOT_ROLLBACKABLE]",
                "只能回滚到已发布的录音评分 Prompt 修订。",
                409,
            )
        return target_revision


def _snapshot_from_revision(
    revision: Any | None,
    prompt: SalesTrainerAudioScorePrompt,
) -> dict[str, Any]:
    if revision is None:
        return prompt_lifecycle_snapshot(prompt)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _revision_summary(
    revision: Any,
    *,
    active_revision_id: str | None,
) -> dict[str, Any]:
    payload = _payload_dict(revision.payload_json)
    revision_id = str(revision.revision_id)
    return {
        "revision_id": revision_id,
        "revision_no": int(revision.revision_no),
        "status": str(revision.status),
        "change_class": str(revision.change_class),
        "name": payload.get("name") if isinstance(payload.get("name"), str) else None,
        "purpose": payload.get("purpose")
        if isinstance(payload.get("purpose"), str)
        else None,
        "is_active": revision_id == active_revision_id,
        "is_working": str(revision.status) == "working",
        "source_revision_id": revision.source_revision_id,
        "payload_hash": str(revision.payload_hash),
        "reason": revision.reason,
        "trace_id": revision.trace_id,
        "created_by": revision.created_by,
        "published_by": revision.published_by,
        "created_at": revision.created_at,
        "published_at": revision.published_at,
    }

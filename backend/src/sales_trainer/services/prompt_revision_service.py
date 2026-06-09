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


def _snapshot_from_revision(
    revision: Any | None,
    prompt: SalesTrainerAudioScorePrompt,
) -> dict[str, Any]:
    if revision is None:
        return prompt_lifecycle_snapshot(prompt)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}

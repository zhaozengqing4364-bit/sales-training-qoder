"""Application-root adapters for cross-domain audio governance effects."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from audio_assessment.errors import AudioAssessmentError
from audio_assessment.ports import AudioGovernanceActor
from newcomer_training.activity import ActivityAttemptService
from newcomer_training.application import CommandActor
from newcomer_training.models import NewcomerActivityAttempt


class FoundationAudioAttemptInvalidationAdapter:
    """Invalidate a newcomer attempt without leaking its ORM into audio."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def invalidate(
        self,
        *,
        actor: AudioGovernanceActor,
        attempt_id: str,
        reason: str,
        idempotency_key: str,
    ) -> None:
        attempt = await self._session.get(NewcomerActivityAttempt, attempt_id)
        if attempt is None or attempt.organization_id != actor.organization_id:
            raise AudioAssessmentError(
                "[AUDIO_ATTEMPT_NOT_FOUND]",
                "关联训练尝试不存在或不可访问。",
                404,
            )
        await ActivityAttemptService(self._session).invalidate_attempt(
            actor=CommandActor(
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                capabilities=actor.capabilities,
                trace_id=actor.trace_id,
            ),
            attempt_id=attempt.attempt_id,
            expected_attempt_version=attempt.version,
            reason=reason,
            idempotency_key=idempotency_key,
        )


__all__ = ["FoundationAudioAttemptInvalidationAdapter"]

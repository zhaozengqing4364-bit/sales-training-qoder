"""Application-root adapters for competency mappings used by path publication."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from competency_evidence.application import CompetencyEvidenceService
from competency_evidence.errors import CompetencyEvidenceError
from newcomer_training.errors import NewcomerTrainingError


class FoundationCompetencyMappingAdapter:
    """Translate competency governance failures at the application boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self._service = CompetencyEvidenceService(session)

    async def require_valid(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
    ) -> None:
        del organization_id, path_revision_id, activity_id, activity_type
        try:
            await self._service.require_published_keys(competency_keys)
        except CompetencyEvidenceError as exc:
            raise NewcomerTrainingError(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
            ) from exc

    async def record_published(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
        actor_id: str,
    ) -> None:
        await self._service.publish_activity_mappings(
            organization_id=organization_id,
            path_revision_id=path_revision_id,
            activity_id=activity_id,
            activity_type=activity_type,
            competency_keys=competency_keys,
            actor_id=actor_id,
        )


__all__ = ["FoundationCompetencyMappingAdapter"]

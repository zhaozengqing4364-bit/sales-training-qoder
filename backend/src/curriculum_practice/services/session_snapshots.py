from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from curriculum_practice.models import (
    LearnerProfile,
    PracticeTemplate,
)
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.asset_resolution import (
    merge_curriculum_into_voice_policy_snapshot,
)
from curriculum_practice.services.learner_profiles import DEFAULT_LEARNER_LEVEL
from curriculum_practice.services.practice_templates import published_ref
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.snapshots import (
    RuntimeSnapshotBuildError,
    RuntimeSnapshotService,
)


class CurriculumSessionSnapshotError(ValueError):
    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
    ) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


async def apply_curriculum_snapshot_to_session(
    *,
    db: AsyncSession,
    session: PracticeSession,
    practice_template_id: UUID | None,
    scenario_type_value: str,
    actor_id: str,
) -> None:
    if practice_template_id is None:
        return

    template = await db.get(PracticeTemplate, str(practice_template_id))
    if template is None:
        raise CurriculumSessionSnapshotError(
            "[PRACTICE_TEMPLATE_NOT_FOUND]",
            status_code=404,
        )
    if template.status != "published":
        raise CurriculumSessionSnapshotError(
            "[PRACTICE_TEMPLATE_NOT_PUBLISHED]",
            status_code=400,
        )
    if template.scenario_type != scenario_type_value:
        raise CurriculumSessionSnapshotError(
            "[PRACTICE_TEMPLATE_SCENARIO_TYPE_MISMATCH]",
            status_code=400,
        )

    snapshot_service = RuntimeSnapshotService.from_database(
        db,
        reference_reader=CurriculumAssetReferenceReader(db).read_reference,
        situation_packs=await SituationPackRepository.from_database(db),
    )
    try:
        profile = await db.get(LearnerProfile, actor_id)
        snapshot = await snapshot_service.build_for_session(
            published_ref(template),
            {
                "id": str(session.session_id),
                "scenario_type": scenario_type_value,
            },
            actor_id,
            learner_level=(
                str(profile.effective_level)
                if profile is not None
                else DEFAULT_LEARNER_LEVEL
            ),
        )
    except RuntimeSnapshotBuildError as exc:
        raise CurriculumSessionSnapshotError(
            f"[RUNTIME_SNAPSHOT_{exc.reason_code.upper()}]",
            status_code=400,
            message=str(exc),
        ) from exc

    session.practice_template_id = str(template.template_id)
    session.curriculum_snapshot = snapshot.model_dump(mode="json")
    merge_curriculum_into_voice_policy_snapshot(session, template=template)

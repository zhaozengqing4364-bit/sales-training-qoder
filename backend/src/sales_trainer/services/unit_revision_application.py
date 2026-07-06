from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.services.audit_metadata import unit_lifecycle_snapshot
from sales_trainer.services.unit_revision_payloads import (
    payload_dict,
    unit_question_bindings_from_payload,
)


class UnitRevisionPayloadApplicator:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def apply(
        self,
        unit: SalesTrainerUnit,
        payload: dict[str, Any],
        *,
        actor_id: str,
    ) -> None:
        setattr(unit, "name", str(payload["name"]))
        setattr(unit, "description", payload.get("description"))
        setattr(unit, "config", payload_dict(payload.get("config")))
        setattr(unit, "status", "published")
        setattr(unit, "updated_by", actor_id)
        await self.replace_questions(str(unit.unit_id), payload)

    async def replace_questions(self, unit_id: str, payload: dict[str, Any]) -> None:
        await self._db.execute(
            delete(SalesTrainerUnitQuestion).where(
                SalesTrainerUnitQuestion.unit_id == unit_id
            )
        )
        for item in unit_question_bindings_from_payload(payload):
            self._db.add(
                SalesTrainerUnitQuestion(
                    unit_id=unit_id,
                    question_id=item.question_id,
                    order_index=item.order_index,
                    points=item.points,
                )
            )
        await self._db.flush()

    async def unit_questions(self, unit_id: str) -> list[SalesTrainerUnitQuestion]:
        result = await self._db.execute(
            select(SalesTrainerUnitQuestion)
            .where(SalesTrainerUnitQuestion.unit_id == unit_id)
            .order_by(SalesTrainerUnitQuestion.order_index.asc())
        )
        return list(result.scalars().all())


def snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    unit: SalesTrainerUnit,
    questions: list[SalesTrainerUnitQuestion],
) -> dict[str, Any]:
    if revision is None:
        return unit_lifecycle_snapshot(unit, questions)
    return payload_dict(revision.payload_json)

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.permissions import can_enter_sales_trainer_learning_path


class LearnerUnitAccessError(Exception):
    def __init__(
        self,
        code: str = "[SALES_TRAINER_UNIT_NOT_FOUND]",
        message: str = "训练单元不存在或未开放。",
        status_code: int = 404,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def require_sales_trainer_learner(actor: User) -> None:
    if not can_enter_sales_trainer_learning_path(actor):
        raise LearnerUnitAccessError(
            "[NEWCOMER_LEARNER_ROLE_REQUIRED]",
            "当前账号无权进入新人训练学习路径。",
            403,
        )


async def require_learner_active_path_unit_access(
    db: AsyncSession,
    *,
    actor: User,
    unit_id: str,
) -> None:
    require_sales_trainer_learner(actor)

    from sales_trainer.services.training_journey_service import (
        TrainingJourneyError,
        TrainingJourneyService,
    )

    try:
        journey = await TrainingJourneyService(db).get_learner_journey(
            str(actor.user_id),
            viewer=actor,
        )
    except TrainingJourneyError as exc:
        if exc.code == "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
            raise LearnerUnitAccessError() from exc
        raise LearnerUnitAccessError(
            exc.code,
            exc.message,
            exc.status_code,
        ) from exc
    for module in journey.get("modules") or []:
        if not isinstance(module, dict):
            continue
        target_ids = {
            str(value)
            for value in module.get("target_unit_ids") or []
            if str(value)
        }
        target_unit_id = str(module.get("target_unit_id") or "")
        if target_unit_id:
            target_ids.add(target_unit_id)
        if unit_id not in target_ids:
            continue
        if bool(module.get("locked")):
            raise LearnerUnitAccessError()
        return
    raise LearnerUnitAccessError()


async def require_learner_active_path_module_access(
    db: AsyncSession,
    *,
    actor: User,
    module_key: str,
) -> None:
    require_sales_trainer_learner(actor)

    from sales_trainer.services.training_journey_service import (
        TrainingJourneyError,
        TrainingJourneyService,
    )

    try:
        journey = await TrainingJourneyService(db).get_learner_journey(
            str(actor.user_id),
            viewer=actor,
        )
    except TrainingJourneyError as exc:
        if exc.code == "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
            raise LearnerUnitAccessError() from exc
        raise LearnerUnitAccessError(
            exc.code,
            exc.message,
            exc.status_code,
        ) from exc
    for module in journey.get("modules") or []:
        if not isinstance(module, dict):
            continue
        if str(module.get("module_key") or "") != module_key:
            continue
        diagnostics = module.get("diagnostics") or []
        diagnostic_codes = {
            str(item.get("code") or "")
            for item in diagnostics
            if isinstance(item, dict)
        }
        if (
            module.get("enabled") is False
            or bool(module.get("locked"))
            or "[NEWCOMER_LEARNER_LEVEL_NOT_ALLOWED]" in diagnostic_codes
        ):
            raise LearnerUnitAccessError()
        return
    raise LearnerUnitAccessError()


async def require_learner_learning_topic_access(
    db: AsyncSession,
    *,
    actor: User,
    topic_key: str,
) -> None:
    require_sales_trainer_learner(actor)

    from sales_trainer.services.training_journey_service import (
        TrainingJourneyError,
        TrainingJourneyService,
    )

    try:
        journey = await TrainingJourneyService(db).get_learner_journey(
            str(actor.user_id),
            viewer=actor,
        )
    except TrainingJourneyError as exc:
        if exc.code == "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
            raise LearnerUnitAccessError() from exc
        raise LearnerUnitAccessError(
            exc.code,
            exc.message,
            exc.status_code,
        ) from exc
    for topic in journey.get("learning_topics") or []:
        if not isinstance(topic, dict):
            continue
        if str(topic.get("topic_key") or "") != topic_key:
            continue
        if bool(topic.get("blocks_next")):
            raise LearnerUnitAccessError()
        return
    raise LearnerUnitAccessError()

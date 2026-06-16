from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.schemas import (
    LearningContentBindingImpactResponse,
    LearningContentBindingUnitImpact,
    LearningContentPathBindingImpact,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevision,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_learning_service import (
    BUSINESS_SKILLS_MODULE_KEY,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    payload_from_revision,
)

ARTICLE_BINDING_ENTRY = "/admin/sales-trainer/articles"
PATH_CONFIG_ENTRY = "/admin/sales-trainer/paths"
QUESTION_DRAFT_ENTRY = "/admin/sales-trainer/questions/drafts"


class LearningContentBindingImpactServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LearningContentBindingImpactService:
    def __init__(self, db: AsyncSession) -> None:
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def get_impact(
        self,
        learning_content_id: str,
    ) -> LearningContentBindingImpactResponse:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active_bindings = _bindings_from_revision(
            active,
            learning_content_id=learning_content_id,
            source="active_revision",
            learner_effective=True,
        )
        working_bindings = _bindings_from_revision(
            working,
            learning_content_id=learning_content_id,
            source="working_revision",
            learner_effective=False,
        )
        has_active = bool(active_bindings)
        has_working = bool(working_bindings)
        is_business_skills = any(
            binding.module_key == BUSINESS_SKILLS_MODULE_KEY
            for binding in [*active_bindings, *working_bindings]
        )
        can_archive = not has_active and not has_working
        block_reason = None
        if not can_archive:
            block_reason = (
                "该学习内容正在被新人训练路径引用。请先到商务技巧文章或路径配置中"
                "替换绑定并发布路径配置，再归档学习内容。"
            )
        return LearningContentBindingImpactResponse(
            learning_content_id=learning_content_id,
            active_bindings=active_bindings,
            working_bindings=working_bindings,
            has_active_binding=has_active,
            has_working_binding=has_working,
            is_bound_to_business_skills=is_business_skills,
            can_archive=can_archive,
            archive_block_reason=block_reason,
            management_entries={
                "article_binding": ARTICLE_BINDING_ENTRY,
                "path_config": PATH_CONFIG_ENTRY,
                "question_drafts": QUESTION_DRAFT_ENTRY,
            },
        )


def _bindings_from_revision(
    revision: SalesTrainerAssetRevision | None,
    *,
    learning_content_id: str,
    source: Literal["active_revision", "working_revision"],
    learner_effective: bool,
) -> list[LearningContentPathBindingImpact]:
    if revision is None:
        return []
    try:
        payload = payload_from_revision(revision)
    except Exception as exc:  # noqa: BLE001 - invalid persisted config must be surfaced.
        raise LearningContentBindingImpactServiceError(
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            "新人训练路径配置非法，无法计算学习内容绑定影响。",
            500,
        ) from exc
    bindings: list[LearningContentPathBindingImpact] = []
    for module in sorted(payload.modules, key=lambda item: item.order_index):
        if (
            module.module_type != "article_exam"
            or module.learning_content_id != learning_content_id
        ):
            continue
        unit_impacts = _unit_impacts(module)
        bindings.append(
            LearningContentPathBindingImpact(
                source=source,
                path_key=payload.path_key,
                module_key=module.module_key,
                module_title=module.title,
                revision_id=str(revision.revision_id),
                revision_no=revision.revision_no,
                learner_effective=learner_effective,
                learning_units=unit_impacts,
                impacted_chapter_orders=_impacted_chapter_orders(unit_impacts),
            )
        )
    return bindings


def _unit_impacts(
    module: NewcomerPathModuleConfig,
) -> list[LearningContentBindingUnitImpact]:
    return [
        LearningContentBindingUnitImpact(
            unit_key=unit.unit_key,
            title=unit.title,
            source_chapter_orders=list(unit.source_chapter_orders),
            ai_coach_remediation_chapter_orders=list(
                unit.ai_coach_remediation_chapter_orders
            ),
            capability_keys=list(unit.capability_keys),
            require_quiz=unit.require_quiz,
            require_ai_coach=unit.require_ai_coach,
        )
        for unit in sorted(module.learning_units, key=lambda item: item.order_index)
    ]


def _impacted_chapter_orders(
    units: list[LearningContentBindingUnitImpact],
) -> list[int]:
    orders: set[int] = set()
    for unit in units:
        orders.update(unit.source_chapter_orders)
        orders.update(unit.ai_coach_remediation_chapter_orders)
    return sorted(orders)

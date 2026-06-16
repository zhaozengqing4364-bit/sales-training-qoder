from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteLearningChapterResponse,
    BusinessEtiquetteLearningUnitProgressResponse,
    BusinessEtiquetteLearningUnitResponse,
    BusinessEtiquetteLearningUnitsResponse,
    NewcomerArticleBinding,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)
from sales_trainer.services.business_etiquette_capability_service import (
    BusinessEtiquetteCapabilityService,
    BusinessEtiquetteCapabilityServiceError,
)
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

BUSINESS_SKILLS_MODULE_KEY = "business_skills"


class BusinessEtiquetteLearningServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessEtiquetteLearningService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_learning_units(
        self,
        *,
        user_id: str,
        module_key: str = BUSINESS_SKILLS_MODULE_KEY,
    ) -> BusinessEtiquetteLearningUnitsResponse:
        try:
            path_response = await SalesTrainerPathConfigService(self._db).get_config()
        except SalesTrainerPathConfigError as exc:
            raise BusinessEtiquetteLearningServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        path_payload = NewcomerPathConfigPayload.model_validate(path_response["path"])
        module = _module_by_key(path_payload, module_key)
        if module is None or module.module_type != "article_exam":
            raise BusinessEtiquetteLearningServiceError(
                "[BUSINESS_ETIQUETTE_MODULE_CONFIG_MISSING]",
                "商务礼仪学习模块配置不存在。",
                404,
            )
        if not module.enabled:
            raise BusinessEtiquetteLearningServiceError(
                "[BUSINESS_ETIQUETTE_MODULE_DISABLED]",
                module.disabled_reason or "商务礼仪学习模块已停用。",
                409,
            )
        if not module.learning_units:
            raise BusinessEtiquetteLearningServiceError(
                "[BUSINESS_ETIQUETTE_LEARNING_UNITS_MISSING]",
                "商务礼仪小单元配置缺失，请管理员在路径配置中心补齐。",
                409,
            )

        try:
            article = await ArticleBindingService(self._db).resolve_module_article(
                NewcomerArticleBinding(module_key=module_key)
            )
        except ArticleBindingServiceError as exc:
            raise BusinessEtiquetteLearningServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

        article_chapters = _article_chapters(article)
        progress = await LearningProgressService(self._db).progress_for_user(
            user_id=user_id,
            content_id=str(article["learning_content_id"]),
            chapters=[
                type("Chapter", (), {"chapter_id": chapter["chapter_id"]})()
                for chapter in article_chapters
            ],
        )
        if not progress.is_success or progress.value is None:
            raise BusinessEtiquetteLearningServiceError(
                "[BUSINESS_ETIQUETTE_PROGRESS_UNAVAILABLE]",
                "读取商务礼仪阅读进度失败。",
                500,
            )
        completed_ids = set(progress.value.completed_chapter_ids)
        chapters_by_order = {
            int(chapter["order_index"]): chapter for chapter in article_chapters
        }
        try:
            capabilities_by_key = (
                await BusinessEtiquetteCapabilityService(
                    self._db
                ).published_capabilities_by_key()
            )
        except BusinessEtiquetteCapabilityServiceError as exc:
            raise BusinessEtiquetteLearningServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        units = [
            _unit_response(
                unit_config,
                chapters_by_order,
                completed_ids,
                capabilities_by_key,
            )
            for unit_config in sorted(
                module.learning_units,
                key=lambda item: item.order_index,
            )
        ]
        return BusinessEtiquetteLearningUnitsResponse(
            module_key=module_key,
            learning_content_id=str(article["learning_content_id"]),
            path_revision_id=path_response["active_revision_id"],
            path_revision_no=path_response["active_revision_no"],
            units=units,
        )


def _module_by_key(
    payload: NewcomerPathConfigPayload,
    module_key: str,
) -> NewcomerPathModuleConfig | None:
    for module in payload.modules:
        if module.module_key == module_key:
            return module
    return None


def _article_chapters(article: dict[str, object]) -> list[dict[str, Any]]:
    chapters = article.get("chapters")
    if not isinstance(chapters, list):
        return []
    return [
        chapter
        for chapter in chapters
        if isinstance(chapter, dict)
        and isinstance(chapter.get("chapter_id"), str)
        and isinstance(chapter.get("title"), str)
        and isinstance(chapter.get("order_index"), int)
    ]


def _unit_response(
    unit_config: Any,
    chapters_by_order: dict[int, dict[str, Any]],
    completed_ids: set[str],
    capabilities_by_key: dict[str, BusinessEtiquetteCapabilityConfig],
) -> BusinessEtiquetteLearningUnitResponse:
    chapters = [
        chapters_by_order[order]
        for order in unit_config.source_chapter_orders
        if order in chapters_by_order
    ]
    if unit_config.enabled and not chapters:
        raise BusinessEtiquetteLearningServiceError(
            "[BUSINESS_ETIQUETTE_UNIT_CHAPTERS_MISSING]",
            f"商务礼仪小单元“{unit_config.title}”未绑定有效原文章节。",
            409,
        )
    chapter_responses = [
        BusinessEtiquetteLearningChapterResponse(
            chapter_id=str(chapter["chapter_id"]),
            title=str(chapter["title"]),
            order_index=int(chapter["order_index"]),
            completed=str(chapter["chapter_id"]) in completed_ids,
        )
        for chapter in chapters
    ]
    completed_chapter_ids = [
        chapter.chapter_id for chapter in chapter_responses if chapter.completed
    ]
    return BusinessEtiquetteLearningUnitResponse(
        unit_key=unit_config.unit_key,
        title=unit_config.title,
        description=unit_config.description,
        order_index=unit_config.order_index,
        enabled=unit_config.enabled,
        source_chapter_orders=unit_config.source_chapter_orders,
        capability_keys=unit_config.capability_keys,
        unlock_after_unit_keys=unit_config.unlock_after_unit_keys,
        require_reading=unit_config.require_reading,
        require_quiz=unit_config.require_quiz,
        require_ai_coach=unit_config.require_ai_coach,
        ai_coach_required_capability_keys=unit_config.ai_coach_required_capability_keys,
        ai_coach_pass_mastery_level_key=unit_config.ai_coach_pass_mastery_level_key,
        ai_coach_ready_mastery_level_key=unit_config.ai_coach_ready_mastery_level_key,
        ai_coach_max_remediation_attempts=(
            unit_config.ai_coach_max_remediation_attempts
        ),
        ai_coach_manual_review_after_max_attempts=(
            unit_config.ai_coach_manual_review_after_max_attempts
        ),
        ai_coach_block_next_until_passed=(
            unit_config.ai_coach_block_next_until_passed
        ),
        ai_coach_remediation_chapter_orders=(
            unit_config.ai_coach_remediation_chapter_orders
        ),
        quiz_question_count=unit_config.quiz_question_count,
        quiz_pass_threshold=unit_config.quiz_pass_threshold,
        quiz_allow_retake=unit_config.quiz_allow_retake,
        quiz_max_attempts=unit_config.quiz_max_attempts,
        quiz_question_type_weights=unit_config.quiz_question_type_weights,
        allow_skip_reading=unit_config.allow_skip_reading,
        block_next_until_complete=unit_config.block_next_until_complete,
        empty_state_message=unit_config.empty_state_message,
        capabilities=[
            capabilities_by_key[key]
            for key in unit_config.capability_keys
            if key in capabilities_by_key
        ],
        chapters=chapter_responses,
        progress=BusinessEtiquetteLearningUnitProgressResponse(
            completed_chapter_ids=completed_chapter_ids,
            total_chapters=len(chapter_responses),
            completed_chapters=len(completed_chapter_ids),
            is_completed=(
                bool(chapter_responses)
                and len(completed_chapter_ids) == len(chapter_responses)
            ),
        ),
    )

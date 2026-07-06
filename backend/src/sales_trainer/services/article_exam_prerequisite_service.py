from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerExamPaper
from sales_trainer.schemas import NewcomerArticleBinding
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)
from sales_trainer.services.curriculum_practice_adapter import (
    LearningChapterSummary,
    LearningProgressAdapter,
    list_learning_chapters,
)
from sales_trainer.services.exam_paper_config import ExamPaperServiceError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


@dataclass(frozen=True, slots=True)
class ArticleExamBinding:
    module_key: str
    learning_content_id: str | None


class ArticleExamPrerequisiteService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def require_article_completed(
        self,
        paper: SalesTrainerExamPaper,
        *,
        actor: User,
    ) -> None:
        binding = await self._article_exam_binding_for_paper(paper)
        if binding is None:
            return

        try:
            article = await ArticleBindingService(self._db).resolve_module_article(
                NewcomerArticleBinding(
                    module_key=binding.module_key,
                    learning_content_id=binding.learning_content_id,
                )
            )
        except ArticleBindingServiceError as exc:
            raise ExamPaperServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

        content_id = str(article["learning_content_id"])
        chapters = await self._chapters(content_id)
        progress_result = await LearningProgressAdapter(self._db).progress_for_user(
            user_id=str(actor.user_id),
            content_id=content_id,
            chapters=chapters,
        )
        if not progress_result.is_success or progress_result.value is None:
            raise ExamPaperServiceError(
                "[NEWCOMER_MODULE_PROGRESS_ERROR]",
                "读取阅读进度失败。",
                500,
            )
        if not progress_result.value.is_completed:
            raise ExamPaperServiceError(
                "[NEWCOMER_ARTICLE_PROGRESS_REQUIRED]",
                "请先完成当前商务技巧文章阅读，再提交考试。",
                403,
            )

    async def _article_exam_binding_for_paper(
        self,
        paper: SalesTrainerExamPaper,
    ) -> ArticleExamBinding | None:
        projection = await SalesTrainerPathConfigService(self._db).active_projection()
        if projection is None:
            return None
        for item in projection.items:
            module = item.path_config
            if (
                module.enabled
                and module.module_type == "article_exam"
                and (
                    module.exam_paper_id == str(paper.paper_id)
                    or module.target_unit_id == str(paper.unit_id)
                )
            ):
                module_key = module.module_key
                if not isinstance(module_key, str) or not module_key:
                    continue
                return ArticleExamBinding(
                    module_key=module_key,
                    learning_content_id=module.learning_content_id,
                )
        return None

    async def _chapters(self, content_id: str) -> list[LearningChapterSummary]:
        return await list_learning_chapters(self._db, content_id)

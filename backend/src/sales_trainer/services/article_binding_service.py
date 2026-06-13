from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.schemas import (
    NewcomerArticleBinding,
    NewcomerPathConfigPayload,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.curriculum_practice_adapter import (
    LearningChapterSummary,
    get_learning_content,
    list_learning_chapters,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    SalesTrainerPathConfigError,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

DEFAULT_ARTICLE_BINDING_REASON = "更新新人训练路径商务技巧学习文章绑定"


class ArticleBindingServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ArticleBindingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)

    async def resolve_module_article(
        self,
        binding: NewcomerArticleBinding,
    ) -> dict[str, object]:
        learning_content_id = binding.learning_content_id
        if learning_content_id is None:
            learning_content_id = await self._configured_learning_content_id(
                binding.module_key
            )
        if learning_content_id is None:
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_NOT_PUBLISHED]",
                "商务技巧文章未绑定已发布内容。",
                404,
            )
        content = await get_learning_content(self._db, learning_content_id)
        if content is None:
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_NOT_FOUND]",
                "LearningContent 不存在。",
                404,
            )
        if content.status != "published":
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_NOT_PUBLISHED]",
                "LearningContent 未发布或已归档。",
                404,
            )
        chapters = await self._chapters(content.learning_content_id)
        if not chapters:
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_CHAPTERS_MISSING]",
                "商务技巧文章还没有学习章节。",
                409,
            )
        return {
            "module_key": binding.module_key,
            "learning_content_id": content.learning_content_id,
            "title": content.title,
            "summary": content.summary,
            "owner": content.owner,
            "source": content.source,
            "chapters": [
                {
                    "chapter_id": chapter.chapter_id,
                    "title": chapter.title,
                    "content": chapter.content,
                    "order_index": chapter.order_index,
                }
                for chapter in chapters
            ],
        }

    async def _chapters(self, content_id: str) -> list[LearningChapterSummary]:
        return await list_learning_chapters(self._db, content_id)

    async def bind_module_article(
        self,
        binding: NewcomerArticleBinding,
        *,
        path_key: str,
        actor: User,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> NewcomerArticleBinding:
        if path_key != NEWCOMER_PATH_LOGICAL_ID:
            raise ArticleBindingServiceError(
                "[NEWCOMER_PATH_CONFIG_ALIAS_READ_ONLY]",
                "新人训练路径兼容路径标识只允许读取，请在新人训练路径配置中心保存当前路径配置。",
                409,
            )
        if binding.learning_content_id is None:
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_NOT_PUBLISHED]",
                "商务技巧文章必须绑定已发布 LearningContent。",
                404,
            )
        content = await get_learning_content(self._db, binding.learning_content_id)
        if content is None:
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_NOT_FOUND]",
                "LearningContent 不存在。",
                404,
            )
        if content.status != "published":
            raise ArticleBindingServiceError(
                "[LEARNING_CONTENT_NOT_PUBLISHED]",
                "LearningContent 未发布或已归档。",
                404,
            )
        path_service = SalesTrainerPathConfigService(self._db)
        path_response = await path_service.get_config()
        path_payload = NewcomerPathConfigPayload.model_validate(path_response["path"])
        module = _module_by_key(path_payload, binding.module_key)
        if module is None or module.module_type != "article_exam":
            raise ArticleBindingServiceError(
                "[NEWCOMER_MODULE_CONFIG_MISSING]",
                "新人训练路径模块配置不存在。",
                404,
            )
        previous_content_id = module.learning_content_id
        next_payload = _replace_module_binding(
            path_payload,
            module_key=binding.module_key,
            learning_content_id=binding.learning_content_id,
        )
        audit_reason = reason or DEFAULT_ARTICLE_BINDING_REASON
        try:
            revision = await path_service.save_config(
                NewcomerPathConfigSaveRequest(
                    path_key=next_payload.path_key,
                    title=next_payload.title,
                    goal_title=next_payload.goal_title,
                    description=next_payload.description,
                    enabled=next_payload.enabled,
                    modules=next_payload.modules,
                    reason=audit_reason,
                ),
                actor=actor,
                trace_id=trace_id,
            )
        except SalesTrainerPathConfigError as exc:
            raise ArticleBindingServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="newcomer_path_config.article_binding_saved",
            target_type="newcomer_path_config",
            target_id=NEWCOMER_PATH_LOGICAL_ID,
            request_id=trace_id,
            metadata={
                "path_key": path_key,
                "module_key": binding.module_key,
                "previous_learning_content_id": previous_content_id,
                "learning_content_id": binding.learning_content_id,
                "before_revision_id": path_response["active_revision_id"],
                "after_revision_id": str(revision.revision_id),
                "reason": audit_reason,
                "trace_id": trace_id,
                "change_class": "binding",
                "impact_scope": "future_learners_only",
            },
        )
        await self._db.commit()
        return NewcomerArticleBinding(
            module_key=binding.module_key,
            learning_content_id=binding.learning_content_id,
            path_key=path_key,
            active_revision_id=path_response["active_revision_id"],
            active_revision_no=path_response["active_revision_no"],
            working_revision_id=str(revision.revision_id),
            working_revision_no=revision.revision_no,
            has_unpublished_revision=True,
            impact_scope="future_learners_only",
        )

    async def _configured_learning_content_id(self, module_key: str) -> str | None:
        path_response = await SalesTrainerPathConfigService(self._db).get_config()
        path_payload = NewcomerPathConfigPayload.model_validate(path_response["path"])
        module = _module_by_key(path_payload, module_key)
        if module is None or not module.enabled or module.module_type != "article_exam":
            return None
        return module.learning_content_id


def _module_by_key(
    payload: NewcomerPathConfigPayload,
    module_key: str,
) -> NewcomerPathModuleConfig | None:
    for module in payload.modules:
        if module.module_key == module_key:
            return module
    return None


def _replace_module_binding(
    payload: NewcomerPathConfigPayload,
    *,
    module_key: str,
    learning_content_id: str,
) -> NewcomerPathConfigPayload:
    modules = [
        _replace_learning_content_id(module, learning_content_id)
        if module.module_key == module_key
        else module
        for module in payload.modules
    ]
    return NewcomerPathConfigPayload(
        path_key=payload.path_key,
        title=payload.title,
        goal_title=payload.goal_title,
        description=payload.description,
        enabled=payload.enabled,
        modules=modules,
    )


def _replace_learning_content_id(
    module: NewcomerPathModuleConfig,
    learning_content_id: str,
) -> NewcomerPathModuleConfig:
    data: dict[str, Any] = module.model_dump(mode="json")
    data["learning_content_id"] = learning_content_id
    return NewcomerPathModuleConfig.model_validate(data)

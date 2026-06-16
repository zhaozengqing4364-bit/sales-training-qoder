from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachChatMessage
from sales_trainer.ai_coach_chat_schemas import AiCoachChatResponseInternalV1
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    AiCoachConfig,
    NewcomerArticleBinding,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError
from sales_trainer.services.ai_coach_chat_generation import AiCoachChatGenerator
from sales_trainer.services.ai_coach_chat_generation_streaming import (
    AiCoachGenerationDeltaHandler,
)
from sales_trainer.services.article_binding_service import (
    ArticleBindingService,
    ArticleBindingServiceError,
)


class AiCoachChatRuntimeError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachChatRuntime:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def module_ai_coach_config(
        self,
        raw_path: object,
        module_key: str,
    ) -> tuple[NewcomerPathModuleConfig, AiCoachConfig]:
        try:
            payload = NewcomerPathConfigPayload.model_validate(raw_path)
        except ValidationError as exc:
            raise AiCoachChatRuntimeError(
                "[AI_COACH_NOT_CONFIGURED]",
                "新人训练路径配置不可用。",
                409,
            ) from exc
        for module in payload.modules:
            if module.module_key == module_key:
                return module, module.ai_coach or AiCoachConfig()
        raise AiCoachChatRuntimeError(
            "[AI_COACH_NOT_CONFIGURED]",
            "商务技巧 AI 教练模块不存在。",
            404,
        )

    def validate_chat_config(self, config: AiCoachConfig) -> None:
        if not config.enabled:
            raise AiCoachChatRuntimeError(
                "[AI_COACH_DISABLED]",
                "该模块未启用 AI 教练。",
                409,
            )
        if not getattr(config, "chat_enabled", True):
            raise AiCoachChatRuntimeError(
                "[AI_COACH_CHAT_DISABLED]",
                "该模块未启用对话式 AI 教练。",
                409,
            )
        if not config.prompt_template_id:
            raise AiCoachChatRuntimeError(
                "[AI_COACH_NOT_CONFIGURED]",
                "AI 教练未绑定生成 Prompt。",
                409,
            )

    async def article_snapshot(
        self,
        module: NewcomerPathModuleConfig,
    ) -> dict[str, object]:
        if not module.learning_content_id:
            return {}
        try:
            return await ArticleBindingService(self._db).resolve_module_article(
                NewcomerArticleBinding(
                    module_key=module.module_key,
                    learning_content_id=module.learning_content_id,
                )
            )
        except ArticleBindingServiceError:
            return {}

    def config_from_session(self, session: SalesTrainerAiCoachSession) -> AiCoachConfig:
        try:
            return AiCoachConfig.model_validate(session.config_snapshot or {})
        except ValidationError as exc:
            raise AiCoachChatRuntimeError(
                "[AI_COACH_PROMPT_CONFIG_INVALID]",
                "AI 教练配置快照非法。",
                409,
            ) from exc

    async def generate_chat_response(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        user_message: str,
        history: list[SalesTrainerAiCoachChatMessage],
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> AiCoachChatResponseInternalV1:
        try:
            return await AiCoachChatGenerator(self._db).generate(
                session=session,
                config=config,
                user_message=user_message,
                history=history,
                on_generation_delta=on_generation_delta,
            )
        except AiCoachChatGenerationError as exc:
            raise AiCoachChatRuntimeError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

    @staticmethod
    def welcome_message(config: AiCoachConfig) -> str:
        value = getattr(config, "chat_welcome_message", None)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "你好，我是商务技巧 AI 教练。你可以直接说想练什么，我会把练习卡片放在对话里。"

    @staticmethod
    def allowed_ui_event_types(config: AiCoachConfig) -> tuple[str, ...]:
        return AiCoachChatGenerator.allowed_ui_event_types(config)

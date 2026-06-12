from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from prompt_templates.compiled_contract import CompiledPromptContract
from prompt_templates.service import PromptTemplateService
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachChatMessage
from sales_trainer.ai_coach_chat_schemas import AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import AiCoachConfig
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError
from sales_trainer.services.ai_coach_chat_generation_parser import (
    AiCoachChatResponseParser,
)
from sales_trainer.services.ai_coach_session_service import AiCoachSessionService
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_AUDIT_HISTORY_UNAVAILABLE,
    RESULT_OK,
    PromptTemplateRevisionResolver,
    PromptTemplateRevisionResolverError,
)


class AiCoachChatPromptCompiler:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compile(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        user_message: str,
        history: list[SalesTrainerAiCoachChatMessage],
    ) -> CompiledPromptContract:
        resolver = PromptTemplateRevisionResolver(self._db)
        try:
            resolution = await resolver.resolve(
                template_id=str(session.prompt_template_id),
                prompt_revision_id=session.prompt_revision_id,
            )
        except PromptTemplateRevisionResolverError as exc:
            raise self._resolver_error(exc) from exc
        if resolution.status != RESULT_OK:
            code = (
                "[AI_COACH_PROMPT_REVISION_AUDIT_MISSING]"
                if resolution.status == RESULT_AUDIT_HISTORY_UNAVAILABLE
                else "[AI_COACH_PROMPT_REVISION_FALLBACK]"
            )
            raise AiCoachChatGenerationError(
                code,
                "AI 教练 Prompt revision 不可用。",
                409,
            )
        compile_result = PromptTemplateService(
            self._db
        ).compile_runtime_prompt_contract(
            template=resolution.snapshot.template,
            variables=self._generation_variables(session, config, user_message, history),
            runtime_consumer="ai_coach.chat.generate",
            system_message=self.system_message(config),
            model_config=None,
        )
        if not compile_result.is_success or compile_result.value is None:
            raise AiCoachChatGenerationError(
                f"[AI_COACH_PROMPT_COMPILE_FAILED:{compile_result.fallback or 'unknown'}]",
                "无法编译 AI 教练 Chat Prompt。",
                502,
            )
        return compile_result.value

    def _generation_variables(
        self,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        user_message: str,
        history: list[SalesTrainerAiCoachChatMessage],
    ) -> dict[str, Any]:
        article = session.article_snapshot or {}
        chapters = article.get("chapters") if isinstance(article, dict) else []
        return {
            "module_key": session.module_key,
            "user_message": user_message,
            "history": [
                {"role": message.role, "content": message.content}
                for message in history
            ],
            "article_title": article.get("title") if isinstance(article, dict) else "",
            "article_summary": article.get("summary") if isinstance(article, dict) else "",
            "chapter_titles": self.chapter_titles(chapters),
            "allowed_interaction_types": list(config.allowed_interaction_types),
            "allowed_ui_event_types": list(
                AiCoachChatResponseParser.allowed_ui_event_types(config)
            ),
            "max_cards_per_message": int(config.max_cards_per_message),
            "turn_number": len(history) + 1,
            "previous_turns": [],
            "coach_mode": config.coach_mode,
            "min_turns": config.min_turns,
            "max_turns": config.max_turns,
            "mastery_threshold": config.mastery_threshold,
            "next_action": "",
            "action_reason": "",
            "coach_state": {},
            "score_result": {},
            "answered_interaction_snapshot": {},
            "user_answer_payload": {},
            "current_focus": None,
            "difficulty": "",
        }

    @staticmethod
    def system_message(config: AiCoachConfig) -> str:
        allowed_ui = ", ".join(AiCoachChatResponseParser.allowed_ui_event_types(config))
        return (
            "你是商务技巧 AI 教练。只能输出 JSON，不要输出 Markdown。"
            f"schema_version 必须是 {AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION}。"
            f"ui_events 只能使用这些 type: {allowed_ui}。"
            "quiz_card.payload.interaction 必须满足 ai_coach_interaction_v1，"
            "所有字段类型必须严格匹配示例；source_evidence 必须是数组或 null。"
            "不得输出 HTML、JSX、CSS、脚本或任意组件树。"
        )

    @staticmethod
    def chapter_titles(chapters: object) -> list[str]:
        if not isinstance(chapters, list):
            return []
        titles: list[str] = []
        for chapter in chapters:
            if isinstance(chapter, dict) and isinstance(chapter.get("title"), str):
                titles.append(str(chapter["title"]))
        return titles

    @staticmethod
    def _resolver_error(
        exc: PromptTemplateRevisionResolverError,
    ) -> AiCoachChatGenerationError:
        return AiCoachChatGenerationError(
            AiCoachSessionService._prompt_resolver_public_code(exc),
            exc.message,
            409,
        )

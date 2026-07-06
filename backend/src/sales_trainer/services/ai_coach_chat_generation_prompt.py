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
from sales_trainer.services.ai_coach_model_config import (
    AiCoachModelConfigError,
    model_config_contract_payload,
    resolve_ai_coach_llm_model_config_from_db,
)
from sales_trainer.services.ai_coach_session_service import AiCoachSessionService
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_AUDIT_HISTORY_UNAVAILABLE,
    RESULT_OK,
    PromptTemplateRevisionResolver,
    PromptTemplateRevisionResolverError,
)

_MODEL_CONFIG_UNSET = object()


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
        model_config: object | None = _MODEL_CONFIG_UNSET,
    ) -> CompiledPromptContract:
        resolver = PromptTemplateRevisionResolver(self._db)
        try:
            resolution = await resolver.resolve(
                template_id=str(session.prompt_template_id),
                prompt_revision_id=(
                    str(session.prompt_revision_id)
                    if session.prompt_revision_id is not None
                    else None
                ),
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
        if model_config is _MODEL_CONFIG_UNSET:
            try:
                model_config = await resolve_ai_coach_llm_model_config_from_db(
                    self._db,
                    config.generation_model,
                )
            except AiCoachModelConfigError as exc:
                raise AiCoachChatGenerationError(exc.code, exc.message, 409) from exc
        compile_result = PromptTemplateService(self._db).compile_runtime_prompt_contract(
            template=resolution.snapshot.template,
            variables=self._generation_variables(session, config, user_message, history),
            runtime_consumer="ai_coach.chat.generate",
            system_message=self.system_message(config),
            model_config=model_config_contract_payload(model_config),
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
        article: dict[str, Any] = (
            dict(session.article_snapshot)
            if isinstance(session.article_snapshot, dict)
            else {}
        )
        chapters = article.get("chapters") if isinstance(article, dict) else []
        raw_path_config = getattr(session, "path_config_snapshot", None)
        path_config = (
            raw_path_config
            if isinstance(raw_path_config, dict)
            else {}
        )
        learning_units = self.business_etiquette_learning_units(path_config)
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
            "business_etiquette_learning_units": learning_units,
            "business_etiquette_capability_keys": self.capability_keys(
                learning_units
            ),
            "allowed_interaction_types": list(config.allowed_interaction_types),
            "allowed_training_card_types": list(
                self.compatible_training_card_types(config)
            ),
            "allowed_ui_event_types": list(
                AiCoachChatResponseParser.allowed_ui_event_types(config)
            ),
            "max_cards_per_message": int(config.max_cards_per_message),
            "training_card_contract": self.training_card_contract(config),
            "feedback_schema": self.feedback_schema(),
            "turn_number": len(history) + 1,
            "previous_turns": [],
            "coach_mode": config.coach_mode,
            "min_turns": config.min_turns,
            "max_turns": config.max_turns,
            "mastery_threshold": config.mastery_threshold,
            "next_action": "",
            "action_reason": "",
            "coach_state": (
                getattr(session, "coach_state", None)
                if isinstance(getattr(session, "coach_state", None), dict)
                else {}
            ),
            "score_result": {},
            "answered_interaction_snapshot": {},
            "user_answer_payload": {},
            "current_focus": None,
            "difficulty": "",
        }

    @staticmethod
    def system_message(config: AiCoachConfig) -> str:
        allowed_ui = ", ".join(AiCoachChatResponseParser.allowed_ui_event_types(config))
        allowed_cards = ", ".join(
            AiCoachChatPromptCompiler.compatible_training_card_types(config)
        )
        return (
            "你是商务技巧 AI 教练，不是出题器。你的首要任务是像教练一样先对话、解释、追问，"
            "只有当当前训练确实需要验证或刻意练习时，才把 quiz_card 当作工具调用结果生成。"
            "只能输出 JSON，不要输出 Markdown。"
            f"schema_version 必须是 {AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION}。"
            f"ui_events 只能使用这些 type: {allowed_ui}。"
            f"quiz_card.payload.interaction.training_card_type 只能使用这些值: {allowed_cards}。"
            "每轮最多生成 1 张 quiz_card；普通聊天、讲解、追问时可以不生成 quiz_card。"
            "assistant_text 必须先自然回应学员，说明你为什么聊天、追问或调用练习卡。"
            "quiz_card.payload.interaction 必须满足 ai_coach_interaction_v1，"
            "场景判断卡可使用 single_choice 或 multiple_choice；改写卡和角色回应卡必须使用 short_answer。"
            "scoring_rubric.partial_credit_policy 只能使用 all_or_nothing、proportional、tiered，"
            "不得使用 partial。"
            "如果 coach_state.active_event_id 存在，表示已有未提交训练卡；除非用户明确要求换题或后台动作要求，"
            "否则优先回答问题或解释当前卡，不要再生成新的 quiz_card。"
            "反馈必须覆盖：做对了什么、主要问题、为什么不合适、可以怎么说、下一步。"
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
    def business_etiquette_learning_units(
        path_config: dict[str, object],
    ) -> list[dict[str, object]]:
        raw_units = path_config.get("learning_units")
        if not isinstance(raw_units, list):
            return []
        units: list[dict[str, object]] = []
        for item in raw_units:
            if not isinstance(item, dict):
                continue
            units.append(
                {
                    "unit_key": item.get("unit_key"),
                    "title": item.get("title"),
                    "source_chapter_orders": item.get("source_chapter_orders") or [],
                    "capability_keys": item.get("capability_keys") or [],
                    "require_ai_coach": item.get("require_ai_coach"),
                }
            )
        return units

    @staticmethod
    def capability_keys(learning_units: list[dict[str, object]]) -> list[str]:
        keys: list[str] = []
        for unit in learning_units:
            raw_keys = unit.get("capability_keys")
            if not isinstance(raw_keys, list):
                continue
            for key in raw_keys:
                if isinstance(key, str) and key and key not in keys:
                    keys.append(key)
        return keys

    @staticmethod
    def compatible_training_card_types(config: AiCoachConfig) -> tuple[str, ...]:
        allowed = set(config.allowed_training_card_types)
        result: list[str] = []
        if "scenario_judgment" in allowed:
            result.append("scenario_judgment")
        if "short_answer" in config.allowed_interaction_types:
            for card_type in ("expression_rewrite", "role_response"):
                if card_type in allowed:
                    result.append(card_type)
        return tuple(result or ["scenario_judgment"])

    @staticmethod
    def training_card_contract(config: AiCoachConfig) -> dict[str, object]:
        return {
            "allowed_training_card_types": list(
                AiCoachChatPromptCompiler.compatible_training_card_types(config)
            ),
            "card_type_rules": {
                "scenario_judgment": (
                    "给出拜访、接待、会议或餐饮场景，让学员判断做法是否合适。"
                ),
                "expression_rewrite": (
                    "给出不专业表达，让学员改写为合适商务表达；必须使用 short_answer。"
                ),
                "role_response": (
                    "给出客户、领导或同事一句话，让学员写回应方式；必须使用 short_answer。"
                ),
            },
        }

    @staticmethod
    def feedback_schema() -> dict[str, str]:
        return {
            "did_well": "你做对了什么",
            "main_issue": "主要问题是什么",
            "why_inappropriate": "为什么在真实商务场景里不合适",
            "suggested_response": "可以怎么说",
            "next_step": "再试一版或进入下一张卡",
        }

    @staticmethod
    def _resolver_error(
        exc: PromptTemplateRevisionResolverError,
    ) -> AiCoachChatGenerationError:
        return AiCoachChatGenerationError(
            AiCoachSessionService._prompt_resolver_public_code(exc),
            exc.message,
            409,
        )

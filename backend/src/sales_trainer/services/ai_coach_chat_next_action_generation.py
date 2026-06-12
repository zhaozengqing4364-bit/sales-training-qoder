from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from prompt_templates.compiled_contract import CompiledPromptContract
from prompt_templates.service import PromptTemplateService
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachChatMessage
from sales_trainer.ai_coach_chat_schemas import AiCoachChatResponseInternalV1
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    AiCoachAnswerPayloadV1,
    AiCoachConfig,
    AiCoachNextActionV1,
    AiCoachScoreResultV1,
)
from sales_trainer.services.ai_coach_chat_coach_state import AiCoachCoachStateV1
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError
from sales_trainer.services.ai_coach_chat_generation import AiCoachChatGenerator
from sales_trainer.services.ai_coach_chat_generation_parser import (
    AiCoachChatResponseParser,
)
from sales_trainer.services.ai_coach_chat_next_action import AiCoachNextActionDecision
from sales_trainer.services.ai_coach_session_service import AiCoachSessionService
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_AUDIT_HISTORY_UNAVAILABLE,
    RESULT_OK,
    PromptTemplateRevisionResolver,
    PromptTemplateRevisionResolverError,
)


class AiCoachChatNextActionGenerator:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._parser = AiCoachChatResponseParser()

    async def generate(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        decision: AiCoachNextActionDecision,
        state: AiCoachCoachStateV1,
        score_result: AiCoachScoreResultV1,
        answer_payload: AiCoachAnswerPayloadV1,
        answered_event_payload: dict[str, Any],
        history: list[SalesTrainerAiCoachChatMessage],
    ) -> AiCoachChatResponseInternalV1:
        contract = await self._compile_contract(
            session=session,
            config=config,
            decision=decision,
            state=state,
            score_result=score_result,
            answer_payload=answer_payload,
            answered_event_payload=answered_event_payload,
            history=history,
        )
        max_attempts = config.retry_policy.max_retries + 1
        last_error: AiCoachChatGenerationError | None = None
        for attempt in range(max_attempts):
            prompt = AiCoachChatGenerator._prompt_for_attempt(
                contract.rendered_prompt,
                last_error,
            )
            result = await LLMService().generate(
                prompt=prompt,
                session_id=session.session_id,
                system_message=contract.system_message,
                allow_fallback_response=False,
            )
            if not result.is_success or not result.value:
                last_error = AiCoachChatGenerationError(
                    "[AI_COACH_LLM_GENERATION_FAILED]",
                    "AI 教练生成下一步失败，请稍后重试。",
                    502,
                )
                continue
            try:
                parsed = self._parser.parse_model_response(str(result.value), config)
                self._validate_response_for_action(parsed, decision.action)
                return parsed
            except AiCoachChatGenerationError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise AiCoachChatGenerationError(
            "[AI_COACH_LLM_GENERATION_FAILED]",
            "AI 教练生成下一步失败，请稍后重试。",
            502,
        )

    async def _compile_contract(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        decision: AiCoachNextActionDecision,
        state: AiCoachCoachStateV1,
        score_result: AiCoachScoreResultV1,
        answer_payload: AiCoachAnswerPayloadV1,
        answered_event_payload: dict[str, Any],
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
            raise AiCoachChatGenerationError(code, "AI 教练 Prompt revision 不可用。", 409)
        compile_result = PromptTemplateService(
            self._db
        ).compile_runtime_prompt_contract(
            template=resolution.snapshot.template,
            variables=self._variables(
                session=session,
                config=config,
                decision=decision,
                state=state,
                score_result=score_result,
                answer_payload=answer_payload,
                answered_event_payload=answered_event_payload,
                history=history,
            ),
            runtime_consumer="ai_coach.chat.next_action",
            system_message=self._system_message(config, decision),
            model_config=None,
        )
        if not compile_result.is_success or compile_result.value is None:
            raise AiCoachChatGenerationError(
                f"[AI_COACH_PROMPT_COMPILE_FAILED:{compile_result.fallback or 'unknown'}]",
                "无法编译 AI 教练下一步 Prompt。",
                502,
            )
        return compile_result.value

    def _variables(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        decision: AiCoachNextActionDecision,
        state: AiCoachCoachStateV1,
        score_result: AiCoachScoreResultV1,
        answer_payload: AiCoachAnswerPayloadV1,
        answered_event_payload: dict[str, Any],
        history: list[SalesTrainerAiCoachChatMessage],
    ) -> dict[str, Any]:
        article = session.article_snapshot or {}
        chapters = article.get("chapters") if isinstance(article, dict) else []
        return {
            "module_key": session.module_key,
            "user_message": "",
            "next_action": decision.action,
            "action_reason": decision.reason,
            "coach_state": state.model_dump(mode="json"),
            "score_result": score_result.model_dump(mode="json"),
            "answered_interaction_snapshot": answered_event_payload.get(
                "interaction_snapshot"
            ),
            "user_answer_payload": answer_payload.model_dump(mode="json"),
            "allowed_ui_event_types": list(AiCoachChatGenerator.allowed_ui_event_types(config)),
            "allowed_interaction_types": list(config.allowed_interaction_types),
            "max_cards_per_message": int(config.max_cards_per_message),
            "current_focus": state.current_focus,
            "difficulty": state.difficulty,
            "article_title": article.get("title") if isinstance(article, dict) else "",
            "article_summary": article.get("summary") if isinstance(article, dict) else "",
            "article_snapshot": session.article_snapshot or {},
            "chapter_titles": self._chapter_titles(chapters),
            "history": [
                {"role": message.role, "content": message.content}
                for message in history
            ],
        }

    @staticmethod
    def _chapter_titles(chapters: object) -> list[str]:
        if not isinstance(chapters, list):
            return []
        titles: list[str] = []
        for chapter in chapters:
            if isinstance(chapter, dict) and isinstance(chapter.get("title"), str):
                titles.append(str(chapter["title"]))
        return titles

    @staticmethod
    def _system_message(
        config: AiCoachConfig,
        decision: AiCoachNextActionDecision,
    ) -> str:
        allowed_ui = ", ".join(AiCoachChatGenerator.allowed_ui_event_types(config))
        return (
            "你是商务技巧 AI 教练。后端已经决定 next_action="
            f"{decision.action}，你必须只服务这个动作。只能输出 JSON，"
            f"ui_events 只能使用这些 type: {allowed_ui}。"
            "不得输出 HTML、JSX、CSS、脚本或任意组件树。"
        )

    @staticmethod
    def _validate_response_for_action(
        response: AiCoachChatResponseInternalV1,
        action: AiCoachNextActionV1,
    ) -> None:
        event_types = [event.type for event in response.ui_events]
        counts = {
            "quiz_card": event_types.count("quiz_card"),
            "explanation_card": event_types.count("explanation_card"),
            "summary_card": event_types.count("summary_card"),
            "followup_prompt": event_types.count("followup_prompt"),
        }

        def invalid(message: str) -> None:
            raise AiCoachChatGenerationError(
                "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]",
                message,
                502,
            )

        match action:
            case "continue_drill" | "increase_difficulty":
                if counts != {
                    "quiz_card": 1,
                    "explanation_card": 0,
                    "summary_card": 0,
                    "followup_prompt": 0,
                }:
                    invalid("该 next_coach_action 只能生成 1 张 quiz_card。")
            case "remediate":
                if counts != {
                    "quiz_card": 1,
                    "explanation_card": 1,
                    "summary_card": 0,
                    "followup_prompt": 0,
                }:
                    invalid("remediate 必须生成 1 张 explanation_card 和 1 张 quiz_card。")
            case "switch_scenario":
                if (
                    counts["quiz_card"] != 1
                    or counts["explanation_card"] != 0
                    or counts["summary_card"] != 0
                    or counts["followup_prompt"] > 1
                ):
                    invalid("switch_scenario 必须生成 1 张 quiz_card，可附 1 个 followup_prompt。")
            case "summarize":
                if (
                    counts["summary_card"] != 1
                    or counts["quiz_card"] != 0
                    or counts["explanation_card"] != 0
                    or counts["followup_prompt"] > 1
                ):
                    invalid("summarize 必须生成 1 张 summary_card，可附 1 个 followup_prompt。")
            case "ask_user_choice":
                if counts != {
                    "quiz_card": 0,
                    "explanation_card": 0,
                    "summary_card": 0,
                    "followup_prompt": 1,
                }:
                    invalid("ask_user_choice 必须只生成 1 个 followup_prompt。")
            case "end_session":
                if counts != {
                    "quiz_card": 0,
                    "explanation_card": 0,
                    "summary_card": 1,
                    "followup_prompt": 0,
                }:
                    invalid("end_session 必须只生成 1 张 summary_card。")

    @staticmethod
    def _resolver_error(
        exc: PromptTemplateRevisionResolverError,
    ) -> AiCoachChatGenerationError:
        return AiCoachChatGenerationError(
            AiCoachSessionService._prompt_resolver_public_code(exc),
            exc.message,
            409,
        )

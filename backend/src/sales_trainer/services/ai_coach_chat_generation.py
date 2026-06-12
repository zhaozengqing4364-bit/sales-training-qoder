from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachChatMessage
from sales_trainer.ai_coach_chat_schemas import AiCoachChatResponseInternalV1
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import AiCoachConfig
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError
from sales_trainer.services.ai_coach_chat_generation_parser import (
    AiCoachChatResponseParser,
)
from sales_trainer.services.ai_coach_chat_generation_prompt import (
    AiCoachChatPromptCompiler,
)


class AiCoachChatGenerator:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._parser = AiCoachChatResponseParser()

    async def generate(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        user_message: str,
        history: list[SalesTrainerAiCoachChatMessage],
    ) -> AiCoachChatResponseInternalV1:
        contract = await AiCoachChatPromptCompiler(self._db).compile(
            session=session,
            config=config,
            user_message=user_message,
            history=history,
        )
        session.prompt_contract_hash = contract.contract_hash
        max_attempts = config.retry_policy.max_retries + 1
        last_error: AiCoachChatGenerationError | None = None
        for attempt in range(max_attempts):
            prompt = self._prompt_for_attempt(contract.rendered_prompt, last_error)
            result = await LLMService().generate(
                prompt=prompt,
                session_id=session.session_id,
                system_message=contract.system_message,
                allow_fallback_response=False,
            )
            if not result.is_success or not result.value:
                last_error = AiCoachChatGenerationError(
                    "[AI_COACH_LLM_GENERATION_FAILED]",
                    "AI 教练生成失败，请稍后重试。",
                    502,
                )
                continue
            try:
                parsed = self._parser.parse_model_response(str(result.value), config)
            except AiCoachChatGenerationError as exc:
                last_error = exc
                continue
            return parsed
        if last_error is not None:
            raise last_error
        raise AiCoachChatGenerationError(
            "[AI_COACH_LLM_GENERATION_FAILED]",
            "AI 教练生成失败，请稍后重试。",
            502,
        )

    @staticmethod
    def allowed_ui_event_types(config: AiCoachConfig) -> tuple[str, ...]:
        return AiCoachChatResponseParser.allowed_ui_event_types(config)

    @staticmethod
    def _prompt_for_attempt(
        base_prompt: str,
        last_error: AiCoachChatGenerationError | None,
    ) -> str:
        if last_error is None:
            return base_prompt
        return (
            f"{base_prompt}\n\n"
            "上一轮输出未通过后端契约校验。请只重新输出一份合法 JSON，"
            f"错误码：{last_error.code}。"
            "不要解释错误，不要输出 Markdown。"
        )

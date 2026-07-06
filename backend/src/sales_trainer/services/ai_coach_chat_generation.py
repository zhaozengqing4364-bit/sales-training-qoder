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
from sales_trainer.services.ai_coach_chat_generation_streaming import (
    AI_COACH_JSON_RESPONSE_FORMAT,
    AiCoachGenerationDeltaHandler,
    emit_streamed_response,
    prompt_for_attempt,
)
from sales_trainer.services.ai_coach_model_config import (
    AiCoachModelConfigError,
    model_config_id,
    resolve_ai_coach_llm_model_config_from_db,
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
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> AiCoachChatResponseInternalV1:
        try:
            model_config = await resolve_ai_coach_llm_model_config_from_db(
                self._db,
                config.generation_model,
            )
        except AiCoachModelConfigError as exc:
            raise AiCoachChatGenerationError(exc.code, exc.message, 409) from exc
        contract = await AiCoachChatPromptCompiler(self._db).compile(
            session=session,
            config=config,
            user_message=user_message,
            history=history,
            model_config=model_config,
        )
        setattr(session, "prompt_contract_hash", contract.contract_hash)
        max_attempts = config.retry_policy.max_retries + 1
        llm_service = LLMService(config=model_config) if model_config is not None else LLMService()
        if on_generation_delta is not None:
            streamed = await emit_streamed_response(
                llm=llm_service,
                parser=self._parser,
                contract=contract,
                config=config,
                session_id=str(session.session_id),
                max_attempts=max_attempts,
                failure_message="AI 教练生成失败，请稍后重试。",
                on_generation_delta=on_generation_delta,
            )
            streamed.response.runtime_audit = self._llm_runtime_audit(
                llm_service,
                model_config,
                session_id=str(session.session_id),
            )
            return streamed.response
        last_error: AiCoachChatGenerationError | None = None
        for attempt in range(max_attempts):
            prompt = prompt_for_attempt(contract.rendered_prompt, last_error)
            result = await llm_service.generate(
                prompt=prompt,
                session_id=str(session.session_id),
                system_message=contract.system_message,
                allow_fallback_response=False,
                response_format=AI_COACH_JSON_RESPONSE_FORMAT,
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
            parsed.runtime_audit = self._llm_runtime_audit(
                llm_service,
                model_config,
                session_id=str(session.session_id),
            )
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
        return prompt_for_attempt(base_prompt, last_error)

    @staticmethod
    def _llm_runtime_audit(
        llm_service: LLMService,
        model_config: object | None,
        *,
        session_id: str | None = None,
    ) -> dict[str, object]:
        effective_config = getattr(llm_service, "_effective_config", None)
        base_url = ""
        if isinstance(effective_config, dict):
            base_url = str(effective_config.get("base_url") or "")
        audit: dict[str, object] = {
            "provider": str(getattr(llm_service, "provider", "") or ""),
            "model_name": str(getattr(llm_service, "model_name", "") or ""),
            "base_url": base_url,
            "base_url_configured": bool(base_url.strip()),
            "model_config_id": model_config_id(model_config),
            "source": "model_config" if model_config is not None else "env_fallback",
            "is_configured": bool(getattr(llm_service, "is_configured", False)),
        }
        if session_id:
            provider_event = AiCoachChatGenerator._latest_provider_response_event(
                llm_service,
                session_id,
            )
            if provider_event:
                audit["provider_response"] = provider_event
        return audit

    @staticmethod
    def _latest_provider_response_event(
        llm_service: LLMService,
        session_id: str,
    ) -> dict[str, object] | None:
        event_reader = getattr(llm_service, "get_session_runtime_events", None)
        if not callable(event_reader):
            return None
        events = event_reader(session_id)
        for event in reversed(events):
            if event.get("event_id") != "llm_provider_response_received":
                continue
            details = event.get("details")
            metrics = event.get("metrics")
            return {
                "event_id": "llm_provider_response_received",
                "status": str(event.get("status") or ""),
                "source": str(event.get("source") or ""),
                "fallback_used": bool(
                    details.get("fallback_used")
                    if isinstance(details, dict)
                    else True
                ),
                "metrics": dict(metrics) if isinstance(metrics, dict) else {},
            }
        return None

"""Production composition for governed newcomer-training LLM invocations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_coach.ai_schemas import register_coach_ai_schemas
from ai_platform import (
    AIInvocationPort,
    GovernedAIInvocationService,
    OpenAICompatibleProvider,
    OpenAICompatibleProviderSettings,
    PromptCompilationService,
    StrictPromptCompiler,
)
from ai_platform.providers import AIProvider
from ai_platform.schemas import OutputSchemaRegistry
from ai_platform.sqlalchemy_adapters import (
    SQLAlchemyAIInvocationStore,
    SQLAlchemyPublishedModelRoutingProfileResolver,
    SQLAlchemyPublishedPromptRevisionResolver,
)
from audio_assessment.ai_schemas import register_audio_ai_schemas
from audio_assessment.ports import AudioObjectStoragePort
from audio_assessment.storage import build_audio_object_storage
from common.ai.config_manager import get_config_manager
from common.ai.endpoint_policy import EndpointPolicyError, validate_provider_base_url
from common.ai.models import ModelProvider, ModelType
from foundation_audio_ai_provider import (
    GovernedParaformerProvider,
    SQLAlchemyAudioArtifactURLResolver,
    WorkloadDispatchProvider,
)
from learning.ai_schemas import register_learning_ai_schemas

AIInvocationFactory = Callable[[], AIInvocationPort]
_APPLICATION_CONFIG = object()


def build_foundation_prompt_compilation_service(
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> PromptCompilationService:
    """Build the preview/compiler seam used to pin dynamic invocation contracts."""

    return PromptCompilationService(
        resolver=SQLAlchemyPublishedPromptRevisionResolver(session_factory),
        compiler=StrictPromptCompiler(),
    )


def build_foundation_ai_invocation_factory(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    effective_config: dict[str, Any] | None | object = _APPLICATION_CONFIG,
    audio_storage: AudioObjectStoragePort | None = None,
) -> AIInvocationFactory:
    config = (
        get_config_manager().get_effective_config(ModelType.LLM)
        if effective_config is _APPLICATION_CONFIG
        else effective_config
    )
    settings = _provider_settings(config if isinstance(config, dict) else None)
    llm_provider = OpenAICompatibleProvider(settings)
    storage = audio_storage or build_audio_object_storage()
    asr_provider = GovernedParaformerProvider(
        resolve_artifact_url=SQLAlchemyAudioArtifactURLResolver(
            session_factory,
            storage=storage,
        )
    )
    provider = WorkloadDispatchProvider(
        llm=llm_provider,
        asr=asr_provider if settings.provider == "alibaba" else None,
    )
    schemas = OutputSchemaRegistry()
    register_learning_ai_schemas(schemas)
    register_audio_ai_schemas(schemas)
    register_coach_ai_schemas(schemas)
    providers: dict[str, AIProvider] = {
        settings.provider: provider,
        GovernedParaformerProvider.provider_name: asr_provider,
        "alibaba_asr": asr_provider,
    }
    if settings.provider != "alibaba":
        providers["alibaba"] = asr_provider
    service = GovernedAIInvocationService(
        prompt_resolver=SQLAlchemyPublishedPromptRevisionResolver(session_factory),
        routing_resolver=SQLAlchemyPublishedModelRoutingProfileResolver(
            session_factory
        ),
        compiler=StrictPromptCompiler(),
        schemas=schemas,
        providers=providers,
        store=SQLAlchemyAIInvocationStore(session_factory),
    )
    return lambda: service


def _provider_settings(
    config: dict[str, Any] | None,
) -> OpenAICompatibleProviderSettings:
    if not config:
        raise RuntimeError("新人训练 AI Worker 缺少 LLM 连接配置，已拒绝启动。")
    provider_name = str(config.get("provider") or "").strip().lower()
    try:
        provider = ModelProvider(provider_name)
    except ValueError as exc:
        raise RuntimeError("新人训练 AI Worker 的 LLM Provider 未受支持。") from exc
    if provider not in {ModelProvider.OPENAI, ModelProvider.ALIBABA}:
        raise RuntimeError(
            "新人训练 AI Worker 当前只支持受控的 OpenAI-compatible LLM Provider。"
        )
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("新人训练 AI Worker 缺少 LLM 凭据，已拒绝启动。")
    try:
        endpoint = validate_provider_base_url(
            provider,
            str(config.get("base_url") or ""),
            resolve_dns=False,
        )
    except EndpointPolicyError as exc:
        raise RuntimeError(
            "新人训练 AI Worker 的 LLM Endpoint 未通过安全策略。"
        ) from exc
    extra = config.get("extra_config")
    extra = extra if isinstance(extra, dict) else {}
    try:
        return OpenAICompatibleProviderSettings(
            provider=provider.value,
            base_url=endpoint.base_url,
            api_key=api_key,
            currency=str(extra.get("currency") or "CNY").upper(),
            input_cost_minor_units_per_million=int(
                extra.get("input_cost_minor_units_per_million", 0)
            ),
            output_cost_minor_units_per_million=int(
                extra.get("output_cost_minor_units_per_million", 0)
            ),
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("新人训练 AI Worker 的 Provider 计费配置无效。") from exc


__all__ = [
    "build_foundation_ai_invocation_factory",
    "build_foundation_prompt_compilation_service",
]

"""Application-root composition for cross-domain realtime compatibility adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from presentation_coach.websocket.presentation_handler import (
    PresentationWebSocketHandler,
)
from presentation_coach.websocket.presentation_realtime_engine_handler import (
    PresentationRealtimeEngineHandler,
)
from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
    PresentationStepFunRuntimeMixin,
)
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeSharedHandler
from training_runtime.plugins import RuntimeHandlerFactoryKey
from training_runtime.realtime import RealtimeSessionEngine


class PresentationStepFunRealtimeAdapter(
    PresentationStepFunRuntimeMixin,
    StepFunRealtimeSharedHandler,
):
    """Concrete compatibility adapter assembled outside both scenario domains."""


def create_presentation_realtime_engine_handler() -> PresentationRealtimeEngineHandler:
    return PresentationRealtimeEngineHandler(
        runtime_engine_factory=RealtimeSessionEngine,
        runtime_adapter_factory=PresentationStepFunRealtimeAdapter,
    )


PRESENTATION_RUNTIME_HANDLER_FACTORIES: Mapping[
    RuntimeHandlerFactoryKey, Callable[[], Any]
] = MappingProxyType(
    {
        RuntimeHandlerFactoryKey.PRESENTATION_LEGACY: PresentationWebSocketHandler,
        RuntimeHandlerFactoryKey.PRESENTATION_STEPFUN_ROLLBACK: (
            PresentationStepFunRealtimeAdapter
        ),
        RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE: (
            create_presentation_realtime_engine_handler
        ),
    }
)


def create_presentation_runtime_handler(
    factory_key: str | RuntimeHandlerFactoryKey,
) -> Any:
    try:
        resolved_key = RuntimeHandlerFactoryKey(factory_key)
    except (TypeError, ValueError) as exc:
        raise ValueError("unknown_runtime_handler_factory_key") from exc
    factory = PRESENTATION_RUNTIME_HANDLER_FACTORIES.get(resolved_key)
    if factory is None:
        raise ValueError("unknown_runtime_handler_factory_key")
    return factory()

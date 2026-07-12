"""Shared scenario plugin contracts and thin runtime adapters."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from common.config import settings
from common.runtime_descriptor import TrainingRuntimeDescriptor

from .realtime import ENGINE_STATE_VERSION


class RuntimeHandlerFactoryKey(StrEnum):
    """Closed application-root factory choices for declarative handler selection."""

    SALES_STEPFUN = "sales_stepfun"
    PRESENTATION_LEGACY = "presentation_legacy"
    PRESENTATION_STEPFUN_ROLLBACK = "presentation_stepfun_rollback"
    PRESENTATION_REALTIME_ENGINE = "presentation_realtime_engine"


LEGACY_SALES_HANDLER_MODULES = (
    # Explicit allowlist of removed Sales websocket modules that must stay absent.
    "sales_bot.websocket.base_sales_handler",
    "sales_bot.websocket.enhanced_handler",
    "sales_bot.websocket.simple_handler",
)


@dataclass(frozen=True)
class ScenarioRuntimeHandlerSelection:
    """A scenario websocket runtime handler selection."""

    scenario_type: str
    runtime_mode: str
    websocket_route: str
    factory_key: RuntimeHandlerFactoryKey


@dataclass(frozen=True)
class ScenarioPluginDiagnostics:
    """Inspectable plugin wiring details for tests and operators."""

    scenario_type: str
    runtime_family: str
    entrypoints: tuple[str, ...]
    details: dict[str, object] = field(default_factory=dict)


class ScenarioTrainingPlugin(Protocol):
    """Backend contract implemented by every training scenario plugin."""

    scenario_type: str

    def select_runtime_handler(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioRuntimeHandlerSelection: ...

    def diagnostics(self) -> ScenarioPluginDiagnostics: ...


def legacy_sales_handlers_absent() -> dict[str, bool]:
    return {
        module: importlib.util.find_spec(module) is None
        for module in LEGACY_SALES_HANDLER_MODULES
    }


class SalesScenarioPlugin:
    """Thin adapter around the StepFun-only Sales runtime."""

    scenario_type = "sales"
    _runtime_mode = "stepfun_realtime"

    def select_runtime_handler(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioRuntimeHandlerSelection:
        return ScenarioRuntimeHandlerSelection(
            scenario_type=self.scenario_type,
            runtime_mode=self._runtime_mode,
            websocket_route="/ws/sales/{session_id}",
            factory_key=RuntimeHandlerFactoryKey.SALES_STEPFUN,
        )

    def diagnostics(self) -> ScenarioPluginDiagnostics:
        return ScenarioPluginDiagnostics(
            scenario_type=self.scenario_type,
            runtime_family="stepfun_only",
            entrypoints=("select_runtime_handler", "diagnostics"),
            details={
                "runtime_factory": RuntimeHandlerFactoryKey.SALES_STEPFUN.value,
                "legacy_handlers_absent": legacy_sales_handlers_absent(),
            },
        )


class PresentationScenarioPlugin:
    """Thin adapter around the existing Presentation training flow."""

    scenario_type = "presentation"

    def __init__(
        self,
        *,
        rollout_resolver: Callable[[], bool] | None = None,
    ) -> None:
        self._rollout_resolver = rollout_resolver or (
            lambda: bool(settings.PRESENTATION_REALTIME_ENGINE_ENABLED)
        )

    def select_runtime_handler(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioRuntimeHandlerSelection:
        runtime_mode = self._runtime_mode(descriptor)
        if runtime_mode == "stepfun_realtime":
            realtime_engine_enabled = bool(self._rollout_resolver())
            factory_key = (
                RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE
                if realtime_engine_enabled
                else RuntimeHandlerFactoryKey.PRESENTATION_STEPFUN_ROLLBACK
            )
        else:
            factory_key = RuntimeHandlerFactoryKey.PRESENTATION_LEGACY

        return ScenarioRuntimeHandlerSelection(
            scenario_type=self.scenario_type,
            runtime_mode=runtime_mode,
            websocket_route="/ws/presentation/{session_id}",
            factory_key=factory_key,
        )

    def diagnostics(self) -> ScenarioPluginDiagnostics:
        realtime_engine_enabled = bool(self._rollout_resolver())
        return ScenarioPluginDiagnostics(
            scenario_type=self.scenario_type,
            runtime_family="presentation_training_flow",
            entrypoints=("select_runtime_handler", "diagnostics"),
            details={
                "legacy_runtime": RuntimeHandlerFactoryKey.PRESENTATION_LEGACY.value,
                "stepfun_runtime": (
                    RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE.value
                ),
                "rollback_runtime": (
                    RuntimeHandlerFactoryKey.PRESENTATION_STEPFUN_ROLLBACK.value
                ),
                "realtime_engine_enabled": realtime_engine_enabled,
                "selected_stepfun_runtime": (
                    "presentation_realtime_engine"
                    if realtime_engine_enabled
                    else "legacy_presentation_stepfun"
                ),
                "engine_state_version": ENGINE_STATE_VERSION,
            },
        )

    @staticmethod
    def _runtime_mode(descriptor: TrainingRuntimeDescriptor) -> str:
        mode = str(descriptor.voice_mode or "").strip().lower()
        return "stepfun_realtime" if mode == "stepfun_realtime" else "legacy"


class ScenarioPluginRegistry:
    """Scenario plugin discovery and dispatch by scenario type or descriptor."""

    def __init__(self, plugins: tuple[ScenarioTrainingPlugin, ...]) -> None:
        self._plugins = {plugin.scenario_type: plugin for plugin in plugins}

    def list_plugins(self) -> tuple[ScenarioTrainingPlugin, ...]:
        return tuple(self._plugins[key] for key in sorted(self._plugins))

    def plugin_for_scenario_type(self, scenario_type: str) -> ScenarioTrainingPlugin:
        key = str(scenario_type or "").strip().lower()
        plugin = self._plugins.get(key)
        if plugin is None:
            raise KeyError(f"Unsupported training scenario plugin: {scenario_type}")
        return plugin

    def plugin_for_descriptor(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioTrainingPlugin:
        return self.plugin_for_scenario_type(descriptor.scenario_type)


def build_default_scenario_plugin_registry() -> ScenarioPluginRegistry:
    return ScenarioPluginRegistry(
        (
            SalesScenarioPlugin(),
            PresentationScenarioPlugin(),
        )
    )


_DEFAULT_REGISTRY = build_default_scenario_plugin_registry()


def get_scenario_plugin(scenario_type: str) -> ScenarioTrainingPlugin:
    return _DEFAULT_REGISTRY.plugin_for_scenario_type(scenario_type)


def dispatch_scenario_plugin(
    descriptor: TrainingRuntimeDescriptor,
) -> ScenarioTrainingPlugin:
    return _DEFAULT_REGISTRY.plugin_for_descriptor(descriptor)

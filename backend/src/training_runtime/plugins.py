"""Shared scenario plugin contracts and thin runtime adapters."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from common.config import settings
from common.runtime_descriptor import TrainingRuntimeDescriptor

from .realtime import ENGINE_STATE_VERSION, RealtimeSessionEngine

PluginAction = str
LEGACY_SALES_HANDLER_MODULES = (
    # Explicit allowlist of removed Sales websocket modules that must stay absent.
    "sales_bot.websocket.base_sales_handler",
    "sales_bot.websocket.enhanced_handler",
    "sales_bot.websocket.simple_handler",
)


@dataclass(frozen=True)
class ScenarioPluginEntrypoint:
    """A shared descriptor for an existing scenario runtime entrypoint."""

    scenario_type: str
    action: PluginAction
    session_id: str
    service_path: str
    method_name: str
    runtime_mode: str | None = None
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioRuntimeHandlerSelection:
    """A scenario websocket runtime handler selection."""

    scenario_type: str
    runtime_mode: str
    websocket_route: str
    handler_factory_path: str
    handler_factory_name: str
    handler_factory_kwargs: dict[str, object] = field(default_factory=dict)


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

    def on_session_start(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint: ...

    def on_session_end(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint: ...

    def select_runtime_handler(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioRuntimeHandlerSelection: ...

    def build_evidence(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint: ...

    def trigger_evaluation(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint: ...

    def build_report_view(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint: ...

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

    def on_session_start(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action="on_session_start",
            service_path="sales_bot.websocket.stepfun_realtime_handler",
            method_name="create_stepfun_realtime_handler",
            payload={"websocket_route": "/ws/sales/{session_id}"},
        )

    def on_session_end(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._report_trigger_entrypoint(descriptor, action="on_session_end")

    def select_runtime_handler(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioRuntimeHandlerSelection:
        return ScenarioRuntimeHandlerSelection(
            scenario_type=self.scenario_type,
            runtime_mode=self._runtime_mode,
            websocket_route="/ws/sales/{session_id}",
            handler_factory_path="sales_bot.websocket.stepfun_realtime_handler",
            handler_factory_name="create_stepfun_realtime_handler",
        )

    def build_evidence(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action="build_evidence",
            service_path="common.conversation.session_evidence.SessionEvidenceService",
            method_name="get_projection",
            payload={"require_completed": False},
        )

    def trigger_evaluation(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._report_trigger_entrypoint(
            descriptor,
            action="trigger_evaluation",
        )

    def build_report_view(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action="build_report_view",
            service_path=(
                "evaluation.services.training_report_snapshot_service."
                "TrainingReportSnapshotService"
            ),
            method_name="_get_snapshot_for_session",
        )

    def diagnostics(self) -> ScenarioPluginDiagnostics:
        return ScenarioPluginDiagnostics(
            scenario_type=self.scenario_type,
            runtime_family="stepfun_only",
            entrypoints=(
                "on_session_start",
                "on_session_end",
                "build_evidence",
                "trigger_evaluation",
                "build_report_view",
                "diagnostics",
            ),
            details={
                "runtime_handler": "sales_bot.websocket.stepfun_realtime_handler.StepFunRealtimeHandler",
                "legacy_handlers_absent": legacy_sales_handlers_absent(),
            },
        )

    def _report_trigger_entrypoint(
        self,
        descriptor: TrainingRuntimeDescriptor,
        *,
        action: PluginAction,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action=action,
            service_path="evaluation.services.report_generation_trigger",
            method_name="trigger_report_generation",
        )

    def _entrypoint(
        self,
        descriptor: TrainingRuntimeDescriptor,
        *,
        action: PluginAction,
        service_path: str,
        method_name: str,
        payload: dict[str, object] | None = None,
    ) -> ScenarioPluginEntrypoint:
        return ScenarioPluginEntrypoint(
            scenario_type=self.scenario_type,
            action=action,
            session_id=descriptor.session_id,
            service_path=service_path,
            method_name=method_name,
            runtime_mode=self._runtime_mode,
            payload={"scenario_type": self.scenario_type, **(payload or {})},
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

    def on_session_start(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        runtime_mode = self._runtime_mode(descriptor)
        if runtime_mode == "stepfun_realtime":
            realtime_engine_enabled = bool(self._rollout_resolver())
            handler_module, handler_name = self._stepfun_handler_selection(
                realtime_engine_enabled
            )
            handler_path = f"{handler_module}.{handler_name}"
        else:
            handler_path = (
                "presentation_coach.websocket.presentation_handler."
                "PresentationWebSocketHandler"
            )
        return self._entrypoint(
            descriptor,
            action="on_session_start",
            service_path=handler_path,
            method_name="handle_connection",
            payload={"websocket_route": "/ws/presentation/{session_id}"},
        )

    def on_session_end(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._report_trigger_entrypoint(descriptor, action="on_session_end")

    def select_runtime_handler(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioRuntimeHandlerSelection:
        runtime_mode = self._runtime_mode(descriptor)
        if runtime_mode == "stepfun_realtime":
            realtime_engine_enabled = bool(self._rollout_resolver())
            handler_factory_path, handler_factory_name = (
                self._stepfun_handler_selection(realtime_engine_enabled)
            )
            handler_factory_kwargs: dict[str, object] = (
                {"runtime_engine_factory": RealtimeSessionEngine}
                if realtime_engine_enabled
                else {}
            )
        else:
            handler_factory_path = "presentation_coach.websocket.presentation_handler"
            handler_factory_name = "PresentationWebSocketHandler"
            handler_factory_kwargs = {}

        return ScenarioRuntimeHandlerSelection(
            scenario_type=self.scenario_type,
            runtime_mode=runtime_mode,
            websocket_route="/ws/presentation/{session_id}",
            handler_factory_path=handler_factory_path,
            handler_factory_name=handler_factory_name,
            handler_factory_kwargs=handler_factory_kwargs,
        )

    def build_evidence(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action="build_evidence",
            service_path="common.conversation.session_evidence.SessionEvidenceService",
            method_name="get_projection",
            payload={"require_completed": False},
        )

    def trigger_evaluation(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._report_trigger_entrypoint(
            descriptor,
            action="trigger_evaluation",
        )

    def build_report_view(
        self,
        descriptor: TrainingRuntimeDescriptor,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action="build_report_view",
            service_path=(
                "evaluation.services.training_report_snapshot_service."
                "TrainingReportSnapshotService"
            ),
            method_name="_get_snapshot_for_session",
        )

    def diagnostics(self) -> ScenarioPluginDiagnostics:
        realtime_engine_enabled = bool(self._rollout_resolver())
        return ScenarioPluginDiagnostics(
            scenario_type=self.scenario_type,
            runtime_family="presentation_training_flow",
            entrypoints=(
                "on_session_start",
                "on_session_end",
                "build_evidence",
                "trigger_evaluation",
                "build_report_view",
                "diagnostics",
            ),
            details={
                "legacy_handler": "presentation_coach.websocket.presentation_handler.PresentationWebSocketHandler",
                "stepfun_handler": (
                    "presentation_coach.websocket.presentation_realtime_engine_handler."
                    "PresentationRealtimeEngineHandler"
                ),
                "rollback_handler": (
                    "presentation_coach.websocket.presentation_stepfun_realtime_handler."
                    "LegacyPresentationStepFunRealtimeHandler"
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
    def _stepfun_handler_selection(
        realtime_engine_enabled: bool,
    ) -> tuple[str, str]:
        if realtime_engine_enabled:
            return (
                "presentation_coach.websocket.presentation_realtime_engine_handler",
                "PresentationRealtimeEngineHandler",
            )
        return (
            "presentation_coach.websocket.presentation_stepfun_realtime_handler",
            "LegacyPresentationStepFunRealtimeHandler",
        )

    def _report_trigger_entrypoint(
        self,
        descriptor: TrainingRuntimeDescriptor,
        *,
        action: PluginAction,
    ) -> ScenarioPluginEntrypoint:
        return self._entrypoint(
            descriptor,
            action=action,
            service_path="evaluation.services.report_generation_trigger",
            method_name="trigger_report_generation",
        )

    def _entrypoint(
        self,
        descriptor: TrainingRuntimeDescriptor,
        *,
        action: PluginAction,
        service_path: str,
        method_name: str,
        payload: dict[str, object] | None = None,
    ) -> ScenarioPluginEntrypoint:
        return ScenarioPluginEntrypoint(
            scenario_type=self.scenario_type,
            action=action,
            session_id=descriptor.session_id,
            service_path=service_path,
            method_name=method_name,
            runtime_mode=self._runtime_mode(descriptor),
            payload={"scenario_type": self.scenario_type, **(payload or {})},
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

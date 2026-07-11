from __future__ import annotations

import importlib.util
from dataclasses import FrozenInstanceError, fields

import pytest

from common.config import Settings
from training_runtime import (
    LEGACY_SALES_HANDLER_MODULES,
    PresentationScenarioPlugin,
    RuntimeHandlerFactoryKey,
    SalesScenarioPlugin,
    TrainingRuntimeDescriptor,
    build_default_scenario_plugin_registry,
    dispatch_scenario_plugin,
    get_scenario_plugin,
    legacy_sales_handlers_absent,
)

REQUIRED_PLUGIN_METHODS = (
    "on_session_start",
    "on_session_end",
    "select_runtime_handler",
    "build_evidence",
    "trigger_evaluation",
    "build_report_view",
    "diagnostics",
)


def test_should_discover_sales_and_presentation_plugins() -> None:
    registry = build_default_scenario_plugin_registry()

    discovered = {plugin.scenario_type: type(plugin) for plugin in registry.list_plugins()}

    assert discovered == {
        "presentation": PresentationScenarioPlugin,
        "sales": SalesScenarioPlugin,
    }


def test_should_dispatch_different_plugins_by_scenario_type_and_descriptor() -> None:
    sales_descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="stepfun_realtime",
    )
    presentation_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-session",
        scenario_type="presentation",
        voice_mode="legacy",
    )

    assert isinstance(get_scenario_plugin("sales"), SalesScenarioPlugin)
    assert isinstance(dispatch_scenario_plugin(sales_descriptor), SalesScenarioPlugin)
    assert isinstance(
        dispatch_scenario_plugin(presentation_descriptor),
        PresentationScenarioPlugin,
    )


def test_should_expose_required_shared_interface_methods() -> None:
    sales_plugin = get_scenario_plugin("sales")
    presentation_plugin = get_scenario_plugin("presentation")

    for plugin in (sales_plugin, presentation_plugin):
        for method_name in REQUIRED_PLUGIN_METHODS:
            assert callable(getattr(plugin, method_name))


def test_should_return_shared_evaluation_evidence_and_report_entrypoints() -> None:
    sales_descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="stepfun_realtime",
    )
    presentation_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-session",
        scenario_type="presentation",
        voice_mode="legacy",
    )

    sales = get_scenario_plugin("sales")
    presentation = get_scenario_plugin("presentation")

    assert sales.build_evidence(sales_descriptor).service_path == (
        "common.conversation.session_evidence.SessionEvidenceService"
    )
    assert presentation.build_evidence(presentation_descriptor).method_name == "get_projection"
    assert sales.trigger_evaluation(sales_descriptor).method_name == (
        "trigger_report_generation"
    )
    assert presentation.trigger_evaluation(presentation_descriptor).payload == {
        "scenario_type": "presentation"
    }
    assert sales.build_report_view(sales_descriptor).service_path.endswith(
        "TrainingReportSnapshotService"
    )
    assert presentation.build_report_view(presentation_descriptor).method_name == (
        "_get_snapshot_for_session"
    )


def test_should_keep_sales_plugin_stepfun_only_and_legacy_handlers_absent() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="legacy",
    )
    plugin = get_scenario_plugin("sales")

    start = plugin.on_session_start(descriptor)
    diagnostics = plugin.diagnostics()

    assert start.runtime_mode == "stepfun_realtime"
    assert start.service_path == "sales_bot.websocket.stepfun_realtime_handler"
    assert start.method_name == "create_stepfun_realtime_handler"
    assert diagnostics.runtime_family == "stepfun_only"
    assert diagnostics.details["legacy_handlers_absent"] == {
        module: True for module in LEGACY_SALES_HANDLER_MODULES
    }
    assert legacy_sales_handlers_absent() == {
        module: importlib.util.find_spec(module) is None
        for module in LEGACY_SALES_HANDLER_MODULES
    }


def test_should_select_sales_stepfun_runtime_handler() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="legacy",
    )
    plugin = get_scenario_plugin("sales")

    selection = plugin.select_runtime_handler(descriptor)

    assert selection.scenario_type == "sales"
    assert selection.runtime_mode == "stepfun_realtime"
    assert selection.websocket_route == "/ws/sales/{session_id}"
    assert selection.handler_factory_path == "sales_bot.websocket.stepfun_realtime_handler"
    assert selection.handler_factory_name == "create_stepfun_realtime_handler"


def test_should_keep_presentation_training_flow_entrypoints() -> None:
    legacy_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-legacy",
        scenario_type="presentation",
        voice_mode="legacy",
    )
    stepfun_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-stepfun",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    plugin = get_scenario_plugin("presentation")

    legacy_start = plugin.on_session_start(legacy_descriptor)
    stepfun_start = plugin.on_session_start(stepfun_descriptor)
    diagnostics = plugin.diagnostics()

    assert legacy_start.runtime_mode == "legacy"
    assert legacy_start.service_path.endswith("PresentationWebSocketHandler")
    assert stepfun_start.runtime_mode == "stepfun_realtime"
    assert stepfun_start.service_path.endswith("PresentationRealtimeEngineHandler")
    assert diagnostics.runtime_family == "presentation_training_flow"


def test_should_select_presentation_runtime_handler_by_voice_mode() -> None:
    legacy_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-legacy",
        scenario_type="presentation",
        voice_mode="legacy",
    )
    stepfun_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-stepfun",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    plugin = get_scenario_plugin("presentation")

    legacy_selection = plugin.select_runtime_handler(legacy_descriptor)
    stepfun_selection = plugin.select_runtime_handler(stepfun_descriptor)

    assert legacy_selection.scenario_type == "presentation"
    assert legacy_selection.runtime_mode == "legacy"
    assert legacy_selection.websocket_route == "/ws/presentation/{session_id}"
    assert legacy_selection.handler_factory_path == (
        "presentation_coach.websocket.presentation_handler"
    )
    assert legacy_selection.handler_factory_name == "PresentationWebSocketHandler"
    assert stepfun_selection.runtime_mode == "stepfun_realtime"
    assert stepfun_selection.websocket_route == "/ws/presentation/{session_id}"
    assert stepfun_selection.handler_factory_path == (
        "presentation_coach.websocket.presentation_realtime_engine_handler"
    )
    assert stepfun_selection.handler_factory_name == "PresentationRealtimeEngineHandler"


def test_presentation_stepfun_defaults_to_engine_facade() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-engine",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    plugin = PresentationScenarioPlugin(rollout_resolver=lambda: True)

    selection = plugin.select_runtime_handler(descriptor)

    assert selection.handler_factory_path == (
        "presentation_coach.websocket.presentation_realtime_engine_handler"
    )
    assert selection.handler_factory_name == "PresentationRealtimeEngineHandler"
    assert selection.factory_key is RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE


def test_presentation_stepfun_flag_false_atomically_selects_legacy_adapter() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-rollback",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    plugin = PresentationScenarioPlugin(rollout_resolver=lambda: False)

    selection = plugin.select_runtime_handler(descriptor)

    assert selection.handler_factory_path == (
        "presentation_coach.websocket.presentation_stepfun_realtime_handler"
    )
    assert selection.handler_factory_name == "LegacyPresentationStepFunRealtimeHandler"
    assert selection.factory_key is None


def test_presentation_rollout_resolver_is_read_once_per_atomic_selection() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-atomic",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    values = iter((True, False))
    calls = 0

    def changing_resolver() -> bool:
        nonlocal calls
        calls += 1
        return next(values)

    selection = PresentationScenarioPlugin(
        rollout_resolver=changing_resolver
    ).select_runtime_handler(descriptor)

    assert calls == 1
    assert selection.handler_factory_name == "PresentationRealtimeEngineHandler"
    assert selection.factory_key is RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE


def test_runtime_handler_selection_is_immutable_hashable_and_declarative() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-declarative",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )
    selection = PresentationScenarioPlugin(
        rollout_resolver=lambda: True
    ).select_runtime_handler(descriptor)

    assert isinstance(hash(selection), int)
    assert not hasattr(selection, "handler_factory_kwargs")
    for definition in fields(selection):
        value = getattr(selection, definition.name)
        assert not isinstance(value, dict)
        assert not callable(value)
    with pytest.raises(FrozenInstanceError):
        selection.factory_key = None  # type: ignore[misc]


def test_presentation_rollout_does_not_change_legacy_voice_mode() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-legacy-voice",
        scenario_type="presentation",
        voice_mode="legacy",
    )

    for enabled in (True, False):
        selection = PresentationScenarioPlugin(
            rollout_resolver=lambda enabled=enabled: enabled
        ).select_runtime_handler(descriptor)
        assert selection.handler_factory_path == (
            "presentation_coach.websocket.presentation_handler"
        )
        assert selection.handler_factory_name == "PresentationWebSocketHandler"


def test_presentation_rollout_diagnostics_identify_selected_and_rollback_paths() -> None:
    enabled = PresentationScenarioPlugin(
        rollout_resolver=lambda: True
    ).diagnostics().details
    disabled = PresentationScenarioPlugin(
        rollout_resolver=lambda: False
    ).diagnostics().details

    assert enabled["realtime_engine_enabled"] is True
    assert enabled["selected_stepfun_runtime"] == "presentation_realtime_engine"
    assert disabled["realtime_engine_enabled"] is False
    assert disabled["selected_stepfun_runtime"] == "legacy_presentation_stepfun"
    assert enabled["rollback_handler"].endswith(
        "LegacyPresentationStepFunRealtimeHandler"
    )


def test_presentation_realtime_engine_setting_defaults_true_and_supports_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PRESENTATION_REALTIME_ENGINE_ENABLED", raising=False)
    assert Settings().PRESENTATION_REALTIME_ENGINE_ENABLED is True

    monkeypatch.setenv("PRESENTATION_REALTIME_ENGINE_ENABLED", "false")
    assert Settings().PRESENTATION_REALTIME_ENGINE_ENABLED is False


@pytest.mark.parametrize("value", ["true", " 1 ", "YES", "on"])
def test_provider_port_setting_accepts_normalized_truthy_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", value)

    assert Settings().REALTIME_PROVIDER_PORT_ENABLED is True


@pytest.mark.parametrize("value", ["false", " 0 ", "NO", "off"])
def test_provider_port_setting_accepts_normalized_falsy_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", value)

    assert Settings().REALTIME_PROVIDER_PORT_ENABLED is False


def test_provider_port_setting_defaults_true_and_unknown_fails_safe_without_raw_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import common.config as config_module

    warnings: list[tuple[str, dict[str, object]]] = []

    class CapturingLogger:
        def warning(self, event: str, **fields: object) -> None:
            warnings.append((event, fields))

    monkeypatch.setattr(config_module, "logger", CapturingLogger(), raising=False)
    monkeypatch.delenv("REALTIME_PROVIDER_PORT_ENABLED", raising=False)
    assert Settings().REALTIME_PROVIDER_PORT_ENABLED is True

    secret_value = "unexpected-secret-flag-value"
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", secret_value)

    assert Settings().REALTIME_PROVIDER_PORT_ENABLED is False
    assert warnings == [
        (
            "invalid_server_rollout_flag",
            {
                "flag_name": "REALTIME_PROVIDER_PORT_ENABLED",
                "fallback": False,
            },
        )
    ]
    assert secret_value not in repr(warnings)


def test_should_reject_unknown_scenario_type() -> None:
    with pytest.raises(KeyError, match="Unsupported training scenario plugin"):
        get_scenario_plugin("roleplay")


def test_sales_runtime_selection_points_to_existing_factory() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="stepfun_realtime",
    )
    selection = get_scenario_plugin("sales").select_runtime_handler(descriptor)

    module = __import__(selection.handler_factory_path, fromlist=[selection.handler_factory_name])
    factory = getattr(module, selection.handler_factory_name)

    assert callable(factory)

from __future__ import annotations

import importlib.util

import pytest

from training_runtime import (
    PresentationScenarioPlugin,
    SalesScenarioPlugin,
    TrainingRuntimeDescriptor,
    build_default_scenario_plugin_registry,
    dispatch_scenario_plugin,
    get_scenario_plugin,
)

REQUIRED_PLUGIN_METHODS = (
    "on_session_start",
    "on_session_end",
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
        "sales_bot.websocket.base_sales_handler": True,
        "sales_bot.websocket.enhanced_handler": True,
        "sales_bot.websocket.simple_handler": True,
    }
    assert importlib.util.find_spec("sales_bot.websocket.base_sales_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.enhanced_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.simple_handler") is None


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
    assert stepfun_start.service_path.endswith("PresentationStepFunRealtimeHandler")
    assert diagnostics.runtime_family == "presentation_training_flow"


def test_should_reject_unknown_scenario_type() -> None:
    with pytest.raises(KeyError, match="Unsupported training scenario plugin"):
        get_scenario_plugin("roleplay")

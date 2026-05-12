"""Training runtime descriptor and plugin exports."""

from .models import TrainingRuntimeDescriptor, TrainingRuntimeSubject
from .plugins import (
    LEGACY_SALES_HANDLER_MODULES,
    PresentationScenarioPlugin,
    SalesScenarioPlugin,
    ScenarioPluginDiagnostics,
    ScenarioPluginEntrypoint,
    ScenarioPluginRegistry,
    ScenarioTrainingPlugin,
    build_default_scenario_plugin_registry,
    dispatch_scenario_plugin,
    get_scenario_plugin,
    legacy_sales_handlers_absent,
)
from .service import build_training_runtime_descriptor

__all__ = [
    "PresentationScenarioPlugin",
    "LEGACY_SALES_HANDLER_MODULES",
    "SalesScenarioPlugin",
    "ScenarioPluginDiagnostics",
    "ScenarioPluginEntrypoint",
    "ScenarioPluginRegistry",
    "ScenarioTrainingPlugin",
    "TrainingRuntimeDescriptor",
    "TrainingRuntimeSubject",
    "build_default_scenario_plugin_registry",
    "build_training_runtime_descriptor",
    "dispatch_scenario_plugin",
    "get_scenario_plugin",
    "legacy_sales_handlers_absent",
]

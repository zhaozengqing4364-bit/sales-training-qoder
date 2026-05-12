"""Training runtime descriptor and plugin exports."""

from .models import TrainingRuntimeDescriptor, TrainingRuntimeSubject
from .plugins import (
    PresentationScenarioPlugin,
    SalesScenarioPlugin,
    ScenarioPluginDiagnostics,
    ScenarioPluginEntrypoint,
    ScenarioPluginRegistry,
    ScenarioTrainingPlugin,
    build_default_scenario_plugin_registry,
    dispatch_scenario_plugin,
    get_scenario_plugin,
)
from .service import build_training_runtime_descriptor

__all__ = [
    "PresentationScenarioPlugin",
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
]

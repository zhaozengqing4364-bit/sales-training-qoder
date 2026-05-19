"""Training runtime descriptor and plugin exports."""

from .models import TrainingRuntimeDescriptor, TrainingRuntimeSubject
from .plugins import (
    LEGACY_SALES_HANDLER_MODULES,
    PresentationScenarioPlugin,
    SalesScenarioPlugin,
    ScenarioPluginDiagnostics,
    ScenarioPluginEntrypoint,
    ScenarioPluginRegistry,
    ScenarioRuntimeHandlerSelection,
    ScenarioTrainingPlugin,
    build_default_scenario_plugin_registry,
    dispatch_scenario_plugin,
    get_scenario_plugin,
    legacy_sales_handlers_absent,
)
from .service import build_training_runtime_descriptor
from .stepfun_transport import (
    StepFunSessionConfig,
    StepFunTransport,
    build_stepfun_session_update_payload,
)

__all__ = [
    "PresentationScenarioPlugin",
    "LEGACY_SALES_HANDLER_MODULES",
    "SalesScenarioPlugin",
    "ScenarioPluginDiagnostics",
    "ScenarioPluginEntrypoint",
    "ScenarioPluginRegistry",
    "ScenarioRuntimeHandlerSelection",
    "ScenarioTrainingPlugin",
    "TrainingRuntimeDescriptor",
    "TrainingRuntimeSubject",
    "StepFunSessionConfig",
    "StepFunTransport",
    "build_default_scenario_plugin_registry",
    "build_stepfun_session_update_payload",
    "build_training_runtime_descriptor",
    "dispatch_scenario_plugin",
    "get_scenario_plugin",
    "legacy_sales_handlers_absent",
]

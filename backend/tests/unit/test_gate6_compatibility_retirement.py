from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
from pathlib import Path

import yaml
from scripts.architecture_dependency_guard import (
    collect_edges,
    strongly_connected_components,
)

from training_runtime import plugins

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
WEB_SRC = REPO_ROOT / "web" / "src"
POLICY_PATH = REPO_ROOT / "docs" / "architecture" / "module-dependency-policy.yaml"

EXPECTED_FACTORY_KEYS = {
    "sales_stepfun",
    "presentation_legacy",
    "presentation_stepfun_rollback",
    "presentation_realtime_engine",
}
EXPECTED_REMAINING_SCC = {
    "agent",
    "common",
    "curriculum_practice",
    "evaluation",
    "prompt_templates",
    "sales_trainer",
    "support",
}


def _policy() -> dict[str, object]:
    value = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _actual_edges() -> set[tuple[str, str]]:
    policy = _policy()
    packages = {str(item) for item in policy["packages"]}  # type: ignore[index]
    return set(collect_edges(BACKEND_SRC, packages))


def _absolute_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _python_module_importer_count(module: str) -> int:
    count = 0
    for path in BACKEND_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.ImportFrom) and node.module == module
            or isinstance(node, ast.Import)
            and any(alias.name == module for alias in node.names)
            for node in ast.walk(tree)
        ):
            count += 1
    return count


def _frontend_type_barrel_importer_count() -> int:
    return sum(
        1
        for path in WEB_SRC.rglob("*.ts*")
        if 'from "@/lib/api/types"' in path.read_text(encoding="utf-8")
        or "from '@/lib/api/types'" in path.read_text(encoding="utf-8")
    )


def test_runtime_selection_is_closed_data_without_executable_strings() -> None:
    selection_fields = {
        field.name
        for field in dataclasses.fields(plugins.ScenarioRuntimeHandlerSelection)
    }

    assert selection_fields == {
        "scenario_type",
        "runtime_mode",
        "websocket_route",
        "factory_key",
    }
    assert {item.value for item in plugins.RuntimeHandlerFactoryKey} == (
        EXPECTED_FACTORY_KEYS
    )


def test_scenario_plugin_surface_contains_no_unused_executable_descriptors() -> None:
    protocol_methods = {
        node.name
        for node in ast.parse(
            (BACKEND_SRC / "training_runtime" / "plugins.py").read_text(
                encoding="utf-8"
            )
        ).body
        if isinstance(node, ast.ClassDef) and node.name == "ScenarioTrainingPlugin"
        for node in node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert not hasattr(plugins, "ScenarioPluginEntrypoint")
    assert protocol_methods == {"select_runtime_handler", "diagnostics"}


def test_application_root_factory_map_is_exhaustive() -> None:
    composition = importlib.import_module("runtime_composition")
    sales_router = importlib.import_module("sales_bot.websocket.router")

    presentation_keys = set(composition.PRESENTATION_RUNTIME_HANDLER_FACTORIES)
    sales_keys = set(sales_router.RUNTIME_HANDLER_FACTORIES)

    assert presentation_keys.isdisjoint(sales_keys)
    assert presentation_keys | sales_keys == set(plugins.RuntimeHandlerFactoryKey)


def test_presentation_runtime_is_root_composed_from_domain_behavior_and_transport() -> None:
    composition = importlib.import_module("runtime_composition")
    presentation = importlib.import_module(
        "presentation_coach.websocket.presentation_stepfun_realtime_handler"
    )

    assert hasattr(presentation, "PresentationStepFunRuntimeMixin")
    assert not hasattr(presentation, "LegacyPresentationStepFunRealtimeHandler")
    assert composition.PresentationStepFunRealtimeAdapter.__mro__[1:4] == (
        presentation.PresentationStepFunRuntimeMixin,
        importlib.import_module(
            "training_runtime.realtime.stepfun_adapter_port"
        ).StepFunRuntimeAdapterPort,
        importlib.import_module(
            "sales_bot.websocket.stepfun_realtime_handler"
        ).StepFunRealtimeSharedHandler,
    )


def test_presentation_engine_facade_requires_root_adapter_injection() -> None:
    handler = importlib.import_module(
        "presentation_coach.websocket.presentation_realtime_engine_handler"
    ).PresentationRealtimeEngineHandler
    parameter = inspect.signature(handler).parameters["runtime_adapter_factory"]

    assert parameter.default is inspect.Parameter.empty


def test_presentation_domain_no_longer_imports_sales_domain() -> None:
    presentation_runtime = (
        BACKEND_SRC
        / "presentation_coach"
        / "websocket"
        / "presentation_stepfun_realtime_handler.py"
    )

    assert "sales_bot" not in _absolute_import_roots(presentation_runtime)


def test_common_roleplay_forwarding_facade_is_retired() -> None:
    assert not (BACKEND_SRC / "common" / "roleplay_contracts.py").exists()
    assert _python_module_importer_count("common.roleplay_contracts") == 0


def test_gate6_dependency_graph_removes_presentation_sales_edge_without_expansion() -> None:
    policy = _policy()
    packages = {str(item) for item in policy["packages"]}  # type: ignore[index]
    edges = _actual_edges()
    components = {
        frozenset(component)
        for component in strongly_connected_components(packages, edges)
        if len(component) > 1
    }

    assert ("presentation_coach", "sales_bot") not in edges
    assert len(edges) <= 51
    assert components == {frozenset(EXPECTED_REMAINING_SCC)}


def test_high_fan_in_facades_are_retained_until_their_exit_conditions_hold() -> None:
    assert _python_module_importer_count("common.db.models") >= 222
    assert _frontend_type_barrel_importer_count() >= 262

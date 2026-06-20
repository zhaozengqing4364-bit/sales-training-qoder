from __future__ import annotations

import ast
import re
from pathlib import Path

from sqlalchemy import CheckConstraint

from common.db.models import (
    PracticeSession,
    SessionStatus,
    TrainingTask,
    TrainingTaskStatus,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = BACKEND_ROOT / "src"

DOMAIN_PACKAGES = {
    "admin",
    "agent",
    "curriculum_analytics",
    "curriculum_practice",
    "evaluation",
    "presentation_coach",
    "prompt_templates",
    "sales_bot",
    "sales_trainer",
    "supervisor",
    "support",
    "training_runtime",
}

COMMON_REVERSE_DEPENDENCY_ALLOWLIST = {
    "common/ai/llm_service.py": {"prompt_templates"},
    "common/analytics/runtime_metrics_service.py": {"agent"},
    "common/api/practice.py": {"agent", "evaluation", "prompt_templates"},
    "common/api/training.py": {"agent"},
    "common/conversation/replay.py": {"agent", "curriculum_practice"},
    "common/db/session_lifecycle.py": {"evaluation"},
    "common/db/voice_policy_snapshot.py": {"agent"},
}


def _constraint_allowed_values(table, constraint_name: str) -> set[str]:
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == constraint_name:
            return set(re.findall(r"'([^']+)'", str(constraint.sqltext)))
    raise AssertionError(f"Missing check constraint: {constraint_name}")


def _python_files_under(relative_dir: str) -> list[Path]:
    return sorted(
        path
        for path in (BACKEND_SRC / relative_dir).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imported


def _top_level_modules(path: Path) -> set[str]:
    return {module.split(".", 1)[0] for module in _imported_modules(path)}


def _relative_backend_src_path(path: Path) -> str:
    return path.relative_to(BACKEND_SRC).as_posix()


def test_should_keep_training_task_and_practice_session_statuses_free_of_runtime_states() -> None:
    forbidden_runtime_states = {"preflight", "reconnect", "stage"}
    training_task_statuses = {item.value for item in TrainingTaskStatus}
    practice_session_statuses = {item.value for item in SessionStatus}

    assert training_task_statuses == {
        "assigned",
        "in_progress",
        "completed",
        "expired",
        "cancelled",
    }
    assert practice_session_statuses == {
        "preparing",
        "in_progress",
        "paused",
        "completed",
        "scoring",
    }
    assert training_task_statuses.isdisjoint(forbidden_runtime_states)
    assert practice_session_statuses.isdisjoint(forbidden_runtime_states)
    assert _constraint_allowed_values(
        PracticeSession.__table__,
        "ck_session_status",
    ) == practice_session_statuses
    assert _constraint_allowed_values(
        TrainingTask.__table__,
        "ck_training_tasks_status",
    ) == training_task_statuses


def test_stepfun_realtime_requirements_include_python_socks() -> None:
    requirements_path = Path(__file__).resolve().parents[2] / "requirements.txt"
    requirements = requirements_path.read_text(encoding="utf-8").splitlines()

    assert any(line.startswith("python-socks>=") for line in requirements)


def test_should_not_restore_legacy_sales_handler_modules() -> None:
    websocket_dir = Path(__file__).resolve().parents[2] / "src" / "sales_bot" / "websocket"

    assert not (websocket_dir / "base_sales_handler.py").exists()
    assert not (websocket_dir / "enhanced_handler.py").exists()
    assert not (websocket_dir / "simple_handler.py").exists()


def test_should_keep_common_reverse_domain_dependencies_pinned() -> None:
    unexpected: dict[str, set[str]] = {}

    for path in _python_files_under("common"):
        rel_path = _relative_backend_src_path(path)
        actual_domains = _top_level_modules(path) & DOMAIN_PACKAGES
        allowed_domains = COMMON_REVERSE_DEPENDENCY_ALLOWLIST.get(rel_path, set())
        unexpected_domains = actual_domains - allowed_domains
        if unexpected_domains:
            unexpected[rel_path] = unexpected_domains

    assert unexpected == {}


def test_should_keep_training_runtime_descriptor_imports_compatible() -> None:
    from common.runtime_descriptor import (
        TrainingRuntimeDescriptor as NeutralDescriptor,
    )
    from common.runtime_descriptor import TrainingRuntimeSubject as NeutralSubject
    from training_runtime.models import (
        TrainingRuntimeDescriptor as LegacyDescriptor,
    )
    from training_runtime.models import TrainingRuntimeSubject as LegacySubject

    assert LegacyDescriptor is NeutralDescriptor
    assert LegacySubject is NeutralSubject


def test_should_keep_sales_trainer_out_of_realtime_runtime_modules() -> None:
    forbidden_prefixes = {
        "sales_bot",
        "training_runtime",
        "common.api.practice",
        "common.services.practice_service",
        "common.services.practice_session_service",
        "common.services.runtime_gate",
    }
    violations: dict[str, set[str]] = {}

    for path in _python_files_under("sales_trainer"):
        forbidden_imports = {
            module
            for module in _imported_modules(path)
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden_prefixes
            )
        }
        if forbidden_imports:
            violations[_relative_backend_src_path(path)] = forbidden_imports

    assert violations == {}


def test_should_keep_support_runtime_domains_behind_contributors() -> None:
    forbidden_runtime_domains = {
        "curriculum_practice",
        "evaluation",
        "presentation_coach",
        "sales_bot",
        "sales_trainer",
        "training_runtime",
    }
    violations: dict[str, set[str]] = {}

    for path in _python_files_under("support"):
        forbidden_imports = _top_level_modules(path) & forbidden_runtime_domains
        if forbidden_imports:
            violations[_relative_backend_src_path(path)] = forbidden_imports

    assert violations == {}


def test_should_keep_cross_domain_adapters_from_exporting_foreign_orm_models() -> None:
    adapter_exports = {
        "sales_trainer/services/curriculum_practice_adapter.py": {
            "LearningChapter",
            "LearningContent",
            "QuestionCategory",
            "QuestionItem",
        },
        "curriculum_practice/services/sales_trainer_revision_adapter.py": {
            "SalesTrainerAssetRevision",
        },
    }

    for relative_path, forbidden_exports in adapter_exports.items():
        module_path = BACKEND_SRC / relative_path
        namespace: dict[str, object] = {}
        exec(module_path.read_text(encoding="utf-8"), namespace)
        exported = set(namespace.get("__all__", []))
        assert exported.isdisjoint(forbidden_exports), relative_path

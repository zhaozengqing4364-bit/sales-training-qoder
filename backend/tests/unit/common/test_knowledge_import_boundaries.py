"""Import-boundary regression tests for common knowledge code.

Lane B/Q-01 starts by protecting the slice that enforces KB lock.  The common
knowledge package may be reused by sales/presentation runtimes, but it must not
import those upper scenario packages itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_SCENARIO_MODULES = {"sales_bot", "presentation_coach", "evaluation"}
KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "src" / "common" / "knowledge"


def _iter_imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def test_common_knowledge_has_no_scenario_reverse_imports() -> None:
    violations: list[str] = []
    for path in sorted(KNOWLEDGE_ROOT.rglob("*.py")):
        for lineno, module in _iter_imported_modules(path):
            top_level = module.split(".", 1)[0]
            if top_level in FORBIDDEN_SCENARIO_MODULES:
                rel_path = path.relative_to(KNOWLEDGE_ROOT.parents[2])
                violations.append(f"{rel_path}:{lineno} imports {module}")

    assert violations == []

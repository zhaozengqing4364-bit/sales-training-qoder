from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

Edge = tuple[str, str]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC_ROOT = REPO_ROOT / "backend" / "src"
DEFAULT_POLICY = (
    REPO_ROOT / "docs" / "architecture" / "module-dependency-policy.yaml"
)


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    func = node.func
    direct = isinstance(func, ast.Name) and func.id in {
        "import_module",
        "__import__",
    }
    attribute = isinstance(func, ast.Attribute) and func.attr in {
        "import_module",
        "__import__",
    }
    return first.value if direct or attribute else None


def _imported_modules(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append((node.module, node.lineno))
        elif isinstance(node, ast.Call):
            dynamic = _literal_dynamic_import(node)
            if dynamic:
                modules.append((dynamic, node.lineno))
    return modules


def collect_edges(
    src_root: Path,
    packages: set[str],
) -> dict[Edge, set[str]]:
    edges: dict[Edge, set[str]] = defaultdict(set)
    for source in sorted(packages):
        package_root = src_root / source
        if not package_root.exists():
            continue
        for path in sorted(package_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            location = path.relative_to(src_root).as_posix()
            for module, lineno in _imported_modules(path):
                target = module.split(".", 1)[0]
                if target in packages and target != source:
                    edges[(source, target)].add(f"{location}:{lineno}")
    return dict(edges)


def strongly_connected_components(
    packages: Iterable[str],
    edges: Iterable[Edge],
) -> list[frozenset[str]]:
    graph: dict[str, set[str]] = {package: set() for package in packages}
    for source, target in edges:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())

    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[frozenset[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph[node]):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])

        if lowlinks[node] != indexes[node]:
            return
        component: set[str] = set()
        while stack:
            target = stack.pop()
            on_stack.remove(target)
            component.add(target)
            if target == node:
                break
        components.append(frozenset(component))

    for package in sorted(graph):
        if package not in indexes:
            visit(package)
    return components


def _required_mapping(
    policy: object,
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(policy, dict):
        return {}, ["Policy document must be a mapping"]
    violations: list[str] = []
    required = {
        "version",
        "packages",
        "stable_edges",
        "temporary_edges",
        "baseline_sccs",
    }
    for key in sorted(required - set(policy)):
        violations.append(f"Policy is missing required field: {key}")
    if policy.get("version") != 1:
        violations.append("Policy version must be 1")
    return policy, violations


def _packages(policy: dict[str, Any]) -> tuple[set[str], list[str]]:
    raw = policy.get("packages")
    if not isinstance(raw, list) or not raw:
        return set(), ["Policy packages must be a non-empty list"]
    values = [str(item).strip() for item in raw]
    violations: list[str] = []
    if any(not item for item in values):
        violations.append("Policy packages must contain non-empty names")
    if len(values) != len(set(values)):
        violations.append("Policy packages must not contain duplicates")
    return {item for item in values if item}, violations


def _edge(value: object, *, context: str) -> tuple[Edge | None, str | None]:
    if not isinstance(value, list) or len(value) != 2:
        return None, f"{context} must contain [source, target]: {value!r}"
    source, target = (str(item).strip() for item in value)
    if not source or not target or source == target:
        return None, f"{context} must contain distinct non-empty packages: {value!r}"
    return (source, target), None


def _stable_edges(
    policy: dict[str, Any],
    packages: set[str],
) -> tuple[set[Edge], list[str]]:
    raw = policy.get("stable_edges")
    if not isinstance(raw, list):
        return set(), ["Policy stable_edges must be a list"]
    edges: set[Edge] = set()
    violations: list[str] = []
    for index, value in enumerate(raw):
        edge, violation = _edge(value, context=f"stable_edges[{index}]")
        if violation:
            violations.append(violation)
            continue
        assert edge is not None
        if not set(edge) <= packages:
            violations.append(
                f"stable_edges[{index}] references undeclared package: {edge}"
            )
        if edge in edges:
            violations.append(f"Duplicate stable dependency: {edge[0]}->{edge[1]}")
        edges.add(edge)
    return edges, violations


def _temporary_edges(
    policy: dict[str, Any],
    packages: set[str],
    *,
    today: date,
) -> tuple[set[Edge], list[str]]:
    raw = policy.get("temporary_edges")
    if not isinstance(raw, list):
        return set(), ["Policy temporary_edges must be a list"]
    edges: set[Edge] = set()
    violations: list[str] = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            violations.append(
                f"temporary_edges[{index}] must be a mapping: {value!r}"
            )
            continue
        required = (
            "source",
            "targets",
            "owner",
            "reason",
            "retire_when",
            "expires_on",
        )
        missing = [key for key in required if key not in value]
        if missing:
            violations.append(
                f"temporary_edges[{index}] is missing required fields: "
                + ", ".join(missing)
            )
            continue

        source = str(value["source"]).strip()
        owner = str(value["owner"]).strip()
        reason = str(value["reason"]).strip()
        retire_when = str(value["retire_when"]).strip()
        expires_on = str(value["expires_on"]).strip()
        raw_targets = value["targets"]
        if not isinstance(raw_targets, list):
            targets: list[str] = []
        else:
            targets = [str(target).strip() for target in raw_targets]

        empty_fields = [
            name
            for name, content in (
                ("source", source),
                ("targets", targets),
                ("owner", owner),
                ("reason", reason),
                ("retire_when", retire_when),
                ("expires_on", expires_on),
            )
            if not content
        ]
        if empty_fields:
            violations.append(
                f"temporary_edges[{index}] has empty required fields: "
                + ", ".join(empty_fields)
            )
            continue
        if len(targets) != len(set(targets)):
            violations.append(
                f"temporary_edges[{index}] targets must not contain duplicates"
            )
        try:
            expiry = date.fromisoformat(expires_on)
        except ValueError:
            violations.append(
                f"Invalid expires_on for temporary_edges[{index}]: {expires_on}"
            )
        else:
            if expiry < today:
                violations.append(
                    f"Expired temporary dependency group {source}->{sorted(targets)} "
                    f"owned by {owner}: {expires_on}"
                )

        for target in targets:
            edge = (source, target)
            if source == target:
                violations.append(
                    f"temporary_edges[{index}] contains self dependency: {source}"
                )
            if not set(edge) <= packages:
                violations.append(
                    f"temporary_edges[{index}] references undeclared package: {edge}"
                )
            if edge in edges:
                violations.append(
                    f"Duplicate temporary dependency: {source}->{target}"
                )
            edges.add(edge)
    return edges, violations


def _baseline_sccs(
    policy: dict[str, Any],
    packages: set[str],
) -> tuple[list[frozenset[str]], list[str]]:
    raw = policy.get("baseline_sccs")
    if not isinstance(raw, list):
        return [], ["Policy baseline_sccs must be a list"]
    baselines: list[frozenset[str]] = []
    violations: list[str] = []
    seen_packages: set[str] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, list) or len(value) < 2:
            violations.append(
                f"baseline_sccs[{index}] must contain at least two packages"
            )
            continue
        component = frozenset(str(item).strip() for item in value)
        if len(component) != len(value) or "" in component:
            violations.append(
                f"baseline_sccs[{index}] must contain unique non-empty packages"
            )
        undeclared = component - packages
        if undeclared:
            violations.append(
                f"baseline_sccs[{index}] references undeclared packages: "
                + ", ".join(sorted(undeclared))
            )
        overlap = component & seen_packages
        if overlap:
            violations.append(
                f"baseline_sccs[{index}] overlaps another baseline: "
                + ", ".join(sorted(overlap))
            )
        seen_packages.update(component)
        baselines.append(component)
    return baselines, violations


def validate_repository(
    *,
    src_root: Path = DEFAULT_SRC_ROOT,
    policy_path: Path = DEFAULT_POLICY,
    today: date | None = None,
) -> list[str]:
    violations: list[str] = []
    try:
        raw_policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"Dependency policy does not exist: {policy_path}"]
    except yaml.YAMLError as exc:
        return [f"Dependency policy is invalid YAML: {exc}"]

    policy, policy_violations = _required_mapping(raw_policy)
    violations.extend(policy_violations)
    packages, package_violations = _packages(policy)
    violations.extend(package_violations)
    stable, stable_violations = _stable_edges(policy, packages)
    violations.extend(stable_violations)
    temporary, temporary_violations = _temporary_edges(
        policy,
        packages,
        today=today or datetime.now(UTC).date(),
    )
    violations.extend(temporary_violations)
    baselines, baseline_violations = _baseline_sccs(policy, packages)
    violations.extend(baseline_violations)

    overlap = stable & temporary
    for source, target in sorted(overlap):
        violations.append(
            f"Dependency cannot be both stable and temporary: {source}->{target}"
        )
    for package in sorted(packages):
        if not (src_root / package).is_dir():
            violations.append(f"Declared package directory is missing: {package}")

    actual_with_locations = collect_edges(src_root, packages)
    actual = set(actual_with_locations)
    for source, target in sorted(actual - stable - temporary):
        locations = ", ".join(sorted(actual_with_locations[(source, target)]))
        violations.append(
            f"Unexpected dependency {source}->{target}: {locations}"
        )
    for source, target in sorted(temporary - actual):
        violations.append(
            f"Stale temporary dependency exception {source}->{target}; "
            "remove it from policy"
        )

    current_sccs = [
        component
        for component in strongly_connected_components(packages, actual)
        if len(component) > 1
    ]
    for component in current_sccs:
        if not any(component <= baseline for baseline in baselines):
            violations.append(
                "Expanded strongly connected component: "
                + ", ".join(sorted(component))
            )
    return sorted(set(violations))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check backend module dependencies",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate repository policy",
    )
    parser.add_argument("--src-root", type=Path, default=DEFAULT_SRC_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    violations = validate_repository(
        src_root=args.src_root.resolve(),
        policy_path=args.policy.resolve(),
    )
    if violations:
        for violation in violations:
            print(f"[architecture] {violation}")
        return 1
    print("[architecture] dependency policy satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

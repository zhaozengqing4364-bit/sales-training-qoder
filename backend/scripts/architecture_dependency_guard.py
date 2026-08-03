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
DEFAULT_FOUNDATION_POLICY = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "newcomer-foundation-guard-policy.yaml"
)

FOUNDATION_PROVIDER_MODULES = {
    "anthropic",
    "dashscope",
    "google.generativeai",
    "openai",
}
FOUNDATION_PROVIDER_INTERNAL_PATHS = {
    "ai_platform.openai_provider",
    "ai_platform.provider",
}
FOUNDATION_PROVIDER_CALLS = {
    "get_llm_service",
    "get_asr_service",
}
FOUNDATION_PROVIDER_METHODS = {
    "apredict",
}
FOUNDATION_HTTP_DECORATORS = {"delete", "get", "patch", "post", "put"}
FOUNDATION_TRANSACTION_METHODS = {"commit", "flush", "rollback"}
FOUNDATION_MUTATION_METHODS = {"add", "delete", "merge"}


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


def _attribute_chain(node: ast.AST) -> tuple[str, ...]:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))


def _foundation_module_paths(
    policy: dict[str, Any],
) -> tuple[dict[str, tuple[str, ...]], list[str]]:
    raw = policy.get("module_paths")
    if not isinstance(raw, dict):
        return {}, ["Foundation policy module_paths must be a mapping"]
    result: dict[str, tuple[str, ...]] = {}
    violations: list[str] = []
    for module, paths in raw.items():
        name = str(module).strip()
        if not name or not isinstance(paths, list) or not paths:
            violations.append(
                f"Foundation module_paths[{module!r}] must be a non-empty list"
            )
            continue
        normalized = tuple(str(path).strip().strip("/") for path in paths)
        if any(not path for path in normalized):
            violations.append(
                f"Foundation module_paths[{name}] contains an empty path"
            )
            continue
        result[name] = normalized
    return result, violations


def _foundation_business_modules(
    policy: dict[str, Any],
) -> tuple[set[str], list[str]]:
    raw = policy.get("business_modules")
    if not isinstance(raw, list) or not raw:
        return set(), ["Foundation policy business_modules must be a non-empty list"]
    modules = [str(item).strip() for item in raw]
    violations: list[str] = []
    if any(not item for item in modules):
        violations.append("Foundation business_modules must contain non-empty names")
    if len(modules) != len(set(modules)):
        violations.append("Foundation business_modules must not contain duplicates")
    return {item for item in modules if item}, violations


def _foundation_stable_edges(
    policy: dict[str, Any],
) -> tuple[set[Edge], list[str]]:
    raw = policy.get("stable_edges")
    if not isinstance(raw, list):
        return set(), ["Foundation policy stable_edges must be a list"]
    edges: set[Edge] = set()
    violations: list[str] = []
    for index, value in enumerate(raw):
        edge, violation = _edge(value, context=f"stable_edges[{index}]")
        if violation:
            violations.append(violation)
            continue
        assert edge is not None
        if edge in edges:
            violations.append(
                f"Duplicate foundation stable dependency: {edge[0]}->{edge[1]}"
            )
        edges.add(edge)
    return edges, violations


def _foundation_import_scope(
    policy: dict[str, Any],
) -> tuple[set[str], set[str], list[str]]:
    raw = policy.get("stable_edge_import_scope")
    if not isinstance(raw, dict):
        return set(), set(), [
            "Foundation policy stable_edge_import_scope must be a mapping"
        ]
    allowed_raw = raw.get("allowed_path_segments")
    forbidden_raw = raw.get("forbidden_path_segments")
    violations: list[str] = []
    if not isinstance(allowed_raw, list) or not allowed_raw:
        violations.append(
            "Foundation stable_edge_import_scope.allowed_path_segments "
            "must be a non-empty list"
        )
        allowed: set[str] = set()
    else:
        allowed = {str(item).strip() for item in allowed_raw if str(item).strip()}
    if not isinstance(forbidden_raw, list) or not forbidden_raw:
        violations.append(
            "Foundation stable_edge_import_scope.forbidden_path_segments "
            "must be a non-empty list"
        )
        forbidden: set[str] = set()
    else:
        forbidden = {
            str(item).strip() for item in forbidden_raw if str(item).strip()
        }
    return allowed, forbidden, violations


def _foundation_source_files(
    src_root: Path,
    module_paths: dict[str, tuple[str, ...]],
    module: str,
) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    violations: list[str] = []
    for relative in module_paths.get(module, ()):
        path = src_root / relative
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if path.is_dir():
            files.extend(
                candidate
                for candidate in sorted(path.rglob("*.py"))
                if "__pycache__" not in candidate.parts
            )
            continue
        violations.append(
            f"Foundation module path does not exist: {module}={relative}"
        )
    return sorted(set(files)), violations


def _foundation_provider_violation(
    tree: ast.AST,
    *,
    location: str,
) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module]
        else:
            modules = []
        for module in modules:
            if (
                module in FOUNDATION_PROVIDER_MODULES
                or any(module.startswith(f"{item}.") for item in FOUNDATION_PROVIDER_MODULES)
                or module in FOUNDATION_PROVIDER_INTERNAL_PATHS
                or any(
                    module.startswith(f"{item}.")
                    for item in FOUNDATION_PROVIDER_INTERNAL_PATHS
                )
            ):
                violations.append(
                    "ARCH_DIRECT_AI_PROVIDER_FORBIDDEN "
                    f"{location}:{node.lineno} imports {module}"
                )
        if not isinstance(node, ast.Call):
            continue
        chain = _attribute_chain(node.func)
        if (
            (chain and chain[-1] in FOUNDATION_PROVIDER_CALLS)
            or (chain and chain[-1] in FOUNDATION_PROVIDER_METHODS)
            or (len(chain) >= 2 and chain[-2:] == ("llm", "apredict"))
        ):
            violations.append(
                "ARCH_DIRECT_AI_PROVIDER_FORBIDDEN "
                f"{location}:{node.lineno} calls {'.'.join(chain)}"
            )
    return violations


def _is_provider_call(node: ast.Call) -> bool:
    chain = _attribute_chain(node.func)
    return bool(
        (chain and chain[-1] in FOUNDATION_PROVIDER_CALLS)
        or (chain and chain[-1] in FOUNDATION_PROVIDER_METHODS)
        or (len(chain) >= 2 and chain[-2:] == ("llm", "apredict"))
    )


def _is_route_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        call = decorator.func if isinstance(decorator, ast.Call) else decorator
        chain = _attribute_chain(call)
        if chain and chain[-1] in FOUNDATION_HTTP_DECORATORS:
            return True
    return False


def _is_database_mutation_call(node: ast.Call) -> bool:
    chain = _attribute_chain(node.func)
    if not chain:
        return False
    method = chain[-1]
    if method in FOUNDATION_TRANSACTION_METHODS:
        return True
    if method not in FOUNDATION_MUTATION_METHODS or len(chain) < 2:
        return False
    receiver = chain[-2].lower()
    return (
        receiver in {"db", "repo", "repository", "session"}
        or receiver.endswith("_repo")
        or receiver.endswith("_repository")
        or receiver.endswith("_session")
    )


def _foundation_delivery_violations(
    tree: ast.AST,
    *,
    location: str,
) -> list[str]:
    violations: list[str] = []
    functions = (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_route_function(node)
    )
    for function in functions:
        body_nodes = list(ast.walk(function))
        has_database_mutation = any(
            isinstance(node, ast.Call) and _is_database_mutation_call(node)
            for node in body_nodes
        )
        has_provider_io = any(
            isinstance(node, ast.Call) and _is_provider_call(node)
            for node in body_nodes
        )
        if has_database_mutation and has_provider_io:
            violations.append(
                "ARCH_DELIVERY_ORCHESTRATION_FORBIDDEN "
                f"{location}:{function.lineno} route {function.name} combines "
                "database mutation and Provider IO"
            )
    return violations


def _foundation_target_for_import(
    module: str,
    module_paths: dict[str, tuple[str, ...]],
) -> str | None:
    candidates: list[tuple[int, str]] = []
    for target, paths in module_paths.items():
        for path in paths:
            prefix = path.removesuffix(".py").replace("/", ".")
            if module == prefix or module.startswith(f"{prefix}."):
                candidates.append((len(prefix), target))
    return max(candidates, default=(0, ""))[1] or None


def _foundation_composition_root(
    policy: dict[str, Any],
    module_paths: dict[str, tuple[str, ...]],
) -> tuple[str | None, set[Edge], list[str]]:
    raw_root = policy.get("composition_root")
    root = str(raw_root).strip() if raw_root is not None else ""
    violations: list[str] = []
    if not root:
        violations.append("Foundation policy composition_root must be non-empty")
        return None, set(), violations
    if root not in module_paths:
        violations.append(
            f"Foundation composition_root has no module_paths entry: {root}"
        )
    raw_edges = policy.get("composition_root_edges")
    if not isinstance(raw_edges, list):
        violations.append("Foundation policy composition_root_edges must be a list")
        return root, set(), violations
    edges: set[Edge] = set()
    for index, value in enumerate(raw_edges):
        edge, violation = _edge(
            value,
            context=f"composition_root_edges[{index}]",
        )
        if violation:
            violations.append(violation)
            continue
        assert edge is not None
        if edge[0] != root:
            violations.append(
                f"composition_root_edges[{index}] must start with {root}: {edge}"
            )
        if edge[1] not in module_paths:
            violations.append(
                "composition_root_edges references target without module_paths: "
                f"{edge[1]}"
            )
        if edge in edges:
            violations.append(
                f"Duplicate composition root dependency: {edge[0]}->{edge[1]}"
            )
        edges.add(edge)
    return root, edges, violations


def _foundation_root_runtime_violations(
    tree: ast.AST,
    *,
    location: str,
) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_database_mutation_call(node):
            violations.append(
                "ARCH_COMPOSITION_ROOT_BUSINESS_MUTATION_FORBIDDEN "
                f"{location}:{node.lineno} calls "
                f"{'.'.join(_attribute_chain(node.func))}"
            )
        if not isinstance(node, ast.Call):
            continue
        chain = _attribute_chain(node.func)
        dynamic_import = _literal_dynamic_import(node)
        dynamic_lookup = bool(
            chain
            and chain[-1] in {"globals", "locals"}
            or chain
            and chain[-1] == "getattr"
            and len(node.args) >= 2
            and not isinstance(node.args[1], ast.Constant)
        )
        if dynamic_import or dynamic_lookup:
            violations.append(
                "ARCH_COMPOSITION_ROOT_SERVICE_LOCATOR_FORBIDDEN "
                f"{location}:{node.lineno} uses dynamic service lookup"
            )
    return violations


def validate_foundation_repository(
    *,
    src_root: Path = DEFAULT_SRC_ROOT,
    policy_path: Path = DEFAULT_FOUNDATION_POLICY,
) -> list[str]:
    try:
        raw_policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"Foundation architecture policy does not exist: {policy_path}"]
    except yaml.YAMLError as exc:
        return [f"Foundation architecture policy is invalid YAML: {exc}"]
    if not isinstance(raw_policy, dict):
        return ["Foundation architecture policy must be a mapping"]
    policy: dict[str, Any] = raw_policy
    violations: list[str] = []
    if policy.get("version") != 1:
        violations.append("Foundation architecture policy version must be 1")
    if policy.get("status") != "enforced":
        violations.append("Foundation architecture policy status must be enforced")

    business_modules, business_violations = _foundation_business_modules(policy)
    stable_edges, stable_violations = _foundation_stable_edges(policy)
    module_paths, path_violations = _foundation_module_paths(policy)
    allowed_segments, forbidden_segments, scope_violations = (
        _foundation_import_scope(policy)
    )
    violations.extend(business_violations)
    violations.extend(stable_violations)
    violations.extend(path_violations)
    violations.extend(scope_violations)
    composition_root, composition_edges, composition_violations = (
        _foundation_composition_root(policy, module_paths)
    )
    violations.extend(composition_violations)

    temporary = policy.get("temporary_exceptions")
    if not isinstance(temporary, list):
        violations.append("Foundation policy temporary_exceptions must be a list")
    else:
        for index, item in enumerate(temporary):
            exception_id = (
                str(item.get("id") or f"index-{index}")
                if isinstance(item, dict)
                else f"index-{index}"
            )
            violations.append(
                f"Foundation temporary exception remains: {exception_id}"
            )

    orm_segments = {
        "models",
        "repositories",
        "repository",
        "sqlalchemy",
        "adapters",
    }
    for source in sorted(business_modules):
        files, file_violations = _foundation_source_files(
            src_root, module_paths, source
        )
        violations.extend(file_violations)
        for path in files:
            location = path.relative_to(src_root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            violations.extend(
                _foundation_provider_violation(tree, location=location)
            )
            violations.extend(
                _foundation_delivery_violations(tree, location=location)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.level == 0
                    and node.module
                ):
                    imported = [node.module]
                else:
                    imported = []
                for module in imported:
                    parts = module.split(".")
                    target = parts[0]
                    if target not in business_modules or target == source:
                        continue
                    if (source, target) not in stable_edges:
                        violations.append(
                            "ARCH_FOUNDATION_EDGE_UNDECLARED "
                            f"{location}:{node.lineno} imports {module}"
                        )
                    segment = parts[1] if len(parts) > 1 else ""
                    if segment in orm_segments:
                        code = "ARCH_CROSS_MODULE_ORM_FORBIDDEN"
                    elif segment in forbidden_segments or segment not in allowed_segments:
                        code = "ARCH_BUSINESS_EDGE_SCOPE_FORBIDDEN"
                    else:
                        continue
                    violations.append(
                        f"{code} {location}:{node.lineno} imports {module}"
                    )
                if source != "newcomer_training" or not isinstance(node, ast.Call):
                    continue
                dynamic = _literal_dynamic_import(node)
                if dynamic:
                    violations.append(
                        "ARCH_DYNAMIC_ACTIVITY_IMPORT_FORBIDDEN "
                        f"{location}:{node.lineno} imports {dynamic}"
                    )

    if composition_root is not None:
        root_files, root_file_violations = _foundation_source_files(
            src_root,
            module_paths,
            composition_root,
        )
        violations.extend(root_file_violations)
        for path in root_files:
            location = path.relative_to(src_root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            violations.extend(
                _foundation_root_runtime_violations(tree, location=location)
            )
            for module, lineno in _imported_modules(path):
                target = _foundation_target_for_import(module, module_paths)
                if target is None or target == composition_root:
                    continue
                if (composition_root, target) not in composition_edges:
                    violations.append(
                        "ARCH_COMPOSITION_ROOT_EDGE_UNDECLARED "
                        f"{location}:{lineno} imports {module}"
                    )

    shared_files, shared_violations = _foundation_source_files(
        src_root, module_paths, "shared_kernel"
    )
    violations.extend(shared_violations)
    for path in shared_files:
        location = path.relative_to(src_root).as_posix()
        for module, lineno in _imported_modules(path):
            if module.split(".", 1)[0] in business_modules:
                violations.append(
                    "ARCH_SHARED_KERNEL_REVERSE_DEPENDENCY "
                    f"{location}:{lineno} imports {module}"
                )
    return sorted(set(violations))


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
    parser.add_argument(
        "--foundation-policy",
        type=Path,
        default=DEFAULT_FOUNDATION_POLICY,
    )
    parser.add_argument(
        "--skip-foundation",
        action="store_true",
        help="skip the newcomer foundation clean-cut policy",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    violations = validate_repository(
        src_root=args.src_root.resolve(),
        policy_path=args.policy.resolve(),
    )
    if not args.skip_foundation:
        violations.extend(
            validate_foundation_repository(
                src_root=args.src_root.resolve(),
                policy_path=args.foundation_policy.resolve(),
            )
        )
    if violations:
        for violation in violations:
            print(f"[architecture] {violation}")
        return 1
    print("[architecture] dependency policy satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

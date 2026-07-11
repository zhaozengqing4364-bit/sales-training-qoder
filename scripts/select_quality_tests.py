#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "docs" / "architecture" / "quality-test-selection-policy.yaml"
DEFAULT_OUTPUT = REPO_ROOT / ".sisyphus" / "evidence" / "quality-test-selection.json"
FAMILY_NAMES = ("backend_integration", "backend_e2e", "playwright")
FAMILY_PREFIXES = {
    "backend_integration": "backend/tests/integration/",
    "backend_e2e": "backend/tests/e2e/",
    "playwright": "web/tests/e2e/",
}
FAMILY_GLOBS = {
    "backend_integration": "backend/tests/integration/**/test_*.py",
    "backend_e2e": "backend/tests/e2e/**/test_*.py",
    "playwright": "web/tests/e2e/**/*.spec.ts",
}
FAMILY_CODEGRAPH_FILTERS = {
    "backend_integration": "backend/tests/integration/test_*.py",
    "backend_e2e": "backend/tests/e2e/test_*.py",
    "playwright": "web/tests/e2e/**",
}


@dataclass(frozen=True, order=True)
class Change:
    status: str
    path: str
    old_path: str | None = None


@dataclass(frozen=True)
class CodeGraphEvidence:
    status: str
    version: str | None
    affected_tests: tuple[str, ...]
    fallback_reason: str | None


@dataclass(frozen=True)
class AdoptionAnchor:
    commit: str
    owner: str
    reason: str
    retire_when: str
    expires_on: date


@dataclass(frozen=True)
class FamilyPolicy:
    prefix: str
    glob: str
    codegraph_filter: str
    critical: tuple[str, ...]


@dataclass(frozen=True)
class PathRule:
    rule_id: str
    patterns: tuple[str, ...]
    selected: dict[str, tuple[str, ...]]
    full_fallback_families: tuple[str, ...]


@dataclass(frozen=True)
class SelectionPolicy:
    codegraph_version: str
    adoption_anchor: AdoptionAnchor
    families: dict[str, FamilyPolicy]
    global_fallback_patterns: tuple[str, ...]
    production_roots: tuple[str, ...]
    path_rules: tuple[PathRule, ...]
    repo_root: Path


@dataclass(frozen=True)
class SelectorContext:
    mode: str
    requested_base: str | None
    effective_base: str | None
    head: str
    base_trusted: bool
    changes: tuple[Change, ...]
    codegraph: CodeGraphEvidence


@dataclass(frozen=True)
class BaseResolution:
    requested_base: str | None
    effective_base: str | None
    trusted: bool
    used_adoption_anchor: bool
    fallback_reason: str | None


def _required_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ValueError(f"{context}.{key} must be non-empty")
    return value


def _string_list(value: object, context: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{context} must be a string list")
    if not allow_empty and not value:
        raise ValueError(f"{context} must not be empty")
    return value


def load_policy(
    path: Path = DEFAULT_POLICY,
    *,
    today: date | None = None,
) -> SelectionPolicy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("selection policy version must be 1")
    graph = raw.get("codegraph")
    anchor = raw.get("adoption_anchor")
    raw_families = raw.get("families")
    raw_rules = raw.get("path_rules")
    if not isinstance(graph, dict) or not isinstance(anchor, dict):
        raise ValueError("selection policy requires codegraph and adoption_anchor")
    if not isinstance(raw_families, dict) or set(raw_families) != set(FAMILY_NAMES):
        raise ValueError("selection policy must declare exactly the supported families")
    if not isinstance(raw_rules, list):
        raise ValueError("selection policy path_rules must be a list")

    families: dict[str, FamilyPolicy] = {}
    for name in FAMILY_NAMES:
        value = raw_families[name]
        if not isinstance(value, dict):
            raise ValueError(f"families.{name} is invalid")
        critical = _string_list(value.get("critical"), f"families.{name}.critical")
        prefix = _required_text(value, "prefix", f"families.{name}")
        glob = _required_text(value, "glob", f"families.{name}")
        codegraph_filter = _required_text(
            value,
            "codegraph_filter",
            f"families.{name}",
        )
        if (
            prefix != FAMILY_PREFIXES[name]
            or glob != FAMILY_GLOBS[name]
            or codegraph_filter != FAMILY_CODEGRAPH_FILTERS[name]
        ):
            raise ValueError(f"families.{name} changed its canonical discovery contract")
        families[name] = FamilyPolicy(
            prefix=prefix,
            glob=glob,
            codegraph_filter=codegraph_filter,
            critical=tuple(sorted(set(critical))),
        )

    rules: list[PathRule] = []
    rule_ids: set[str] = set()
    for index, value in enumerate(raw_rules):
        if not isinstance(value, dict):
            raise ValueError(f"path_rules[{index}] is invalid")
        rule_id = _required_text(value, "id", f"path_rules[{index}]")
        if rule_id in rule_ids:
            raise ValueError(f"duplicate path rule id: {rule_id}")
        rule_ids.add(rule_id)
        patterns = _string_list(
            value.get("patterns"),
            f"path_rules[{index}].patterns",
            allow_empty=False,
        )
        selected_raw = value.get("select", {})
        if not isinstance(selected_raw, dict) or not set(selected_raw) <= set(FAMILY_NAMES):
            raise ValueError(f"path_rules[{index}].select is invalid")
        selected = {
            family: tuple(
                sorted(
                    set(
                        _string_list(
                            items,
                            f"path_rules[{index}].select.{family}",
                        )
                    )
                )
            )
            for family, items in selected_raw.items()
        }
        raw_fallback_families = _string_list(
            value.get("full_fallback_families", []),
            f"path_rules[{index}].full_fallback_families",
        )
        if not set(raw_fallback_families) <= set(FAMILY_NAMES):
            raise ValueError(
                f"path_rules[{index}].full_fallback_families is invalid"
            )
        if not any(selected.values()) and not raw_fallback_families:
            raise ValueError(
                f"path_rules[{index}] must select tests or declare a family fallback"
            )
        rules.append(
            PathRule(
                rule_id=rule_id,
                patterns=tuple(patterns),
                selected=selected,
                full_fallback_families=tuple(sorted(raw_fallback_families)),
            )
        )

    expires_on = date.fromisoformat(_required_text(anchor, "expires_on", "adoption_anchor"))
    if (today or date.today()) > expires_on:
        raise ValueError(
            f"adoption anchor expired on {expires_on.isoformat()}; retire it"
        )
    global_fallback_patterns = _string_list(
        raw.get("global_fallback_patterns", []),
        "global_fallback_patterns",
    )
    production_roots = _string_list(
        raw.get("production_roots"),
        "production_roots",
        allow_empty=False,
    )
    return SelectionPolicy(
        codegraph_version=_required_text(graph, "required_version", "codegraph"),
        adoption_anchor=AdoptionAnchor(
            commit=_required_text(anchor, "commit", "adoption_anchor"),
            owner=_required_text(anchor, "owner", "adoption_anchor"),
            reason=_required_text(anchor, "reason", "adoption_anchor"),
            retire_when=_required_text(anchor, "retire_when", "adoption_anchor"),
            expires_on=expires_on,
        ),
        families=families,
        global_fallback_patterns=tuple(global_fallback_patterns),
        production_roots=tuple(production_roots),
        path_rules=tuple(rules),
        repo_root=path.resolve().parents[2],
    )


def build_diff_spec(mode: str, base: str, head: str) -> str:
    if mode == "pr":
        return f"{base}...{head}"
    if mode == "push":
        return f"{base}..{head}"
    raise ValueError(f"unsupported diff mode: {mode}")


def parse_name_status_z(payload: bytes) -> tuple[Change, ...]:
    tokens = payload.decode("utf-8", errors="surrogateescape").split("\0")
    if tokens and tokens[-1] == "":
        tokens.pop()
    changes: list[Change] = []
    index = 0
    while index < len(tokens):
        status_token = tokens[index]
        index += 1
        status = status_token[:1]
        if status in {"R", "C"}:
            if index + 1 >= len(tokens):
                raise ValueError("truncated rename/copy name-status payload")
            old_path, path = tokens[index], tokens[index + 1]
            index += 2
            changes.append(Change("R" if status == "R" else "C", path, old_path))
        else:
            if index >= len(tokens):
                raise ValueError("truncated name-status payload")
            changes.append(Change(status, tokens[index]))
            index += 1
    return tuple(changes)


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _is_production_path(policy: SelectionPolicy, path: str) -> bool:
    if not any(path.startswith(root) for root in policy.production_roots):
        return False
    parts = Path(path).parts
    name = Path(path).name
    if "__tests__" in parts or name.endswith(
        (
            ".test.ts",
            ".test.tsx",
            ".spec.ts",
            ".spec.tsx",
            ".stories.ts",
            ".stories.tsx",
            ".d.ts",
        )
    ):
        return False
    return True


def _family_for_path(policy: SelectionPolicy, path: str) -> str | None:
    for name, family in policy.families.items():
        if path.startswith(family.prefix):
            return name
    return None


def runner_paths(family: str, paths: Iterable[str]) -> list[str]:
    if family not in FAMILY_PREFIXES:
        raise ValueError(f"unknown test family: {family}")
    result = sorted(set(paths))
    for path in result:
        file_name = Path(path).name
        matches_test_contract = (
            file_name.startswith("test_") and file_name.endswith(".py")
            if family in {"backend_integration", "backend_e2e"}
            else file_name.endswith(".spec.ts")
        )
        if (
            not path.startswith(FAMILY_PREFIXES[family])
            or not matches_test_contract
            or ".." in Path(path).parts
            or any(character in path for character in ("\x00", "\n", "\r"))
        ):
            raise ValueError(f"path outside {family}: {path}")
    return result


def manifest_runner_paths(manifest: dict[str, Any], family: str) -> list[str]:
    if manifest.get("schema_version") != 1:
        raise ValueError("selector manifest schema_version must be 1")
    selected = manifest.get("selected")
    if not isinstance(selected, dict):
        raise ValueError("selector manifest selected must be a mapping")
    paths = selected.get(family)
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError(f"selector manifest selected.{family} must be a string list")
    validated = runner_paths(family, paths)
    working_directory_prefix = {
        "backend_integration": "backend/",
        "backend_e2e": "backend/",
        "playwright": "web/",
    }[family]
    return [path.removeprefix(working_directory_prefix) for path in validated]


def validate_codegraph_payload(
    stdout: str,
    *,
    repo_root: Path,
    version: str,
) -> CodeGraphEvidence:
    if "\x1b" in stdout:
        return CodeGraphEvidence("invalid", version, (), "malformed-json")
    try:
        raw = json.loads(stdout)
    except json.JSONDecodeError:
        return CodeGraphEvidence("invalid", version, (), "malformed-json")
    if not isinstance(raw, dict):
        return CodeGraphEvidence("invalid", version, (), "malformed-json")
    changed = raw.get("changedFiles")
    affected = raw.get("affectedTests")
    traversed = raw.get("totalDependentsTraversed")
    if (
        not isinstance(changed, list)
        or not all(isinstance(item, str) for item in changed)
        or not isinstance(affected, list)
        or not all(isinstance(item, str) for item in affected)
        or not isinstance(traversed, int)
        or traversed < 0
    ):
        return CodeGraphEvidence("invalid", version, (), "invalid-json-schema")
    valid: list[str] = []
    for item in affected:
        path = (repo_root / item).resolve()
        if repo_root.resolve() not in path.parents or not path.is_file():
            return CodeGraphEvidence("invalid", version, (), "invalid-test-path")
        family = next(
            (
                name
                for name, prefix in FAMILY_PREFIXES.items()
                if item.startswith(prefix)
            ),
            None,
        )
        if family is None:
            continue
        try:
            runner_paths(family, [item])
        except ValueError:
            # CodeGraph's broad Playwright filter can legitimately surface
            # e2e helper modules. They are dependency evidence, not runnable
            # specs, so keep them out of runner arrays without invalidating
            # otherwise well-formed additive evidence.
            continue
        valid.append(item)
    return CodeGraphEvidence("healthy", version, tuple(sorted(set(valid))), None)


def codegraph_status_is_healthy(status: object) -> bool:
    if not isinstance(status, dict):
        return False
    pending_changes = status.get("pendingChanges")
    pending_clean = (
        isinstance(pending_changes, dict)
        and set(pending_changes) == {"added", "modified", "removed"}
        and all(pending_changes[key] == 0 for key in pending_changes)
    )
    return bool(
        status.get("initialized") is True
        and status.get("worktreeMismatch") in (None, False)
        and pending_clean
    )


def resolve_effective_base(
    *,
    requested_base: str | None,
    head: str,
    policy: SelectionPolicy,
    object_exists: Callable[[str], bool],
    is_ancestor: Callable[[str, str], bool],
    today: date | None = None,
) -> BaseResolution:
    current_day = today or date.today()
    anchor = policy.adoption_anchor
    if current_day > anchor.expires_on:
        raise ValueError(
            f"adoption anchor expired on {anchor.expires_on.isoformat()}; retire it"
        )
    if not requested_base or not object_exists(requested_base) or not object_exists(head):
        return BaseResolution(requested_base, None, False, False, "base-or-head-missing")
    if is_ancestor(anchor.commit, requested_base):
        return BaseResolution(requested_base, requested_base, True, False, None)
    if object_exists(anchor.commit) and is_ancestor(anchor.commit, head):
        return BaseResolution(requested_base, anchor.commit, True, True, None)
    return BaseResolution(requested_base, None, False, False, "adoption-anchor-unavailable")


def discover_family_tests(policy: SelectionPolicy, family: str) -> list[str]:
    if family not in policy.families:
        raise ValueError(f"unknown test family: {family}")
    return sorted(
        path.relative_to(policy.repo_root).as_posix()
        for path in policy.repo_root.glob(policy.families[family].glob)
        if path.is_file()
    )


def select_tests(
    policy: SelectionPolicy,
    context: SelectorContext,
) -> dict[str, Any]:
    selected: dict[str, set[str]] = {name: set() for name in FAMILY_NAMES}
    reasons: dict[str, set[str]] = {}
    fallback_reasons: set[str] = set()
    family_fallback_reasons: dict[str, set[str]] = {
        name: set() for name in FAMILY_NAMES
    }
    degraded_reasons: set[str] = set()

    def fallback_all(reason: str) -> None:
        fallback_reasons.add(reason)
        for name in FAMILY_NAMES:
            family_fallback_reasons[name].add(reason)

    def add(family: str, path: str, reason: str) -> None:
        checked = runner_paths(family, [path])[0]
        selected[family].add(checked)
        reasons.setdefault(checked, set()).add(reason)

    for family, config in policy.families.items():
        for path in config.critical:
            add(family, path, "critical-baseline")

    if context.mode in {"full", "schedule", "release"}:
        fallback_all(f"mode:{context.mode}")
    if not context.base_trusted:
        fallback_all("untrusted-base")
    if context.codegraph.status == "invalid":
        fallback_all(context.codegraph.fallback_reason or "codegraph-invalid")
    elif context.codegraph.status == "missing":
        degraded_reasons.add(context.codegraph.fallback_reason or "codegraph-missing")

    production_changes: list[str] = []
    matched_production: set[str] = set()
    for change in sorted(set(context.changes), key=lambda item: (item.path, item.old_path or "", item.status)):
        if change.status in {"D", "R"}:
            fallback_all(f"delete-or-rename:{change.path}")
        if _matches(change.path, policy.global_fallback_patterns):
            fallback_all(f"global-path:{change.path}")
        family = _family_for_path(policy, change.path)
        if family is not None and change.status != "D":
            try:
                add(family, change.path, "direct-change")
            except ValueError:
                # Files under a slow-test family can be shared fixtures,
                # route manifests, or setup helpers rather than executable
                # tests. They affect the whole family but must never be
                # forwarded to pytest/Playwright as runner arguments.
                family_fallback_reasons[family].add(
                    f"test-support-change:{change.path}"
                )
        is_production_change = _is_production_path(policy, change.path)
        if is_production_change:
            production_changes.append(change.path)
        for rule in policy.path_rules:
            if not _matches(change.path, rule.patterns):
                continue
            if is_production_change:
                matched_production.add(change.path)
            for selected_family, paths in rule.selected.items():
                for path in paths:
                    add(selected_family, path, f"path-policy:{rule.rule_id}")
            for family_name in rule.full_fallback_families:
                family_fallback_reasons[family_name].add(
                    f"path-policy-full:{rule.rule_id}"
                )

    unknown_production = sorted(set(production_changes) - matched_production)
    for path in unknown_production:
        fallback_all(f"unknown-production-path:{path}")

    if context.codegraph.status == "healthy":
        for path in context.codegraph.affected_tests:
            family = _family_for_path(policy, path)
            if family is None:
                fallback_all(f"codegraph-path-outside-families:{path}")
                continue
            add(family, path, "codegraph-affected")

    if production_changes and not any(selected.values()):
        fallback_all("production-change-selected-no-slow-tests")

    fallback_families = {
        family for family, values in family_fallback_reasons.items() if values
    }
    if fallback_families == set(FAMILY_NAMES):
        selection_mode = "full-fallback"
    elif fallback_families:
        selection_mode = "family-fallback"
    else:
        selection_mode = "selected"
    for family in sorted(fallback_families):
        for path in discover_family_tests(policy, family):
            add(family, path, "full-fallback")

    normalized_selected = {
        family: runner_paths(family, paths) for family, paths in selected.items()
    }
    return {
        "schema_version": 1,
        "selection_mode": selection_mode,
        "mode": context.mode,
        "requested_base": context.requested_base,
        "effective_base": context.effective_base,
        "head": context.head,
        "changed_paths": sorted({change.path for change in context.changes}),
        "changes": [
            {"status": change.status, "path": change.path, "old_path": change.old_path}
            for change in sorted(set(context.changes), key=lambda item: (item.path, item.old_path or "", item.status))
        ],
        "codegraph": {
            "status": context.codegraph.status,
            "version": context.codegraph.version,
            "fallback_reason": context.codegraph.fallback_reason,
        },
        "fallback_reasons": sorted(fallback_reasons),
        "family_fallback_reasons": {
            family: sorted(values)
            for family, values in family_fallback_reasons.items()
            if values
        },
        "degraded_reasons": sorted(degraded_reasons),
        "selected": normalized_selected,
        "reasons": {path: sorted(values) for path, values in sorted(reasons.items())},
    }


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout


def collect_changes(
    repo_root: Path,
    *,
    diff_spec: str | None,
) -> tuple[Change, ...]:
    changes: set[Change] = set()
    if diff_spec:
        changes.update(parse_name_status_z(_git(repo_root, "diff", "--name-status", "-z", "--find-renames", diff_spec)))
    changes.update(parse_name_status_z(_git(repo_root, "diff", "--name-status", "-z", "--find-renames")))
    changes.update(parse_name_status_z(_git(repo_root, "diff", "--cached", "--name-status", "-z", "--find-renames")))
    untracked = _git(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    for raw_path in untracked.decode("utf-8", errors="surrogateescape").split("\0"):
        if raw_path:
            changes.add(Change("A", raw_path))
    return tuple(sorted(changes, key=lambda item: (item.path, item.old_path or "", item.status)))


def _git_object_exists(repo_root: Path, value: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"],
        cwd=repo_root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _git_is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _codegraph_evidence(
    policy: SelectionPolicy,
    changed_paths: Sequence[str],
) -> CodeGraphEvidence:
    executable = shutil.which("codegraph")
    if not executable:
        return CodeGraphEvidence("missing", None, (), "command-missing")
    version_result = subprocess.run(
        [executable, "version"],
        cwd=policy.repo_root,
        check=False,
        text=True,
        capture_output=True,
    )
    version = version_result.stdout.strip().split()[-1] if version_result.stdout.strip() else None
    if version_result.returncode != 0 or version != policy.codegraph_version:
        return CodeGraphEvidence("invalid", version, (), "version-mismatch")
    status_result = subprocess.run(
        [executable, "status", "--json", str(policy.repo_root)],
        cwd=policy.repo_root,
        check=False,
        text=True,
        capture_output=True,
    )
    try:
        status = json.loads(status_result.stdout)
    except json.JSONDecodeError:
        return CodeGraphEvidence("invalid", version, (), "status-malformed-json")
    if (
        status_result.returncode != 0
        or not codegraph_status_is_healthy(status)
    ):
        return CodeGraphEvidence("invalid", version, (), "index-unhealthy")
    if not changed_paths:
        return CodeGraphEvidence("healthy", version, (), None)

    affected: set[str] = set()
    for family in FAMILY_NAMES:
        family_policy = policy.families[family]
        result = subprocess.run(
            [
                executable,
                "affected",
                "--json",
                "--filter",
                family_policy.codegraph_filter,
                *changed_paths,
            ],
            cwd=policy.repo_root,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            return CodeGraphEvidence("invalid", version, (), "affected-command-failed")
        evidence = validate_codegraph_payload(
            result.stdout,
            repo_root=policy.repo_root,
            version=version,
        )
        if evidence.status != "healthy":
            return evidence
        affected.update(evidence.affected_tests)
    if any(_is_production_path(policy, path) for path in changed_paths) and not affected:
        return CodeGraphEvidence("invalid", version, (), "empty-production-result")
    return CodeGraphEvidence("healthy", version, tuple(sorted(affected)), None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select conservative slow quality tests")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=("pr", "push", "local", "full", "schedule", "release"), default="local")
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--emit-family", choices=FAMILY_NAMES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.emit_family:
        raw = json.loads(args.output.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("selector manifest must be a JSON object")
        for path in manifest_runner_paths(raw, args.emit_family):
            print(path)
        return 0
    policy = load_policy(args.policy)
    base = args.base
    if args.mode == "local" and not base:
        upstream = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            cwd=policy.repo_root,
            check=False,
            text=True,
            capture_output=True,
        )
        if upstream.returncode == 0:
            merge_base = subprocess.run(
                ["git", "merge-base", args.head, upstream.stdout.strip()],
                cwd=policy.repo_root,
                check=False,
                text=True,
                capture_output=True,
            )
            if merge_base.returncode == 0:
                base = merge_base.stdout.strip()
    full_mode = args.mode in {"full", "schedule", "release"}
    resolution = BaseResolution(base, None, False, False, "full-mode") if full_mode else resolve_effective_base(
        requested_base=base,
        head=args.head,
        policy=policy,
        object_exists=lambda value: _git_object_exists(policy.repo_root, value),
        is_ancestor=lambda ancestor, descendant: _git_is_ancestor(policy.repo_root, ancestor, descendant),
    )
    diff_spec = None
    if resolution.trusted and resolution.effective_base:
        diff_mode = "push" if args.mode == "push" else "pr"
        diff_spec = build_diff_spec(diff_mode, resolution.effective_base, args.head)
    changes = collect_changes(policy.repo_root, diff_spec=diff_spec)
    graph = _codegraph_evidence(policy, [change.path for change in changes])
    manifest = select_tests(
        policy,
        SelectorContext(
            mode=args.mode,
            requested_base=base,
            effective_base=resolution.effective_base,
            head=args.head,
            base_trusted=resolution.trusted or full_mode,
            changes=changes,
            codegraph=graph,
        ),
    )
    manifest["base_resolution"] = {
        "used_adoption_anchor": resolution.used_adoption_anchor,
        "fallback_reason": resolution.fallback_reason,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Quality test selection manifest: {args.output}")
    print(f"Selection mode: {manifest['selection_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

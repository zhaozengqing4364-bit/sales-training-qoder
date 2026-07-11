#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "docs" / "architecture" / "changed-coverage-policy.yaml"
DEFAULT_SELECTION_POLICY = REPO_ROOT / "docs" / "architecture" / "quality-test-selection-policy.yaml"
DEFAULT_BACKEND_REPORT = REPO_ROOT / ".sisyphus" / "evidence" / "backend-coverage.json"
DEFAULT_FRONTEND_REPORT = REPO_ROOT / "web" / "coverage" / "coverage-final.json"
DEFAULT_SELECTOR_MANIFEST = REPO_ROOT / ".sisyphus" / "evidence" / "quality-test-selection.json"
DEFAULT_OUTPUT = REPO_ROOT / ".sisyphus" / "evidence" / "changed-coverage-report.json"
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
ADOPTION_ANCHOR_FIELDS = (
    "commit",
    "owner",
    "reason",
    "retire_when",
    "expires_on",
)


@dataclass(frozen=True)
class BranchFloor:
    covered: int
    total: int

    @property
    def ratio(self) -> float:
        return self.covered / self.total if self.total else 1.0


@dataclass(frozen=True)
class CoveragePolicy:
    changed_line_threshold: float
    adoption_commit: str
    adoption_owner: str
    adoption_reason: str
    adoption_retire_when: str
    adoption_expires_on: date
    production_roots: dict[str, str]
    critical_branch_files: dict[str, dict[str, BranchFloor]]


def _required_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ValueError(f"{context}.{key} must be non-empty")
    return value


def validate_adoption_anchor_consistency(
    coverage_policy_path: Path,
    selection_policy_path: Path = DEFAULT_SELECTION_POLICY,
) -> None:
    policies: list[dict[str, Any]] = []
    for path in (coverage_policy_path, selection_policy_path):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("adoption_anchor"), dict):
            raise ValueError(f"policy is missing adoption_anchor: {path}")
        policies.append(raw["adoption_anchor"])
    coverage_anchor, selection_anchor = policies
    coverage_values = tuple(str(coverage_anchor.get(field, "")) for field in ADOPTION_ANCHOR_FIELDS)
    selection_values = tuple(str(selection_anchor.get(field, "")) for field in ADOPTION_ANCHOR_FIELDS)
    if coverage_values != selection_values:
        raise ValueError("coverage and selection adoption anchors differ")


def load_policy(
    path: Path = DEFAULT_POLICY,
    *,
    today: date | None = None,
) -> CoveragePolicy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("coverage policy version must be 1")
    threshold = raw.get("changed_line_threshold")
    if not isinstance(threshold, int | float) or not 0 <= float(threshold) <= 100:
        raise ValueError("changed_line_threshold must be between 0 and 100")
    anchor = raw.get("adoption_anchor")
    roots = raw.get("production_roots")
    critical = raw.get("critical_branch_files")
    if not isinstance(anchor, dict) or not isinstance(roots, dict) or not isinstance(critical, dict):
        raise ValueError("coverage policy is missing required mappings")
    expires_on = date.fromisoformat(_required_text(anchor, "expires_on", "adoption_anchor"))
    if (today or date.today()) > expires_on:
        raise ValueError(
            f"adoption anchor expired on {expires_on.isoformat()}; retire it"
        )
    production_roots = {
        language: _required_text(roots, language, "production_roots")
        for language in ("backend", "frontend")
    }
    critical_files: dict[str, dict[str, BranchFloor]] = {}
    for language in ("backend", "frontend"):
        raw_files = critical.get(language)
        if not isinstance(raw_files, dict):
            raise ValueError(f"critical_branch_files.{language} must be a mapping")
        language_files: dict[str, BranchFloor] = {}
        for file_path, value in raw_files.items():
            if not isinstance(value, dict):
                raise ValueError(f"invalid branch floor for {file_path}")
            covered, total = value.get("covered"), value.get("total")
            if (
                not isinstance(covered, int)
                or not isinstance(total, int)
                or covered < 0
                or total < 0
                or covered > total
            ):
                raise ValueError(f"invalid branch floor for {file_path}")
            language_files[str(file_path)] = BranchFloor(covered, total)
        critical_files[language] = language_files
    return CoveragePolicy(
        changed_line_threshold=float(threshold),
        adoption_commit=_required_text(anchor, "commit", "adoption_anchor"),
        adoption_owner=_required_text(anchor, "owner", "adoption_anchor"),
        adoption_reason=_required_text(anchor, "reason", "adoption_anchor"),
        adoption_retire_when=_required_text(anchor, "retire_when", "adoption_anchor"),
        adoption_expires_on=expires_on,
        production_roots=production_roots,
        critical_branch_files=critical_files,
    )


def parse_unified_zero_diff(diff: str) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = {}
    current_path: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            marker = line[4:].strip()
            current_path = None if marker == "/dev/null" else marker.removeprefix("b/")
            continue
        match = HUNK_RE.match(line)
        if match is None or current_path is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        if count:
            changed.setdefault(current_path, set()).update(range(start, start + count))
    return changed


def _merge_changed_lines(*values: dict[str, set[int]]) -> dict[str, set[int]]:
    merged: dict[str, set[int]] = {}
    for value in values:
        for path, lines in value.items():
            merged.setdefault(path, set()).update(lines)
    return merged


def _is_production_path(policy: CoveragePolicy, path: str) -> bool:
    backend_root = policy.production_roots["backend"]
    frontend_root = policy.production_roots["frontend"]
    if path.startswith(backend_root):
        if not path.endswith(".py"):
            return False
    elif path.startswith(frontend_root):
        if not path.endswith((".ts", ".tsx")):
            return False
    else:
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


def _report_entry(files: dict[str, Any], repo_path: str, strip_prefix: str) -> dict[str, Any] | None:
    candidates = {repo_path, repo_path.removeprefix(strip_prefix)}
    for key, value in files.items():
        normalized = str(key).replace("\\", "/")
        if normalized in candidates or any(normalized.endswith(f"/{candidate}") for candidate in candidates):
            return value if isinstance(value, dict) else None
    return None


def _backend_line_evidence(entry: dict[str, Any]) -> tuple[set[int], set[int]]:
    executed = {int(value) for value in entry.get("executed_lines", [])}
    missing = {int(value) for value in entry.get("missing_lines", [])}
    return executed | missing, executed


def _frontend_line_evidence(entry: dict[str, Any]) -> tuple[set[int], set[int]]:
    statement_map = entry.get("statementMap")
    counts = entry.get("s")
    if not isinstance(statement_map, dict) or not isinstance(counts, dict):
        return set(), set()
    executable: set[int] = set()
    covered: set[int] = set()
    for statement_id, location in statement_map.items():
        try:
            start_line = int(location["start"]["line"])
            end_line = int(location.get("end", location["start"])["line"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_line < start_line:
            continue
        statement_lines = set(range(start_line, end_line + 1))
        executable.update(statement_lines)
        if int(counts.get(statement_id, 0)) > 0:
            covered.update(statement_lines)
    return executable, covered


def _backend_branch_evidence(entry: dict[str, Any]) -> tuple[int, int, set[int]]:
    summary = entry.get("summary")
    if not isinstance(summary, dict):
        return 0, 0, set()
    covered = int(summary.get("covered_branches", 0))
    total = int(summary.get("num_branches", 0))
    missing_sources = {
        int(branch[0])
        for branch in entry.get("missing_branches", [])
        if isinstance(branch, list) and branch
    }
    return covered, total, missing_sources


def _frontend_branch_evidence(entry: dict[str, Any]) -> tuple[int, int, set[int]]:
    branch_map = entry.get("branchMap")
    counts = entry.get("b")
    if not isinstance(branch_map, dict) or not isinstance(counts, dict):
        return 0, 0, set()
    covered = 0
    total = 0
    missing_sources: set[int] = set()
    for branch_id, values in counts.items():
        if not isinstance(values, list):
            continue
        total += len(values)
        covered += sum(1 for value in values if int(value) > 0)
        if all(int(value) > 0 for value in values):
            continue
        try:
            missing_sources.add(int(branch_map[branch_id]["loc"]["start"]["line"]))
        except (KeyError, TypeError, ValueError):
            continue
    return covered, total, missing_sources


def _critical_results(
    policy: CoveragePolicy,
    *,
    language: str,
    report_files: dict[str, Any],
    changed_lines: dict[str, set[int]],
) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    violations: list[str] = []
    strip_prefix = "backend/" if language == "backend" else ""
    branch_reader = _backend_branch_evidence if language == "backend" else _frontend_branch_evidence
    for path, floor in sorted(policy.critical_branch_files[language].items()):
        entry = _report_entry(report_files, path, strip_prefix)
        if entry is None:
            violations.append(f"critical file missing from fresh coverage report: {path}")
            continue
        covered, total, missing_sources = branch_reader(entry)
        if floor.total > 0 and total == 0:
            violations.append(f"critical branch evidence is empty: {path}")
        ratio = covered / total if total else 1.0
        if ratio + 1e-12 < floor.ratio:
            violations.append(
                "critical branch baseline regressed: "
                f"{path} current={covered}/{total} floor={floor.covered}/{floor.total}"
            )
        changed_missing = sorted(changed_lines.get(path, set()) & missing_sources)
        if changed_missing:
            violations.append(
                f"changed critical branch is not fully covered: {path}:{changed_missing}"
            )
        results.append(
            {
                "path": path,
                "covered": covered,
                "total": total,
                "floor_covered": floor.covered,
                "floor_total": floor.total,
                "changed_missing_source_lines": changed_missing,
            }
        )
    return results, violations


def evaluate_coverage(
    policy: CoveragePolicy,
    *,
    changed_lines: dict[str, set[int]],
    backend_report: dict[str, Any],
    frontend_report: dict[str, Any],
    selector_manifest: dict[str, Any],
    base_trusted: bool,
) -> dict[str, Any]:
    violations: list[str] = []
    backend_meta = backend_report.get("meta")
    if not isinstance(backend_meta, dict) or backend_meta.get("branch_coverage") is not True:
        violations.append("backend coverage report must have branch_coverage=true")
    backend_files = backend_report.get("files")
    if not isinstance(backend_files, dict):
        backend_files = {}
        violations.append("backend coverage report files must be a mapping")
    if not isinstance(frontend_report, dict):
        frontend_report = {}
        violations.append("frontend coverage report must be a mapping")

    critical_results: dict[str, list[dict[str, Any]]] = {}
    for language, files in (("backend", backend_files), ("frontend", frontend_report)):
        values, errors = _critical_results(
            policy,
            language=language,
            report_files=files,
            changed_lines=changed_lines,
        )
        critical_results[language] = values
        violations.extend(errors)

    if not base_trusted:
        if selector_manifest.get("selection_mode") != "full-fallback":
            violations.append("untrusted base requires selector full-fallback evidence")
        changed_summary = {
            "status": "not-applicable-full-fallback",
            "covered": 0,
            "executable": 0,
            "percent": None,
        }
        return {
            "schema_version": 1,
            "changed_lines": changed_summary,
            "critical_branches": critical_results,
            "violations": sorted(set(violations)),
        }

    covered_count = 0
    executable_count = 0
    file_results: list[dict[str, Any]] = []
    for path, lines in sorted(changed_lines.items()):
        if not _is_production_path(policy, path):
            continue
        if path.startswith(policy.production_roots["backend"]):
            entry = _report_entry(backend_files, path, "backend/")
            line_reader = _backend_line_evidence
        elif path.startswith(policy.production_roots["frontend"]):
            entry = _report_entry(frontend_report, path, "")
            line_reader = _frontend_line_evidence
        else:
            continue
        if entry is None:
            violations.append(f"changed production file missing from fresh coverage report: {path}")
            continue
        executable, covered = line_reader(entry)
        changed_executable = set(lines) & executable
        changed_covered = changed_executable & covered
        executable_count += len(changed_executable)
        covered_count += len(changed_covered)
        file_results.append(
            {
                "path": path,
                "changed_executable": len(changed_executable),
                "changed_covered": len(changed_covered),
                "missing_lines": sorted(changed_executable - changed_covered),
            }
        )

    if executable_count:
        percent = covered_count * 100.0 / executable_count
        status = "measured"
        if percent + 1e-12 < policy.changed_line_threshold:
            violations.append(
                f"changed executable line coverage {percent:.2f}% is below {policy.changed_line_threshold:.2f}%"
            )
    else:
        percent = None
        status = "no-executable-lines"
    return {
        "schema_version": 1,
        "changed_lines": {
            "status": status,
            "covered": covered_count,
            "executable": executable_count,
            "percent": percent,
            "threshold": policy.changed_line_threshold,
            "files": file_results,
        },
        "critical_branches": critical_results,
        "violations": sorted(set(violations)),
    }


def _git_diff(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", *args, "--", "backend/src", "web/src"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def build_coverage_diff_spec(mode: str, base: str, head: str) -> str:
    if mode == "push":
        return f"{base}..{head}"
    if mode in {"pr", "local"}:
        return f"{base}...{head}"
    raise ValueError(f"unsupported selector mode for changed coverage: {mode}")


def collect_changed_lines(
    repo_root: Path,
    *,
    effective_base: str | None,
    head: str,
    selector_manifest: dict[str, Any],
) -> dict[str, set[int]]:
    diffs: list[dict[str, set[int]]] = []
    if effective_base:
        mode = str(selector_manifest.get("mode") or "")
        diffs.append(
            parse_unified_zero_diff(
                _git_diff(
                    repo_root,
                    build_coverage_diff_spec(mode, effective_base, head),
                )
            )
        )
    diffs.append(parse_unified_zero_diff(_git_diff(repo_root)))
    diffs.append(parse_unified_zero_diff(_git_diff(repo_root, "--cached")))
    merged = _merge_changed_lines(*diffs)
    for change in selector_manifest.get("changes", []):
        if not isinstance(change, dict) or change.get("status") != "A":
            continue
        path = str(change.get("path") or "")
        if not path.startswith(("backend/src/", "web/src/")):
            continue
        source = repo_root / path
        if source.is_file():
            merged.setdefault(path, set()).update(
                range(1, len(source.read_text(encoding="utf-8").splitlines()) + 1)
            )
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return raw


def validate_selector_manifest(
    manifest: dict[str, Any],
    *,
    expected_head: str,
) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("selector manifest schema_version must be 1")
    if manifest.get("head") != expected_head:
        raise ValueError("selector manifest head does not match coverage head")
    if manifest.get("mode") not in {
        "pr",
        "push",
        "local",
        "full",
        "schedule",
        "release",
    }:
        raise ValueError("selector manifest mode is invalid")
    if manifest.get("selection_mode") not in {
        "selected",
        "family-fallback",
        "full-fallback",
    }:
        raise ValueError("selector manifest selection_mode is invalid")
    effective_base = manifest.get("effective_base")
    if effective_base is not None and not isinstance(effective_base, str):
        raise ValueError("selector manifest effective_base must be a string or null")
    changes = manifest.get("changes")
    if not isinstance(changes, list):
        raise ValueError("selector manifest changes must be a list")
    for change in changes:
        if (
            not isinstance(change, dict)
            or not isinstance(change.get("status"), str)
            or not isinstance(change.get("path"), str)
            or change.get("old_path") is not None
            and not isinstance(change.get("old_path"), str)
        ):
            raise ValueError("selector manifest contains an invalid change")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check changed-line and critical branch coverage")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--selection-policy", type=Path, default=DEFAULT_SELECTION_POLICY)
    parser.add_argument("--backend-report", type=Path, default=DEFAULT_BACKEND_REPORT)
    parser.add_argument("--frontend-report", type=Path, default=DEFAULT_FRONTEND_REPORT)
    parser.add_argument("--selector-manifest", type=Path, default=DEFAULT_SELECTOR_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--head", default="HEAD")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_adoption_anchor_consistency(args.policy, args.selection_policy)
    policy = load_policy(args.policy)
    selector = _read_json(args.selector_manifest)
    validate_selector_manifest(selector, expected_head=args.head)
    effective_base = selector.get("effective_base")
    base_trusted = isinstance(effective_base, str) and bool(effective_base)
    changed_lines = collect_changed_lines(
        REPO_ROOT,
        effective_base=effective_base if base_trusted else None,
        head=args.head,
        selector_manifest=selector,
    )
    result = evaluate_coverage(
        policy,
        changed_lines=changed_lines,
        backend_report=_read_json(args.backend_report),
        frontend_report=_read_json(args.frontend_report),
        selector_manifest=selector,
        base_trusted=base_trusted,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["violations"]:
        for violation in result["violations"]:
            print(f"[coverage] {violation}")
        return 1
    print(f"Changed coverage satisfied: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

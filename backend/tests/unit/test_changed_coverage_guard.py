from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_changed_coverage.py"
SPEC = importlib.util.spec_from_file_location("changed_coverage_guard", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

evaluate_coverage = MODULE.evaluate_coverage
build_coverage_diff_spec = MODULE.build_coverage_diff_spec
load_policy = MODULE.load_policy
parse_unified_zero_diff = MODULE.parse_unified_zero_diff
validate_adoption_anchor_consistency = MODULE.validate_adoption_anchor_consistency
validate_selector_manifest = MODULE.validate_selector_manifest

EXPECTED_CRITICAL_BRANCH_FLOORS = {
    "backend": {
        "backend/src/common/db/session_lifecycle.py": (44, 64),
        "backend/src/sales_trainer/services/path_progress_service.py": (2, 8),
        "backend/src/sales_trainer/services/path_projection_payloads.py": (22, 24),
        "backend/src/sales_trainer/services/path_service.py": (18, 22),
        "backend/src/sales_bot/websocket/session_control_adapter.py": (8, 10),
        "backend/src/sales_trainer/services/training_journey_service.py": (290, 434),
        "backend/src/sales_bot/services/roleplay_state_card.py": (14, 20),
    },
    "frontend": {
        "web/src/app/(user)/practice/[sessionId]/use-recording-state-machine.ts": (19, 20),
        "web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts": (58, 68),
        "web/src/app/(user)/practice/[sessionId]/runtime-lock.ts": (26, 47),
        "web/src/hooks/use-audio-recorder.ts": (19, 135),
    },
}


def _write_policy(
    tmp_path: Path,
    *,
    backend_critical: dict[str, tuple[int, int]] | None = None,
    frontend_critical: dict[str, tuple[int, int]] | None = None,
    expires_on: str = "2026-08-10",
    load_today: date = date(2026, 7, 10),
):
    path = tmp_path / "policy.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "changed_line_threshold": 80.0,
                "adoption_anchor": {
                    "commit": "d96ec87f",
                    "owner": "architecture-governance",
                    "reason": "synthetic adoption",
                    "retire_when": "base contains adoption commit",
                    "expires_on": expires_on,
                },
                "production_roots": {
                    "backend": "backend/src/",
                    "frontend": "web/src/",
                },
                "critical_branch_files": {
                    "backend": {
                        path: {"covered": covered, "total": total}
                        for path, (covered, total) in (backend_critical or {}).items()
                    },
                    "frontend": {
                        path: {"covered": covered, "total": total}
                        for path, (covered, total) in (frontend_critical or {}).items()
                    },
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return load_policy(path, today=load_today)


def _backend_report(
    *,
    path: str = "src/example.py",
    executed: list[int] | None = None,
    missing: list[int] | None = None,
    covered_branches: int = 0,
    total_branches: int = 0,
    missing_branches: list[list[int]] | None = None,
    branch_coverage: bool = True,
) -> dict[str, object]:
    return {
        "meta": {"branch_coverage": branch_coverage},
        "files": {
            path: {
                "executed_lines": executed or [],
                "missing_lines": missing or [],
                "executed_branches": [],
                "missing_branches": missing_branches or [],
                "summary": {
                    "covered_branches": covered_branches,
                    "num_branches": total_branches,
                },
            }
        },
    }


def _frontend_report(
    *,
    path: str = "/repo/web/src/example.ts",
    counts: list[int] | None = None,
    branch_counts: list[list[int]] | None = None,
    branch_line: int = 1,
) -> dict[str, object]:
    statement_counts = counts or []
    return {
        path: {
            "statementMap": {
                str(index): {"start": {"line": index + 1}}
                for index in range(len(statement_counts))
            },
            "s": {
                str(index): count for index, count in enumerate(statement_counts)
            },
            "branchMap": {
                str(index): {"loc": {"start": {"line": branch_line}}}
                for index, _counts in enumerate(branch_counts or [])
            },
            "b": {
                str(index): values
                for index, values in enumerate(branch_counts or [])
            },
        }
    }


def _selector(mode: str = "selected") -> dict[str, object]:
    return {"selection_mode": mode, "effective_base": "base"}


def test_should_parse_only_added_lines_from_zero_context_diff() -> None:
    diff = """diff --git a/backend/src/example.py b/backend/src/example.py
--- a/backend/src/example.py
+++ b/backend/src/example.py
@@ -2,2 +2,3 @@
-old
+new
+added
 context
diff --git a/web/src/deleted.ts b/web/src/deleted.ts
--- a/web/src/deleted.ts
+++ /dev/null
@@ -1 +0,0 @@
-deleted
"""

    assert parse_unified_zero_diff(diff) == {
        "backend/src/example.py": {2, 3, 4},
    }


def test_should_share_pr_and_push_diff_semantics_with_selector_manifest() -> None:
    assert build_coverage_diff_spec("pr", "base", "head") == "base...head"
    assert build_coverage_diff_spec("local", "base", "head") == "base...head"
    assert build_coverage_diff_spec("push", "before", "after") == "before..after"
    with pytest.raises(ValueError, match="unsupported selector mode"):
        build_coverage_diff_spec("unknown", "base", "head")


@pytest.mark.parametrize(
    ("covered", "expected_violation"),
    [(4, False), (3, True)],
)
def test_should_enforce_changed_executable_line_threshold_at_80_percent(
    tmp_path: Path,
    covered: int,
    expected_violation: bool,
) -> None:
    policy = _write_policy(tmp_path)
    report = _backend_report(
        executed=list(range(1, covered + 1)),
        missing=list(range(covered + 1, 6)),
    )

    result = evaluate_coverage(
        policy,
        changed_lines={"backend/src/example.py": set(range(1, 6))},
        backend_report=report,
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert bool(result["violations"]) is expected_violation
    assert result["changed_lines"]["percent"] == covered * 20.0


def test_should_read_istanbul_statement_locations_for_frontend_lines(
    tmp_path: Path,
) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={"web/src/example.ts": {1, 2, 3, 4, 5}},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report=_frontend_report(counts=[1, 1, 1, 1, 0]),
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert result["changed_lines"]["percent"] == 80.0
    assert result["violations"] == []


def test_should_cover_every_line_spanned_by_a_multiline_istanbul_statement(
    tmp_path: Path,
) -> None:
    frontend_report = {
        "/repo/web/src/example.ts": {
            "statementMap": {
                "0": {
                    "start": {"line": 2},
                    "end": {"line": 4},
                },
            },
            "s": {"0": 1},
            "branchMap": {},
            "b": {},
        }
    }

    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={"web/src/example.ts": {3, 4}},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report=frontend_report,
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert result["changed_lines"]["executable"] == 2
    assert result["changed_lines"]["covered"] == 2
    assert result["violations"] == []


def test_should_fail_when_changed_production_file_is_missing_from_report(
    tmp_path: Path,
) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={"backend/src/missing.py": {1}},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert any("missing from fresh coverage report" in item for item in result["violations"])


def test_should_ignore_colocated_frontend_tests_excluded_from_coverage(
    tmp_path: Path,
) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={"web/src/app/page.test.tsx": {1, 2, 3}},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert result["changed_lines"]["status"] == "no-executable-lines"
    assert result["violations"] == []


def test_should_ignore_frontend_assets_that_istanbul_cannot_instrument(
    tmp_path: Path,
) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={"web/src/app/globals.css": {1, 2, 3}},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert result["changed_lines"]["status"] == "no-executable-lines"
    assert result["violations"] == []


def test_should_exclude_non_executable_changed_lines_from_denominator(
    tmp_path: Path,
) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={"backend/src/example.py": {99}},
        backend_report=_backend_report(executed=[1]),
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert result["changed_lines"]["status"] == "no-executable-lines"
    assert result["violations"] == []


def test_should_require_changed_critical_branch_source_lines_to_be_fully_covered(
    tmp_path: Path,
) -> None:
    critical = "backend/src/example.py"
    result = evaluate_coverage(
        _write_policy(tmp_path, backend_critical={critical: (1, 2)}),
        changed_lines={critical: {10}},
        backend_report=_backend_report(
            executed=[10],
            covered_branches=1,
            total_branches=2,
            missing_branches=[[10, 11]],
        ),
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert any("changed critical branch" in item for item in result["violations"])


def test_should_fail_when_critical_branch_baseline_regresses(
    tmp_path: Path,
) -> None:
    critical = "backend/src/example.py"
    result = evaluate_coverage(
        _write_policy(tmp_path, backend_critical={critical: (2, 2)}),
        changed_lines={},
        backend_report=_backend_report(
            executed=[1],
            covered_branches=1,
            total_branches=2,
        ),
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert any("critical branch baseline regressed" in item for item in result["violations"])


def test_should_fail_when_critical_branch_evidence_is_empty(
    tmp_path: Path,
) -> None:
    critical = "web/src/example.ts"
    result = evaluate_coverage(
        _write_policy(tmp_path, frontend_critical={critical: (1, 2)}),
        changed_lines={},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report=_frontend_report(counts=[1]),
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert any("critical branch evidence is empty" in item for item in result["violations"])


def test_should_allow_changed_line_na_only_when_selector_proves_full_fallback(
    tmp_path: Path,
) -> None:
    policy = _write_policy(tmp_path)
    invalid = evaluate_coverage(
        policy,
        changed_lines={},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report={},
        selector_manifest=_selector("selected"),
        base_trusted=False,
    )
    allowed = evaluate_coverage(
        policy,
        changed_lines={},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report={},
        selector_manifest=_selector("full-fallback"),
        base_trusted=False,
    )

    assert any("untrusted base" in item for item in invalid["violations"])
    assert allowed["changed_lines"]["status"] == "not-applicable-full-fallback"
    assert allowed["violations"] == []


def test_should_reject_backend_report_without_branch_coverage(tmp_path: Path) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={},
        backend_report=_backend_report(branch_coverage=False),
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    assert any("branch_coverage=true" in item for item in result["violations"])


def test_should_fail_closed_when_coverage_adoption_anchor_expires(
    tmp_path: Path,
) -> None:
    path = tmp_path / "expired.yaml"
    policy = _write_policy(
        tmp_path,
        expires_on="2026-07-09",
        load_today=date(2026, 7, 9),
    )
    del policy
    original = tmp_path / "policy.yaml"
    path.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="adoption anchor expired"):
        load_policy(path, today=date(2026, 7, 10))


def test_should_reject_drift_between_selection_and_coverage_adoption_anchors(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.yaml"
    coverage = tmp_path / "coverage.yaml"
    common_anchor = {
        "commit": "d96ec87f",
        "owner": "architecture-governance",
        "reason": "synthetic adoption",
        "retire_when": "base contains adoption commit",
        "expires_on": "2026-08-10",
    }
    selection.write_text(
        yaml.safe_dump({"adoption_anchor": common_anchor}),
        encoding="utf-8",
    )
    coverage.write_text(
        yaml.safe_dump({
            "adoption_anchor": {**common_anchor, "commit": "different"},
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="adoption anchors differ"):
        validate_adoption_anchor_consistency(coverage, selection)


def test_repo_selection_and_coverage_adoption_anchors_are_identical() -> None:
    validate_adoption_anchor_consistency(
        REPO_ROOT / "docs" / "architecture" / "changed-coverage-policy.yaml",
        REPO_ROOT / "docs" / "architecture" / "quality-test-selection-policy.yaml",
    )


def test_repo_critical_branch_floors_cannot_drop_below_adoption_baseline() -> None:
    policy = load_policy(
        REPO_ROOT / "docs" / "architecture" / "changed-coverage-policy.yaml",
        today=date(2026, 7, 10),
    )

    for language, expected_files in EXPECTED_CRITICAL_BRANCH_FLOORS.items():
        actual_files = policy.critical_branch_files[language]
        assert set(actual_files) == set(expected_files)
        for path, (covered, total) in expected_files.items():
            assert actual_files[path].ratio + 1e-12 >= covered / total


def test_guard_result_is_json_serializable(tmp_path: Path) -> None:
    result = evaluate_coverage(
        _write_policy(tmp_path),
        changed_lines={},
        backend_report={"meta": {"branch_coverage": True}, "files": {}},
        frontend_report={},
        selector_manifest=_selector(),
        base_trusted=True,
    )

    json.dumps(result, sort_keys=True)


def test_should_reject_stale_or_malformed_selector_manifest() -> None:
    manifest = {
        "schema_version": 1,
        "head": "checked-out-sha",
        "mode": "pr",
        "selection_mode": "selected",
        "effective_base": "base-sha",
        "changes": [],
    }
    validate_selector_manifest(manifest, expected_head="checked-out-sha")

    with pytest.raises(ValueError, match="head does not match"):
        validate_selector_manifest(manifest, expected_head="different-sha")

    with pytest.raises(ValueError, match="invalid change"):
        validate_selector_manifest(
            {**manifest, "changes": [{"status": "M", "path": 123}]},
            expected_head="checked-out-sha",
        )

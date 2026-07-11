from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "select_quality_tests.py"
SPEC = importlib.util.spec_from_file_location("quality_test_selector", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

Change = MODULE.Change
CodeGraphEvidence = MODULE.CodeGraphEvidence
SelectorContext = MODULE.SelectorContext
build_diff_spec = MODULE.build_diff_spec
codegraph_status_is_healthy = MODULE.codegraph_status_is_healthy
discover_family_tests = MODULE.discover_family_tests
load_policy = MODULE.load_policy
manifest_runner_paths = MODULE.manifest_runner_paths
parse_name_status_z = MODULE.parse_name_status_z
resolve_effective_base = MODULE.resolve_effective_base
runner_paths = MODULE.runner_paths
select_tests = MODULE.select_tests
validate_codegraph_payload = MODULE.validate_codegraph_payload

POLICY_PATH = REPO_ROOT / "docs" / "architecture" / "quality-test-selection-policy.yaml"
EXPECTED_BACKEND_INTEGRATION_CRITICAL = {
    "backend/tests/integration/test_auth_login_api.py",
    "backend/tests/integration/test_history_evidence_flow.py",
    "backend/tests/integration/test_replay_api.py",
    "backend/tests/integration/test_sales_realtime_reconnect_flow.py",
    "backend/tests/integration/test_support_runtime_api.py",
    "backend/tests/integration/test_observability_surfaces.py",
    "backend/tests/integration/test_admin_business_rules_api.py",
    "backend/tests/integration/test_admin_model_configs_api.py",
    "backend/tests/integration/test_scoring_rulesets_api.py",
    "backend/tests/integration/test_supervisor_retraining_api.py",
    "backend/tests/integration/test_business_etiquette_quiz_api.py",
    "backend/tests/integration/test_business_etiquette_ai_coach_progress_api.py",
    "backend/tests/integration/test_newcomer_training_journey_api.py",
    "backend/tests/integration/test_newcomer_training_path_article_api.py",
    "backend/tests/integration/test_newcomer_training_path_config_api.py",
    "backend/tests/integration/test_newcomer_training_path_material_api.py",
    "backend/tests/integration/test_newcomer_training_path_rbac_api.py",
    "backend/tests/integration/test_practice_session_object_permissions.py",
    "backend/tests/integration/test_sales_trainer_persisted_path_unlock.py",
}
EXPECTED_PLAYWRIGHT_CRITICAL = {
    "web/tests/e2e/smoke.spec.ts",
    "web/tests/e2e/newcomer-training-closed-loop.spec.ts",
    "web/tests/e2e/presentation-phase4.spec.ts",
    "web/tests/e2e/sales-phase4.spec.ts",
}


def _policy():
    return load_policy(POLICY_PATH)


def _healthy_graph(*tests: str) -> CodeGraphEvidence:
    return CodeGraphEvidence(
        status="healthy",
        version="1.2.0",
        affected_tests=tuple(tests),
        fallback_reason=None,
    )


def test_repo_policy_preserves_the_complete_critical_baseline() -> None:
    policy = _policy()

    assert set(policy.families["backend_integration"].critical) == (
        EXPECTED_BACKEND_INTEGRATION_CRITICAL
    )
    assert set(policy.families["playwright"].critical) == (
        EXPECTED_PLAYWRIGHT_CRITICAL
    )
    assert policy.families["backend_e2e"].critical == ()


def _context(
    *changes: Change,
    codegraph: CodeGraphEvidence | None = None,
    base_trusted: bool = True,
    mode: str = "pr",
) -> SelectorContext:
    return SelectorContext(
        mode=mode,
        requested_base="base-sha",
        effective_base="base-sha" if base_trusted else None,
        head="head-sha",
        base_trusted=base_trusted,
        changes=tuple(changes),
        codegraph=codegraph or _healthy_graph(),
    )


def test_should_build_pr_and_push_diff_specs_without_head_parent_fallback() -> None:
    assert build_diff_spec("pr", "base", "head") == "base...head"
    assert build_diff_spec("push", "before", "after") == "before..after"
    with pytest.raises(ValueError, match="unsupported diff mode"):
        build_diff_spec("local", "base", "head")


def test_should_parse_add_delete_and_rename_from_nul_name_status() -> None:
    payload = b"M\x00backend/src/a.py\x00D\x00backend/src/deleted.py\x00R100\x00old.py\x00new.py\x00"

    changes = parse_name_status_z(payload)

    assert changes == (
        Change(status="M", path="backend/src/a.py"),
        Change(status="D", path="backend/src/deleted.py"),
        Change(status="R", path="new.py", old_path="old.py"),
    )


def test_should_select_critical_baseline_and_deterministic_path_rules() -> None:
    manifest = select_tests(
        _policy(),
        _context(Change("M", "backend/src/sales_trainer/services/path_service.py")),
    )

    integration = manifest["selected"]["backend_integration"]
    assert integration == sorted(integration)
    assert "backend/tests/integration/test_newcomer_training_path_config_api.py" in integration
    assert "web/tests/e2e/newcomer-training-closed-loop.spec.ts" in manifest["selected"]["playwright"]
    assert manifest["selection_mode"] == "selected"
    reasons = manifest["reasons"][
        "backend/tests/integration/test_newcomer_training_path_config_api.py"
    ]
    assert "critical-baseline" in reasons
    assert "path-policy:sales-trainer-path" in reasons


def test_should_include_direct_changed_slow_tests() -> None:
    direct = "backend/tests/integration/test_direct_change.py"
    playwright = "web/tests/e2e/audit.spec.ts"

    manifest = select_tests(
        _policy(),
        _context(Change("M", direct), Change("A", playwright)),
    )

    assert direct in manifest["selected"]["backend_integration"]
    assert playwright in manifest["selected"]["playwright"]
    assert manifest["reasons"][direct] == ["direct-change"]


def test_should_fallback_family_for_changed_test_support_without_running_it() -> None:
    support_file = "web/tests/e2e/newcomer-training-route-manifest.ts"

    manifest = select_tests(
        _policy(),
        _context(Change("M", support_file)),
    )

    assert manifest["selection_mode"] == "family-fallback"
    assert support_file not in manifest["selected"]["playwright"]
    assert set(manifest["selected"]["playwright"]) == set(
        discover_family_tests(_policy(), "playwright")
    )
    assert manifest["family_fallback_reasons"]["playwright"] == [
        f"test-support-change:{support_file}"
    ]


def test_should_full_fallback_for_cross_runner_presentation_fixture() -> None:
    fixture = (
        "backend/tests/e2e/fixtures/"
        "presentation-phase4-normal.v1.pptx.base64"
    )

    manifest = select_tests(
        _policy(),
        _context(Change("M", fixture)),
    )

    assert manifest["selection_mode"] == "full-fallback"
    assert f"global-path:{fixture}" in manifest["fallback_reasons"]
    assert "web/tests/e2e/presentation-phase4.spec.ts" in (
        manifest["selected"]["playwright"]
    )


def test_should_use_healthy_codegraph_only_as_an_additive_source() -> None:
    graph_test = "backend/tests/integration/test_graph_only.py"
    manifest = select_tests(
        _policy(),
        _context(
            Change("M", "docs/api-contract/example.md"),
            codegraph=_healthy_graph(graph_test),
        ),
    )

    assert graph_test in manifest["selected"]["backend_integration"]
    assert manifest["reasons"][graph_test] == ["codegraph-affected"]


def test_should_keep_policy_selection_when_codegraph_is_missing() -> None:
    manifest = select_tests(
        _policy(),
        _context(
            Change("M", "backend/src/sales_trainer/services/path_service.py"),
            codegraph=CodeGraphEvidence(
                "missing",
                None,
                (),
                "command-missing",
            ),
        ),
    )

    assert manifest["selection_mode"] == "selected"
    assert manifest["degraded_reasons"] == ["command-missing"]
    assert "backend/tests/integration/test_newcomer_training_path_config_api.py" in (
        manifest["selected"]["backend_integration"]
    )


@pytest.mark.parametrize(
    "evidence",
    [
        CodeGraphEvidence("invalid", "1.2.0", (), "malformed-json"),
        CodeGraphEvidence("invalid", "1.2.0", (), "empty-production-result"),
    ],
)
def test_should_full_fallback_when_codegraph_is_malformed_or_empty(
    evidence: CodeGraphEvidence,
) -> None:
    manifest = select_tests(
        _policy(),
        _context(
            Change("M", "backend/src/sales_trainer/services/path_service.py"),
            codegraph=evidence,
        ),
    )

    assert manifest["selection_mode"] == "full-fallback"
    assert evidence.fallback_reason in manifest["fallback_reasons"]
    assert len(manifest["selected"]["backend_integration"]) > 18


def test_should_discover_all_nested_playwright_specs() -> None:
    policy = _policy()
    discovered = discover_family_tests(policy, "playwright")

    assert len(discovered) >= 7
    assert "web/tests/e2e/audit/audit.spec.ts" in discovered
    assert policy.families["playwright"].codegraph_filter == "web/tests/e2e/**"


def test_should_match_literal_session_id_route_brackets() -> None:
    manifest = select_tests(
        _policy(),
        _context(
            Change(
                "M",
                "web/src/app/(user)/practice/[sessionId]/page.tsx",
            )
        ),
    )

    assert manifest["selection_mode"] == "selected"
    assert "web/tests/e2e/sales-phase4.spec.ts" in manifest["selected"]["playwright"]


def test_should_full_fallback_backend_integration_for_generic_api_change() -> None:
    manifest = select_tests(
        _policy(),
        _context(Change("M", "backend/src/example_domain/api.py")),
    )

    assert manifest["selection_mode"] == "family-fallback"
    assert len(manifest["selected"]["backend_integration"]) > 18
    assert len(manifest["selected"]["playwright"]) == 4


def test_should_apply_path_policy_to_changed_contracts_outside_production_roots() -> None:
    manifest = select_tests(
        _policy(),
        _context(
            Change(
                "M",
                "specs/001-ai-practice-system/contracts/openapi.yaml",
            )
        ),
    )

    assert manifest["selection_mode"] == "family-fallback"
    assert "backend/tests/integration/test_admin_users_api.py" in (
        manifest["selected"]["backend_integration"]
    )
    assert "path-policy:public-api" in manifest["reasons"][
        "backend/tests/integration/test_admin_users_api.py"
    ]


def test_should_not_treat_colocated_frontend_tests_as_production_changes() -> None:
    manifest = select_tests(
        _policy(),
        _context(
            Change(
                "M",
                "web/src/app/(user)/practice/[sessionId]/page.test.tsx",
            )
        ),
    )

    assert manifest["selection_mode"] == "selected"
    assert not any(
        "unknown-production-path" in reason
        for reason in manifest["fallback_reasons"]
    )


@pytest.mark.parametrize("status", ["D", "R"])
def test_should_full_fallback_for_delete_or_rename(status: str) -> None:
    change = Change(status, "backend/src/sales_trainer/services/new_name.py")
    manifest = select_tests(_policy(), _context(change))

    assert manifest["selection_mode"] == "full-fallback"
    assert any("delete-or-rename" in reason for reason in manifest["fallback_reasons"])


def test_should_full_fallback_for_untrusted_base_unknown_or_global_paths() -> None:
    untrusted = select_tests(
        _policy(),
        _context(Change("M", "docs/readme.md"), base_trusted=False),
    )
    unknown = select_tests(
        _policy(),
        _context(Change("M", "backend/src/unknown_domain/new_service.py")),
    )
    global_change = select_tests(
        _policy(),
        _context(Change("M", "backend/tests/conftest.py")),
    )
    workflow_change = select_tests(
        _policy(),
        _context(Change("M", ".github/workflows/release-truth-gate.yml")),
    )

    assert untrusted["selection_mode"] == "full-fallback"
    assert unknown["selection_mode"] == "full-fallback"
    assert global_change["selection_mode"] == "full-fallback"
    assert workflow_change["selection_mode"] == "full-fallback"


def test_should_emit_stably_sorted_json_manifest() -> None:
    manifest = select_tests(
        _policy(),
        _context(
            Change("M", "web/tests/e2e/z-last.spec.ts"),
            Change("M", "backend/tests/integration/test_a_first.py"),
        ),
    )

    rendered = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    rerendered = json.dumps(
        select_tests(
            _policy(),
            _context(
                Change("M", "backend/tests/integration/test_a_first.py"),
                Change("M", "web/tests/e2e/z-last.spec.ts"),
            ),
        ),
        ensure_ascii=False,
        sort_keys=True,
    )
    assert rendered == rerendered


def test_should_reject_runner_paths_outside_known_family_prefixes() -> None:
    with pytest.raises(ValueError, match="outside backend_integration"):
        runner_paths(
            "backend_integration",
            ["web/tests/e2e/smoke.spec.ts"],
        )
    with pytest.raises(ValueError, match="outside playwright"):
        runner_paths(
            "playwright",
            ["web/tests/e2e/smoke.spec.ts\n--config=attacker.ts"],
        )
    with pytest.raises(ValueError, match="outside playwright"):
        runner_paths(
            "playwright",
            ["web/tests/e2e/global-setup.ts"],
        )


def test_should_emit_manifest_paths_relative_to_each_runner_working_directory() -> None:
    manifest = {
        "schema_version": 1,
        "selected": {
            "backend_integration": [
                "backend/tests/integration/test_auth_login_api.py",
            ],
            "backend_e2e": ["backend/tests/e2e/test_release.py"],
            "playwright": ["web/tests/e2e/smoke.spec.ts"],
        }
    }

    assert manifest_runner_paths(manifest, "backend_integration") == [
        "tests/integration/test_auth_login_api.py",
    ]
    assert manifest_runner_paths(manifest, "backend_e2e") == [
        "tests/e2e/test_release.py",
    ]
    assert manifest_runner_paths(manifest, "playwright") == [
        "tests/e2e/smoke.spec.ts",
    ]

    manifest["selected"]["playwright"] = ["../../outside.spec.ts"]
    with pytest.raises(ValueError, match="outside playwright"):
        manifest_runner_paths(manifest, "playwright")

    manifest["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        manifest_runner_paths(manifest, "backend_integration")


def test_should_validate_codegraph_json_schema_and_paths(tmp_path: Path) -> None:
    test_path = tmp_path / "backend" / "tests" / "integration" / "test_ok.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("", encoding="utf-8")
    helper_path = tmp_path / "web" / "tests" / "e2e" / "helpers.ts"
    helper_path.parent.mkdir(parents=True)
    helper_path.write_text("", encoding="utf-8")
    payload = {
        "changedFiles": ["backend/src/example.py"],
        "affectedTests": [
            "backend/tests/integration/test_ok.py",
            "web/tests/e2e/helpers.ts",
        ],
        "totalDependentsTraversed": 4,
    }

    evidence = validate_codegraph_payload(
        json.dumps(payload),
        repo_root=tmp_path,
        version="1.2.0",
    )
    malformed = validate_codegraph_payload(
        "\x1b[31mnot-json",
        repo_root=tmp_path,
        version="1.2.0",
    )

    assert evidence.status == "healthy"
    assert evidence.affected_tests == (
        "backend/tests/integration/test_ok.py",
    )
    assert malformed.status == "invalid"
    assert malformed.fallback_reason == "malformed-json"


def test_should_require_all_codegraph_pending_change_counts_to_be_zero() -> None:
    healthy = {
        "initialized": True,
        "pendingChanges": {"added": 0, "modified": 0, "removed": 0},
        "worktreeMismatch": None,
    }
    dirty = {
        **healthy,
        "pendingChanges": {"added": 1, "modified": 0, "removed": 0},
    }

    assert codegraph_status_is_healthy(healthy) is True
    assert codegraph_status_is_healthy(dirty) is False
    assert codegraph_status_is_healthy({**healthy, "pendingChanges": []}) is False


def test_should_use_temporary_adoption_anchor_until_base_contains_it() -> None:
    policy = _policy()
    anchor = policy.adoption_anchor.commit
    used = resolve_effective_base(
        requested_base="old-base",
        head="head",
        policy=policy,
        object_exists=lambda value: value in {"old-base", "head", anchor},
        is_ancestor=lambda ancestor, descendant: (
            ancestor == anchor and descendant == "head"
        ),
        today=date(2026, 7, 10),
    )
    retired = resolve_effective_base(
        requested_base="new-base",
        head="head",
        policy=policy,
        object_exists=lambda _value: True,
        is_ancestor=lambda ancestor, descendant: ancestor == anchor,
        today=date(2026, 7, 10),
    )

    assert used.effective_base == anchor
    assert used.used_adoption_anchor is True
    assert retired.effective_base == "new-base"
    assert retired.used_adoption_anchor is False


def test_should_fail_closed_when_adoption_anchor_expires() -> None:
    policy = _policy()
    with pytest.raises(ValueError, match="adoption anchor expired"):
        resolve_effective_base(
            requested_base="old-base",
            head="head",
            policy=policy,
            object_exists=lambda _value: True,
            is_ancestor=lambda _ancestor, _descendant: False,
            today=date(2026, 8, 11),
        )


def test_should_reject_expired_or_malformed_selection_policy(
    tmp_path: Path,
) -> None:
    raw = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    raw["adoption_anchor"]["expires_on"] = "2026-07-09"
    expired = tmp_path / "docs" / "architecture" / "expired.yaml"
    expired.parent.mkdir(parents=True)
    expired.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="adoption anchor expired"):
        load_policy(expired, today=date(2026, 7, 10))

    raw["adoption_anchor"]["expires_on"] = "2026-08-10"
    raw["path_rules"][0]["select"]["backend_integration"] = "not-a-list"
    malformed = tmp_path / "docs" / "architecture" / "malformed.yaml"
    malformed.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="must be a string list"):
        load_policy(malformed, today=date(2026, 7, 10))

    raw["path_rules"][0]["select"] = {}
    no_op = tmp_path / "docs" / "architecture" / "no-op.yaml"
    no_op.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="must select tests"):
        load_policy(no_op, today=date(2026, 7, 10))

    raw["path_rules"][0]["select"] = {
        "playwright": ["web/tests/e2e/smoke.spec.ts"],
    }
    raw["families"]["playwright"]["glob"] = "web/tests/e2e/smoke.spec.ts"
    narrowed_family = tmp_path / "docs" / "architecture" / "narrowed.yaml"
    narrowed_family.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical discovery contract"):
        load_policy(narrowed_family, today=date(2026, 7, 10))

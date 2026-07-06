from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "export_newcomer_dead_data_diagnostics.py"
)


def _load_export_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "export_newcomer_dead_data_diagnostics", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_export_payload_keeps_dead_data_export_dry_run_and_sampled() -> None:
    module = _load_export_module()

    payload = module.build_export_payload(
        {
            "generated_at": "2026-06-29T00:00:00+00:00",
            "summary": {"total": 3, "error": 1, "warning": 1, "info": 1},
            "scanned": {
                "revisions": [{"revision_id": "rev-1"}, {"revision_id": "rev-2"}],
                "audio_submissions": {"scanned": 7},
                "materials": {
                    "materials": 3,
                    "versions": 4,
                    "total_materials": 8,
                    "total_versions": 9,
                    "limit": 100,
                    "truncated": True,
                },
                "material_scan_limit": 100,
            },
            "issues": [
                {
                    "severity": "warning",
                    "code": "AUDIO_LEGACY_RESULT",
                    "source": "audio_submission",
                    "resource_type": "audio_submission",
                    "resource_id": "audio-1",
                    "metadata": {"legacy_snapshot_only": True},
                },
                {
                    "severity": "error",
                    "code": "AUDIO_LEGACY_RESULT",
                    "source": "audio_submission",
                    "resource_type": "audio_submission",
                    "resource_id": "audio-2",
                },
                {
                    "severity": "info",
                    "code": "ORPHAN_MATERIAL_VERSION",
                    "source": "material_inventory",
                    "resource_type": "sales_trainer_material_version",
                    "resource_id": "material-version-1",
                },
            ],
            "candidate_actions": [
                {
                    "code": "legacy_audio_replay",
                    "resource_type": "audio_submission",
                    "resource_id": "audio-1",
                    "safe_to_apply_automatically": False,
                    "requires_manual_approval": True,
                },
                {
                    "code": "inventory_note",
                    "resource_type": "sales_trainer_material_version",
                    "resource_id": "material-version-1",
                    "safe_to_apply_automatically": False,
                    "requires_manual_approval": False,
                },
            ],
            "manual_decisions": [{"code": "legacy_audio_replay"}],
            "rollback_plan": {"required": False},
        },
        sample_limit=1,
        scan_limit=1000,
        material_scan_limit=100,
    )

    assert payload["mode"] == "dry_run"
    assert payload["mutates_history"] is False
    assert payload["requires_manual_approval"] is True
    assert payload["summary"] == {
        "total_issues": 3,
        "error": 1,
        "warning": 1,
        "info": 1,
        "total_scanned_records": 16,
        "auto_backfill_candidates": 0,
        "auto_backfill_records": 0,
        "manual_review_required": 1,
        "manual_review_records": 1,
        "legacy_or_read_only_replay_candidates": 2,
        "legacy_mark_records": 2,
        "candidate_actions": 2,
        "manual_decisions": 1,
    }
    assert payload["scan_scope"]["limit"] == 1000
    assert payload["scan_scope"]["audio_scan_limit"] == 1000
    assert payload["scan_scope"]["material_scan_limit"] == 100
    assert payload["scan_scope"]["include_issues"] is False
    assert payload["scan_scope"]["materials_total"] == 8
    assert payload["scan_scope"]["material_versions_total"] == 9
    assert payload["scan_scope"]["material_inventory_truncated"] is True
    assert payload["sample_resource_ids_by_issue_code"] == {
        "AUDIO_LEGACY_RESULT": ["audio-1"],
        "ORPHAN_MATERIAL_VERSION": ["material-version-1"],
    }
    assert payload["sample_record_ids"] == {
        "auto_backfill": [],
        "manual_review": ["audio_submission:audio-1"],
        "legacy_mark": ["audio_submission:audio-1"],
    }
    assert payload["expected_write_fields"]["auto_backfill"] == []
    assert "path_revision_id" in payload["expected_write_fields"][
        "manual_lineage_backfill_candidates"
    ]
    assert payload["issues"] == []
    assert payload["issues_omitted"] is True


def test_build_export_payload_redacts_sensitive_nested_fields() -> None:
    module = _load_export_module()

    payload = module.build_export_payload(
        {
            "summary": {},
            "scanned": {
                "audio_submissions": {"scanned": 1},
                "contact_phone": "should-not-leak",
            },
            "issues": [
                {
                    "code": "PATH_REVISION_PAYLOAD_INVALID",
                    "resource_id": "revision-1",
                    "metadata": {
                        "api_key": "should-not-leak",
                        "nested": {"Authorization": "Bearer should-not-leak"},
                    },
                }
            ],
            "candidate_actions": [
                {
                    "code": "manual_repair",
                    "requires_manual_approval": True,
                    "operator_email": "should-not-leak",
                }
            ],
            "manual_decisions": [{"token": "should-not-leak"}],
            "rollback_plan": {"secret_note": "should-not-leak"},
        },
        sample_limit=5,
        include_issues=True,
    )
    payload_json = json.dumps(payload, ensure_ascii=False)

    assert "should-not-leak" not in payload_json
    assert payload["scanned"]["contact_phone"] == "<redacted>"
    assert payload["issues"][0]["metadata"]["api_key"] == "<redacted>"
    assert payload["issues"][0]["metadata"]["nested"]["Authorization"] == "<redacted>"
    assert payload["candidate_actions"][0]["operator_email"] == "<redacted>"
    assert payload["manual_decisions"][0]["token"] == "<redacted>"
    assert payload["rollback_plan"]["secret_note"] == "<redacted>"


def test_parse_args_supports_explicit_dry_run_and_limit_alias() -> None:
    module = _load_export_module()

    args = module.parse_args(
        [
            "--dry-run",
            "--limit",
            "1000",
            "--material-scan-limit",
            "25",
            "--sample-limit",
            "3",
            "--include-issues",
        ]
    )

    assert args.dry_run is True
    assert args.audio_scan_limit == 1000
    assert args.material_scan_limit == 25
    assert args.sample_limit == 3
    assert args.include_issues is True


def test_parse_args_rejects_invalid_material_scan_limit() -> None:
    module = _load_export_module()

    with pytest.raises(SystemExit) as exc_info:
        module.parse_args(["--material-scan-limit", "0"])

    assert exc_info.value.code == 2

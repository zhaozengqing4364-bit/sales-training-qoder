from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from common.analytics import release_readiness
from common.analytics.release_readiness import (
    run_release_readiness_checks,
    validate_production_config,
    verify_openapi_parity,
    verify_phase4_e2e_evidence,
)
from common.monitoring.logger import REDACTED_VALUE, sanitize_log_kwargs


def test_validate_production_config_rejects_unsafe_values() -> None:
    findings = validate_production_config(
        {
            "ENVIRONMENT": "production",
            "DEV_LOGIN_ENABLED": "true",
            "SECRET_KEY": "change-me",
            "DEBUG": "true",
            "CORS_ORIGINS": "*",
        }
    )

    assert {finding.code for finding in findings} == {
        "PROD_DEV_LOGIN_ENABLED",
        "PROD_SECRET_KEY_UNSAFE",
        "PROD_DEBUG_TRUE",
        "PROD_CORS_WIDE_OPEN",
    }


def test_validate_production_config_rejects_wide_open_cors_regex() -> None:
    findings = validate_production_config(
        {
            "ENVIRONMENT": "production",
            "SECRET_KEY": "production-secret-key-with-32-characters",
            "DEBUG": "false",
            "CORS_ALLOW_ORIGIN_REGEX": r"^https?://.*$",
        }
    )

    assert {finding.code for finding in findings} == {"PROD_CORS_WIDE_OPEN"}


def test_sanitize_log_kwargs_masks_sensitive_values_instead_of_omitting() -> None:
    sanitized = sanitize_log_kwargs(
        {
            "access_token": "token-value",
            "session_cookie": "cookie=value",
            "password": "password-value",
            "user_email": "person@example.com",
        }
    )

    assert sanitized == {
        "access_token": REDACTED_VALUE,
        "session_cookie": REDACTED_VALUE,
        "password": REDACTED_VALUE,
        "user_email": "pe***@example.com",
    }
    assert "token-value" not in json.dumps(sanitized)
    assert "cookie=value" not in json.dumps(sanitized)
    assert "password-value" not in json.dumps(sanitized)
    assert "person@example.com" not in json.dumps(sanitized)


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(entry)}\n" for entry in entries),
        encoding="utf-8",
    )


def test_verify_phase4_e2e_evidence_accepts_clean_issue43_and_issue44_manifests(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / release_readiness.ISSUE43_MANIFEST,
        [
            {
                "path": "sales",
                "repeat_each_index": index,
                "session_id": f"sales-session-{index}",
                "agent_id": f"sales-agent-{index}",
                "persona_id": f"sales-persona-{index}",
                "diagnostics": {
                    "report_status": "completed",
                    "evaluation_status": "succeeded",
                    "report_snapshot_exists": True,
                },
            }
            for index in range(3)
        ],
    )
    _write_jsonl(
        tmp_path / release_readiness.ISSUE44_MANIFEST,
        [
            *[
                {
                    "path": "normal",
                    "repeat_each_index": index,
                    "session_id": f"session-{index}",
                    "presentation_id": f"presentation-{index}",
                    "diagnostics": {"report_status": "completed"},
                }
                for index in range(3)
            ],
            *[
                {
                    "path": "corrupted",
                    "repeat_each_index": index,
                    "degradation": {
                        "session_create_status": 400,
                        "no_success_evidence_fabricated": True,
                    },
                }
                for index in range(3)
            ],
        ],
    )

    findings, details = verify_phase4_e2e_evidence(tmp_path)

    assert findings == []
    assert details["issue43"]["3_clean_runs"] is True
    assert details["issue43"]["clean_runs"] == [0, 1, 2]
    assert details["issue43"]["independent_session_count"] == 3
    assert details["issue44"]["3_clean_runs"] is True


def test_verify_phase4_e2e_evidence_rejects_issue43_notepad_transcript_fallback(
    tmp_path: Path,
) -> None:
    _write_jsonl(
        tmp_path / ".sisyphus/evidence/issue-43-provider-transcript.jsonl",
        [
            {"direction": "provider", "payload": {"type": "response.done"}},
            {"direction": "provider_close"},
        ],
    )
    notepad_path = tmp_path / ".sisyphus/notepads/prd-23-full-implementation/learnings.md"
    notepad_path.parent.mkdir(parents=True, exist_ok=True)
    notepad_path.write_text(
        "`bash scripts/issue43-sales-e2e-triple-run.sh` → 3 passed\n",
        encoding="utf-8",
    )
    _write_jsonl(
        tmp_path / release_readiness.ISSUE44_MANIFEST,
        [
            *[
                {
                    "path": "normal",
                    "repeat_each_index": index,
                    "session_id": f"session-{index}",
                    "presentation_id": f"presentation-{index}",
                    "diagnostics": {"report_status": "completed"},
                }
                for index in range(3)
            ],
            *[
                {
                    "path": "corrupted",
                    "repeat_each_index": index,
                    "degradation": {
                        "session_create_status": 400,
                        "no_success_evidence_fabricated": True,
                    },
                }
                for index in range(3)
            ],
        ],
    )

    findings, details = verify_phase4_e2e_evidence(tmp_path)

    assert {finding.code for finding in findings} == {"PHASE4_ISSUE43_MANIFEST_MISSING"}
    assert details["issue43"] == {
        "manifest_path": str(release_readiness.ISSUE43_MANIFEST),
        "3_clean_runs": False,
    }


def test_verify_phase4_e2e_evidence_rejects_issue43_manifest_without_completed_report_diagnostics(
    tmp_path: Path,
) -> None:
    _write_jsonl(
        tmp_path / release_readiness.ISSUE43_MANIFEST,
        [
            {
                "path": "sales",
                "repeat_each_index": index,
                "session_id": f"sales-session-{index}",
                "agent_id": f"sales-agent-{index}",
                "persona_id": f"sales-persona-{index}",
                "diagnostics": {"report_status": "completed"},
            }
            for index in range(3)
        ],
    )
    _write_jsonl(
        tmp_path / release_readiness.ISSUE44_MANIFEST,
        [
            *[
                {
                    "path": "normal",
                    "repeat_each_index": index,
                    "session_id": f"session-{index}",
                    "presentation_id": f"presentation-{index}",
                    "diagnostics": {"report_status": "completed"},
                }
                for index in range(3)
            ],
            *[
                {
                    "path": "corrupted",
                    "repeat_each_index": index,
                    "degradation": {
                        "session_create_status": 400,
                        "no_success_evidence_fabricated": True,
                    },
                }
                for index in range(3)
            ],
        ],
    )

    findings, details = verify_phase4_e2e_evidence(tmp_path)

    assert {finding.code for finding in findings} == {"PHASE4_ISSUE43_MANIFEST_INCOMPLETE"}
    assert details["issue43"]["3_clean_runs"] is False
    assert details["issue43"]["clean_runs"] == []


def test_verify_phase4_e2e_evidence_reports_missing_manifest(tmp_path: Path) -> None:
    findings, details = verify_phase4_e2e_evidence(tmp_path)

    assert "PHASE4_ISSUE43_MANIFEST_MISSING" in {finding.code for finding in findings}
    assert "PHASE4_ISSUE44_MANIFEST_MISSING" in {finding.code for finding in findings}
    assert details["issue43"]["3_clean_runs"] is False
    assert details["issue44"]["3_clean_runs"] is False


def test_verify_openapi_parity_uses_canonical_contract_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app_factory import create_app

    contract_path = Path("contract/openapi.yaml")
    full_contract_path = tmp_path / contract_path
    full_contract_path.parent.mkdir(parents=True)
    full_contract_path.write_text(
        yaml.safe_dump(create_app().openapi(), sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_readiness, "CANONICAL_OPENAPI_CONTRACT", contract_path)

    findings, details = verify_openapi_parity(tmp_path)

    assert findings == []
    assert details["canonical_contract_path"] == str(contract_path)


def test_run_release_readiness_checks_reports_secret_and_manifest_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release_readiness,
        "verify_openapi_parity",
        lambda repo_root: ([], {"canonical_contract_path": "test"}),
    )

    report = run_release_readiness_checks(
        tmp_path,
        env={
            "ENVIRONMENT": "production",
            "SECRET_KEY": "change-me",
            "DEBUG": "false",
            "CORS_ORIGINS": "https://app.example.com",
        },
    )

    assert report.passed is False
    assert "PROD_SECRET_KEY_UNSAFE" in {finding.code for finding in report.findings}
    assert "PHASE4_ISSUE44_MANIFEST_MISSING" in {
        finding.code for finding in report.findings
    }

"""Phase 5 release readiness checks for the release verification gate."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CANONICAL_OPENAPI_CONTRACT = Path(
    "specs/001-ai-practice-system/contracts/openapi.yaml"
)
ISSUE43_MANIFEST = Path(".sisyphus/evidence/issue-43-run-manifest.jsonl")
ISSUE44_MANIFEST = Path(".sisyphus/evidence/issue-44-run-manifest.jsonl")

DEFAULT_SECRET_KEYS = {
    "",
    "default",
    "secret",
    "change-me",
    "your-super-secret-key-change-in-production-min-32-chars",
}


@dataclass(frozen=True, slots=True)
class ReleaseReadinessFinding:
    """One blocking Phase 5 readiness finding."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class ReleaseReadinessReport:
    """Machine-readable release readiness report."""

    passed: bool
    findings: list[ReleaseReadinessFinding]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [asdict(finding) for finding in self.findings],
            "details": self.details,
        }


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_wide_open_cors_regex(value: str) -> bool:
    normalized = value.strip()
    unanchored = normalized.removeprefix("^").removesuffix("$")
    if normalized in {".*", "^.*$", "*"} or unanchored in {".*", "*"}:
        return True

    for scheme_prefix in ("https?://", "https://", "http://"):
        if unanchored.startswith(scheme_prefix):
            return unanchored.removeprefix(scheme_prefix) in {".*", ".+"}
    return False


def validate_production_config(env: dict[str, str] | None = None) -> list[ReleaseReadinessFinding]:
    """Validate production-only hardening requirements from an explicit env map."""

    env_map = env or dict(os.environ)
    environment = env_map.get("ENVIRONMENT", "development").strip().lower()
    if environment not in {"production", "prod"}:
        return []

    findings: list[ReleaseReadinessFinding] = []
    secret_key = env_map.get("SECRET_KEY", "").strip()
    cors_origins = [
        item.strip() for item in env_map.get("CORS_ORIGINS", "").split(",") if item.strip()
    ]
    cors_regex = env_map.get("CORS_ALLOW_ORIGIN_REGEX", "").strip()

    if _truthy(env_map.get("DEV_LOGIN_ENABLED")) or _truthy(
        env_map.get("AUTH_ENABLE_DEV_LOGIN")
    ):
        findings.append(
            ReleaseReadinessFinding(
                code="PROD_DEV_LOGIN_ENABLED",
                message="Production must reject DEV_LOGIN_ENABLED/AUTH_ENABLE_DEV_LOGIN.",
            )
        )
    if secret_key.lower() in DEFAULT_SECRET_KEYS or len(secret_key) < 32:
        findings.append(
            ReleaseReadinessFinding(
                code="PROD_SECRET_KEY_UNSAFE",
                message="Production SECRET_KEY must be explicit, non-default, and at least 32 characters.",
            )
        )
    if _truthy(env_map.get("DEBUG")):
        findings.append(
            ReleaseReadinessFinding(
                code="PROD_DEBUG_TRUE",
                message="Production must reject DEBUG=true.",
            )
        )
    if "*" in cors_origins or _is_wide_open_cors_regex(cors_regex):
        findings.append(
            ReleaseReadinessFinding(
                code="PROD_CORS_WIDE_OPEN",
                message="Production CORS must use explicit origins and cannot be wide open.",
            )
        )

    return findings


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                entries.append(parsed)
    return entries


def _repeat_index(entry: dict[str, Any]) -> int | None:
    index = entry.get("repeat_each_index")
    return index if isinstance(index, int) else None


def _verify_issue44_manifest(repo_root: Path) -> tuple[list[ReleaseReadinessFinding], dict[str, Any]]:
    path = repo_root / ISSUE44_MANIFEST
    if not path.exists():
        return [
            ReleaseReadinessFinding(
                code="PHASE4_ISSUE44_MANIFEST_MISSING",
                message="Issue #44 manifest is missing.",
                path=str(ISSUE44_MANIFEST),
            )
        ], {"manifest_path": str(ISSUE44_MANIFEST), "3_clean_runs": False}

    entries = _read_jsonl(path)
    normal = [entry for entry in entries if entry.get("path") == "normal"]
    corrupted = [entry for entry in entries if entry.get("path") == "corrupted"]
    clean_normal_indexes = {
        index
        for entry in normal
        if (index := _repeat_index(entry)) is not None
        if (entry.get("diagnostics") or {}).get("report_status") == "completed"
        and entry.get("session_id")
        and entry.get("presentation_id")
    }
    clean_corrupted_indexes = {
        index
        for entry in corrupted
        if (index := _repeat_index(entry)) is not None
        if (entry.get("degradation") or {}).get("no_success_evidence_fabricated") is True
        and (entry.get("degradation") or {}).get("session_create_status") == 400
    }
    passed = clean_normal_indexes == {0, 1, 2} and clean_corrupted_indexes == {0, 1, 2}
    detail = {
        "manifest_path": str(ISSUE44_MANIFEST),
        "normal_clean_runs": sorted(clean_normal_indexes),
        "corrupted_clean_runs": sorted(clean_corrupted_indexes),
        "3_clean_runs": passed,
    }
    if passed:
        return [], detail
    return [
        ReleaseReadinessFinding(
            code="PHASE4_ISSUE44_MANIFEST_INCOMPLETE",
            message="Issue #44 manifest must prove 3 normal clean runs and 3 corrupted degradation runs.",
            path=str(ISSUE44_MANIFEST),
        )
    ], detail


def _verify_issue43_evidence(repo_root: Path) -> tuple[list[ReleaseReadinessFinding], dict[str, Any]]:
    manifest_path = repo_root / ISSUE43_MANIFEST
    if not manifest_path.exists():
        return [
            ReleaseReadinessFinding(
                code="PHASE4_ISSUE43_MANIFEST_MISSING",
                message="Issue #43 manifest is missing.",
                path=str(ISSUE43_MANIFEST),
            )
        ], {"manifest_path": str(ISSUE43_MANIFEST), "3_clean_runs": False}

    entries = _read_jsonl(manifest_path)
    clean_entries = [
        entry
        for entry in entries
        if _repeat_index(entry) is not None
        and entry.get("path") == "sales"
        and entry.get("session_id")
        and entry.get("agent_id")
        and entry.get("persona_id")
        and (entry.get("diagnostics") or {}).get("report_status") == "completed"
        and (entry.get("diagnostics") or {}).get("evaluation_status") == "succeeded"
        and (entry.get("diagnostics") or {}).get("report_snapshot_exists") is True
    ]
    clean_indexes = {_repeat_index(entry) for entry in clean_entries}
    session_ids = {
        entry.get("session_id") for entry in clean_entries if isinstance(entry.get("session_id"), str)
    }
    passed = clean_indexes == {0, 1, 2} and len(session_ids) == 3
    detail = {
        "manifest_path": str(ISSUE43_MANIFEST),
        "clean_runs": sorted(index for index in clean_indexes if index is not None),
        "independent_session_count": len(session_ids),
        "3_clean_runs": passed,
    }
    if passed:
        return [], detail
    return [
        ReleaseReadinessFinding(
            code="PHASE4_ISSUE43_MANIFEST_INCOMPLETE",
            message="Issue #43 manifest must prove 3 independent clean Sales runs with completed report diagnostics.",
            path=str(ISSUE43_MANIFEST),
        )
    ], detail


def verify_phase4_e2e_evidence(repo_root: Path) -> tuple[list[ReleaseReadinessFinding], dict[str, Any]]:
    """Verify latest #43/#44 Phase 4 E2E evidence without rerunning E2E flows."""

    issue43_findings, issue43_detail = _verify_issue43_evidence(repo_root)
    issue44_findings, issue44_detail = _verify_issue44_manifest(repo_root)
    return issue43_findings + issue44_findings, {
        "issue43": issue43_detail,
        "issue44": issue44_detail,
    }


def _normalize_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Normalize generated metadata only; paths/components remain strict parity."""

    normalized = json.loads(json.dumps(spec, sort_keys=True))
    normalized.pop("servers", None)
    return normalized


def verify_openapi_parity(repo_root: Path) -> tuple[list[ReleaseReadinessFinding], dict[str, Any]]:
    """Compare runtime OpenAPI with the canonical submitted contract path."""

    contract_path = repo_root / CANONICAL_OPENAPI_CONTRACT
    if not contract_path.exists():
        return [
            ReleaseReadinessFinding(
                code="OPENAPI_CONTRACT_MISSING",
                message="Canonical OpenAPI contract is missing.",
                path=str(CANONICAL_OPENAPI_CONTRACT),
            )
        ], {"canonical_contract_path": str(CANONICAL_OPENAPI_CONTRACT)}

    from app_factory import create_app

    yaml = importlib.import_module("yaml")
    runtime = _normalize_openapi(create_app().openapi())
    submitted = _normalize_openapi(yaml.safe_load(contract_path.read_text(encoding="utf-8")))
    runtime_paths = set((runtime.get("paths") or {}).keys())
    submitted_paths = set((submitted.get("paths") or {}).keys())
    details = {
        "canonical_contract_path": str(CANONICAL_OPENAPI_CONTRACT),
        "runtime_path_count": len(runtime_paths),
        "contract_path_count": len(submitted_paths),
        "missing_runtime_paths": sorted(submitted_paths - runtime_paths),
        "extra_runtime_paths": sorted(runtime_paths - submitted_paths),
    }
    if runtime == submitted:
        return [], details
    return [
        ReleaseReadinessFinding(
            code="OPENAPI_PARITY_MISMATCH",
            message="Runtime OpenAPI does not match the canonical submitted contract.",
            path=str(CANONICAL_OPENAPI_CONTRACT),
        )
    ], details


def run_release_readiness_checks(
    repo_root: Path,
    env: dict[str, str] | None = None,
) -> ReleaseReadinessReport:
    """Run all Phase 5 release readiness checks."""

    findings = validate_production_config(env)
    manifest_findings, manifest_details = verify_phase4_e2e_evidence(repo_root)
    openapi_findings, openapi_details = verify_openapi_parity(repo_root)
    findings.extend(manifest_findings)
    findings.extend(openapi_findings)
    details = {
        "production_config_checked": (env or os.environ).get("ENVIRONMENT") in {
            "production",
            "prod",
        },
        "phase4_e2e": manifest_details,
        "openapi": openapi_details,
    }
    return ReleaseReadinessReport(passed=not findings, findings=findings, details=details)

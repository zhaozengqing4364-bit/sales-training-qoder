#!/usr/bin/env python3
"""Export newcomer training dead-data diagnostics as a no-mutation dry run."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent.models as _agent_models  # noqa: E402,F401 - register ORM mappers
from common.db.session import AsyncSessionLocal  # noqa: E402
from sales_trainer.services.newcomer_dead_data_diagnostics_service import (  # noqa: E402
    NewcomerDeadDataDiagnosticsService,
)

load_dotenv()

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "answer",
    "authorization",
    "bearer",
    "email",
    "file_hash",
    "mobile",
    "original_filename",
    "password",
    "phone",
    "prompt",
    "scoring_template",
    "secret",
    "storage_key",
    "system_prompt",
    "token",
    "transcript",
)
_REDACTED = "<redacted>"
_EXPECTED_WRITE_FIELDS = {
    "auto_backfill": [],
    "manual_lineage_backfill_candidates": [
        "path_revision_id",
        "path_revision_no",
        "module_key",
        "prompt_revision_id",
        "material_revision_id",
        "exam_paper_id",
    ],
    "legacy_mark_candidates": [
        "legacy_snapshot_only",
        "regrade_unavailable",
    ],
    "asset_repair_candidates": [
        "material_id",
        "material_version_id",
        "scoring_prompt_id",
        "learning_content_id",
        "exam_paper_id",
    ],
}


def build_export_payload(
    report: dict[str, Any],
    *,
    sample_limit: int,
    scan_limit: int | None = None,
    material_scan_limit: int | None = None,
    include_issues: bool = False,
) -> dict[str, Any]:
    issues = _dict_list(report.get("issues"))
    candidate_actions = _dict_list(report.get("candidate_actions"))
    manual_decisions = _dict_list(report.get("manual_decisions"))
    summary = _dict(report.get("summary"))
    scanned = _dict(report.get("scanned"))

    sample_ids: dict[str, list[str]] = defaultdict(list)
    legacy_issues = [issue for issue in issues if _is_legacy_issue(issue)]
    manual_actions = [
        action
        for action in candidate_actions
        if bool(action.get("requires_manual_approval"))
    ]
    automatic_actions = [
        action
        for action in candidate_actions
        if bool(action.get("safe_to_apply_automatically"))
    ]
    sample_record_ids = {
        "auto_backfill": _sample_record_ids(
            automatic_actions,
            sample_limit=sample_limit,
        ),
        "manual_review": _sample_record_ids(
            manual_actions,
            sample_limit=sample_limit,
        ),
        "legacy_mark": _sample_record_ids(
            legacy_issues,
            sample_limit=sample_limit,
        ),
    }
    for issue in issues:
        code = str(issue.get("code") or "UNKNOWN")
        resource_id = issue.get("resource_id")
        if resource_id is None or len(sample_ids[code]) >= sample_limit:
            continue
        sample_ids[code].append(str(resource_id))

    legacy_issue_count = len(legacy_issues)
    manual_review_count = _unique_record_count(manual_actions)
    automatic_count = _unique_record_count(automatic_actions)
    legacy_mark_count = _unique_record_count(legacy_issues)

    payload = {
        "mode": "dry_run",
        "mutates_history": False,
        "requires_manual_approval": True,
        "source": "NewcomerDeadDataDiagnosticsService",
        "generated_at": report.get("generated_at"),
        "scan_scope": {
            "limit": scan_limit if scan_limit is not None else scanned.get("audio_scan_limit"),
            "audio_scan_limit": scan_limit
            if scan_limit is not None
            else scanned.get("audio_scan_limit"),
            "material_scan_limit": material_scan_limit
            if material_scan_limit is not None
            else scanned.get("material_scan_limit"),
            "sample_limit": sample_limit,
            "include_issues": include_issues,
            "models": [
                "SalesTrainerAssetRevision",
                "SalesTrainerAudioSubmission",
                "SalesTrainerMaterial",
                "SalesTrainerMaterialVersion",
            ],
            "active_revision_id": scanned.get("active_revision_id"),
            "working_revision_id": scanned.get("working_revision_id"),
            "audio_submissions_scanned": _dict(scanned.get("audio_submissions")).get(
                "scanned"
            ),
            "materials_scanned": _dict(scanned.get("materials")).get("materials"),
            "material_versions_scanned": _dict(scanned.get("materials")).get("versions"),
            "materials_total": _dict(scanned.get("materials")).get("total_materials"),
            "material_versions_total": _dict(scanned.get("materials")).get(
                "total_versions"
            ),
            "material_inventory_truncated": _dict(scanned.get("materials")).get(
                "truncated"
            ),
        },
        "summary": {
            "total_issues": int(summary.get("total") or len(issues)),
            "error": int(summary.get("error") or 0),
            "warning": int(summary.get("warning") or 0),
            "info": int(summary.get("info") or 0),
            "total_scanned_records": _total_scanned_records(scanned),
            "auto_backfill_candidates": automatic_count,
            "auto_backfill_records": automatic_count,
            "manual_review_required": manual_review_count,
            "manual_review_records": manual_review_count,
            "legacy_or_read_only_replay_candidates": legacy_issue_count,
            "legacy_mark_records": legacy_mark_count,
            "candidate_actions": len(candidate_actions),
            "manual_decisions": len(manual_decisions),
        },
        "scanned": scanned,
        "sample_resource_ids_by_issue_code": dict(sample_ids),
        "sample_record_ids": sample_record_ids,
        "expected_write_fields": _EXPECTED_WRITE_FIELDS,
        "warnings": [
            "dry_run_only_no_database_mutation",
            "manual_approval_required_before_any_history_backfill",
            "do_not_use_latest_active_revision_to_fabricate_legacy_lineage",
        ],
        "candidate_actions": _sample_records(candidate_actions, sample_limit=sample_limit),
        "manual_decisions": manual_decisions,
        "rollback_plan": report.get("rollback_plan"),
        "issues": issues if include_issues else [],
        "issues_omitted": not include_issues,
    }
    return _redact_sensitive(payload)


async def export_dead_data_diagnostics(
    *,
    audio_scan_limit: int,
    material_scan_limit: int,
    sample_limit: int,
    include_issues: bool,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        report = await NewcomerDeadDataDiagnosticsService(
            db,
            audio_scan_limit=audio_scan_limit,
            material_scan_limit=material_scan_limit,
        ).build_report()
    return build_export_payload(
        report,
        sample_limit=sample_limit,
        scan_limit=audio_scan_limit,
        material_scan_limit=material_scan_limit,
        include_issues=include_issues,
    )


def _total_scanned_records(scanned: dict[str, Any]) -> int:
    total = 0
    audio = _dict(scanned.get("audio_submissions"))
    total += int(audio.get("scanned") or 0)
    materials = _dict(scanned.get("materials"))
    total += int(materials.get("materials") or 0)
    total += int(materials.get("versions") or 0)
    revisions = scanned.get("revisions")
    if isinstance(revisions, list):
        total += len(revisions)
    return total


def _is_legacy_issue(issue: dict[str, Any]) -> bool:
    metadata = _dict(issue.get("metadata"))
    return bool(
        issue.get("source") == "audio_submission"
        or metadata.get("legacy_snapshot_only")
        or metadata.get("regrade_unavailable")
    )


def _unique_record_count(items: list[dict[str, Any]]) -> int:
    return len({_record_key(item) for item in items})


def _sample_record_ids(items: list[dict[str, Any]], *, sample_limit: int) -> list[str]:
    samples: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = _record_key(item)
        if key in seen:
            continue
        seen.add(key)
        samples.append(key)
        if len(samples) >= sample_limit:
            break
    return samples


def _sample_records(items: list[dict[str, Any]], *, sample_limit: int) -> list[dict[str, Any]]:
    if sample_limit == 0:
        return []
    return items[:sample_limit]


def _record_key(item: dict[str, Any]) -> str:
    resource_type = str(item.get("resource_type") or "unknown")
    resource_id = item.get("resource_id")
    if resource_id is not None:
        return f"{resource_type}:{resource_id}"
    code = str(item.get("issue_code") or item.get("code") or "UNKNOWN")
    source = str(item.get("source") or "unknown")
    return f"{resource_type}:{source}:{code}"


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = _REDACTED
            else:
                redacted[key_text] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export newcomer training dead-data diagnostics. This script is "
            "dry-run only and never mutates database rows."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run alias; this script has no apply mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Alias for --audio-scan-limit for production preview runbooks.",
    )
    parser.add_argument(
        "--audio-scan-limit",
        type=int,
        default=None,
        help="Maximum audio submissions to scan, newest first.",
    )
    parser.add_argument(
        "--material-scan-limit",
        type=int,
        default=1000,
        help="Maximum materials and material versions to scan, newest first.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="Maximum sample resource ids per issue code.",
    )
    parser.add_argument(
        "--include-issues",
        action="store_true",
        help="Include redacted issue details. Omit to export aggregate and samples only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to stdout.",
    )
    args = parser.parse_args(argv)
    if args.audio_scan_limit is not None and args.limit is not None:
        parser.error("use either --limit or --audio-scan-limit, not both")
    args.audio_scan_limit = args.audio_scan_limit or args.limit or 500
    if args.audio_scan_limit < 1:
        parser.error("--limit/--audio-scan-limit must be >= 1")
    if args.material_scan_limit < 1:
        parser.error("--material-scan-limit must be >= 1")
    if args.sample_limit < 0:
        parser.error("--sample-limit must be >= 0")
    return args


async def async_main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = await export_dead_data_diagnostics(
        audio_scan_limit=args.audio_scan_limit,
        material_scan_limit=args.material_scan_limit,
        sample_limit=args.sample_limit,
        include_issues=args.include_issues,
    )
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(content, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"wrote dry-run diagnostics to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())

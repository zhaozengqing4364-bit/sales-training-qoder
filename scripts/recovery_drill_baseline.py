#!/usr/bin/env python3
"""Recovery drill baseline inventory for repo-local backup / restore operations.

This script keeps the current recovery drill authority in one executable,
grep-discoverable place so the runbook, tests, and automation reuse the same
commands, preconditions, and file seams.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DrillDefinition:
    id: str
    title: str
    checked_command: str
    authority_paths: tuple[str, ...]
    evidence: tuple[str, ...]
    why_it_matters: str
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    failure_signals: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ManualBoundary:
    id: str
    title: str
    reason: str
    required_outside_repo: str


DRILLS: tuple[DrillDefinition, ...] = (
    DrillDefinition(
        id="db_migration",
        title="db migration / restore alignment",
        checked_command=(
            "cd backend && venv/bin/python -m alembic upgrade head"
        ),
        authority_paths=(
            "backend/alembic.ini",
            "backend/alembic/env.py",
            "backend/scripts/repair_legacy_schema.py",
            "backend/src/common/db/session.py",
            "backend/tests/integration/test_startup_or_bootstrap_authority.py",
        ),
        evidence=(
            "alembic stdout",
            "explicit repair stderr/stdout when legacy drift is present",
        ),
        why_it_matters=(
            "Schema authority must stay on Alembic plus explicit repair; startup bootstrap "
            "must not silently mutate production-like databases."
        ),
        failure_signals=(
            "non-zero alembic exit",
            "legacy drift runtime error mentioning repair_legacy_schema.py",
        ),
    ),
    DrillDefinition(
        id="auth_bootstrap",
        title="auth bootstrap / admin recovery",
        checked_command=(
            'backend/venv/bin/python backend/scripts/bootstrap_auth_admin.py --email "${RECOVERY_ADMIN_EMAIL}" '
            '--name "${RECOVERY_ADMIN_NAME}" --role "${RECOVERY_ADMIN_ROLE:-admin}"'
        ),
        authority_paths=(
            "backend/scripts/bootstrap_auth_admin.py",
            "backend/src/common/auth/service.py",
            "docs/setup/auth-local.md",
        ),
        evidence=(
            "[created] or [updated] bootstrap output",
            "follow-up login trace or support/admin auth verification",
        ),
        why_it_matters=(
            "Recovery must rebuild support/admin access without treating auth bootstrap as a schema-repair path."
        ),
        preconditions=("RECOVERY_ADMIN_EMAIL", "RECOVERY_ADMIN_NAME"),
        failure_signals=(
            "missing RECOVERY_ADMIN_EMAIL / RECOVERY_ADMIN_NAME",
            "bootstrap_auth_admin.py non-zero exit",
        ),
    ),
    DrillDefinition(
        id="redis_session_state",
        title="redis session state snapshot authority",
        checked_command=(
            "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
            "backend/tests/integration/test_websocket_status_contract.py -q"
        ),
        authority_paths=(
            "backend/src/common/websocket/session_state_service.py",
            "backend/tests/integration/test_websocket_status_contract.py",
            "docs/backup-recovery-runbook.md",
        ),
        evidence=(
            "pytest output showing SessionStateService.get_stats() reconnect snapshot fields",
            "redis snapshot authority wording in the runbook",
        ),
        why_it_matters=(
            "Redis is the restart-safe reconnect surface; operators need proof that snapshot state survives outside a single process."
        ),
        failure_signals=(
            "websocket status contract pytest failure",
            "missing reconnect snapshot fields in proof output",
        ),
    ),
    DrillDefinition(
        id="websocket_reconnect",
        title="websocket reconnect continuity",
        checked_command=(
            "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
            "backend/tests/integration/test_sales_realtime_reconnect_flow.py -q"
        ),
        authority_paths=(
            "backend/src/common/websocket/session_manager.py",
            "backend/src/common/websocket/session_state_service.py",
            "backend/src/sales_bot/websocket/stepfun_realtime_handler.py",
            "backend/tests/integration/test_sales_realtime_reconnect_flow.py",
        ),
        evidence=(
            "pytest output showing reconnected restored_state",
            "request_epoch / connection_epoch continuity evidence",
        ),
        why_it_matters=(
            "Restart and reconnect drills must prove process-local live sockets and shared redis snapshots are interpreted correctly."
        ),
        failure_signals=(
            "sales realtime reconnect pytest failure",
            "missing restored_state/request_epoch evidence",
        ),
    ),
    DrillDefinition(
        id="oss_signing_playback",
        title="oss signing / playback reachability",
        checked_command=(
            "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
            "backend/tests/unit/test_oss_signing_service.py backend/tests/contract/test_audio_audit_contract.py -q"
        ),
        authority_paths=(
            "backend/src/common/oss/signing.py",
            "backend/tests/unit/test_oss_signing_service.py",
            "backend/tests/contract/test_audio_audit_contract.py",
        ),
        evidence=(
            "pytest output proving ALI_OSS_BUCKET-based signing and signed playback URLs",
            "contract evidence that missing OSS config fails as OssConfigError / OSS_NOT_CONFIGURED",
        ),
        why_it_matters=(
            "Audio recovery proof currently lives in signing/playback contracts, not in a bucket-export script the repo does not have."
        ),
        failure_signals=(
            "OSS signing/unit contract pytest failure",
            "OSS_NOT_CONFIGURED contract regression",
        ),
    ),
    DrillDefinition(
        id="health_check",
        title="post-recovery health check",
        checked_command='curl -fsS "${RECOVERY_HEALTH_URL:-http://127.0.0.1:3444/health}"',
        authority_paths=(
            "backend/src/main.py",
            "docs/backup-recovery-runbook.md",
        ),
        evidence=(
            "/health JSON payload",
            "timestamp + version fields captured in drill notes",
        ),
        why_it_matters=(
            "Every recovery drill needs one cheap health endpoint proof before operators read deeper traces or logs."
        ),
        failure_signals=(
            "curl non-zero exit",
            "missing healthy/timestamp/version fields",
        ),
    ),
)


MANUAL_ONLY: tuple[ManualBoundary, ...] = (
    ManualBoundary(
        id="redis_service_restore",
        title="redis service-level restore",
        reason=(
            "The repository can describe Redis reconnect snapshot authority, but it does not ship a repo-native RDB restore workflow."
        ),
        required_outside_repo=(
            "Use the environment's Redis service restore procedure and record whether session-state loss is accepted."
        ),
    ),
    ManualBoundary(
        id="oss_bucket_export",
        title="oss bucket export / backup",
        reason=(
            "The repository can sign PUT/GET playback URLs, but it does not ship bucket-wide OSS export or backup tooling."
        ),
        required_outside_repo=(
            "Use external bucket lifecycle / export tooling and record bucket, endpoint, and representative playback checks."
        ),
    ),
    ManualBoundary(
        id="multi_instance_drain",
        title="multi-instance websocket drain",
        reason=(
            "SessionManager visibility is process-local and the repo has no cluster drain or traffic-shedding endpoint."
        ),
        required_outside_repo=(
            "Use ingress / load-balancer traffic drain controls outside the repo, then inspect SessionManager + SessionStateService separately."
        ),
    ),
)


def _all_paths() -> Iterable[str]:
    for drill in DRILLS:
        yield from drill.authority_paths


DRILLS_BY_ID = {drill.id: drill for drill in DRILLS}


def validate_repository(repo_root: Path) -> list[str]:
    missing: list[str] = []
    for relative_path in sorted(set(_all_paths())):
        if not (repo_root / relative_path).exists():
            missing.append(relative_path)
    return missing


def build_status_report(repo_root: Path) -> str:
    missing = validate_repository(repo_root)
    lines = [
        "Recovery drill baseline (repo-local authority inventory)",
        f"repo_root: {repo_root}",
        "",
        "Automatable / checked drills:",
    ]

    for drill in DRILLS:
        lines.extend(
            [
                f"[drill] {drill.id}",
                f"  title: {drill.title}",
                f"  checked_command: {drill.checked_command}",
                f"  authority_paths: {', '.join(drill.authority_paths)}",
                f"  evidence: {', '.join(drill.evidence)}",
                f"  why_it_matters: {drill.why_it_matters}",
            ]
        )
        if drill.preconditions:
            lines.append(f"  preconditions: {', '.join(drill.preconditions)}")
        if drill.failure_signals:
            lines.append(f"  failure_signals: {', '.join(drill.failure_signals)}")
        lines.append("")

    lines.append("Manual-only boundaries:")
    for boundary in MANUAL_ONLY:
        lines.extend(
            [
                f"[manual-only] {boundary.id}",
                f"  title: {boundary.title}",
                f"  reason: {boundary.reason}",
                f"  required_outside_repo: {boundary.required_outside_repo}",
                "",
            ]
        )

    if missing:
        lines.append("Repository validation: missing authority paths")
        for relative_path in missing:
            lines.append(f"  - {relative_path}")
    else:
        lines.append("Repository validation: all referenced authority paths exist")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("status", "check"),
        default="status",
        help="status prints the drill inventory; check also exits non-zero if authority paths are missing.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    report = build_status_report(repo_root)
    print(report, end="")

    if args.mode == "check":
        return 1 if validate_repository(repo_root) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

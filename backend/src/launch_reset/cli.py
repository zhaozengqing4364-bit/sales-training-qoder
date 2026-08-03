"""Local-only CLI for inspect, dry-run, apply, and independent verification."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from launch_reset.application import ResetApplicationService
from launch_reset.errors import ResetExecutionError, ResetSafetyError


def _safe_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    postgres = manifest.get("inspection", {}).get("postgresql", {})
    return {
        "manifest": {
            "format": manifest.get("format"),
            "version": manifest.get("version"),
            "environment": manifest.get("environment"),
            "plan_checksum": manifest.get("plan_checksum"),
        },
        "target_fingerprint": postgres.get("fingerprint"),
        "inspection": manifest.get("inspection", {}),
        "warnings": manifest.get("warnings", []),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarded pre-launch project data-plane reset"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--manifest", type=Path, required=True)

    dry_run_parser = subparsers.add_parser("dry-run")
    dry_run_parser.add_argument("--manifest", type=Path, required=True)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--manifest", type=Path, required=True)
    apply_parser.add_argument("--snapshot", type=Path)
    apply_parser.add_argument("--target-fingerprint", required=True)
    apply_parser.add_argument("--confirm-token", required=True)
    apply_parser.add_argument("--admin-email", required=True)
    apply_parser.add_argument("--admin-name", required=True)
    apply_parser.add_argument(
        "--admin-password-env", default="LAUNCH_ADMIN_INITIAL_PASSWORD"
    )

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--snapshot", type=Path)
    verify_parser.add_argument("--admin-email")
    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    service = ResetApplicationService()
    if args.command == "inspect":
        manifest = await service.inspect(args.manifest)
        return _safe_summary(manifest)
    if args.command == "dry-run":
        manifest, token = await service.dry_run(args.manifest)
        return {**_safe_summary(manifest), "confirmation_token": token}
    if args.command == "apply":
        password = os.getenv(args.admin_password_env, "")
        if not password:
            raise ResetSafetyError("[RESET_ADMIN_PASSWORD_ENV_MISSING]")
        snapshot_path = args.snapshot or args.manifest.with_suffix(".snapshot.json")
        return await service.apply(
            manifest_path=args.manifest,
            snapshot_path=snapshot_path,
            supplied_fingerprint=args.target_fingerprint,
            confirmation_token=args.confirm_token,
            admin_email=args.admin_email,
            admin_name=args.admin_name,
            initial_password=password,
        )
    if args.command == "verify":
        return await service.verify(
            manifest_path=args.manifest,
            snapshot_path=args.snapshot,
            admin_email=args.admin_email,
        )
    raise ResetSafetyError("[RESET_COMMAND_INVALID]")


def main() -> int:
    args = _parser().parse_args()
    try:
        result = asyncio.run(_run(args))
    except (ResetSafetyError, ResetExecutionError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {"success": False, "error": f"[{type(exc).__name__.upper()}]"},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps({"success": True, "data": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]

"""
Audit or repair historical PracticeSession runtime snapshot drift.

Default mode is dry-run:
    python scripts/repair_runtime_snapshots.py

Apply repairable fixes explicitly:
    python scripts/repair_runtime_snapshots.py --apply
    python scripts/repair_runtime_snapshots.py --session-id <uuid> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common.db.session import AsyncSessionLocal
from common.monitoring.logger import configure_logging, get_logger
from common.services.session_runtime_repair_service import SessionRuntimeRepairService

load_dotenv()
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


async def _run(args: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as db:
        result = await SessionRuntimeRepairService(db).run(
            apply=bool(args.apply),
            session_ids=list(args.session_id or []),
            limit=int(args.limit),
            include_completed=bool(args.include_completed),
        )

    payload = result.to_dict()
    if args.json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        logger.info(
            "Runtime snapshot repair finished",
            dry_run=payload["dry_run"],
            scanned_sessions=payload["scanned_sessions"],
            finding_count=payload["finding_count"],
            repaired_sessions=payload["repaired_sessions"],
        )
        for finding in payload["findings"]:
            logger.info("Runtime snapshot repair finding", **finding)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit/repair historical runtime snapshot drift. Dry-run by default."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply repairable fixes. Omit for dry-run audit.",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        help="Limit repair to a specific PracticeSession id. Can be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum sessions to scan when --session-id is not provided.",
    )
    parser.add_argument(
        "--include-completed",
        action="store_true",
        help="Also scan completed sessions. Default scans only runnable statuses.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary to stdout.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())

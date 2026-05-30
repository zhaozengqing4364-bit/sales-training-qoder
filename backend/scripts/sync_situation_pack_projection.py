#!/usr/bin/env python3
"""Sync active Roleplay SituationPack ConfigBundle into projection rows.

Dry-run by default:
    python scripts/sync_situation_pack_projection.py

Apply changes explicitly:
    python scripts/sync_situation_pack_projection.py --apply --actor-id <user-id>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.db.models import SystemLog  # noqa: E402
from common.db.session import AsyncSessionLocal  # noqa: E402
from common.monitoring.logger import get_trace_id  # noqa: E402
from curriculum_practice.services.roleplay.situation_pack_projection_sync import (  # noqa: E402
    SituationPackProjectionSyncService,
)

load_dotenv()


async def _sync(
    *,
    apply: bool,
    actor_id: str | None,
    reason: str | None,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        result = await SituationPackProjectionSyncService(
            db
        ).sync_active_published_ruleset(actor_id=actor_id)
        payload = {
            "dry_run": not apply,
            "synced_codes": list(result.synced_codes),
            "created_count": result.created_count,
            "updated_count": result.updated_count,
            "actor_id": actor_id,
            "reason": reason,
            "trace_id": get_trace_id(),
        }
        if apply:
            db.add(
                SystemLog(
                    action="situation_pack_projection_sync",
                    user_id=None,
                    user_identifier=actor_id or "system",
                    status="success",
                    details=json.dumps(payload, ensure_ascii=False, default=str),
                )
            )
            await db.commit()
        else:
            await db.rollback()
        return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply projection sync. Omit for dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run alias; kept for automation readability.",
    )
    parser.add_argument("--actor-id", default=None)
    parser.add_argument("--reason", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    apply = bool(args.apply and not args.dry_run)
    payload = asyncio.run(
        _sync(
            apply=apply,
            actor_id=args.actor_id,
            reason=args.reason,
        )
    )
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

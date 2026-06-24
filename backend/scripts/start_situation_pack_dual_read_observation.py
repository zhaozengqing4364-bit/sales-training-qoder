#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent.models  # noqa: E402,F401 - register ORM mappers
import curriculum_practice.models  # noqa: E402,F401 - register ORM mappers
from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY  # noqa: E402
from common.db.models import ConfigBundleAuditLog, SystemLog  # noqa: E402
from common.db.session import AsyncSessionLocal  # noqa: E402
from common.monitoring.logger import get_trace_id  # noqa: E402
from curriculum_practice.services.roleplay.situation_pack_projection_sync import (  # noqa: E402
    SituationPackProjectionSyncService,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (  # noqa: E402
    SituationPackRepository,
)
from curriculum_practice.services.support_runtime_contributor import (  # noqa: E402
    build_curriculum_practice_config_asset_center,
)

load_dotenv()

OBSERVATION_STARTED_ACTION = "situation_pack_dual_read_observation_started"


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _required_flag_snapshot() -> dict[str, bool]:
    return {
        "SITUATION_PACK_DUAL_READ": _env_bool("SITUATION_PACK_DUAL_READ"),
        "SITUATION_PACK_READ_ORM": _env_bool("SITUATION_PACK_READ_ORM"),
        "SITUATION_PACK_B1_AUTHORITY": _env_bool("SITUATION_PACK_B1_AUTHORITY"),
    }


def _flag_blockers(flags: dict[str, bool]) -> list[str]:
    blockers: list[str] = []
    if not flags["SITUATION_PACK_DUAL_READ"]:
        blockers.append("dual_read_disabled")
    if not flags["SITUATION_PACK_READ_ORM"]:
        blockers.append("orm_projection_read_disabled")
    if flags["SITUATION_PACK_B1_AUTHORITY"]:
        blockers.append("b1_authority_must_remain_disabled_for_observation_start")
    return blockers


async def _latest_projection_sync(db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        select(ConfigBundleAuditLog)
        .where(ConfigBundleAuditLog.bundle_key == ROLEPLAY_SITUATION_PACKS_KEY)
        .order_by(ConfigBundleAuditLog.created_at.desc())
        .limit(1)
    )
    audit = result.scalar_one_or_none()
    snapshot = audit.after_snapshot_json if audit is not None else {}
    if not isinstance(snapshot, dict):
        return None
    projection_sync = snapshot.get("projection_sync")
    return projection_sync if isinstance(projection_sync, dict) else None


async def _latest_observation_start(db: AsyncSession) -> str | None:
    result = await db.execute(
        select(SystemLog.created_at)
        .where(SystemLog.action == OBSERVATION_STARTED_ACTION)
        .order_by(SystemLog.created_at.desc())
        .limit(1)
    )
    created_at = result.scalar_one_or_none()
    return created_at.isoformat() if created_at is not None else None


async def _record_observation_start(
    db: AsyncSession,
    *,
    actor_id: str | None,
    reason: str,
    evidence: dict[str, Any],
) -> None:
    db.add(
        SystemLog(
            action=OBSERVATION_STARTED_ACTION,
            user_id=None,
            user_identifier=actor_id or "system",
            status="success",
            details=json.dumps(
                {
                    "reason": reason,
                    "trace_id": get_trace_id(),
                    "evidence": evidence,
                },
                ensure_ascii=False,
                default=str,
            ),
        )
    )


async def _start_observation(
    *,
    apply: bool,
    actor_id: str | None,
    reason: str,
) -> dict[str, Any]:
    flags = _required_flag_snapshot()
    blockers = _flag_blockers(flags)
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as db:
        sync_result = await SituationPackProjectionSyncService(
            db
        ).sync_active_published_ruleset(actor_id=actor_id)
        repo = await SituationPackRepository.from_database(db)
        published_packs = repo.list_published()
        overview = await build_curriculum_practice_config_asset_center(db, now)
        projection_sync = await _latest_projection_sync(db)
        existing_started_at = await _latest_observation_start(db)

        dual_read = overview.get("dual_read")
        if not isinstance(dual_read, dict):
            dual_read = {}
        mismatch_count = int(dual_read.get("mismatch_count") or 0)
        if mismatch_count != 0:
            blockers.append("dual_read_mismatch_nonzero")
        if not projection_sync or str(projection_sync.get("status") or "") != "ok":
            blockers.append("projection_sync_not_ok")

        payload: dict[str, Any] = {
            "dry_run": not apply,
            "status": "blocked" if blockers else "ready",
            "blockers": blockers,
            "flags": flags,
            "reason": reason,
            "actor_id": actor_id,
            "published_count": len(published_packs),
            "projection_sync_apply": {
                "synced_codes": list(sync_result.synced_codes),
                "created_count": sync_result.created_count,
                "updated_count": sync_result.updated_count,
            },
            "latest_projection_sync": projection_sync,
            "dual_read": dual_read,
            "observation_started_at": existing_started_at,
            "observation_would_start_at": None
            if existing_started_at
            else now.isoformat(),
        }

        if blockers:
            await db.rollback()
            return payload

        if apply and existing_started_at is None:
            await _record_observation_start(
                db,
                actor_id=actor_id,
                reason=reason,
                evidence=payload,
            )
            await db.commit()
            payload["observation_started_at"] = now.isoformat()
            payload["observation_would_start_at"] = None
            payload["status"] = "started"
            return payload

        if apply:
            await db.commit()
            payload["status"] = "already_started"
            return payload

        await db.rollback()
        return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start and verify SituationPack dual-read observation."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply projection sync and record observation start when checks pass.",
    )
    parser.add_argument("--actor-id", default=None)
    parser.add_argument("--reason", default="p0-dual-read-start")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = asyncio.run(
        _start_observation(
            apply=bool(args.apply),
            actor_id=args.actor_id,
            reason=str(args.reason or "p0-dual-read-start"),
        )
    )
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0 if not payload["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Repair legacy PublishedAssetRef.source_config_version_id values.

Dry-run by default:
    python scripts/repair_published_asset_ref_config_versions.py

Apply changes explicitly:
    python scripts/repair_published_asset_ref_config_versions.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.db.models import ConfigVersion  # noqa: E402
from common.db.session import AsyncSessionLocal  # noqa: E402
from curriculum_practice.models import PracticeTemplate  # noqa: E402

load_dotenv()


async def _repair(*, apply: bool, limit: int) -> dict[str, Any]:
    scanned = 0
    repaired: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PracticeTemplate)
            .where(
                PracticeTemplate.status == "published",
                PracticeTemplate.published_asset_refs.is_not(None),
            )
            .order_by(PracticeTemplate.updated_at.desc())
            .limit(limit)
        )
        templates = list(result.scalars().all())
        for template in templates:
            scanned += 1
            refs = dict(template.published_asset_refs or {})
            pack_ref = refs.get("situation_pack_ref")
            if not isinstance(pack_ref, dict):
                continue
            source_config_id = str(pack_ref.get("source_config_id") or "").strip()
            source_config_version_id = str(
                pack_ref.get("source_config_version_id") or ""
            ).strip()
            if not source_config_id:
                skipped.append(
                    {
                        "template_id": str(template.template_id),
                        "reason": "missing_source_config_id",
                    }
                )
                continue
            version = await db.scalar(
                select(ConfigVersion).where(
                    ConfigVersion.source_config_id == source_config_id
                )
            )
            if version is None:
                skipped.append(
                    {
                        "template_id": str(template.template_id),
                        "reason": "config_version_not_found",
                        "source_config_id": source_config_id,
                    }
                )
                continue
            target_version_id = str(version.version_id)
            if source_config_version_id == target_version_id:
                continue
            if apply:
                pack_ref["source_config_version_id"] = target_version_id
                refs["situation_pack_ref"] = pack_ref
                template.published_asset_refs = refs
                flag_modified(template, "published_asset_refs")
            repaired.append(
                {
                    "template_id": str(template.template_id),
                    "source_config_id": source_config_id,
                    "before_source_config_version_id": source_config_version_id,
                    "after_source_config_version_id": target_version_id,
                }
            )
        if apply:
            await db.commit()
        else:
            await db.rollback()
    return {
        "dry_run": not apply,
        "scanned": scanned,
        "repaired": repaired,
        "skipped": skipped,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply repair. Omit for dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run alias; kept for automation readability.",
    )
    parser.add_argument("--limit", type=int, default=1000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    apply = bool(args.apply and not args.dry_run)
    payload = asyncio.run(_repair(apply=apply, limit=int(args.limit)))
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

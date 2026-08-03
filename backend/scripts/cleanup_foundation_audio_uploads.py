#!/usr/bin/env python3
"""Clean one bounded batch of expired/cancelled foundation audio uploads."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_assessment.maintenance import AudioUploadMaintenanceService  # noqa: E402
from audio_assessment.storage import build_audio_object_storage  # noqa: E402
from common.db.model_registry.registration import register_all_models  # noqa: E402
from common.db.session import AsyncSessionLocal  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="清理一批已过期或已取消的新人训练录音分片。"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="单次最多处理的上传会话数，范围 1～1000。",
    )
    return parser.parse_args()


async def _run(arguments: argparse.Namespace) -> None:
    register_all_models()
    result = await AudioUploadMaintenanceService(
        AsyncSessionLocal,
        storage=build_audio_object_storage(),
    ).run_once(limit=int(arguments.limit))
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if result.failed_count:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(_run(_arguments()))

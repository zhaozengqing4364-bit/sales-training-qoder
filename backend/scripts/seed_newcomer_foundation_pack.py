#!/usr/bin/env python3
"""Install or verify the governed newcomer foundation standard pack."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.db.session import AsyncSessionLocal  # noqa: E402
from common.db.model_registry.registration import register_all_models  # noqa: E402
from foundation_standard_pack import (  # noqa: E402
    install_or_verify_standard_pack,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="安装或校验新人销售基础训练标准包。"
    )
    parser.add_argument(
        "--organization-id",
        default=os.getenv("NEWCOMER_FOUNDATION_ORGANIZATION_ID", "default"),
        help="目标组织标识；默认读取 NEWCOMER_FOUNDATION_ORGANIZATION_ID。",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="只校验，不写入数据库。",
    )
    return parser.parse_args()


async def _run(arguments: argparse.Namespace) -> None:
    organization_id = str(arguments.organization_id).strip()
    if not organization_id:
        raise SystemExit("organization-id 不能为空。")
    register_all_models()
    async with AsyncSessionLocal() as session:
        try:
            result = await install_or_verify_standard_pack(
                session,
                organization_id=organization_id,
                verify_only=bool(arguments.verify_only),
            )
            if arguments.verify_only:
                await session.rollback()
            else:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_run(_arguments()))

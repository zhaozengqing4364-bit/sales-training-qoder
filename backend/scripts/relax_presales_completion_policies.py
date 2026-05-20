"""将售前路径各阶段 completion_policy 放宽为「参与即可」（测试用）。

用法（在 backend 目录）:
    python -m scripts.relax_presales_completion_policies
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select

from common.db.session import async_session_factory
from curriculum_practice.models import PracticeTemplate


def _relax_policy(policy: dict) -> dict:
    updated = copy.deepcopy(policy)
    updated["min_score"] = 0
    updated["min_rounds"] = 0
    return updated


def _relax_plan(plan: dict) -> dict:
    updated = copy.deepcopy(plan)
    stages = updated.get("stages")
    if not isinstance(stages, list):
        return updated
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        policy = stage.get("completion_policy")
        if isinstance(policy, dict):
            stage["completion_policy"] = _relax_policy(policy)
    return updated


async def main() -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(PracticeTemplate).where(PracticeTemplate.status == "published")
        )
        templates = list(result.scalars().all())
        changed = 0
        for template in templates:
            plan = template.curriculum_plan
            if not isinstance(plan, dict):
                continue
            if "售前" not in str(plan.get("name") or "") and "presales" not in json.dumps(
                plan, ensure_ascii=False
            ).lower():
                continue
            relaxed = _relax_plan(plan)
            if relaxed == plan:
                continue
            template.curriculum_plan = relaxed
            changed += 1
            print(f"updated template {template.template_id} ({template.name})")
        if changed:
            await db.commit()
        print(f"done: {changed} template(s) updated")


if __name__ == "__main__":
    asyncio.run(main())

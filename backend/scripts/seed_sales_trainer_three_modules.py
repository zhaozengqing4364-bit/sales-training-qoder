"""Seed three self-select modules for sales-trainer home (replaces 17-level COO timeline on home).

Usage:
  PYTHONPATH=src python scripts/seed_sales_trainer_three_modules.py
  PYTHONPATH=src python scripts/seed_sales_trainer_three_modules.py --verify-only

Depends on (module 2 hub links to COO chapters):
  scripts/import_coo_learning_content.py  (writes config-assets/coo-learning-content.id)
  Optional: scripts/seed_coo_questions.py + seed_coo_path_extension.py for per-chapter quiz units
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.db.models import User
from common.db.session import AsyncSessionLocal
from sales_trainer.models import SalesTrainerAudioScorePrompt, SalesTrainerUnit
from sales_trainer.schemas import SalesTrainerPathConfig
from sales_trainer.services.path_service import SalesTrainerPathService

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ID_PATH = (
    Path(__file__).resolve().parents[1] / "config-assets/coo-learning-content.id"
)

OWNER_EMAIL = "sales-trainer.modules.seed.admin@example.com"
LEARNER_EMAIL = "sales-trainer.goal.demo.learner@example.com"

PATH_KEY = "new_seller_modules_v1"
PATH_TITLE = "新人销售三模块训练"
GOAL_TITLE = "按模块自选完成核心能力训练"
LEGACY_PATH_KEY = "new_seller_goal_path"

M1_NAME = "模块一：PPT演练"
M2_NAME = "模块二：拜访前商务"
M3_5_NAME = "模块三：金字塔演讲（5分钟）"
M3_10_NAME = "模块三：金字塔演讲（10分钟）"
M3_15_NAME = "模块三：金字塔演讲（15分钟）"
PPT_PROMPT_NAME = "主胶片讲解录音评分"
PYRAMID_PROMPT_NAME = "金字塔演讲录音评分"

MODULE_COUNT = 5

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    """Raised when verify-only checks fail."""


@dataclass(slots=True)
class SeedSummary:
    created: int = 0
    updated: int = 0
    verified: bool = False
    path_key: str = PATH_KEY
    disabled_legacy_units: int = 0
    unit_ids: list[str] | None = None
    content_id: str | None = None

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"path_key={self.path_key}",
            f"disabled_legacy_units={self.disabled_legacy_units}",
            f"unit_count={len(self.unit_ids or [])}",
            f"content_id={self.content_id or ''}",
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


def read_content_id() -> str | None:
    if not CONTENT_ID_PATH.exists():
        return None
    value = CONTENT_ID_PATH.read_text(encoding="utf-8").strip()
    return value or None


async def _first(db: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
    return (await db.execute(stmt)).scalars().first()


async def _upsert_user(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    email: str,
    name: str,
    role: str,
) -> User:
    normalized_email = email.strip().lower()
    user = await _first(db, select(User).where(User.email == normalized_email))
    if user is None:
        user = User(
            user_id=_uuid(),
            email=normalized_email,
            name=name,
            role=role,
            department="销售训练演示部",
            is_active=True,
            wechat_user_id=_wechat_id(normalized_email),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
        user.name = name
        user.role = role
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = _wechat_id(normalized_email)
    return user


def _path_config(
    *,
    order_index: int,
    level_title: str,
    level_description: str,
    completion_rule: Literal["passed", "scored", "submitted"] = "passed",
    primary_action_label: str = "进入本模块",
) -> dict[str, Any]:
    return SalesTrainerPathConfig(
        enabled=True,
        path_key=PATH_KEY,
        path_title=PATH_TITLE,
        goal_title=GOAL_TITLE,
        level_title=level_title,
        level_description=level_description,
        order_index=order_index,
        unlock_after_unit_ids=[],
        completion_rule=completion_rule,
        primary_action_label=primary_action_label,
        retry_action_label="再练一次",
        review_action_label="查看结果",
        guidance_templates={
            "not_started": "可随时开始本模块，无前置解锁要求。",
            "not_passed": "最近一次未达通关线，可重练或先学习其他模块。",
            "start_level_reason": "建议顺序：PPT演练 → 拜访前商务 → 金字塔演讲（时长自选）。",
            "retry_level_reason": "根据反馈重练本模块即可。",
            "path_completed_reason": "三模块均已有训练记录，可回看结果。",
        },
    ).model_dump(exclude_none=True)


async def _upsert_unit(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    name: str,
    description: str,
    unit_type: str,
    config: dict[str, Any],
) -> SalesTrainerUnit:
    unit = await _first(
        db,
        select(SalesTrainerUnit).where(SalesTrainerUnit.name == name),
    )
    if unit is None:
        unit = SalesTrainerUnit(
            unit_id=_uuid(),
            name=name,
            unit_type=unit_type,
            created_by=owner_id,
        )
        db.add(unit)
        summary.created += 1
    else:
        summary.updated += 1
    unit.unit_type = unit_type
    unit.description = description
    unit.config = config
    unit.status = "published"
    unit.updated_by = owner_id
    return unit


def _default_output_schema() -> dict[str, str]:
    return {
        "total_score": "number",
        "passed": "boolean",
        "summary": "string",
        "strengths": "array",
        "improvements": "array",
    }


async def _upsert_audio_prompt(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    name: str,
    purpose: str,
    system_prompt: str,
    scoring_template: str,
) -> SalesTrainerAudioScorePrompt:
    prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.name == name,
            SalesTrainerAudioScorePrompt.purpose == purpose,
        ),
    )
    if prompt is None:
        prompt = SalesTrainerAudioScorePrompt(
            prompt_id=_uuid(),
            name=name,
            purpose=purpose,
            created_by=owner_id,
        )
        db.add(prompt)
        summary.created += 1
    else:
        summary.updated += 1
    prompt.system_prompt = system_prompt
    prompt.scoring_template = scoring_template
    prompt.output_schema = _default_output_schema()
    prompt.version = max(int(prompt.version or 1), 1)
    prompt.status = "published"
    prompt.updated_by = owner_id
    return prompt


async def _disable_orphan_module_path_units(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    keep_unit_ids: set[str],
) -> int:
    """Disable path.enabled on published units tied to PATH_KEY but not in the canonical set."""
    units = (
        await db.execute(
            select(SalesTrainerUnit).where(SalesTrainerUnit.status == "published")
        )
    ).scalars().all()
    disabled = 0
    for unit in units:
        if str(unit.unit_id) in keep_unit_ids:
            continue
        config = dict(unit.config or {})
        path = dict(config.get("path") or {})
        if path.get("path_key") != PATH_KEY:
            continue
        if path.get("enabled") is False:
            continue
        path["enabled"] = False
        config["path"] = path
        unit.config = config
        disabled += 1
        summary.updated += 1
    return disabled


async def _disable_legacy_goal_path_units(
    db: AsyncSession,
    summary: SeedSummary,
) -> int:
    units = (
        await db.execute(
            select(SalesTrainerUnit).where(SalesTrainerUnit.status == "published")
        )
    ).scalars().all()
    disabled = 0
    for unit in units:
        config = dict(unit.config or {})
        path = dict(config.get("path") or {})
        if path.get("path_key") != LEGACY_PATH_KEY:
            continue
        if path.get("enabled") is False:
            continue
        path["enabled"] = False
        config["path"] = path
        unit.config = config
        disabled += 1
        summary.updated += 1
    summary.disabled_legacy_units = disabled
    return disabled


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    content_id = read_content_id()
    summary.content_id = content_id

    owner = await _upsert_user(
        db,
        summary,
        email=OWNER_EMAIL,
        name="三模块路径管理员",
        role="admin",
    )
    await _upsert_user(
        db,
        summary,
        email=LEARNER_EMAIL,
        name="销售训练演示学员",
        role="user",
    )
    await db.flush()

    await _disable_legacy_goal_path_units(db, summary)
    ppt_prompt = await _upsert_audio_prompt(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=PPT_PROMPT_NAME,
        purpose="ppt_pitch",
        system_prompt=(
            "你是销售主胶片讲解录音评分员。根据转写文本评估学员是否按 PPT 逻辑"
            "讲清背景、方案核心与价值，只输出符合 schema 的 JSON。"
        ),
        scoring_template=(
            "请对主胶片讲解录音评分。转写文本：{transcript}\n"
            "关注：开场自我介绍、背景与合规痛点、三位一体方案逻辑、"
            "是否遗漏关键页、表达流畅度。返回总分、是否通过、总结、优点与改进建议。"
        ),
    )
    pyramid_prompt = await _upsert_audio_prompt(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=PYRAMID_PROMPT_NAME,
        purpose="pyramid_speech",
        system_prompt="你是销售演讲录音评分员，只输出符合 schema 的 JSON。",
        scoring_template=(
            "请根据金字塔结构演讲评分，转写文本：{transcript}\n"
            "关注结论先行、论据层次与收尾行动，返回总分、优点和改进建议。"
        ),
    )
    await db.flush()

    m1 = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=M1_NAME,
        description="上传主胶片讲解录音，由 AI 转写并评分（非实时 PPT 演练场）。",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": str(ppt_prompt.prompt_id),
                "purpose": "ppt_pitch",
                "pass_threshold": 70,
            },
            "path": _path_config(
                order_index=1,
                level_title="第1关：PPT演练",
                level_description="按公司主胶片逻辑讲解并上传录音，获取 AI 评分反馈。",
                completion_rule="scored",
                primary_action_label="上传 PPT 讲解录音",
            ),
        },
    )

    learner_cfg: dict[str, Any] = {"hub": True}
    if content_id:
        learner_cfg["learning_content_id"] = content_id

    m2 = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=M2_NAME,
        description="阅读 COO 谈市场十五讲，章节可任意顺序浏览，无强制通关顺序。",
        unit_type="quiz",
        config={
            "quiz": {"pass_threshold": 0},
            "path": _path_config(
                order_index=2,
                level_title="第2关：拜访前商务",
                level_description="从章节目录进入阅读；每章可配合测验（若已发布）。",
                completion_rule="submitted",
                primary_action_label="进入学习目录",
            ),
            "learner": learner_cfg,
        },
    )

    audio_base = {
        "scoring_prompt_id": str(pyramid_prompt.prompt_id),
        "purpose": "pyramid_speech",
        "pass_threshold": 70,
    }

    m3_5 = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=M3_5_NAME,
        description="上传约 5 分钟的金字塔结构演讲录音，获取转写与评分反馈。",
        unit_type="audio_scoring",
        config={
            "audio": {**audio_base, "purpose": "pyramid_speech_5m"},
            "path": _path_config(
                order_index=3,
                level_title="金字塔演讲 · 5 分钟",
                level_description="短时版本：结论先行，控制在约 5 分钟。",
                completion_rule="scored",
                primary_action_label="上传 5 分钟录音",
            ),
        },
    )
    m3_10 = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=M3_10_NAME,
        description="上传约 10 分钟的金字塔结构演讲录音。",
        unit_type="audio_scoring",
        config={
            "audio": {**audio_base, "purpose": "pyramid_speech_10m"},
            "path": _path_config(
                order_index=4,
                level_title="金字塔演讲 · 10 分钟",
                level_description="标准版本：完整金字塔展开。",
                completion_rule="scored",
                primary_action_label="上传 10 分钟录音",
            ),
        },
    )
    m3_15 = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=M3_15_NAME,
        description="上传约 15 分钟的金字塔结构演讲录音。",
        unit_type="audio_scoring",
        config={
            "audio": {**audio_base, "purpose": "pyramid_speech_15m"},
            "path": _path_config(
                order_index=5,
                level_title="金字塔演讲 · 15 分钟",
                level_description="完整版本：充分展开论据与案例。",
                completion_rule="scored",
                primary_action_label="上传 15 分钟录音",
            ),
        },
    )

    canonical_ids = {
        str(m1.unit_id),
        str(m2.unit_id),
        str(m3_5.unit_id),
        str(m3_10.unit_id),
        str(m3_15.unit_id),
    }
    summary.unit_ids = list(canonical_ids)
    await _disable_orphan_module_path_units(db, summary, keep_unit_ids=canonical_ids)
    await db.commit()
    await verify(db, summary=summary)
    return summary


async def verify(db: AsyncSession, *, summary: SeedSummary | None = None) -> SeedSummary:
    summary = summary or SeedSummary()
    learner = await _first(db, select(User).where(User.email == LEARNER_EMAIL))
    if learner is None:
        raise VerifyError(f"learner {LEARNER_EMAIL} not found")

    for name in (M1_NAME, M2_NAME, M3_5_NAME, M3_10_NAME, M3_15_NAME):
        unit = await _first(
            db,
            select(SalesTrainerUnit).where(
                SalesTrainerUnit.name == name,
                SalesTrainerUnit.status == "published",
            ),
        )
        if unit is None:
            raise VerifyError(f"published unit missing: {name}")
        path_cfg = (unit.config or {}).get("path") or {}
        if path_cfg.get("path_key") != PATH_KEY:
            raise VerifyError(f"{name} path_key mismatch")
        if path_cfg.get("enabled") is not True:
            raise VerifyError(f"{name} path not enabled")
        if path_cfg.get("unlock_after_unit_ids"):
            raise VerifyError(f"{name} must not have unlock_after_unit_ids")

    m1 = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == M1_NAME,
            SalesTrainerUnit.status == "published",
        ),
    )
    if m1 is None:
        raise VerifyError(f"published unit missing: {M1_NAME}")
    if m1.unit_type != "audio_scoring":
        raise VerifyError(f"{M1_NAME} must be audio_scoring, got {m1.unit_type}")
    audio_cfg = (m1.config or {}).get("audio") or {}
    if audio_cfg.get("purpose") != "ppt_pitch":
        raise VerifyError(f"{M1_NAME} audio.purpose must be ppt_pitch")

    paths = await SalesTrainerPathService(db).list_paths_for_user(str(learner.user_id))
    path = next((item for item in paths if item["path_key"] == PATH_KEY), None)
    if path is None:
        raise VerifyError(f"{PATH_KEY} not returned by SalesTrainerPathService")
    if path["total_levels"] != MODULE_COUNT:
        raise VerifyError(f"expected {MODULE_COUNT} levels, got {path['total_levels']}")
    if any(level["locked"] for level in path["levels"]):
        raise VerifyError("module path levels must not be locked")

    legacy_visible = [
        item
        for item in paths
        if item["path_key"] == LEGACY_PATH_KEY
    ]
    if legacy_visible:
        raise VerifyError(
            "legacy new_seller_goal_path still visible; run seed to disable path.enabled"
        )

    summary.verified = True
    return summary


async def run(*, verify_only: bool) -> tuple[int, SeedSummary | None, str | None]:
    async with AsyncSessionLocal() as db:
        try:
            summary = await verify(db) if verify_only else await seed(db)
        except VerifyError as exc:
            await db.rollback()
            return 2, None, str(exc)
        except Exception as exc:
            await db.rollback()
            return 1, None, str(exc)
        return 0, summary, None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed or verify new_seller_modules_v1 (three-module home)."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify module path data.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    exit_code, summary, error = asyncio.run(run(verify_only=bool(args.verify_only)))
    if summary is not None:
        for line in summary.to_lines():
            print(line)
    if error is not None:
        print(f"error={error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

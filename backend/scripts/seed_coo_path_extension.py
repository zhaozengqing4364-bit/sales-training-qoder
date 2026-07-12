"""Extend new_seller_goal_path with 15 COO quiz units (order 1-15).

Usage:
  PYTHONPATH=src python scripts/seed_coo_path_extension.py
  PYTHONPATH=src python scripts/seed_coo_path_extension.py --verify-only

Depends on:
  scripts/import_coo_learning_content.py
  scripts/seed_coo_questions.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import yaml
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sales_trainer.services.path_service import SalesTrainerPathService

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.db.models import User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import QuestionItem
from sales_trainer.models import SalesTrainerUnit, SalesTrainerUnitQuestion
from sales_trainer.schemas import SalesTrainerPathConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs/content/coo-series-manifest.yaml"
CONTENT_ID_PATH = (
    Path(__file__).resolve().parents[1] / "config-assets/coo-learning-content.id"
)
QUESTIONS_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "config-assets/coo-questions-manifest.json"
)

OWNER_EMAIL = "coo.path.seed.admin@example.com"
LEARNER_EMAIL = "sales-trainer.goal.demo.learner@example.com"
PATH_KEY = "new_seller_goal_path"
PATH_TITLE = "新人销售闯关"
GOAL_TITLE = "掌握首次客户沟通"
LEGACY_QUIZ_UNIT_NAME = "第一关：产品定位做题"
LEGACY_AUDIO_UNIT_NAME = "第二关：客户开场录音"
COO_UNIT_COUNT = 15
TOTAL_LEVELS = 17

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    """Raised when verify-only checks fail."""


@dataclass(slots=True)
class SeedSummary:
    created: int = 0
    updated: int = 0
    verified: bool = False
    content_id: str | None = None
    coo_unit_ids: list[str] | None = None

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"content_id={self.content_id or ''}",
            f"coo_unit_count={len(self.coo_unit_ids or [])}",
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


def load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_content_id() -> str:
    if CONTENT_ID_PATH.exists():
        value = CONTENT_ID_PATH.read_text(encoding="utf-8").strip()
        if value:
            return value
    raise VerifyError(
        f"missing content id file: {CONTENT_ID_PATH}; run import_coo_learning_content.py first"
    )


def read_questions_manifest() -> dict[str, list[str]]:
    if not QUESTIONS_MANIFEST_PATH.exists():
        raise VerifyError(
            f"missing {QUESTIONS_MANIFEST_PATH}; run seed_coo_questions.py first"
        )
    return json.loads(QUESTIONS_MANIFEST_PATH.read_text(encoding="utf-8"))


async def _first(db: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
    return (await db.execute(stmt)).scalars().first()


async def _upsert_owner(db: AsyncSession, summary: SeedSummary) -> User:
    user = await _first(db, select(User).where(User.email == OWNER_EMAIL))
    if user is None:
        user = User(
            user_id=_uuid(),
            email=OWNER_EMAIL,
            name="COO路径扩展管理员",
            role="admin",
            department="销售训练演示部",
            is_active=True,
            wechat_user_id=_wechat_id(OWNER_EMAIL),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
    return user


def _path_config(
    *,
    order_index: int,
    level_title: str,
    level_description: str,
    unlock_after_unit_ids: list[str] | None = None,
    primary_action_label: str = "开始本章测验",
) -> dict[str, Any]:
    return SalesTrainerPathConfig(
        enabled=True,
        path_key=PATH_KEY,
        path_title=PATH_TITLE,
        goal_title=GOAL_TITLE,
        level_title=level_title,
        level_description=level_description,
        order_index=order_index,
        unlock_after_unit_ids=unlock_after_unit_ids or [],
        completion_rule="passed",
        primary_action_label=primary_action_label,
        retry_action_label="重练本关",
        review_action_label="查看结果",
        guidance_templates={
            "not_started": "建议先阅读对应章节，再完成本章测验。",
            "not_passed": "最近一次未通过，请复习章节后重练。",
            "start_level_reason": "按 COO 谈市场系列继续推进下一项核心能力。",
            "retry_level_reason": "先把当前章节测验补齐，再进入下一关。",
            "path_completed_reason": "已形成完整 COO 系列训练证据，可以回看结果。",
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
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == name,
            SalesTrainerUnit.unit_type == unit_type,
        ),
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
    unit.description = description
    unit.config = config
    unit.status = "published"
    unit.updated_by = owner_id
    return unit


async def _replace_unit_questions(
    db: AsyncSession,
    unit_id: str,
    question_ids: Sequence[str],
) -> None:
    await db.execute(
        delete(SalesTrainerUnitQuestion).where(
            SalesTrainerUnitQuestion.unit_id == unit_id
        )
    )
    for index, question_id in enumerate(question_ids, start=1):
        db.add(
            SalesTrainerUnitQuestion(
                unit_id=unit_id,
                question_id=question_id,
                order_index=index,
                points=10,
            )
        )


def _quiz_pass_threshold(question_count: int) -> int:
    """~67% pass line, consistent with legacy 20/30 for 3-question units."""
    return max(1, (question_count * 10 * 2 + 2) // 3)


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    manifest = load_manifest()
    series_list: list[dict[str, Any]] = manifest["series"]
    content_id = read_content_id()
    questions_by_series = read_questions_manifest()
    owner = await _upsert_owner(db, summary)
    await db.flush()

    coo_units: list[SalesTrainerUnit] = []
    previous_unit_id: str | None = None

    for item in series_list:
        series_index = int(item["series_index"])
        expected_count = len(item.get("question_slots") or [])
        question_ids = questions_by_series.get(str(series_index), [])
        if expected_count and len(question_ids) != expected_count:
            raise VerifyError(
                f"series {series_index} expected {expected_count} questions, got {len(question_ids)}"
            )
        if not question_ids:
            raise VerifyError(f"series {series_index} has no question bindings")

        questions = (
            (
                await db.execute(
                    select(QuestionItem).where(
                        QuestionItem.question_id.in_(question_ids),
                        QuestionItem.status == "published",
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(questions) != len(question_ids):
            raise VerifyError(
                f"series {series_index} published questions missing "
                f"(expected {len(question_ids)}, got {len(questions)})"
            )

        question_count = len(question_ids)
        pass_threshold = _quiz_pass_threshold(question_count)

        unlock_ids = [previous_unit_id] if previous_unit_id else []
        short_title = item["short_title"]
        level_title = item["path"]["level_title"]
        unit = await _upsert_unit(
            db,
            summary,
            owner_id=str(owner.user_id),
            name=item["quiz_unit_name"],
            description=f"COO谈市场系列之{series_index}「{short_title}」配套测验（{question_count}题）。",
            unit_type="quiz",
            config={
                "quiz": {"pass_threshold": pass_threshold},
                "path": _path_config(
                    order_index=series_index,
                    level_title=level_title,
                    level_description=f"阅读第{series_index}章并完成 {question_count} 道测验题。",
                    unlock_after_unit_ids=unlock_ids,
                ),
                "learner": {
                    "learning_content_id": content_id,
                    "chapter_order_index": series_index,
                },
            },
        )
        await db.flush()
        await _replace_unit_questions(db, str(unit.unit_id), question_ids)
        coo_units.append(unit)
        previous_unit_id = str(unit.unit_id)

    last_coo_unit_id = str(coo_units[-1].unit_id)

    legacy_quiz = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == LEGACY_QUIZ_UNIT_NAME,
            SalesTrainerUnit.unit_type == "quiz",
        ),
    )
    if legacy_quiz is None:
        raise VerifyError(f"legacy quiz unit not found: {LEGACY_QUIZ_UNIT_NAME}")

    legacy_audio = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == LEGACY_AUDIO_UNIT_NAME,
            SalesTrainerUnit.unit_type == "audio_scoring",
        ),
    )
    if legacy_audio is None:
        raise VerifyError(f"legacy audio unit not found: {LEGACY_AUDIO_UNIT_NAME}")

    legacy_quiz_config = dict(legacy_quiz.config or {})
    legacy_quiz_path = dict(legacy_quiz_config.get("path") or {})
    legacy_quiz_path.update(
        _path_config(
            order_index=16,
            level_title="第16关：产品定位",
            level_description="用客观题确认新人是否理解首次客户沟通的目标和结构。",
            unlock_after_unit_ids=[last_coo_unit_id],
            primary_action_label="开始本关",
        )
    )
    legacy_quiz_config["path"] = legacy_quiz_path
    legacy_quiz.config = legacy_quiz_config
    legacy_quiz.updated_by = str(owner.user_id)
    summary.updated += 1

    legacy_audio_config = dict(legacy_audio.config or {})
    legacy_audio_path = dict(legacy_audio_config.get("path") or {})
    legacy_audio_path.update(
        _path_config(
            order_index=17,
            level_title="第17关：客户开场录音",
            level_description="把产品定位理解转成真实销售开场表达。",
            unlock_after_unit_ids=[str(legacy_quiz.unit_id)],
            primary_action_label="上传语音作业",
        )
    )
    legacy_audio_config["path"] = legacy_audio_path
    legacy_audio.config = legacy_audio_config
    legacy_audio.updated_by = str(owner.user_id)
    summary.updated += 1

    summary.content_id = content_id
    summary.coo_unit_ids = [str(unit.unit_id) for unit in coo_units]
    await db.commit()
    await verify(db, summary=summary)
    return summary


async def verify(
    db: AsyncSession, *, summary: SeedSummary | None = None
) -> SeedSummary:
    summary = summary or SeedSummary()
    manifest = load_manifest()
    content_id = read_content_id()
    summary.content_id = content_id

    learner = await _first(db, select(User).where(User.email == LEARNER_EMAIL))
    if learner is None:
        raise VerifyError(
            f"demo learner {LEARNER_EMAIL} not found; run seed_sales_trainer_goal_path_demo.py"
        )

    coo_unit_names = [item["quiz_unit_name"] for item in manifest["series"]]
    coo_units = (
        (
            await db.execute(
                select(SalesTrainerUnit).where(
                    SalesTrainerUnit.name.in_(coo_unit_names),
                    SalesTrainerUnit.unit_type == "quiz",
                    SalesTrainerUnit.status == "published",
                )
            )
        )
        .scalars()
        .all()
    )
    if len(coo_units) != COO_UNIT_COUNT:
        raise VerifyError(f"expected {COO_UNIT_COUNT} COO units, got {len(coo_units)}")

    for unit in coo_units:
        learner_cfg = (unit.config or {}).get("learner") or {}
        if learner_cfg.get("learning_content_id") != content_id:
            raise VerifyError(f"unit {unit.name} missing learner.learning_content_id")
        if not learner_cfg.get("chapter_order_index"):
            raise VerifyError(f"unit {unit.name} missing learner.chapter_order_index")
        path_cfg = (unit.config or {}).get("path") or {}
        if path_cfg.get("path_key") != PATH_KEY:
            raise VerifyError(f"unit {unit.name} path_key mismatch")

    legacy_quiz = await _first(
        db,
        select(SalesTrainerUnit).where(SalesTrainerUnit.name == LEGACY_QUIZ_UNIT_NAME),
    )
    legacy_audio = await _first(
        db,
        select(SalesTrainerUnit).where(SalesTrainerUnit.name == LEGACY_AUDIO_UNIT_NAME),
    )
    if legacy_quiz is None or legacy_audio is None:
        raise VerifyError("legacy demo units missing")

    quiz_order = ((legacy_quiz.config or {}).get("path") or {}).get("order_index")
    audio_order = ((legacy_audio.config or {}).get("path") or {}).get("order_index")
    if quiz_order != 16 or audio_order != 17:
        raise VerifyError(
            f"legacy order mismatch: quiz={quiz_order} audio={audio_order}"
        )

    paths = await SalesTrainerPathService(db).list_paths_for_user(str(learner.user_id))
    path = next((item for item in paths if item["path_key"] == PATH_KEY), None)
    if path is None:
        raise VerifyError(
            "new_seller_goal_path not returned by SalesTrainerPathService"
        )
    if path["total_levels"] != TOTAL_LEVELS:
        raise VerifyError(
            f"expected {TOTAL_LEVELS} path levels, got {path['total_levels']}"
        )

    summary.coo_unit_ids = [str(unit.unit_id) for unit in coo_units]
    summary.verified = True
    return summary


async def run(*, verify_only: bool) -> tuple[int, SeedSummary | None, str | None]:
    if not MANIFEST_PATH.exists():
        return 2, None, f"missing manifest: {MANIFEST_PATH}"

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
        description="Seed or verify COO path extension on new_seller_goal_path."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify COO path units and path aggregation.",
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

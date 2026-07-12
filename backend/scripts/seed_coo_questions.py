"""Seed COO series companion questions for sales_trainer path units.

Usage:
  PYTHONPATH=src python scripts/seed_coo_questions.py
  PYTHONPATH=src python scripts/seed_coo_questions.py --verify-only
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
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from coo_question_prompts import resolve_short_answer_ai_scoring
from sales_trainer.services.question_bank_adapter import QuestionBankAdapter

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.db.models import User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import QuestionCategory, QuestionItem

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs/content/coo-series-manifest.yaml"
SPECS_PATH = Path(__file__).resolve().parent / "coo_question_specs.json"
QUESTIONS_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "config-assets/coo-questions-manifest.json"
)
OWNER_EMAIL = "coo.questions.seed.admin@example.com"
CATEGORY_NAME = "COO谈市场配套题库"
DEPARTMENT = "销售训练内容部"

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    """Raised when verify-only checks fail."""


@dataclass(slots=True)
class SeedSummary:
    created: int = 0
    updated: int = 0
    verified: bool = False
    question_count: int = 0

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"question_count={self.question_count}",
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


def load_question_specs() -> list[dict[str, Any]]:
    return json.loads(SPECS_PATH.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _build_scoring_criteria(spec: dict[str, Any]) -> dict[str, Any]:
    qtype = spec["question_type"]
    if qtype == "single_choice":
        return {
            "question_type": "single_choice",
            "options": [
                {"value": value, "label": label} for value, label in spec["options"]
            ],
            "correct_answer": spec["correct"],
            "dimensions": [f"coo_series_{spec['series_index']:02d}"],
            "explanation": spec.get("explanation", ""),
            "natural_key": spec["natural_key"],
        }
    if qtype == "true_false":
        return {
            "question_type": "true_false",
            "correct_bool": bool(spec["correct_bool"]),
            "dimensions": [f"coo_series_{spec['series_index']:02d}"],
            "explanation": spec.get("explanation", ""),
            "natural_key": spec["natural_key"],
        }
    series_index = int(spec["series_index"])
    ai_enabled = series_index <= 5
    ai_config = resolve_short_answer_ai_scoring(
        spec,
        enabled=ai_enabled,
        pass_threshold=70,
    )
    return {
        "question_type": "short_answer",
        "dimensions": [f"coo_series_{spec['series_index']:02d}"],
        "explanation": spec.get("explanation", ""),
        "natural_key": spec["natural_key"],
        "ai_scoring": ai_config,
    }


async def _first(db: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
    return (await db.execute(stmt)).scalars().first()


async def _upsert_owner(db: AsyncSession, summary: SeedSummary) -> User:
    user = await _first(db, select(User).where(User.email == OWNER_EMAIL))
    if user is None:
        user = User(
            user_id=_uuid(),
            email=OWNER_EMAIL,
            name="COO题库导入管理员",
            role="admin",
            department=DEPARTMENT,
            is_active=True,
            wechat_user_id=_wechat_id(OWNER_EMAIL),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
    return user


async def _upsert_category(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> QuestionCategory:
    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.usage_scope == "sales_trainer",
            QuestionCategory.name == CATEGORY_NAME,
        ),
    )
    if category is None:
        category = QuestionCategory(
            category_id=_uuid(),
            name=CATEGORY_NAME,
            usage_scope="sales_trainer",
            order_index=2,
            created_by=owner_id,
        )
        db.add(category)
        summary.created += 1
    else:
        summary.updated += 1
    category.description = "COO谈市场十五系列配套测验题库。"
    category.updated_by = owner_id
    return category


async def _upsert_question(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    category_id: str,
    spec: dict[str, Any],
) -> QuestionItem:
    natural_key = spec["natural_key"]
    title = spec["title"]
    question = await _first(
        db,
        select(QuestionItem).where(
            QuestionItem.usage_scope == "sales_trainer",
            QuestionItem.title == title,
        ),
    )
    if question is None:
        question = QuestionItem(
            question_id=_uuid(),
            title=title,
            usage_scope="sales_trainer",
            created_by=owner_id,
        )
        db.add(question)
        summary.created += 1
    else:
        summary.updated += 1

    scoring_criteria = _build_scoring_criteria(spec)
    question.category_id = category_id
    question.stem = spec["stem"]
    question.reference_answer = spec["reference_answer"]
    question.scoring_criteria = scoring_criteria
    question.scoring_dimensions = [f"coo_series_{spec['series_index']:02d}"]
    question.tags = ["COO谈市场", f"系列{spec['series_index']}", natural_key]
    question.difficulty = (
        "easy" if spec["question_type"] != "short_answer" else "medium"
    )
    question.status = "published"
    question.safety_flagged = False
    question.department = DEPARTMENT
    question.version = max(int(question.version or 1), 1)
    question.published_by = owner_id
    question.published_at = question.published_at or _now()
    question.updated_by = owner_id
    return question


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    specs = load_question_specs()
    manifest = load_manifest()
    expected_keys = {
        slot["natural_key"]
        for series in manifest["series"]
        for slot in series["question_slots"]
    }
    spec_keys = {spec["natural_key"] for spec in specs}
    if spec_keys != expected_keys:
        missing = expected_keys - spec_keys
        extra = spec_keys - expected_keys
        raise VerifyError(
            f"question spec keys mismatch: missing={sorted(missing)} extra={sorted(extra)}"
        )

    owner = await _upsert_owner(db, summary)
    await db.flush()
    category = await _upsert_category(db, summary, owner_id=str(owner.user_id))
    await db.flush()

    by_series: dict[str, list[str]] = {}
    for spec in sorted(specs, key=lambda item: item["natural_key"]):
        question = await _upsert_question(
            db,
            summary,
            owner_id=str(owner.user_id),
            category_id=str(category.category_id),
            spec=spec,
        )
        await db.flush()
        series_key = str(spec["series_index"])
        by_series.setdefault(series_key, []).append(str(question.question_id))

    summary.question_count = len(specs)
    QUESTIONS_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUESTIONS_MANIFEST_PATH.write_text(
        json.dumps(by_series, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    await db.commit()
    await verify(db, summary=summary)
    return summary


async def verify(
    db: AsyncSession, *, summary: SeedSummary | None = None
) -> SeedSummary:
    summary = summary or SeedSummary()
    manifest = load_manifest()
    specs = load_question_specs()

    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.usage_scope == "sales_trainer",
            QuestionCategory.name == CATEGORY_NAME,
        ),
    )
    if category is None:
        raise VerifyError("COO question category does not exist")

    questions = (
        (
            await db.execute(
                select(QuestionItem).where(
                    QuestionItem.usage_scope == "sales_trainer",
                    QuestionItem.category_id == category.category_id,
                    QuestionItem.status == "published",
                )
            )
        )
        .scalars()
        .all()
    )
    titles = {spec["title"] for spec in specs}
    found_titles = {question.title for question in questions}
    if not titles.issubset(found_titles):
        raise VerifyError(
            f"missing published COO questions: {sorted(titles - found_titles)}"
        )

    adapter = QuestionBankAdapter(db)
    unsupported = [
        adapter.unsupported_reason(question)
        for question in questions
        if question.title in titles and adapter.unsupported_reason(question) is not None
    ]
    if unsupported:
        details = [
            f"{item.question_id}:{item.reason}"
            for item in unsupported
            if item is not None
        ]
        raise VerifyError(f"unsupported COO question contracts: {details}")

    if not QUESTIONS_MANIFEST_PATH.exists():
        raise VerifyError("coo-questions-manifest.json does not exist")
    manifest_data = json.loads(QUESTIONS_MANIFEST_PATH.read_text(encoding="utf-8"))
    if len(manifest_data) != len(manifest["series"]):
        raise VerifyError("questions manifest series count mismatch")

    summary.question_count = len(specs)
    summary.verified = True
    return summary


async def run(*, verify_only: bool) -> tuple[int, SeedSummary | None, str | None]:
    if not MANIFEST_PATH.exists():
        return 2, None, f"missing manifest: {MANIFEST_PATH}"
    if not SPECS_PATH.exists():
        return 2, None, f"missing specs: {SPECS_PATH}"

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
        description="Seed or verify COO companion questions."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify COO questions and manifest.",
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

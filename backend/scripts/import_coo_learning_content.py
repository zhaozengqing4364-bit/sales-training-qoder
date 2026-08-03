"""Import COO market series from coo.md into LearningContent + 15 chapters.

Usage:
  PYTHONPATH=src python scripts/import_coo_learning_content.py
  PYTHONPATH=src python scripts/import_coo_learning_content.py --verify-only
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
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
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
from common.db.models import User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import LearningChapter, LearningContent

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs/content/coo-series-manifest.yaml"
COO_MD_PATH = REPO_ROOT / "coo.md"
CONTENT_ID_PATH = (
    Path(__file__).resolve().parents[1] / "config-assets/coo-learning-content.id"
)
OWNER_EMAIL = "coo.learning.import.admin@example.com"

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    """Raised when verify-only checks fail."""


@dataclass(slots=True)
class ImportSummary:
    created: int = 0
    updated: int = 0
    verified: bool = False
    content_id: str | None = None
    chapter_count: int = 0

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"content_id={self.content_id or ''}",
            f"chapter_count={self.chapter_count}",
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


def _hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"


def load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def slice_series_body(lines: list[str], start_line: int, end_line: int) -> str:
    chunk = lines[start_line:end_line]
    if chunk and chunk[0].startswith("# 系列之"):
        chunk = chunk[1:]
    body = "\n".join(chunk).strip()
    return body


async def _first(db: AsyncSession, stmt: Select[tuple[ModelT]]) -> ModelT | None:
    return (await db.execute(stmt)).scalars().first()


async def _upsert_owner(db: AsyncSession, summary: ImportSummary) -> User:
    user = await _first(db, select(User).where(User.email == OWNER_EMAIL))
    if user is None:
        user = User(
            user_id=_uuid(),
            email=OWNER_EMAIL,
            name="COO学习内容导入管理员",
            role="admin",
            is_active=True,
            wechat_user_id=_wechat_id(OWNER_EMAIL),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
        user.is_active = True
    return user


async def import_content(db: AsyncSession) -> ImportSummary:
    summary = ImportSummary()
    manifest = load_manifest()
    lc_meta = manifest["learning_content"]
    series_list: list[dict[str, Any]] = manifest["series"]
    coo_lines = COO_MD_PATH.read_text(encoding="utf-8").splitlines()

    owner = await _upsert_owner(db, summary)
    await db.flush()

    content = await _first(
        db,
        select(LearningContent).where(LearningContent.title == lc_meta["title"]),
    )
    if content is None:
        content = LearningContent(
            learning_content_id=_uuid(),
            title=lc_meta["title"],
        )
        db.add(content)
        summary.created += 1
    else:
        summary.updated += 1

    chapter_payloads: list[dict[str, Any]] = []
    for item in series_list:
        anchor = item["source_anchor"]
        body = slice_series_body(coo_lines, anchor["start_line"], anchor["end_line"])
        if not body:
            raise VerifyError(
                f"empty chapter body for {item['chapter_key']} "
                f"(lines {anchor['start_line']}-{anchor['end_line']})"
            )
        chapter_payloads.append(
            {
                "order_index": int(item["series_index"]),
                "chapter_key": item["chapter_key"],
                "title": item["title"],
                "content": body,
            }
        )

    content.summary = lc_meta.get("summary")
    content.owner = lc_meta.get("owner", "coo-market-series")
    content.source = lc_meta.get("source", "coo.md")
    content.status = "published"
    content.safety_flagged = False
    content.version = max(int(content.version or 1), 1)
    content.content_hash = _hash(
        json.dumps(chapter_payloads, ensure_ascii=False, separators=(",", ":"))
    )
    content.created_by = content.created_by or str(owner.user_id)
    content.updated_by = str(owner.user_id)
    content.published_by = str(owner.user_id)
    content.published_at = content.published_at or _now()
    await db.flush()

    for payload in chapter_payloads:
        order_index = payload["order_index"]
        chapter = await _first(
            db,
            select(LearningChapter).where(
                LearningChapter.learning_content_id == content.learning_content_id,
                LearningChapter.order_index == order_index,
            ),
        )
        if chapter is None:
            chapter = LearningChapter(
                chapter_id=_uuid(),
                learning_content_id=str(content.learning_content_id),
                order_index=order_index,
            )
            db.add(chapter)
            summary.created += 1
        else:
            summary.updated += 1
        chapter.title = payload["title"]
        chapter.content = payload["content"]
        chapter.created_by = chapter.created_by or str(owner.user_id)
        chapter.updated_by = str(owner.user_id)

    summary.content_id = str(content.learning_content_id)
    summary.chapter_count = len(chapter_payloads)
    await db.commit()

    CONTENT_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_ID_PATH.write_text(f"{summary.content_id}\n", encoding="utf-8")

    await verify(db, summary=summary)
    return summary


async def verify(db: AsyncSession, *, summary: ImportSummary | None = None) -> ImportSummary:
    summary = summary or ImportSummary()
    manifest = load_manifest()
    lc_meta = manifest["learning_content"]
    expected_count = len(manifest["series"])

    content = await _first(
        db,
        select(LearningContent).where(LearningContent.title == lc_meta["title"]),
    )
    if content is None:
        raise VerifyError("COO learning content does not exist")
    if content.status != "published":
        raise VerifyError("COO learning content is not published")

    chapter_count = await db.scalar(
        select(func.count())
        .select_from(LearningChapter)
        .where(LearningChapter.learning_content_id == content.learning_content_id)
    )
    if int(chapter_count or 0) != expected_count:
        raise VerifyError(
            f"expected {expected_count} chapters, got {chapter_count}"
        )

    empty_chapters = (
        await db.execute(
            select(LearningChapter.order_index).where(
                LearningChapter.learning_content_id == content.learning_content_id,
                (LearningChapter.content.is_(None))
                | (func.length(func.trim(LearningChapter.content)) < 100),
            )
        )
    ).scalars().all()
    if empty_chapters:
        raise VerifyError(f"chapters with insufficient content: {list(empty_chapters)}")

    summary.content_id = str(content.learning_content_id)
    summary.chapter_count = int(chapter_count or 0)
    summary.verified = True
    return summary


async def run(*, verify_only: bool) -> tuple[int, ImportSummary | None, str | None]:
    if not MANIFEST_PATH.exists():
        return 2, None, f"missing manifest: {MANIFEST_PATH}"
    if not COO_MD_PATH.exists():
        return 2, None, f"missing coo.md: {COO_MD_PATH}"

    async with AsyncSessionLocal() as db:
        try:
            summary = await verify(db) if verify_only else await import_content(db)
        except VerifyError as exc:
            await db.rollback()
            return 2, None, str(exc)
        except Exception as exc:
            await db.rollback()
            return 1, None, str(exc)
        return 0, summary, None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import or verify COO learning content from coo.md."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify published COO learning content exists.",
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

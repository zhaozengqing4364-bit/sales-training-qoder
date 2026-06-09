from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.db.models import User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import ExamPaperQuestionBinding, SalesTrainerPathConfig

PATH_KEY = "newcomer_training_path_v1"
LEGACY_PATH_KEY = "new_seller_modules_v1"
PATH_TITLE = "新人训练路径"
GOAL_TITLE = "掌握新人核心训练路径"
MODULE_KEYS = ["ppt_explain", "business_skills", "pyramid_speech", "realtime_placeholder"]
BUSINESS_SKILLS_MODULE_KEY = "business_skills"
BUSINESS_SKILLS_PAPER_KEY = "newcomer_business_skills_paper_v1"
LEARNING_CONTENT_SOURCE = "seed_newcomer_training_path"
LEARNING_CONTENT_TITLE = "见客户前商务礼仪"
LEARNING_CONTENT_SUMMARY = "阅读文章后完成商务技巧考卷。"
BUSINESS_SKILLS_QUESTION_TITLES = [
    "见客户前第一步是什么？",
    "商务礼仪多选题",
    "礼仪判断题",
    "商务技巧简答题",
]
OWNER_EMAIL = "newcomer.training.seed.admin@example.com"
LEARNER_EMAIL = "newcomer.training.seed.learner@example.com"

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    pass


class SeedSummary:
    def __init__(self) -> None:
        self.created = 0
        self.updated = 0
        self.verified = False
        self.path_key = PATH_KEY

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"path_key={self.path_key}",
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


def _wechat_id(email: str) -> str:
    normalized = email.strip().lower()
    return f"local_{normalized.replace('@', '_at_').replace('.', '_')}"


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
            department="新人训练路径",
            is_active=True,
            wechat_user_id=_wechat_id(normalized_email),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
        user.name = name
        user.role = role
        user.department = "新人训练路径"
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = _wechat_id(normalized_email)
    return user


def _path_config(
    *,
    module_key: str,
    module_type: str,
    order_index: int,
    level_title: str,
    level_description: str,
    enabled: bool = True,
    completion_rule: Literal["passed", "scored", "submitted"] = "scored",
    target_unit_id: str | None = None,
    learning_content_id: str | None = None,
    exam_paper_id: str | None = None,
    disabled_reason: str | None = None,
    primary_action_label: str | None = None,
) -> dict[str, Any]:
    return SalesTrainerPathConfig(
        enabled=enabled,
        path_key=PATH_KEY,
        module_key=module_key,
        module_type=module_type,
        path_title=PATH_TITLE,
        goal_title=GOAL_TITLE,
        level_title=level_title,
        level_description=level_description,
        order_index=order_index,
        target_unit_id=target_unit_id,
        learning_content_id=learning_content_id,
        exam_paper_id=exam_paper_id,
        disabled_reason=disabled_reason,
        completion_rule=completion_rule,
        primary_action_label=primary_action_label,
        retry_action_label="再练一次",
        review_action_label="查看结果",
        guidance_templates={
            "not_started": "可按模块顺序开始本项训练。",
            "not_passed": "最近一次训练未通关，可重练。",
            "start_level_reason": "继续推进新人训练路径。",
            "retry_level_reason": "先补齐当前模块再继续。",
            "path_completed_reason": "已有完整训练记录，可回看结果。",
        },
    ).model_dump(exclude_none=True)


async def _upsert_learning_content(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> LearningContent:
    content = await _first(
        db,
        select(LearningContent).where(LearningContent.source == LEARNING_CONTENT_SOURCE),
    )
    if content is None:
        content = LearningContent(
            learning_content_id=_uuid(),
            title=LEARNING_CONTENT_TITLE,
            summary=LEARNING_CONTENT_SUMMARY,
            owner=PATH_TITLE,
            source=LEARNING_CONTENT_SOURCE,
            status="published",
            safety_flagged=False,
            created_by=owner_id,
            updated_by=owner_id,
            published_by=owner_id,
            published_at=_now(),
        )
        db.add(content)
        summary.created += 1
    else:
        summary.updated += 1
        content.title = LEARNING_CONTENT_TITLE
        content.summary = LEARNING_CONTENT_SUMMARY
        content.owner = PATH_TITLE
        content.source = LEARNING_CONTENT_SOURCE
        content.status = "published"
        content.safety_flagged = False
        content.updated_by = owner_id
        content.published_by = content.published_by or owner_id
        content.published_at = content.published_at or _now()
    return content


async def _upsert_chapter(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    content_id: str,
    title: str,
    content: str,
    order_index: int,
) -> LearningChapter:
    chapter = await _first(
        db,
        select(LearningChapter).where(
            LearningChapter.learning_content_id == content_id,
            LearningChapter.order_index == order_index,
        ),
    )
    if chapter is None:
        chapter = LearningChapter(
            chapter_id=_uuid(),
            learning_content_id=content_id,
            title=title,
            content=content,
            order_index=order_index,
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(chapter)
        summary.created += 1
    else:
        summary.updated += 1
        chapter.title = title
        chapter.content = content
        chapter.updated_by = owner_id
    return chapter


async def _upsert_question_category(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> QuestionCategory:
    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.usage_scope == "sales_trainer",
            QuestionCategory.name == "新人训练路径商务技巧题库",
        ),
    )
    if category is None:
        category = QuestionCategory(
            category_id=_uuid(),
            name="新人训练路径商务技巧题库",
            usage_scope="sales_trainer",
            order_index=1,
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(category)
        summary.created += 1
    else:
        summary.updated += 1
        category.updated_by = owner_id
    category.description = "新人训练路径商务技巧模块题库。"
    return category


async def _upsert_question(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    category_id: str,
    title: str,
    stem: str,
    reference_answer: str,
    scoring_criteria: dict[str, Any],
    scoring_dimensions: list[str],
) -> QuestionItem:
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
            updated_by=owner_id,
        )
        db.add(question)
        summary.created += 1
    else:
        summary.updated += 1
        question.updated_by = owner_id
    question.category_id = category_id
    question.stem = stem
    question.reference_answer = reference_answer
    question.scoring_criteria = scoring_criteria
    question.scoring_dimensions = scoring_dimensions
    question.tags = ["新人训练路径", BUSINESS_SKILLS_MODULE_KEY, title]
    question.difficulty = "medium"
    question.status = "published"
    question.safety_flagged = False
    question.department = "新人训练路径"
    question.version = max(int(question.version or 1), 1)
    question.published_by = owner_id
    question.published_at = question.published_at or _now()
    return question


async def _upsert_paper(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    unit_id: str,
    question_bindings: list[ExamPaperQuestionBinding],
) -> SalesTrainerExamPaper:
    paper = await _first(
        db,
        select(SalesTrainerExamPaper).where(
            SalesTrainerExamPaper.paper_key == BUSINESS_SKILLS_PAPER_KEY,
        ),
    )
    if paper is None:
        paper = SalesTrainerExamPaper(
            paper_id=_uuid(),
            paper_key=BUSINESS_SKILLS_PAPER_KEY,
            title="商务技巧考卷",
            description="绑定见客户前商务礼仪文章的考卷。",
            module_key=BUSINESS_SKILLS_MODULE_KEY,
            unit_id=unit_id,
            pass_threshold=70,
            status="published",
            created_by=owner_id,
            updated_by=owner_id,
        )
        db.add(paper)
        summary.created += 1
    else:
        summary.updated += 1
        paper.title = "商务技巧考卷"
        paper.description = "绑定见客户前商务礼仪文章的考卷。"
        paper.module_key = BUSINESS_SKILLS_MODULE_KEY
        paper.unit_id = unit_id
        paper.pass_threshold = 70
        paper.status = "published"
        paper.updated_by = owner_id
    paper.created_by = paper.created_by or owner_id
    paper.updated_by = owner_id
    await db.flush()
    await db.execute(
        delete(SalesTrainerUnitQuestion).where(
            SalesTrainerUnitQuestion.unit_id == unit_id
        )
    )
    for binding in question_bindings:
        db.add(
            SalesTrainerUnitQuestion(
                id=_uuid(),
                unit_id=unit_id,
                question_id=binding.question_id,
                order_index=binding.order_index,
                points=binding.points,
            )
        )
    return paper


async def _upsert_unit(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
    name: str,
    description: str,
    unit_type: str,
    config: dict[str, Any],
    status: str = "published",
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
            updated_by=owner_id,
        )
        db.add(unit)
        summary.created += 1
    else:
        summary.updated += 1
        unit.updated_by = owner_id
    unit.description = description
    unit.config = config
    unit.status = status
    return unit


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    owner = await _upsert_user(
        db,
        summary,
        email=OWNER_EMAIL,
        name="新人训练路径种子管理员",
        role="admin",
    )
    await _upsert_user(
        db,
        summary,
        email=LEARNER_EMAIL,
        name="新人训练路径演示学员",
        role="user",
    )
    await db.flush()

    content = await _upsert_learning_content(db, summary, owner_id=str(owner.user_id))
    await db.flush()
    await _upsert_chapter(
        db,
        summary,
        owner_id=str(owner.user_id),
        content_id=str(content.learning_content_id),
        title="拜访前准备",
        content="拜访客户前先确认背景、目标与礼仪要求。",
        order_index=1,
    )
    await _upsert_chapter(
        db,
        summary,
        owner_id=str(owner.user_id),
        content_id=str(content.learning_content_id),
        title="商务礼仪",
        content="保持得体表达、明确边界、避免夸大承诺。",
        order_index=2,
    )

    category = await _upsert_question_category(db, summary, owner_id=str(owner.user_id))
    await db.flush()
    q1 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="见客户前第一步是什么？",
        stem="见客户前最重要的准备动作是什么？",
        reference_answer="确认客户背景与目标。",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "直接谈价格"},
                {"value": "B", "label": "确认客户背景与目标"},
                {"value": "C", "label": "跳过准备快速见面"},
            ],
            "correct_answer": "B",
        },
        scoring_dimensions=["business_skills", "prep"],
    )
    q2 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="商务礼仪多选题",
        stem="以下哪些做法符合商务礼仪？",
        reference_answer="保持准时、表达清晰、尊重对方。",
        scoring_criteria={
            "question_type": "multiple_choice",
            "options": [
                {"value": "A", "label": "提前到场"},
                {"value": "B", "label": "打断对方发言"},
                {"value": "C", "label": "表达清晰"},
                {"value": "D", "label": "尊重对方"},
            ],
            "correct_answers": ["A", "C", "D"],
        },
        scoring_dimensions=["business_skills", "etiquette"],
    )
    q3 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="礼仪判断题",
        stem="见客户时可以随意打断对方以抢占话语权。",
        reference_answer="错误。",
        scoring_criteria={
            "question_type": "true_false",
            "correct_bool": False,
        },
        scoring_dimensions=["business_skills", "etiquette"],
    )
    q4 = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="商务技巧简答题",
        stem="请简述商务拜访时需要注意的两个要点。",
        reference_answer="保持尊重和清晰表达。",
        scoring_criteria={
            "question_type": "short_answer",
            "ai_scoring": {
                "enabled": True,
                "pass_threshold": 70,
            },
        },
        scoring_dimensions=["business_skills", "short_answer"],
    )
    await db.flush()

    paper_unit = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="商务技巧",
        description="阅读见客户前商务礼仪文章并完成考卷。",
        unit_type="quiz",
        config={
            "quiz": {"pass_threshold": 70},
            "path": _path_config(
                module_key=BUSINESS_SKILLS_MODULE_KEY,
                module_type="article_exam",
                order_index=2,
                level_title="第2关：商务技巧",
                level_description="阅读文章后完成商务技巧考卷。",
                learning_content_id=str(content.learning_content_id),
                exam_paper_id=BUSINESS_SKILLS_PAPER_KEY,
                completion_rule="submitted",
                primary_action_label="阅读文章并考试",
            ),
            "learner": {
                "learning_content_id": str(content.learning_content_id),
                "article_title": content.title,
            },
        },
    )
    await db.flush()
    await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="PPT讲解",
        description="上传PPT讲解录音并获取评分。",
        unit_type="audio_scoring",
        config={
            "audio": {
                "purpose": "ppt_pitch",
                "pass_threshold": 70,
            },
            "path": _path_config(
                module_key="ppt_explain",
                module_type="audio_scoring",
                order_index=1,
                level_title="第1关：PPT讲解",
                level_description="上传PPT讲解录音并获取评分。",
                target_unit_id=None,
                completion_rule="scored",
                primary_action_label="上传录音",
            ),
        },
    )
    await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="电梯演讲",
        description="上传 10/20/30 分钟的电梯演讲录音，由 AI 评分。",
        unit_type="audio_scoring",
        config={
            "audio": {
                "purpose": "pyramid_speech",
                "pass_threshold": 70,
            },
            "path": _path_config(
                module_key="pyramid_speech",
                module_type="audio_scoring_group",
                order_index=3,
                level_title="第3关：电梯演讲",
                level_description="按 10/20/30 分钟档位上传录音。",
                completion_rule="scored",
                primary_action_label="上传录音",
            ),
            "duration_options": [10, 20, 30],
        },
    )
    _ = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name="实时对练占位",
        description="当前版本仅展示占位，不允许启动实时对练。",
        unit_type="quiz",
        config={
            "path": _path_config(
                module_key="realtime_placeholder",
                module_type="realtime_placeholder",
                order_index=4,
                level_title="第4关：实时对练（占位）",
                level_description="当前版本不开放。",
                enabled=False,
                completion_rule="submitted",
                disabled_reason="模块 4 仅为占位，不支持实时对练。",
            )
        },
        status="published",
    )

    paper = await _upsert_paper(
        db,
        summary,
        owner_id=str(owner.user_id),
        unit_id=str(paper_unit.unit_id),
        question_bindings=[
            ExamPaperQuestionBinding(question_id=str(q1.question_id), order_index=1, points=25),
            ExamPaperQuestionBinding(question_id=str(q2.question_id), order_index=2, points=25),
            ExamPaperQuestionBinding(question_id=str(q3.question_id), order_index=3, points=25),
            ExamPaperQuestionBinding(question_id=str(q4.question_id), order_index=4, points=25),
        ],
    )

    paper_unit.config = {
        **(paper_unit.config or {}),
        "quiz": {"pass_threshold": 70},
        "path": _path_config(
            module_key=BUSINESS_SKILLS_MODULE_KEY,
            module_type="article_exam",
            order_index=2,
            level_title="第2关：商务技巧",
            level_description="阅读文章后完成商务技巧考卷。",
            learning_content_id=str(content.learning_content_id),
            exam_paper_id=str(paper.paper_id),
            completion_rule="submitted",
            primary_action_label="阅读文章并考试",
        ),
        "learner": {
            "learning_content_id": str(content.learning_content_id),
            "article_title": content.title,
        },
    }
    paper_unit.status = "published"
    paper_unit.updated_by = str(owner.user_id)

    await db.commit()
    await db.refresh(content)
    summary.verified = False
    await verify(db, summary=summary)
    return summary


async def verify(db: AsyncSession, *, summary: SeedSummary | None = None) -> SeedSummary:
    summary = summary or SeedSummary()
    learner = await _first(db, select(User).where(User.email == LEARNER_EMAIL))
    if learner is None:
        raise VerifyError(f"missing learner {LEARNER_EMAIL}")

    content = await _first(
        db,
        select(LearningContent).where(LearningContent.source == LEARNING_CONTENT_SOURCE),
    )
    if content is None:
        raise VerifyError("missing learning content")
    if content.status != "published":
        raise VerifyError("learning content not published")

    chapters = (
        await db.execute(
            select(LearningChapter)
            .where(LearningChapter.learning_content_id == content.learning_content_id)
            .order_by(LearningChapter.order_index.asc())
        )
    ).scalars().all()
    if len(chapters) != 2:
        raise VerifyError(f"expected 2 learning chapters, got {len(chapters)}")

    paper = await _first(
        db,
        select(SalesTrainerExamPaper).where(
            SalesTrainerExamPaper.paper_key == BUSINESS_SKILLS_PAPER_KEY
        ),
    )
    if paper is None:
        raise VerifyError("missing business skills paper")
    if paper.status != "published":
        raise VerifyError("business skills paper not published")
    paper_questions = (
        await db.execute(
            select(SalesTrainerUnitQuestion).where(
                SalesTrainerUnitQuestion.unit_id == paper.unit_id
            )
        )
    ).scalars().all()
    if len(paper_questions) != 4:
        raise VerifyError(
            f"expected 4 business skills paper questions, got {len(paper_questions)}"
        )

    questions = (
        await db.execute(
            select(QuestionItem)
            .where(
                QuestionItem.usage_scope == "sales_trainer",
                QuestionItem.title.in_(BUSINESS_SKILLS_QUESTION_TITLES),
            )
            .order_by(QuestionItem.title.asc())
        )
    ).scalars().all()
    if len(questions) != 4:
        raise VerifyError(
            f"expected 4 seeded business skills questions, got {len(questions)}"
        )

    units = (
        await db.execute(
            select(SalesTrainerUnit).where(
                SalesTrainerUnit.config["path"]["path_key"].as_string() == PATH_KEY
            )
        )
    ).scalars().all()
    if len(units) != len(MODULE_KEYS):
        raise VerifyError(f"expected {len(MODULE_KEYS)} newcomer units, got {len(units)}")

    modules = {}
    for unit in units:
        path = (unit.config or {}).get("path") or {}
        if path.get("path_key") != PATH_KEY:
            raise VerifyError(f"{unit.name} path_key mismatch")
        module_key = path.get("module_key")
        if not module_key:
            raise VerifyError(f"{unit.name} missing module_key")
        modules[str(module_key)] = unit

    expected_keys = set(MODULE_KEYS)
    if set(modules) != expected_keys:
        raise VerifyError(f"module keys mismatch: {sorted(set(modules) ^ expected_keys)}")

    business_unit = modules[BUSINESS_SKILLS_MODULE_KEY]
    business_path = (business_unit.config or {}).get("path") or {}
    if business_path.get("module_type") != "article_exam":
        raise VerifyError("business_skills module_type mismatch")
    if business_path.get("learning_content_id") != str(content.learning_content_id):
        raise VerifyError("business_skills learning_content_id mismatch")
    if business_path.get("exam_paper_id") != str(paper.paper_id):
        raise VerifyError("business_skills exam_paper_id mismatch")

    if ((modules["realtime_placeholder"].config or {}).get("path") or {}).get("enabled") is not False:
        raise VerifyError("module 4 must remain disabled")
    if (modules["pyramid_speech"].config or {}).get("duration_options") != [10, 20, 30]:
        raise VerifyError("pyramid_speech duration options mismatch")

    summary.verified = True
    return summary


async def run(*, verify_only: bool) -> tuple[int, SeedSummary | None, str | None]:
    async with AsyncSessionLocal() as db:
        try:
            summary = await verify(db) if verify_only else await seed(db)
        except VerifyError as exc:
            return 1, None, str(exc)
        return 0, summary, None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed or verify newcomer_training_path_v1 baseline modules."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify baseline records without mutating data.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    exit_code, summary, error = asyncio.run(run(verify_only=bool(args.verify_only)))
    if error:
        print(error, file=sys.stderr)
        return exit_code
    if summary is not None:
        for line in summary.to_lines():
            print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

"""Seed a local sales-trainer goal path demo.

Usage:
  PYTHONPATH=src python scripts/seed_sales_trainer_goal_path_demo.py --verify-only
  PYTHONPATH=src python scripts/seed_sales_trainer_goal_path_demo.py

This script is intentionally a local verification/demo helper. It does not run
at application startup and it does not introduce new sales-trainer tables.
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
from typing import Any, TypeVar

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.question_bank_adapter import QuestionBankAdapter

import agent.models as _agent_models  # noqa: F401 - register ORM mappers
import curriculum_practice.models as _curriculum_models  # noqa: F401 - register ORM mappers
import sales_trainer.models as _sales_trainer_models  # noqa: F401 - register ORM mappers
from common.db.models import User
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.schemas import SalesTrainerPathConfig, ShortAnswerAiScoringConfig

OWNER_EMAIL = "sales-trainer.goal.demo.admin@example.com"
LEARNER_EMAIL = "sales-trainer.goal.demo.learner@example.com"
DEPARTMENT = "销售训练演示部"
CATEGORY_NAME = "新人销售闯关题库"
PATH_KEY = "new_seller_goal_path"
PATH_TITLE = "新人销售闯关"
GOAL_TITLE = "掌握首次客户沟通"
QUIZ_UNIT_NAME = "第一关：产品定位做题"
AUDIO_UNIT_NAME = "第二关：客户开场录音"
PROMPT_NAME = "新人销售开场录音评分"

ModelT = TypeVar("ModelT")


class VerifyError(Exception):
    """Raised when the demo path is not ready."""


@dataclass(slots=True)
class SeedSummary:
    created: int = 0
    updated: int = 0
    verified: bool = False
    path_key: str = PATH_KEY
    quiz_unit_id: str | None = None
    audio_unit_id: str | None = None
    learner_user_id: str | None = None

    def to_lines(self) -> list[str]:
        return [
            f"created={self.created}",
            f"updated={self.updated}",
            f"verified={self.verified}",
            f"path_key={self.path_key}",
            f"quiz_unit_id={self.quiz_unit_id or ''}",
            f"audio_unit_id={self.audio_unit_id or ''}",
            f"learner_user_id={self.learner_user_id or ''}",
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
            department=DEPARTMENT,
            is_active=True,
            wechat_user_id=_wechat_id(normalized_email),
        )
        db.add(user)
        summary.created += 1
    else:
        summary.updated += 1
        user.name = name
        user.role = role
        user.department = DEPARTMENT
        user.is_active = True
        if not user.wechat_user_id:
            user.wechat_user_id = _wechat_id(normalized_email)
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
            order_index=1,
            created_by=owner_id,
        )
        db.add(category)
        summary.created += 1
    else:
        summary.updated += 1
    category.description = "本地验收用题库：覆盖单选、多选、判断和简答配置。"
    category.updated_by = owner_id
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
    tags: list[str],
    difficulty: str = "easy",
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
        )
        db.add(question)
        summary.created += 1
    else:
        summary.updated += 1
    question.category_id = category_id
    question.stem = stem
    question.reference_answer = reference_answer
    question.scoring_criteria = scoring_criteria
    question.scoring_dimensions = scoring_dimensions
    question.tags = tags
    question.difficulty = difficulty
    question.status = "published"
    question.safety_flagged = False
    question.department = DEPARTMENT
    question.version = max(int(question.version or 1), 1)
    question.published_by = owner_id
    question.published_at = question.published_at or _now()
    question.updated_by = owner_id
    return question


async def _upsert_prompt(
    db: AsyncSession,
    summary: SeedSummary,
    *,
    owner_id: str,
) -> SalesTrainerAudioScorePrompt:
    prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.name == PROMPT_NAME,
            SalesTrainerAudioScorePrompt.purpose == "sales_opening_demo",
        ),
    )
    if prompt is None:
        prompt = SalesTrainerAudioScorePrompt(
            prompt_id=_uuid(),
            name=PROMPT_NAME,
            purpose="sales_opening_demo",
            created_by=owner_id,
        )
        db.add(prompt)
        summary.created += 1
    else:
        summary.updated += 1
    prompt.system_prompt = "你是销售训练录音评分员，只输出符合 schema 的 JSON。"
    prompt.scoring_template = (
        "请根据销售开场表达评分，转写文本：{transcript}\n"
        "重点看需求确认、价值表达、推进动作，返回总分、优点和改进建议。"
    )
    prompt.output_schema = {
        "total_score": "number",
        "passed": "boolean",
        "summary": "string",
        "strengths": "array",
        "improvements": "array",
    }
    prompt.version = max(int(prompt.version or 1), 1)
    prompt.status = "published"
    prompt.updated_by = owner_id
    return prompt


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
    questions: Sequence[QuestionItem],
) -> None:
    await db.execute(
        delete(SalesTrainerUnitQuestion).where(
            SalesTrainerUnitQuestion.unit_id == unit_id
        )
    )
    for index, question in enumerate(questions, start=1):
        db.add(
            SalesTrainerUnitQuestion(
                unit_id=unit_id,
                question_id=str(question.question_id),
                order_index=index,
                points=10,
            )
        )


def _path_config(
    *,
    order_index: int,
    level_title: str,
    level_description: str,
    unlock_after_unit_ids: list[str] | None = None,
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
        primary_action_label="开始本关",
        retry_action_label="重练本关",
        review_action_label="查看结果",
        guidance_templates={
            "not_started": "本关还没有训练证据，先完成一次练习。",
            "not_passed": "最近一次没有通关，建议根据反馈重练。",
            "start_level_reason": "按新人销售目标继续推进下一项核心能力。",
            "retry_level_reason": "先把当前薄弱关卡补齐，再进入下一关。",
            "path_completed_reason": "已形成完整销售训练证据，可以回看最近一次结果。",
        },
    ).model_dump(exclude_none=True)


async def seed(db: AsyncSession) -> SeedSummary:
    summary = SeedSummary()
    owner = await _upsert_user(
        db,
        summary,
        email=OWNER_EMAIL,
        name="销售训练演示管理员",
        role="admin",
    )
    learner = await _upsert_user(
        db,
        summary,
        email=LEARNER_EMAIL,
        name="销售训练演示学员",
        role="user",
    )
    await db.flush()

    category = await _upsert_category(db, summary, owner_id=str(owner.user_id))
    await db.flush()

    single_choice = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="识别首次沟通的第一目标",
        stem="第一次和客户沟通时，优先要确认什么？",
        reference_answer="A. 客户当前业务问题",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "客户当前业务问题"},
                {"value": "B", "label": "立刻报价"},
                {"value": "C", "label": "要求客户先签约"},
                {"value": "D", "label": "只介绍公司规模"},
            ],
            "correct_answer": "A",
            "dimensions": ["need_discovery"],
            "explanation": "首次沟通应先建立场景和问题共识，再进入方案或报价。",
        },
        scoring_dimensions=["need_discovery"],
        tags=["首次沟通", "需求确认"],
    )
    multiple_choice = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="判断客户开场信息是否完整",
        stem="一个完整的销售开场通常应包含哪些内容？",
        reference_answer="A. 说明来意；C. 确认客户场景",
        scoring_criteria={
            "question_type": "multiple_choice",
            "options": [
                {"value": "A", "label": "说明来意"},
                {"value": "B", "label": "直接催促付款"},
                {"value": "C", "label": "确认客户场景"},
                {"value": "D", "label": "回避下一步安排"},
            ],
            "correct_answers": ["A", "C"],
            "dimensions": ["opening_structure"],
            "explanation": "开场需要让客户知道你是谁、为何沟通，并快速确认对方场景。",
        },
        scoring_dimensions=["opening_structure"],
        tags=["开场", "结构"],
    )
    true_false = await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="销售开场是否应先确认场景",
        stem="销售开场先确认客户场景，再介绍产品价值。",
        reference_answer="正确",
        scoring_criteria={
            "question_type": "true_false",
            "correct_bool": True,
            "dimensions": ["opening_sequence"],
            "explanation": "先确认场景可以让后续价值表达更具体。",
        },
        scoring_dimensions=["opening_sequence"],
        tags=["开场", "判断"],
    )
    ai_config = ShortAnswerAiScoringConfig(
        enabled=True,
        pass_threshold=70,
        temperature=0.2,
        timeout=30,
        max_retries=1,
        max_tokens=800,
    ).model_dump(exclude_none=True)
    await _upsert_question(
        db,
        summary,
        owner_id=str(owner.user_id),
        category_id=str(category.category_id),
        title="简述首次客户沟通开场白",
        stem="请写一段 60 字以内的首次客户沟通开场白。",
        reference_answer="先自我介绍并说明来意，再用一个问题确认客户当前业务场景，最后约定下一步沟通方向。",
        scoring_criteria={
            "question_type": "short_answer",
            "dimensions": ["opening_expression", "need_discovery"],
            "explanation": "简答题由 AI 结合参考答案、评分维度和学员答案给出 0-100 分。",
            "ai_scoring": ai_config,
        },
        scoring_dimensions=["opening_expression", "need_discovery"],
        tags=["开场", "简答", "AI评分"],
        difficulty="medium",
    )
    prompt = await _upsert_prompt(db, summary, owner_id=str(owner.user_id))
    await db.flush()

    quiz_unit = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=QUIZ_UNIT_NAME,
        description="先用客观题确认新人是否理解首次客户沟通的目标和结构。",
        unit_type="quiz",
        config={
            "quiz": {"pass_threshold": 30},
            "path": _path_config(
                order_index=1,
                level_title="第一关：产品定位",
                level_description="用三道客观题确认你是否知道首次客户沟通先问什么、怎么开场。",
            ),
        },
    )
    await db.flush()
    audio_unit = await _upsert_unit(
        db,
        summary,
        owner_id=str(owner.user_id),
        name=AUDIO_UNIT_NAME,
        description="上传一段客户开场录音，由转写和评分服务给出表达反馈。",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": str(prompt.prompt_id),
                "purpose": "sales_opening_demo",
                "pass_threshold": 70,
            },
            "path": _path_config(
                order_index=2,
                level_title="第二关：录音表达",
                level_description="把第一关理解转成真实销售开场表达。",
                unlock_after_unit_ids=[str(quiz_unit.unit_id)],
            ),
        },
    )
    await _replace_unit_questions(
        db,
        str(quiz_unit.unit_id),
        [
            single_choice,
            multiple_choice,
            true_false,
        ],
    )

    summary.quiz_unit_id = str(quiz_unit.unit_id)
    summary.audio_unit_id = str(audio_unit.unit_id)
    summary.learner_user_id = str(learner.user_id)
    await db.commit()
    await verify(db, summary=summary)
    return summary


async def verify(
    db: AsyncSession, *, summary: SeedSummary | None = None
) -> SeedSummary:
    summary = summary or SeedSummary()
    learner = await _first(db, select(User).where(User.email == LEARNER_EMAIL))
    if learner is None:
        raise VerifyError("demo learner does not exist")
    summary.learner_user_id = str(learner.user_id)

    category = await _first(
        db,
        select(QuestionCategory).where(
            QuestionCategory.usage_scope == "sales_trainer",
            QuestionCategory.name == CATEGORY_NAME,
        ),
    )
    if category is None:
        raise VerifyError("demo sales-trainer category does not exist")

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
    question_types = {
        str((question.scoring_criteria or {}).get("question_type"))
        for question in questions
    }
    missing_types = {
        "single_choice",
        "multiple_choice",
        "true_false",
        "short_answer",
    } - question_types
    if missing_types:
        raise VerifyError(f"missing published question types: {sorted(missing_types)}")
    adapter = QuestionBankAdapter(db)
    unsupported = [
        adapter.unsupported_reason(question)
        for question in questions
        if adapter.unsupported_reason(question) is not None
    ]
    if unsupported:
        details = [
            f"{item.question_id}:{item.reason}"
            for item in unsupported
            if item is not None
        ]
        raise VerifyError(f"unsupported question contracts: {details}")

    prompt = await _first(
        db,
        select(SalesTrainerAudioScorePrompt).where(
            SalesTrainerAudioScorePrompt.name == PROMPT_NAME,
            SalesTrainerAudioScorePrompt.status == "published",
        ),
    )
    if prompt is None:
        raise VerifyError("published demo audio scoring prompt does not exist")

    quiz_unit = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == QUIZ_UNIT_NAME,
            SalesTrainerUnit.unit_type == "quiz",
            SalesTrainerUnit.status == "published",
        ),
    )
    audio_unit = await _first(
        db,
        select(SalesTrainerUnit).where(
            SalesTrainerUnit.name == AUDIO_UNIT_NAME,
            SalesTrainerUnit.unit_type == "audio_scoring",
            SalesTrainerUnit.status == "published",
        ),
    )
    if quiz_unit is None or audio_unit is None:
        raise VerifyError("published demo quiz/audio units do not exist")
    summary.quiz_unit_id = str(quiz_unit.unit_id)
    summary.audio_unit_id = str(audio_unit.unit_id)

    paths = await SalesTrainerPathService(db).list_paths_for_user(str(learner.user_id))
    path = next((item for item in paths if item["path_key"] == PATH_KEY), None)
    if path is None:
        raise VerifyError("demo path is not returned by SalesTrainerPathService")
    if path["total_levels"] != 2:
        raise VerifyError(f"demo path expected 2 levels, got {path['total_levels']}")
    level_ids = [level["unit_id"] for level in path["levels"]]
    if level_ids != [str(quiz_unit.unit_id), str(audio_unit.unit_id)]:
        raise VerifyError("demo path levels are not ordered as expected")
    recommendation = path["goal_context"]["next_recommendation"]
    if not recommendation or not recommendation.get("target_path"):
        raise VerifyError("demo path does not expose a next recommendation")

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
        description="Seed or verify the local sales trainer goal-path demo."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify that the demo data is present and path-readable.",
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

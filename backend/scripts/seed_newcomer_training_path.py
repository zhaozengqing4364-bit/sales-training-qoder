"""Idempotent representative seed for activity-orchestrated newcomer training."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import agent.models  # noqa: E402,F401
import curriculum_practice.models  # noqa: E402,F401
import sales_trainer.models  # noqa: E402,F401
from agent.models import VoiceRuntimeProfile  # noqa: E402
from common.auth.service import get_dev_user  # noqa: E402
from common.db.models import User  # noqa: E402
from common.db.session import AsyncSessionLocal  # noqa: E402
from curriculum_practice.models import (  # noqa: E402
    LearningChapter,
    LearningContent,
    PracticeTemplate,
    QuestionCategory,
    QuestionItem,
)
from sales_trainer.models import (  # noqa: E402
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.orchestration.contracts import TrainingPathPayload  # noqa: E402
from sales_trainer.orchestration.revision_service import (  # noqa: E402
    TrainingPathRevisionService,
)
from sales_trainer.services.asset_revision_service import (  # noqa: E402
    SalesTrainerAssetRevisionService,
)

SEED_PREFIX = "newcomer-seed"


@dataclass(frozen=True, slots=True)
class SeedSummary:
    active_revision_id: str
    active_revision_no: int
    verified: bool
    created_resources: int

    def to_lines(self) -> tuple[str, ...]:
        return (
            f"active_revision_id={self.active_revision_id}",
            f"active_revision_no={self.active_revision_no}",
            f"created_resources={self.created_resources}",
            f"verified={str(self.verified).lower()}",
        )


async def seed(db: AsyncSession, *, actor: User | None = None) -> SeedSummary:
    actor = actor or await get_dev_user(db)
    path_service = TrainingPathRevisionService(db)
    active = await path_service.active_revision()
    if active is not None:
        try:
            payload = TrainingPathPayload.model_validate(active.payload_json)
        except Exception:
            payload = None
        if (
            payload is not None
            and payload.schema_version == "newcomer_training_orchestration_v1"
        ):
            return SeedSummary(
                str(active.revision_id), int(active.revision_no), True, 0
            )

    created = 0
    content_ids: dict[str, str] = {}
    paper_ids: dict[str, str] = {}
    rubric_ids: dict[str, str] = {}
    material_ids: dict[str, str] = {}
    for key, title in (
        ("product-a", "产品 A"),
        ("product-b", "产品 B"),
        ("technical", "技术基础"),
    ):
        content, was_created = await _learning_content(
            db, key=key, title=f"{title}学习资料"
        )
        created += int(was_created)
        content_ids[key] = str(content.learning_content_id)
        paper, was_created = await _paper(
            db, actor=actor, key=key, title=f"{title}小测"
        )
        created += int(was_created)
        paper_ids[key] = str(paper.paper_id)
    for key, title in (
        ("ppt", "PPT 讲解"),
        ("product-a", "产品 A 讲解"),
        ("product-b", "产品 B 讲解"),
        ("demo", "标准 Demo"),
    ):
        rubric_id = f"{SEED_PREFIX}-rubric-{key}"
        created += int(
            await _published_asset(
                db,
                actor=actor,
                resource_type="audio_scoring_rubric",
                logical_id=rubric_id,
                payload={"dimensions": ["准确性", "结构", "表达"], "max_score": 100},
            )
        )
        rubric_ids[key] = rubric_id
        material, was_created = await _material(db, key=key, title=title)
        created += int(was_created)
        material_ids[key] = str(material.material_id)

    coach_id = f"{SEED_PREFIX}-coach"
    created += int(
        await _published_asset(
            db,
            actor=actor,
            resource_type="ai_coach_profile",
            logical_id=coach_id,
            payload={
                "config": {
                    "enabled": True,
                    "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                    "min_turns": 1,
                    "max_turns": 5,
                    "mastery_threshold": 80,
                },
                "first_question": "请总结今天学习的重点。",
            },
        )
    )
    realtime = await _realtime_activity(db)
    payload = _path_payload(
        content_ids, paper_ids, rubric_ids, material_ids, coach_id, realtime
    )
    await path_service.save_draft(
        payload=payload, actor=actor, reason="播种活动编排新人训练原型"
    )
    result = await path_service.publish(actor=actor, reason="发布活动编排新人训练原型")
    await db.commit()
    verified = TrainingPathPayload.model_validate(result.revision.payload_json)
    return SeedSummary(
        str(result.revision.revision_id),
        int(result.revision.revision_no),
        verified.title == "新人训练路径",
        created,
    )


async def verify(db: AsyncSession) -> SeedSummary:
    active = await TrainingPathRevisionService(db).active_revision()
    if active is None:
        raise RuntimeError("新人训练路径尚未播种")
    payload = TrainingPathPayload.model_validate(active.payload_json)
    product_modules = payload.phases[1].modules
    if len(product_modules) != 3 or [item.title for item in product_modules] != [
        "产品 A 核心功能",
        "产品 B 核心功能",
        "标准产品 Demo",
    ]:
        raise RuntimeError("产品活动模块校验失败")
    return SeedSummary(str(active.revision_id), int(active.revision_no), True, 0)


async def _learning_content(
    db: AsyncSession, *, key: str, title: str
) -> tuple[LearningContent, bool]:
    source = f"seed://{SEED_PREFIX}/{key}"
    row = await db.scalar(
        select(LearningContent).where(LearningContent.source == source)
    )
    if row is not None:
        return row, False
    row = LearningContent(
        title=title,
        summary=f"{title}的可配置学习内容。",
        source=source,
        status="published",
        content_hash=_hash(title),
    )
    db.add(row)
    await db.flush()
    db.add(
        LearningChapter(
            learning_content_id=row.learning_content_id,
            title="核心内容",
            content=f"# {title}\n\n通过后台可继续增加章节。",
            order_index=1,
        )
    )
    await db.flush()
    return row, True


async def _paper(
    db: AsyncSession, *, actor: User, key: str, title: str
) -> tuple[SalesTrainerExamPaper, bool]:
    paper_key = f"{SEED_PREFIX}-{key}"
    row = await db.scalar(
        select(SalesTrainerExamPaper).where(
            SalesTrainerExamPaper.paper_key == paper_key
        )
    )
    if row is not None:
        return row, False
    unit = SalesTrainerUnit(
        name=title,
        unit_type="quiz",
        config={},
        status="published",
        created_by=str(actor.user_id),
        updated_by=str(actor.user_id),
    )
    db.add(unit)
    await db.flush()
    category = await db.scalar(
        select(QuestionCategory).where(QuestionCategory.name == f"{SEED_PREFIX}-{key}")
    )
    if category is None:
        category = QuestionCategory(
            name=f"{SEED_PREFIX}-{key}", usage_scope="sales_trainer"
        )
        db.add(category)
        await db.flush()
    question = QuestionItem(
        category_id=category.category_id,
        title=title,
        stem=f"关于{title}，请选择正确做法。",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "按标准流程完成"},
                {"value": "B", "label": "跳过关键步骤"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    db.add(question)
    await db.flush()
    db.add(
        SalesTrainerUnitQuestion(
            unit_id=unit.unit_id,
            question_id=question.question_id,
            order_index=1,
            points=100,
        )
    )
    row = SalesTrainerExamPaper(
        paper_key=paper_key,
        title=title,
        module_key="configurable",
        unit_id=unit.unit_id,
        pass_threshold=80,
        status="published",
        created_by=str(actor.user_id),
        updated_by=str(actor.user_id),
    )
    db.add(row)
    await db.flush()
    return row, True


async def _material(
    db: AsyncSession, *, key: str, title: str
) -> tuple[SalesTrainerMaterial, bool]:
    material_key = f"{SEED_PREFIX}-{key}"
    row = await db.scalar(
        select(SalesTrainerMaterial).where(
            SalesTrainerMaterial.material_key == material_key
        )
    )
    if row is not None:
        return row, False
    row = SalesTrainerMaterial(
        material_key=material_key,
        name=title,
        material_type="ppt_deck",
        purpose="configurable_training",
        status="published",
    )
    db.add(row)
    await db.flush()
    version = SalesTrainerMaterialVersion(
        material_id=row.material_id,
        version_label="v1",
        title=f"{title} v1",
        file_name=f"{key}.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes=1,
        storage_key=f"seed/{key}.pptx",
        file_hash=_hash(key),
        status="published",
    )
    db.add(version)
    await db.flush()
    row.current_version_id = version.version_id
    await db.flush()
    return row, True


async def _published_asset(
    db: AsyncSession,
    *,
    actor: User,
    resource_type: str,
    logical_id: str,
    payload: dict[str, object],
) -> bool:
    service = SalesTrainerAssetRevisionService(db)
    if (
        await service.active_revision(
            resource_type=resource_type, logical_id=logical_id
        )
        is not None
    ):
        return False
    await service.create_published_revision(
        resource_type=resource_type,
        logical_id=logical_id,
        payload=payload,
        actor=actor,
        change_class="semantic",
        reason="新人训练原型资源",
    )
    return True


async def _realtime_activity(db: AsyncSession) -> dict[str, str] | None:
    runtime = await db.scalar(
        select(VoiceRuntimeProfile)
        .where(
            VoiceRuntimeProfile.is_active.is_(True),
            VoiceRuntimeProfile.voice_mode == "stepfun_realtime",
        )
        .order_by(
            VoiceRuntimeProfile.is_default.desc(), VoiceRuntimeProfile.created_at.asc()
        )
    )
    if runtime is None:
        return None
    template = await db.scalar(
        select(PracticeTemplate)
        .where(
            PracticeTemplate.runtime_profile_id == runtime.id,
            PracticeTemplate.status == "published",
        )
        .order_by(PracticeTemplate.created_at.asc())
    )
    return (
        {
            "practice_template_id": str(template.template_id),
            "runtime_profile_id": str(runtime.id),
        }
        if template
        else None
    )


def _path_payload(
    content: dict[str, str],
    papers: dict[str, str],
    rubrics: dict[str, str],
    materials: dict[str, str],
    coach_id: str,
    realtime: dict[str, str] | None,
) -> TrainingPathPayload:
    def lesson(
        activity_id: str, title: str, content_id: str, order: int
    ) -> dict[str, object]:
        return {
            "activity_id": activity_id,
            "type": "lesson",
            "title": title,
            "order_index": order,
            "config": {"learning_content_id": content_id},
        }

    def quiz(
        activity_id: str, title: str, paper_id: str, order: int
    ) -> dict[str, object]:
        return {
            "activity_id": activity_id,
            "type": "quiz",
            "title": title,
            "order_index": order,
            "config": {"exam_paper_id": paper_id, "pass_score": 80},
        }

    def audio(activity_id: str, title: str, key: str, order: int) -> dict[str, object]:
        return {
            "activity_id": activity_id,
            "type": "audio_assessment",
            "title": title,
            "order_index": order,
            "config": {
                "scoring_rubric_id": rubrics[key],
                "material_id": materials[key],
                "pass_score": 75,
                "max_attempts": 3,
            },
        }

    product_a = [
        lesson("product-a-lesson", "学习产品 A", content["product-a"], 1),
        quiz("product-a-quiz", "产品 A 小测", papers["product-a"], 2),
        audio("product-a-audio", "讲解产品 A", "product-a", 3),
    ]
    product_b = [
        lesson("product-b-lesson", "学习产品 B", content["product-b"], 1),
        quiz("product-b-quiz", "产品 B 小测", papers["product-b"], 2),
        audio("product-b-audio", "讲解产品 B", "product-b", 3),
    ]
    practice = [
        {
            "activity_id": "coach-optional",
            "type": "ai_coach",
            "title": "AI 教练巩固",
            "order_index": 1,
            "required": False,
            "config": {"coach_profile_id": coach_id},
        },
        {
            "activity_id": "assignment-summary",
            "type": "assignment",
            "title": "提交学习总结",
            "order_index": 2,
            "config": {
                "submission_type": "text_or_file",
                "review_mode": "manual_review",
            },
        },
    ]
    if realtime:
        practice.append(
            {
                "activity_id": "realtime-roleplay",
                "type": "realtime_roleplay",
                "title": "StepAudio 实时对练",
                "order_index": 3,
                "config": realtime,
            }
        )
    return TrainingPathPayload.model_validate(
        {
            "title": "新人训练路径",
            "description": "所有阶段、模块与活动均可在后台配置。",
            "phases": [
                {
                    "phase_id": "onboarding",
                    "title": "入门认知",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "ppt-intro",
                            "title": "公司与方案介绍",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                audio("ppt-intro-audio", "PPT 讲解录音", "ppt", 1)
                            ],
                        }
                    ],
                },
                {
                    "phase_id": "products",
                    "title": "产品能力",
                    "order_index": 2,
                    "modules": [
                        {
                            "module_id": "product-a",
                            "title": "产品 A 核心功能",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": product_a,
                        },
                        {
                            "module_id": "product-b",
                            "title": "产品 B 核心功能",
                            "order_index": 2,
                            "completion_policy": {"mode": "all_required"},
                            "activities": product_b,
                        },
                        {
                            "module_id": "standard-demo",
                            "title": "标准产品 Demo",
                            "order_index": 3,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                audio(
                                    "standard-demo-audio", "标准 Demo 讲解", "demo", 1
                                )
                            ],
                        },
                    ],
                },
                {
                    "phase_id": "practice",
                    "title": "实战演练",
                    "order_index": 3,
                    "modules": [
                        {
                            "module_id": "technical",
                            "title": "技术基础",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                lesson(
                                    "technical-lesson",
                                    "技术资料学习",
                                    content["technical"],
                                    1,
                                ),
                                quiz(
                                    "technical-quiz",
                                    "技术基础小测",
                                    papers["technical"],
                                    2,
                                ),
                            ],
                        },
                        {
                            "module_id": "practice-loop",
                            "title": "综合实战",
                            "order_index": 2,
                            "completion_policy": {"mode": "all_required"},
                            "activities": practice,
                        },
                    ],
                },
            ],
        }
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _run(*, verify_only: bool) -> SeedSummary:
    async with AsyncSessionLocal() as db:
        return await verify(db) if verify_only else await seed(db)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed activity-orchestrated newcomer training."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the active seed without creating or updating records.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    summary = asyncio.run(_run(verify_only=bool(args.verify_only)))
    print("\n".join(summary.to_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

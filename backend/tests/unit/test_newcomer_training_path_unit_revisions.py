from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import (
    SalesTrainerUnitCreate,
    SalesTrainerUnitUpdate,
    UnitQuestionBinding,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.unit_revision_service import (
    UnitRevisionService,
    UnitRevisionServiceError,
)
from sales_trainer.services.unit_service import UnitService


def _admin() -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"unit-revision-admin-{suffix}",
        name="Unit Revision Admin",
        email=f"unit-revision-admin-{suffix}@example.com",
        role="admin",
    )


def _question(question_id: str, *, category_id: str, title: str) -> QuestionItem:
    return QuestionItem(
        question_id=question_id,
        category_id=category_id,
        title=title,
        stem=f"{title} 的答案是什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "正确"},
                {"value": "B", "label": "错误"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )


@pytest.mark.asyncio
async def test_should_save_published_unit_update_as_future_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    category = QuestionCategory(
        category_id="unit-revision-category",
        name="训练单元修订题库",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question("unit-revision-first", category_id=category.category_id, title="旧题")
    second = _question("unit-revision-second", category_id=category.category_id, title="新题")
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="商务技巧旧单元",
            description="旧说明",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    initial_revision = await _latest_unit_revision(test_db, str(unit.unit_id))

    updated = await service.update_unit(
        unit,
        SalesTrainerUnitUpdate(
            name="商务技巧新单元",
            description="新说明",
            config={"quiz": {"pass_threshold": 12}},
            questions=[
                UnitQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )

    current_questions = await service.get_unit_questions(str(unit.unit_id))
    working_revision = await _latest_unit_revision(
        test_db,
        str(unit.unit_id),
        status="working",
    )
    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_unit",
        target_id=str(unit.unit_id),
    )
    revision_log = next(log for log in logs if log.action == "unit_revision_saved")

    assert updated.name == "商务技巧旧单元"
    assert updated.description == "旧说明"
    assert updated.config["quiz"]["pass_threshold"] == 10
    assert [item.question_id for item in current_questions] == [first.question_id]
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert working_revision.change_class == "scoring_high_risk"
    assert working_revision.payload_json["name"] == "商务技巧新单元"
    assert working_revision.payload_json["description"] == "新说明"
    assert working_revision.payload_json["config"]["quiz"]["pass_threshold"] == 12
    assert working_revision.payload_json["questions"][0]["question_id"] == second.question_id
    assert revision_log.metadata_json["future_only"] is True
    assert revision_log.metadata_json["working_revision_id"] == working_revision.revision_id
    assert revision_log.metadata_json["source_revision_id"] == initial_revision.revision_id


@pytest.mark.asyncio
async def test_should_publish_saved_unit_revision_for_future_learners(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    category = QuestionCategory(
        category_id="unit-revision-publish-category",
        name="训练单元发布题库",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question("unit-revision-publish-first", category_id=category.category_id, title="旧题")
    second = _question("unit-revision-publish-second", category_id=category.category_id, title="新题")
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="发布前单元",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    await service.update_unit(
        unit,
        SalesTrainerUnitUpdate(
            name="发布后单元",
            config={"quiz": {"pass_threshold": 12}},
            questions=[
                UnitQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )
    working_revision = await _latest_unit_revision(
        test_db,
        str(unit.unit_id),
        status="working",
    )

    published = await service.publish_unit(unit, actor=admin)

    current_questions = await service.get_unit_questions(str(unit.unit_id))
    published_revision = await _latest_unit_revision(test_db, str(unit.unit_id))
    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_unit",
        target_id=str(unit.unit_id),
    )
    revision_log = next(log for log in logs if log.action == "unit_revision_published")

    assert published.name == "发布后单元"
    assert published.config["quiz"]["pass_threshold"] == 12
    assert [item.question_id for item in current_questions] == [second.question_id]
    assert published_revision.revision_id == working_revision.revision_id
    assert published_revision.status == "published"
    assert revision_log.metadata_json["after_revision_id"] == working_revision.revision_id
    assert revision_log.metadata_json["future_only"] is True


@pytest.mark.asyncio
async def test_should_list_unit_revision_history_with_active_state(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    category = QuestionCategory(
        category_id="unit-revision-history-category",
        name="训练单元历史题库",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question("unit-revision-history-first", category_id=category.category_id, title="旧题")
    second = _question("unit-revision-history-second", category_id=category.category_id, title="新题")
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="历史版本单元",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    await service.update_unit(
        unit,
        SalesTrainerUnitUpdate(
            name="历史版本单元新版",
            config={"quiz": {"pass_threshold": 12}},
            questions=[
                UnitQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)

    revisions = await UnitRevisionService(test_db).list_revisions(str(unit.unit_id))

    assert [item["revision_no"] for item in revisions] == [2, 1]
    assert revisions[0]["is_active"] is True
    assert revisions[0]["is_working"] is False
    assert revisions[0]["title"] == "历史版本单元新版"
    assert revisions[0]["question_count"] == 1
    assert revisions[1]["is_active"] is False
    assert revisions[1]["title"] == "历史版本单元"


@pytest.mark.asyncio
async def test_should_roll_back_unit_revision_for_future_learners(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    category = QuestionCategory(
        category_id="unit-revision-rollback-category",
        name="训练单元回滚题库",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question("unit-revision-rollback-first", category_id=category.category_id, title="旧题")
    second = _question("unit-revision-rollback-second", category_id=category.category_id, title="新题")
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="回滚前单元",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    initial_revision = await _latest_unit_revision(test_db, str(unit.unit_id))
    await service.update_unit(
        unit,
        SalesTrainerUnitUpdate(
            name="回滚前单元新版",
            config={"quiz": {"pass_threshold": 12}},
            questions=[
                UnitQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    active_before_rollback = await _latest_unit_revision(test_db, str(unit.unit_id))

    rolled_back = await UnitRevisionService(test_db).rollback_to_revision(
        unit,
        target_revision_id=str(initial_revision.revision_id),
        reason="恢复试运行前的训练单元配置",
        actor=admin,
    )

    current_questions = await service.get_unit_questions(str(unit.unit_id))
    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_unit",
        target_id=str(unit.unit_id),
    )
    revision_log = next(log for log in logs if log.action == "unit_revision_rolled_back")

    assert rolled_back.name == "回滚前单元"
    assert rolled_back.config["quiz"]["pass_threshold"] == 10
    assert [item.question_id for item in current_questions] == [first.question_id]
    assert revision_log.metadata_json["before_revision_id"] == active_before_rollback.revision_id
    assert revision_log.metadata_json["after_revision_id"] == initial_revision.revision_id
    assert revision_log.metadata_json["reason"] == "恢复试运行前的训练单元配置"
    assert revision_log.metadata_json["future_only"] is True


@pytest.mark.asyncio
async def test_should_reject_rollback_to_working_unit_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    category = QuestionCategory(
        category_id="unit-revision-working-rollback-category",
        name="训练单元待发布回滚题库",
        order_index=1,
        usage_scope="sales_trainer",
    )
    first = _question("unit-revision-working-first", category_id=category.category_id, title="旧题")
    second = _question("unit-revision-working-second", category_id=category.category_id, title="新题")
    test_db.add_all([admin, category, first, second])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="待发布回滚单元",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=first.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_unit(unit, actor=admin)
    await service.update_unit(
        unit,
        SalesTrainerUnitUpdate(
            name="待发布回滚单元新版",
            questions=[
                UnitQuestionBinding(
                    question_id=second.question_id,
                    order_index=1,
                    points=12,
                )
            ],
        ),
        actor=admin,
    )
    working_revision = await _latest_unit_revision(
        test_db,
        str(unit.unit_id),
        status="working",
    )

    with pytest.raises(UnitRevisionServiceError) as exc_info:
        await UnitRevisionService(test_db).rollback_to_revision(
            unit,
            target_revision_id=str(working_revision.revision_id),
            reason="不能把待发布修订当成回滚目标",
            actor=admin,
        )

    assert exc_info.value.code == "[ASSET_REVISION_NOT_ROLLBACKABLE]"


async def _latest_unit_revision(
    test_db: AsyncSession,
    unit_id: str,
    *,
    status: str = "published",
) -> SalesTrainerAssetRevision:
    result = await test_db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "sales_trainer_unit",
            SalesTrainerAssetRevision.logical_id == unit_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
        .limit(1)
    )
    return result.scalar_one()

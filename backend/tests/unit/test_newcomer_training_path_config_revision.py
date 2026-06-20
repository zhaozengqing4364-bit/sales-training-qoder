from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import LearningContent
from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerOperationLog,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.path_service import SalesTrainerPathService


def _admin() -> User:
    return User(
        user_id="newcomer-path-config-admin",
        wechat_user_id="newcomer-path-config-admin",
        name="新人路径配置管理员",
        email="newcomer-path-config-admin@example.com",
        role="admin",
    )


BUSINESS_CONTENT_ID = "path-config-business-content"
BUSINESS_PAPER_ID = "path-config-business-paper"


def _unit(unit_id: str, *, title: str, order_index: int = 1) -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=unit_id,
        name=title,
        description=f"{title}说明",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "path_title": "新人训练路径",
                "goal_title": "完成新人训练",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": order_index,
                "completion_rule": "submitted",
            }
        },
    )


def _path_unit(
    unit_id: str,
    *,
    title: str,
    module_key: str,
    module_type: str = "article_exam",
    order_index: int,
    updated_at: datetime,
    enabled: bool = True,
    audio_purpose: str | None = None,
    duration_minutes: int | None = None,
) -> SalesTrainerUnit:
    unit = _unit(unit_id, title=title, order_index=order_index)
    unit.config["path"]["module_key"] = module_key
    unit.config["path"]["module_type"] = module_type
    unit.config["path"]["enabled"] = enabled
    unit.updated_at = updated_at
    if module_type in {"audio_scoring", "audio_scoring_group"}:
        unit.unit_type = "audio_scoring"
    if audio_purpose is not None:
        unit.config["audio"] = {"purpose": audio_purpose}
    if duration_minutes is not None:
        unit.config["duration_minutes"] = duration_minutes
    return unit


def _payload(*, unit_id: str, title: str) -> NewcomerPathConfigSaveRequest:
    return NewcomerPathConfigSaveRequest(
        path_key="newcomer_training_path_v1",
        title="新人训练路径",
        goal_title="完成新人训练",
        reason="配置商务技巧模块",
        modules=[
            NewcomerPathModuleConfig(
                module_key="business_skills",
                module_type="article_exam",
                enabled=True,
                order_index=1,
                title=title,
                description=f"{title}说明",
                target_unit_id=unit_id,
                learning_content_id=BUSINESS_CONTENT_ID,
                exam_paper_id=BUSINESS_PAPER_ID,
                completion_rule="submitted",
                primary_action_label="开始学习",
            )
        ],
    )


def _business_assets(admin: User, unit: SalesTrainerUnit) -> tuple[LearningContent, SalesTrainerExamPaper]:
    return (
        LearningContent(
            learning_content_id=BUSINESS_CONTENT_ID,
            title="商务技巧学习内容",
            summary="发布配置测试用学习内容。",
            owner="新人训练路径",
            source="unit_test",
            status="published",
            created_by=str(admin.user_id),
            updated_by=str(admin.user_id),
        ),
        SalesTrainerExamPaper(
            paper_id=BUSINESS_PAPER_ID,
            paper_key=f"{unit.unit_id}-paper",
            title="商务技巧考卷",
            module_key="business_skills",
            unit_id=unit.unit_id,
            pass_threshold=60,
            status="published",
            created_by=str(admin.user_id),
            updated_by=str(admin.user_id),
        ),
    )


@pytest.mark.asyncio
async def test_should_backfill_path_config_from_published_unit_when_no_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    unit = _unit("path-config-backfill-unit", title="商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()

    config = await SalesTrainerPathConfigService(test_db).get_config()

    assert config["source"] == "unit_backfill"
    assert config["active_revision_id"] is None
    assert config["path"]["title"] == "新人训练路径"
    assert config["path"]["modules"][0]["title"] == "商务技巧"
    assert config["path"]["modules"][0]["target_unit_id"] == unit.unit_id


@pytest.mark.asyncio
async def test_should_backfill_one_path_module_per_business_stage(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    old_business = _path_unit(
        "path-backfill-business-old",
        title="商务技巧旧单元",
        module_key="business_skills",
        order_index=2,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    current_business = _path_unit(
        "path-backfill-business-current",
        title="商务技巧当前单元",
        module_key="business_skills",
        order_index=2,
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    ppt_unit = _path_unit(
        "path-backfill-ppt",
        title="PPT 讲解录音",
        module_key="ppt_explain",
        module_type="audio_scoring",
        order_index=1,
        updated_at=datetime(2026, 1, 15, tzinfo=UTC),
        audio_purpose="ppt_pitch",
    )
    elevator_unit = _path_unit(
        "path-backfill-elevator-10",
        title="电梯演讲 · 10 分钟",
        module_key="pyramid_speech",
        module_type="audio_scoring_group",
        order_index=3,
        updated_at=datetime(2026, 1, 20, tzinfo=UTC),
        audio_purpose="pyramid_speech",
        duration_minutes=10,
    )
    elevator_20 = _path_unit(
        "path-backfill-elevator-20",
        title="电梯演讲 · 20 分钟",
        module_key="elevator_pitch",
        module_type="audio_scoring_group",
        order_index=3,
        updated_at=datetime(2026, 1, 21, tzinfo=UTC),
        audio_purpose="elevator_pitch",
        duration_minutes=20,
    )
    elevator_30 = _path_unit(
        "path-backfill-elevator-30",
        title="电梯演讲 · 30 分钟",
        module_key="elevator_pitch",
        module_type="audio_scoring_group",
        order_index=3,
        updated_at=datetime(2026, 1, 22, tzinfo=UTC),
        audio_purpose="elevator_pitch",
        duration_minutes=30,
    )
    realtime_unit = _path_unit(
        "path-backfill-realtime",
        title="实时对练占位",
        module_key="realtime_placeholder",
        module_type="realtime_placeholder",
        order_index=4,
        updated_at=datetime(2026, 1, 20, tzinfo=UTC),
        enabled=False,
    )
    uuid_noise = _path_unit(
        "path-backfill-uuid-noise",
        title="金字塔演讲 · 10 分钟",
        module_key="94849c04-2674-4796-be76-d3e901baa41e",
        module_type="audio_scoring",
        order_index=5,
        updated_at=datetime(2026, 2, 15, tzinfo=UTC),
        audio_purpose="pyramid_speech_10m",
    )
    test_db.add_all([
        admin,
        old_business,
        current_business,
        ppt_unit,
        elevator_unit,
        elevator_20,
        elevator_30,
        realtime_unit,
        uuid_noise,
    ])
    await test_db.commit()

    config = await SalesTrainerPathConfigService(test_db).get_config()

    modules = config["path"]["modules"]
    assert [module["module_key"] for module in modules] == [
        "ppt_explanation",
        "business_skills",
        "elevator_pitch",
        "realtime_roleplay_placeholder",
    ]
    assert modules[1]["target_unit_id"] == current_business.unit_id
    assert modules[1]["title"] == "商务技巧当前单元"
    assert modules[2]["target_unit_id"] == elevator_30.unit_id
    assert [
        option["duration_minutes"]
        for option in modules[2]["duration_options"]
    ] == [10, 20, 30]
    assert modules[3]["target_unit_id"] == realtime_unit.unit_id
    assert modules[3]["enabled"] is False


@pytest.mark.asyncio
async def test_should_keep_learner_path_on_active_revision_until_working_is_published(
    test_db: AsyncSession,
    ) -> None:
    admin = _admin()
    unit = _unit("path-config-working-unit", title="商务技巧旧版")
    test_db.add_all([admin, unit, *_business_assets(admin, unit)])
    await test_db.commit()

    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(_payload(unit_id=unit.unit_id, title="商务技巧新版"), actor=admin)

    before_publish = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(admin.user_id)
    )
    assert before_publish[0]["levels"][0]["level_title"] == "商务技巧旧版"

    await service.publish_config(actor=admin, reason="新版商务技巧路径生效")
    after_publish = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(admin.user_id)
    )

    assert after_publish[0]["levels"][0]["level_title"] == "商务技巧新版"


@pytest.mark.asyncio
async def test_should_expose_active_revision_module_identity_to_learner_path(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    unit = _unit("path-config-module-identity-unit", title="旧单元配置")
    unit.config["path"]["module_key"] = "ppt_explanation"
    unit.config["path"]["module_type"] = "audio_scoring"
    test_db.add_all([admin, unit, *_business_assets(admin, unit)])
    await test_db.commit()

    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(
        _payload(unit_id=unit.unit_id, title="商务技巧路径配置"),
        actor=admin,
    )
    await service.publish_config(actor=admin, reason="路径 active revision 生效")

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(str(admin.user_id))
    level = paths[0]["levels"][0]

    assert paths[0]["path_revision_id"] is not None
    assert paths[0]["path_revision_no"] == 1
    assert level["module_key"] == "business_skills"
    assert level["module_type"] == "article_exam"
    assert level["target_path"] == "/sales-trainer/business-skills"


@pytest.mark.asyncio
async def test_should_rollback_path_config_future_only_and_write_audit_log(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    unit = _unit("path-config-rollback-unit", title="商务技巧原始")
    test_db.add_all([admin, unit, *_business_assets(admin, unit)])
    await test_db.commit()
    service = SalesTrainerPathConfigService(test_db)

    await service.save_config(_payload(unit_id=unit.unit_id, title="商务技巧第一版"), actor=admin)
    first_publish = await service.publish_config(actor=admin, reason="第一版生效")
    await service.save_config(_payload(unit_id=unit.unit_id, title="商务技巧第二版"), actor=admin)
    await service.publish_config(actor=admin, reason="第二版生效")

    before_rollback = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(admin.user_id)
    )
    assert before_rollback[0]["levels"][0]["level_title"] == "商务技巧第二版"

    await service.rollback_config(
        revision_id=str(first_publish.revision.revision_id),
        actor=admin,
        reason="回滚到第一版",
    )
    after_rollback = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(admin.user_id)
    )

    logs = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action == "newcomer_path_config.rollback"
        )
    )
    rollback_log = logs.scalar_one()

    assert after_rollback[0]["levels"][0]["level_title"] == "商务技巧第一版"
    assert rollback_log.metadata_json["reason"] == "回滚到第一版"
    assert rollback_log.metadata_json["after_revision_id"] == str(
        first_publish.revision.revision_id
    )

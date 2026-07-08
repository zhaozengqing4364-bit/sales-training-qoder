from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PromptTemplate, User
from curriculum_practice.models import LearningContent
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerOperationLog,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    NewcomerPathConfigResponse,
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    SalesTrainerPathConfigError,
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
BUSINESS_AI_COACH_PROMPT_ID = "11111111-1111-1111-1111-111111111111"


def _ai_coach_config() -> dict[str, object]:
    return {
        "enabled": True,
        "coach_mode": "mixed_drill",
        "allowed_interaction_types": ["single_choice", "multiple_choice"],
        "prompt_template_id": BUSINESS_AI_COACH_PROMPT_ID,
        "prompt_revision_id": None,
        "prompt_contract_hash": None,
        "scoring_prompt_template_id": None,
        "scoring_prompt_revision_id": None,
        "scoring_contract_hash": None,
        "min_turns": 3,
        "max_turns": 10,
        "mastery_threshold": 90,
        "output_schema_version": "ai_coach_interaction_v1",
        "generation_model": None,
        "scoring_model": None,
        "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
        "failure_behavior": "skip_turn",
    }


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
                ai_coach=_ai_coach_config(),
                completion_rule="submitted",
                primary_action_label="开始学习",
            )
        ],
    )


def _payload_from_modules(
    modules: list[dict[str, object]],
    *,
    path_key: str = "newcomer_training_path_v1",
    enabled: bool = True,
) -> NewcomerPathConfigSaveRequest:
    return NewcomerPathConfigSaveRequest.model_validate(
        {
            "path_key": path_key,
            "title": "新人训练路径",
            "goal_title": "完成新人训练",
            "enabled": enabled,
            "reason": "校验新人路径配置",
            "modules": modules,
        }
    )


def _realtime_binding(*, ready: bool = True) -> dict[str, object]:
    return {
        "binding_key": "newcomer_realtime_roleplay_v1",
        "runtime_owner": "training_runtime",
        "runtime_descriptor_id": "newcomer-realtime-runtime",
        "scenario_key": "newcomer-realtime-roleplay",
        "runtime_config_revision_id": "runtime-config-rev-1",
        "provider_readiness_snapshot": {
            "provider": "mock",
            "ready": ready,
            "checked_at": "2026-06-27T00:00:00Z",
            "config_revision_id": "runtime-config-rev-1",
            "failure_code": None if ready else "[MOCK_PROVIDER_NOT_READY]",
            "failure_message": None if ready else "mock provider not ready",
        },
        "permission_policy": {
            "learner_enter": "sales_trainer.enter_realtime",
            "admin_configure": "sales_trainer.manage_modules",
            "admin_provider_health": "sales_trainer.view_settings",
        },
        "failure_policy": {
            "terminal_codes": ["CONFIG_INVALID"],
            "transient_codes": ["PROVIDER_TIMEOUT"],
            "voluntary_codes": ["USER_CANCELLED"],
            "terminal_retry_allowed": False,
        },
        "rollback_policy": {
            "rollback_via_active_revision": True,
            "disable_module_on_invalid_binding": True,
            "fallback_to_placeholder": False,
        },
    }


def _business_assets(
    admin: User, unit: SalesTrainerUnit
) -> tuple[LearningContent, SalesTrainerExamPaper, PromptTemplate]:
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
        PromptTemplate(
            id=BUSINESS_AI_COACH_PROMPT_ID,
            name="商务技巧 AI 教练对话生成",
            prompt_type="stage",
            business_purpose=PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION,
            category="sales_trainer_ai_coach",
            template="请根据 {{ module_key }} 和 {{ coach_mode }} 生成教练回复。",
            variables=["module_key", "coach_mode"],
            is_active=True,
            is_default=False,
            is_system=False,
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

    assert config["source"] == "legacy_migration_snapshot"
    assert config["fallback_reason"] == "active_revision_missing"
    assert config["legacy_snapshot_only"] is True
    assert config["diagnostics"]["fallback_applied"] is True
    assert config["diagnostics"]["fallback_reason"] == "active_revision_missing"
    assert config["management_entry"] == "/admin/newcomer-training/path-config"
    assert config["permission"] == "sales_trainer.manage_modules"
    assert config["active_revision_id"] is None
    assert config["active_revision_snapshot"] is None
    assert config["path"]["title"] == "新人训练路径"
    assert config["path"]["modules"][0]["title"] == "商务技巧"
    assert config["path"]["modules"][0]["target_unit_id"] == unit.unit_id


@pytest.mark.asyncio
async def test_should_validate_path_config_diagnostics_contract(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    unit = _unit("path-config-diagnostics-unit", title="商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()

    config = await SalesTrainerPathConfigService(test_db).get_config()

    validated = NewcomerPathConfigResponse.model_validate(config)
    assert validated.diagnostics.fallback_applied is True
    assert validated.diagnostics.permission_policy.publish == (
        "sales_trainer.manage_modules"
    )
    assert validated.diagnostics.high_risk_actions.publish.preview_endpoint == (
        "/api/v1/admin/newcomer-training/path-config/publish/preview"
    )

    invalid_config = dict(config)
    invalid_config["diagnostics"] = dict(config["diagnostics"])
    invalid_config["diagnostics"].pop("high_risk_actions")

    with pytest.raises(ValidationError):
        NewcomerPathConfigResponse.model_validate(invalid_config)


@pytest.mark.asyncio
async def test_should_expose_legacy_active_path_key_as_canonical_for_management(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    payload = _payload_from_modules(
        [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 1,
                "title": "商务礼仪规范",
                "completion_rule": "submitted",
            }
        ],
        path_key="new_seller_modules_v1",
    )
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload.model_dump(mode="json", exclude={"reason"}),
        actor=admin,
        change_class="semantic",
        reason="模拟旧 active revision",
    )
    await test_db.commit()

    config = await SalesTrainerPathConfigService(test_db).get_config()

    assert config["source"] == "active_revision"
    assert config["legacy_snapshot_only"] is False
    assert config["path"]["path_key"] == NEWCOMER_PATH_LOGICAL_ID
    assert (
        config["active_revision_snapshot"]["payload"]["path_key"]
        == "new_seller_modules_v1"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code", "expected_status", "message_fragment"),
    [
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "business_skills",
                        "module_type": "article_exam",
                        "enabled": True,
                        "order_index": 1,
                        "title": "商务技巧",
                    }
                ],
                path_key="new_seller_modules_v1",
            ),
            "[NEWCOMER_PATH_CONFIG_ALIAS_READ_ONLY]",
            409,
            "兼容路径标识只允许读取",
        ),
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "business_skills",
                        "module_type": "article_exam",
                        "enabled": True,
                        "order_index": 1,
                        "title": "商务技巧 1",
                    },
                    {
                        "module_key": "business_skills",
                        "module_type": "article_exam",
                        "enabled": True,
                        "order_index": 2,
                        "title": "商务技巧 2",
                    },
                ]
            ),
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            422,
            "重复 module_key",
        ),
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "ppt_explanation",
                        "module_type": "audio_scoring",
                        "enabled": True,
                        "order_index": 1,
                        "title": "PPT 讲解",
                    },
                    {
                        "module_key": "business_skills",
                        "module_type": "article_exam",
                        "enabled": True,
                        "order_index": 1,
                        "title": "商务技巧",
                    },
                ]
            ),
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            422,
            "重复 order_index",
        ),
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "pyramid_speech",
                        "module_type": "audio_scoring_group",
                        "enabled": True,
                        "order_index": 1,
                        "title": "电梯演讲",
                    }
                ]
            ),
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            422,
            "兼容 module_key",
        ),
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "business_skills",
                        "module_type": "audio_scoring",
                        "enabled": True,
                        "order_index": 1,
                        "title": "商务技巧",
                    }
                ]
            ),
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            422,
            "必须使用 module_type=article_exam",
        ),
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "realtime_roleplay_placeholder",
                        "module_type": "realtime_roleplay",
                        "enabled": False,
                        "order_index": 1,
                        "title": "实时对练占位",
                    }
                ]
            ),
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            422,
            "必须使用 module_type=realtime_placeholder",
        ),
        (
            _payload_from_modules(
                [
                    {
                        "module_key": "business_skills",
                        "module_type": "article_exam",
                        "enabled": True,
                        "order_index": 1,
                        "title": "商务技巧",
                    }
                ],
                enabled=False,
            ),
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            422,
            "enabled=false",
        ),
    ],
)
async def test_should_reject_invalid_path_payload_on_save(
    test_db: AsyncSession,
    payload: NewcomerPathConfigSaveRequest,
    expected_code: str,
    expected_status: int,
    message_fragment: str,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    with pytest.raises(SalesTrainerPathConfigError) as exc_info:
        await SalesTrainerPathConfigService(test_db).save_config(payload, actor=admin)

    assert exc_info.value.code == expected_code
    assert exc_info.value.status_code == expected_status
    assert message_fragment in exc_info.value.message


@pytest.mark.asyncio
async def test_should_reject_enabled_realtime_roleplay_without_runtime_binding_on_publish(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(
        _payload_from_modules(
            [
                {
                    "module_key": "realtime_roleplay",
                    "module_type": "realtime_roleplay",
                    "enabled": True,
                    "order_index": 1,
                    "title": "实时对练",
                    "completion_rule": "submitted",
                }
            ]
        ),
        actor=admin,
    )

    with pytest.raises(SalesTrainerPathConfigError) as exc_info:
        await service.publish_config(actor=admin, reason="启用实时对练")

    assert exc_info.value.code == "[NEWCOMER_REALTIME_BINDING_INVALID]"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_should_reject_realtime_roleplay_when_provider_is_not_ready(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(
        _payload_from_modules(
            [
                {
                    "module_key": "realtime_roleplay",
                    "module_type": "realtime_roleplay",
                    "enabled": True,
                    "order_index": 1,
                    "title": "实时对练",
                    "completion_rule": "submitted",
                    "runtime_binding": _realtime_binding(ready=False),
                }
            ]
        ),
        actor=admin,
    )

    with pytest.raises(SalesTrainerPathConfigError) as exc_info:
        await service.publish_config(actor=admin, reason="启用实时对练")

    assert exc_info.value.code == "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]"
    assert exc_info.value.status_code == 503
    assert "mock provider not ready" in exc_info.value.message


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
    assert before_publish == []

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
    publish_result = await service.publish_config(actor=admin, reason="路径 active revision 生效")
    config = await service.get_config()

    paths = await SalesTrainerPathService(test_db).list_paths_for_user(str(admin.user_id))
    level = paths[0]["levels"][0]

    assert config["source"] == "active_revision"
    assert config["fallback_reason"] is None
    assert config["legacy_snapshot_only"] is False
    assert config["diagnostics"]["fallback_applied"] is False
    assert config["diagnostics"]["fallback_reason"] is None
    assert config["active_revision_snapshot"]["revision_id"] == str(
        publish_result.revision.revision_id
    )
    assert config["active_revision_snapshot"]["payload"]["modules"][0]["module_key"] == (
        "business_skills"
    )
    assert paths[0]["path_revision_id"] is not None
    assert paths[0]["path_revision_no"] == 1
    assert level["module_key"] == "business_skills"
    assert level["module_type"] == "article_exam"
    assert level["target_path"] == "/sales-trainer/business-skills"


@pytest.mark.asyncio
async def test_publish_preview_projects_realtime_provider_readiness(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()

    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(
        _payload_from_modules(
            [
                {
                    "module_key": "realtime_roleplay",
                    "module_type": "realtime_roleplay",
                    "enabled": True,
                    "order_index": 1,
                    "title": "实时对练",
                    "completion_rule": "submitted",
                    "runtime_binding": _realtime_binding(ready=True),
                }
            ]
        ),
        actor=admin,
    )

    preview = await service.publish_preview()

    readiness = preview["impact_scope"]["realtime_provider_readiness"]
    assert readiness == [
        {
            "module_key": "realtime_roleplay",
            "module_type": "realtime_roleplay",
            "title": "实时对练",
            "enabled": True,
            "runtime_descriptor_id": "newcomer-realtime-runtime",
            "provider_readiness_snapshot": {
                "provider": "mock",
                "ready": True,
                "checked_at": "2026-06-27T00:00:00Z",
                "config_revision_id": "runtime-config-rev-1",
                "failure_code": None,
                "failure_message": None,
            },
            "ready": True,
            "failure_code": None,
            "failure_message": None,
        }
    ]


@pytest.mark.asyncio
async def test_should_require_working_revision_before_publish(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    unit = _unit("path-config-no-working-unit", title="商务技巧")
    test_db.add_all([admin, unit, *_business_assets(admin, unit)])
    await test_db.commit()

    with pytest.raises(SalesTrainerPathConfigError) as exc_info:
        await SalesTrainerPathConfigService(test_db).publish_config(
            actor=admin,
            reason="试图直接发布 backfill 路径",
        )

    assert exc_info.value.code == "[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]"
    assert exc_info.value.status_code == 409


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

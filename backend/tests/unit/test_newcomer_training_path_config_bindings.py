from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import NewcomerPathConfigSaveRequest
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


def _admin() -> User:
    return User(
        user_id="path-config-binding-admin",
        wechat_user_id="path-config-binding-admin",
        name="新人路径配置管理员",
        email="path-config-binding-admin@example.com",
        role="admin",
    )


def _audio_unit() -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id="ppt-audio-unit",
        name="PPT 讲解录音",
        description="上传 PPT 讲解录音",
        unit_type="audio_scoring",
        status="published",
        config={
            "audio": {
                "purpose": "ppt_pitch",
                "scoring_prompt_id": "prompt-from-unit",
            },
            "materials": {
                "bindings": [
                    {
                        "material_id": "material-from-unit",
                        "locked_version_id": "version-from-unit",
                        "version_policy": "locked_version",
                    }
                ]
            },
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "path_title": "新人训练路径",
                "module_key": "ppt_explanation",
                "module_type": "audio_scoring",
                "order_index": 1,
            },
        },
    )


@pytest.mark.asyncio
async def test_should_backfill_audio_module_bindings_from_unit_config(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    unit = _audio_unit()
    test_db.add_all([admin, unit])
    await test_db.commit()

    config = await SalesTrainerPathConfigService(test_db).get_config()

    module = config["path"]["modules"][0]
    assert module["module_key"] == "ppt_explanation"
    assert module["scoring_prompt_id"] == "prompt-from-unit"
    assert module["material_id"] == "material-from-unit"
    assert module["material_version_id"] == "version-from-unit"


@pytest.mark.asyncio
async def test_should_save_audio_module_bindings_as_path_revision(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    payload = NewcomerPathConfigSaveRequest.model_validate(
        {
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "goal_title": "完成新人训练",
            "reason": "绑定 PPT 材料和录音评分标准",
            "modules": [
                {
                    "module_key": "ppt_explanation",
                    "module_type": "audio_scoring",
                    "enabled": True,
                    "order_index": 1,
                    "title": "PPT 讲解录音",
                    "description": "上传 PPT 讲解录音",
                    "target_unit_id": "ppt-audio-unit",
                    "material_id": "material-from-path",
                    "material_version_id": "version-from-path",
                    "scoring_prompt_id": "prompt-from-path",
                    "completion_rule": "scored",
                }
            ],
        }
    )

    revision = await SalesTrainerPathConfigService(test_db).save_config(
        payload,
        actor=admin,
    )

    module = revision.payload_json["modules"][0]
    assert revision.change_class == "binding"
    assert module["scoring_prompt_id"] == "prompt-from-path"
    assert module["material_id"] == "material-from-path"
    assert module["material_version_id"] == "version-from-path"

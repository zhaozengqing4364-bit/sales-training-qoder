from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.schemas import NewcomerPathConfigSaveRequest
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
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


@pytest.mark.asyncio
async def test_should_save_company_product_demo_as_audio_scenario_module(
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
            "reason": "新增公司产品 Demo 讲解场景",
            "modules": [
                {
                    "module_key": "company_product_demo",
                    "scenario_key": "company_product_demo",
                    "module_type": "audio_scoring",
                    "enabled": True,
                    "order_index": 2,
                    "title": "公司产品 Demo",
                    "description": "上传产品 Demo 讲解录音",
                    "target_unit_id": "company-demo-audio-unit",
                    "material_id": "product-demo-material",
                    "material_version_id": "product-demo-version",
                    "scoring_prompt_id": "product-demo-prompt",
                    "completion_rule": "passed",
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
    assert module["module_key"] == "company_product_demo"
    assert module["scenario_key"] == "company_product_demo"
    assert module["module_type"] == "audio_scoring"


@pytest.mark.asyncio
async def test_should_reject_audio_unit_when_scenario_does_not_match_module(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="公司产品 Demo 评分",
        purpose="company_product_demo",
        system_prompt="你是评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"product-demo-material-{uuid.uuid4().hex[:8]}",
        name="产品资料",
        material_type="script",
        purpose="company_product_demo",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v1",
        title="产品资料 v1",
        file_name="demo.pdf",
        content_type="application/pdf",
        file_size_bytes=100,
        storage_key="/tmp/demo.pdf",
        status="published",
        created_by=admin.user_id,
        published_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    ppt_unit = _audio_unit()
    test_db.add_all([admin, prompt, material, version, ppt_unit])
    await test_db.commit()
    payload = NewcomerPathConfigSaveRequest.model_validate(
        {
            "path_key": "newcomer_training_path_v1",
            "title": "新人训练路径",
            "goal_title": "完成新人训练",
            "reason": "错误绑定 PPT 单元到产品 Demo",
            "modules": [
                {
                    "module_key": "company_product_demo",
                    "scenario_key": "company_product_demo",
                    "module_type": "audio_scoring",
                    "enabled": True,
                    "order_index": 2,
                    "title": "公司产品 Demo",
                    "target_unit_id": ppt_unit.unit_id,
                    "material_id": material.material_id,
                    "material_version_id": version.version_id,
                    "scoring_prompt_id": prompt.prompt_id,
                    "completion_rule": "passed",
                }
            ],
        }
    )
    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(payload, actor=admin)

    with pytest.raises(SalesTrainerPathConfigError) as exc:
        await service.publish_config(actor=admin, reason="发布错误绑定")

    assert exc.value.code == "[NEWCOMER_MODULE_CONFIG_INVALID]"
    assert "公司产品 Demo场景" in exc.value.message

from __future__ import annotations

import pytest

from sales_trainer.models import SalesTrainerMaterial, SalesTrainerMaterialVersion
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.journey_service import NewcomerJourneyService
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)


def _payload(title: str) -> TrainingPathPayload:
    return TrainingPathPayload.model_validate(
        {
            "title": title,
            "phases": [
                {
                    "phase_id": "phase-product",
                    "title": "产品能力",
                    "outcome": "能独立讲解核心产品",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "product-a",
                            "title": "产品 A",
                            "outcome": "能说明产品 A 的适用场景",
                            "order_index": 1,
                            "estimated_minutes": 35,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "activity-product-a-assignment",
                                    "type": "assignment",
                                    "title": "总结产品 A",
                                    "objective": "用客户语言总结产品 A",
                                    "why_it_matters": "客户只关心产品能解决什么问题",
                                    "steps": ["回顾资料", "整理要点", "提交总结"],
                                    "success_criteria": ["包含适用场景", "包含客户收益"],
                                    "primary_action_label": "开始整理总结",
                                    "order_index": 1,
                                    "estimated_minutes": 15,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


async def _publish(test_db, actor, title):
    service = TrainingPathRevisionService(test_db)
    await service.save_draft(payload=_payload(title), actor=actor, reason=title)
    result = await service.publish(actor=actor, reason=title)
    await test_db.commit()
    return result.revision


async def _publish_audio_path(test_db, actor) -> None:
    material = SalesTrainerMaterial(
        material_id="material-ppt-intro",
        material_key="ppt-intro",
        name="新人销售 PPT",
        status="published",
        created_by=str(actor.user_id),
        updated_by=str(actor.user_id),
    )
    test_db.add(material)
    await test_db.flush()
    version = SalesTrainerMaterialVersion(
        version_id="material-version-ppt-v3",
        material_id=material.material_id,
        version_label="v3.0",
        title="新人销售 PPT（2026 夏季版）",
        file_name="新人销售标准讲解-v3.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes=4096,
        storage_key="tests/newcomer/ppt-v3.pptx",
        status="published",
        created_by=str(actor.user_id),
        published_by=str(actor.user_id),
    )
    test_db.add(version)
    material.current_version_id = version.version_id
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type="audio_scoring_rubric",
        logical_id="rubric-ppt-intro",
        payload={
            "title": "PPT 标准讲解评分",
            "dimensions": [
                {
                    "key": "structure",
                    "label": "讲解结构",
                    "description": "开场、方案和下一步衔接自然",
                    "weight": 40,
                },
                "客户语言",
            ],
            "pass_score": 80,
        },
        actor=actor,
        change_class="scoring_high_risk",
        reason="测试学习者准备包",
    )
    await TrainingPathRevisionService(test_db).save_draft(
        payload=TrainingPathPayload.model_validate(
            {
                "title": "录音训练路径",
                "phases": [
                    {
                        "phase_id": "phase-pitch",
                        "title": "产品讲解",
                        "order_index": 1,
                        "modules": [
                            {
                                "module_id": "module-ppt",
                                "title": "PPT 讲解",
                                "order_index": 1,
                                "completion_policy": {"mode": "all_required"},
                                "activities": [
                                    {
                                        "activity_id": "activity-ppt-audio",
                                        "type": "audio_assessment",
                                        "title": "PPT 讲解录音",
                                        "order_index": 1,
                                        "config": {
                                            "scoring_rubric_id": "rubric-ppt-intro",
                                            "material_id": material.material_id,
                                            "pass_score": 80,
                                            "example_transcript": "先确认客户现状，再说明产品如何解决问题。",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ),
        actor=actor,
        reason="测试学习者准备包",
    )
    await TrainingPathRevisionService(test_db).publish(
        actor=actor,
        reason="测试学习者准备包",
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_should_pin_revision_and_return_one_primary_next_action(
    test_db, test_user
):
    published = await _publish(test_db, test_user, "版本一")
    journey = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )

    detail = await NewcomerJourneyService(test_db).activity_detail(
        learner=test_user, activity_id="activity-product-a-assignment"
    )
    assert detail.runner.model_dump() == {
        "type": "assignment",
        "submission_type": "text",
        "review_mode": "automatic_complete",
        "max_file_size_bytes": 10485760,
    }

    assert journey.path_revision_id == published.revision_id
    assert journey.primary_next_action.activity_id == "activity-product-a-assignment"
    assert journey.phases[0].modules[0].estimated_minutes == 35
    assert journey.phases[0].modules[0].activities[0].estimated_minutes == 15
    assert journey.phases[0].outcome == "能独立讲解核心产品"
    assert journey.phases[0].modules[0].outcome == "能说明产品 A 的适用场景"
    activity = journey.phases[0].modules[0].activities[0]
    assert activity.objective == "用客户语言总结产品 A"
    assert activity.why_it_matters == "客户只关心产品能解决什么问题"
    assert activity.steps == ["回顾资料", "整理要点", "提交总结"]
    assert activity.success_criteria == ["包含适用场景", "包含客户收益"]
    assert journey.primary_next_action.label == "开始整理总结"
    assert (
        sum(
            activity.is_primary_next_action
            for phase in journey.phases
            for module in phase.modules
            for activity in module.activities
        )
        == 1
    )


@pytest.mark.asyncio
async def test_should_keep_existing_enrollment_on_old_revision_after_publish(
    test_db, test_user
):
    first = await _publish(test_db, test_user, "版本一")
    before = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )
    await _publish(test_db, test_user, "版本二")
    after = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )

    assert before.path_revision_id == first.revision_id
    assert after.path_revision_id == first.revision_id


@pytest.mark.asyncio
async def test_audio_detail_should_project_preparation_pack_without_internal_keys(
    test_db, test_user
):
    await _publish_audio_path(test_db, test_user)

    detail = await NewcomerJourneyService(test_db).activity_detail(
        learner=test_user,
        activity_id="activity-ppt-audio",
    )

    runner = detail.runner.model_dump()
    assert runner["material_version_label"] == "v3.0"
    assert runner["material_file_name"] == "新人销售标准讲解-v3.pptx"
    assert runner["material_content_type"].startswith("application/")
    assert runner["scoring_rubric_revision_id"]
    assert runner["scoring_rubric_revision_no"] == 1
    assert runner["scoring_rubric_title"] == "PPT 标准讲解评分"
    assert runner["scoring_focuses"] == [
        {
            "label": "讲解结构",
            "description": "开场、方案和下一步衔接自然",
            "weight": 40.0,
        },
        {"label": "客户语言", "description": None, "weight": None},
    ]
    assert runner["example_transcript"] == "先确认客户现状，再说明产品如何解决问题。"
    assert "key" not in str(runner["scoring_focuses"])

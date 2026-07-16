from __future__ import annotations

import pytest

from agent.models import VoiceRuntimeProfile
from common.db.models import ScoringRuleset
from curriculum_practice.models import CaseItem, PracticeTemplate, RoleProfile
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.journey_service import (
    NewcomerJourneyService,
    _runner_descriptor,
)
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.prompt_revision_payloads import PROMPT_RESOURCE_TYPE
from sales_trainer.services.realtime_binding_snapshot_service import (
    freeze_realtime_bindings,
    validate_realtime_binding_snapshots,
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
                                    "success_criteria": [
                                        "包含适用场景",
                                        "包含客户收益",
                                    ],
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
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id="rubric-ppt-intro",
        name="PPT 标准讲解评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练录音评分专家。",
        scoring_template="请评分。\n{transcript}",
        output_schema={},
        learner_rubric={
            "visible_to_learner": True,
            "pass_threshold": 80,
            "criteria": [
                {
                    "key": "structure",
                    "label": "讲解结构",
                    "description": "开场、方案和下一步衔接自然",
                    "weight": 40,
                },
                {
                    "key": "customer_language",
                    "label": "客户语言",
                    "description": None,
                    "weight": None,
                },
            ],
            "common_mistakes": [],
        },
        version=1,
        status="published",
        created_by=str(actor.user_id),
        updated_by=str(actor.user_id),
    )
    test_db.add(prompt)
    await test_db.flush()
    revision = SalesTrainerAssetRevision(
        resource_type=PROMPT_RESOURCE_TYPE,
        logical_id="rubric-ppt-intro",
        revision_no=1,
        status="published",
        payload_json={
            "prompt_id": "rubric-ppt-intro",
            "name": prompt.name,
            "purpose": prompt.purpose,
            "system_prompt": prompt.system_prompt,
            "scoring_template": prompt.scoring_template,
            "output_schema": {},
            "learner_rubric": prompt.learner_rubric,
            "version": 1,
            "status": "published",
        },
        payload_hash="hash-prompt-ppt",
        created_by=str(actor.user_id),
        published_by=str(actor.user_id),
    )
    test_db.add(revision)
    await test_db.flush()
    test_db.add(
        SalesTrainerAssetActiveRevision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id="rubric-ppt-intro",
            active_revision_id=revision.revision_id,
        )
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
async def test_should_move_existing_enrollment_to_latest_revision_after_publish(
    test_db, test_user
):
    first = await _publish(test_db, test_user, "版本一")
    before = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )
    assert before.path_revision_id == first.revision_id
    second = await _publish(test_db, test_user, "版本二")
    after = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )

    assert after.path_revision_id == second.revision_id


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


@pytest.mark.asyncio
async def test_realtime_detail_should_project_published_learner_preparation_without_ids(
    test_db, test_user
):
    test_db.add_all(
        [
            CaseItem(
                case_item_id="case-enterprise-upgrade",
                industry="企业服务",
                company_profile="一家正在评估销售培训平台的成长型企业",
                customer_role="销售负责人",
                pain_points=["新人上手慢"],
                objections=["实施周期是否过长"],
                hidden_information="仅在学员问到实施计划时披露",
                success_criteria=["澄清现状", "确认下一步演示安排"],
                allowed_disclosure_policy={"phases": ["discovery"]},
                version=2,
                content_hash="sha256:case-v2",
                status="published",
            ),
            RoleProfile(
                role_profile_id="role-sales-leader",
                role_type="customer",
                role_name="谨慎的销售负责人",
                communication_style="重视数据依据，会追问实施风险",
                pressure_level="medium",
                knowledge_boundary=["公司销售团队现状"],
                behavior_rules=["信息不足时继续追问"],
                voice_style_hint="冷静、克制",
                version=3,
                content_hash="sha256:role-v3",
                status="published",
            ),
            ScoringRuleset(
                ruleset_id="ruleset-roleplay-v4",
                scenario_type="sales",
                version="v4",
                display_name="客户需求探索评分标准",
                description="依据需求澄清、价值表达和下一步推进进行评分",
                status="published",
                definition_json={
                    "dimensions": [
                        {
                            "dimension_id": "discovery",
                            "label": "需求澄清",
                            "description": "通过提问确认客户现状与目标",
                            "weight": 6,
                        },
                        {
                            "dimension_id": "next_step",
                            "label": "下一步推进",
                            "description": "形成明确且双方认可的下一步",
                            "weight": 4,
                        },
                    ],
                    "passing_score": 75,
                },
                is_active=True,
            ),
            VoiceRuntimeProfile(
                id="runtime-profile-only",
                name="新人训练实时对练",
                is_active=True,
                voice_mode="stepfun_realtime",
            ),
            PracticeTemplate(
                template_id="practice-enterprise-upgrade",
                name="企业销售培训平台首次沟通",
                description="与正在评估培训平台的销售负责人完成首次需求沟通",
                scenario_type="sales",
                mode="customer_roleplay",
                agent_id="agent-runtime-only",
                persona_id="persona-runtime-only",
                runtime_profile_id="runtime-profile-only",
                voice_mode="stepfun_realtime",
                scoring_ruleset_id="ruleset-roleplay-v4",
                case_item_id="case-enterprise-upgrade",
                role_profile_id="role-sales-leader",
                status="published",
                version=5,
                published_asset_refs={},
            ),
        ]
    )
    await test_db.flush()
    payload = TrainingPathPayload.model_validate(
        {
            "title": "实时对练路径",
            "phases": [
                {
                    "phase_id": "phase-roleplay",
                    "title": "客户对练",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-roleplay",
                            "title": "首次沟通",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "activity-roleplay",
                                    "type": "realtime_roleplay",
                                    "title": "首次需求沟通对练",
                                    "order_index": 1,
                                    "config": {
                                        "practice_template_id": "practice-enterprise-upgrade",
                                        "runtime_profile_id": "runtime-profile-only",
                                        "completion_mode": "scored",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    runner = (
        await _runner_descriptor(
            test_db,
            payload.phases[0].modules[0].activities[0],
        )
    ).model_dump()

    assert runner["configuration_ready"] is True
    assert runner["template_title"] == "企业销售培训平台首次沟通"
    assert runner["template_version"] == 5
    assert runner["scenario"] == "与正在评估培训平台的销售负责人完成首次需求沟通"
    assert runner["counterpart_role"] == "谨慎的销售负责人"
    assert runner["counterpart_style"] == "重视数据依据，会追问实施风险"
    assert runner["goals"] == ["澄清现状", "确认下一步演示安排"]
    assert runner["scoring_title"] == "客户需求探索评分标准"
    assert runner["scoring_version"] == "v4"
    assert runner["passing_score"] == 75
    assert [item["label"] for item in runner["scoring_focuses"]] == [
        "需求澄清",
        "下一步推进",
    ]
    assert not any(
        internal_key in runner
        for internal_key in (
            "practice_template_id",
            "runtime_profile_id",
            "agent_id",
            "persona_id",
            "scoring_ruleset_id",
        )
    )

    frozen_payload = await freeze_realtime_bindings(test_db, payload)
    frozen_activity = frozen_payload.phases[0].modules[0].activities[0]
    frozen_config = frozen_activity.config
    assert frozen_config.runner_snapshot is not None
    assert frozen_config.practice_template_version == 5

    template = await test_db.get(PracticeTemplate, "practice-enterprise-upgrade")
    assert template is not None
    template.name = "后来发布的新模板名称"
    template.version = 6
    await test_db.flush()
    stale_runner = (await _runner_descriptor(test_db, frozen_activity)).model_dump()
    assert stale_runner["configuration_ready"] is False
    assert stale_runner["template_title"] == "企业销售培训平台首次沟通"
    assert stale_runner["template_version"] == 5
    stale_issues = await validate_realtime_binding_snapshots(test_db, frozen_payload)
    assert stale_issues[0].code == "realtime_binding_snapshot_stale"

    template.name = "企业销售培训平台首次沟通"
    template.version = 5
    await test_db.flush()

    role_profile = await test_db.get(RoleProfile, "role-sales-leader")
    assert role_profile is not None
    original_style = role_profile.communication_style
    role_profile.communication_style = "后来修改的沟通风格"
    await test_db.flush()
    child_asset_stale_runner = (
        await _runner_descriptor(test_db, frozen_activity)
    ).model_dump()
    assert child_asset_stale_runner["configuration_ready"] is False
    assert child_asset_stale_runner["counterpart_style"] == original_style
    role_profile.communication_style = original_style
    await test_db.flush()

    mismatched_activity = (
        payload.phases[0]
        .modules[0]
        .activities[0]
        .model_copy(
            update={
                "config": payload.phases[0]
                .modules[0]
                .activities[0]
                .config.model_copy(update={"runtime_profile_id": "other-profile"})
            }
        )
    )
    mismatched_runner = (
        await _runner_descriptor(test_db, mismatched_activity)
    ).model_dump()
    assert mismatched_runner["configuration_ready"] is False
    assert mismatched_runner["configuration_message"] == (
        "对练配置尚未准备完整，请联系培训管理员。"
    )

    template.runtime_profile_id = "missing-runtime-profile"
    await test_db.flush()
    missing_profile_activity = (
        payload.phases[0]
        .modules[0]
        .activities[0]
        .model_copy(
            update={
                "config": payload.phases[0]
                .modules[0]
                .activities[0]
                .config.model_copy(
                    update={"runtime_profile_id": "missing-runtime-profile"}
                )
            }
        )
    )
    missing_profile_runner = (
        await _runner_descriptor(test_db, missing_profile_activity)
    ).model_dump()
    assert missing_profile_runner["configuration_ready"] is False


@pytest.mark.asyncio
async def test_should_lock_later_required_activities_and_reject_deep_link_writes(
    test_db, test_user
):
    payload = TrainingPathPayload.model_validate(
        {
            "title": "顺序解锁训练",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "入门",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-1",
                            "title": "基础任务",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "assignment-first",
                                    "type": "assignment",
                                    "title": "先完成",
                                    "order_index": 1,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                },
                                {
                                    "activity_id": "assignment-second",
                                    "type": "assignment",
                                    "title": "后完成",
                                    "order_index": 2,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    )
    revisions = TrainingPathRevisionService(test_db)
    await revisions.save_draft(payload=payload, actor=test_user, reason="顺序解锁")
    await revisions.publish(actor=test_user, reason="顺序解锁")
    service = NewcomerJourneyService(test_db)

    journey = await service.get_or_create_for_learner(learner=test_user)
    first, second = journey.phases[0].modules[0].activities
    assert first.locked is False
    assert second.locked is True
    assert second.lock_reason == "请先完成前一项必修任务"

    locked_detail = await service.activity_detail(
        learner=test_user,
        activity_id="assignment-second",
    )
    assert locked_detail.activity.locked is True
    with pytest.raises(NewcomerOrchestrationError) as error:
        await service.context_for_activity(
            learner=test_user,
            activity_id="assignment-second",
        )
    assert error.value.code == "[NEWCOMER_ACTIVITY_PREREQUISITE_NOT_MET]"

    test_db.add(
        NewcomerTrainingActivityAttempt(
            enrollment_id=journey.enrollment_id,
            path_revision_id=journey.path_revision_id,
            activity_id="assignment-first",
            activity_type="assignment",
            attempt_no=1,
            status="completed",
            passed=True,
            client_token="unlock-first",
            activity_snapshot={"activity_id": "assignment-first"},
        )
    )
    await test_db.flush()

    unlocked = await service.get_or_create_for_learner(learner=test_user)
    assert unlocked.phases[0].modules[0].activities[1].locked is False
    context = await service.context_for_activity(
        learner=test_user,
        activity_id="assignment-second",
    )
    assert context.activity.activity_id == "assignment-second"

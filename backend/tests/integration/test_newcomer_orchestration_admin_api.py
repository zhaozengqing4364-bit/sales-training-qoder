from __future__ import annotations

import pytest


def _payload(
    *, title: str = "可配置新人训练", phase_title: str = "入门"
) -> dict[str, object]:
    return {
        "title": title,
        "phases": [
            {
                "phase_id": "phase-1",
                "title": phase_title,
                "order_index": 1,
                "modules": [
                    {
                        "module_id": "product-a",
                        "title": "产品 A",
                        "order_index": 1,
                        "completion_policy": {"mode": "all_required"},
                        "activities": [
                            {
                                "activity_id": "assignment-1",
                                "type": "assignment",
                                "title": "学习总结",
                                "order_index": 1,
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


def _incomplete_audio_payload(
    *, scoring_rubric_id: str = ""
) -> dict[str, object]:
    return {
        "title": "待补资源的新人训练",
        "phases": [
            {
                "phase_id": "phase-audio",
                "title": "讲解训练",
                "order_index": 1,
                "modules": [
                    {
                        "module_id": "module-audio",
                        "title": "产品讲解",
                        "order_index": 1,
                        "completion_policy": {"mode": "all_required"},
                        "activities": [
                            {
                                "activity_id": "audio-1",
                                "type": "audio_assessment",
                                "title": "产品讲解录音",
                                "order_index": 1,
                                "config": {
                                    "scoring_rubric_id": scoring_rubric_id,
                                    "material_id": None,
                                    "pass_score": 80,
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _all_incomplete_resource_bindings_payload() -> dict[str, object]:
    activities = [
        {
            "activity_id": "lesson-1",
            "type": "lesson",
            "title": "内容学习",
            "order_index": 1,
            "config": {"learning_content_id": ""},
        },
        {
            "activity_id": "quiz-1",
            "type": "quiz",
            "title": "考试测验",
            "order_index": 2,
            "config": {"exam_paper_id": "", "pass_score": 80},
        },
        {
            "activity_id": "audio-1",
            "type": "audio_assessment",
            "title": "录音讲解",
            "order_index": 3,
            "config": {"scoring_rubric_id": "", "pass_score": 80},
        },
        {
            "activity_id": "roleplay-1",
            "type": "realtime_roleplay",
            "title": "实时对练",
            "order_index": 4,
            "config": {"practice_template_id": "", "runtime_profile_id": ""},
        },
        {
            "activity_id": "coach-1",
            "type": "ai_coach",
            "title": "AI 教练",
            "order_index": 5,
            "config": {"coach_profile_id": ""},
        },
    ]
    return {
        "title": "待补全部资源的新人训练",
        "phases": [
            {
                "phase_id": "phase-1",
                "title": "入门",
                "order_index": 1,
                "modules": [
                    {
                        "module_id": "module-1",
                        "title": "基础训练",
                        "order_index": 1,
                        "completion_policy": {"mode": "all_required"},
                        "activities": activities,
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_admin_can_save_validate_and_publish_activity_path(
    async_client, auth_headers
):
    saved = await async_client.put(
        "/api/v1/admin/newcomer-training/path/draft",
        headers={**auth_headers, "x-request-id": "path-admin-test"},
        json={"payload": _payload(), "reason": "配置产品 A"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "working"

    preview = await async_client.post(
        "/api/v1/admin/newcomer-training/path/validate", headers=auth_headers
    )
    assert preview.status_code == 200
    assert preview.json()["data"] == {"can_publish": True, "issues": []}

    published = await async_client.post(
        "/api/v1/admin/newcomer-training/path/publish",
        headers=auth_headers,
        json={"reason": "发布产品 A"},
    )
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "published"


@pytest.mark.asyncio
async def test_incomplete_resource_binding_is_saved_but_blocks_publish_with_issue(
    async_client, auth_headers
):
    draft = await async_client.put(
        "/api/v1/admin/newcomer-training/path/draft",
        headers=auth_headers,
        json={
            "payload": _incomplete_audio_payload(),
            "reason": "先保存未完成配置",
        },
    )
    assert draft.status_code == 200, draft.text

    candidate = await async_client.post(
        "/api/v1/admin/newcomer-training/path/validate-candidate",
        headers=auth_headers,
        json={"payload": _incomplete_audio_payload()},
    )
    assert candidate.status_code == 200, candidate.text
    assert candidate.json()["data"] == {
        "can_publish": False,
        "issues": [
            {
                "code": "scoring_rubric_required",
                "message": "产品讲解录音：请选择已发布的录音评分标准。",
                "object_id": "audio-1",
                "field_path": "phases[0].modules[0].activities[0].config.scoring_rubric_id",
                "severity": "error",
            }
        ],
    }

    blocked = await async_client.post(
        "/api/v1/admin/newcomer-training/path/publish-candidate",
        headers=auth_headers,
        json={
            "payload": _incomplete_audio_payload(),
            "reason": "尝试发布未完成配置",
            "expected_revision_id": draft.json()["data"]["revision_id"],
        },
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"] == "[NEWCOMER_PATH_VALIDATION_FAILED]"
    assert blocked.json()["details"] == candidate.json()["data"]["issues"]


@pytest.mark.asyncio
async def test_candidate_validation_reports_only_actionable_missing_bindings(
    async_client, auth_headers
):
    response = await async_client.post(
        "/api/v1/admin/newcomer-training/path/validate-candidate",
        headers=auth_headers,
        json={"payload": _all_incomplete_resource_bindings_payload()},
    )

    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert {issue["code"] for issue in issues} == {
        "learning_content_required",
        "exam_paper_required",
        "scoring_rubric_required",
        "practice_template_required",
        "runtime_profile_required",
        "coach_profile_required",
    }
    assert all(
        issue["object_id"] != "roleplay-1"
        or issue["code"] != "realtime_binding_snapshot_stale"
        for issue in issues
    )


@pytest.mark.asyncio
async def test_admin_can_validate_and_publish_unsaved_candidate(
    async_client, auth_headers
):
    candidate = await async_client.post(
        "/api/v1/admin/newcomer-training/path/validate-candidate",
        headers=auth_headers,
        json={"payload": _payload()},
    )
    assert candidate.status_code == 200, candidate.text
    assert candidate.json()["data"] == {"can_publish": True, "issues": []}

    before_publish = await async_client.get(
        "/api/v1/admin/newcomer-training/path/", headers=auth_headers
    )
    assert before_publish.json()["data"]["working_revision_id"] is None

    published = await async_client.post(
        "/api/v1/admin/newcomer-training/path/publish-candidate",
        headers=auth_headers,
        json={
            "payload": _payload(),
            "reason": "直接发布已检查候选",
            "expected_revision_id": None,
        },
    )
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "published"


@pytest.mark.asyncio
async def test_publish_candidate_syncs_existing_learner_to_latest_path(
    async_client, auth_headers
):
    first_payload = _payload(title="全员同步版本一")
    first = await async_client.post(
        "/api/v1/admin/newcomer-training/path/publish-candidate",
        headers=auth_headers,
        json={
            "payload": first_payload,
            "reason": "发布版本一",
            "expected_revision_id": None,
        },
    )
    assert first.status_code == 200, first.text

    before = await async_client.get(
        "/api/v1/newcomer-training/journey", headers=auth_headers
    )
    assert before.status_code == 200, before.text
    assert (
        before.json()["data"]["path_revision_id"] == first.json()["data"]["revision_id"]
    )

    second_payload = _payload(title="全员同步版本二", phase_title="同步后的入门")
    second = await async_client.post(
        "/api/v1/admin/newcomer-training/path/publish-candidate",
        headers=auth_headers,
        json={
            "payload": second_payload,
            "reason": "同步全体在训学员",
            "expected_revision_id": first.json()["data"]["revision_id"],
        },
    )
    assert second.status_code == 200, second.text

    after = await async_client.get(
        "/api/v1/newcomer-training/journey", headers=auth_headers
    )
    assert after.status_code == 200, after.text
    assert (
        after.json()["data"]["path_revision_id"] == second.json()["data"]["revision_id"]
    )
    assert after.json()["data"]["phases"][0]["title"] == "同步后的入门"


@pytest.mark.asyncio
async def test_admin_returns_409_for_stale_path_revision(async_client, auth_headers):
    saved = await async_client.put(
        "/api/v1/admin/newcomer-training/path/draft",
        headers=auth_headers,
        json={"payload": _payload(), "reason": "先保存一次"},
    )
    assert saved.status_code == 200

    conflict = await async_client.put(
        "/api/v1/admin/newcomer-training/path/draft",
        headers=auth_headers,
        json={
            "payload": {**_payload(), "title": "陈旧编辑"},
            "reason": "尝试覆盖",
            "expected_revision_id": "stale-revision",
        },
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"] == "[NEWCOMER_PATH_REVISION_CONFLICT]"


@pytest.mark.asyncio
async def test_admin_activity_type_catalog_has_exact_six_types(
    async_client, auth_headers
):
    response = await async_client.get(
        "/api/v1/admin/newcomer-training/path/activity-types", headers=auth_headers
    )
    assert response.status_code == 200
    assert [item["type"] for item in response.json()["data"]] == [
        "lesson",
        "quiz",
        "audio_assessment",
        "realtime_roleplay",
        "ai_coach",
        "assignment",
    ]


@pytest.mark.asyncio
async def test_admin_lists_only_active_governed_coach_profiles(
    async_client, auth_headers, test_db, test_user
):
    from sales_trainer.services.asset_revision_service import (
        SalesTrainerAssetRevisionService,
    )

    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type="ai_coach_profile",
        logical_id="product-coach",
        payload={"title": "产品教练", "config": {"enabled": True}},
        actor=test_user,
        change_class="semantic",
        reason="测试教练方案",
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/newcomer-training/path/coach-profiles",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == [
        {"id": "product-coach", "title": "产品教练", "status": "published"}
    ]


@pytest.mark.asyncio
async def test_admin_creates_and_lists_structured_audio_rubric(
    async_client, auth_headers
):
    created = await async_client.post(
        "/api/v1/admin/newcomer-training/path/scoring-rubrics",
        headers={**auth_headers, "x-request-id": "rubric-create"},
        json={
            "title": "产品讲解评分标准",
            "pass_score": 80,
            "dimensions": [{"key": "accuracy", "label": "内容准确", "weight": 1}],
        },
    )
    assert created.status_code == 200, created.text
    rubric_id = created.json()["data"]["id"]
    assert created.json()["data"] == {
        "id": rubric_id,
        "title": "产品讲解评分标准",
        "status": "published",
    }

    listed = await async_client.get(
        "/api/v1/admin/newcomer-training/path/scoring-rubrics",
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"] == [
        {
            "id": rubric_id,
            "title": "产品讲解评分标准",
            "status": "published",
        }
    ]

    # Same catalog as 录音评分标准 page
    prompts = await async_client.get(
        "/api/v1/admin/sales-trainer/audio-score-prompts",
        headers=auth_headers,
    )
    assert prompts.status_code == 200, prompts.text
    items = prompts.json()["data"]["items"]
    match = next((item for item in items if item["prompt_id"] == rubric_id), None)
    assert match is not None
    assert match["name"] == "产品讲解评分标准"
    assert match["status"] == "published"
    assert "{transcript}" in match["scoring_template"]

    saved = await async_client.put(
        "/api/v1/admin/newcomer-training/path/draft",
        headers=auth_headers,
        json={
            "payload": _incomplete_audio_payload(scoring_rubric_id=rubric_id),
            "reason": "绑定新建评分标准并保存草稿",
        },
    )
    assert saved.status_code == 200, saved.text

    reloaded = await async_client.get(
        "/api/v1/admin/newcomer-training/path/",
        headers=auth_headers,
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["data"]["working_revision_id"] == saved.json()["data"]["revision_id"]
    activity = reloaded.json()["data"]["payload"]["phases"][0]["modules"][0]["activities"][0]
    assert activity["config"]["scoring_rubric_id"] == rubric_id


@pytest.mark.asyncio
async def test_admin_preserves_and_publishes_long_audio_scoring_prompt(
    async_client, auth_headers
):
    created = await async_client.post(
        "/api/v1/admin/newcomer-training/path/scoring-rubrics",
        headers=auth_headers,
        json={
            "title": "石犀 PPT 长提示词评分标准",
            "pass_score": 80,
            "dimensions": [{"key": "accuracy", "label": "内容准确", "weight": 1}],
        },
    )
    assert created.status_code == 200, created.text
    prompt_id = created.json()["data"]["id"]
    long_template = "\n".join(
        [
            "# 石犀数据流动治理平台 PPT 讲解评估提示词",
            (
                "检查产品定位、行业背景、资产与用户两端、平台加组件、"
                "产品能力、客户价值、服务模式和商业价值。"
            )
            * 1_000,
            (
                "你必须且只能输出合法 JSON，包含 total_score、summary、"
                "strengths、improvements、dimension_scores。"
            ),
            "{transcript}",
        ]
    )

    saved_revision = await async_client.put(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}",
        headers=auth_headers,
        json={
            "system_prompt": "你是严格的企业产品培训考官。",
            "scoring_template": long_template,
        },
    )
    assert saved_revision.status_code == 200, saved_revision.text

    published = await async_client.post(
        f"/api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish",
        headers=auth_headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["data"]["version"] == 2
    assert published.json()["data"]["system_prompt"] == "你是严格的企业产品培训考官。"
    assert published.json()["data"]["scoring_template"] == long_template


@pytest.mark.asyncio
async def test_admin_journey_uses_activity_identity(
    async_client, auth_headers, test_user
):
    await async_client.put(
        "/api/v1/admin/newcomer-training/path/draft",
        headers=auth_headers,
        json={"payload": _payload(), "reason": "配置活动身份"},
    )
    await async_client.post(
        "/api/v1/admin/newcomer-training/path/publish",
        headers=auth_headers,
        json={"reason": "发布活动身份"},
    )

    response = await async_client.get(
        f"/api/v1/admin/newcomer-training/journeys/{test_user.user_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    activity = response.json()["data"]["phases"][0]["modules"][0]["activities"][0]
    assert activity["activity_id"] == "assignment-1"
    assert "module_key" not in activity

    listed = await async_client.get(
        "/api/v1/admin/newcomer-training/journeys", headers=auth_headers
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["learner_id"] == str(test_user.user_id)
    summary = listed.json()["data"]["items"][0]["summary"]
    assert "journey" not in listed.json()["data"]["items"][0]
    assert summary["path_title"]
    assert "progress" in summary
    assert "primary_next_action" in summary
    assert "risk_labels" in summary
    assert "phases" not in summary

    dossier = await async_client.get(
        f"/api/v1/admin/newcomer-training/readiness/dossiers/{test_user.user_id}",
        headers=auth_headers,
    )
    assert dossier.status_code == 200, dossier.text
    dossier_data = dossier.json()["data"]
    assert dossier_data["contract_version"] == "readiness_dossier_v1"
    assert dossier_data["status"] == "not_started"
    assert dossier_data["summary"]["total_modules"] == 1
    assert dossier_data["realtime_gate"]["locked"] is True

    workbench = await async_client.get(
        "/api/v1/admin/newcomer-training/readiness/workbench",
        headers=auth_headers,
    )
    assert workbench.status_code == 200, workbench.text
    workbench_data = workbench.json()["data"]
    assert workbench_data["contract_version"] == "readiness_dossier_v1"
    assert set(workbench_data["groups"]) == {
        "pending_review",
        "not_passed",
        "needs_retraining",
        "config_exception",
        "approved",
        "in_training",
    }


@pytest.mark.asyncio
async def test_learning_content_binding_impact_uses_activity_identity(
    async_client, auth_headers
):
    response = await async_client.get(
        "/api/v1/curriculum/learning-contents/content-unbound/binding-impact",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "learning_content_id": "content-unbound",
        "active_bindings": [],
        "working_bindings": [],
        "can_archive": True,
        "archive_block_reason": None,
    }

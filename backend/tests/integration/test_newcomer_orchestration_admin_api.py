from __future__ import annotations

import pytest


def _payload() -> dict[str, object]:
    return {
        "title": "可配置新人训练",
        "phases": [
            {
                "phase_id": "phase-1",
                "title": "入门",
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
            "dimensions": [
                {"key": "accuracy", "label": "内容准确", "weight": 1}
            ],
        },
    )
    assert created.status_code == 200, created.text
    rubric_id = created.json()["data"]["id"]

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
    assert (
        listed.json()["data"]["items"][0]["journey"]["phases"][0]["modules"][0][
            "module_id"
        ]
        == "product-a"
    )

    dossier = await async_client.get(
        f"/api/v1/admin/newcomer-training/readiness/dossiers/{test_user.user_id}",
        headers=auth_headers,
    )
    assert dossier.status_code == 200, dossier.text
    assert dossier.json()["data"]["status"] == "in_training"


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

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

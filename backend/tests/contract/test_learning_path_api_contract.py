from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import PracticeTemplate


@pytest.mark.asyncio
async def test_next_task_api_contract_returns_recommendation_reason_and_cta(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    test_db.add(
        PracticeTemplate(
            name="产品知识专项",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id="agent-1",
            persona_id="persona-1",
            runtime_profile_id="runtime-1",
            scoring_ruleset_id="ruleset-1",
            knowledge_base_refs=[],
            status="published",
        )
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/curriculum-practice/learning-path/me/next-task",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["title"] == "产品知识专项"
    assert data["state"] in {"available", "locked", "completed", "pending_review"}
    assert data["primary_cta"] == "开始默认路径"
    assert data["retry_action"] is None


@pytest.mark.asyncio
async def test_learning_path_api_contract_returns_ordered_stages_and_prerequisites(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    test_db.add(
        PracticeTemplate(
            template_id="11111111-1111-1111-1111-111111111111",
            name="课程化路径",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id="agent-1",
            persona_id="persona-1",
            runtime_profile_id="runtime-1",
            scoring_ruleset_id="ruleset-1",
            knowledge_base_refs=[],
            status="published",
            version=1,
            content_hash="hash-path",
            curriculum_plan={
                "name": "销售课程路径",
                "stages": [
                    {
                        "template_stage_key": "template_stage_opening",
                        "order": 1,
                        "name": "开场建立信任",
                        "template_ref": {
                            "asset_type": "practice_template",
                            "asset_id": "11111111-1111-1111-1111-111111111111",
                            "version": 1,
                            "hash": "hash-path",
                            "snapshot_label": "published",
                        },
                        "completion_policy": {"min_score": 7, "min_rounds": 1, "max_duration_seconds": 600},
                        "prerequisites": [],
                    },
                    {
                        "template_stage_key": "template_stage_review",
                        "order": 2,
                        "name": "主管认证复核",
                        "template_ref": {
                            "asset_type": "practice_template",
                            "asset_id": "11111111-1111-1111-1111-111111111111",
                            "version": 1,
                            "hash": "hash-path",
                            "snapshot_label": "published",
                        },
                        "completion_policy": {"min_score": 8, "min_rounds": 1, "max_duration_seconds": 600},
                        "prerequisites": [{"template_stage_key": "template_stage_opening", "required_result": "completed"}],
                    },
                ],
            },
        )
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/curriculum-practice/learning-path/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"]
    assert data["path_type"] in {"weakness_driven", "role_default"}
    assert [stage["template_stage_key"] for stage in data["stages"]] == [
        "template_stage_opening",
        "template_stage_review",
    ]
    assert data["stages"][1]["prerequisites"] == [
        {"template_stage_key": "template_stage_opening", "required_result": "completed"}
    ]


@pytest.mark.asyncio
async def test_learning_path_api_contract_returns_failure_reason(
    async_client: AsyncClient,
    auth_headers: dict,
) -> None:
    response = await async_client.get(
        "/api/v1/curriculum-practice/learning-path/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["next_task"]["failure_reason"] is None


@pytest.mark.asyncio
async def test_learning_path_api_contract_returns_pending_review_placeholder(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    test_db.add(
        PracticeTemplate(
            template_id="22222222-2222-2222-2222-222222222222",
            name="认证路径",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id="agent-1",
            persona_id="persona-1",
            runtime_profile_id="runtime-1",
            scoring_ruleset_id="ruleset-1",
            knowledge_base_refs=[],
            status="published",
            version=1,
            content_hash="hash-review",
            curriculum_plan={
                "name": "认证路径",
                "stages": [
                    {
                        "template_stage_key": "template_stage_review",
                        "order": 1,
                        "name": "主管认证复核",
                        "template_ref": {
                            "asset_type": "practice_template",
                            "asset_id": "22222222-2222-2222-2222-222222222222",
                            "version": 1,
                            "hash": "hash-review",
                            "snapshot_label": "published",
                        },
                        "completion_policy": {"min_score": 8, "min_rounds": 1, "max_duration_seconds": 600},
                        "prerequisites": [],
                    }
                ],
            },
        )
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/curriculum-practice/learning-path/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    states = {stage["state"] for stage in response.json()["data"]["stages"]}
    assert "pending_review" in states

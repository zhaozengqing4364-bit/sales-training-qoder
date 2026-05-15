from __future__ import annotations

import pytest
from httpx import AsyncClient


def _category_payload() -> dict[str, object]:
    return {"name": "需求诊断", "description": "题库分类", "order_index": 1}


def _question_payload(category_id: str) -> dict[str, object]:
    return {
        "category_id": category_id,
        "title": "识别客户预算",
        "stem": "客户说预算有限时如何追问？",
        "reference_answer": "先确认预算范围，再澄清优先级。",
        "scoring_criteria": {"dimensions": ["clarity"]},
        "scoring_dimensions": ["clarity"],
        "tags": ["discovery", "budget"],
        "difficulty": "medium",
        "safety_flagged": False,
        "department": "sales-enablement",
    }


@pytest.mark.asyncio
async def test_test_bank_category_contract_returns_stable_envelope_and_fields(
    async_client: AsyncClient,
    contract_auth_headers: dict[str, str],
) -> None:
    response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=contract_auth_headers,
        json=_category_payload(),
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["success"] is True
    assert payload["trace_id"] is not None
    data = payload["data"]
    assert data.keys() >= {
        "category_id",
        "parent_id",
        "name",
        "description",
        "order_index",
        "created_at",
        "updated_at",
    }


@pytest.mark.asyncio
async def test_test_bank_question_contract_returns_lifecycle_and_snapshot_fields(
    async_client: AsyncClient,
    contract_auth_headers: dict[str, str],
) -> None:
    category_response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=contract_auth_headers,
        json=_category_payload(),
    )
    category_id = category_response.json()["data"]["category_id"]

    response = await async_client.post(
        "/api/v1/curriculum/test-bank/questions",
        headers=contract_auth_headers,
        json=_question_payload(category_id),
    )

    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert data.keys() >= {
        "question_id",
        "category_id",
        "title",
        "stem",
        "reference_answer",
        "scoring_criteria",
        "scoring_dimensions",
        "tags",
        "difficulty",
        "status",
        "safety_flagged",
        "department",
        "version",
        "content_hash",
        "published_at",
        "created_at",
        "updated_at",
    }
    assert data["status"] == "draft"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_test_bank_publish_gate_contract_returns_gate_results(
    async_client: AsyncClient,
    contract_auth_headers: dict[str, str],
) -> None:
    category_response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=contract_auth_headers,
        json=_category_payload(),
    )
    category_id = category_response.json()["data"]["category_id"]
    create_response = await async_client.post(
        "/api/v1/curriculum/test-bank/questions",
        headers=contract_auth_headers,
        json=_question_payload(category_id) | {"reference_answer": ""},
    )
    question_id = create_response.json()["data"]["question_id"]

    response = await async_client.post(
        f"/api/v1/curriculum/test-bank/questions/{question_id}/publish",
        headers=contract_auth_headers,
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "[QUESTION_ITEM_PUBLISH_GATE_FAILED]"
    gate_result = payload["details"]["gate_results"][0]
    assert gate_result.keys() >= {"gate_name", "status", "reason_code", "message"}
    assert gate_result["reason_code"] == "missing_reference_answer"

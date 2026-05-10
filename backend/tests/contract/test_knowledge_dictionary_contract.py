from __future__ import annotations

import pytest


@pytest.mark.contract
class TestKnowledgeDictionaryContract:
    async def test_dictionary_crud_response_matches_contract(
        self,
        async_client,
        contract_auth_headers,
    ):
        kb_response = await async_client.post(
            "/api/v1/admin/knowledge",
            headers=contract_auth_headers,
            json={
                "name": "词典契约知识库",
                "description": "验证 KB scoped dictionary contract",
                "category": "product",
            },
        )
        assert kb_response.status_code == 201
        kb_id = kb_response.json()["data"]["id"]

        create_response = await async_client.post(
            f"/api/v1/admin/knowledge/{kb_id}/dictionary-entries",
            headers=contract_auth_headers,
            json={
                "canonical_term": "石犀科技",
                "aliases": ["实习科技", "石溪科技"],
                "term_type": "organization",
                "status": "draft",
                "confidence": 96,
                "notes": "ASR 易误识别词",
            },
        )
        assert create_response.status_code == 201
        created_body = create_response.json()
        assert created_body["success"] is True
        created = created_body["data"]
        assert created["knowledge_base_id"] == kb_id
        assert created["canonical_term"] == "石犀科技"
        assert created["aliases"] == ["实习科技", "石溪科技"]
        assert created["status"] == "draft"
        assert created["confidence"] == 96
        assert created["source"] == "manual"
        assert created["evidence_count"] == 0
        assert created["created_at"]
        assert created["updated_at"]

        publish_response = await async_client.put(
            f"/api/v1/admin/knowledge/{kb_id}/dictionary-entries/{created['id']}",
            headers=contract_auth_headers,
            json={"status": "active"},
        )
        assert publish_response.status_code == 200
        assert publish_response.json()["data"]["status"] == "active"

        list_response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}/dictionary-entries?status=active",
            headers=contract_auth_headers,
        )
        assert list_response.status_code == 200
        list_body = list_response.json()
        assert list_body["success"] is True
        assert list_body["data"]["total"] == 1
        assert list_body["data"]["items"][0]["id"] == created["id"]

    async def test_dictionary_invalid_status_is_rejected_by_contract(
        self,
        async_client,
        contract_auth_headers,
    ):
        kb_response = await async_client.post(
            "/api/v1/admin/knowledge",
            headers=contract_auth_headers,
            json={
                "name": "非法状态知识库",
                "description": "验证词典状态校验",
                "category": "product",
            },
        )
        assert kb_response.status_code == 201
        kb_id = kb_response.json()["data"]["id"]

        response = await async_client.post(
            f"/api/v1/admin/knowledge/{kb_id}/dictionary-entries",
            headers=contract_auth_headers,
            json={
                "canonical_term": "石犀科技",
                "aliases": ["实习科技"],
                "status": "published",
            },
        )

        assert response.status_code == 422

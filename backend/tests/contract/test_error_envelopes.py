from __future__ import annotations

import uuid

import pytest

from common.auth.service import create_access_token


def _auth_headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.contract
class TestTargetedErrorEnvelopes:
    async def test_agent_create_invalid_category_returns_documented_error_envelope(
        self,
        async_client,
        test_db,
        test_user,
    ):
        test_user.role = "admin"
        await test_db.commit()

        response = await async_client.post(
            "/api/v1/admin/agents",
            headers=_auth_headers_for(test_user.user_id),
            json={
                "name": "错误分类智能体",
                "category": "customer_service",
                "capabilities_config": {},
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[AGENT_CATEGORY_RESTRICTED]"
        assert body["message"] == "当前仅支持创建「销售」与「演讲」两类智能体。"
        assert body.get("trace_id")

    async def test_voice_runtime_missing_profile_returns_documented_error_envelope(
        self,
        async_client,
        test_db,
        test_user,
    ):
        test_user.role = "admin"
        await test_db.commit()

        response = await async_client.put(
            f"/api/v1/admin/voice-runtime/profiles/{uuid.uuid4()}",
            headers=_auth_headers_for(test_user.user_id),
            json={"name": "不存在的配置"},
        )

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[VOICE_RUNTIME_PROFILE_NOT_FOUND]"
        assert body["message"] == "运行时配置不存在。"
        assert body.get("trace_id")

    async def test_presentation_missing_resource_keeps_documented_error_envelope(
        self,
        async_client,
        test_user,
    ):
        response = await async_client.get(
            f"/api/v1/presentations/{uuid.uuid4()}",
            headers=_auth_headers_for(test_user.user_id),
        )

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PRESENTATION_NOT_FOUND]"
        assert body["message"] == "演示文稿不存在。"
        assert body.get("trace_id")

    async def test_evaluation_access_denied_returns_documented_error_envelope(
        self,
        async_client,
        test_user,
    ):
        test_user.role = "user"

        response = await async_client.get(
            f"/api/v1/evaluation/sessions/{uuid.uuid4()}/report",
            headers=_auth_headers_for(test_user.user_id),
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[ACCESS_DENIED]"
        assert body["message"] == "你没有权限访问该会话。"
        assert body.get("trace_id")

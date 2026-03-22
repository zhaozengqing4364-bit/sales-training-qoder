"""
Contract tests for support runtime read-only API.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestSupportRuntimeContract:
    """Contract coverage for support runtime endpoints."""

    async def test_get_runtime_overview_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        response = await async_client.get(
            "/api/v1/support/runtime/overview?window_hours=24",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            body = response.json()
            assert body.get("success") is True
            assert "trace_id" in body
            data = body.get("data", {})
            assert "session_health" in data
            assert "fault_health" in data

    async def test_get_faults_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        response = await async_client.get(
            "/api/v1/support/runtime/faults?limit=10",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            body = response.json()
            assert body.get("success") is True
            assert "trace_id" in body
            data = body.get("data", {})
            assert isinstance(data.get("items", []), list)

    async def test_faults_rejects_invalid_status_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        response = await async_client.get(
            "/api/v1/support/runtime/faults?status=success",
            headers=auth_headers,
        )
        assert response.status_code in [400, 401, 403]

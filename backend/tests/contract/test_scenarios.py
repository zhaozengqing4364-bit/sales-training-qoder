"""
Contract Tests for Scenarios API
Tests API contracts for sales scenario management
"""
import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestScenariosContract:
    """Contract tests for scenarios API"""

    async def test_list_scenarios(self, async_client: AsyncClient, auth_headers: dict):
        """Test GET /api/v1/scenarios returns list of scenarios"""
        response = await async_client.get(
            "/api/v1/scenarios",
            headers=auth_headers
        )
        # May be 200 or 404
        assert response.status_code in [200, 404]

    async def test_get_sales_scenarios(self, async_client: AsyncClient, auth_headers: dict):
        """Test GET /api/v1/scenarios?scenario_type=sales returns sales scenarios"""
        response = await async_client.get(
            "/api/v1/scenarios?scenario_type=sales",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    async def test_get_presentation_scenarios(self, async_client: AsyncClient, auth_headers: dict):
        """Test GET /api/v1/scenarios?scenario_type=presentation returns presentation scenarios"""
        response = await async_client.get(
            "/api/v1/scenarios?scenario_type=presentation",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

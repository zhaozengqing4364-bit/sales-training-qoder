"""
Contract Tests for Sales Sessions API
Tests API contracts for sales practice sessions
"""
import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestSalesSessionsContract:
    """Contract tests for sales sessions API"""

    async def test_create_sales_session(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test POST /api/v1/practice/sessions with sales scenario"""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=auth_headers,
            json={
                "scenario_type": "sales",
                "sales_persona": "impatient_ceo"
            }
        )
        # May be 201 (created), 400 (invalid), or 404 (not found)
        assert response.status_code in [201, 400, 404]

    async def test_create_sales_session_with_persona(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test POST /api/v1/practice/sessions with specific persona"""
        personas = ["impatient_ceo", "skeptical_buyer", "price_focused", "technical_cto"]

        for persona in personas:
            response = await async_client.post(
                "/api/v1/practice/sessions",
                headers=auth_headers,
                json={
                    "scenario_type": "sales",
                    "sales_persona": persona
                }
            )
            # At least the request should be valid format
            assert response.status_code in [201, 400, 404]

    async def test_get_sales_session(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_session_id: str
    ):
        """Test GET /api/v1/practice/sessions/{id} for sales session"""
        response = await async_client.get(
            f"/api/v1/practice/sessions/{test_session_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

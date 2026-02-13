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
        contract_auth_headers: dict,
    ):
        """Test POST /api/v1/practice/sessions with sales scenario"""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=contract_auth_headers,
            json={
                "scenario_type": "sales",
                "sales_persona": "impatient_ceo"
            }
        )
        assert response.status_code == 201
        body = response.json()
        assert body.get("trace_id")
        assert body.get("success") is True

    async def test_create_sales_session_with_persona(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
    ):
        """Test POST /api/v1/practice/sessions with specific persona"""
        personas = ["impatient_ceo", "skeptical_buyer", "price_focused", "technical_cto"]

        for persona in personas:
            response = await async_client.post(
                "/api/v1/practice/sessions",
                headers=contract_auth_headers,
                json={
                    "scenario_type": "sales",
                    "sales_persona": persona
                }
            )
            assert response.status_code == 201
            body = response.json()
            assert body.get("trace_id")
            assert body.get("success") is True

    async def test_get_sales_session(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict,
        test_session_id: str,
    ):
        """Test GET /api/v1/practice/sessions/{id} for sales session"""
        response = await async_client.get(
            f"/api/v1/practice/sessions/{test_session_id}",
            headers=contract_auth_headers
        )
        assert response.status_code == 404
        assert response.json().get("trace_id")

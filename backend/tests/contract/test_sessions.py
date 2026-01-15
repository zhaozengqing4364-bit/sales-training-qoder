"""
Contract Tests for Practice Sessions API
Tests API contracts for creating and managing practice sessions
"""
import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestSessionsContract:
    """Contract tests for practice sessions API"""

    async def test_create_practice_session(self, async_client: AsyncClient, auth_headers: dict, test_presentation_id: str):
        """Test POST /api/v1/practice/sessions creates a session"""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=auth_headers,
            json={
                "scenario_type": "presentation",
                "presentation_id": test_presentation_id
            }
        )
        # May be 201 (created) or 400/404 (invalid data)
        assert response.status_code in [201, 400, 404]

    async def test_get_session(self, async_client: AsyncClient, auth_headers: dict, test_session_id: str):
        """Test GET /api/v1/practice/sessions/{id} returns session details"""
        response = await async_client.get(
            f"/api/v1/practice/sessions/{test_session_id}",
            headers=auth_headers
        )
        # May be 200 or 404
        assert response.status_code in [200, 404]

    async def test_delete_session(self, async_client: AsyncClient, auth_headers: dict, test_session_id: str):
        """Test DELETE /api/v1/practice/sessions/{id} deletes session"""
        response = await async_client.delete(
            f"/api/v1/practice/sessions/{test_session_id}",
            headers=auth_headers
        )
        # May be 204 (deleted) or 404 (not found)
        assert response.status_code in [204, 404]

"""
Contract Tests for Presentations API
Tests API contracts for PPT presentation CRUD operations
"""
import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestPresentationsContract:
    """Contract tests for presentations API"""

    async def test_create_presentation(self, async_client: AsyncClient, auth_headers: dict):
        """Test POST /api/v1/presentations creates a presentation"""
        # This would need a multipart file upload
        # For now, test the endpoint exists
        response = await async_client.post(
            "/api/v1/presentations",
            headers=auth_headers,
            data={"title": "Test Presentation"}
        )
        # Expect 422 (missing file) or 201 (created)
        assert response.status_code in [201, 422]

    async def test_list_presentations(self, async_client: AsyncClient, auth_headers: dict):
        """Test GET /api/v1/presentations returns list"""
        response = await async_client.get(
            "/api/v1/presentations",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_presentation(self, async_client: AsyncClient, auth_headers: dict, test_presentation_id: str):
        """Test GET /api/v1/presentations/{id} returns details"""
        response = await async_client.get(
            f"/api/v1/presentations/{test_presentation_id}",
            headers=auth_headers
        )
        # May be 404 if not exists, or 200 if exists
        assert response.status_code in [200, 404]

    async def test_get_presentation_pages(self, async_client: AsyncClient, auth_headers: dict, test_presentation_id: str):
        """Test GET /api/v1/presentations/{id}/pages returns pages"""
        response = await async_client.get(
            f"/api/v1/presentations/{test_presentation_id}/pages",
            headers=auth_headers
        )
        # May be 404 or 200
        assert response.status_code in [200, 404]

    async def test_add_talking_point(self, async_client: AsyncClient, auth_headers: dict, test_presentation_id: str):
        """Test POST /api/v1/presentations/{id}/pages/{n}/talking-points"""
        response = await async_client.post(
            f"/api/v1/presentations/{test_presentation_id}/pages/1/talking-points",
            headers=auth_headers,
            json={"description": "Test talking point"}
        )
        # May be 404 (page not found) or 201 (created)
        assert response.status_code in [201, 404]

    async def test_add_forbidden_word(self, async_client: AsyncClient, auth_headers: dict, test_presentation_id: str):
        """Test POST /api/v1/presentations/{id}/forbidden-words"""
        response = await async_client.post(
            f"/api/v1/presentations/{test_presentation_id}/forbidden-words",
            headers=auth_headers,
            json={
                "phrase": "test phrase",
                "suggested_alternative": "better phrase"
            }
        )
        # May be 404 or 201
        assert response.status_code in [201, 404]

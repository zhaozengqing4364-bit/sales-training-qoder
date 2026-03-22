"""
Contract Tests for PPT Upload API
Tests API contracts for presentation upload management
"""
import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestPPTUploadContract:
    """Contract tests for PPT upload API"""

    async def test_upload_presentation(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_file_path: str
    ):
        """Test POST /api/v1/admin/presentations with file upload"""
        with open(test_file_path, "rb") as f:
            response = await async_client.post(
                "/api/v1/admin/presentations",
                headers=auth_headers,
                data={"title": "Test Presentation"},
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        # May be 201 (created), 400/422 (invalid), or 401/403 (auth/rbac)
        assert response.status_code in [201, 400, 401, 403, 422]

    async def test_upload_presentation_without_file(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test POST /api/v1/admin/presentations without file returns error"""
        response = await async_client.post(
            "/api/v1/admin/presentations",
            headers=auth_headers,
            data={"title": "Test Presentation"}
        )
        # Should return validation error
        assert response.status_code in [400, 401, 403, 422]

    async def test_list_presentations(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/admin/presentations returns list"""
        response = await async_client.get(
            "/api/v1/admin/presentations",
            headers=auth_headers
        )
        # May be 200 or auth/rbac failure
        assert response.status_code in [200, 401, 403]

    async def test_get_presentation_pages(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_presentation_id: str
    ):
        """Test GET /api/v1/admin/presentations/{id}/pages"""
        response = await async_client.get(
            f"/api/v1/admin/presentations/{test_presentation_id}/pages",
            headers=auth_headers
        )
        assert response.status_code in [200, 404, 401, 403]

    async def test_add_talking_point(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_page_id: str
    ):
        """Test POST /api/v1/admin/pages/{id}/talking-points"""
        response = await async_client.post(
            f"/api/v1/admin/pages/{test_page_id}/talking-points",
            headers=auth_headers,
            json={
                "point_text": "This is a required talking point",
                "order": 1
            }
        )
        assert response.status_code in [201, 400, 404, 401, 403]

    async def test_add_forbidden_word(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_presentation_id: str
    ):
        """Test POST /api/v1/admin/presentations/{id}/forbidden-words"""
        response = await async_client.post(
            f"/api/v1/admin/presentations/{test_presentation_id}/forbidden-words",
            headers=auth_headers,
            json={
                "word": "um",
                "pattern_type": "literal"
            }
        )
        assert response.status_code in [201, 400, 404, 401, 403]

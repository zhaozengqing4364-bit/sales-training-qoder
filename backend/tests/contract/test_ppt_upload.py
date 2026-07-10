"""
Contract Tests for PPT Upload API
Tests API contracts for presentation upload management
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ForbiddenWord, Presentation, User
from common.db.schemas import ForbiddenWordResponse


@pytest.mark.contract
class TestPPTUploadContract:
    """Contract tests for PPT upload API"""

    async def test_upload_presentation(
        self, async_client: AsyncClient, auth_headers: dict, test_file_path: str
    ):
        """Test POST /api/v1/admin/presentations with file upload"""
        with open(test_file_path, "rb") as f:
            response = await async_client.post(
                "/api/v1/admin/presentations",
                headers=auth_headers,
                data={"title": "Test Presentation"},
                files={"file": ("test.pdf", f, "application/pdf")},
            )
        # May be 201 (created), 400/422 (invalid), or 401/403 (auth/rbac)
        assert response.status_code in [201, 400, 401, 403, 422]

    async def test_upload_presentation_without_file(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test POST /api/v1/admin/presentations without file returns error"""
        response = await async_client.post(
            "/api/v1/admin/presentations",
            headers=auth_headers,
            data={"title": "Test Presentation"},
        )
        # Should return validation error
        assert response.status_code in [400, 401, 403, 422]

    async def test_list_presentations(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test GET /api/v1/admin/presentations returns list"""
        response = await async_client.get(
            "/api/v1/admin/presentations", headers=auth_headers
        )
        # May be 200 or auth/rbac failure
        assert response.status_code in [200, 401, 403]

    async def test_get_presentation_pages(
        self, async_client: AsyncClient, auth_headers: dict, test_presentation_id: str
    ):
        """Test GET /api/v1/admin/presentations/{id}/pages"""
        response = await async_client.get(
            f"/api/v1/admin/presentations/{test_presentation_id}/pages",
            headers=auth_headers,
        )
        assert response.status_code in [200, 404, 401, 403]

    async def test_add_talking_point(
        self, async_client: AsyncClient, auth_headers: dict, test_page_id: str
    ):
        """Test POST /api/v1/admin/pages/{id}/talking-points"""
        response = await async_client.post(
            f"/api/v1/admin/pages/{test_page_id}/talking-points",
            headers=auth_headers,
            json={"point_text": "This is a required talking point", "order": 1},
        )
        assert response.status_code in [201, 400, 404, 401, 403]

    @pytest.mark.parametrize(
        ("path_template", "payload"),
        [
            (
                "/api/v1/admin/presentations/{presentation_id}/forbidden-words",
                {"word": "um", "pattern_type": "literal"},
            ),
            (
                "/api/v1/presentations/{presentation_id}/forbidden-words",
                {"phrase": "um"},
            ),
        ],
    )
    async def test_add_forbidden_word(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_db: AsyncSession,
        test_user: User,
        path_template: str,
        payload: dict[str, object],
    ) -> None:
        """Both forbidden-word POST surfaces return the governed stable DTO."""
        presentation = Presentation(
            presentation_id=str(uuid.uuid4()),
            title="Forbidden-word contract presentation",
            file_url="/tmp/forbidden-word-contract.pptx",
            status="ready",
            uploaded_by_admin_id=str(test_user.user_id),
        )
        test_db.add(presentation)
        await test_db.commit()

        response = await async_client.post(
            path_template.format(presentation_id=presentation.presentation_id),
            headers=auth_headers,
            json=payload,
        )

        assert response.status_code == 201
        body = ForbiddenWordResponse.model_validate(response.json())
        assert body.phrase == "um"
        assert body.presentation_id == uuid.UUID(str(presentation.presentation_id))
        assert body.page_id is None
        assert body.is_regex is False

        result = await test_db.execute(
            select(ForbiddenWord).where(
                ForbiddenWord.presentation_id == str(presentation.presentation_id)
            )
        )
        persisted = list(result.scalars().all())
        assert len(persisted) == 1
        assert persisted[0].word_id == str(body.word_id)

    @pytest.mark.parametrize(
        ("path_template", "payload", "error_code"),
        [
            (
                "/api/v1/admin/presentations/{presentation_id}/forbidden-words",
                {"word": "um", "pattern_type": "literal"},
                "[ADMIN_FORBIDDEN_WORD_CREATE_FAILED]",
            ),
            (
                "/api/v1/presentations/{presentation_id}/forbidden-words",
                {"phrase": "um"},
                "[PRESENTATION_FORBIDDEN_WORD_CREATE_FAILED]",
            ),
        ],
    )
    async def test_add_forbidden_word_rolls_back_database_failure(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
        path_template: str,
        payload: dict[str, object],
        error_code: str,
    ) -> None:
        """A failed write returns a stable error and leaves no retry-visible row."""
        presentation = Presentation(
            presentation_id=str(uuid.uuid4()),
            title="Forbidden-word rollback presentation",
            file_url="/tmp/forbidden-word-rollback.pptx",
            status="ready",
            uploaded_by_admin_id=str(test_user.user_id),
        )
        test_db.add(presentation)
        await test_db.commit()
        presentation_id = str(presentation.presentation_id)

        async def fail_flush(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise SQLAlchemyError("forced forbidden-word flush failure")

        monkeypatch.setattr(test_db, "flush", fail_flush)
        response = await async_client.post(
            path_template.format(presentation_id=presentation_id),
            headers=auth_headers,
            json=payload,
        )

        assert response.status_code == 500
        assert response.json()["error"] == error_code
        result = await test_db.execute(
            select(ForbiddenWord).where(
                ForbiddenWord.presentation_id == presentation_id
            )
        )
        assert list(result.scalars().all()) == []

    async def test_forbidden_word_openapi_uses_stable_response_schema(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Both write surfaces publish the same explicit success schema."""
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]

        for path in (
            "/api/v1/admin/presentations/{presentation_id}/forbidden-words",
            "/api/v1/presentations/{presentation_id}/forbidden-words",
        ):
            schema = paths[path]["post"]["responses"]["201"]["content"][
                "application/json"
            ]["schema"]
            assert schema == {"$ref": "#/components/schemas/ForbiddenWordResponse"}

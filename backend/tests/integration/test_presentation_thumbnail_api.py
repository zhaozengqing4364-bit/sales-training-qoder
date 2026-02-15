import io
from pathlib import Path

import pytest
from httpx import AsyncClient

from common.error_handling.result import Result


class _FakePPTParser:
    def __init__(self, output_root: Path):
        self.output_root = output_root

    async def parse_presentation(self, file_content: bytes, filename: str):
        _ = (file_content, filename)
        return Result.ok(
            {
                "total_pages": 2,
                "title": "Demo",
                "pages": [
                    {"page_number": 1, "extracted_text": "第一页要点"},
                    {"page_number": 2, "extracted_text": "第二页要点"},
                ],
            }
        )

    async def generate_thumbnail(
        self,
        file_content: bytes,
        page_number: int = 1,
        output_dir: str = "./data/ppts/thumbnails",
    ):
        _ = file_content
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        output_file = target_dir / f"page-{page_number}.png"
        output_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        return Result.ok(str(output_file))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_presentation_sets_page_image_url(
    async_client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

    from presentation_coach.api import presentations as presentations_api

    fake_parser = _FakePPTParser(tmp_path)
    monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

    file_stream = io.BytesIO(b"fake-pptx-content")
    response = await async_client.post(
        "/api/v1/presentations",
        headers=auth_headers,
        data={"title": "演练文稿"},
        files={
            "file": (
                "demo.pptx",
                file_stream,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    presentation_id = payload["presentation_id"]

    pages_response = await async_client.get(
        f"/api/v1/presentations/{presentation_id}/pages",
        headers=auth_headers,
    )
    assert pages_response.status_code == 200
    pages = pages_response.json()
    assert len(pages) == 2
    assert all(page.get("image_url") for page in pages)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_thumbnail_endpoint_returns_image_payload(
    async_client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

    from presentation_coach.api import presentations as presentations_api

    fake_parser = _FakePPTParser(tmp_path)
    monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

    upload_response = await async_client.post(
        "/api/v1/presentations",
        headers=auth_headers,
        data={"title": "缩略图测试"},
        files={
            "file": (
                "thumb.pptx",
                io.BytesIO(b"fake"),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert upload_response.status_code == 200
    presentation_id = upload_response.json()["presentation_id"]

    pages_response = await async_client.get(
        f"/api/v1/presentations/{presentation_id}/pages",
        headers=auth_headers,
    )
    assert pages_response.status_code == 200
    image_url = pages_response.json()[0]["image_url"]
    assert image_url

    thumbnail_response = await async_client.get(image_url, headers=auth_headers)
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers.get("content-type", "").startswith("image/")
    assert len(thumbnail_response.content) > 0

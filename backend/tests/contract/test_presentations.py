import io
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Presentation, Scenario, User
from common.error_handling.result import Result


class _FakePPTParser:
    def __init__(self, output_root: Path, payloads: dict[str, dict[str, object]]):
        self.output_root = output_root
        self.payloads = payloads

    async def parse_presentation(self, file_content: bytes, filename: str):
        _ = file_content
        payload = self.payloads.get(filename)
        if payload is None:
            return Result.fail(f"missing payload for {filename}")
        return Result.ok(payload)

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


async def _upload_presentation(
    async_client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str,
    filename: str,
) -> dict[str, object]:
    response = await async_client.post(
        "/api/v1/presentations",
        headers=headers,
        data={"title": title},
        files={
            "file": (
                filename,
                io.BytesIO(b"fake-pptx"),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.contract
class TestPresentationsContract:
    async def test_replace_presentation_in_place_keeps_id_and_increments_version(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """POST /api/v1/presentations/{id}/replace should keep presentation_id stable and bump version."""
        monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

        from presentation_coach.api import presentations as presentations_api

        fake_parser = _FakePPTParser(
            tmp_path,
            payloads={
                "v1.pptx": {
                    "total_pages": 2,
                    "pages": [
                        {"page_number": 1, "extracted_text": "旧版第 1 页"},
                        {"page_number": 2, "extracted_text": "旧版第 2 页"},
                    ],
                },
                "v2.pptx": {
                    "total_pages": 1,
                    "pages": [
                        {"page_number": 1, "extracted_text": "新版第 1 页"},
                    ],
                },
            },
        )
        monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

        original = await _upload_presentation(
            async_client,
            contract_auth_headers,
            title="标准销售演示",
            filename="v1.pptx",
        )
        presentation_id = original["presentation_id"]
        assert original["version_number"] == 1
        assert original["status"] == "ready"
        assert original["total_pages"] == 2

        replace_response = await async_client.post(
            f"/api/v1/presentations/{presentation_id}/replace",
            headers=contract_auth_headers,
            data={"title": "标准销售演示（新版）"},
            files={
                "file": (
                    "v2.pptx",
                    io.BytesIO(b"fake-pptx-v2"),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )

        assert replace_response.status_code == 200, replace_response.text
        replaced = replace_response.json()
        assert replaced["presentation_id"] == presentation_id
        assert replaced["version_number"] == 2
        assert replaced["status"] == "ready"
        assert replaced["total_pages"] == 1

        detail_response = await async_client.get(
            f"/api/v1/presentations/{presentation_id}",
            headers=contract_auth_headers,
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["presentation_id"] == presentation_id
        assert detail["version_number"] == 2
        assert detail["status"] == "ready"
        assert detail["total_pages"] == 1
        assert len(detail["pages"]) == 1
        assert detail["pages"][0]["ocr_extracted_text"] == "新版第 1 页"

    async def test_replace_presentation_blocks_when_active_session_exists(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict[str, str],
        test_db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """POST /api/v1/presentations/{id}/replace should fail with an explicit blocker payload when a session is active."""
        monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

        from presentation_coach.api import presentations as presentations_api

        fake_parser = _FakePPTParser(
            tmp_path,
            payloads={
                "v1.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "稳定版"}],
                },
                "v2.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "替换版"}],
                },
            },
        )
        monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

        original = await _upload_presentation(
            async_client,
            contract_auth_headers,
            title="被占用的标准演示",
            filename="v1.pptx",
        )
        presentation_id = str(original["presentation_id"])

        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="presentation",
            name="contract_active_presentation",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(test_user.user_id),
            scenario_id=scenario.scenario_id,
            presentation_id=presentation_id,
            status="in_progress",
        )
        test_db.add_all([scenario, session])
        await test_db.commit()

        replace_response = await async_client.post(
            f"/api/v1/presentations/{presentation_id}/replace",
            headers=contract_auth_headers,
            files={
                "file": (
                    "v2.pptx",
                    io.BytesIO(b"fake-pptx-v2"),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )

        assert replace_response.status_code == 409
        body = replace_response.json()
        assert body.get("trace_id")
        assert body["success"] is False
        assert body["error"] == "[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]"
        assert "进行中的演练" in body["message"]
        details = body["details"]
        assert details["active_session_count"] == 1
        assert details["presentation_id"] == presentation_id
        assert details["active_sessions"][0]["session_id"] == session.session_id
        assert details["active_sessions"][0]["status"] == "in_progress"

        persisted = (
            await test_db.execute(
                select(Presentation).where(Presentation.presentation_id == presentation_id)
            )
        ).scalar_one()
        assert persisted.version_number == 1
        assert persisted.status == "ready"

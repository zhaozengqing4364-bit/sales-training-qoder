import asyncio
import io
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ForbiddenWord,
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
)
from common.error_handling.result import Result
from presentation_coach.services.coach_service import PresentationCoachService


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


class _DelayedFakePPTParser(_FakePPTParser):
    def __init__(
        self,
        output_root: Path,
        payloads: dict[str, dict[str, object]],
        *,
        parse_delays: dict[str, float],
    ):
        super().__init__(output_root, payloads)
        self.parse_delays = parse_delays

    async def parse_presentation(self, file_content: bytes, filename: str):
        delay = self.parse_delays.get(filename, 0.0)
        if delay > 0:
            await asyncio.sleep(delay)
        return await super().parse_presentation(file_content, filename)


class _AsyncBarrier:
    def __init__(self, parties: int):
        self.parties = parties
        self.arrivals = 0
        self._lock = asyncio.Lock()
        self._released = asyncio.Event()

    async def wait(self, *, timeout_seconds: float = 3.0) -> None:
        async with self._lock:
            self.arrivals += 1
            if self.arrivals >= self.parties:
                self._released.set()

        await asyncio.wait_for(self._released.wait(), timeout=timeout_seconds)


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


@pytest.mark.integration
@pytest.mark.asyncio
class TestPresentationFlow:
    async def test_replace_presentation_rebuilds_page_metadata_and_new_session_reads_latest_material(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """Replacing a standard PPT should keep the same presentation_id while new sessions read the rebuilt page content, talking points, and forbidden words."""
        monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

        from presentation_coach.api import presentations as presentations_api

        fake_parser = _FakePPTParser(
            tmp_path,
            payloads={
                "deck-v1.pptx": {
                    "total_pages": 2,
                    "pages": [
                        {"page_number": 1, "extracted_text": "旧版首页脚本"},
                        {"page_number": 2, "extracted_text": "旧版第二页内容"},
                    ],
                },
                "deck-v2.pptx": {
                    "total_pages": 1,
                    "pages": [
                        {"page_number": 1, "extracted_text": "新版首页脚本"},
                    ],
                },
            },
        )
        monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

        original = await _upload_presentation(
            async_client,
            auth_headers,
            title="标准演示模板",
            filename="deck-v1.pptx",
        )
        presentation_id = str(original["presentation_id"])
        assert original["version_number"] == 1

        original_page = (
            await test_db.execute(
                select(Page).where(
                    Page.presentation_id == presentation_id,
                    Page.page_number == 1,
                )
            )
        ).scalar_one()
        stale_page_id = original_page.page_id

        talking_point = RequiredTalkingPoint(
            page_id=stale_page_id,
            description="先讲业务目标",
            created_by="admin",
            is_ai_generated=False,
            confirmed_by_admin=True,
        )
        page_forbidden_word = ForbiddenWord(
            page_id=stale_page_id,
            presentation_id=None,
            phrase="绝对没问题",
            suggested_alternative="我们会给出明确交付保障",
        )
        global_forbidden_word = ForbiddenWord(
            presentation_id=presentation_id,
            page_id=None,
            phrase="保证成交",
            suggested_alternative="提升成交概率",
        )
        test_db.add_all([talking_point, page_forbidden_word, global_forbidden_word])
        await test_db.commit()

        replace_response = await async_client.post(
            f"/api/v1/presentations/{presentation_id}/replace",
            headers=auth_headers,
            files={
                "file": (
                    "deck-v2.pptx",
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

        pages = (
            await test_db.execute(
                select(Page)
                .where(Page.presentation_id == presentation_id)
                .order_by(Page.page_number)
            )
        ).scalars().all()
        assert len(pages) == 1
        assert pages[0].page_number == 1
        assert pages[0].ocr_extracted_text == "新版首页脚本"
        assert pages[0].page_id != stale_page_id

        stale_page = (
            await test_db.execute(select(Page).where(Page.page_id == stale_page_id))
        ).scalar_one_or_none()
        assert stale_page is None

        rebuilt_points = (
            await test_db.execute(
                select(RequiredTalkingPoint).where(
                    RequiredTalkingPoint.page_id == pages[0].page_id
                )
            )
        ).scalars().all()
        assert [point.description for point in rebuilt_points] == ["先讲业务目标"]

        rebuilt_page_words = (
            await test_db.execute(
                select(ForbiddenWord).where(ForbiddenWord.page_id == pages[0].page_id)
            )
        ).scalars().all()
        assert [word.phrase for word in rebuilt_page_words] == ["绝对没问题"]

        create_session_response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=auth_headers,
            json={
                "scenario_type": "presentation",
                "presentation_id": presentation_id,
            },
        )
        assert create_session_response.status_code == 201, create_session_response.text
        session_id = create_session_response.json()["data"]["session_id"]

        service = PresentationCoachService(test_db)
        requirements_result = await service.get_current_page_requirements(session_id, 1)
        assert requirements_result.is_success is True
        requirements = requirements_result.value
        assert requirements["page_content"] == "新版首页脚本"
        assert requirements["required_points"] == ["先讲业务目标"]
        assert set(requirements["forbidden_words"]) == {"绝对没问题", "保证成交"}

    async def test_replace_presentation_is_blocked_for_non_terminal_session(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """A presentation already referenced by a non-terminal session should reject in-place replacement instead of mutating live material."""
        monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

        from presentation_coach.api import presentations as presentations_api

        fake_parser = _FakePPTParser(
            tmp_path,
            payloads={
                "stable-v1.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "稳定内容"}],
                },
                "stable-v2.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "不应覆盖的内容"}],
                },
            },
        )
        monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

        original = await _upload_presentation(
            async_client,
            auth_headers,
            title="正在演练的模板",
            filename="stable-v1.pptx",
        )
        presentation_id = str(original["presentation_id"])

        create_session_response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=auth_headers,
            json={
                "scenario_type": "presentation",
                "presentation_id": presentation_id,
            },
        )
        assert create_session_response.status_code == 201, create_session_response.text

        replace_response = await async_client.post(
            f"/api/v1/presentations/{presentation_id}/replace",
            headers=auth_headers,
            files={
                "file": (
                    "stable-v2.pptx",
                    io.BytesIO(b"blocked-replace"),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )

        assert replace_response.status_code == 409
        body = replace_response.json()
        assert body["error"] == "[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]"

        detail_response = await async_client.get(
            f"/api/v1/presentations/{presentation_id}",
            headers=auth_headers,
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["version_number"] == 1
        assert detail["status"] == "ready"
        assert detail["pages"][0]["ocr_extracted_text"] == "稳定内容"

    async def test_concurrent_replace_requests_share_one_version_slot_and_lose_an_update(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """Two concurrent in-place replaces can race on page rebuild so one writer commits version 2 while the other falls into the global 500 fallback."""
        monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

        import agent.models  # noqa: F401
        from common.db.models import Base
        from common.db.session import get_db
        from main import app
        from presentation_coach.api import presentations as presentations_api
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from httpx import ASGITransport, AsyncClient

        database_path = tmp_path / "presentation-replace-race.sqlite3"
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", echo=False)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        fake_parser = _DelayedFakePPTParser(
            tmp_path,
            payloads={
                "race-base.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "基线内容"}],
                },
                "race-a.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "并发写者 A"}],
                },
                "race-b.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "并发写者 B"}],
                },
            },
            parse_delays={
                "race-a.pptx": 0.2,
                "race-b.pptx": 0.0,
            },
        )
        monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

        barrier = _AsyncBarrier(parties=2)
        original_non_terminal_check = (
            presentations_api._non_terminal_sessions_for_presentation
        )

        async def _barriered_non_terminal_sessions(db, presentation_id: str):
            sessions = await original_non_terminal_check(db, presentation_id)
            if not sessions:
                await barrier.wait()
            return sessions

        monkeypatch.setattr(
            presentations_api,
            "_non_terminal_sessions_for_presentation",
            _barriered_non_terminal_sessions,
        )

        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as isolated_client:
                login_response = await isolated_client.post("/api/v1/auth/dev-login")
                assert login_response.status_code == 200, login_response.text
                login_payload = login_response.json()
                access_token = (
                    login_payload.get("access_token")
                    or login_payload.get("token")
                    or (login_payload.get("data") or {}).get("access_token")
                )
                assert access_token
                auth_headers = {"Authorization": f"Bearer {access_token}"}

                original = await _upload_presentation(
                    isolated_client,
                    auth_headers,
                    title="并发替换模板",
                    filename="race-base.pptx",
                )
                presentation_id = str(original["presentation_id"])
                assert original["version_number"] == 1

                async def _replace(filename: str):
                    return await isolated_client.post(
                        f"/api/v1/presentations/{presentation_id}/replace",
                        headers=auth_headers,
                        files={
                            "file": (
                                filename,
                                io.BytesIO(filename.encode("utf-8")),
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            )
                        },
                    )

                replace_a, replace_b = await asyncio.gather(
                    _replace("race-a.pptx"),
                    _replace("race-b.pptx"),
                )

                assert barrier.arrivals == 2
                responses = [replace_a, replace_b]
                assert sorted(response.status_code for response in responses) == [200, 500]

                successful_response = next(
                    response for response in responses if response.status_code == 200
                )
                failed_response = next(
                    response for response in responses if response.status_code == 500
                )

                successful_body = successful_response.json()
                assert successful_body["presentation_id"] == presentation_id
                assert successful_body["version_number"] == 2
                assert successful_body["file_url"].endswith("-v2.pptx")
                assert successful_body["pages"][0]["ocr_extracted_text"] == "并发写者 B"

                failed_body = failed_response.json()
                assert failed_body["success"] is False
                assert failed_body["fallback"] == "[PLEASE_TRY_AGAIN]"
                assert failed_body.get("trace_id")

                detail_response = await isolated_client.get(
                    f"/api/v1/presentations/{presentation_id}",
                    headers=auth_headers,
                )
                assert detail_response.status_code == 200, detail_response.text
                detail = detail_response.json()
                assert detail["version_number"] == 2
                assert detail["status"] == "ready"
                assert detail["pages"][0]["ocr_extracted_text"] == "并发写者 B"
                assert detail["file_url"].endswith("-v2.pptx")
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()

    async def test_delete_presentation_has_no_route_level_active_session_blocker(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """Deleting a presentation with a live session currently succeeds without any route-level blocker, and the session loses its presentation link in the focused test harness."""
        monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "ppts"))

        from presentation_coach.api import presentations as presentations_api

        fake_parser = _FakePPTParser(
            tmp_path,
            payloads={
                "delete-v1.pptx": {
                    "total_pages": 1,
                    "pages": [{"page_number": 1, "extracted_text": "待删除内容"}],
                },
            },
        )
        monkeypatch.setattr(presentations_api, "get_ppt_parser", lambda: fake_parser)

        original = await _upload_presentation(
            async_client,
            auth_headers,
            title="待删除模板",
            filename="delete-v1.pptx",
        )
        presentation_id = str(original["presentation_id"])

        create_session_response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=auth_headers,
            json={
                "scenario_type": "presentation",
                "presentation_id": presentation_id,
            },
        )
        assert create_session_response.status_code == 201, create_session_response.text
        session_id = create_session_response.json()["data"]["session_id"]

        delete_response = await async_client.delete(
            f"/api/v1/presentations/{presentation_id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204, delete_response.text

        deleted_presentation = (
            await test_db.execute(
                select(Presentation).where(
                    Presentation.presentation_id == presentation_id
                )
            )
        ).scalar_one_or_none()
        assert deleted_presentation is None

        persisted_session = (
            await test_db.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
        ).scalar_one()
        assert persisted_session.presentation_id is None

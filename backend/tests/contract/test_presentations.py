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
                io.BytesIO(b"PKfake-pptx"),
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
                    io.BytesIO(b"PKfake-pptx-v2"),
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
                    io.BytesIO(b"PKfake-pptx-v2"),
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

    async def test_get_missing_presentation_returns_structured_not_found_envelope(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict[str, str],
    ):
        response = await async_client.get(
            "/api/v1/presentations/123e4567-e89b-12d3-a456-426614174000",
            headers=contract_auth_headers,
        )

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PRESENTATION_NOT_FOUND]"
        assert body["message"] == "演示文稿不存在。"
        assert body.get("trace_id")

    async def test_presentations_role_guard_returns_structured_detail_payload(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict[str, str],
        test_db: AsyncSession,
        test_user: User,
    ):
        test_user.role = "support"
        await test_db.commit()

        response = await async_client.get(
            "/api/v1/presentations",
            headers=contract_auth_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body.get("trace_id")
        assert body["detail"] == {
            "error": "[ROLE_REQUIRED]",
            "message": "当前账号权限不足，无法执行该操作。",
        }

    async def test_admin_role_guard_returns_structured_detail_payload(
        self,
        async_client: AsyncClient,
        contract_auth_headers: dict[str, str],
        test_db: AsyncSession,
        test_user: User,
    ):
        test_user.role = "user"
        await test_db.commit()

        response = await async_client.get(
            "/api/v1/admin/presentations",
            headers=contract_auth_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body.get("trace_id")
        assert body["detail"] == {
            "error": "[ROLE_REQUIRED]",
            "message": "[ADMIN_REQUIRED] 当前账号权限不足，无法执行该操作。",
        }

    async def test_resource_race_inventory_marks_replace_as_first_confirmed_proof_target(self):
        from presentation_coach.api.presentations import (
            PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS,
            PRESENTATION_RESOURCE_RACE_FOCUS,
            PRESENTATION_RESOURCE_RACE_INVENTORY,
        )

        surfaces = {
            entry["surface"]: entry for entry in PRESENTATION_RESOURCE_RACE_INVENTORY
        }

        assert set(surfaces) == {
            "upload_new_presentation",
            "replace_presentation_in_place",
            "delete_presentation",
        }
        assert (
            surfaces["upload_new_presentation"]["active_session_blocker_coverage"]
            == "not_applicable"
        )
        assert surfaces["upload_new_presentation"]["proof_state"] == "inventory_only"
        assert (
            surfaces["replace_presentation_in_place"][
                "active_session_blocker_coverage"
            ]
            == "covered_for_live_session_mutation_only"
        )
        assert surfaces["replace_presentation_in_place"]["proof_state"] == (
            "confirmed_concurrent_writer_race"
        )
        assert (
            surfaces["replace_presentation_in_place"]["recommended_next_step"]
            == "serialize_in_place_replace_with_local_or_distributed_lock_before_multi-writer rollout"
        )
        assert (
            surfaces["delete_presentation"]["active_session_blocker_coverage"]
            == "not_covered"
        )
        assert surfaces["delete_presentation"]["proof_state"] == (
            "confirmed_route_guard_gap"
        )
        assert (
            PRESENTATION_RESOURCE_RACE_FOCUS["highest_priority_surface"]
            == "replace_presentation_in_place"
        )
        assert (
            PRESENTATION_RESOURCE_RACE_FOCUS["recommended_next_proof"]
            == "concurrent_replace_without_active_sessions"
        )
        assert (
            PRESENTATION_RESOURCE_RACE_FOCUS["recommended_next_step"]
            == "add compare-and-swap or lock around in-place replace before multi-writer rollout"
        )

        conclusions = PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS
        assert conclusions["artifact_purpose"].startswith("canonical, code-adjacent")
        assert conclusions["proof_boundary"].startswith("ground conclusions only in focused proofs")

        confirmed = {
            entry["surface"]: entry for entry in conclusions["confirmed_findings"]
        }
        assert set(confirmed) == {
            "replace_presentation_in_place",
            "delete_presentation",
        }
        assert confirmed["replace_presentation_in_place"]["finding"] == (
            "confirmed_concurrent_writer_race"
        )
        assert "presentation row version_number/file_url" in confirmed[
            "replace_presentation_in_place"
        ]["shared_conflict_surfaces"]
        assert "distributed lock only if multiple app instances" in confirmed[
            "replace_presentation_in_place"
        ]["multi_instance_lock_candidate"]
        assert confirmed["delete_presentation"]["finding"] == (
            "confirmed_route_guard_gap_not_lock_gap"
        )
        assert "delete currently returns 204" in confirmed["delete_presentation"][
            "proof_summary"
        ]

        inventory_only = {
            entry["surface"]: entry for entry in conclusions["inventory_only_surfaces"]
        }
        assert inventory_only["upload_new_presentation"][
            "why_not_prioritized"
        ] == "no focused proof shows harmful cross-request contention on the current new-upload path"

        not_recommended = {
            entry["candidate"]: entry for entry in conclusions["not_recommended_now"]
        }
        assert "coordination cost" in not_recommended[
            "system-wide distributed lock for every presentation mutation"
        ]["reason"]
        assert "blind retries hide the conflict" in not_recommended[
            "retry-only mitigation for replace losers"
        ]["reason"]

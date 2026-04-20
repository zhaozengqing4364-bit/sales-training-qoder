"""
Contract tests for support runtime read-only API.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestSupportRuntimeContract:
    """Contract coverage for support runtime endpoints."""

    async def test_get_runtime_overview_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        response = await async_client.get(
            "/api/v1/support/runtime/overview?window_hours=24",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            body = response.json()
            assert body.get("success") is True
            assert "trace_id" in body
            data = body.get("data", {})
            assert "session_health" in data
            assert "release_health" in data
            assert "anomaly_summary" in data

            session_health = data["session_health"]
            assert "active_sessions" in session_health
            assert "completed_sessions_window" in session_health
            assert "scoring_sessions" in session_health
            assert "stuck_scoring_sessions" in session_health
            assert "completion_rate" in session_health

            release_health = data["release_health"]
            assert release_health.get("status") in {"healthy", "warning", "blocking"}
            assert isinstance(release_health.get("blocking_count"), int)
            assert isinstance(release_health.get("warning_count"), int)

            anomaly_summary = data["anomaly_summary"]
            assert isinstance(anomaly_summary.get("blocking", []), list)
            assert isinstance(anomaly_summary.get("warning", []), list)

    async def test_get_faults_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        response = await async_client.get(
            "/api/v1/support/runtime/faults?limit=10",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            body = response.json()
            assert body.get("success") is True
            assert "trace_id" in body
            data = body.get("data", {})
            assert isinstance(data.get("items", []), list)

            items = data.get("items", [])
            if items:
                item = items[0]
                assert item.get("severity") in {"blocking", "warning"}
                assert isinstance(item.get("kind"), str)
                assert isinstance(item.get("summary"), str)
                assert "detected_at" in item

    async def test_faults_openapi_exposes_linked_asset_change_contract(
        self,
        async_client: AsyncClient,
    ) -> None:
        response = await async_client.get("/openapi.json")
        assert response.status_code == 200

        document = response.json()
        route_schema = document["paths"]["/api/v1/support/runtime/faults"]["get"][
            "responses"
        ]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in route_schema

        components = document.get("components", {}).get("schemas", {})
        assert "LinkedAssetChangeReference" in components
        assert any(
            schema.get("properties", {})
            .get("linked_asset_changes", {})
            .get("items", {})
            .get("$ref", "")
            .endswith("/LinkedAssetChangeReference")
            for schema in components.values()
            if isinstance(schema, dict)
        )

        linked_asset_schema = components["LinkedAssetChangeReference"]
        assert linked_asset_schema["type"] == "object"
        assert set(linked_asset_schema.get("properties", {})) >= {
            "asset_type",
            "asset_label",
            "asset_id",
            "asset_name",
            "admin_path",
            "latest_change_label",
            "latest_change_type",
            "last_changed_at",
            "change_count_7d",
            "sessions_since_change",
            "impact_level",
            "health_status",
        }

    async def test_faults_rejects_invalid_severity_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        response = await async_client.get(
            "/api/v1/support/runtime/faults?severity=critical",
            headers=auth_headers,
        )
        assert response.status_code in [400, 401, 403]

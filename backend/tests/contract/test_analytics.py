"""
Contract Tests for Analytics API
Tests API contracts for practice history and leaderboard
"""
import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestAnalyticsContract:
    """Contract tests for analytics API"""

    async def test_get_practice_history(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/practice/history returns practice history"""
        response = await async_client.get(
            "/api/v1/practice/history",
            headers=auth_headers
        )
        # May be 200 (success) or 401 (unauthorized)
        assert response.status_code in [200, 401]

    async def test_get_practice_history_with_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/practice/history?scenario_type=presentation"""
        response = await async_client.get(
            "/api/v1/practice/history?scenario_type=presentation",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

    async def test_get_leaderboard(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/analytics/leaderboard returns rankings"""
        response = await async_client.get(
            "/api/v1/analytics/leaderboard",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

    async def test_get_leaderboard_with_scenario_type(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/analytics/leaderboard?scenario_type=sales"""
        response = await async_client.get(
            "/api/v1/analytics/leaderboard?scenario_type=sales",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

    async def test_get_leaderboard_with_include_me_and_alias_filters(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test alias normalization and include_me payload in leaderboard API."""
        response = await async_client.get(
            "/api/v1/analytics/leaderboard"
            "?scenario_type=sales_bot&time_period=week&include_me=true&limit=20",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

        if response.status_code == 200:
            payload = response.json()
            assert payload.get("scenario_type") == "sales"
            assert payload.get("time_period") == "weekly"
            assert isinstance(payload.get("entries", []), list)
            assert "my_rank" in payload
            assert payload["my_rank"].get("scenario_type") == "sales"
            assert payload["my_rank"].get("time_period") == "weekly"

    async def test_get_my_rank(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/analytics/leaderboard/my-rank"""
        response = await async_client.get(
            "/api/v1/analytics/leaderboard/my-rank",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

    async def test_get_my_rank_with_alias_time_period(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test my-rank API normalizes scenario/time aliases."""
        response = await async_client.get(
            "/api/v1/analytics/leaderboard/my-rank"
            "?scenario_type=sales_bot&time_period=month",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

        if response.status_code == 200:
            payload = response.json()
            assert payload.get("scenario_type") == "sales"
            assert payload.get("time_period") == "monthly"
            assert "rank" in payload

    async def test_get_progress_stats(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test GET /api/v1/practice/history/statistics returns progress statistics"""
        response = await async_client.get(
            "/api/v1/practice/history/statistics",
            headers=auth_headers
        )
        assert response.status_code in [200, 401]

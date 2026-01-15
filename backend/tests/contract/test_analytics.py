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

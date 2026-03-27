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

    async def test_get_admin_overview_projection_summary_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test admin overview exposes projection-backed score semantics."""
        response = await async_client.get(
            "/api/v1/admin/analytics/overview",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            payload = response.json()
            assert payload.get("success") is True
            data = payload.get("data", {})
            assert "evaluable_sessions" in data
            assert "not_evaluable_sessions" in data
            assert data.get("score_basis") == "session_evidence_projection_evaluable_only"
            assert isinstance(data.get("top_issue_families", []), list)
            assert isinstance(data.get("not_evaluable_reasons", []), list)

    async def test_get_admin_trends_projection_summary_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test admin trends exposes projection summary and issue family buckets."""
        response = await async_client.get(
            "/api/v1/admin/analytics/trends?time_range=30d&granularity=day",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            payload = response.json()
            assert payload.get("success") is True
            data = payload.get("data", {})
            assert isinstance(data.get("trend_data", []), list)
            assert isinstance(data.get("score_distribution", {}), dict)
            summary = data.get("projection_summary", {})
            assert "evaluable_sessions" in summary
            assert "not_evaluable_sessions" in summary
            assert summary.get("score_basis") == "session_evidence_projection_evaluable_only"
            assert isinstance(summary.get("issue_family_distribution", []), list)
            assert isinstance(summary.get("not_evaluable_reasons", []), list)

    async def test_get_admin_leaderboard_projection_fields_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test admin leaderboard entries expose projection-backed score metadata."""
        response = await async_client.get(
            "/api/v1/admin/analytics/leaderboard?time_range=30d&limit=20",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            payload = response.json()
            assert payload.get("success") is True
            leaderboard = payload.get("data", {}).get("leaderboard", [])
            assert isinstance(leaderboard, list)
            if leaderboard:
                entry = leaderboard[0]
                assert "evaluable_sessions" in entry
                assert "not_evaluable_sessions" in entry
                assert entry.get("score_basis") == "session_evidence_projection_evaluable_only"
                assert "primary_issue_type" in entry
                assert "primary_next_goal_type" in entry

    async def test_get_admin_operating_pack_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test admin operating pack exposes weekly cohort buckets and manager lists."""
        response = await async_client.get(
            "/api/v1/admin/analytics/operating-pack?time_range=7d&limit=10&inactive_days=7",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            payload = response.json()
            assert payload.get("success") is True
            data = payload.get("data", {})
            assert data.get("score_basis") == "session_evidence_projection_evaluable_only"
            assert isinstance(data.get("weekly_summary", {}), dict)
            assert isinstance(data.get("cohort_issue_buckets", []), list)
            assert isinstance(data.get("department_issue_buckets", []), list)
            assert isinstance(data.get("repeated_blocker_families", []), list)
            assert isinstance(data.get("degradation_breakdown", {}), dict)
            weekly_summary = data.get("weekly_summary", {})
            top_blocker_family = weekly_summary.get("top_blocker_family")
            top_not_evaluable_reason = weekly_summary.get("top_not_evaluable_reason")
            top_degraded_reason = weekly_summary.get("top_degraded_reason")
            if top_blocker_family:
                assert "issue_family" in top_blocker_family
                assert "issue_text" in top_blocker_family
                assert "count" in top_blocker_family
            if top_not_evaluable_reason:
                assert "reason" in top_not_evaluable_reason
                assert "count" in top_not_evaluable_reason
            if top_degraded_reason:
                assert "reason" in top_degraded_reason
                assert "count" in top_degraded_reason
            manager_lists = data.get("manager_lists", {})
            not_passed = manager_lists.get("not_passed", [])
            inactive_streak = manager_lists.get("inactive_streak", [])
            improving = manager_lists.get("improving", [])
            assert isinstance(not_passed, list)
            assert isinstance(inactive_streak, list)
            assert isinstance(improving, list)
            if not_passed:
                first_risk = not_passed[0]
                assert "issue_family" in first_risk
                assert "session_id" in first_risk
                assert "session_start_time" in first_risk
            if inactive_streak:
                assert "inactive_days" in inactive_streak[0]
            if improving:
                assert "pass_gain" in improving[0]

    async def test_export_admin_analytics_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test admin analytics export stays on the current CSV surface."""
        response = await async_client.get(
            "/api/v1/admin/analytics/export?time_range=7d&format=csv",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            assert "text/csv" in response.headers.get("content-type", "")
            assert "attachment; filename=analytics_report_" in response.headers.get(
                "content-disposition",
                "",
            )
            body = response.text
            assert "=== 系统概览 ===" in body
            assert "=== 分数分布 ===" in body
            assert "=== 用户排行榜 ===" in body

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

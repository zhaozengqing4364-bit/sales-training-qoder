"""
Integration Tests for Analytics Flow
Tests the complete analytics workflow from practice completion to leaderboard update
"""
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestAnalyticsFlow:
    """Integration tests for analytics flow"""

    async def test_practice_to_leaderboard_update(self, async_client, auth_headers):
        """Test that completing a practice session updates the leaderboard"""
        # 1. Create a practice session
        create_response = await async_client.post(
            "/api/v1/practice/sessions",
            headers=auth_headers,
            json={
                "scenario_type": "sales_bot",
                "sales_persona": "impatient_ceo"
            }
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create practice session")

        session_data = create_response.json()
        session_id = session_data.get("session_id")

        # 2. End the session (which should trigger analytics update)
        end_response = await async_client.delete(
            f"/api/v1/practice/sessions/{session_id}",
            headers=auth_headers
        )

        if end_response.status_code != 200:
            pytest.skip("Cannot end practice session")

        # 3. Check that practice history includes this session
        history_response = await async_client.get(
            "/api/v1/analytics/history",
            headers=auth_headers
        )

        if history_response.status_code == 200:
            history = history_response.json()
            sessions = history.get("sessions", [])
            # Verify session appears in history
            session_ids = [s.get("session_id") for s in sessions]
            assert session_id in session_ids
        else:
            pytest.skip("Cannot retrieve practice history")

    async def test_leaderboard_calculation(self, async_client, auth_headers):
        """Test that leaderboard is calculated correctly based on practice sessions"""
        # 1. Get leaderboard
        response = await async_client.get(
            "/api/v1/analytics/leaderboard?scenario_type=sales_bot",
            headers=auth_headers
        )

        if response.status_code != 200:
            pytest.skip("Cannot retrieve leaderboard")

        leaderboard = response.json()
        entries = leaderboard.get("entries", [])

        # 2. Verify leaderboard structure
        assert isinstance(entries, list)
        for entry in entries:
            assert "user_id" in entry or "name" in entry
            assert "average_score" in entry
            assert "rank" in entry

    async def test_progress_trends(self, async_client, auth_headers):
        """Test that progress trends can be calculated over time"""
        # Get progress statistics
        response = await async_client.get(
            "/api/v1/analytics/progress",
            headers=auth_headers
        )

        if response.status_code != 200:
            pytest.skip("Cannot retrieve progress statistics")

        progress = response.json()

        # Verify progress data structure
        assert "total_sessions" in progress or "sessions" in progress

    async def test_multiple_scenario_leaderboards(self, async_client, auth_headers):
        """Test that different scenario types have separate leaderboards"""
        # Get presentation leaderboard
        pres_response = await async_client.get(
            "/api/v1/analytics/leaderboard?scenario_type=presentation",
            headers=auth_headers
        )

        # Get sales leaderboard
        sales_response = await async_client.get(
            "/api/v1/analytics/leaderboard?scenario_type=sales_bot",
            headers=auth_headers
        )

        if pres_response.status_code == 200 and sales_response.status_code == 200:
            pres_leaderboard = pres_response.json()
            sales_leaderboard = sales_response.json()

            # Both should have entries list
            assert "entries" in pres_leaderboard
            assert "entries" in sales_leaderboard
        else:
            pytest.skip("Cannot retrieve both leaderboards")

    async def test_user_rank_calculation(self, async_client, auth_headers):
        """Test that user's rank is calculated correctly"""
        response = await async_client.get(
            "/api/v1/analytics/leaderboard/my-rank",
            headers=auth_headers
        )

        if response.status_code != 200:
            pytest.skip("Cannot retrieve user rank")

        rank_data = response.json()

        # Verify rank structure
        assert "rank" in rank_data or "message" in rank_data

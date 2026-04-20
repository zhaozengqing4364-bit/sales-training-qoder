"""
Contract Tests for Analytics API
Tests API contracts for practice history and leaderboard
"""
import pytest
from httpx import AsyncClient

from admin.api.training_records import TRAINING_RECORDS_DB_PERFORMANCE_BASELINE
from common.analytics.admin_analytics_service import (
    ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE,
)
from common.analytics.history_service import HISTORY_QUERY_DB_PERFORMANCE_BASELINE
from common.conversation.session_evidence import (
    SESSION_EVIDENCE_DB_PERFORMANCE_BASELINE,
)

QUERY_INDEX_DISCOVERY_CONCLUSIONS = {
    "confirmed_gaps": {
        "focused_proof": (
            {
                "slug": "admin_overview_growth_replays_projection_window",
                "baseline_paths": ("projection_window_load",),
                "proof": (
                    "test_get_overview_stats_replays_projection_window_for_growth_comparison proves overview growth "
                    "replays the projection window twice for current-vs-previous comparison, including two "
                    "practice_sessions window reads, two batched conversation_messages reads, and two user-count queries."
                ),
                "follow_up": (
                    "If this becomes hot under real admin traffic, test shared current/previous window reuse or "
                    "aggregate pushdown before proposing index-only work."
                ),
            },
            {
                "slug": "admin_leaderboard_requires_full_window_projection_before_top_n",
                "baseline_paths": ("projection_window_load", "leaderboard_python_reduce"),
                "proof": (
                    "test_get_leaderboard_batches_projection_window_and_messages_once shows admin leaderboard still "
                    "loads the whole projection window before ranking, while "
                    "test_calculate_leaderboard_pushes_ranking_aggregation_into_sql proves the classic leaderboard "
                    "service already keeps aggregate math in SQL."
                ),
                "follow_up": (
                    "Treat this as a query-shape or top-N reuse candidate first; only escalate to index work if real "
                    "admin timings show SQL scan time dominates the projection/Python reduce cost."
                ),
            },
        ),
        "code_path_confirmed": (
            {
                "slug": "admin_export_rebuilds_same_projection_window_for_each_csv_section",
                "baseline_paths": ("projection_window_load",),
                "proof": (
                    "ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE records export_analytics fanout into overview, trends, "
                    "and leaderboard, each rebuilding the same time-window projection."
                ),
                "follow_up": (
                    "A future optimization slice should first test shared projection reuse across CSV sections instead "
                    "of jumping straight to index creation."
                ),
            },
            {
                "slug": "training_records_list_has_row_level_agent_persona_n_plus_one",
                "baseline_paths": ("list_training_records",),
                "proof": (
                    "TRAINING_RECORDS_DB_PERFORMANCE_BASELINE records up to two extra Agent/Persona SELECTs per row "
                    "inside session_to_response after the paged PracticeSession query completes."
                ),
                "follow_up": (
                    "Fix the row-level metadata lookup pattern before spending effort on admin training-record search "
                    "indexes."
                ),
            },
            {
                "slug": "manager_intervention_overlay_reloads_completed_history_after_page_load",
                "baseline_paths": (
                    "manager_intervention_overlay",
                    "history_session_window_and_message_batch",
                ),
                "proof": (
                    "HISTORY_QUERY_DB_PERFORMANCE_BASELINE records a second completed-session/message replay after "
                    "manager_interventions load, so admin user-session drill-ins can pay for duplicate history work."
                ),
                "follow_up": (
                    "Only promote this into implementation if real admin usage shows it hot; the likely fix is "
                    "deduplicated projection reuse rather than new indexes."
                ),
            },
        ),
    },
    "needs_real_postgres_evidence": (
        {
            "slug": "practice_sessions_composite_window_indexes",
            "baseline_paths": (
                "projection_window_load",
                "history_session_window_and_message_batch",
            ),
            "why_not_confirmed": (
                "Current proof shows repeated practice_sessions filters and ordering, but not whether Postgres "
                "scan/sort cost is the dominant latency versus Python-side projection rebuild work."
            ),
            "measurement_plan": (
                "Capture EXPLAIN ANALYZE or pg_stat_statements for admin analytics/history windows and compare the "
                "existing single-column indexes against composite window candidates before adding anything."
            ),
        },
        {
            "slug": "admin_analytics_scenario_filter_plan",
            "baseline_paths": ("projection_window_load",),
            "why_not_confirmed": (
                "The code-path inventory only shows scenario.has(scenario_type=...) relationship filtering; it does "
                "not prove whether the measurable bottleneck is planner shape, scenario lookup, or the projection "
                "load after filtering."
            ),
            "measurement_plan": (
                "Inspect real Postgres plans for scenario-filtered admin analytics queries and choose between a "
                "query-shape rewrite and supporting indexes only if the filter itself shows up as a material cost."
            ),
        },
        {
            "slug": "conversation_messages_order_by_timestamp_extension",
            "baseline_paths": (
                "history_session_window_and_message_batch",
                "single_session_projection_load",
            ),
            "why_not_confirmed": (
                "Both history and per-session projection paths already batch by session_id/turn_number; without a real "
                "plan we do not know whether adding timestamp to the composite index removes material sort work."
            ),
            "measurement_plan": (
                "Run EXPLAIN on hot conversation_messages reads for long sessions and only consider extending the "
                "existing (session_id, turn_number) index with timestamp if residual ORDER BY work is visible."
            ),
        },
        {
            "slug": "training_records_search_text_indexes",
            "baseline_paths": ("list_training_records",),
            "why_not_confirmed": (
                "The current evidence only proves ILIKE search surfaces exist on user/scenario names; it does not yet "
                "show that search latency is worse than the confirmed agent/persona row-level N+1."
            ),
            "measurement_plan": (
                "Fix the row-level lookup pattern first, then use real Postgres timing to decide whether trigram or "
                "text-search support is needed for admin training-record search."
            ),
        },
    ),
}


@pytest.mark.contract
class TestAnalyticsContract:
    """Contract tests for analytics API"""

    def test_db_performance_baseline_keeps_confirmed_shapes_separate_from_runtime_hypotheses(self):
        """Keep the first-round DB baseline evidence-backed instead of speculative."""
        baseline_entries = (
            list(ADMIN_ANALYTICS_DB_PERFORMANCE_BASELINE)
            + list(HISTORY_QUERY_DB_PERFORMANCE_BASELINE)
            + list(SESSION_EVIDENCE_DB_PERFORMANCE_BASELINE)
            + list(TRAINING_RECORDS_DB_PERFORMANCE_BASELINE)
        )

        expected_paths = {
            "projection_window_load",
            "leaderboard_python_reduce",
            "history_session_window_and_message_batch",
            "manager_intervention_overlay",
            "single_session_projection_load",
            "list_training_records",
            "get_training_record",
        }

        assert {entry["path"] for entry in baseline_entries} == expected_paths
        for entry in baseline_entries:
            assert entry["risk"]
            assert entry["query_shape"]
            assert entry["evidence_level"].startswith("code_path_confirmed")
            if entry["path"] != "get_training_record":
                assert entry["index_candidates"]
                assert any(
                    token in entry["evidence_level"]
                    for token in (
                        "needs_runtime",
                        "needs_real_runtime_measurement",
                        "needs_postgres_measurement",
                        "requires_real_query_plan_evidence",
                        "depends_on_real_admin_usage",
                    )
                )

    def test_query_index_discovery_conclusions_stay_layered_and_actionable(self):
        """Keep the reusable query/index backlog explicit about proof tier and next proof step."""
        confirmed_gaps = QUERY_INDEX_DISCOVERY_CONCLUSIONS["confirmed_gaps"]
        focused_proof = confirmed_gaps["focused_proof"]
        code_path_confirmed = confirmed_gaps["code_path_confirmed"]
        runtime_hypotheses = QUERY_INDEX_DISCOVERY_CONCLUSIONS["needs_real_postgres_evidence"]

        assert {item["slug"] for item in focused_proof} == {
            "admin_overview_growth_replays_projection_window",
            "admin_leaderboard_requires_full_window_projection_before_top_n",
        }
        assert {item["slug"] for item in code_path_confirmed} == {
            "admin_export_rebuilds_same_projection_window_for_each_csv_section",
            "training_records_list_has_row_level_agent_persona_n_plus_one",
            "manager_intervention_overlay_reloads_completed_history_after_page_load",
        }
        assert {item["slug"] for item in runtime_hypotheses} == {
            "practice_sessions_composite_window_indexes",
            "admin_analytics_scenario_filter_plan",
            "conversation_messages_order_by_timestamp_extension",
            "training_records_search_text_indexes",
        }

        for item in focused_proof + code_path_confirmed:
            assert item["baseline_paths"]
            assert item["proof"]
            assert item["follow_up"]

        for item in runtime_hypotheses:
            assert item["baseline_paths"]
            assert item["why_not_confirmed"]
            assert item["measurement_plan"]

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

"""
Integration Tests for Staged Evaluation Database Tables

TDD Tests for Task C1: Create Staged Evaluation Database Tables
"""
import pytest
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def clean_staged_eval_tables(test_db: AsyncSession):
    """Clean up staged evaluation tables after each test."""
    yield
    # Cleanup after test
    await test_db.execute(text("DELETE FROM comprehensive_reports"))
    await test_db.execute(text("DELETE FROM staged_evaluation_results"))
    await test_db.commit()


class TestStagedEvaluationResultsTable:
    """Test staged_evaluation_results table structure."""

    @pytest.mark.asyncio
    async def test_table_exists(self, test_db: AsyncSession):
        """Should have staged_evaluation_results table."""
        result = await test_db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'staged_evaluation_results'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_columns_exist(self, test_db: AsyncSession):
        """Should have all required columns."""
        result = await test_db.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'staged_evaluation_results'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: (row[1], row[2]) for row in result.fetchall()}

        # Check required columns exist
        assert "id" in columns
        assert "session_id" in columns
        assert "stage_number" in columns
        assert "start_turn" in columns
        assert "end_turn" in columns
        assert "timestamp" in columns
        assert "scores" in columns
        assert "strengths" in columns
        assert "weaknesses" in columns
        assert "key_insights" in columns
        assert "improvement_suggestions" in columns
        assert "stage_summary" in columns
        assert "comparison_with_previous" in columns
        assert "is_fallback" in columns
        assert "cost_tokens" in columns
        assert "processing_time_ms" in columns

    @pytest.mark.asyncio
    async def test_session_index_exists(self, test_db: AsyncSession):
        """Should have index on session_id."""
        result = await test_db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE indexname = 'idx_staged_eval_session'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_stage_unique_index_exists(self, test_db: AsyncSession):
        """Should have unique index on session_id + stage_number."""
        result = await test_db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE indexname = 'idx_staged_eval_stage'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_insert_and_retrieve(self, test_db: AsyncSession, clean_staged_eval_tables):
        """Should be able to insert and retrieve staged evaluation."""
        session_id = str(uuid4())

        await test_db.execute(
            text("""
                INSERT INTO staged_evaluation_results (
                    session_id, stage_number, start_turn, end_turn,
                    scores, strengths, weaknesses, key_insights,
                    improvement_suggestions, stage_summary, is_fallback
                ) VALUES (
                    :session_id, 1, 0, 5,
                    '{"professionalism": 85, "communication": 90}',
                    '["Good clarity", "Strong points"]',
                    '["Needs more data", "Slow response"]',
                    '["Key insight 1"]',
                    '["Practice more"]',
                    'Stage 1 summary text',
                    false
                )
            """),
            {"session_id": session_id}
        )
        await test_db.commit()

        # Retrieve the record
        result = await test_db.execute(
            text("""
                SELECT session_id, stage_number, scores, strengths
                FROM staged_evaluation_results
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == session_id
        assert row[1] == 1
        assert "professionalism" in str(row[2])


class TestComprehensiveReportsTable:
    """Test comprehensive_reports table structure."""

    @pytest.mark.asyncio
    async def test_table_exists(self, test_db: AsyncSession):
        """Should have comprehensive_reports table."""
        result = await test_db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'comprehensive_reports'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_columns_exist(self, test_db: AsyncSession):
        """Should have all required columns."""
        result = await test_db.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'comprehensive_reports'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: (row[1], row[2]) for row in result.fetchall()}

        # Check required columns exist
        assert "id" in columns
        assert "session_id" in columns
        assert "generated_at" in columns
        assert "total_stages" in columns
        assert "total_turns" in columns
        assert "overall_assessment" in columns
        assert "key_strengths" in columns
        assert "priority_improvements" in columns
        assert "trend_summary" in columns
        assert "personalized_advice" in columns
        assert "practice_recommendations" in columns
        assert "estimated_skill_level" in columns
        assert "trend_analysis" in columns
        assert "score_timeline" in columns
        assert "is_fallback" in columns

    @pytest.mark.asyncio
    async def test_session_unique_index_exists(self, test_db: AsyncSession):
        """Should have unique index on session_id."""
        result = await test_db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE indexname = 'idx_comprehensive_reports_session'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_insert_and_retrieve(self, test_db: AsyncSession, clean_staged_eval_tables):
        """Should be able to insert and retrieve comprehensive report."""
        session_id = str(uuid4())

        await test_db.execute(
            text("""
                INSERT INTO comprehensive_reports (
                    session_id, total_stages, total_turns,
                    overall_assessment, key_strengths, priority_improvements,
                    trend_summary, personalized_advice, practice_recommendations,
                    estimated_skill_level, trend_analysis, score_timeline
                ) VALUES (
                    :session_id, 3, 15,
                    'Overall assessment text',
                    '["Strength 1", "Strength 2"]',
                    '["Improvement 1"]',
                    'Trend summary text',
                    'Personalized advice text',
                    '["Recommendation 1"]',
                    'intermediate',
                    '[{"stage": 1, "score": 80}]',
                    '[{"turn": 5, "score": 85}]'
                )
            """),
            {"session_id": session_id}
        )
        await test_db.commit()

        # Retrieve the record
        result = await test_db.execute(
            text("""
                SELECT session_id, total_stages, overall_assessment, estimated_skill_level
                FROM comprehensive_reports
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == session_id
        assert row[1] == 3
        assert row[2] == "Overall assessment text"
        assert row[3] == "intermediate"


class TestStagedEvaluationConstraints:
    """Test database constraints."""

    @pytest.mark.asyncio
    async def test_unique_stage_per_session(self, test_db: AsyncSession, clean_staged_eval_tables):
        """Should enforce unique stage_number per session."""
        session_id = str(uuid4())

        # Insert first stage
        await test_db.execute(
            text("""
                INSERT INTO staged_evaluation_results (
                    session_id, stage_number, start_turn, end_turn
                ) VALUES (:session_id, 1, 0, 5)
            """),
            {"session_id": session_id}
        )
        await test_db.commit()

        # Try to insert duplicate stage - should fail
        with pytest.raises(Exception) as exc_info:
            await test_db.execute(
                text("""
                    INSERT INTO staged_evaluation_results (
                        session_id, stage_number, start_turn, end_turn
                    ) VALUES (:session_id, 1, 6, 10)
                """),
                {"session_id": session_id}
            )
            await test_db.commit()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_unique_session_in_comprehensive_reports(self, test_db: AsyncSession, clean_staged_eval_tables):
        """Should enforce unique session_id in comprehensive_reports."""
        session_id = str(uuid4())

        # Insert first report
        await test_db.execute(
            text("""
                INSERT INTO comprehensive_reports (session_id, total_stages)
                VALUES (:session_id, 3)
            """),
            {"session_id": session_id}
        )
        await test_db.commit()

        # Try to insert duplicate session - should fail
        with pytest.raises(Exception) as exc_info:
            await test_db.execute(
                text("""
                    INSERT INTO comprehensive_reports (session_id, total_stages)
                    VALUES (:session_id, 5)
                """),
                {"session_id": session_id}
            )
            await test_db.commit()

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()


class TestJSONBColumns:
    """Test JSONB column functionality."""

    @pytest.mark.asyncio
    async def test_jsonb_scores_storage(self, test_db: AsyncSession, clean_staged_eval_tables):
        """Should store and retrieve JSONB scores correctly."""
        session_id = str(uuid4())
        scores = {"professionalism": 85, "communication": 90, "overall": 87}

        await test_db.execute(
            text("""
                INSERT INTO staged_evaluation_results (
                    session_id, stage_number, start_turn, end_turn, scores
                ) VALUES (:session_id, 1, 0, 5, :scores)
            """),
            {"session_id": session_id, "scores": str(scores).replace("'", '"')}
        )
        await test_db.commit()

        # Retrieve and verify JSONB
        result = await test_db.execute(
            text("""
                SELECT scores->>'professionalism' as prof
                FROM staged_evaluation_results
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "85"

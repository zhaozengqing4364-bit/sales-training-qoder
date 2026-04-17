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


@pytest_asyncio.fixture(autouse=True)
async def postgres_only(test_db: AsyncSession):
    """These schema assertions rely on PostgreSQL system catalogs and JSONB behavior."""
    dialect_name = test_db.bind.dialect.name if test_db.bind else ""
    if dialect_name != "postgresql":
        pytest.skip("PostgreSQL-only staged evaluation DB tests")


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

        expected_columns = {
            "id",
            "session_id",
            "stage_number",
            "start_turn",
            "end_turn",
            "created_at",
            "scores",
            "strengths",
            "weaknesses",
            "suggestions",
            "summary",
        }
        legacy_columns = {
            "timestamp",
            "key_insights",
            "improvement_suggestions",
            "stage_summary",
            "comparison_with_previous",
            "is_fallback",
            "cost_tokens",
            "processing_time_ms",
        }

        assert expected_columns.issubset(columns)
        assert legacy_columns.isdisjoint(columns)

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
    async def test_insert_and_retrieve(
        self, test_db: AsyncSession, clean_staged_eval_tables
    ):
        """Should be able to insert and retrieve staged evaluation."""
        session_id = str(uuid4())

        await test_db.execute(
            text("""
                INSERT INTO staged_evaluation_results (
                    session_id, stage_number, start_turn, end_turn,
                    scores, strengths, weaknesses, suggestions, summary
                ) VALUES (
                    :session_id, 1, 0, 5,
                    '{"professionalism": 85, "communication": 90}',
                    '["Good clarity", "Strong points"]',
                    '["Needs more data", "Slow response"]',
                    '["Practice more"]',
                    'Stage 1 summary text'
                )
            """),
            {"session_id": session_id},
        )
        await test_db.commit()

        # Retrieve the record
        result = await test_db.execute(
            text("""
                SELECT session_id, stage_number, scores, strengths
                FROM staged_evaluation_results
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
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

        expected_columns = {
            "session_id",
            "created_at",
            "overall_score",
            "dimension_scores",
            "stage_summaries",
            "key_strengths",
            "key_improvements",
            "detailed_feedback",
            "recommendations",
        }
        legacy_columns = {
            "id",
            "generated_at",
            "total_stages",
            "total_turns",
            "overall_assessment",
            "priority_improvements",
            "trend_summary",
            "personalized_advice",
            "practice_recommendations",
            "estimated_skill_level",
            "trend_analysis",
            "score_timeline",
            "is_fallback",
            "comparison_to_baseline",
        }

        assert expected_columns.issubset(columns)
        assert legacy_columns.isdisjoint(columns)

    @pytest.mark.asyncio
    async def test_session_id_is_primary_key(self, test_db: AsyncSession):
        """Should use session_id as the canonical primary key."""
        result = await test_db.execute(
            text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = 'comprehensive_reports'
                  AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.ordinal_position
            """)
        )
        pk_columns = [row[0] for row in result.fetchall()]
        assert pk_columns == ["session_id"]

    @pytest.mark.asyncio
    async def test_insert_and_retrieve(
        self, test_db: AsyncSession, clean_staged_eval_tables
    ):
        """Should be able to insert and retrieve comprehensive report."""
        session_id = str(uuid4())

        await test_db.execute(
            text("""
                INSERT INTO comprehensive_reports (
                    session_id, overall_score, dimension_scores,
                    stage_summaries, key_strengths, key_improvements,
                    detailed_feedback, recommendations
                ) VALUES (
                    :session_id, 87.5,
                    '[{"name": "communication", "score": 87.5, "weight": 0.25, "description": "Communication"}]',
                    '[{"stage_number": 1, "summary": "Stage 1 summary text"}]',
                    '["Strength 1", "Strength 2"]',
                    '["Improvement 1"]',
                    'Overall assessment text',
                    '["Recommendation 1"]'
                )
            """),
            {"session_id": session_id},
        )
        await test_db.commit()

        # Retrieve the record
        result = await test_db.execute(
            text("""
                SELECT session_id, overall_score, detailed_feedback
                FROM comprehensive_reports
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == session_id
        assert row[1] == 87.5
        assert row[2] == "Overall assessment text"


class TestStagedEvaluationConstraints:
    """Test database constraints."""

    @pytest.mark.asyncio
    async def test_unique_stage_per_session(
        self, test_db: AsyncSession, clean_staged_eval_tables
    ):
        """Should enforce unique stage_number per session."""
        session_id = str(uuid4())

        # Insert first stage
        await test_db.execute(
            text("""
                INSERT INTO staged_evaluation_results (
                    session_id, stage_number, start_turn, end_turn
                ) VALUES (:session_id, 1, 0, 5)
            """),
            {"session_id": session_id},
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
                {"session_id": session_id},
            )
            await test_db.commit()

        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_unique_session_in_comprehensive_reports(
        self, test_db: AsyncSession, clean_staged_eval_tables
    ):
        """Should enforce unique session_id in comprehensive_reports."""
        session_id = str(uuid4())

        # Insert first report
        await test_db.execute(
            text("""
                INSERT INTO comprehensive_reports (session_id, overall_score)
                VALUES (:session_id, 3)
            """),
            {"session_id": session_id},
        )
        await test_db.commit()

        # Try to insert duplicate session - should fail
        with pytest.raises(Exception) as exc_info:
            await test_db.execute(
                text("""
                    INSERT INTO comprehensive_reports (session_id, overall_score)
                    VALUES (:session_id, 5)
                """),
                {"session_id": session_id},
            )
            await test_db.commit()

        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )


class TestJSONBColumns:
    """Test JSONB column functionality."""

    @pytest.mark.asyncio
    async def test_jsonb_scores_storage(
        self, test_db: AsyncSession, clean_staged_eval_tables
    ):
        """Should store and retrieve JSONB scores correctly."""
        session_id = str(uuid4())
        scores = {"professionalism": 85, "communication": 90, "overall": 87}

        await test_db.execute(
            text("""
                INSERT INTO staged_evaluation_results (
                    session_id, stage_number, start_turn, end_turn, scores
                ) VALUES (:session_id, 1, 0, 5, :scores)
            """),
            {"session_id": session_id, "scores": str(scores).replace("'", '"')},
        )
        await test_db.commit()

        # Retrieve and verify JSONB
        result = await test_db.execute(
            text("""
                SELECT scores->>'professionalism' as prof
                FROM staged_evaluation_results
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "85"

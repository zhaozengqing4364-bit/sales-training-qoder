from __future__ import annotations

import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_newcomer_orchestration_tables_match_runtime_metadata(test_engine):
    def collect(sync_connection):
        inspector = inspect(sync_connection)
        return {
            table: {
                "columns": {item["name"] for item in inspector.get_columns(table)},
                "indexes": {item["name"] for item in inspector.get_indexes(table)},
                "checks": {item["name"] for item in inspector.get_check_constraints(table)},
            }
            for table in (
                "newcomer_training_enrollments",
                "newcomer_training_activity_attempts",
            )
        }

    async with test_engine.connect() as connection:
        schema = await connection.run_sync(collect)
    assert "path_revision_id" in schema["newcomer_training_enrollments"]["columns"]
    assert "activity_snapshot" in schema["newcomer_training_activity_attempts"]["columns"]
    assert "uq_newcomer_training_active_enrollment" in schema["newcomer_training_enrollments"]["indexes"]
    assert "uq_newcomer_training_attempt_client_token" in schema["newcomer_training_activity_attempts"]["indexes"]
    assert "ck_newcomer_training_activity_type" in schema["newcomer_training_activity_attempts"]["checks"]

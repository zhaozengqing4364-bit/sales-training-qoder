from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


def _create_legacy_personas_schema(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE personas (
                        id VARCHAR(36) PRIMARY KEY,
                        system_prompt TEXT,
                        knowledge_base_ids TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO personas (id, system_prompt, knowledge_base_ids)
                    VALUES ('persona-1', 'legacy prompt', '["kb-1"]')
                    """
                )
            )
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_production_startup_refuses_to_patch_legacy_personas_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-production.db"
    _create_legacy_personas_schema(db_path)

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ENVIRONMENT", "production")

    db_session = _load_db_session_module()

    with pytest.raises(RuntimeError, match="Run Alembic migration 20260216_0100_015"):
        await db_session.init_db()


def _load_db_session_module():
    import common.db.session as db_session

    return importlib.reload(db_session)


def _load_repair_legacy_schema_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "repair_legacy_schema.py"
    spec = importlib.util.spec_from_file_location("repair_legacy_schema", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_repair_script_updates_legacy_personas_schema_explicitly(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-repair.db"
    _create_legacy_personas_schema(db_path)

    repair_module = _load_repair_legacy_schema_module()

    sync_url = repair_module._to_sync_database_url(f"sqlite+aiosqlite:///{db_path}")
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            repair_module._repair_startup_schema_compatibility(conn)

        with engine.begin() as conn:
            columns = {column["name"] for column in inspect(conn).get_columns("personas")}
            assert "persona_policy" in columns
            payload = conn.execute(
                text("SELECT persona_policy FROM personas WHERE id = 'persona-1'")
            ).scalar_one()
            assert payload is not None
            assert "legacy prompt" in str(payload)
    finally:
        engine.dispose()

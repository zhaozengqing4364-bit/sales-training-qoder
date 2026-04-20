from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import agent.models  # noqa: F401
from common.db.models import (
    Base,
    KnowledgeAnswerabilityProfile,
    KnowledgeConfigVersion,
    KnowledgeEntityAlias,
    KnowledgeIntentRule,
    KnowledgeQueryProfile,
    KnowledgeRankingProfile,
)
from common.knowledge_engine.config_repo import KnowledgeAnswerConfigRepository

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "seed_knowledge_answer_config.py"


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _load_seed_module():
    assert SCRIPT_PATH.exists(), "seed script is missing"
    spec = importlib.util.spec_from_file_location("seed_knowledge_answer_config", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_script_inserts_active_config_snapshot_and_minimal_profiles(db_session: Session):
    seed_module = _load_seed_module()

    seed_result = seed_module.seed_knowledge_answer_config(
        db_session,
        version_name="seed-test-v1",
    )

    db_session.expire_all()

    active_version = db_session.query(KnowledgeConfigVersion).filter_by(status="active").one()
    assert active_version.version_name == "seed-test-v1"
    assert active_version.enabled is True

    assert db_session.query(KnowledgeQueryProfile).count() >= 4
    assert db_session.query(KnowledgeIntentRule).count() >= 4
    assert db_session.query(KnowledgeEntityAlias).count() >= 1
    assert db_session.query(KnowledgeRankingProfile).count() >= 4
    assert db_session.query(KnowledgeAnswerabilityProfile).count() >= 4

    snapshot = KnowledgeAnswerConfigRepository(db_session).get_active_config()
    assert snapshot is not None
    assert snapshot.config_version_name == "seed-test-v1"
    assert "product_overview" in snapshot.query_profiles
    assert snapshot.query_profiles["product_overview"].stop_after_first_success is True
    assert any(alias.alias == "世袭科技" for alias in snapshot.entity_aliases)
    assert "pricing_lookup" in snapshot.answerability_profiles

    assert seed_result["created"] is True
    assert seed_result["version_name"] == "seed-test-v1"


def test_seed_script_is_idempotent_for_same_version_name(db_session: Session):
    seed_module = _load_seed_module()

    first = seed_module.seed_knowledge_answer_config(db_session, version_name="seed-test-v1")
    second = seed_module.seed_knowledge_answer_config(db_session, version_name="seed-test-v1")

    assert first["version_name"] == "seed-test-v1"
    assert second["version_name"] == "seed-test-v1"
    assert db_session.query(KnowledgeConfigVersion).count() == 1
    assert db_session.query(KnowledgeQueryProfile).filter_by(profile_key="product_overview").count() == 1
    assert db_session.query(KnowledgeIntentRule).filter_by(intent_key="company_intro").count() == 1
    assert db_session.query(KnowledgeEntityAlias).filter_by(alias="世袭科技").count() == 1

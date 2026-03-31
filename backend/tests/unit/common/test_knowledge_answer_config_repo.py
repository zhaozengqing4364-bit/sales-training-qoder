from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Register FK targets used by PracticeSession before create_all.
import agent.models  # noqa: F401
from common.db import models as db_models
from common.db.models import Base
from common.knowledge_engine.config_repo import KnowledgeAnswerConfigRepository


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine) -> Session:
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def _create_config_version(
    db_session: Session,
    *,
    version_name: str,
    status: str = "active",
    enabled: bool = True,
):
    config_version = db_models.KnowledgeConfigVersion(
        version_name=version_name,
        status=status,
        enabled=enabled,
        notes=f"seed:{uuid.uuid4()}",
    )
    db_session.add(config_version)
    db_session.flush()
    return config_version


def _seed_active_config_snapshot(db_session: Session) -> str:
    inactive_version = _create_config_version(
        db_session,
        version_name="draft-v0",
        status="draft",
    )
    active_version = _create_config_version(
        db_session,
        version_name="active-v1",
        status="active",
    )

    db_session.add_all(
        [
            db_models.KnowledgeQueryProfile(
                config_version_id=inactive_version.id,
                profile_key="ignored_profile",
                rewrite_strategy="single_query",
                max_rewrite_queries=1,
                stop_after_first_success=False,
            ),
            db_models.KnowledgeQueryProfile(
                config_version_id=active_version.id,
                profile_key="product_overview",
                description="Product overview answers",
                rewrite_strategy="multi_query",
                max_rewrite_queries=3,
                stop_after_first_success=True,
                enabled=True,
            ),
            db_models.KnowledgeQueryProfile(
                config_version_id=active_version.id,
                profile_key="disabled_profile",
                rewrite_strategy="single_query",
                max_rewrite_queries=1,
                stop_after_first_success=False,
                enabled=False,
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=active_version.id,
                intent_key="pricing_query",
                priority=20,
                match_type="keyword_contains",
                pattern="价格",
                profile_key="product_overview",
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=active_version.id,
                intent_key="company_intro",
                priority=10,
                match_type="regex",
                pattern=".*石犀.*",
                profile_key="product_overview",
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=active_version.id,
                intent_key="disabled_rule",
                priority=1,
                match_type="keyword_contains",
                pattern="忽略",
                profile_key="product_overview",
                enabled=False,
            ),
            db_models.KnowledgeEntityAlias(
                config_version_id=active_version.id,
                canonical_entity="石犀科技",
                alias="实习科技",
                entity_type="company",
                confidence=0.92,
            ),
            db_models.KnowledgeEntityAlias(
                config_version_id=active_version.id,
                canonical_entity="销售训练平台",
                alias="训练平台",
                entity_type="product",
                confidence=0.88,
                enabled=False,
            ),
            db_models.KnowledgeRankingProfile(
                config_version_id=active_version.id,
                profile_key="default_ranking",
                title_exact_boost=2.0,
                entity_match_boost=1.5,
                doc_type_weights_json={"faq": 1.2},
                section_weights_json={"pricing": 1.4},
                min_pass_score=0.65,
                min_pass_score_keyword=0.55,
            ),
            db_models.KnowledgeAnswerabilityProfile(
                config_version_id=active_version.id,
                profile_key="default_answerability",
                required_slots_json=["definition", "capability"],
                optional_slots_json=["use_case"],
                sufficient_threshold=1.0,
                partial_threshold=0.5,
            ),
        ]
    )
    db_session.commit()
    return active_version.id


def test_repo_returns_none_when_no_enabled_active_version_exists(db_session: Session):
    _create_config_version(db_session, version_name="draft-v0", status="draft")
    _create_config_version(db_session, version_name="inactive-v1", status="active", enabled=False)
    db_session.commit()

    repo = KnowledgeAnswerConfigRepository(db_session)

    assert repo.get_active_config() is None


def test_repo_loads_normalized_active_config_snapshot_without_leaking_orm(db_session: Session):
    active_version_id = _seed_active_config_snapshot(db_session)

    repo = KnowledgeAnswerConfigRepository(db_session)
    snapshot = repo.get_active_config()

    assert snapshot is not None
    assert snapshot.config_version_id == active_version_id
    assert snapshot.config_version_name == "active-v1"
    assert snapshot.profile_source == "database"

    assert list(snapshot.query_profiles) == ["product_overview"]
    query_profile = snapshot.query_profiles["product_overview"]
    assert query_profile.profile_key == "product_overview"
    assert query_profile.description == "Product overview answers"
    assert query_profile.rewrite_strategy == "multi_query"
    assert query_profile.max_rewrite_queries == 3
    assert query_profile.stop_after_first_success is True
    assert query_profile.profile_source == "database"

    assert [rule.intent_key for rule in snapshot.intent_rules] == [
        "company_intro",
        "pricing_query",
    ]
    assert snapshot.intent_rules[0].priority == 10
    assert snapshot.intent_rules[1].match_type == "keyword_contains"
    assert snapshot.intent_rules[1].pattern == "价格"

    assert len(snapshot.entity_aliases) == 1
    alias = snapshot.entity_aliases[0]
    assert alias.canonical_entity == "石犀科技"
    assert alias.alias == "实习科技"
    assert alias.entity_type == "company"
    assert alias.confidence == pytest.approx(0.92)

    ranking_profile = snapshot.ranking_profiles["default_ranking"]
    assert ranking_profile.title_exact_boost == pytest.approx(2.0)
    assert ranking_profile.entity_match_boost == pytest.approx(1.5)
    assert ranking_profile.doc_type_weights == {"faq": 1.2}
    assert ranking_profile.section_weights == {"pricing": 1.4}
    assert ranking_profile.min_pass_score == pytest.approx(0.65)
    assert ranking_profile.min_pass_score_keyword == pytest.approx(0.55)
    assert ranking_profile.profile_source == "database"

    answerability_profile = snapshot.answerability_profiles["default_answerability"]
    assert answerability_profile.required_slots == ["definition", "capability"]
    assert answerability_profile.optional_slots == ["use_case"]
    assert answerability_profile.sufficient_threshold == pytest.approx(1.0)
    assert answerability_profile.partial_threshold == pytest.approx(0.5)
    assert answerability_profile.profile_source == "database"

    assert not hasattr(snapshot, "_sa_instance_state")
    assert not hasattr(query_profile, "_sa_instance_state")
    assert not hasattr(alias, "_sa_instance_state")
    assert not hasattr(ranking_profile, "_sa_instance_state")
    assert not hasattr(answerability_profile, "_sa_instance_state")

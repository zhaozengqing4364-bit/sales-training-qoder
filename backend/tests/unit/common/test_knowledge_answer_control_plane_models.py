from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Register FK targets used by PracticeSession before create_all.
import agent.models  # noqa: F401
from common.db import models as db_models
from common.db.models import Base, PracticeSession, Scenario, User


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


@pytest.fixture
def practice_session(db_session: Session) -> PracticeSession:
    user = User(wechat_user_id=f"wechat_{uuid.uuid4()}", name="Knowledge QA Tester")
    scenario = Scenario(scenario_type="sales", name="Knowledge QA Scenario")
    db_session.add_all([user, scenario])
    db_session.flush()

    session = PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="in_progress",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def knowledge_control_plane_migration_path() -> Path:
    versions_dir = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    matches = sorted(versions_dir.glob("*_knowledge_answer_control_plane.py"))
    assert matches, "knowledge answer control plane migration file is missing"
    return matches[-1]


def _create_config_version(db_session: Session, version_name: str = "baseline-v1"):
    config_version = db_models.KnowledgeConfigVersion(
        version_name=version_name,
        status="active",
        notes="initial control plane",
    )
    db_session.add(config_version)
    db_session.commit()
    db_session.refresh(config_version)
    return config_version


def test_control_plane_migration_file_declares_expected_tables(
    knowledge_control_plane_migration_path: Path,
):
    migration_source = knowledge_control_plane_migration_path.read_text(encoding="utf-8")

    for table_name in (
        "knowledge_config_versions",
        "knowledge_query_profiles",
        "knowledge_intent_rules",
        "knowledge_entity_aliases",
        "knowledge_ranking_profiles",
        "knowledge_answerability_profiles",
        "knowledge_answer_runs",
        "knowledge_answer_run_steps",
    ):
        assert f'"{table_name}"' in migration_source


def test_control_plane_migration_revises_latest_backend_revision(
    knowledge_control_plane_migration_path: Path,
):
    spec = importlib.util.spec_from_file_location(
        "knowledge_answer_control_plane_migration",
        knowledge_control_plane_migration_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.down_revision == "20260328_1000_022"


def test_config_version_model_tracks_version_name_and_status(db_session: Session):
    config_version = _create_config_version(db_session)

    assert config_version.version_name == "baseline-v1"
    assert config_version.status == "active"
    assert config_version.enabled is True
    assert config_version.created_at is not None


def test_query_profile_model_has_profile_key_and_strategy_fields(db_session: Session):
    config_version = _create_config_version(db_session)

    profile = db_models.KnowledgeQueryProfile(
        config_version_id=config_version.id,
        profile_key="product_overview",
        description="Product overview answers",
        rewrite_strategy="multi_query",
        max_rewrite_queries=3,
        stop_after_first_success=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert profile.profile_key == "product_overview"
    assert profile.rewrite_strategy == "multi_query"
    assert profile.max_rewrite_queries == 3
    assert profile.stop_after_first_success is True


def test_intent_rule_model_has_match_fields_and_profile_key(db_session: Session):
    config_version = _create_config_version(db_session)

    rule = db_models.KnowledgeIntentRule(
        config_version_id=config_version.id,
        intent_key="pricing_query",
        priority=10,
        match_type="keyword_contains",
        pattern="价格",
        profile_key="pricing",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    assert rule.intent_key == "pricing_query"
    assert rule.priority == 10
    assert rule.match_type == "keyword_contains"
    assert rule.profile_key == "pricing"


def test_entity_alias_model_persists_alias_and_canonical_entity(db_session: Session):
    config_version = _create_config_version(db_session)

    alias = db_models.KnowledgeEntityAlias(
        config_version_id=config_version.id,
        canonical_entity="石犀科技",
        alias="实习科技",
        entity_type="company",
        confidence=0.92,
    )
    db_session.add(alias)
    db_session.commit()
    db_session.refresh(alias)

    assert alias.canonical_entity == "石犀科技"
    assert alias.alias == "实习科技"
    assert alias.entity_type == "company"
    assert alias.confidence == pytest.approx(0.92)


def test_ranking_profile_model_has_weight_and_threshold_fields(db_session: Session):
    config_version = _create_config_version(db_session)

    profile = db_models.KnowledgeRankingProfile(
        config_version_id=config_version.id,
        profile_key="default_ranking",
        title_exact_boost=2.0,
        entity_match_boost=1.5,
        doc_type_weights_json={"faq": 1.2},
        section_weights_json={"pricing": 1.4},
        min_pass_score=0.65,
        min_pass_score_keyword=0.55,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert profile.profile_key == "default_ranking"
    assert profile.doc_type_weights_json == {"faq": 1.2}
    assert profile.section_weights_json == {"pricing": 1.4}
    assert profile.min_pass_score == pytest.approx(0.65)
    assert profile.min_pass_score_keyword == pytest.approx(0.55)


def test_answerability_profile_model_has_slot_lists_and_thresholds(db_session: Session):
    config_version = _create_config_version(db_session)

    profile = db_models.KnowledgeAnswerabilityProfile(
        config_version_id=config_version.id,
        profile_key="product_overview_answerability",
        required_slots_json=["definition", "capability"],
        optional_slots_json=["use_case"],
        sufficient_threshold=1.0,
        partial_threshold=0.5,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert profile.profile_key == "product_overview_answerability"
    assert profile.required_slots_json == ["definition", "capability"]
    assert profile.optional_slots_json == ["use_case"]
    assert profile.sufficient_threshold == pytest.approx(1.0)
    assert profile.partial_threshold == pytest.approx(0.5)


def test_answer_run_model_captures_query_and_config_version(db_session: Session, practice_session: PracticeSession):
    config_version = _create_config_version(db_session)

    answer_run = db_models.KnowledgeAnswerRun(
        session_id=practice_session.session_id,
        config_version_id=config_version.id,
        entrypoint="stepfun_realtime",
        query_text="介绍一下石犀科技",
        answerability="partial",
        final_status="completed",
        citations_json=[{"document_title": "产品手册"}],
        retrieval_summary_json={"candidate_count": 3},
    )
    db_session.add(answer_run)
    db_session.commit()
    db_session.refresh(answer_run)

    assert answer_run.session_id == practice_session.session_id
    assert answer_run.entrypoint == "stepfun_realtime"
    assert answer_run.query_text == "介绍一下石犀科技"
    assert answer_run.answerability == "partial"
    assert answer_run.citations_json == [{"document_title": "产品手册"}]


def test_answer_run_step_model_captures_payloads_and_status(db_session: Session, practice_session: PracticeSession):
    config_version = _create_config_version(db_session)
    answer_run = db_models.KnowledgeAnswerRun(
        session_id=practice_session.session_id,
        config_version_id=config_version.id,
        entrypoint="stepfun_realtime",
        query_text="介绍一下石犀科技",
        answerability="sufficient",
        final_status="completed",
    )
    db_session.add(answer_run)
    db_session.commit()
    db_session.refresh(answer_run)

    run_step = db_models.KnowledgeAnswerRunStep(
        answer_run_id=answer_run.id,
        step_name="retrieve_candidates",
        step_order=1,
        status="completed",
        input_payload={"query": "石犀科技"},
        output_payload={"candidate_count": 5},
        duration_ms=47,
    )
    db_session.add(run_step)
    db_session.commit()
    db_session.refresh(run_step)

    assert run_step.answer_run_id == answer_run.id
    assert run_step.step_name == "retrieve_candidates"
    assert run_step.status == "completed"
    assert run_step.output_payload == {"candidate_count": 5}
    assert run_step.duration_ms == 47

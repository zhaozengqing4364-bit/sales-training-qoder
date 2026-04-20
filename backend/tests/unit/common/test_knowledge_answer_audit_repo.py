from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import agent.models  # noqa: F401
from common.db.models import (
    Base,
    KnowledgeAnswerRun,
    KnowledgeAnswerRunStep,
    KnowledgeConfigVersion,
    PracticeSession,
    Scenario,
    User,
)
from common.knowledge_engine.audit_repo import KnowledgeAnswerAuditRepository
from common.knowledge_engine.schemas import KnowledgeAuditStep


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
    user = User(wechat_user_id=f"wechat_{uuid.uuid4()}", name="Knowledge Audit Tester")
    scenario = Scenario(scenario_type="sales", name="Knowledge Audit Scenario")
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
def config_version(db_session: Session) -> KnowledgeConfigVersion:
    version = KnowledgeConfigVersion(
        version_name="knowledge-audit-v1",
        status="active",
        notes="audit seed",
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    return version


def test_audit_repo_persists_run_and_ordered_steps(
    db_session: Session,
    practice_session: PracticeSession,
    config_version: KnowledgeConfigVersion,
):
    repo = KnowledgeAnswerAuditRepository(db_session)

    persisted = repo.create_run(
        session_id=practice_session.session_id,
        config_version_id=config_version.id,
        entrypoint="stepfun_realtime",
        query_text="请介绍一下石犀科技",
        answerability="partial",
        final_status="completed",
        blocked_reason=None,
        citations=[{"document_title": "石犀科技产品手册", "snippet": "石犀科技是一家销售训练平台。"}],
        retrieval_summary={"hit_count": 1, "executed_query_count": 2},
        steps=[
            KnowledgeAuditStep(
                step_name="resolve",
                status="completed",
                duration_ms=3,
                input_payload={"query": "请介绍一下世袭科技"},
                output_payload={"normalized_query": "请介绍一下石犀科技"},
            ),
            KnowledgeAuditStep(
                step_name="assemble",
                status="completed",
                duration_ms=4,
                input_payload={"candidate_count": 1},
                output_payload={"citation_count": 1},
            ),
        ],
    )

    assert persisted.id
    assert persisted.entrypoint == "stepfun_realtime"
    assert persisted.answerability == "partial"
    assert persisted.citations_json[0]["document_title"] == "石犀科技产品手册"
    assert persisted.retrieval_summary_json == {"hit_count": 1, "executed_query_count": 2}

    db_session.expire_all()
    stored_run = db_session.execute(
        select(KnowledgeAnswerRun).where(KnowledgeAnswerRun.id == persisted.id)
    ).scalar_one()
    stored_steps = list(
        db_session.execute(
            select(KnowledgeAnswerRunStep)
            .where(KnowledgeAnswerRunStep.answer_run_id == persisted.id)
            .order_by(KnowledgeAnswerRunStep.step_order.asc())
        ).scalars()
    )

    assert stored_run.query_text == "请介绍一下石犀科技"
    assert [step.step_name for step in stored_steps] == ["resolve", "assemble"]
    assert [step.step_order for step in stored_steps] == [1, 2]
    assert stored_steps[0].input_payload == {"query": "请介绍一下世袭科技"}
    assert stored_steps[1].output_payload == {"citation_count": 1}


def test_audit_repo_normalizes_invalid_payloads_to_safe_defaults(
    db_session: Session,
    practice_session: PracticeSession,
):
    repo = KnowledgeAnswerAuditRepository(db_session)

    persisted = repo.create_run(
        session_id=practice_session.session_id,
        config_version_id=None,
        entrypoint="runtime_diagnostics",
        query_text="知识库状态",
        answerability="blocked",
        final_status="failed",
        blocked_reason="retrieval_failed",
        citations=["not-a-dict"],
        retrieval_summary=["not-a-dict"],
        steps=[],
    )

    assert persisted.citations_json == []
    assert persisted.retrieval_summary_json == {}

    stored_steps = list(
        db_session.execute(
            select(KnowledgeAnswerRunStep).where(
                KnowledgeAnswerRunStep.answer_run_id == persisted.id
            )
        ).scalars()
    )
    assert stored_steps == []

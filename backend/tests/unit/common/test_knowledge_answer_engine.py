from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import agent.models  # noqa: F401
from common.db import models as db_models
from common.db.models import Base, PracticeSession, Scenario, User
from common.error_handling.result import Result
from common.knowledge_engine.answerability import KnowledgeAnswerabilityEvaluator
from common.knowledge_engine.assembler import KnowledgeAnswerAssembler
from common.knowledge_engine.audit_repo import KnowledgeAnswerAuditRepository
from common.knowledge_engine.config_repo import KnowledgeAnswerConfigRepository
from common.knowledge_engine.engine import KnowledgeAnswerEngine
from common.knowledge_engine.entity_resolver import KnowledgeEntityResolver
from common.knowledge_engine.haystack_adapter import KnowledgeHaystackAdapter
from common.knowledge_engine.intent_classifier import KnowledgeIntentClassifier
from common.knowledge_engine.reranker import KnowledgeReranker
from common.knowledge_engine.retrieval_planner import KnowledgeRetrievalPlanner
from common.knowledge_engine.schemas import KnowledgeAnswerRequest


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
    user = User(wechat_user_id=f"wechat_{uuid.uuid4()}", name="Knowledge Engine Tester")
    scenario = Scenario(scenario_type="sales", name="Knowledge Engine Scenario")
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


def _seed_runtime_config(db_session: Session) -> None:
    version = db_models.KnowledgeConfigVersion(
        version_name="runtime-v1",
        status="active",
        enabled=True,
        notes="runtime seed",
    )
    db_session.add(version)
    db_session.flush()
    db_session.add_all(
        [
            db_models.KnowledgeQueryProfile(
                config_version_id=version.id,
                profile_key="product_overview",
                description="产品介绍",
                rewrite_strategy="multi_query",
                max_rewrite_queries=4,
                stop_after_first_success=True,
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=version.id,
                intent_key="company_intro",
                priority=10,
                match_type="regex",
                pattern="介绍一下.*石犀科技",
                profile_key="product_overview",
            ),
            db_models.KnowledgeEntityAlias(
                config_version_id=version.id,
                canonical_entity="石犀科技",
                alias="世袭科技",
                entity_type="company",
                confidence=0.96,
            ),
            db_models.KnowledgeRankingProfile(
                config_version_id=version.id,
                profile_key="product_overview",
                title_exact_boost=0.25,
                entity_match_boost=0.2,
                doc_type_weights_json={"product": 0.18},
                section_weights_json={"overview": 0.14},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
            ),
            db_models.KnowledgeAnswerabilityProfile(
                config_version_id=version.id,
                profile_key="product_overview",
                required_slots_json=["definition", "capability"],
                optional_slots_json=["use_case"],
                sufficient_threshold=0.66,
                partial_threshold=0.5,
            ),
        ]
    )
    db_session.commit()


def test_engine_can_be_constructed_with_default_dependencies():
    engine = KnowledgeAnswerEngine()

    assert engine is not None


def test_engine_answer_runs_full_orchestration_and_persists_audit(
    db_session: Session,
    practice_session: PracticeSession,
):
    _seed_runtime_config(db_session)
    captured_queries: list[str] = []

    async def search_multiple(**kwargs):
        captured_queries.append(str(kwargs["query"]))
        query = str(kwargs["query"])
        if query == "石犀科技 产品介绍":
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_id": "doc-1",
                        "chunk_id": "chunk-1",
                        "document_title": "石犀科技产品手册",
                        "content": "石犀科技是一家销售训练平台，支持企业知识驱动演练。",
                        "snippet": "石犀科技是一家销售训练平台。",
                        "score": 0.52,
                        "retrieval_mode": "hybrid",
                        "slot_hits": ["definition", "capability"],
                        "metadata": {"doc_type": "product", "section": "overview"},
                    }
                ]
            )
        return Result.ok([])

    engine = KnowledgeAnswerEngine(
        config_repository=KnowledgeAnswerConfigRepository(db_session),
        entity_resolver=KnowledgeEntityResolver(),
        intent_classifier_factory=KnowledgeIntentClassifier,
        retrieval_planner_factory=KnowledgeRetrievalPlanner,
        haystack_adapter=KnowledgeHaystackAdapter(search_multiple=search_multiple),
        reranker=KnowledgeReranker(),
        answerability_evaluator_factory=KnowledgeAnswerabilityEvaluator,
        assembler=KnowledgeAnswerAssembler(),
        audit_repository=KnowledgeAnswerAuditRepository(db_session),
    )

    result = engine.answer(
        KnowledgeAnswerRequest(
            query="请介绍一下世袭科技",
            session_id=str(practice_session.session_id),
            scenario_type="sales",
            knowledge_base_ids=["kb-1"],
            entrypoint="stepfun_realtime",
            runtime_options={
                "top_k": 3,
                "similarity_threshold": 0.65,
                "enable_hybrid": True,
                "keyword_candidate_limit": 32,
                "embedding_timeout_ms": 0,
                "enable_rerank": True,
                "rerank_top_k": 8,
            },
        )
    )

    assert captured_queries == ["请介绍一下石犀科技", "石犀科技 产品介绍"]
    assert result.answerability == "sufficient"
    assert result.source_status == "ready"
    assert result.final_text == "根据知识库证据：\n1. 石犀科技是一家销售训练平台。"
    assert result.blocked_text is None
    assert result.rewritten_queries == ["请介绍一下石犀科技", "石犀科技 产品介绍"]
    assert result.citations[0].document_title == "石犀科技产品手册"
    assert result.retrieval_summary["config_version_id"]
    assert result.retrieval_summary["config_version_name"] == "runtime-v1"
    assert result.retrieval_summary["resolved_query"] == "请介绍一下石犀科技"
    assert result.retrieval_summary["profile_key"] == "product_overview"
    assert result.retrieval_summary["executed_query_count"] == 2
    assert result.audit_run_id

    persisted_run = db_session.get(db_models.KnowledgeAnswerRun, result.audit_run_id)
    assert persisted_run is not None
    assert persisted_run.entrypoint == "stepfun_realtime"
    assert persisted_run.answerability == "sufficient"
    assert persisted_run.retrieval_summary_json["resolved_query"] == "请介绍一下石犀科技"


def test_engine_blocks_when_retrieved_rows_do_not_support_user_query_terms(
    db_session: Session,
    practice_session: PracticeSession,
):
    _seed_runtime_config(db_session)
    version_id = db_session.query(db_models.KnowledgeConfigVersion.id).scalar()
    db_session.add(
        db_models.KnowledgeIntentRule(
            config_version_id=version_id,
            intent_key="internship_score_intro",
            priority=20,
            match_type="regex",
            pattern="介绍一下.*实习成绩",
            profile_key="product_overview",
        )
    )
    db_session.commit()
    captured_queries: list[str] = []

    async def search_multiple(**kwargs):
        captured_queries.append(str(kwargs["query"]))
        return Result.ok(
            [
                {
                    "knowledge_base_id": "kb-1",
                    "knowledge_base_name": "产品知识库",
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "document_title": "石犀科技产品手册",
                    "content": "石犀科技是成都本土的智慧城市解决方案提供商。",
                    "snippet": "石犀科技是成都本土的智慧城市解决方案提供商。",
                    "score": 0.92,
                    "retrieval_mode": "hybrid",
                    "slot_hits": ["definition", "capability", "use_case"],
                    "metadata": {"doc_type": "product", "section": "overview"},
                }
            ]
        )

    engine = KnowledgeAnswerEngine(
        config_repository=KnowledgeAnswerConfigRepository(db_session),
        entity_resolver=KnowledgeEntityResolver(),
        intent_classifier_factory=KnowledgeIntentClassifier,
        retrieval_planner_factory=KnowledgeRetrievalPlanner,
        haystack_adapter=KnowledgeHaystackAdapter(search_multiple=search_multiple),
        reranker=KnowledgeReranker(),
        answerability_evaluator_factory=KnowledgeAnswerabilityEvaluator,
        assembler=KnowledgeAnswerAssembler(),
        audit_repository=KnowledgeAnswerAuditRepository(db_session),
    )

    result = engine.answer(
        KnowledgeAnswerRequest(
            query="介绍一下实习成绩",
            session_id=str(practice_session.session_id),
            scenario_type="sales",
            knowledge_base_ids=["kb-1"],
            entrypoint="stepfun_realtime",
            runtime_options={
                "top_k": 3,
                "similarity_threshold": 0.65,
                "enable_hybrid": True,
                "keyword_candidate_limit": 32,
                "embedding_timeout_ms": 0,
                "enable_rerank": True,
                "rerank_top_k": 8,
            },
        )
    )

    assert captured_queries == ["介绍一下实习成绩"]
    assert result.answerability == "insufficient"
    assert result.final_text is None
    assert result.blocked_text is not None
    assert result.retrieval_summary["blocked_reason"] == "query_not_supported_by_evidence"


def test_engine_accepts_evidence_supported_by_runtime_asr_lexicon(
    db_session: Session,
    practice_session: PracticeSession,
):
    _seed_runtime_config(db_session)
    captured_queries: list[str] = []

    async def search_multiple(**kwargs):
        captured_queries.append(str(kwargs["query"]))
        return Result.ok(
            [
                {
                    "knowledge_base_id": "kb-1",
                    "knowledge_base_name": "产品知识库",
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "document_title": "石犀科技产品手册",
                    "content": "石犀科技是一家销售训练平台，支持企业知识驱动演练。",
                    "snippet": "石犀科技是一家销售训练平台。",
                    "score": 0.92,
                    "retrieval_mode": "hybrid",
                    "slot_hits": ["definition", "capability", "use_case"],
                    "metadata": {"doc_type": "product", "section": "overview"},
                }
            ]
        )

    engine = KnowledgeAnswerEngine(
        config_repository=KnowledgeAnswerConfigRepository(db_session),
        entity_resolver=KnowledgeEntityResolver(),
        intent_classifier_factory=KnowledgeIntentClassifier,
        retrieval_planner_factory=KnowledgeRetrievalPlanner,
        haystack_adapter=KnowledgeHaystackAdapter(search_multiple=search_multiple),
        reranker=KnowledgeReranker(),
        answerability_evaluator_factory=KnowledgeAnswerabilityEvaluator,
        assembler=KnowledgeAnswerAssembler(),
        audit_repository=KnowledgeAnswerAuditRepository(db_session),
    )

    result = engine.answer(
        KnowledgeAnswerRequest(
            query="请介绍一下实习科技",
            session_id=str(practice_session.session_id),
            scenario_type="sales",
            knowledge_base_ids=["kb-1"],
            entrypoint="stepfun_realtime",
            runtime_options={
                "top_k": 3,
                "similarity_threshold": 0.65,
                "enable_hybrid": True,
                "keyword_candidate_limit": 32,
                "embedding_timeout_ms": 0,
                "enable_rerank": True,
                "rerank_top_k": 8,
                "tool_policy": {
                    "transcript_normalization_lexicon": [
                        {
                            "canonical_term": "石犀",
                            "aliases": ["实习"],
                        }
                    ]
                },
            },
        )
    )

    assert captured_queries == ["请介绍一下石犀科技"]
    assert result.answerability == "sufficient"
    assert result.final_text == "根据知识库证据：\n1. 石犀科技是一家销售训练平台。"
    assert result.blocked_text is None
    assert result.retrieval_summary["resolved_query"] == "请介绍一下石犀科技"
    assert result.retrieval_summary["entity_resolution"]["matches"][0]["matched_text"] == "实习"
    assert result.retrieval_summary["entity_resolution"]["matches"][0]["match_source"] == "alias"


def test_engine_answer_returns_placeholder_contract_with_observability_fields_when_no_config(
    db_session: Session,
):
    engine = KnowledgeAnswerEngine(
        config_repository=KnowledgeAnswerConfigRepository(db_session),
    )

    result = engine.answer(
        KnowledgeAnswerRequest(
            query="介绍一下企业版",
            knowledge_base_ids=["kb-1"],
            entrypoint="stepfun_realtime",
        )
    )

    assert result.final_text is None
    assert result.blocked_text is None
    assert result.answerability == "unanswered"
    assert result.source_status == "not_run"
    assert result.citations == []
    assert result.rewritten_queries == []
    assert result.unsupported_claims == []
    assert result.audit_run_id is None
    assert result.retrieval_summary == {}

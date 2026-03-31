from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import agent.models  # noqa: F401
from common.db import models as db_models
from common.db.models import Base
from common.error_handling.result import Result
from common.knowledge_engine.config_repo import KnowledgeAnswerConfigRepository
from common.knowledge_engine.engine import KnowledgeAnswerEngine
from common.knowledge_engine.evaluation import (
    KnowledgeAnswerEngineEvaluationHarness,
    KnowledgeAnswerEvalCase,
)
from common.knowledge_engine.haystack_adapter import KnowledgeHaystackAdapter

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "knowledge_answer_eval_cases.json"


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


@pytest.fixture
def raw_eval_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def eval_cases(raw_eval_cases: list[dict[str, Any]]) -> list[KnowledgeAnswerEvalCase]:
    return [KnowledgeAnswerEvalCase.from_dict(case) for case in raw_eval_cases]


@pytest.fixture
def seeded_config(db_session: Session) -> None:
    version = db_models.KnowledgeConfigVersion(
        version_name="eval-v1",
        status="active",
        enabled=True,
        notes="evaluation seed",
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
            db_models.KnowledgeQueryProfile(
                config_version_id=version.id,
                profile_key="pricing_lookup",
                description="价格问答",
                rewrite_strategy="single_query",
                max_rewrite_queries=1,
                stop_after_first_success=False,
            ),
            db_models.KnowledgeQueryProfile(
                config_version_id=version.id,
                profile_key="version_compare",
                description="版本比较",
                rewrite_strategy="multi_query",
                max_rewrite_queries=3,
                stop_after_first_success=False,
            ),
            db_models.KnowledgeQueryProfile(
                config_version_id=version.id,
                profile_key="coaching_guidance",
                description="辅导建议",
                rewrite_strategy="single_query",
                max_rewrite_queries=1,
                stop_after_first_success=False,
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=version.id,
                intent_key="company_intro",
                priority=10,
                match_type="regex",
                pattern="介绍一下.*石犀科技",
                profile_key="product_overview",
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=version.id,
                intent_key="pricing_query",
                priority=20,
                match_type="entity_keyword_contains",
                pattern="价格|报价|多少钱",
                profile_key="pricing_lookup",
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=version.id,
                intent_key="version_compare",
                priority=30,
                match_type="keyword_contains",
                pattern="区别|对比|版本",
                profile_key="version_compare",
            ),
            db_models.KnowledgeIntentRule(
                config_version_id=version.id,
                intent_key="coaching_guidance",
                priority=40,
                match_type="keyword_contains",
                pattern="怎么讲|怎么回答|话术|辅导",
                profile_key="coaching_guidance",
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
                doc_type_weights_json={"product": 0.18, "faq": 0.05},
                section_weights_json={"overview": 0.14, "pricing": 0.02},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
            ),
            db_models.KnowledgeRankingProfile(
                config_version_id=version.id,
                profile_key="pricing_lookup",
                title_exact_boost=0.2,
                entity_match_boost=0.15,
                doc_type_weights_json={"pricing": 0.22},
                section_weights_json={"pricing": 0.14},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
            ),
            db_models.KnowledgeRankingProfile(
                config_version_id=version.id,
                profile_key="version_compare",
                title_exact_boost=0.2,
                entity_match_boost=0.15,
                doc_type_weights_json={"comparison": 0.22},
                section_weights_json={"comparison": 0.12},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
            ),
            db_models.KnowledgeRankingProfile(
                config_version_id=version.id,
                profile_key="coaching_guidance",
                title_exact_boost=0.15,
                entity_match_boost=0.0,
                doc_type_weights_json={"coach": 0.2},
                section_weights_json={"guidance": 0.15},
                min_pass_score=0.42,
                min_pass_score_keyword=0.3,
            ),
            db_models.KnowledgeAnswerabilityProfile(
                config_version_id=version.id,
                profile_key="product_overview",
                required_slots_json=["definition", "capability"],
                optional_slots_json=["use_case"],
                sufficient_threshold=0.66,
                partial_threshold=0.5,
            ),
            db_models.KnowledgeAnswerabilityProfile(
                config_version_id=version.id,
                profile_key="pricing_lookup",
                required_slots_json=["price"],
                optional_slots_json=["edition"],
                sufficient_threshold=0.5,
                partial_threshold=0.5,
            ),
            db_models.KnowledgeAnswerabilityProfile(
                config_version_id=version.id,
                profile_key="version_compare",
                required_slots_json=["version_a", "version_b"],
                optional_slots_json=["difference"],
                sufficient_threshold=0.66,
                partial_threshold=0.5,
            ),
            db_models.KnowledgeAnswerabilityProfile(
                config_version_id=version.id,
                profile_key="coaching_guidance",
                required_slots_json=["guidance"],
                optional_slots_json=["example"],
                sufficient_threshold=0.5,
                partial_threshold=0.5,
            ),
        ]
    )
    db_session.commit()


class StubKnowledgeSearch:
    def __init__(self, fixtures: list[dict[str, Any]]) -> None:
        self._cases = {str(case["id"]): case for case in fixtures}

    async def search_multiple(self, **kwargs):
        case_id = str((kwargs.get("metadata_filter") or {}).get("eval_case_id") or "")
        if not case_id or case_id not in self._cases:
            return Result.ok([])

        query = str(kwargs.get("query") or "")
        case = self._cases[case_id]

        timeout_query = case.get("timeout_query")
        if timeout_query and query == timeout_query:
            return Result.fail("embedding timeout")

        rows_by_query = case.get("rows_by_query") or {}
        return Result.ok(list(rows_by_query.get(query, [])))


@pytest.mark.parametrize("case_index", [0, 1, 2, 3, 4])
def test_knowledge_answer_engine_eval_cases_cover_expected_behaviors(
    db_session: Session,
    seeded_config: None,
    raw_eval_cases: list[dict[str, Any]],
    eval_cases: list[KnowledgeAnswerEvalCase],
    case_index: int,
):
    search = StubKnowledgeSearch(raw_eval_cases)
    engine = KnowledgeAnswerEngine(
        config_repository=KnowledgeAnswerConfigRepository(db_session),
        haystack_adapter=KnowledgeHaystackAdapter(search_multiple=search.search_multiple),
    )
    harness = KnowledgeAnswerEngineEvaluationHarness(
        engine=engine,
        runtime_options_builder=lambda case: {
            "top_k": 3,
            "similarity_threshold": 0.65,
            "enable_hybrid": True,
            "keyword_candidate_limit": 32,
            "embedding_timeout_ms": 50,
            "enable_rerank": True,
            "rerank_top_k": 8,
            "metadata_filter": {"eval_case_id": case.case_id},
        },
    )

    result = harness.evaluate_case(eval_cases[case_index])

    assert result.passed is True
    assert result.mismatches == []


def test_knowledge_answer_engine_eval_harness_reports_fixture_run_summary(
    db_session: Session,
    seeded_config: None,
    raw_eval_cases: list[dict[str, Any]],
    eval_cases: list[KnowledgeAnswerEvalCase],
):
    search = StubKnowledgeSearch(raw_eval_cases)
    engine = KnowledgeAnswerEngine(
        config_repository=KnowledgeAnswerConfigRepository(db_session),
        haystack_adapter=KnowledgeHaystackAdapter(search_multiple=search.search_multiple),
    )
    harness = KnowledgeAnswerEngineEvaluationHarness(
        engine=engine,
        runtime_options_builder=lambda case: {
            "top_k": 3,
            "similarity_threshold": 0.65,
            "enable_hybrid": True,
            "keyword_candidate_limit": 32,
            "embedding_timeout_ms": 50,
            "enable_rerank": True,
            "rerank_top_k": 8,
            "metadata_filter": {"eval_case_id": case.case_id},
        },
    )

    run = harness.evaluate_cases(eval_cases)

    assert run.passed is True
    assert run.total_cases == 5
    assert run.passed_cases == 5
    assert run.failed_case_ids == []

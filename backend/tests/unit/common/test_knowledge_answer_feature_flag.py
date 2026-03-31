from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import agent.models  # noqa: F401
from common.db.models import (
    Base,
    KnowledgeAnswerRun,
    KnowledgeAnswerRunStep,
    KnowledgeAnswerabilityProfile,
    KnowledgeConfigVersion,
    KnowledgeEntityAlias,
    KnowledgeIntentRule,
    KnowledgeQueryProfile,
    KnowledgeRankingProfile,
    PracticeSession,
    Scenario,
    User,
)
from common.error_handling.result import Result
from sales_bot.websocket.components.stepfun_internal_knowledge_searcher import (
    search_internal_knowledge,
)


@pytest_asyncio.fixture
async def async_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _seed_runtime_config(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as session:
        version = KnowledgeConfigVersion(
            version_name="rollout-v1",
            status="active",
            enabled=True,
            notes="feature-flag rollout seed",
        )
        session.add(version)
        await session.flush()
        session.add_all(
            [
                KnowledgeQueryProfile(
                    config_version_id=version.id,
                    profile_key="product_overview",
                    description="产品介绍",
                    rewrite_strategy="multi_query",
                    max_rewrite_queries=4,
                    stop_after_first_success=True,
                ),
                KnowledgeIntentRule(
                    config_version_id=version.id,
                    intent_key="company_intro",
                    priority=10,
                    match_type="regex",
                    pattern="介绍一下.*石犀科技",
                    profile_key="product_overview",
                ),
                KnowledgeEntityAlias(
                    config_version_id=version.id,
                    canonical_entity="石犀科技",
                    alias="世袭科技",
                    entity_type="company",
                    confidence=0.96,
                ),
                KnowledgeRankingProfile(
                    config_version_id=version.id,
                    profile_key="product_overview",
                    title_exact_boost=0.25,
                    entity_match_boost=0.2,
                    doc_type_weights_json={"product": 0.18},
                    section_weights_json={"overview": 0.14},
                    min_pass_score=0.45,
                    min_pass_score_keyword=0.35,
                ),
                KnowledgeAnswerabilityProfile(
                    config_version_id=version.id,
                    profile_key="product_overview",
                    required_slots_json=["definition", "capability"],
                    optional_slots_json=["use_case"],
                    sufficient_threshold=0.66,
                    partial_threshold=0.5,
                ),
            ]
        )
        await session.commit()
        return version.id


async def _seed_practice_session(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as session:
        user = User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=f"wechat_{uuid.uuid4().hex[:8]}",
            name="Rollout Tester",
            role="user",
        )
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="Rollout Scenario",
            is_active=True,
        )
        practice_session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=user.user_id,
            scenario_id=scenario.scenario_id,
            status="in_progress",
            voice_mode="stepfun_realtime",
        )
        session.add_all([user, scenario, practice_session])
        await session.commit()
        return str(practice_session.session_id)


class RolloutKnowledgeService:
    def __init__(self, _db):
        self.queries: list[str] = []

    async def get_search_health(self, **kwargs):
        return {
            "is_ready": True,
            "ready_document_count": 1,
            "ready_chunk_count": 2,
            "vector_chunk_count": 2,
        }

    async def search_multiple(self, **kwargs):
        query = str(kwargs["query"])
        self.queries.append(query)

        if query == "石犀科技 产品介绍":
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_id": "engine-doc-1",
                        "chunk_id": "engine-chunk-1",
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

        if query == "请介绍一下世袭科技 产品介绍":
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_title": "世袭科技旧版手册",
                        "content": "世袭科技是一家面向企业训练场景的智能销售训练平台。",
                        "score": 0.93,
                        "retrieval_mode": "keyword_fallback",
                    }
                ]
            )

        return Result.ok([])

    def get_last_search_timing(self):
        return {
            "phase_vector_ms": 18.0,
            "phase_keyword_ms": 4.0,
            "cache_hit_ready_docs": False,
        }


async def _run_search(
    *,
    factory: async_sessionmaker[AsyncSession],
    session_id: str | None,
) -> tuple[dict[str, object], list[str], AsyncSession]:
    record_metric = AsyncMock()

    captured_queries: list[str] = []

    class BoundKnowledgeService(RolloutKnowledgeService):
        async def search_multiple(self, **kwargs):
            result = await super().search_multiple(**kwargs)
            captured_queries.append(str(kwargs["query"]))
            return result

    payload = await search_internal_knowledge(
        arguments_obj={
            "query": "请介绍一下世袭科技",
            "top_k": 3,
            "session_id": session_id,
        },
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "require_kb_grounding": True,
                "retrieval_similarity_threshold": 0.65,
                "retrieval_enable_hybrid": True,
                "retrieval_enable_rerank": True,
                "retrieval_rerank_top_k": 8,
            },
        },
        session_factory=factory,
        knowledge_service_cls=BoundKnowledgeService,
        record_metric=record_metric,
    )

    return payload, captured_queries, record_metric


@pytest.mark.asyncio
async def test_feature_flags_keep_legacy_path_when_engine_disabled(
    monkeypatch: pytest.MonkeyPatch,
    async_session_factory: async_sessionmaker[AsyncSession],
):
    await _seed_runtime_config(async_session_factory)
    session_id = await _seed_practice_session(async_session_factory)
    monkeypatch.setenv("KNOWLEDGE_ANSWER_ENGINE_ENABLED", "false")
    monkeypatch.setenv("KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN", "false")

    payload, captured_queries, _record_metric = await _run_search(
        factory=async_session_factory,
        session_id=session_id,
    )

    assert payload["query"] == "请介绍一下世袭科技"
    assert payload["results"][0]["document_title"] == "世袭科技旧版手册"
    assert payload["_answerability"]["query"] == "请介绍一下世袭科技"
    assert payload["_answerability"].get("audit_run_id") is None
    assert captured_queries == ["请介绍一下世袭科技", "请介绍一下世袭科技 产品介绍"]

    async with async_session_factory() as session:
        run_count = await session.scalar(select(func.count()).select_from(KnowledgeAnswerRun))
        step_count = await session.scalar(select(func.count()).select_from(KnowledgeAnswerRunStep))

    assert run_count == 0
    assert step_count == 0


@pytest.mark.asyncio
async def test_feature_flags_use_new_engine_path_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    async_session_factory: async_sessionmaker[AsyncSession],
):
    await _seed_runtime_config(async_session_factory)
    session_id = await _seed_practice_session(async_session_factory)
    monkeypatch.setenv("KNOWLEDGE_ANSWER_ENGINE_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN", "false")

    payload, captured_queries, _record_metric = await _run_search(
        factory=async_session_factory,
        session_id=session_id,
    )

    assert payload["query"] == "请介绍一下石犀科技"
    assert payload["rewritten_queries"] == ["请介绍一下石犀科技", "石犀科技 产品介绍"]
    assert payload["intent"]["intent_key"] == "company_intro"
    assert payload["entity_resolution"]["canonical_entities"] == ["石犀科技"]
    assert payload["results"][0]["document_title"] == "石犀科技产品手册"
    assert payload["_answerability"]["audit_run_id"]
    assert captured_queries == ["请介绍一下石犀科技", "石犀科技 产品介绍"]

    async with async_session_factory() as session:
        runs = (
            await session.execute(
                select(KnowledgeAnswerRun).order_by(KnowledgeAnswerRun.created_at.desc())
            )
        ).scalars().all()
        steps = (
            await session.execute(
                select(KnowledgeAnswerRunStep).order_by(KnowledgeAnswerRunStep.step_order.asc())
            )
        ).scalars().all()

    assert len(runs) == 1
    assert runs[0].session_id == session_id
    assert runs[0].retrieval_summary_json["resolved_query"] == "请介绍一下石犀科技"
    assert [step.step_name for step in steps] == [
        "resolve",
        "classify",
        "plan",
        "retrieve",
        "rank",
        "answerability",
        "assemble",
    ]


@pytest.mark.asyncio
async def test_feature_flags_dual_run_records_audit_without_user_visible_cutover(
    monkeypatch: pytest.MonkeyPatch,
    async_session_factory: async_sessionmaker[AsyncSession],
):
    await _seed_runtime_config(async_session_factory)
    session_id = await _seed_practice_session(async_session_factory)
    monkeypatch.setenv("KNOWLEDGE_ANSWER_ENGINE_ENABLED", "false")
    monkeypatch.setenv("KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN", "true")

    payload, captured_queries, _record_metric = await _run_search(
        factory=async_session_factory,
        session_id=session_id,
    )

    assert payload["query"] == "请介绍一下世袭科技"
    assert payload["results"][0]["document_title"] == "世袭科技旧版手册"
    assert payload["_answerability"]["query"] == "请介绍一下世袭科技"
    assert payload["_diagnostics"]["knowledge_answer_rollout"]["mode"] == "dual_run"
    assert payload["_diagnostics"]["knowledge_answer_rollout"]["shadow_audit_run_id"]
    assert "请介绍一下世袭科技" in captured_queries
    assert "请介绍一下世袭科技 产品介绍" in captured_queries
    assert "请介绍一下石犀科技" in captured_queries
    assert "石犀科技 产品介绍" in captured_queries

    async with async_session_factory() as session:
        runs = (
            await session.execute(select(KnowledgeAnswerRun).order_by(KnowledgeAnswerRun.created_at.desc()))
        ).scalars().all()

    assert len(runs) == 1
    assert runs[0].session_id == session_id
    assert runs[0].retrieval_summary_json["resolved_query"] == "请介绍一下石犀科技"

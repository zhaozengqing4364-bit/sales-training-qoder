from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    PracticeSession,
    Scenario,
    SessionStatus,
    TrainingReportSnapshot,
)
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.services.learning_path import LearningPathService


class _RecommendationResult:
    is_success: bool
    value: dict[str, Any]

    def __init__(self, value: dict[str, Any]) -> None:
        self.is_success = True
        self.value = value


class _SpyRecommendationService:
    def __init__(self) -> None:
        self.seen_session_ids: list[str] = []

    def build_for_session(self, session: PracticeSession) -> _RecommendationResult:
        self.seen_session_ids.append(str(session.session_id))
        scores = {
            "product_knowledge": float(session.accuracy_score or 0),
            "objection_handling": float(session.completeness_score or 0),
            "value_logic": float(session.logic_score or 0),
        }
        weak_dimension = min(scores, key=scores.__getitem__)
        return _RecommendationResult(
            {
                "recommendation_kind": "next_practice_ruleset",
                "weak_dimension": weak_dimension,
                "title": f"练习 {weak_dimension}",
                "reason": f"{weak_dimension} 得分偏低",
                "action_label": "开始专项练习",
                "target_path": f"/training/sales?focus={weak_dimension}",
                "evidence_summary": {
                    "weak_dimension": weak_dimension,
                    "score": scores[weak_dimension],
                },
            }
        )

    async def build_for_session_with_db(
        self, *, db: AsyncSession, session: PracticeSession
    ) -> _RecommendationResult:
        self.seen_session_ids.append(f"db:{session.session_id}")
        return self.build_for_session(session)


def _template(template_id: str, *, stage_key: str, name: str) -> PracticeTemplate:
    return PracticeTemplate(
        template_id=template_id,
        name=name,
        description=f"{name} description",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash=f"hash-{template_id}",
        curriculum_plan={
            "name": f"{name} path",
            "stages": [
                {
                    "template_stage_key": stage_key,
                    "order": 1,
                    "name": name,
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": template_id,
                        "version": 1,
                        "hash": f"hash-{template_id}",
                        "snapshot_label": "published",
                    },
                    "completion_policy": {
                        "min_score": 7,
                        "min_rounds": 1,
                        "max_duration_seconds": 600,
                    },
                    "failure_policy": "retry_current",
                    "prerequisites": [],
                }
            ],
        },
    )


def _session(
    session_id: str,
    *,
    user_id: str = "learner-1",
    template_id: str = "template-product",
    logic_score: float = 80,
    accuracy_score: float = 50,
    completeness_score: float = 70,
    started_days_ago: int = 1,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id="scenario-sales",
        scenario_type="sales",
        name="销售对练",
    )
    session = PracticeSession(
        session_id=session_id,
        user_id=user_id,
        scenario_id="scenario-sales",
        practice_template_id=template_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        effectiveness_snapshot={"evaluable": True},
        start_time=datetime.now(UTC) - timedelta(days=started_days_ago),
        curriculum_snapshot={
            "stage_snapshots": {
                "template_stage_product": {
                    "template_ref": {
                        "asset_type": "practice_template",
                        "asset_id": template_id,
                        "version": 1,
                        "hash": f"hash-{template_id}",
                        "snapshot_label": "published",
                    },
                    "runtime_payload": {},
                    "content_assets": [],
                    "rubric": {
                        "asset_type": "rubric_set",
                        "asset_id": "rubric-1",
                        "version": 1,
                        "hash": "hash-rubric",
                        "snapshot_label": "published",
                    },
                    "runtime": {
                        "agent_id": "agent-1",
                        "persona_id": "persona-1",
                        "runtime_profile_id": "runtime-1",
                        "voice_policy_snapshot_hash": "voice-hash",
                        "instruction_contract_hash": "instruction-hash",
                    },
                }
            }
        },
    )
    session.scenario = scenario
    return session


def _report_snapshot(
    snapshot_id: str,
    *,
    session: PracticeSession,
    dimensions: dict[str, float],
    stage_key: str = "template_stage_product",
) -> TrainingReportSnapshot:
    snapshot = TrainingReportSnapshot(
        snapshot_id=snapshot_id,
        session_id=str(session.session_id),
        evaluation_run_id=f"run-{snapshot_id}",
        report_payload={
            "dimensions": dimensions,
            "lineage": {
                "stage_snapshots": {
                    stage_key: {
                        "result": "completed",
                        "score": max(dimensions.values()) if dimensions else None,
                    }
                }
            },
        },
        ruleset_source="session_evidence_projection",
        ruleset_version="v1",
        score_basis="persisted_snapshot",
        evidence_completeness={},
    )
    return snapshot


@pytest.mark.asyncio
async def test_should_aggregate_weak_dimensions_across_recent_reports() -> None:
    spy = _SpyRecommendationService()
    service = LearningPathService(recommendation_service=spy)
    older = _session("session-older", accuracy_score=72, completeness_score=43, started_days_ago=2)
    newer = _session("session-newer", accuracy_score=49, completeness_score=65, started_days_ago=1)
    older.report_snapshots = [
        _report_snapshot("report-older", session=older, dimensions={"objection_handling": 4.3})
    ]
    newer.report_snapshots = [
        _report_snapshot("report-newer", session=newer, dimensions={"product_knowledge": 4.9})
    ]

    result = await service.build_from_evidence(
        user_id="learner-1",
        sessions=[older, newer],
        templates=[
            _template("template-product", stage_key="template_stage_product", name="产品知识专项"),
            _template("template-objection", stage_key="template_stage_objection", name="异议处理专项"),
        ],
    )

    assert result["path_type"] == "weakness_driven"
    assert result["recommended_template_ids"] == ["template-objection", "template-product"]
    assert [reason["dimension_name"] for reason in result["recommendation_reasons"]] == [
        "objection_handling",
        "product_knowledge",
    ]
    assert result["recommendation_reasons"][0]["source_report_id"] == "report-older"
    assert result["next_task"]["reason"]


@pytest.mark.asyncio
async def test_should_trace_recommendation_reason_to_report_dimension_and_score() -> None:
    service = LearningPathService(recommendation_service=_SpyRecommendationService())
    session = _session("session-report", accuracy_score=51)
    session.report_snapshots = [
        _report_snapshot("report-trace", session=session, dimensions={"product_knowledge": 4.8})
    ]

    result = await service.build_from_evidence(
        user_id="learner-1",
        sessions=[session],
        templates=[_template("template-product", stage_key="template_stage_product", name="产品知识专项")],
    )

    assert result["recommendation_reasons"] == [
        {
            "dimension_name": "product_knowledge",
            "score": 4.8,
            "source_report_id": "report-trace",
            "recommended_template_id": "template-product",
            "reason": "product_knowledge 得分偏低",
        }
    ]


@pytest.mark.asyncio
async def test_should_reuse_next_practice_recommendation_service() -> None:
    spy = _SpyRecommendationService()
    service = LearningPathService(recommendation_service=spy)
    one = _session("session-one")
    two = _session("session-two", started_days_ago=0)
    one.report_snapshots = [
        _report_snapshot("report-one", session=one, dimensions={"product_knowledge": 4.8})
    ]
    two.report_snapshots = [
        _report_snapshot("report-two", session=two, dimensions={"product_knowledge": 4.7})
    ]

    await service.build_from_evidence(
        user_id="learner-1",
        sessions=[one, two],
        templates=[_template("template-product", stage_key="template_stage_product", name="产品知识专项")],
    )

    assert spy.seen_session_ids == ["session-two", "session-one"]


@pytest.mark.asyncio
async def test_should_deduplicate_templates_by_highest_severity() -> None:
    service = LearningPathService(recommendation_service=_SpyRecommendationService())
    mild = _session("session-mild", accuracy_score=58, started_days_ago=2)
    severe = _session("session-severe", accuracy_score=35, started_days_ago=1)
    mild.report_snapshots = [
        _report_snapshot("report-mild", session=mild, dimensions={"product_knowledge": 4.8})
    ]
    severe.report_snapshots = [
        _report_snapshot("report-severe", session=severe, dimensions={"product_knowledge": 3.5})
    ]

    result = await service.build_from_evidence(
        user_id="learner-1",
        sessions=[mild, severe],
        templates=[_template("template-product", stage_key="template_stage_product", name="产品知识专项")],
    )

    assert result["recommended_template_ids"] == ["template-product"]
    assert result["recommendation_reasons"][0]["score"] == 3.5
    assert result["recommendation_reasons"][0]["source_report_id"] == "report-severe"


@pytest.mark.asyncio
async def test_should_expose_stage_result_from_report_lineage() -> None:
    service = LearningPathService(recommendation_service=_SpyRecommendationService())
    session = _session("session-stage", accuracy_score=42)
    session.report_snapshots = [
        _report_snapshot(
            "report-stage",
            session=session,
            dimensions={"product_knowledge": 4.2},
            stage_key="template_stage_product",
        )
    ]

    result = await service.build_from_evidence(
        user_id="learner-1",
        sessions=[session],
        templates=[_template("template-product", stage_key="template_stage_product", name="产品知识专项")],
    )

    assert result["stages"][0]["result"] == {"result": "completed", "score": 4.2}


@pytest.mark.asyncio
async def test_should_return_role_default_path_for_cold_start_user() -> None:
    service = LearningPathService(recommendation_service=_SpyRecommendationService())

    result = await service.build_from_evidence(
        user_id="learner-1",
        sessions=[],
        templates=[_template("template-product", stage_key="template_stage_product", name="产品知识专项")],
    )

    assert result["path_type"] == "role_default"
    assert result["recommended_template_ids"] == ["template-product"]
    assert result["next_task"]["title"] == "产品知识专项"
    assert result["next_task"]["primary_cta"] == "开始默认路径"
    assert result["generated_at"]


@pytest.mark.asyncio
async def test_should_refresh_database_ruleset_when_db_is_available() -> None:
    spy = _SpyRecommendationService()
    service = LearningPathService(db=Mock(spec=AsyncSession), recommendation_service=spy)
    session = _session("session-db")
    session.report_snapshots = [
        _report_snapshot("report-db", session=session, dimensions={"product_knowledge": 4.8})
    ]

    await service.build_from_evidence(
        user_id="learner-1",
        sessions=[session],
        templates=[_template("template-product", stage_key="template_stage_product", name="产品知识专项")],
    )

    assert "db:session-db" in spy.seen_session_ids

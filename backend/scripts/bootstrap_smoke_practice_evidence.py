"""
Bootstrap deterministic practice evidence for critical smoke flows.

Usage:
  python backend/scripts/bootstrap_smoke_practice_evidence.py --email admin@qoder.ai
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.models import Agent, AgentPersona, Persona
from common.conversation.models import ConversationMessage
from common.db.models import (
    ComprehensiveReport,
    EvaluationRun,
    PracticeSession,
    Scenario,
    SessionAudioSegment,
    SessionStatus,
    StagedEvaluationResult,
    TrainingReportSnapshot,
    TrainingTask,
    User,
)
from common.db.session import AsyncSessionLocal
from curriculum_practice.models import PracticeTemplate  # noqa: F401 - registers practice_templates metadata

SMOKE_SCENARIO_NAME = "Smoke critical report session"
SMOKE_AGENT_NAME = "Smoke Phase 4 Sales Agent"
SMOKE_PERSONA_NAME = "Smoke Phase 4 Budget Buyer"
SMOKE_TEMPLATE_NAME = "Smoke Phase 4 Sales Curriculum Template"
SMOKE_TRAINING_TASK_TITLE = "Smoke Phase 4 Sales Curriculum Task"


def _make_effectiveness_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": True,
        },
        "main_capability_passed": True,
        "overall_result": "pass",
        "metrics": {
            "value_expression_score": 88.0,
            "customer_benefit_score": 84.0,
            "evidence_usage_score": 89.0,
            "objection_handling_score": 81.0,
            "next_step_score": 79.0,
            "value_articulation_rollup": 86.0,
            "evidence_benefit_rollup": 87.0,
            "objection_progress_rollup": 80.0,
        },
        "main_issue": {
            "issue_type": "evidence_gap",
            "issue_text": "价值主张缺少案例、数据或 ROI 支撑，客户很难相信收益承诺。",
            "recovery_rule": "下一轮先给出案例、数据或 benchmark，再回应价格与 ROI 追问。",
        },
        "next_goal": {
            "goal_type": "evidence_backing",
            "goal_text": "先用案例、数据或 ROI 证据支撑主张，再推进下一步。",
            "rule": "至少补上一条证据和一个明确的下一步动作。",
        },
        "version": "rule_v1",
        "evaluable": True,
        "not_evaluable_reason": None,
    }


def _make_voice_policy_snapshot() -> dict[str, object]:
    return {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "smoke-runtime-profile",
        "instruction_contract_hash": "smoke-contract-hash",
        "network_access_mode": "off",
        "resolved_at": datetime.now(UTC).isoformat(),
        "knowledge_base_ids": ["kb-smoke-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
        },
        "source": {
            "voice_mode": "runtime_profile",
            "knowledge_base_ids": "agent",
        },
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 1,
                "hit_query_count": 1,
                "total_results": 1,
                "hit_rate": 1.0,
                "recent_attempts": [
                    {
                        "attempted_at": datetime.now(UTC).isoformat(),
                        "query": "ROI 回本案例",
                        "status": "hit",
                        "result_count": 1,
                        "retrieval_mode": "hybrid",
                        "knowledge_base_ids": ["kb-smoke-1"],
                        "result_summaries": [
                            {
                                "knowledge_base_id": "kb-smoke-1",
                                "knowledge_base_name": "Smoke 知识库",
                                "snippet": "客户 A 在 6 个月内实现 ROI 回本，迁移期 SLA 99.9%",
                                "score": 0.92,
                                "retrieval_mode": "vector",
                            }
                        ],
                    }
                ],
                "audio_audit": {
                    "recording_status": "completed",
                    "storage_prefix": "sessions/smoke/audio",
                },
            }
        },
    }


def _make_dimension_scores() -> list[dict[str, object]]:
    return [
        {"name": "价值表达", "score": 86.0, "weight": 0.2, "description": "清晰表达业务价值"},
        {"name": "客户收益连接", "score": 84.0, "weight": 0.2, "description": "把方案收益连接到客户目标"},
        {"name": "证据使用", "score": 89.0, "weight": 0.25, "description": "使用案例、数据或 ROI 支撑主张"},
        {"name": "异议处理", "score": 81.0, "weight": 0.2, "description": "回应预算和风险异议"},
        {"name": "推进下一步", "score": 79.0, "weight": 0.15, "description": "提出明确可执行的下一步"},
    ]


def _make_stage_summaries() -> list[dict[str, object]]:
    return [
        {
            "stage_number": 1,
            "start_turn": 1,
            "end_turn": 2,
            "average_score": 86.0,
            "key_points": ["用 ROI 案例回应预算疑虑", "说明迁移期 SLA 风险控制"],
            "summary": "用户能用案例和 SLA 数据支撑价值主张。",
        },
        {
            "stage_number": 2,
            "start_turn": 3,
            "end_turn": 3,
            "average_score": 80.0,
            "key_points": ["给出试点作为下一步"],
            "summary": "下一步动作明确，但仍可补充更具体的决策人和时间。",
        },
    ]


async def bootstrap_smoke_practice_evidence(*, email: str) -> tuple[str, str, str]:
    normalized_email = email.strip().lower()
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(
            select(User).where(User.email == normalized_email)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            raise RuntimeError(
                f"Smoke evidence bootstrap requires an existing user for email={normalized_email}"
            )
        now = datetime.now(UTC)

        scenario_result = await db.execute(
            select(Scenario).where(
                Scenario.scenario_type == "sales",
                Scenario.name == SMOKE_SCENARIO_NAME,
            )
        )
        scenario = scenario_result.scalar_one_or_none()
        if scenario is None:
            scenario = Scenario(
                scenario_id=str(uuid.uuid4()),
                scenario_type="sales",
                name=SMOKE_SCENARIO_NAME,
                is_active=True,
            )
            db.add(scenario)
            await db.flush()

        agent_result = await db.execute(
            select(Agent).where(Agent.name == SMOKE_AGENT_NAME)
        )
        agent = agent_result.scalar_one_or_none()
        if agent is None:
            agent = Agent(
                id=str(uuid.uuid4()),
                name=SMOKE_AGENT_NAME,
                description="Deterministic Sales agent for smoke and Phase 4 E2E flows",
                category="sales",
                system_prompt="You are a Sales training coach for deterministic E2E flows.",
                capabilities_config={
                    "sales_stage": {"enabled": True},
                    "fuzzy_detection": {"enabled": True},
                    "realtime_scoring": {"enabled": True},
                },
                status="published",
                created_by=str(user.user_id),
                published_at=now,
            )
            db.add(agent)
            await db.flush()

        persona_result = await db.execute(
            select(Persona).where(Persona.name == SMOKE_PERSONA_NAME)
        )
        persona = persona_result.scalar_one_or_none()
        if persona is None:
            persona = Persona(
                id=str(uuid.uuid4()),
                name=SMOKE_PERSONA_NAME,
                description="Budget-conscious buyer for deterministic Sales E2E flows",
                category="customer",
                difficulty="medium",
                system_prompt="You care about budget risk, ROI evidence, and a safe pilot scope.",
                traits={"关注点": "预算、ROI、试点范围"},
                behavior_config={"sales_stage": {"enabled": True}},
                scoring_weights=[
                    {"name": "价值表达", "weight": 0.2},
                    {"name": "客户收益连接", "weight": 0.2},
                    {"name": "证据使用", "weight": 0.25},
                    {"name": "异议处理", "weight": 0.2},
                    {"name": "推进下一步", "weight": 0.15},
                ],
                status="active",
                created_by=str(user.user_id),
            )
            db.add(persona)
            await db.flush()

        link_result = await db.execute(
            select(AgentPersona).where(
                AgentPersona.agent_id == agent.id,
                AgentPersona.persona_id == persona.id,
            )
        )
        if link_result.scalar_one_or_none() is None:
            db.add(
                AgentPersona(
                    id=str(uuid.uuid4()),
                    agent_id=agent.id,
                    persona_id=persona.id,
                    is_default=True,
                )
            )
            await db.flush()

        template_result = await db.execute(
            select(PracticeTemplate).where(PracticeTemplate.name == SMOKE_TEMPLATE_NAME)
        )
        template = template_result.scalar_one_or_none()
        if template is None:
            template = PracticeTemplate(
                template_id=str(uuid.uuid4()),
                name=SMOKE_TEMPLATE_NAME,
                description="Deterministic curriculum template for smoke analytics and report flows",
                scenario_type="sales",
                mode="customer_roleplay",
                agent_id=str(agent.id),
                persona_id=str(persona.id),
                runtime_profile_id="smoke-runtime-profile",
                voice_mode="stepfun_realtime",
                scoring_ruleset_id="smoke-sales-ruleset",
                knowledge_base_refs=["kb-smoke-1"],
                curriculum_plan={
                    "version": "smoke-v1",
                    "stages": [
                        {
                            "stage_id": "evidence-backed-value",
                            "name": "证据支撑价值表达",
                            "goal": "用案例、数据或 ROI 回应预算疑虑",
                        },
                        {
                            "stage_id": "next-step-close",
                            "name": "推进下一步",
                            "goal": "提出低风险试点作为下一步",
                        },
                    ],
                },
                max_stage_duration_seconds=180,
                status="published",
                version=1,
                content_hash="smoke-phase4-sales-template-v1",
                published_at=now,
                published_by=str(user.user_id),
                created_by=str(user.user_id),
                updated_by=str(user.user_id),
            )
            db.add(template)
            await db.flush()
        else:
            template.agent_id = str(agent.id)
            template.persona_id = str(persona.id)
            template.runtime_profile_id = "smoke-runtime-profile"
            template.scoring_ruleset_id = "smoke-sales-ruleset"
            template.status = "published"
            template.updated_by = str(user.user_id)
            template.updated_at = now

        session_result = await db.execute(
            select(PracticeSession)
            .where(
                PracticeSession.user_id == str(user.user_id),
                PracticeSession.scenario_id == scenario.scenario_id,
            )
            .order_by(PracticeSession.start_time.desc())
        )
        session = session_result.scalars().first()

        session_start = now - timedelta(minutes=6)

        if session is None:
            session = PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(user.user_id),
                scenario_id=scenario.scenario_id,
            )
            db.add(session)
            await db.flush()

        template_id = str(template.template_id)
        dimension_scores = _make_dimension_scores()
        stage_summaries = _make_stage_summaries()
        session.status = SessionStatus.COMPLETED.value
        session.start_time = session_start
        session.end_time = now
        session.total_duration_seconds = 6 * 60
        session.voice_mode = "stepfun_realtime"
        session.practice_template_id = template_id
        session.curriculum_snapshot = {
            "practice_template": {
                "template_id": template_id,
                "name": str(template.name),
                "version": int(template.version or 1),
                "content_hash": str(template.content_hash or ""),
            },
            "stage_snapshots": {
                "evidence-backed-value": {
                    "template_ref": {"asset_id": template_id, "version": int(template.version or 1)},
                    "goal": "用案例、数据或 ROI 回应预算疑虑",
                },
                "next-step-close": {
                    "template_ref": {"asset_id": template_id, "version": int(template.version or 1)},
                    "goal": "提出低风险试点作为下一步",
                },
            },
        }
        session.logic_score = 88.0
        session.accuracy_score = 84.0
        session.completeness_score = 80.0
        session.effectiveness_snapshot = _make_effectiveness_snapshot()
        session.voice_policy_snapshot = _make_voice_policy_snapshot()
        session.report_status = "completed"
        session.report_error = None

        await db.execute(
            delete(ConversationMessage).where(
                ConversationMessage.session_id == session.session_id
            )
        )
        await db.execute(
            delete(SessionAudioSegment).where(
                SessionAudioSegment.session_id == session.session_id
            )
        )
        await db.execute(
            delete(StagedEvaluationResult).where(
                StagedEvaluationResult.session_id == session.session_id
            )
        )
        await db.execute(
            delete(ComprehensiveReport).where(
                ComprehensiveReport.session_id == session.session_id
            )
        )
        await db.execute(
            delete(TrainingReportSnapshot).where(
                TrainingReportSnapshot.session_id == session.session_id
            )
        )
        await db.execute(
            delete(EvaluationRun).where(EvaluationRun.session_id == session.session_id)
        )

        db.add_all(
            [
                ConversationMessage(
                    session_id=session.session_id,
                    turn_number=1,
                    role="user",
                    content="我们有 3 个同类客户在 6 个月内回本，迁移期间 SLA 维持 99.9%。",
                    timestamp=session_start + timedelta(seconds=30),
                    duration_ms=1_800,
                    sales_stage="objection",
                    audio_url=f"https://example.com/{session.session_id}/audio-1.webm",
                    score_snapshot={
                        "overall_score": 88.0,
                        "dimension_scores": {
                            "价值表达": 86.0,
                            "客户收益连接": 84.0,
                            "证据使用": 89.0,
                            "异议处理": 81.0,
                            "推进下一步": 79.0,
                        },
                    },
                ),
                ConversationMessage(
                    session_id=session.session_id,
                    turn_number=2,
                    role="assistant",
                    content="明白，我会先用真实案例和回本周期回应这个 ROI 担忧。",
                    timestamp=session_start + timedelta(seconds=42),
                    duration_ms=1_600,
                    sales_stage="objection",
                    score_snapshot={"overall_score": 85.0},
                ),
                ConversationMessage(
                    session_id=session.session_id,
                    turn_number=3,
                    role="user",
                    content="如果预算紧张，你会先推进哪个下一步？",
                    timestamp=session_start + timedelta(seconds=56),
                    duration_ms=1_400,
                    sales_stage="closing",
                    score_snapshot={"overall_score": 84.0},
                ),
            ]
        )
        db.add_all(
            [
                StagedEvaluationResult(
                    session_id=session.session_id,
                    stage_number=1,
                    start_turn=1,
                    end_turn=2,
                    scores={
                        "价值表达": 86.0,
                        "客户收益连接": 84.0,
                        "证据使用": 89.0,
                    },
                    strengths=["用同类客户回本案例支撑 ROI", "补充迁移期 SLA 证据"],
                    weaknesses=["预算异议可以更早量化风险"],
                    suggestions=["先给出客户案例，再说明试点范围"],
                    summary="证据支撑充分，价值表达清晰。",
                    created_at=session_start + timedelta(minutes=3),
                ),
                StagedEvaluationResult(
                    session_id=session.session_id,
                    stage_number=2,
                    start_turn=3,
                    end_turn=3,
                    scores={
                        "异议处理": 81.0,
                        "推进下一步": 79.0,
                    },
                    strengths=["能把预算风险收敛到低风险试点"],
                    weaknesses=["下一步缺少明确时间窗口"],
                    suggestions=["补充试点时间、决策人和验收指标"],
                    summary="下一步方向明确，仍需更具体的推进计划。",
                    created_at=session_start + timedelta(minutes=5),
                ),
                SessionAudioSegment(
                    session_id=session.session_id,
                    segment_sequence=0,
                    object_key=f"audio/{session.session_id}/seg_0000.webm",
                    content_type="audio/webm",
                    size_bytes=20_480,
                    duration_ms=12_000,
                    upload_status="uploaded",
                    created_at=session_start + timedelta(seconds=5),
                ),
                SessionAudioSegment(
                    session_id=session.session_id,
                    segment_sequence=1,
                    object_key=f"audio/{session.session_id}/seg_0001.webm",
                    content_type="audio/webm",
                    size_bytes=10_240,
                    duration_ms=8_000,
                    upload_status="uploaded",
                    created_at=session_start + timedelta(seconds=20),
                ),
            ]
        )

        evaluation_run = EvaluationRun(
            run_id=str(uuid.uuid4()),
            session_id=session.session_id,
            status="succeeded",
            started_at=session_start + timedelta(minutes=6),
            finished_at=now,
            input_evidence_reference={"source": "smoke_practice_evidence"},
            result_payload={"overall_score": 84.0, "dimension_scores": dimension_scores},
            result_summary="Smoke report snapshot for curriculum analytics and report QA.",
        )
        db.add(evaluation_run)
        await db.flush()

        db.add_all(
            [
                ComprehensiveReport(
                    session_id=session.session_id,
                    overall_score=84.0,
                    dimension_scores=dimension_scores,
                    key_strengths=["证据支撑充分", "能回应预算异议"],
                    key_improvements=["把下一步推进计划具体到时间和验收指标"],
                    recommendations=["下一轮用 ROI 案例开场，并明确试点验收标准"],
                    detailed_feedback="Smoke 报告：价值表达、证据使用和预算异议处理链路完整。",
                    stage_summaries=stage_summaries,
                    scoring_metadata={
                        "ruleset_id": "smoke-sales-ruleset",
                        "version": "smoke-v1",
                        "score_basis": "smoke_seed",
                        "source": "smoke_seed",
                    },
                    created_at=now,
                ),
                TrainingReportSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    session_id=session.session_id,
                    evaluation_run_id=evaluation_run.run_id,
                    report_payload={
                        "overall_score": 84.0,
                        "dimension_scores": dimension_scores,
                        "stage_summaries": stage_summaries,
                        "lineage": {"source": "smoke_practice_evidence"},
                    },
                    ruleset_source="smoke_seed",
                    ruleset_version="smoke-v1",
                    score_basis="smoke_seed",
                    evidence_completeness={"conversation": True, "staged_evaluations": True},
                    generated_at=now,
                ),
            ]
        )

        task_result = await db.execute(
            select(TrainingTask).where(
                TrainingTask.resulting_session_id == session.session_id,
                TrainingTask.source == "smoke",
            )
        )
        training_task = task_result.scalar_one_or_none()
        if training_task is None:
            training_task = TrainingTask(
                task_id=str(uuid.uuid4()),
                title=SMOKE_TRAINING_TASK_TITLE,
                assignee_id=str(user.user_id),
                scenario_type="sales",
                goal="完成 smoke 销售课程训练链路",
                practice_template_id=template_id,
                source="smoke",
                status="completed",
                resulting_session_id=session.session_id,
                before_after_summary={"source": "smoke_practice_evidence"},
            )
            db.add(training_task)
        else:
            training_task.title = SMOKE_TRAINING_TASK_TITLE
            training_task.practice_template_id = template_id
            training_task.status = "completed"
            training_task.updated_at = now

        await db.commit()

        session_id = str(session.session_id)
        return (
            session_id,
            f"/practice/{session_id}/report",
            f"/practice/{session_id}/replay",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap deterministic report/replay evidence for smoke flows"
    )
    parser.add_argument(
        "--email", required=True, help="Existing user email to own the smoke session"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    session_id, report_path, replay_path = asyncio.run(
        bootstrap_smoke_practice_evidence(email=args.email)
    )
    print(f"SMOKE_REPORT_SESSION_ID={session_id}")
    print(f"SMOKE_REPORT_PATH={report_path}")
    print(f"SMOKE_REPLAY_PATH={replay_path}")

from __future__ import annotations

import ast
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import (
    EvaluationRun,
    PracticeSession,
    Scenario,
    ScoringRuleset,
    TrainingReportSnapshot,
    TrainingTask,
    User,
)
from common.knowledge.models import KnowledgeBase
from common.training_tasks.schemas import (
    TrainingTaskCompleteRequest,
    TrainingTaskStartSessionRequest,
)
from common.training_tasks.service import (
    complete_training_task,
    start_training_task_session,
)
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.services.learning_path import LearningPathService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]

SCORING_DIMENSIONS = (
    "product_knowledge",
    "objection_handling",
    "value_logic",
)

SECURITY_EVIDENCE = (
    (
        "RBAC admin boundary",
        "tests/integration/test_rbac_access_control_api.py",
        "test_admin_analytics_routes_reject_non_admin_with_trace_id",
    ),
    (
        "IDOR session owner boundary",
        "tests/integration/test_session_lifecycle_api.py",
        "test_lifecycle_api_enforces_owner_and_admin_access",
    ),
    (
        "Snapshot owner/admin boundary",
        "tests/integration/test_voice_runtime_session_snapshot.py",
        "test_session_snapshot_access_control_owner_admin_only",
    ),
    (
        "Prompt contract bypass inventory",
        "tests/unit/prompt_templates/test_taxonomy.py",
        "test_prompt_source_taxonomy_clears_known_template_bypass_entrypoints",
    ),
    (
        "Sensitive output redaction",
        "tests/unit/admin/test_admin_users_api_models.py",
        "test_sanitize_log_kwargs_redacts_sensitive_top_level_fields",
    ),
    (
        "Reviewer-only thinking evidence",
        "tests/contract/test_thinking_visibility_contract.py",
        "test_learner_report_contract_should_not_include_raw_thinking",
    ),
)


@dataclass(slots=True)
class ExaminerRuntimeSeed:
    agent: Agent
    persona: Persona
    runtime_profile: VoiceRuntimeProfile
    ruleset: ScoringRuleset
    knowledge_base: KnowledgeBase
    learning_template: PracticeTemplate
    examiner_template: PracticeTemplate
    scenario: Scenario


def build_examiner_seed_manifest(
    *, owner_id: str = "sales-enablement", import_batch_id: str = "issue-77-final-gate"
) -> dict[str, Any]:
    chapters = [
        {
            "chapter_key": f"chapter-{index:02d}",
            "title": title,
            "owner_id": owner_id,
            "source": "admin_import",
            "import_batch_id": import_batch_id,
        }
        for index, title in enumerate(
            (
                "客户画像识别",
                "痛点挖掘",
                "价值主张",
                "ROI 证据",
                "异议处理",
                "推进承诺",
                "复盘改进",
            ),
            start=1,
        )
    ]
    questions = [
        {
            "question_id": f"q-{index:02d}",
            "chapter_key": chapters[(index - 1) % len(chapters)]["chapter_key"],
            "dimension": SCORING_DIMENSIONS[(index - 1) % len(SCORING_DIMENSIONS)],
            "prompt": f"请用销售训练方法回答第 {index} 题。",
            "expected_keywords": ["客户", "证据", "下一步"],
            "owner_id": owner_id,
            "source": "admin_import",
            "import_batch_id": import_batch_id,
        }
        for index in range(1, 21)
    ]
    return {
        "schema_version": "examiner_seed_v1",
        "owner_id": owner_id,
        "source": "admin_import",
        "import_batch_id": import_batch_id,
        "chapters": chapters,
        "questions": questions,
    }


def validate_examiner_seed_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    chapters = manifest.get("chapters")
    questions = manifest.get("questions")
    assert isinstance(chapters, list)
    assert isinstance(questions, list)
    assert len(chapters) >= 7
    assert len(questions) >= 20

    chapter_keys = {str(chapter["chapter_key"]) for chapter in chapters}
    dimensions = {str(question["dimension"]) for question in questions}
    assert dimensions >= set(SCORING_DIMENSIONS)

    owner_id = str(manifest["owner_id"])
    import_batch_id = str(manifest["import_batch_id"])
    source = str(manifest["source"])
    for item in [*chapters, *questions]:
        assert item["owner_id"] == owner_id
        assert item["source"] == source
        assert item["import_batch_id"] == import_batch_id
        assert "<script" not in str(item).lower()
        assert "ignore previous" not in str(item).lower()
    for question in questions:
        assert str(question["chapter_key"]) in chapter_keys
        assert question["expected_keywords"]

    return {
        "chapter_count": len(chapters),
        "question_count": len(questions),
        "dimensions": sorted(dimensions),
        "owner_id": owner_id,
        "source": source,
        "import_batch_id": import_batch_id,
    }


def assert_security_evidence_manifest_is_executable() -> list[dict[str, str]]:
    resolved: list[dict[str, str]] = []
    for gate, relative_path, test_name in SECURITY_EVIDENCE:
        path = BACKEND_ROOT / relative_path
        assert path.exists(), f"missing security evidence file: {relative_path}"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        test_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        assert test_name in test_names, f"missing {relative_path}::{test_name}"
        resolved.append({"gate": gate, "path": relative_path, "test_name": test_name})
    return resolved


def assert_examiner_backend_does_not_import_sales_bot() -> None:
    source_paths = [
        PROJECT_ROOT / "backend/src/curriculum_practice",
        PROJECT_ROOT / "backend/src/common/training_tasks",
        PROJECT_ROOT / "backend/src/training_runtime",
    ]
    for root in source_paths:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                else:
                    continue
                assert not any(
                    name == "sales_bot" or name.startswith("sales_bot.")
                    for name in imported
                ), f"examiner boundary imports sales_bot in {path}"


async def seed_examiner_runtime(
    db: AsyncSession,
    *,
    owner_id: str,
) -> ExaminerRuntimeSeed:
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Issue 77 Learning Examiner Agent",
        description="Backend final gate examiner agent",
        category="sales",
        system_prompt="Assess learner answers using the published scoring rubric.",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Issue 77 Examiner Persona",
        description="Examiner persona for sales training learning checks",
        category="examiner",
        difficulty="medium",
        system_prompt="Ask concise exam questions and keep scoring fair.",
        status="active",
    )
    runtime_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Issue 77 StepFun Runtime",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.3,
    )
    ruleset = ScoringRuleset(
        ruleset_id=str(uuid.uuid4()),
        scenario_type="sales",
        version="issue-77-examiner-v1",
        display_name="Issue 77 Examiner Rubric",
        status="published",
        definition_json={
            "dimensions": list(SCORING_DIMENSIONS),
            "passing_score": 70,
        },
        is_active=True,
    )
    knowledge_base = KnowledgeBase(
        id=str(uuid.uuid4()),
        name="Issue 77 Imported Seed Knowledge",
        description="Imported seed content for examiner final gate",
        category="product",
        vector_collection="issue_77_examiner_seed",
        status="active",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="Issue 77 学习考官",
        description="Learning examiner final gate scenario",
        is_active=True,
    )
    db.add_all([agent, persona, runtime_profile, ruleset, knowledge_base, scenario])
    await db.flush()
    db.add(AgentPersona(agent_id=agent.id, persona_id=persona.id, is_default=True))

    learning_template = PracticeTemplate(
        template_id=str(uuid.uuid4()),
        name="Issue 77 产品知识学习",
        description="product knowledge learning stage",
        scenario_type="sales",
        mode="learning",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        status="published",
        version=1,
        content_hash="sha256:issue77learning",
        published_by=owner_id,
        published_at=datetime.now(UTC),
    )
    examiner_template = PracticeTemplate(
        template_id=str(uuid.uuid4()),
        name="Issue 77 学习考官考试",
        description="product objection value examiner stage",
        scenario_type="sales",
        mode="examiner",
        agent_id=agent.id,
        persona_id=persona.id,
        runtime_profile_id=runtime_profile.id,
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=ruleset.ruleset_id,
        knowledge_base_refs=[knowledge_base.id],
        status="published",
        version=1,
        content_hash="sha256:issue77examiner",
        max_stage_duration_seconds=900,
        published_by=owner_id,
        published_at=datetime.now(UTC),
    )
    db.add_all([learning_template, examiner_template])
    await db.commit()
    return ExaminerRuntimeSeed(
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
        learning_template=learning_template,
        examiner_template=examiner_template,
        scenario=scenario,
    )


async def create_reported_completed_session(
    db: AsyncSession,
    *,
    user_id: str,
    template: PracticeTemplate,
    scenario: Scenario,
    dimensions: dict[str, float],
    session_id: str | None = None,
) -> PracticeSession:
    resolved_session_id = session_id or str(uuid.uuid4())
    session = await db.get(PracticeSession, resolved_session_id)
    if session is None:
        session = PracticeSession(session_id=resolved_session_id, user_id=user_id)
        db.add(session)
    session.scenario_id = scenario.scenario_id
    session.agent_id = template.agent_id
    session.persona_id = template.persona_id
    session.voice_runtime_profile_id = template.runtime_profile_id
    session.voice_mode = "stepfun_realtime"
    session.practice_template_id = template.template_id
    session.status = "completed"
    session.report_status = "completed"
    session.logic_score = dimensions.get("value_logic", 7.0) * 10
    session.accuracy_score = dimensions.get("product_knowledge", 7.0) * 10
    session.completeness_score = dimensions.get("objection_handling", 7.0) * 10
    session.effectiveness_snapshot = {"evaluable": True}
    session.runtime_state = {
        "template_stage_context": {
            "template_stage_progress": {
                template.template_id: {"attempts": 1, "score": min(dimensions.values())}
            }
        }
    }
    session.start_time = datetime.now(UTC) - timedelta(minutes=10)
    session.end_time = datetime.now(UTC)
    run = EvaluationRun(
        run_id=str(uuid.uuid4()),
        session_id=session.session_id,
        status="succeeded",
        input_evidence_reference={"source": "issue-77-final-gate"},
        result_payload={"dimensions": dimensions},
    )
    snapshot = TrainingReportSnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session.session_id,
        evaluation_run_id=run.run_id,
        report_payload={
            "overall_score": round(sum(dimensions.values()) / len(dimensions), 2),
            "dimensions": dimensions,
            "lineage": {
                "stage_snapshots": {
                    template.template_id: {"attempts": 1, "score": min(dimensions.values())}
                }
            },
        },
        evidence_completeness={"conversation": True, "rubric": True},
        score_basis="issue_77_executable_seed",
        generated_at=datetime.now(UTC),
    )
    db.add_all([session, run, snapshot])
    await db.commit()
    await db.refresh(session)
    return session


async def run_import_bind_examiner_flow(
    db: AsyncSession,
    *,
    learner: User,
    runtime_seed: ExaminerRuntimeSeed,
    import_manifest: dict[str, Any],
) -> dict[str, Any]:
    task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="Issue 77 导入题库绑定学习考官",
        assignee_id=str(learner.user_id),
        scenario_type="sales",
        goal="完成导入题库后的学习考官考试",
        focus_intent="product_knowledge",
        completion_criteria={
            "minimum_sessions": 1,
            "question_count": len(import_manifest["questions"]),
            "dimension_count": len({item["dimension"] for item in import_manifest["questions"]}),
            "import_batch_id": import_manifest["import_batch_id"],
        },
        practice_template_id=runtime_seed.examiner_template.template_id,
        source="admin_import",
        status="assigned",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    updated_task, exam_session = await start_training_task_session(
        db,
        task,
        TrainingTaskStartSessionRequest(
            agent_id=runtime_seed.agent.id,
            persona_id=runtime_seed.persona.id,
            scenario_id=runtime_seed.scenario.scenario_id,
            runtime_profile_id=runtime_seed.runtime_profile.id,
            voice_mode="stepfun_realtime",
        ),
        current_user=learner,
    )
    exam_session.status = "completed"
    exam_session.report_status = "completed"
    exam_session.effectiveness_snapshot = {"evaluable": True, "main_capability_passed": True}
    await db.commit()
    await create_reported_completed_session(
        db,
        user_id=str(learner.user_id),
        template=runtime_seed.examiner_template,
        scenario=runtime_seed.scenario,
        dimensions={
            "product_knowledge": 8.2,
            "objection_handling": 7.8,
            "value_logic": 8.0,
        },
        session_id=str(exam_session.session_id),
    )
    completed_task = await complete_training_task(
        db,
        updated_task,
        TrainingTaskCompleteRequest(session_id=str(exam_session.session_id)),
    )
    learning_path = await LearningPathService(db).build_for_user(str(learner.user_id))
    return {
        "task": completed_task,
        "session": exam_session,
        "learning_path": learning_path,
    }

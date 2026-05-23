"""Single authority for creating curriculum examiner practice sessions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario
from common.monitoring.logger import get_logger
from common.services.session_runtime_state_service import SessionRuntimeStateService
from curriculum_practice.models import ExaminerAgent, PracticeTemplate, QuestionItem

logger = get_logger(__name__)


@dataclass(slots=True)
class ExaminerSessionCreateResult:
    session: PracticeSession
    examiner_agent: ExaminerAgent


class ExaminerSessionAssembler:
    """Build examiner sessions with frozen curriculum snapshots."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_study_exam_session(
        self,
        *,
        user_id: str,
        learning_content_id: str,
    ) -> ExaminerSessionCreateResult:
        agent = await self._resolve_examiner_agent(learning_content_id)

        questions = await self._load_published_questions(agent)
        scenario = await self._get_or_create_exam_scenario()
        session = PracticeSession(
            user_id=user_id,
            scenario_id=str(scenario.scenario_id),
            status="in_progress",
            report_status="pending",
            curriculum_snapshot=self._build_curriculum_snapshot(
                learning_content_id=learning_content_id,
                agent=agent,
                questions=questions,
            ),
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        await SessionRuntimeStateService(self._db).initialize_on_create(
            str(session.session_id),
            has_runtime_snapshot=isinstance(session.curriculum_snapshot, dict),
            source="examiner_session_assembler",
        )
        return ExaminerSessionCreateResult(session=session, examiner_agent=agent)

    async def _resolve_examiner_agent(
        self,
        learning_content_id: str,
    ) -> ExaminerAgent:
        template_result = await self._db.execute(
            select(PracticeTemplate)
            .where(
                PracticeTemplate.learning_content_id == learning_content_id,
                PracticeTemplate.status == "published",
                PracticeTemplate.examiner_agent_id.isnot(None),
            )
            .order_by(PracticeTemplate.updated_at.desc())
            .limit(1)
        )
        template = template_result.scalar_one_or_none()
        if template is None or not template.examiner_agent_id:
            logger.warning(
                "No published practice template with examiner binding",
                learning_content_id=learning_content_id,
            )
            raise ValueError("[TEMPLATE_EXAMINER_NOT_BOUND]")

        agent = await self._db.get(ExaminerAgent, str(template.examiner_agent_id))
        if agent is None or getattr(agent, "status", None) != "published":
            logger.warning(
                "Template-bound examiner agent unavailable",
                learning_content_id=learning_content_id,
                examiner_agent_id=str(template.examiner_agent_id),
            )
            raise ValueError("[EXAMINER_AGENT_NOT_FOUND]")
        return agent

    async def _load_published_questions(
        self,
        agent: ExaminerAgent,
    ) -> list[QuestionItem]:
        question_ids = [
            str(item).strip()
            for item in (agent.question_source_ids or [])
            if str(item).strip()
        ]
        if not question_ids:
            raise ValueError("[EXAM_QUESTION_BANK_EMPTY]")

        questions_result = await self._db.execute(
            select(QuestionItem).where(
                QuestionItem.question_id.in_(question_ids),
                QuestionItem.status == "published",
                QuestionItem.safety_flagged.is_(False),
            )
        )
        questions_by_id = {
            str(item.question_id): item for item in questions_result.scalars().all()
        }
        questions = [
            questions_by_id[question_id]
            for question_id in question_ids
            if question_id in questions_by_id
        ]
        if not questions:
            raise ValueError("[EXAM_QUESTION_BANK_EMPTY]")
        return questions

    async def _get_or_create_exam_scenario(self) -> Scenario:
        result = await self._db.execute(
            select(Scenario)
            .where(Scenario.scenario_type == "sales", Scenario.is_active.is_(True))
            .order_by(Scenario.created_at.desc())
            .limit(1)
        )
        scenario = result.scalar_one_or_none()
        if scenario is not None:
            return scenario
        scenario = Scenario(
            scenario_type="sales",
            name="AI 考官考核",
            description="课程学习完成后的 AI 考官考核场景。",
            persona_prompt="AI 考官根据题库逐题考核学员。",
            is_active=True,
        )
        self._db.add(scenario)
        await self._db.flush()
        return scenario

    @staticmethod
    def _build_curriculum_snapshot(
        *,
        learning_content_id: str,
        agent: ExaminerAgent,
        questions: list[QuestionItem],
    ) -> dict[str, object]:
        return {
            "kind": "curriculum_examiner_session",
            "learning_content_id": learning_content_id,
            "content_assets": [
                _curriculum_exam_asset_ref("examiner_agent", agent, str(agent.name)),
                *[
                    _curriculum_exam_asset_ref(
                        "question_item", question, str(question.title)
                    )
                    for question in questions
                ],
            ],
        }


def _curriculum_exam_asset_ref(
    asset_type: str, asset: object, label: str
) -> dict[str, object]:
    id_attr = {
        "examiner_agent": "examiner_agent_id",
        "question_item": "question_id",
        "learning_content": "learning_content_id",
    }.get(asset_type, f"{asset_type}_id")
    return {
        "asset_type": asset_type,
        "asset_id": str(getattr(asset, id_attr, "")),
        "version": int(getattr(asset, "version", 0) or 0),
        "hash": getattr(asset, "content_hash", None),
        "snapshot_label": label,
    }

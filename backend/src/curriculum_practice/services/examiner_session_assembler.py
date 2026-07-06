"""Single authority for creating curriculum examiner practice sessions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario
from common.monitoring.logger import get_logger
from common.services.session_runtime_state_service import SessionRuntimeStateService
from curriculum_practice.models import ExaminerAgent, PracticeTemplate, QuestionItem
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.orm_payload_typing import orm_list, set_orm_field
from curriculum_practice.services.practice_templates import published_ref
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.snapshots import (
    RuntimeSnapshotBuildError,
    RuntimeSnapshotService,
)

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
        template, agent = await self._resolve_examiner_template(learning_content_id)

        await self._load_published_questions(agent)
        scenario = await self._get_or_create_exam_scenario()
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            scenario_id=str(scenario.scenario_id),
            status="in_progress",
            report_status="pending",
            practice_template_id=str(template.template_id),
            agent_id=str(template.agent_id),
            persona_id=str(template.persona_id),
            voice_runtime_profile_id=str(template.runtime_profile_id),
            voice_mode=str(template.voice_mode),
        )
        await self._apply_curriculum_snapshot(
            session=session,
            template=template,
            learning_content_id=learning_content_id,
            user_id=user_id,
        )
        if isinstance(session.curriculum_snapshot, dict):
            session.curriculum_snapshot.update(
                self._compat_examiner_snapshot_fields(
                    learning_content_id=learning_content_id,
                )
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

    async def _resolve_examiner_template(
        self,
        learning_content_id: str,
    ) -> tuple[PracticeTemplate, ExaminerAgent]:
        template_result = await self._db.execute(
            select(PracticeTemplate)
            .where(
                PracticeTemplate.learning_content_id == learning_content_id,
                PracticeTemplate.status == "published",
                PracticeTemplate.examiner_agent_id.isnot(None),
            )
        )
        templates = list(template_result.scalars().all())
        if not templates:
            logger.warning(
                "No published practice template with examiner binding",
                learning_content_id=learning_content_id,
            )
            raise ValueError("[TEMPLATE_EXAMINER_NOT_BOUND]")
        if len(templates) > 1:
            logger.warning(
                "Ambiguous published examiner templates for learning content",
                learning_content_id=learning_content_id,
                template_ids=[str(template.template_id) for template in templates],
            )
            raise ValueError("[TEMPLATE_EXAMINER_AMBIGUOUS]")

        template = templates[0]
        agent = await self._db.get(ExaminerAgent, str(template.examiner_agent_id))
        if agent is None or getattr(agent, "status", None) != "published":
            logger.warning(
                "Template-bound examiner agent unavailable",
                learning_content_id=learning_content_id,
                examiner_agent_id=str(template.examiner_agent_id),
            )
            raise ValueError("[EXAMINER_AGENT_NOT_FOUND]")
        return template, agent

    async def _apply_curriculum_snapshot(
        self,
        *,
        session: PracticeSession,
        template: PracticeTemplate,
        learning_content_id: str,
        user_id: str,
    ) -> None:
        snapshot_service = RuntimeSnapshotService.from_database(
            self._db,
            reference_reader=CurriculumAssetReferenceReader(self._db).read_reference,
            situation_packs=await SituationPackRepository.from_database(self._db),
        )
        try:
            snapshot = await snapshot_service.build_for_session(
                published_ref(template),
                {
                    "id": str(session.session_id),
                    "scenario_type": "sales",
                },
                user_id,
            )
        except RuntimeSnapshotBuildError as exc:
            logger.warning(
                "Failed to build examiner session runtime snapshot",
                learning_content_id=learning_content_id,
                template_id=str(template.template_id),
                reason_code=exc.reason_code,
            )
            raise ValueError(f"[RUNTIME_SNAPSHOT_{exc.reason_code.upper()}]") from exc

        set_orm_field(session, "curriculum_snapshot", snapshot.model_dump(mode="json"))

    async def _load_published_questions(
        self,
        agent: ExaminerAgent,
    ) -> list[QuestionItem]:
        question_ids = [
            str(item).strip()
            for item in orm_list(agent.question_source_ids)
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
    def _compat_examiner_snapshot_fields(
        *,
        learning_content_id: str,
    ) -> dict[str, object]:
        return {
            "kind": "curriculum_examiner_session",
            "learning_content_id": learning_content_id,
        }

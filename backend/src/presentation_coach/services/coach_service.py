"""
Presentation Coach Service - Business logic for PPT coaching
Handles coaching workflow, scoring, and session management
"""
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ForbiddenWord,
    InterruptionEvent,
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
)
from common.db.schemas import InterruptionType, SessionDetail
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class PresentationCoachService:
    """
    Main service for PPT presentation coaching
    Orchestrates interruption detection, scoring, and session management
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: str,
        presentation_id: str
    ) -> Result[PracticeSession]:
        """
        Create a new practice session
        """
        try:
            # Verify presentation exists and is ready
            result = await self.db.execute(
                select(Presentation).where(
                    Presentation.presentation_id == presentation_id,
                    Presentation.status == "ready"
                )
            )
            presentation = result.scalar_one_or_none()

            if not presentation:
                return Result.fail("Presentation not found or not ready")

            # Get scenario ID
            result = await self.db.execute(
                select(Scenario).where(Scenario.scenario_type == "presentation")
            )
            scenario = result.scalar_one_or_none()

            if not scenario:
                return Result.fail("Presentation scenario not configured")

            # Create session
            session = PracticeSession(
                user_id=user_id,
                scenario_id=scenario.scenario_id,
                presentation_id=presentation_id,
                status="preparing"
            )

            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)

            logger.info(f"Created session: {session.session_id}")
            return Result.ok(session)

        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            await self.db.rollback()
            return Result.fail("[USE_KEYWORD_SEARCH]")

    async def start_session(self, session_id: str) -> Result[bool]:
        """Start a practice session"""
        try:
            result = await self.db.execute(
                update(PracticeSession)
                .where(PracticeSession.session_id == session_id)
                .values(status="in_progress", start_time=datetime.utcnow())
            )
            await self.db.commit()

            logger.info(f"Started session: {session_id}")
            return Result.ok(True)

        except Exception as e:
            logger.error(f"Failed to start session: {str(e)}")
            await self.db.rollback()
            return Result.fail("[START_FAILED]")

    async def end_session(self, session_id: str) -> Result[SessionDetail]:
        """End session and generate report"""
        try:
            result = await self.db.execute(
                update(PracticeSession)
                .where(PracticeSession.session_id == session_id)
                .values(
                    status="scoring",
                    end_time=datetime.utcnow()
                )
            )
            await self.db.commit()

            # Get session details
            session_result = await self.db.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
            session = session_result.scalar_one_or_none()

            if session:
                # Generate scores
                await self._calculate_scores(session)
                await self.db.refresh(session)

            return Result.ok(session)

        except Exception as e:
            logger.error(f"Failed to end session: {str(e)}")
            await self.db.rollback()
            return Result.fail("[END_FAILED]")

    async def get_current_page_requirements(
        self,
        session_id: str,
        page_number: int
    ) -> Result[dict[str, Any]]:
        """Get required talking points for current page"""
        try:
            # Get session
            session_result = await self.db.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
            session = session_result.scalar_one_or_none()

            if not session:
                return Result.fail("[SESSION_NOT_FOUND]")

            # Get page requirements
            page_result = await self.db.execute(
                select(Page).where(
                    Page.presentation_id == session.presentation_id,
                    Page.page_number == page_number
                )
            )
            page = page_result.scalar_one_or_none()

            if not page:
                return Result.ok({
                    "page_number": page_number,
                    "required_points": [],
                    "forbidden_words": []
                })

            # Get required points
            points_result = await self.db.execute(
                select(RequiredTalkingPoint).where(
                    RequiredTalkingPoint.page_id == page.page_id,
                    RequiredTalkingPoint.confirmed_by_admin == True
                )
            )
            required_points = points_result.scalars().all()

            # Get forbidden words
            words_result = await self.db.execute(
                select(ForbiddenWord).where(
                    (ForbiddenWord.presentation_id == session.presentation_id) |
                    (ForbiddenWord.page_id == page.page_id)
                )
            )
            forbidden_words = words_result.scalars().all()

            return Result.ok({
                "page_number": page_number,
                "page_content": page.ocr_extracted_text,
                "required_points": [p.description for p in required_points],
                "forbidden_words": [w.phrase for w in forbidden_words]
            })

        except Exception as e:
            logger.error(f"Failed to get page requirements: {str(e)}")
            return Result.fail("[USE_KEYWORD_SEARCH]")

    async def record_interruption(
        self,
        session_id: str,
        interruption_type: InterruptionType,
        trigger_content: str,
        ai_response: str,
        detection_latency_ms: int
    ) -> Result[InterruptionEvent]:
        """Record an interruption event"""
        try:
            event = InterruptionEvent(
                session_id=session_id,
                interruption_type=interruption_type.value,
                trigger_content=trigger_content,
                ai_response=ai_response,
                detection_latency_ms=detection_latency_ms
            )

            self.db.add(event)

            # Increment interruption count
            await self.db.execute(
                update(PracticeSession)
                .where(PracticeSession.session_id == session_id)
                .values(interruption_count=PracticeSession.interruption_count + 1)
            )

            await self.db.commit()
            await self.db.refresh(event)

            return Result.ok(event)

        except Exception as e:
            logger.error(f"Failed to record interruption: {str(e)}")
            await self.db.rollback()
            return Result.fail("[LOG_FAILED]")

    async def _calculate_scores(self, session: PracticeSession):
        """Calculate session scores (logic, accuracy, completeness)"""
        # Get interruption events
        result = await self.db.execute(
            select(InterruptionEvent).where(
                InterruptionEvent.session_id == session.session_id
            )
        )
        events = result.scalars().all()

        # Calculate scores based on interruptions
        total_events = len(events)

        if total_events == 0:
            # No interruptions - perfect score
            session.logic_score = 100.0
            session.accuracy_score = 100.0
            session.completeness_score = 100.0
        else:
            # Count effective interruptions
            effective = sum(1 for e in events if e.was_effective)

            # Logic score: based on effective interruptions
            session.logic_score = min(100, (effective / total_events) * 100)

            # Accuracy score: inverse of forbidden word interruptions
            forbidden_count = sum(
                1 for e in events
                if e.interruption_type == "forbidden_word"
            )
            session.accuracy_score = max(0, 100 - (forbidden_count * 10))

            # Completeness score: based on required points coverage
            missing_count = sum(
                1 for e in events
                if e.interruption_type == "missing_point"
            )
            session.completeness_score = max(0, 100 - (missing_count * 15))

        # Mark as completed
        session.status = "completed"

        await self.db.commit()

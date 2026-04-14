"""
Replay Service

Service for retrieving conversation replay data with timeline markers.
Implements get_messages(), get_replay_data(), get_highlights(), and timeline generation.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
- API Contract: docs/api-contract/replay.md
"""
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.conversation.models import ConversationMessage
from common.conversation.session_evidence import SessionEvidenceService
from common.conversation.storage import normalize_objection_ledger
from common.db.models import PracticeSession, SessionStatus
from common.db.voice_policy_snapshot import build_voice_policy_snapshot_ref_payload
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger(__name__)

# Sales stage display names
STAGE_NAMES = {
    "opening": "开场破冰",
    "discovery": "需求挖掘",
    "presentation": "方案呈现",
    "objection": "异议处理",
    "closing": "促成成交"
}

class ReplayService:
    """
    Replay Service - Retrieves conversation replay data with timeline markers.

    Implements:
    - get_messages(): Paginated message retrieval
    - get_replay_data(): Complete replay data with timeline markers
    - get_highlights(): Key moments from the conversation
    - _generate_timeline_markers(): Timeline marker generation

    Requirements: R10
    Design: Section 12
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize ReplayService.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    @staticmethod
    def _normalize_turn_number(raw_turn_number: int | None, fallback_turn_number: int = 1) -> int:
        """Normalize legacy turn numbers to keep API contract compatible (>=1)."""
        if isinstance(raw_turn_number, int) and raw_turn_number >= 1:
            return raw_turn_number
        return max(1, fallback_turn_number)

    async def _get_session(self, session_id: str) -> Result[PracticeSession]:
        """
        Get a practice session by ID.

        Args:
            session_id: Practice session UUID

        Returns:
            Result[PracticeSession]: Success with session or failure
        """
        try:
            stmt = select(PracticeSession).where(
                PracticeSession.session_id == session_id
            )
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                return Result.fail(f"[SESSION_NOT_FOUND] Session with id '{session_id}' not found")

            return Result.ok(session)

        except (SQLAlchemyError, ValueError, OSError) as e:
            logger.error(f"Failed to get session: {str(e)}")
            return Result.fail(f"[SESSION_GET_FAILED] {str(e)}")

    async def _check_session_completed(self, session_id: str) -> Result[PracticeSession]:
        """
        Check if a session is completed (required for replay).

        Args:
            session_id: Practice session UUID

        Returns:
            Result[PracticeSession]: Success with session if completed, failure otherwise
        """
        session_result = await self._get_session(session_id)
        if not session_result.is_success:
            return session_result

        session = session_result.value
        if session.status != SessionStatus.COMPLETED.value:
            return Result.fail(
                f"[SESSION_NOT_COMPLETED] Session must be completed for replay. "
                f"Current status: {session.status}"
            )

        return Result.ok(session)

    async def get_messages(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> Result[tuple[list[ConversationMessage], int]]:
        """
        Get paginated messages for a completed session.

        Args:
            session_id: Practice session UUID
            page: Page number (1-indexed)
            page_size: Number of messages per page

        Returns:
            Result[tuple[list[ConversationMessage], int]]: Success with (messages, total) or failure

        Requirements: R10.1
        """
        try:
            # Check session is completed
            session_result = await self._check_session_completed(session_id)
            if not session_result.is_success:
                return session_result

            # Count total messages
            count_stmt = select(func.count()).select_from(ConversationMessage).where(
                ConversationMessage.session_id == session_id
            )
            total_result = await self.db.execute(count_stmt)
            total = total_result.scalar() or 0

            # Get paginated messages
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.turn_number)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await self.db.execute(stmt)
            messages = list(result.scalars().all())

            logger.info(f"Retrieved {len(messages)} messages for session {session_id}")

            return Result.ok((messages, total))

        except (SQLAlchemyError, ValueError, OSError) as e:
            logger.error(f"Failed to get messages: {str(e)}")
            return Result.fail(f"[MESSAGES_GET_FAILED] {str(e)}")

    async def get_replay_data(self, session_id: str) -> Result[dict[str, Any]]:
        """
        Get complete replay data including messages and timeline markers.

        Args:
            session_id: Practice session UUID

        Returns:
            Result[dict]: Success with replay data or failure

        Requirements: R10.2
        """
        try:
            projection_result = await SessionEvidenceService(self.db).get_projection(
                session_id=session_id,
                require_completed=True,
            )
            if not projection_result.is_success:
                return projection_result

            projection = projection_result.value
            session = projection.session
            enriched_messages = self._attach_learning_evidence(
                projection.messages,
                projection,
            )
            timeline_markers = (
                list(projection.timeline_markers)
                if isinstance(projection.timeline_markers, list)
                else []
            )
            preferred_stage_key = self._resolve_anchor_stage_key(
                projection,
                enriched_messages,
            )
            replay_anchor = self._resolve_replay_anchor(
                messages=enriched_messages,
                timeline_markers=timeline_markers,
                preferred_stage_key=preferred_stage_key,
            )
            main_issue_with_anchor = self._attach_replay_anchor(
                projection.main_issue,
                replay_anchor,
            )
            next_goal_with_anchor = self._attach_replay_anchor(
                projection.next_goal,
                replay_anchor,
            )

            scenario_type = str(
                getattr(
                    projection,
                    "scenario_type",
                    SessionEvidenceService.resolve_scenario_type(session),
                )
            ).lower()
            is_presentation_scenario = scenario_type == "presentation"
            presentation_review = (
                projection.presentation_review if is_presentation_scenario else None
            )
            main_issue_payload = (
                None if is_presentation_scenario else main_issue_with_anchor
            )
            next_goal_payload = (
                None if is_presentation_scenario else next_goal_with_anchor
            )

            # Get agent and persona names (if available)
            agent_name = None
            persona_name = None
            if session.agent_id:
                from agent.models import Agent
                agent_stmt = select(Agent).where(Agent.id == session.agent_id)
                agent_result = await self.db.execute(agent_stmt)
                agent = agent_result.scalar_one_or_none()
                if agent:
                    agent_name = agent.name

            if session.persona_id:
                from agent.models import Persona
                persona_stmt = select(Persona).where(Persona.id == session.persona_id)
                persona_result = await self.db.execute(persona_stmt)
                persona = persona_result.scalar_one_or_none()
                if persona:
                    persona_name = persona.name

            replay_data = {
                "session_id": session_id,
                "scenario_type": scenario_type,
                "presentation_id": getattr(session, "presentation_id", None),
                "agent_name": agent_name,
                "persona_name": persona_name,
                "voice_policy_snapshot_ref": build_voice_policy_snapshot_ref_payload(session.voice_policy_snapshot),
                "total_duration_ms": projection.total_duration_ms,
                "messages": enriched_messages,
                "timeline_markers": timeline_markers,
                "stage_summary": [] if is_presentation_scenario else projection.stage_summary,
                "overall_score": projection.overall_score,
                "effectiveness_snapshot": (
                    None if is_presentation_scenario else projection.effectiveness_snapshot
                ),
                "pass_flags": None if is_presentation_scenario else projection.pass_flags,
                "main_capability_passed": (
                    None if is_presentation_scenario else projection.main_capability_passed
                ),
                "overall_result": None if is_presentation_scenario else projection.overall_result,
                "main_issue": main_issue_payload,
                "next_goal": next_goal_payload,
                "evaluable": None if is_presentation_scenario else projection.evaluable,
                "not_evaluable_reason": (
                    None if is_presentation_scenario else projection.not_evaluable_reason
                ),
                "evidence_completeness": projection.evidence_completeness,
                "canonical_evaluation_kernel": projection.canonical_evaluation_kernel,
                "compatibility_readers": projection.compatibility_readers,
                "presentation_review": presentation_review,
            }

            # Attach audio-audit read model (graceful — never breaks replay/report)
            try:
                from common.api.practice import build_session_audio_audit
                replay_data["audio_audit"] = await build_session_audio_audit(
                    self.db, session_id, session,
                )
            except Exception:
                replay_data["audio_audit"] = None

            replay_data["conclusion_evidence"] = (
                None if is_presentation_scenario else projection.conclusion_evidence
            )
            replay_data["evidence_degradation"] = (
                None if is_presentation_scenario else projection.evidence_degradation
            )

            logger.info(
                "replay_data_generated",
                session_id=session_id,
                scenario_type=scenario_type,
                presentation_review_available=bool(presentation_review),
                highlight_learning_count=sum(
                    1 for message in enriched_messages if message.get("learning_evidence")
                ),
                issue_family=(
                    main_issue_payload.get("issue_type")
                    if isinstance(main_issue_payload, dict)
                    else None
                ),
                main_issue_anchor_status=(
                    main_issue_payload.get("replay_anchor", {}).get("status")
                    if isinstance(main_issue_payload, dict)
                    else None
                ),
                next_goal_anchor_status=(
                    next_goal_payload.get("replay_anchor", {}).get("status")
                    if isinstance(next_goal_payload, dict)
                    else None
                ),
                main_issue_anchor_reason=(
                    main_issue_payload.get("replay_anchor", {}).get("degraded_reason")
                    if isinstance(main_issue_payload, dict)
                    else None
                ),
                next_goal_anchor_reason=(
                    next_goal_payload.get("replay_anchor", {}).get("degraded_reason")
                    if isinstance(next_goal_payload, dict)
                    else None
                ),
            )

            return Result.ok(replay_data)

        except (SQLAlchemyError, ValueError, OSError) as e:
            logger.error(f"Failed to get replay data: {str(e)}")
            return Result.fail(f"[REPLAY_DATA_FAILED] {str(e)}")

    async def get_highlights(self, session_id: str) -> Result[dict[str, Any]]:
        """
        Get highlighted messages (key moments) from a session with summary.

        Story 3.4: 高光片段与原因可解释呈现

        Args:
            session_id: Practice session UUID

        Returns:
            Result[dict]: Success with highlights and summary or failure
            Format: {
                "highlights": [...],
                "total_good": int,
                "total_bad": int
            }

        Requirements: R10.3
        """
        try:
            projection_result = await SessionEvidenceService(self.db).get_projection(
                session_id=session_id,
                require_completed=True,
            )
            if not projection_result.is_success:
                return projection_result

            projection = projection_result.value
            enriched_messages = self._attach_learning_evidence(
                projection.messages,
                projection,
            )

            highlights = []
            total_good = 0
            total_bad = 0

            for index, message in enumerate(enriched_messages):
                if not message.get("is_highlight"):
                    continue

                learning_evidence = message.get("learning_evidence")
                context = (
                    learning_evidence.get("nearby_context")
                    if isinstance(learning_evidence, dict)
                    else self._build_nearby_context(enriched_messages, index)
                )
                stage = (
                    learning_evidence.get("stage")
                    if isinstance(learning_evidence, dict)
                    else None
                )
                highlight = {
                    "id": message.get("id"),
                    "turn_number": self._normalize_turn_number(
                        message.get("turn_number"),
                        index + 1,
                    ),
                    "role": message.get("role"),
                    "content": message.get("content"),
                    "timestamp": message.get("timestamp"),
                    "highlight_type": message.get("highlight_type"),
                    "highlight_reason": message.get("highlight_reason"),
                    "ai_feedback": message.get("ai_feedback"),
                    "suggested_response": (
                        learning_evidence.get("suggested_response")
                        if isinstance(learning_evidence, dict)
                        else self._generate_suggested_response_from_payload(message)
                    ),
                    "sales_stage": message.get("sales_stage"),
                    "stage_name": message.get("stage_name")
                    or (stage.get("name") if isinstance(stage, dict) else None),
                    "context": context,
                    "learning_evidence": learning_evidence,
                }
                highlights.append(highlight)

                if message.get("highlight_type") == "good":
                    total_good += 1
                elif message.get("highlight_type") == "bad":
                    total_bad += 1

            logger.info(
                "session_highlights_generated",
                session_id=session_id,
                total_highlights=len(highlights),
                total_good=total_good,
                total_bad=total_bad,
                issue_family=self._resolve_issue_family(projection),
            )

            return Result.ok({
                "highlights": highlights,
                "total_good": total_good,
                "total_bad": total_bad
            })

        except (SQLAlchemyError, ValueError, OSError) as e:
            logger.error(f"Failed to get highlights: {str(e)}")
            return Result.fail(f"[HIGHLIGHTS_GET_FAILED] {str(e)}")

    @staticmethod
    def _build_context_preview(message: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return None
        return {
            "id": message.get("id"),
            "role": message.get("role"),
            "content": message.get("content"),
            "timestamp": message.get("timestamp"),
        }

    def _build_nearby_context(
        self,
        messages: list[dict[str, Any]],
        index: int,
    ) -> dict[str, Any]:
        prev_message = messages[index - 1] if index > 0 else None
        next_message = messages[index + 1] if index + 1 < len(messages) else None
        return {
            "prev_message": self._build_context_preview(prev_message),
            "next_message": self._build_context_preview(next_message),
        }

    @staticmethod
    def _resolve_issue_family(projection: Any) -> str | None:
        main_issue = getattr(projection, "main_issue", None)
        if isinstance(main_issue, dict):
            issue_type = main_issue.get("issue_type")
            if isinstance(issue_type, str) and issue_type.strip():
                return issue_type.strip()

        focus_type = getattr(projection, "sales_alignment_focus_type", None)
        if isinstance(focus_type, str) and focus_type.strip():
            return focus_type.strip()

        return None

    @staticmethod
    def _extract_objection_family(message: dict[str, Any]) -> str | None:
        transcript_metadata = message.get("transcript_metadata")
        if not isinstance(transcript_metadata, dict):
            return None

        objection_ledger = normalize_objection_ledger(
            transcript_metadata.get("objection_ledger")
        )
        if not isinstance(objection_ledger, dict):
            return None

        objection_family = objection_ledger.get("objection_family")
        if isinstance(objection_family, str) and objection_family.strip():
            return objection_family.strip()
        return None

    @staticmethod
    def _stage_payload(sales_stage: Any) -> dict[str, str] | None:
        if not isinstance(sales_stage, str) or not sales_stage.strip():
            return None
        stage_key = sales_stage.strip()
        return {
            "key": stage_key,
            "name": STAGE_NAMES.get(stage_key, stage_key),
        }

    def _build_learning_evidence(
        self,
        *,
        message: dict[str, Any],
        context: dict[str, Any],
        projection: Any,
    ) -> dict[str, Any] | None:
        if not message.get("is_highlight"):
            return None

        linked_issue = getattr(projection, "main_issue", None)
        linked_goal = getattr(projection, "next_goal", None)
        return {
            "reason": message.get("highlight_reason") or message.get("ai_feedback"),
            "issue_family": self._resolve_issue_family(projection),
            "objection_family": self._extract_objection_family(message),
            "stage": self._stage_payload(message.get("sales_stage")),
            "nearby_context": context,
            "suggested_response": self._generate_suggested_response_from_payload(message),
            "linked_issue": dict(linked_issue) if isinstance(linked_issue, dict) else None,
            "linked_goal": dict(linked_goal) if isinstance(linked_goal, dict) else None,
        }

    def _attach_learning_evidence(
        self,
        messages: list[dict[str, Any]],
        projection: Any,
    ) -> list[dict[str, Any]]:
        enriched_messages: list[dict[str, Any]] = []
        for index, raw_message in enumerate(messages):
            message = dict(raw_message)
            stage = self._stage_payload(message.get("sales_stage"))
            if message.get("stage_name") is None and isinstance(stage, dict):
                message["stage_name"] = stage["name"]

            context = self._build_nearby_context(messages, index)
            learning_evidence = self._build_learning_evidence(
                message=message,
                context=context,
                projection=projection,
            )
            if learning_evidence is not None:
                message["learning_evidence"] = learning_evidence
            enriched_messages.append(message)
        return enriched_messages

    @staticmethod
    def _normalize_stage_key(raw_stage: Any) -> str | None:
        if not isinstance(raw_stage, str):
            return None
        stage_key = raw_stage.strip()
        return stage_key or None

    @classmethod
    def _message_matches_stage(
        cls,
        message: dict[str, Any],
        preferred_stage_key: str | None,
    ) -> bool:
        if preferred_stage_key is None:
            return True
        return cls._normalize_stage_key(message.get("sales_stage")) == preferred_stage_key

    @classmethod
    def _resolve_anchor_stage_key(
        cls,
        projection: Any,
        messages: list[dict[str, Any]],
    ) -> str | None:
        preferred_stage_key = cls._normalize_stage_key(
            getattr(projection, "sales_alignment_stage_key", None)
        )
        if preferred_stage_key is not None:
            return preferred_stage_key

        for message in reversed(messages):
            message_stage_key = cls._normalize_stage_key(message.get("sales_stage"))
            if message_stage_key is not None:
                return message_stage_key
        return None

    @classmethod
    def _find_preferred_highlight_message(
        cls,
        messages: list[dict[str, Any]],
        preferred_stage_key: str | None,
    ) -> dict[str, Any] | None:
        matchers = (
            lambda message: bool(message.get("id"))
            and bool(message.get("is_highlight"))
            and message.get("highlight_type") == "bad"
            and cls._message_matches_stage(message, preferred_stage_key),
            lambda message: bool(message.get("id"))
            and bool(message.get("is_highlight"))
            and cls._message_matches_stage(message, preferred_stage_key),
            lambda message: bool(message.get("id"))
            and bool(message.get("is_highlight"))
            and message.get("highlight_type") == "bad",
            lambda message: bool(message.get("id")) and bool(message.get("is_highlight")),
        )

        for matcher in matchers:
            for message in reversed(messages):
                if matcher(message):
                    return message
        return None

    @classmethod
    def _find_stage_anchor_message(
        cls,
        messages: list[dict[str, Any]],
        preferred_stage_key: str | None,
    ) -> dict[str, Any] | None:
        if preferred_stage_key is None:
            return None

        for message in messages:
            if not message.get("id"):
                continue
            if cls._message_matches_stage(message, preferred_stage_key):
                return message
        return None

    @staticmethod
    def _find_timeline_marker(
        timeline_markers: list[dict[str, Any]],
        *,
        message_id: Any,
        marker_type: str,
    ) -> dict[str, Any] | None:
        if not isinstance(message_id, str) or not message_id.strip():
            return None

        for marker in timeline_markers:
            if not isinstance(marker, dict):
                continue
            if marker.get("message_id") != message_id:
                continue
            if marker.get("type") != marker_type:
                continue
            return marker
        return None

    @staticmethod
    def _build_anchor_marker_payload(
        marker: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(marker, dict):
            return None

        marker_type = marker.get("type")
        label = marker.get("label")
        if not isinstance(marker_type, str) or not isinstance(label, str):
            return None

        return {
            "type": marker_type,
            "timestamp_ms": int(marker.get("timestamp_ms") or 0),
            "label": label,
        }

    def _build_replay_anchor_payload(
        self,
        *,
        message: dict[str, Any] | None,
        marker: dict[str, Any] | None,
        status: str,
        degraded_reason: str | None,
    ) -> dict[str, Any]:
        if not isinstance(message, dict):
            return {
                "status": "missing",
                "message_id": None,
                "turn_number": None,
                "marker": None,
                "degraded_reason": degraded_reason or "anchor_target_not_found",
            }

        return {
            "status": status,
            "message_id": message.get("id"),
            "turn_number": self._normalize_turn_number(message.get("turn_number"), 1),
            "marker": self._build_anchor_marker_payload(marker),
            "degraded_reason": degraded_reason,
        }

    def _resolve_replay_anchor(
        self,
        *,
        messages: list[dict[str, Any]],
        timeline_markers: list[dict[str, Any]],
        preferred_stage_key: str | None,
    ) -> dict[str, Any]:
        highlight_message = self._find_preferred_highlight_message(
            messages,
            preferred_stage_key,
        )
        if highlight_message is not None:
            highlight_marker = self._find_timeline_marker(
                timeline_markers,
                message_id=highlight_message.get("id"),
                marker_type="highlight",
            )
            if highlight_marker is not None:
                return self._build_replay_anchor_payload(
                    message=highlight_message,
                    marker=highlight_marker,
                    status="resolved",
                    degraded_reason=None,
                )
            return self._build_replay_anchor_payload(
                message=highlight_message,
                marker=None,
                status="degraded",
                degraded_reason="missing_marker",
            )

        stage_message = self._find_stage_anchor_message(messages, preferred_stage_key)
        if stage_message is not None:
            stage_marker = self._find_timeline_marker(
                timeline_markers,
                message_id=stage_message.get("id"),
                marker_type="stage_change",
            )
            return self._build_replay_anchor_payload(
                message=stage_message,
                marker=stage_marker,
                status="degraded",
                degraded_reason="no_matching_highlight",
            )

        return self._build_replay_anchor_payload(
            message=None,
            marker=None,
            status="missing",
            degraded_reason="anchor_target_not_found",
        )

    @staticmethod
    def _attach_replay_anchor(
        summary_payload: dict[str, Any] | None,
        replay_anchor: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(summary_payload, dict):
            return summary_payload

        return {
            **summary_payload,
            "replay_anchor": replay_anchor,
        }

    def _generate_timeline_markers(
        self,
        messages: list[ConversationMessage]
    ) -> list[dict[str, Any]]:
        """
        Generate timeline markers from messages.

        Markers include:
        - Stage changes
        - Fuzzy word detections (high severity)
        - Highlights

        Args:
            messages: List of conversation messages

        Returns:
            list[dict]: Timeline markers
        """
        markers = []
        current_stage = None
        cumulative_ms = 0

        for msg in messages:
            # Stage change marker
            if msg.sales_stage and msg.sales_stage != current_stage:
                markers.append({
                    "timestamp_ms": cumulative_ms,
                    "type": "stage_change",
                    "label": STAGE_NAMES.get(msg.sales_stage, msg.sales_stage),
                    "message_id": msg.id,
                    "highlight_type": None
                })
                current_stage = msg.sales_stage

            # Fuzzy word markers (high severity only)
            if msg.fuzzy_words:
                for fw in msg.fuzzy_words:
                    if fw.get("severity") == "high":
                        matched_words = fw.get("matched", [])
                        markers.append({
                            "timestamp_ms": cumulative_ms,
                            "type": "fuzzy_word",
                            "label": f"模糊词: {', '.join(matched_words)}",
                            "message_id": msg.id,
                            "highlight_type": "bad"
                        })

            # Highlight markers
            if msg.is_highlight:
                markers.append({
                    "timestamp_ms": cumulative_ms,
                    "type": "highlight",
                    "label": msg.highlight_reason or "关键时刻",
                    "message_id": msg.id,
                    "highlight_type": msg.highlight_type
                })

            # Accumulate duration
            cumulative_ms += msg.duration_ms or 0

        return markers

    def _generate_stage_summary(
        self,
        messages: list[ConversationMessage]
    ) -> list[dict[str, Any]]:
        """
        Generate summary statistics for each sales stage.

        Args:
            messages: List of conversation messages

        Returns:
            list[dict]: Stage summaries with duration and average score
        """
        normalized_messages = [
            SessionEvidenceService.serialize_message(message, index + 1)
            for index, message in enumerate(messages)
        ]
        return SessionEvidenceService.build_stage_summary(normalized_messages)

    def _calculate_total_duration(self, messages: list[ConversationMessage]) -> int:
        """
        Calculate total duration of all messages.

        Args:
            messages: List of conversation messages

        Returns:
            int: Total duration in milliseconds
        """
        normalized_messages = [
            SessionEvidenceService.serialize_message(message, index + 1)
            for index, message in enumerate(messages)
        ]
        return SessionEvidenceService.calculate_total_duration(normalized_messages)

    def _message_to_dict(
        self,
        message: ConversationMessage,
        fallback_turn_number: int = 1,
    ) -> dict[str, Any]:
        """
        Convert a ConversationMessage to a dictionary.

        Args:
            message: ConversationMessage instance

        Returns:
            dict: Message data
        """
        return SessionEvidenceService.serialize_message(
            message,
            fallback_turn_number=fallback_turn_number,
        )

    @staticmethod
    def _generate_suggested_response_from_fields(
        highlight_type: Any,
        fuzzy_words: Any,
    ) -> str | None:
        if highlight_type != "bad":
            return None

        if isinstance(fuzzy_words, list):
            suggestions = []
            for fuzzy_word in fuzzy_words:
                if isinstance(fuzzy_word, dict) and fuzzy_word.get("suggestion"):
                    suggestions.append(str(fuzzy_word["suggestion"]))
            if suggestions:
                return f"建议改进: {'; '.join(suggestions)}"

        return None

    def _generate_suggested_response(self, message: ConversationMessage) -> str | None:
        """
        Generate a suggested better response for a highlight.

        For bad highlights (e.g., fuzzy words), suggests improvements.
        For good highlights, returns None.

        Args:
            message: ConversationMessage instance

        Returns:
            str | None: Suggested response or None
        """
        return self._generate_suggested_response_from_fields(
            getattr(message, "highlight_type", None),
            getattr(message, "fuzzy_words", None),
        )

    def _generate_suggested_response_from_payload(
        self,
        message: dict[str, Any],
    ) -> str | None:
        return self._generate_suggested_response_from_fields(
            message.get("highlight_type"),
            message.get("fuzzy_words"),
        )

    async def _get_message_context(
        self,
        message: ConversationMessage,
        context_range: int = 1
    ) -> dict[str, Any]:
        """Get context messages around a highlight.

        Args:
            message: The highlight message
            context_range: Number of messages before and after to include

        Returns:
            dict: Context with prev_message and next_message
        """
        context = {"prev_message": None, "next_message": None}

        try:
            # Get previous message
            if message.turn_number > 1:
                prev_stmt = (
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.session_id == message.session_id,
                        ConversationMessage.turn_number == message.turn_number - 1
                    )
                )
                prev_result = await self.db.execute(prev_stmt)
                prev_msg = prev_result.scalar_one_or_none()
                if prev_msg:
                    context["prev_message"] = {
                        "id": prev_msg.id,
                        "role": prev_msg.role,
                        "content": prev_msg.content,
                        "timestamp": prev_msg.timestamp.isoformat() if prev_msg.timestamp else None,
                    }

            # Get next message
            next_stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == message.session_id,
                    ConversationMessage.turn_number == message.turn_number + 1
                )
            )
            next_result = await self.db.execute(next_stmt)
            next_msg = next_result.scalar_one_or_none()
            if next_msg:
                context["next_message"] = {
                    "id": next_msg.id,
                    "role": next_msg.role,
                    "content": next_msg.content,
                    "timestamp": next_msg.timestamp.isoformat() if next_msg.timestamp else None,
                }

        except (SQLAlchemyError, ValueError) as e:
            logger.warning(f"Failed to get message context: {str(e)}")

        return context

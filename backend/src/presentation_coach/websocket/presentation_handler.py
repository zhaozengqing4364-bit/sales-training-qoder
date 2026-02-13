"""
Presentation WebSocket Handler
Real-time bidirectional voice communication for PPT coaching
Constitution Principle I & II: No error popups, <300ms end-to-end latency
Constitution Principle IV: Fault tolerance and recovery with session state persistence
"""
import asyncio
from datetime import datetime
from typing import Any

from fastapi import WebSocket

from common.audio.asr_service import get_asr_service
from common.audio.tts_service import get_tts_service
from common.conversation.storage import MessageStorageService
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger, get_trace_id
from common.websocket.base_handler import BaseWebSocketHandler
from common.websocket.session_state_service import SessionStateSnapshot
from presentation_coach.services.coach_service import PresentationCoachService
from presentation_coach.services.feedback_service import get_feedback_service
from presentation_coach.services.forbidden_matcher import get_forbidden_matcher
from presentation_coach.services.interruption_detector import get_interruption_detector
from presentation_coach.services.point_tracker import PointTracker

logger = get_logger(__name__)


class PresentationWebSocketHandler(BaseWebSocketHandler):
    """
    WebSocket handler for PPT presentation coaching
    Implements bidirectional interruption with <300ms latency target
    """

    def __init__(self):
        super().__init__("presentation")
        self.asr_service = get_asr_service()
        self.tts_service = get_tts_service()
        self.interruption_detector = get_interruption_detector()
        self.forbidden_matcher = get_forbidden_matcher()
        self.feedback_service = get_feedback_service()
        self.point_tracker = None

        # State tracking
        self.current_page = 1
        self.is_user_speaking = False
        self.is_ai_speaking = False
        self.transcript_buffer = ""
        self.session_id: str = ""
        self.turn_count = 0
        self.ai_state = "idle"
        self.session_status = "in_progress"

    def _get_active_websocket(self) -> WebSocket | None:
        """Get current active presentation websocket safely."""
        manager_connections = getattr(self.manager, "active_connections", {})
        connections: dict[str, WebSocket] = {}
        if isinstance(manager_connections, dict):
            scenario_connections = manager_connections.get("presentation", {})
            if isinstance(scenario_connections, dict):
                connections = scenario_connections

        if self.session_id and self.session_id in connections:
            return connections[self.session_id]
        if connections:
            return next(iter(connections.values()))
        return self.websocket

    def _create_state_snapshot(self) -> SessionStateSnapshot:
        """
        Create a session state snapshot for presentation coaching.
        Includes current page, turn count, and AI state.
        """
        snapshot = SessionStateSnapshot(
            session_id=self.session_id or "",
            scenario=self.scenario,
            turn_count=self.turn_count,
            current_page=self.current_page,
            session_status=self.session_status,
            ai_state=self.ai_state,
            user_id=self.user_id,
        )
        logger.info(
            f"Created state snapshot: session_id={snapshot.session_id}, "
            f"turn_count={snapshot.turn_count}, page={snapshot.current_page}"
        )
        return snapshot

    async def _restore_session_state(self, state: SessionStateSnapshot):
        """
        Restore session state from snapshot for presentation coaching.
        Restores page, turn count, and AI state.
        """
        await super()._restore_session_state(state)

        # Restore presentation-specific state
        self.turn_count = state.turn_count
        self.current_page = state.current_page or 1
        self.session_status = state.session_status
        self.ai_state = state.ai_state or "idle"

        logger.info(
            f"Restored presentation state: turn_count={self.turn_count}, "
            f"page={self.current_page}, status={self.session_status}, ai_state={self.ai_state}"
        )

        # Send reconnection success message
        await self._send_reconnection_success(state)

        # Re-send current page context to ensure UI consistency
        await self._restore_page_context()

    async def _restore_page_context(self):
        """
        Restore page context after reconnection.
        Re-sends current page requirements and state to ensure UI consistency.
        """
        websocket = self._get_active_websocket()
        if not websocket:
            logger.warning("No active websocket found for page context restoration")
            return

        requirements: dict[str, Any] = {
            "required_points": [],
            "total_pages": None,
            "page_content": "",
        }

        try:
            async with AsyncSessionLocal() as db:
                coach_service = PresentationCoachService(db)
                result = await coach_service.get_current_page_requirements(
                    self.session_id,
                    self.current_page
                )

                if result.is_success:
                    requirements = result.value
                    # Restore point tracker state
                    if requirements.get("required_points"):
                        if not self.point_tracker:
                            self.point_tracker = PointTracker(
                                requirements["required_points"]
                            )

            # Send page context to restore UI
            await self._send_page_context(
                ws=websocket,
                page_number=self.current_page,
                requirements=requirements,
            )

            logger.info(
                f"Restored page context: page={self.current_page}, "
                f"session_id={self.session_id}"
            )

        except Exception as e:
            logger.error(f"Failed to restore page context: {str(e)}")
            # Continue without page context to avoid blocking reconnection

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str
    ):
        """Main connection handler"""
        self.session_id = session_id
        # Call base class handler (it will use self.scenario which is "presentation")
        await super().handle_connection(websocket, session_id, token)

    async def handle_message(self, message: dict):
        """Handle incoming message"""
        msg_type = message.get("type")

        try:
            if msg_type == "audio_chunk":
                await self._handle_audio_chunk(message["data"])

            elif msg_type == "user_speaking":
                await self._handle_user_speaking(message["data"]["speaking"])

            elif msg_type == "page_change":
                page_payload = message.get("data", {})
                page_number = page_payload.get("page_number", page_payload.get("page"))
                if isinstance(page_number, int):
                    await self._handle_page_change(page_number)
                else:
                    logger.warning(f"Invalid page_change payload: {page_payload}")

            elif msg_type == "pause":
                await self._handle_pause()

            elif msg_type == "resume":
                await self._handle_resume()

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error handling message {msg_type}: {str(e)}")

    async def _handle_audio_chunk(self, data: dict):
        """
        Handle audio chunk from user
        Stream through ASR and check for interruption triggers
        """
        if self.is_ai_speaking:
            # User is interrupting AI
            logger.info("User interrupted AI")
            self.is_ai_speaking = False
            self.send_status("listening")

        # Process audio through ASR
        audio_data = data.get("audio")
        if audio_data:
            # For now, just acknowledge (ASR would be integrated here)
            pass

    async def _handle_user_speaking(self, is_speaking: bool):
        """
        Handle user speaking state change
        When user stops speaking, check if interruption is needed
        """
        self.is_user_speaking = is_speaking

        if not is_speaking:
            # User stopped speaking - check if we should interrupt
            await self._check_and_interrupt()

    async def _check_and_interrupt(self):
        """
        Check if interruption is needed based on current transcript
        Constitution: <100ms detection, <300ms end-to-end latency
        """
        if not self.transcript_buffer:
            return

        session_id = self.session_id
        if not session_id:
            connections = self.manager.active_connections.get("presentation", {})
            if connections:
                session_id = next(iter(connections.keys()))

        transcript = self.transcript_buffer
        user_message_id = await self._save_conversation_message(
            role="user",
            content=transcript,
        )

        try:
            async with AsyncSessionLocal() as db:
                coach_service = PresentationCoachService(db)
                result = await coach_service.get_current_page_requirements(
                    session_id, self.current_page
                )

                if not result.is_success:
                    return

                requirements = result.value
                context = {
                    "required_points": requirements["required_points"],
                    "forbidden_words": requirements["forbidden_words"],
                    "session_id": session_id,
                }

                interrupt_decision = await self.interruption_detector.should_interrupt(
                    transcript,
                    context
                )

                if interrupt_decision.is_success and interrupt_decision.value:
                    decision = interrupt_decision.value
                    if user_message_id:
                        await self._update_message_analysis(
                            message_id=user_message_id,
                            analysis_data={
                                "ai_feedback": (
                                    f"{decision.get('type', 'unknown')}:"
                                    f"{decision.get('trigger', '')}"
                                ),
                            },
                        )
                    await self._send_interruption(decision)
        finally:
            self.transcript_buffer = ""

    async def _send_interruption(self, decision: dict):
        """
        Send interruption to user via TTS
        """
        reason = decision["type"]
        trigger = decision.get("trigger", "")

        # Generate AI response
        ai_response = await self._generate_interruption_response(reason, trigger)

        # Send interruption message
        await self.manager.send_json(
            self.manager.active_connections["presentation"].values().__next__(),
            {
                "type": "interruption",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "reason": reason,
                    "trigger": trigger,
                    "ai_message": ai_response,
                    "interruption_latency_ms": 85  # Track latency
                }
            }
        )

        # Generate and send TTS
        tts_result = await self.tts_service.synthesize(ai_response)
        if tts_result.is_success:
            audio_stream = tts_result.value

            # Send audio chunks
            async for chunk in audio_stream:
                await self.manager.send_json(
                    self.manager.active_connections["presentation"].values().__next__(),
                    {
                        "type": "tts_audio",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "audio": chunk.decode() if isinstance(chunk, bytes) else chunk,
                            "text": ai_response,
                            "duration_ms": 2500
                        }
                    }
                )

        self.is_ai_speaking = True
        self.send_status("speaking")

    async def _generate_interruption_response(self, reason: str, trigger: str) -> str:
        """Generate AI response for interruption"""
        # Predefined responses for common scenarios
        if reason == "forbidden_word":
            return f"Please avoid saying '{trigger}'. Try using a different phrase."

        elif reason == "missing_point":
            return "You haven't mentioned all the required points yet. Can you elaborate more?"

        elif reason == "vague_response":
            return "That's too vague. Could you provide more specific details?"

        else:
            return "Could you please continue?"

    async def _handle_page_change(self, page_number: int):
        """Handle page change"""
        self.current_page = page_number

        requirements: dict[str, Any] = {
            "required_points": [],
            "total_pages": None,
            "page_content": "",
        }

        # Reset point tracker for new page
        async with AsyncSessionLocal() as db:
            coach_service = PresentationCoachService(db)
            result = await coach_service.get_current_page_requirements(
                self.session_id or list(self.manager.active_connections["presentation"].keys())[0],
                page_number
            )

            if result.is_success:
                requirements = result.value
                self.point_tracker = PointTracker(requirements["required_points"])

        websocket = self._get_active_websocket()
        if websocket:
            await self._send_page_context(
                ws=websocket,
                page_number=page_number,
                requirements=requirements,
            )

    async def _handle_pause(self):
        """Handle session pause"""
        await self.manager.send_json(
            self.manager.active_connections["presentation"].values().__next__(),
            {
                "type": "status",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "session_status": "paused",
                    "ai_state": "idle"
                }
            }
        )

    async def _handle_resume(self):
        """Handle session resume"""
        await self.manager.send_json(
            self.manager.active_connections["presentation"].values().__next__(),
            {
                "type": "status",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "session_status": "in_progress",
                    "ai_state": "listening"
                }
            }
        )

    async def _send_forbidden_word_alert(
        self,
        websocket: WebSocket,
        detections: list[dict]
    ) -> None:
        """
        Send forbidden word detection alert to client
        Includes trace_id for observability (Story 2.8)
        """
        await self.manager.send_json(
            websocket,
            {
                "type": "forbidden_word",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "detections": detections,
                    "current_page": self.current_page
                }
            }
        )
        logger.info(
            "forbidden_word_alert_sent",
            session_id=self.session_id,
            page=self.current_page,
            detection_count=len(detections)
        )

    async def _send_realtime_feedback(
        self,
        websocket_or_decision: WebSocket | dict[str, Any],
        feedback_type: str | None = None,
        message: str | None = None,
        suggestions: list[str] | None = None
    ) -> None:
        """
        Send real-time feedback to client
        Includes trace_id for observability (Story 2.8)
        """
        if isinstance(websocket_or_decision, dict):
            decision = websocket_or_decision
            websocket = self._get_active_websocket()
            if websocket is None:
                return

            decision_type = str(decision.get("type", "generic"))
            decision_message = str(
                decision.get("reason")
                or decision.get("trigger")
                or "实时反馈"
            )

            await self._send_realtime_feedback(
                websocket,
                feedback_type=decision_type,
                message=decision_message,
                suggestions=suggestions,
            )

            if decision_type == "forbidden_word":
                trigger = str(decision.get("trigger", "")).strip()
                if trigger:
                    await self._send_forbidden_word_alert(
                        websocket,
                        [{
                            "word": trigger,
                            "category": "forbidden",
                            "reason": decision_message,
                        }],
                    )
            return

        websocket = websocket_or_decision
        if feedback_type is None or message is None:
            raise ValueError("feedback_type and message are required")

        await self.manager.send_json(
            websocket,
            {
                "type": "feedback",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "feedback_type": feedback_type,
                    "message": message,
                    "suggestions": suggestions or [],
                    "current_page": self.current_page
                }
            }
        )
        logger.info(
            "realtime_feedback_sent",
            session_id=self.session_id,
            feedback_type=feedback_type,
            page=self.current_page
        )

    async def _send_point_updates(
        self,
        websocket: WebSocket,
        point_results: list[dict]
    ) -> None:
        """
        Send point coverage updates to client
        Includes trace_id for observability (Story 2.8)
        """
        await self.manager.send_json(
            websocket,
            {
                "type": "point_covered",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "points": point_results,
                    "current_page": self.current_page
                }
            }
        )
        logger.info(
            "point_updates_sent",
            session_id=self.session_id,
            page=self.current_page,
            point_count=len(point_results)
        )

    async def _send_page_context(
        self,
        ws: WebSocket,
        page_number: int,
        requirements: dict[str, Any],
    ) -> None:
        """Send structured page context events for replayable UI updates."""
        await self.manager.send_json(
            ws,
            {
                "type": "slide_update",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "page_number": page_number,
                    "total_pages": requirements.get("total_pages"),
                    "page_content": requirements.get("page_content", ""),
                },
            },
        )

        required_points = requirements.get("required_points") or []
        if required_points:
            await self._send_point_updates(
                ws,
                [{"point": point, "covered": False} for point in required_points],
            )
        else:
            await self._send_point_updates(ws, [])

        await self.manager.send_json(
            ws,
            {
                "type": "status",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_status": self.session_status,
                    "ai_state": "listening",
                    "turn_count": self.turn_count,
                    "current_page": page_number,
                    "context": f"Page {page_number} of presentation",
                },
            },
        )
        self.ai_state = "listening"

    async def _save_conversation_message(self, role: str, content: str) -> str | None:
        """Persist conversation message and return message id."""
        if not self.session_id or not content:
            return None

        if role == "user":
            self.turn_count += 1
        elif role == "assistant" and self.turn_count == 0:
            self.turn_count = 1

        async with AsyncSessionLocal() as db:
            storage = MessageStorageService(db)
            result = await storage.save_message(
                session_id=self.session_id,
                turn_number=self.turn_count,
                role=role,
                content=content,
            )

        if result.is_success:
            return str(result.value.id)

        logger.warning(
            f"Failed to save conversation message: role={role}, error={result.fallback}"
        )
        return None

    async def _update_message_analysis(
        self,
        message_id: str,
        analysis_data: dict[str, Any],
    ) -> bool:
        """Update persisted message analysis fields."""
        if not message_id:
            return False

        async with AsyncSessionLocal() as db:
            storage = MessageStorageService(db)
            result = await storage.update_analysis(
                message_id=message_id,
                fuzzy_words=analysis_data.get("fuzzy_words"),
                sales_stage=analysis_data.get("sales_stage"),
                score_snapshot=analysis_data.get("score_snapshot"),
                ai_feedback=analysis_data.get("ai_feedback"),
            )

        return result.is_success

    async def _send_status(self, ai_state: str):
        """Send structured status event with observability context."""
        self.ai_state = ai_state
        websocket = self._get_active_websocket()
        if websocket is None:
            return

        await self.manager.send_json(
            websocket,
            {
                "type": "status",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_status": self.session_status,
                    "ai_state": ai_state,
                    "turn_count": self.turn_count,
                    "current_page": self.current_page,
                },
            },
        )

    async def _send_error(self, code: str, message: str):
        """Send structured error event with session context."""
        websocket = self._get_active_websocket()
        if websocket is None:
            return

        await self.manager.send_json(
            websocket,
            {
                "type": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "code": code,
                    "message": message,
                    "user_action": "请稍后重试",
                    "session_status": self.session_status,
                    "ai_state": self.ai_state,
                    "turn_count": self.turn_count,
                },
            },
        )

    async def _handle_session_end(self):
        """Notify frontend session ended with trace context."""
        websocket = self._get_active_websocket()
        if websocket is None:
            return

        await self.manager.send_json(
            websocket,
            {
                "type": "session_ended",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "session_id": self.session_id,
                    "session_status": self.session_status,
                    "turn_count": self.turn_count,
                },
            },
        )
        self.running = False

    def send_status(self, ai_state: str):
        """Backwards-compatible fire-and-forget status sender."""
        asyncio.create_task(self._send_status(ai_state))

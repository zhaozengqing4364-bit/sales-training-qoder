"""
Presentation WebSocket Handler
Real-time bidirectional voice communication for PPT coaching
Constitution Principle I & II: No error popups, <300ms end-to-end latency
Constitution Principle IV: Fault tolerance and recovery with session state persistence
"""

import asyncio
import base64
import inspect
import json
import uuid
from typing import Any, cast

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from agent.models import Agent, Persona
from agent.services.persona_policy import normalize_persona_policy
from common.audio.asr_service import get_asr_service
from common.audio.tts_service import get_tts_service
from common.auth.service import JWTError, verify_token
from common.conversation.storage import MessageStorageService
from common.db.models import PracticeSession
from common.db.schemas import InterruptionType
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger, set_trace_id
from common.monitoring.trace_context import normalize_trace_id
from common.websocket.base_handler import BaseWebSocketHandler
from common.websocket.session_manager import get_session_manager
from common.websocket.session_state_service import SessionStateSnapshot
from presentation_coach.services.coach_service import PresentationCoachService
from presentation_coach.services.feedback_service import get_feedback_service
from presentation_coach.services.forbidden_matcher import get_forbidden_matcher
from presentation_coach.services.interruption_detector import get_interruption_detector
from presentation_coach.services.point_tracker import PointTracker
from presentation_coach.services.presentation_ai_policy_service import (
    PresentationAIPolicyService,
)
from presentation_coach.services.prompt_role_resolver import (
    PresentationPromptRoleResolver,
    PromptRoleContext,
)
from presentation_coach.websocket.components import PresentationEventEmitter
from prompt_templates.service import PromptTemplateService

logger = get_logger(__name__)


class PresentationWebSocketHandler(BaseWebSocketHandler):
    """
    WebSocket handler for PPT presentation coaching
    Implements bidirectional interruption with <300ms latency target
    """

    BINARY_AUDIO_CHUNK = 0x01
    BINARY_AUDIO_INTERRUPT = 0x02

    def __init__(self):
        super().__init__("presentation")
        self.asr_service = get_asr_service()
        self.tts_service = get_tts_service()
        self.interruption_detector = get_interruption_detector()
        self.forbidden_matcher = get_forbidden_matcher()
        self.feedback_service = get_feedback_service()
        self.prompt_role_resolver = PresentationPromptRoleResolver()
        self.point_tracker = None
        self._effective_ai_policy: dict[str, Any] | None = None

        # State tracking
        self.current_page = 1
        self.is_user_speaking = False
        self.is_ai_speaking = False
        self.transcript_buffer = ""
        self.session_id: str | None = None
        self.turn_count = 0
        self.ai_state = "idle"
        self.session_status = "in_progress"

        # ASR streaming state
        self.asr_queue: asyncio.Queue[bytes | None] | None = None
        self.asr_task: asyncio.Task | None = None
        self.current_transcript = ""
        self.audio_buffer_size = 0
        self.MIN_AUDIO_SIZE = 4800
        self.current_stream_id: str | None = None
        self._tts_task: asyncio.Task | None = None
        self.ASR_QUEUE_MAX_SIZE = 200
        self.ASR_HIGH_WATERMARK = 150
        self.ASR_LOW_WATERMARK = 100
        self._backpressure_active = False
        self._stream_generation = 0
        self._active_tts_generation = 0
        self.event_emitter = PresentationEventEmitter(
            send_json=lambda ws, payload: self.manager.send_json(ws, payload),
            websocket_provider=self._get_active_websocket,
        )

    @staticmethod
    def _utc_now_iso() -> str:
        return PresentationEventEmitter._utc_now_iso()

    @staticmethod
    def _normalize_forbidden_words(words: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for word in words:
            if isinstance(word, dict) and isinstance(word.get("phrase"), str):
                normalized.append(word)
            elif isinstance(word, str) and word.strip():
                normalized.append(
                    {
                        "phrase": word.strip(),
                        "suggested_alternative": "",
                        "is_regex": False,
                        "severity": "warning",
                    }
                )
        return normalized

    async def _initialize_page_feedback(
        self,
        *,
        session_id: str,
        page_number: int,
        requirements: dict[str, Any],
    ) -> None:
        effective_policy = await self._load_effective_ai_policy(session_id=session_id)
        rule_config = (
            effective_policy.get("rule_config")
            if isinstance(effective_policy.get("rule_config"), dict)
            else {}
        )
        required_points = requirements.get("required_points") or []
        forbidden_words = self._normalize_forbidden_words(
            requirements.get("forbidden_words") or []
        )

        init_result = await self.feedback_service.initialize_page(
            session_id=session_id,
            page_number=page_number,
            required_points=required_points,
            forbidden_words=forbidden_words,
            rule_config=rule_config,
        )

        if not init_result.is_success:
            logger.warning(
                "Failed to initialize presentation feedback page",
                session_id=session_id,
                page_number=page_number,
                error=init_result.fallback,
            )

    async def _load_effective_ai_policy(
        self,
        *,
        session_id: str,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if self._effective_ai_policy is not None and not refresh:
            return self._effective_ai_policy

        try:
            async with AsyncSessionLocal() as db:
                policy_service = PresentationAIPolicyService(db)
                try:
                    effective = await policy_service.resolve_effective_policy_for_session(
                        session_id=session_id
                    )
                except ValueError:
                    effective = await policy_service.resolve_effective_policy()
        except Exception:
            logger.warning(
                "Failed to resolve presentation AI policy, using defaults",
                session_id=session_id,
                exc_info=True,
            )
            effective = {}

        self._effective_ai_policy = effective
        logger.info(
            "Loaded effective presentation AI policy",
            session_id=session_id,
            source=effective.get("source"),
        )
        return effective

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
                session_id = self.session_id
                if not session_id:
                    return
                assert session_id is not None
                result = await coach_service.get_current_page_requirements(
                    session_id, self.current_page
                )

                if result.is_success and isinstance(result.value, dict):
                    requirements = result.value
                    # Restore point tracker state
                    if requirements.get("required_points"):
                        if not self.point_tracker:
                            self.point_tracker = PointTracker(
                                requirements["required_points"]
                            )
                    await self._initialize_page_feedback(
                        session_id=session_id,
                        page_number=self.current_page,
                        requirements=requirements,
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

    async def sync_lifecycle_transition(self, transition) -> None:
        """Mirror REST lifecycle writes into the live presentation runtime."""
        await super().sync_lifecycle_transition(transition)

        if transition.action in {"pause", "end"}:
            await self._stop_streaming_asr(process_transcript=False)

        if transition.action in {"start", "resume"} and self.session_status == "in_progress":
            await self._restore_page_context()

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ):
        """Handle presentation websocket with text + binary audio frames."""
        # Set trace_id from token or generate new
        try:
            payload = verify_token(token)
            set_trace_id(
                normalize_trace_id(trace_id)
                or normalize_trace_id(payload.get("trace_id", ""))
                or ""
            )
            self.user_id = payload.get("user_id")
        except (JWTError, RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Token verification failed: {str(e)}")
            set_trace_id(normalize_trace_id(trace_id) or "")

        existing_state = await self.state_service.get_state(session_id)
        is_reconnection = existing_state.is_success and existing_state.value is not None

        self.websocket = websocket
        self.session_id = session_id
        try:
            await self._load_effective_ai_policy(session_id=session_id, refresh=True)
        except Exception:
            logger.warning(
                "Failed to preload presentation AI policy, fallback to defaults",
                session_id=session_id,
                exc_info=True,
            )
            self._effective_ai_policy = None
        await self.manager.connect(websocket, self.scenario, session_id)

        self.message_queue = asyncio.Queue()
        self.running = True

        if is_reconnection:
            logger.info(f"Reconnection detected for session: {session_id}")
            state_snapshot = existing_state.value
            if state_snapshot is not None:
                await self._restore_session_state(state_snapshot)

        processing_task = asyncio.create_task(self._process_messages())

        try:
            while self.running:
                try:
                    raw = await asyncio.wait_for(websocket.receive(), timeout=30.0)

                    if raw.get("type") == "websocket.disconnect":
                        break

                    if raw.get("text") is not None:
                        await self._touch_session_activity()
                        try:
                            data = json.loads(raw["text"])
                            await self.message_queue.put(data)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Invalid JSON message in presentation websocket"
                            )
                    elif raw.get("bytes") is not None:
                        await self._touch_session_activity()
                        await self._handle_binary_frame(raw["bytes"])

                except TimeoutError:
                    await self.manager.send_json(
                        websocket,
                        {
                            "type": "heartbeat",
                            "timestamp": self._utc_now_iso(),
                            "data": {},
                        },
                    )

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally: session={session_id}")
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            await self._stop_streaming_asr(process_transcript=False)
            self.feedback_service.clear_session(self.session_id)
            await self._save_session_state()
            self.running = False
            await self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()

    async def _handle_binary_frame(self, data: bytes):
        """Handle binary audio frames from frontend."""
        if len(data) < 1:
            logger.warning(f"Binary frame too short: {len(data)} bytes")
            return

        frame_type = data[0]
        audio_bytes = data[1:]

        if frame_type == self.BINARY_AUDIO_INTERRUPT:
            await self._handle_interrupt("user_speaking")
            if audio_bytes:
                await self._enqueue_audio_bytes(audio_bytes)
            return

        if frame_type == self.BINARY_AUDIO_CHUNK:
            await self._enqueue_audio_bytes(audio_bytes)
            return

        logger.warning(f"Unknown binary frame type: 0x{frame_type:02x}")

    async def handle_message(self, message: dict):
        """Handle incoming message"""
        msg_type = message.get("type")
        payload = message.get("data", {})
        await self._touch_session_activity()

        try:
            if msg_type == "audio_chunk":
                await self._handle_audio_chunk(payload)

            elif msg_type == "audio_end":
                await self._handle_audio_end()

            elif msg_type == "user_speaking":
                await self._handle_user_speaking(bool(payload.get("speaking", False)))

            elif msg_type == "interrupt":
                reason = str(payload.get("reason") or "manual")
                await self._handle_interrupt(reason)

            elif msg_type == "control":
                action = str(payload.get("action") or "")
                await self._handle_control(action)

            elif msg_type == "page_change":
                page_payload = payload
                page_number = page_payload.get("page_number", page_payload.get("page"))
                if isinstance(page_number, int):
                    await self._handle_page_change(page_number)
                else:
                    logger.warning(f"Invalid page_change payload: {page_payload}")

            elif msg_type == "pause":
                await self._handle_pause()

            elif msg_type == "resume":
                await self._handle_resume()

            elif msg_type == "heartbeat_ack":
                return

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error handling message {msg_type}: {str(e)}")

    async def _handle_audio_chunk(self, data: dict):
        """
        Handle audio chunk from user
        Stream through ASR and check for interruption triggers
        """
        interrupt = bool(data.get("interrupt", False))
        if interrupt:
            logger.info("Received interrupt flag in presentation audio chunk")
            await self._handle_interrupt("user_speaking")
        elif self.is_ai_speaking:
            logger.info("User interrupted AI")
            await self._handle_interrupt("user_speaking")

        # Process audio through ASR
        audio_data = data.get("audio")
        if audio_data:
            try:
                audio_bytes = base64.b64decode(audio_data)
                await self._enqueue_audio_bytes(audio_bytes)
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning(f"Failed to decode presentation audio chunk: {exc}")

    async def _enqueue_audio_bytes(self, audio_bytes: bytes):
        """Enqueue audio bytes into ASR pipeline."""
        if not audio_bytes:
            return

        if not self.asr_queue:
            await self._start_streaming_asr()

        if self.asr_queue:
            self.audio_buffer_size += len(audio_bytes)
            queue_size = self.asr_queue.qsize()
            if queue_size >= self.ASR_HIGH_WATERMARK and not self._backpressure_active:
                self._backpressure_active = True
                await self._send_backpressure("slow_down", queue_size)
            elif (
                queue_size <= self.ASR_LOW_WATERMARK
                and self._backpressure_active
            ):
                self._backpressure_active = False
                await self._send_backpressure("resume", queue_size)

            if queue_size >= self.ASR_QUEUE_MAX_SIZE:
                logger.warning(
                    "Presentation ASR queue full, dropping audio chunk",
                    session_id=self.session_id,
                    queue_size=queue_size,
                )
                return

            try:
                self.asr_queue.put_nowait(audio_bytes)
            except asyncio.QueueFull:
                logger.warning(
                    "Presentation ASR queue full on put_nowait, dropping chunk",
                    session_id=self.session_id,
                    queue_size=self.asr_queue.qsize(),
                )

    async def _start_streaming_asr(self):
        """Start streaming ASR task if not running."""
        if self.asr_task and not self.asr_task.done() and self.asr_queue is not None:
            return

        self.current_transcript = ""
        self.transcript_buffer = ""
        self.audio_buffer_size = 0
        self.asr_queue = asyncio.Queue(maxsize=self.ASR_QUEUE_MAX_SIZE)
        self.asr_task = asyncio.create_task(self._run_streaming_asr())
        self.is_user_speaking = True
        await self._send_status("listening")

    async def _stop_streaming_asr(self, *, process_transcript: bool = True):
        """Stop ASR stream and optionally process final transcript."""
        if self.asr_queue is None and (self.asr_task is None or self.asr_task.done()):
            return

        self.is_user_speaking = False

        if self.asr_queue is not None:
            await self.asr_queue.put(None)

        if self.asr_task and not self.asr_task.done():
            try:
                await asyncio.wait_for(self.asr_task, timeout=5.0)
            except TimeoutError:
                self.asr_task.cancel()
            except (RuntimeError, ValueError, OSError) as exc:
                logger.warning(f"Presentation ASR task finished with error: {exc}")

        final_transcript = (self.current_transcript or self.transcript_buffer).strip()
        self.current_transcript = ""
        self.asr_task = None
        self.asr_queue = None
        self.audio_buffer_size = 0
        if self._backpressure_active:
            self._backpressure_active = False
            await self._send_backpressure("resume", 0)

        if not process_transcript:
            self.transcript_buffer = ""
            return

        if not final_transcript or len(final_transcript) == 0:
            await self._send_status("listening")
            return

        self.transcript_buffer = final_transcript
        await self._check_and_interrupt()

    async def _run_streaming_asr(self):
        """Consume queued audio and stream ASR transcript updates."""

        async def audio_generator():
            while True:
                if self.asr_queue is None:
                    break
                try:
                    chunk = await asyncio.wait_for(self.asr_queue.get(), timeout=30.0)
                except TimeoutError:
                    logger.warning(
                        "Presentation ASR queue timeout",
                        session_id=self.session_id,
                    )
                    break
                if chunk is None:
                    break
                yield chunk

        try:
            async for result in self.asr_service.stream_transcribe(audio_generator()):
                if result.is_success and result.value:
                    text = str(result.value).strip()
                    if not text:
                        continue
                    self.current_transcript = text
                    self.transcript_buffer = text
                    await self._send_transcript(text=text, is_final=False)

            if self.current_transcript.strip():
                await self._send_transcript(
                    text=self.current_transcript.strip(),
                    is_final=True,
                )
        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error(f"Presentation streaming ASR failed: {exc}", exc_info=True)

    async def _handle_audio_end(self):
        """Handle end-of-utterance signal from frontend."""
        # Do not clear transcript buffers before ASR finalization.
        # Short utterances can still contain valid recognized text.
        await self._stop_streaming_asr(process_transcript=True)

    async def _handle_user_speaking(self, is_speaking: bool):
        """
        Handle user speaking state change
        When user stops speaking, check if interruption is needed
        """
        self.is_user_speaking = is_speaking

        if is_speaking:
            await self._start_streaming_asr()
            return

        # User stopped speaking - finalize current ASR segment
        await self._handle_audio_end()

    async def _send_transcript(self, text: str, is_final: bool):
        await self.event_emitter.send_transcript(text=text, is_final=is_final)

    async def _check_and_interrupt(self):
        """
        Check if interruption is needed based on current transcript
        Constitution: <100ms detection, <300ms end-to-end latency
        """
        if not self.transcript_buffer:
            await self._send_status("listening")
            return

        session_id = self.session_id
        if not session_id:
            connections = self.manager.active_connections.get("presentation", {})
            if connections:
                session_id = next(iter(connections.keys()))
        if not session_id:
            self.transcript_buffer = ""
            return

        transcript = self.transcript_buffer
        websocket = self._get_active_websocket()
        user_message_id = await self._save_conversation_message(
            role="user",
            content=transcript,
        )

        decision: dict[str, Any] | None = None

        try:
            async with AsyncSessionLocal() as db:
                coach_service = PresentationCoachService(db)
                result = await coach_service.get_current_page_requirements(
                    session_id, self.current_page
                )

                if not result.is_success:
                    return

                if not isinstance(result.value, dict):
                    return
                requirements = result.value
                await self._initialize_page_feedback(
                    session_id=session_id,
                    page_number=self.current_page,
                    requirements=requirements,
                )

                feedback_result = await self.feedback_service.check_transcript(
                    session_id=session_id,
                    transcript=transcript,
                )

                if feedback_result.is_success and feedback_result.value is not None:
                    feedback = feedback_result.value

                    if websocket is not None:
                        point_results = [
                            {
                                "point_id": point.point_id,
                                "is_covered": point.is_covered,
                                "content": point.point_content,
                            }
                            for point in feedback.point_results
                        ]
                        await self._send_point_updates(websocket, point_results)

                        if feedback.forbidden_matches:
                            detections = [
                                {
                                    "word": match.word,
                                    "suggestion": match.suggestion,
                                }
                                for match in feedback.forbidden_matches
                            ]
                            await self._send_forbidden_word_alert(websocket, detections)

                    if feedback.should_interrupt and feedback.interruption_reason:
                        decision = {
                            "type": feedback.interruption_reason,
                            "trigger": transcript,
                            "reason": feedback.interruption_message,
                        }

                context = {
                    "required_points": requirements.get("required_points", []),
                    "forbidden_words": requirements.get("forbidden_words", []),
                    "session_id": session_id,
                }

                effective_policy = await self._load_effective_ai_policy(
                    session_id=session_id
                )
                fallback_config = (
                    effective_policy.get("fallback_config")
                    if isinstance(effective_policy.get("fallback_config"), dict)
                    else {}
                )
                enable_detector_fallback = bool(
                    fallback_config.get("enable_interruption_detector_fallback", True)
                )

                if decision is None and enable_detector_fallback:
                    interrupt_decision = (
                        await self.interruption_detector.should_interrupt(
                            transcript,
                            context,
                        )
                    )
                    if interrupt_decision.is_success and interrupt_decision.value:
                        decision = interrupt_decision.value

                if decision:
                    if user_message_id:
                        await self._update_message_analysis(
                            message_id=user_message_id,
                            analysis_data={
                                "ai_feedback": (
                                    f"{decision.get('type', 'unknown')}:"
                                    f"{decision.get('trigger', '')}"
                                ),
                                "transcript_metadata": {
                                    "page_number": self.current_page,
                                },
                            },
                        )
                    await self._send_realtime_feedback(decision)
                    await self._send_interruption(decision)
        finally:
            self.transcript_buffer = ""
            if not decision:
                if websocket is not None and transcript.strip():
                    await self._send_chat_response(
                        websocket,
                        message="已收到你的讲解，可继续当前页或切换下一页。",
                    )
                await self._send_status("listening")

    async def _send_interruption(self, decision: dict):
        """
        Send interruption to user via TTS
        """
        websocket = self._get_active_websocket()
        if websocket is None:
            return

        reason = decision["type"]
        trigger = decision.get("trigger", "")

        # Generate AI response
        ai_response = await self._generate_interruption_response(reason, trigger)
        stream_id = f"presentation-{uuid.uuid4().hex}"
        self._stream_generation += 1
        generation = self._stream_generation
        self._active_tts_generation = generation
        self.current_stream_id = stream_id

        # Send interruption message
        await self.event_emitter.send_interruption(
            reason=reason,
            trigger=trigger,
            ai_message=ai_response,
            stream_id=stream_id,
            interruption_latency_ms=85,
            websocket=websocket,
        )

        # Generate and send TTS
        tts_result = await self.tts_service.synthesize(ai_response)
        if tts_result.is_success and tts_result.value is not None:
            audio_stream = tts_result.value

            async def _stream_tts() -> None:
                async for chunk in audio_stream:
                    if generation != self._active_tts_generation:
                        logger.info(
                            "Skip stale presentation TTS chunk",
                            session_id=self.session_id,
                            stream_id=stream_id,
                        )
                        break
                    if isinstance(chunk, bytes):
                        audio_payload = base64.b64encode(chunk).decode("utf-8")
                    elif isinstance(chunk, str):
                        audio_payload = chunk
                    else:
                        continue

                    await self.event_emitter.send_tts_audio(
                        audio=audio_payload,
                        text=ai_response,
                        duration_ms=2500,
                        stream_id=stream_id,
                        websocket=websocket,
                    )

            self._tts_task = asyncio.create_task(_stream_tts())
            try:
                await self._tts_task
            except asyncio.CancelledError:
                logger.info("Presentation TTS stream cancelled", stream_id=stream_id)
            finally:
                self._tts_task = None

        if generation != self._active_tts_generation:
            logger.info(
                "Skip stale presentation interruption state update",
                session_id=self.session_id,
                stream_id=stream_id,
            )
            return

        self.is_ai_speaking = True
        await self._send_status("speaking")

        if self.session_id:
            interruption_type = InterruptionType.VAGUE_RESPONSE
            try:
                interruption_type = InterruptionType(reason)
            except ValueError:
                logger.warning(
                    "Unknown interruption type fallback to vague_response",
                    reason=reason,
                )

            async with AsyncSessionLocal() as db:
                coach_service = PresentationCoachService(db)
                await coach_service.record_interruption(
                    session_id=self.session_id,
                    interruption_type=interruption_type,
                    trigger_content=trigger,
                    ai_response=ai_response,
                    detection_latency_ms=85,
                )

    async def _generate_interruption_response(self, reason: str, trigger: str) -> str:
        template_text: str | None = None
        effective_policy = (
            await self._load_effective_ai_policy(session_id=self.session_id)
            if self.session_id
            else {}
        )
        prompt_config = (
            effective_policy.get("prompt_config")
            if isinstance(effective_policy.get("prompt_config"), dict)
            else {}
        )
        fallback_config = (
            effective_policy.get("fallback_config")
            if isinstance(effective_policy.get("fallback_config"), dict)
            else {}
        )
        enable_prompt_first = bool(prompt_config.get("enable_prompt_first", True))
        explicit_template_id = str(
            prompt_config.get("interruption_template_id") or ""
        ).strip()
        allow_scenario_prompt_fallback = bool(
            fallback_config.get("allow_scenario_prompt_fallback", True)
        )
        context = PromptRoleContext(
            reason=reason,
            trigger=trigger,
            transcript=self.transcript_buffer,
            page_number=self.current_page,
            required_points=[],
            forbidden_words=[],
        )

        if self.session_id:
            try:
                async with AsyncSessionLocal() as db:
                    coach_service = PresentationCoachService(db)
                    requirements_result = (
                        await coach_service.get_current_page_requirements(
                            self.session_id,
                            self.current_page,
                        )
                    )
                    if requirements_result.is_success and isinstance(
                        requirements_result.value, dict
                    ):
                        requirements = requirements_result.value
                        context.required_points = list(
                            requirements.get("required_points") or []
                        )
                        context.forbidden_words = list(
                            requirements.get("forbidden_words") or []
                        )

                    session_identity_result = await db.execute(
                        select(
                            PracticeSession.agent_id,
                            PracticeSession.persona_id,
                            PracticeSession.scenario_id,
                            PracticeSession.voice_policy_snapshot,
                        ).where(PracticeSession.session_id == self.session_id)
                    )
                    session_identity = session_identity_result.first()
                    if session_identity:
                        agent_id = cast(str | None, session_identity[0])
                        session_snapshot = cast(dict[str, Any] | None, session_identity[3])
                        if isinstance(session_snapshot, dict):
                            snapshot_instructions = str(
                                session_snapshot.get("instructions") or ""
                            ).strip()
                            if snapshot_instructions:
                                context.agent_system_prompt = snapshot_instructions
                        if agent_id:
                            agent_result = await db.execute(
                                select(Agent.name).where(Agent.id == agent_id)
                            )
                            agent = agent_result.first()
                            if agent:
                                context.agent_name = cast(str | None, agent[0])

                        persona_id = cast(str | None, session_identity[1])
                        if persona_id:
                            persona_result = await db.execute(
                                select(
                                    Persona.name,
                                    Persona.persona_policy,
                                    Persona.system_prompt,
                                    Persona.knowledge_base_ids,
                                    Persona.traits,
                                ).where(Persona.id == persona_id)
                            )
                            persona = persona_result.first()
                            if persona:
                                context.persona_name = cast(str | None, persona[0])
                                resolved_persona_policy = normalize_persona_policy(
                                    cast(dict[str, Any] | None, persona[1]),
                                    fallback_system_prompt=cast(str | None, persona[2]),
                                    fallback_kb_ids=cast(list[str] | None, persona[3]),
                                )
                                context.persona_system_prompt = cast(
                                    str | None,
                                    resolved_persona_policy.get("system_prompt"),
                                )
                                context.persona_traits = (
                                    dict(persona[4])
                                    if isinstance(persona[4], dict)
                                    else {}
                                )

                        prompt_service = PromptTemplateService(db)
                        if enable_prompt_first and explicit_template_id:
                            try:
                                template = await prompt_service.get_template(
                                    uuid.UUID(explicit_template_id)
                                )
                                if template and template.template and template.is_active:
                                    template_text = template.template
                            except ValueError:
                                logger.warning(
                                    "Invalid explicit presentation interruption template id",
                                    session_id=self.session_id,
                                    template_id=explicit_template_id,
                                )

                        if not template_text and allow_scenario_prompt_fallback:
                            template = await prompt_service.get_template_for_scenario(
                                prompt_type="interruption",
                                scenario_type="presentation",
                                scenario_id=(
                                    str(session_identity[2])
                                    if session_identity[2]
                                    else None
                                ),
                            )
                            if template and template.template:
                                template_text = template.template
            except (RuntimeError, ValueError, OSError):
                logger.error(
                    "Failed to resolve role-aware interruption prompt",
                    session_id=self.session_id,
                    reason=reason,
                    exc_info=True,
                )

        return self.prompt_role_resolver.resolve_interruption_message(
            context=context,
            template_text=template_text,
        )

    async def _handle_page_change(self, page_number: int):
        """Handle page change"""
        self.current_page = page_number

        requirements: dict[str, Any] = {
            "required_points": [],
            "total_pages": None,
            "page_content": "",
        }

        # Reset point tracker for new page
        target_session_id = self.session_id
        if not target_session_id:
            active_session_ids = list(
                self.manager.active_connections.get("presentation", {}).keys()
            )
            if active_session_ids:
                target_session_id = active_session_ids[0]

        if not target_session_id:
            logger.warning("Skip page change requirements load: missing session id")
            return
        assert target_session_id is not None

        async with AsyncSessionLocal() as db:
            coach_service = PresentationCoachService(db)
            result = await coach_service.get_current_page_requirements(
                target_session_id, page_number
            )

            if result.is_success and isinstance(result.value, dict):
                requirements = result.value
                self.point_tracker = PointTracker(requirements["required_points"])
                await self._initialize_page_feedback(
                    session_id=target_session_id,
                    page_number=page_number,
                    requirements=requirements,
                )

        websocket = self._get_active_websocket()
        if websocket:
            await self._send_page_context(
                ws=websocket,
                page_number=page_number,
                requirements=requirements,
            )

    async def _handle_pause(self):
        """Handle session pause"""
        self.session_status = "paused"
        await self._stop_streaming_asr(process_transcript=False)
        await self._send_status("idle")

    async def _handle_resume(self):
        """Handle session resume"""
        self.session_status = "in_progress"
        await self._send_status("listening")

    async def _handle_interrupt(self, reason: str = "manual"):
        self.is_ai_speaking = False
        self._stream_generation += 1
        self._active_tts_generation = self._stream_generation
        stream_id = self.current_stream_id
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass
            finally:
                self._tts_task = None

        websocket = self._get_active_websocket()

        if websocket is not None:
            await self.event_emitter.send_interrupted(
                reason=reason,
                session_status=self.session_status,
                turn_count=self.turn_count,
                stream_id=stream_id,
                websocket=websocket,
            )

        self.current_stream_id = None
        await self._send_status(
            "listening" if self.session_status == "in_progress" else "idle"
        )

    async def _touch_session_activity(self) -> None:
        """Update session activity timestamp for timeout management."""
        if self.session_id:
            await get_session_manager().update_activity(self.session_id)

    async def _send_backpressure(self, action: str, queue_size: int) -> None:
        """Send ASR backpressure signal to frontend."""
        await self.event_emitter.send_backpressure(
            action=action,
            queue_size=queue_size,
            high_watermark=self.ASR_HIGH_WATERMARK,
            low_watermark=self.ASR_LOW_WATERMARK,
        )

    async def _handle_control(self, action: str):
        normalized_action = action.strip().lower()

        if normalized_action == "start":
            if not self.session_id:
                await self._send_error("[SESSION_NOT_FOUND]", "会话不存在")
                return

            async with AsyncSessionLocal() as db:
                coach_service = PresentationCoachService(db)
                result = await coach_service.start_session(self.session_id)
                requirements: dict[str, Any] | None = None
                if result.is_success:
                    get_requirements = getattr(
                        coach_service,
                        "get_current_page_requirements",
                        None,
                    )
                    if callable(get_requirements):
                        maybe_requirements = get_requirements(
                            self.session_id,
                            self.current_page,
                        )
                        if inspect.isawaitable(maybe_requirements):
                            requirements_result = await maybe_requirements
                            if requirements_result.is_success and isinstance(
                                requirements_result.value,
                                dict,
                            ):
                                requirements = requirements_result.value

            if not result.is_success:
                await self._send_error("[START_FAILED]", "会话启动失败")
                return

            self.session_status = "in_progress"

            websocket = self._get_active_websocket()
            if websocket is not None and requirements is not None:
                await self._initialize_page_feedback(
                    session_id=self.session_id,
                    page_number=self.current_page,
                    requirements=requirements,
                )
                await self._send_page_context(
                    ws=websocket,
                    page_number=self.current_page,
                    requirements=requirements,
                )

            await self._send_status("listening")
            return

        if normalized_action == "pause":
            await self._handle_pause()
            return

        if normalized_action == "resume":
            await self._handle_resume()
            return

        if normalized_action == "end":
            if not self.session_id:
                await self._send_error("[SESSION_NOT_FOUND]", "会话不存在")
                return

            async with AsyncSessionLocal() as db:
                coach_service = PresentationCoachService(db)
                result = await coach_service.end_session(self.session_id)

            if not result.is_success:
                await self._send_error("[END_FAILED]", "会话结束失败")
                return

            self.session_status = "completed"
            await self._handle_session_end()
            return

        logger.warning(f"Unknown control action: {action}")

    async def _send_forbidden_word_alert(
        self, websocket: WebSocket, detections: list[dict]
    ) -> None:
        """
        Send forbidden word detection alert to client
        Includes trace_id for observability (Story 2.8)
        """
        await self.event_emitter.send_forbidden_word_alert(
            detections=detections,
            current_page=self.current_page,
            websocket=websocket,
        )
        logger.info(
            "forbidden_word_alert_sent",
            session_id=self.session_id,
            page=self.current_page,
            detection_count=len(detections),
        )

    async def _send_realtime_feedback(
        self,
        websocket_or_decision: WebSocket | dict[str, Any],
        feedback_type: str | None = None,
        message: str | None = None,
        suggestions: list[str] | None = None,
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
                decision.get("reason") or decision.get("trigger") or "实时反馈"
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
                        [
                            {
                                "word": trigger,
                                "suggestion": decision_message,
                            }
                        ],
                    )
            return

        websocket = websocket_or_decision
        if feedback_type is None or message is None:
            raise ValueError("feedback_type and message are required")

        await self.event_emitter.send_feedback(
            feedback_type=feedback_type,
            message=message,
            suggestions=suggestions or [],
            current_page=self.current_page,
            websocket=websocket,
        )
        logger.info(
            "realtime_feedback_sent",
            session_id=self.session_id,
            feedback_type=feedback_type,
            page=self.current_page,
        )

    async def _send_chat_response(self, websocket: WebSocket, message: str) -> None:
        """Send a chat-visible AI response message to client."""
        await self.event_emitter.send_chat_response(
            message=message,
            current_page=self.current_page,
            websocket=websocket,
        )
        logger.info(
            "chat_response_sent",
            session_id=self.session_id,
            page=self.current_page,
        )

    async def _send_point_updates(
        self,
        websocket: WebSocket,
        point_results: list[dict],
        *,
        replace_existing: bool = False,
    ) -> None:
        """
        Send point coverage updates to client
        Includes trace_id for observability (Story 2.8)
        """
        await self.event_emitter.send_point_updates(
            current_page=self.current_page,
            point_results=point_results,
            replace_existing=replace_existing,
            websocket=websocket,
        )
        logger.info(
            "point_updates_sent",
            session_id=self.session_id,
            page=self.current_page,
            replace_existing=replace_existing,
            point_count=len(point_results),
        )

    async def _send_page_context(
        self,
        ws: WebSocket,
        page_number: int,
        requirements: dict[str, Any],
    ) -> None:
        """Send structured page context events for replayable UI updates."""
        await self.event_emitter.send_page_context(
            page_number=page_number,
            requirements=requirements,
            session_status=self.session_status,
            turn_count=self.turn_count,
            session_id=self.session_id,
            websocket=ws,
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

        if (
            result.is_success
            and result.value is not None
            and hasattr(result.value, "id")
        ):
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
                transcript_metadata=analysis_data.get("transcript_metadata"),
                sales_stage=analysis_data.get("sales_stage"),
                score_snapshot=analysis_data.get("score_snapshot"),
                ai_feedback=analysis_data.get("ai_feedback"),
            )

        return result.is_success

    async def _send_status(self, ai_state: str):
        """Send structured status event with observability context."""
        self.ai_state = ai_state
        await self.event_emitter.send_status(
            ai_state=ai_state,
            session_status=self.session_status,
            turn_count=self.turn_count,
            current_page=self.current_page,
        )

    async def _send_error(self, code: str, message: str):
        """Send structured error event with session context."""
        await self.event_emitter.send_error(
            code=code,
            message=message,
            session_status=self.session_status,
            ai_state=self.ai_state,
            turn_count=self.turn_count,
        )

    async def _handle_session_end(self):
        """Notify frontend session ended with trace context."""
        await self.event_emitter.send_session_ended(
            session_id=self.session_id,
            session_status=self.session_status,
            turn_count=self.turn_count,
        )
        self.running = False

    def send_status(self, ai_state: str):
        """Backwards-compatible fire-and-forget status sender."""
        asyncio.create_task(self._send_status(ai_state))

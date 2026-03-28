"""
Enhanced Sales Bot WebSocket Handler

v1-8 Refactor: Uses composition pattern with extracted components:
- TTSComponent: TTS response generation (single-shot + streaming)
- CapabilityProcessor: Capability module execution & real-time feedback
- MessagePersistence: Database message storage

Extends BaseSalesHandler (common ASR/TTS/connection pipeline) and adds:
- Dynamic Agent/Persona configuration
- Capability module integration (fuzzy detection, sales stage, scoring)
- Message storage for replay
- Real-time feedback messages
- Interrupt handling (LLM/TTS task cancellation)
- Backpressure control with latency tracking

References:
- Requirements: R11 (WebSocket Enhancement)
- Design: Section 20 (EnhancedSalesHandler)
- API Contract: docs/api-contract/websocket.md
"""

import asyncio
import base64
import contextlib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.capabilities.runner import CapabilityRunner
from agent.context import AgentContext
from agent.services.agent_service import AgentService
from agent.services.persona_service import PersonaService
from common.ai.config_manager import get_config_manager
from common.ai.llm_service import create_llm_service, get_llm_service
from common.ai.models import ModelType
from common.audio.asr_service import get_asr_service
from common.db.models import PracticeSession
from common.audio.tts_factory import get_tts_service_with_fallback
from common.db.session import AsyncSessionLocal
from common.effectiveness import coerce_live_session_conclusion_summary
from common.knowledge.kb_lock_guard import evaluate_kb_lock_decision
from common.knowledge.service import KnowledgeService
from common.monitoring.latency_tracker import LatencyTracker, get_latency_tracker
from common.monitoring.logger import get_logger
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.services.voice_instruction_compiler import VoiceInstructionCompiler
from sales_bot.websocket.base_sales_handler import BaseSalesHandler
from sales_bot.websocket.components import (
    TTSComponent,
    CapabilityProcessor,
    MessagePersistence,
)

logger = get_logger(__name__)


class EnhancedSalesHandler(BaseSalesHandler):
    """
    Enhanced WebSocket handler for sales practice with Agent Platform integration.

    Uses composition pattern to integrate:
    - TTSComponent: TTS audio generation and delivery
    - CapabilityProcessor: Capability module execution and feedback
    - MessagePersistence: Conversation message storage
    - CapabilityRunner: Executes capability modules
    - AgentContext: Provides runtime context for capabilities
    """

    def __init__(self):
        super().__init__("sales")
        # Session identifiers
        self.agent_id: str | None = None
        self.persona_id: str | None = None
        self.user_id: str | None = None

        # Composed components (initialized in initialize())
        self.capability_runner: CapabilityRunner | None = None
        self.context: AgentContext | None = None
        self.tts_component: TTSComponent | None = None
        self.capability_processor: CapabilityProcessor | None = None
        self.persistence: MessagePersistence | None = None

        # Configuration
        self.agent_config: dict[str, Any] = {}
        self.persona_config: dict[str, Any] = {}

        # Backpressure control (Requirements: Voice Practice Optimization P0-2)
        self.ASR_QUEUE_MAX_SIZE = 200
        self.ASR_HIGH_WATERMARK = 150
        self.ASR_LOW_WATERMARK = 100
        self._backpressure_active = False

        # Task references for interrupt cancellation (Requirements 3.3, 3.4)
        self._llm_task: asyncio.Task | None = None
        self._tts_task: asyncio.Task | None = None
        self._greeting_task: asyncio.Task | None = None
        self._response_task: asyncio.Task | None = None
        self._is_interrupted: bool = False
        self._db_lock = asyncio.Lock()
        self._llm_override_service: object | None = None
        self._llm_override_config_id: str | None = None
        self._voice_policy_snapshot: dict[str, Any] = {}
        self._base_instructions: str = ""
        self._coach_health: str = "healthy"
        self._coach_health_reason: str | None = None
        self._latest_live_session_summary: dict[str, Any] | None = None

        # Internal state for current turn
        self._current_turn_initialized: bool = False

        # 使用带降级的TTS服务
        self.tts_service = get_tts_service_with_fallback()

    # ========== Initialization ==========

    async def initialize(
        self,
        session_id: str,
        agent_id: str,
        persona_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> bool:
        """
        Initialize handler with Agent/Persona configuration.

        Loads Agent and Persona from database, initializes capability runner,
        TTS component, capability processor, and message persistence.

        Returns:
            True if initialization successful, False otherwise.
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self.persona_id = persona_id
        self.user_id = user_id

        session_result = await db.execute(
            select(PracticeSession.voice_policy_snapshot).where(
                PracticeSession.session_id == session_id
            )
        )
        session_snapshot = session_result.scalar_one_or_none()
        self._voice_policy_snapshot = (
            session_snapshot if isinstance(session_snapshot, dict) else {}
        )

        # Load Agent configuration
        agent_service = AgentService(db)
        agent_result = await agent_service.get_by_id(agent_id, admin=True)
        if not agent_result.is_success:
            logger.error(f"Failed to load Agent: {agent_result.fallback}")
            return False

        agent = agent_result.value
        self.agent_config = {
            "id": agent.id,
            "name": agent.name,
            "system_prompt": agent.system_prompt,
            "welcome_message": agent.welcome_message,
            "capabilities_config": agent.capabilities_config or {},
            "default_knowledge_base_ids": agent.default_knowledge_base_ids or [],
        }

        # Load Persona configuration
        persona_service = PersonaService(db)
        persona_result = await persona_service.get_by_id(persona_id)
        if not persona_result.is_success:
            logger.error(f"Failed to load Persona: {persona_result.fallback}")
            return False

        persona = persona_result.value
        snapshot_persona_policy = (
            self._voice_policy_snapshot.get("persona_policy")
            if isinstance(self._voice_policy_snapshot.get("persona_policy"), dict)
            else {}
        )
        snapshot_system_prompt = str(
            snapshot_persona_policy.get("system_prompt") or ""
        ).strip()
        snapshot_kb_ids = self._snapshot_knowledge_base_ids()
        self.persona_config = {
            "id": persona.id,
            "name": persona.name,
            "system_prompt": snapshot_system_prompt or persona.system_prompt,
            "traits": persona.traits or {},
            "behavior_config": persona.behavior_config or {},
            "scoring_weights": persona.scoring_weights,
            "knowledge_base_ids": snapshot_kb_ids or (persona.knowledge_base_ids or []),
            "tts_config": persona.tts_config or {},
        }
        self._base_instructions = self._resolve_base_instructions()

        # Initialize AgentContext
        self.context = AgentContext(
            session_id=session_id,
            agent_id=agent_id,
            persona_id=persona_id,
            user_id=user_id,
            state={},
            conversation_history=[],
            agent_config=self.agent_config,
            persona_config=self.persona_config,
            start_time=datetime.now(timezone.utc),
        )

        # Initialize CapabilityRunner
        capabilities_config = self.agent_config.setdefault("capabilities_config", {})
        merged_kb_ids = self._snapshot_knowledge_base_ids()
        if not merged_kb_ids:
            merged_kb_ids = list(dict.fromkeys([
                *self.agent_config.get("default_knowledge_base_ids", []),
                *self.persona_config.get("knowledge_base_ids", []),
            ]))
        if merged_kb_ids:
            knowledge_cfg = capabilities_config.get("knowledge_retrieval", {})
            if not isinstance(knowledge_cfg, dict):
                knowledge_cfg = {}
            if not bool(knowledge_cfg.get("enabled", False)):
                capabilities_config["knowledge_retrieval"] = {
                    **knowledge_cfg,
                    "enabled": True,
                }
                logger.info(
                    "Auto-enabled knowledge_retrieval for bound knowledge bases",
                    session_id=session_id,
                    knowledge_base_count=len(merged_kb_ids),
                )

        self.capability_runner = CapabilityRunner(
            self.agent_config,
            self.persona_config.get("behavior_config", {}),
        )

        # Inject KnowledgeService into knowledge_retrieval capability
        knowledge_cap = self.capability_runner.get_capability("knowledge_retrieval")
        if knowledge_cap:
            knowledge_service = KnowledgeService(db)
            knowledge_cap.set_knowledge_service(knowledge_service)
            logger.info("Injected KnowledgeService into knowledge_retrieval capability")

        # v1-8: Initialize composed components
        self.tts_component = TTSComponent(self.tts_service, self.persona_config)
        self.capability_processor = CapabilityProcessor(self.capability_runner)
        self.persistence = MessagePersistence(session_id)

        # Call capability session start
        await self.capability_runner.on_session_start(self.context)

        logger.info(
            "EnhancedSalesHandler initialized",
            session_id=session_id,
            agent_id=agent_id,
            persona_id=persona_id,
            capabilities=self.capability_runner.list_capabilities(),
        )

        return True

    def _snapshot_knowledge_base_ids(self) -> list[str]:
        raw_ids = self._voice_policy_snapshot.get("knowledge_base_ids")
        if not isinstance(raw_ids, list):
            return []
        deduped: list[str] = []
        seen: set[str] = set()
        for item in raw_ids:
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _resolve_base_instructions(self) -> str:
        snapshot_instructions = str(
            self._voice_policy_snapshot.get("instructions") or ""
        ).strip()
        if snapshot_instructions:
            return snapshot_instructions

        legacy_prompt = str(self.persona_config.get("system_prompt") or "").strip()
        if legacy_prompt:
            return legacy_prompt
        return str(self.agent_config.get("system_prompt") or "你是一个销售教练。").strip()

    @staticmethod
    def _coach_health_message(status: str) -> str:
        if status == "degraded":
            return "实时辅导暂不可用，训练仍可继续。"
        if status == "resumed":
            return "实时辅导已恢复，后续建议会继续更新。"
        return "实时辅导正常。"

    def _sync_coach_health_from_processor(self) -> None:
        if self.capability_processor is None:
            return
        self._coach_health = str(
            getattr(self.capability_processor, "coach_health", "healthy") or "healthy"
        )
        reason = getattr(self.capability_processor, "_coach_health_reason", None)
        self._coach_health_reason = (
            str(reason).strip() if isinstance(reason, str) and reason.strip() else None
        )
        self._latest_live_session_summary = coerce_live_session_conclusion_summary(
            getattr(self.capability_processor, "live_session_summary", None)
        )

    def _coach_health_payload(self) -> dict[str, Any]:
        return {
            "status": self._coach_health,
            "reason": self._coach_health_reason,
            "message": self._coach_health_message(self._coach_health),
        }

    def get_runtime_diagnostics(self) -> dict[str, Any]:
        self._sync_coach_health_from_processor()
        live_session_summary = coerce_live_session_conclusion_summary(
            self._latest_live_session_summary
        )
        claim_truth = (
            live_session_summary.get("claim_truth")
            if isinstance(live_session_summary, dict)
            and isinstance(live_session_summary.get("claim_truth"), dict)
            else None
        )
        return {
            "live_session_summary": live_session_summary,
            "claim_truth": claim_truth,
            "coach_health": self._coach_health_payload(),
        }

    def _create_state_snapshot(self) -> SessionStateSnapshot:
        self._sync_coach_health_from_processor()
        runtime_state: dict[str, Any] = {}
        coach_health = self._coach_health_payload()
        if coach_health["status"] != "healthy" or coach_health["reason"] is not None:
            runtime_state["coach_health"] = coach_health
        live_session_summary = coerce_live_session_conclusion_summary(
            self._latest_live_session_summary
        )
        if live_session_summary is not None:
            runtime_state["live_session_summary"] = live_session_summary
        return SessionStateSnapshot(
            session_id=self.session_id or "",
            scenario=self.scenario,
            turn_count=self.turn_count,
            session_status=self.session_status,
            ai_state=self.ai_state,
            runtime_state=runtime_state or None,
            user_id=self.user_id,
        )

    async def _restore_session_state(self, state: SessionStateSnapshot):
        await super()._restore_session_state(state)
        self.session_id = state.session_id or self.session_id
        self.user_id = state.user_id or self.user_id
        self.turn_count = state.turn_count
        self.session_status = state.session_status or self.session_status
        self.ai_state = state.ai_state or self.ai_state
        runtime_state = state.runtime_state if isinstance(state.runtime_state, dict) else {}
        restored_coach_health = runtime_state.get("coach_health")
        restored_live_session_summary = coerce_live_session_conclusion_summary(
            runtime_state.get("live_session_summary")
        )
        if isinstance(restored_coach_health, dict):
            restored_status = str(restored_coach_health.get("status") or "healthy")
            if restored_status not in {"healthy", "degraded", "resumed"}:
                restored_status = "healthy"
            restored_reason = restored_coach_health.get("reason")
            self._coach_health = restored_status
            self._coach_health_reason = (
                str(restored_reason).strip()
                if isinstance(restored_reason, str) and restored_reason.strip()
                else None
            )
        else:
            self._coach_health = "healthy"
            self._coach_health_reason = None
        self._latest_live_session_summary = restored_live_session_summary
        if self.capability_processor is not None:
            self.capability_processor.coach_health = self._coach_health
            self.capability_processor._coach_health_reason = self._coach_health_reason
            self.capability_processor.live_session_summary = restored_live_session_summary
        await self._send_reconnection_success(self._create_state_snapshot())

    # ========== Connection lifecycle hooks ==========

    async def _on_connection_established(self, **kwargs):
        """Send greeting after connection is established."""
        # Greeting is sent via _send_delayed_greeting in base class
        pass

    async def _on_connection_closed(self):
        """Clean up capability session on disconnect."""
        if self._greeting_task and not self._greeting_task.done():
            self._greeting_task.cancel()
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
        if self.capability_runner and self.context:
            try:
                await self.capability_runner.on_session_end(self.context)
            except (RuntimeError, ValueError) as e:
                logger.error(f"Error ending capability session: {e}")
        await super()._on_connection_closed()

    async def _handle_session_end(self):
        """Handle session end with capability cleanup and report generation."""
        logger.info(f"Enhanced session end requested: session_id={self.session_id}")

        # Cancel ongoing tasks
        if self._greeting_task and not self._greeting_task.done():
            self._greeting_task.cancel()
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()

        # End capability session
        if self.capability_runner and self.context:
            try:
                await self.capability_runner.on_session_end(self.context)
            except (RuntimeError, ValueError) as e:
                logger.error(f"Error ending capability session: {e}")

        # Trigger comprehensive report generation in background
        try:
            async with AsyncSessionLocal() as db:
                from common.ai.llm_service import LLMService
                from prompt_templates.service import PromptTemplateService
                from evaluation.services.staged_evaluation import StagedEvaluationService
                from evaluation.services.comprehensive_report import ComprehensiveReportService

                llm_service = LLMService()
                prompt_service = PromptTemplateService(db)
                staged_eval_service = StagedEvaluationService(
                    db_session=db, prompt_service=prompt_service, llm_service=llm_service
                )
                report_service = ComprehensiveReportService(
                    db_session=db,
                    staged_eval_service=staged_eval_service,
                    prompt_service=prompt_service,
                    llm_service=llm_service,
                )
                result = await report_service.generate_report(self.session_id, scenario_type="sales")
                if result.is_success:
                    logger.info(f"Comprehensive report generated for session {self.session_id}")
                else:
                    logger.warning(f"Report generation failed: {result.fallback}")
        except (RuntimeError, ValueError, OSError, ImportError) as e:
            logger.warning(f"Report generation skipped during session end: {e}")

        # Call base class to send confirmation and stop loop
        await super()._handle_session_end()

    # ========== Custom message handling ==========

    async def _handle_custom_message(self, msg_type: str, data: dict, message: dict):
        """Handle enhanced-specific message types (interrupt)."""
        if msg_type == "interrupt":
            reason = data.get("reason", "unknown")
            await self._handle_user_interrupt(reason)
        else:
            logger.warning(f"Unknown message type: {msg_type}")

    # ========== Interrupt handling ==========

    async def _handle_user_interrupt(self, reason: str = "unknown"):
        """
        Handle user interrupt signal - immediately stop TTS and LLM tasks.
        Target: <100ms response time (Constitution Principle II)
        """
        logger.info(f"[INTERRUPT] User interrupt received (reason: {reason})")
        self._is_interrupted = True

        if self._greeting_task and not self._greeting_task.done():
            self._greeting_task.cancel()
            logger.info("[INTERRUPT] Greeting task cancelled")

        # Cancel background response task (LLM+TTS pipeline)
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
            logger.info("[INTERRUPT] Response task cancelled")
            try:
                await self._response_task
            except asyncio.CancelledError:
                pass
            self._response_task = None

        interrupted_stream_id = self.current_stream_id

        # Cancel TTS task
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            logger.info("[INTERRUPT] TTS task cancelled")
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass
            self._tts_task = None

        # Cancel LLM task
        if self._llm_task and not self._llm_task.done():
            self._llm_task.cancel()
            logger.info("[INTERRUPT] LLM task cancelled")
            try:
                await self._llm_task
            except asyncio.CancelledError:
                pass
            self._llm_task = None

        # Stop streaming ASR
        await self._stop_streaming_asr()

        # Send interrupt confirmation
        trace_id = self._get_trace_id()
        await self.manager.send_json(
            self.websocket,
            {
                "type": "interrupted",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "stream_id": interrupted_stream_id,
                "data": {"reason": reason},
            },
        )

        self._is_interrupted = False
        self._current_turn_initialized = False
        await self._send_status("listening")
        logger.info("[INTERRUPT] Interrupt handling complete")

    # ========== Audio/ASR overrides (add backpressure + latency tracking) ==========

    async def _handle_audio_chunk(self, data: dict):
        """Handle audio chunk with backpressure control and latency tracking."""
        audio_base64 = data.get("audio", "")
        interrupt = data.get("interrupt", False)

        if interrupt:
            logger.info("User interrupted AI via audio chunk")
            await self._handle_user_interrupt("user_speaking")
            return

        if audio_base64:
            try:
                audio_bytes = base64.b64decode(audio_base64)

                # Latency tracking
                trace_id = self._get_trace_id()
                if trace_id:
                    latency_tracker = get_latency_tracker()
                    latency_tracker.record(
                        trace_id,
                        LatencyTracker.STAGE_AUDIO_RECEIVED,
                        {"audio_size": len(audio_bytes)},
                    )

                async with self._state_lock:
                    should_start = self.asr_queue is None
                if should_start and self._greeting_task and not self._greeting_task.done():
                    self._greeting_task.cancel()

                await self._enqueue_audio_bytes(audio_bytes)
            except (ValueError, OSError) as e:
                logger.error(f"Failed to decode audio: {e}")

    async def _start_streaming_asr(self):
        """Start streaming ASR session with turn tracking."""
        await self._stop_streaming_asr()

        await self._start_new_turn(interaction_type="audio")
        async with self._state_lock:
            self.is_user_speaking = True
            self.current_transcript = ""
            self.asr_queue = asyncio.Queue(maxsize=self.ASR_QUEUE_MAX_SIZE)
            self.asr_task = asyncio.create_task(self._run_streaming_asr())

        await self._send_status("listening")
        logger.info("Started streaming ASR session")

    async def _stop_streaming_asr(self):
        """Stop streaming ASR and process the final transcript.
        
        CRITICAL FIX: _process_user_text is launched as a background task instead of
        being awaited inline. Previously, the LLM+TTS pipeline (~5-10s) blocked the
        message processing loop, causing subsequent recording messages (user_speaking,
        audio_chunk, audio_end) to pile up. When they finally processed sequentially,
        ASR would start and immediately stop — producing only "嗯".
        """
        final_transcript = ""
        should_send_resume = False
        async with self._state_lock:
            self.is_user_speaking = False

            if self.asr_queue:
                try:
                    self.asr_queue.put_nowait(None)
                except asyncio.QueueFull:
                    try:
                        self.asr_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    with contextlib.suppress(asyncio.QueueFull):
                        self.asr_queue.put_nowait(None)

            if self.asr_task and not self.asr_task.done():
                try:
                    final_transcript = await asyncio.wait_for(self.asr_task, timeout=15.0)
                except TimeoutError:
                    logger.warning("ASR task timeout, cancelling")
                    self.asr_task.cancel()
                    if self.current_transcript and len(self.current_transcript.strip()) > 0:
                        final_transcript = self.current_transcript
                        logger.info(f"[ASR] Using current transcript after timeout: {final_transcript[:50]}...")
                except (RuntimeError, OSError) as e:
                    logger.error(f"Error waiting for ASR task: {e}")

            self.asr_task = None
            self.asr_queue = None
            if self._backpressure_active:
                self._backpressure_active = False
                should_send_resume = True

        if should_send_resume:
            await self._send_backpressure("resume", 0)

        if final_transcript and len(final_transcript.strip()) > 0:
            logger.info(f"[ASR] Processing final transcript (non-blocking): {final_transcript[:50]}...")
            # Fire-and-forget: run LLM+TTS pipeline in background so the message
            # processing loop stays responsive for the next recording session.
            await self._launch_response_task(final_transcript, source="asr_final")

    async def _run_streaming_asr(self):
        """Run streaming ASR with latency tracking."""
        asr_service = get_asr_service()
        total_bytes = 0
        trace_id = self._get_trace_id()
        latency_tracker = get_latency_tracker()

        if trace_id:
            latency_tracker.record(trace_id, LatencyTracker.STAGE_ASR_START)

        async def audio_generator():
            nonlocal total_bytes
            while True:
                try:
                    chunk = await asyncio.wait_for(self.asr_queue.get(), timeout=30.0)
                    if chunk is None:
                        logger.info(f"Audio stream ended, total {total_bytes} bytes")
                        break
                    total_bytes += len(chunk)
                    yield chunk
                except TimeoutError:
                    logger.warning("Audio queue timeout")
                    break

        final_transcript = ""
        try:
            async for result in asr_service.stream_transcribe(audio_generator()):
                if result.is_success and result.value:
                    self.current_transcript = result.value
                    await self._send_transcript(result.value, is_final=False)
                    logger.debug(f"ASR interim: {result.value}")

            if self.current_transcript and len(self.current_transcript.strip()) > 0:
                final_transcript = self.current_transcript
                logger.info(f"ASR final: {final_transcript}")
                await self._send_transcript(final_transcript, is_final=True)

                if trace_id:
                    latency_tracker.record(
                        trace_id,
                        LatencyTracker.STAGE_ASR_COMPLETE,
                        {"transcript_length": len(final_transcript)},
                    )
            else:
                logger.warning("ASR returned empty transcript")
                await self._send_status("listening")

        except (ConnectionError, OSError, RuntimeError) as e:
            logger.error(f"Streaming ASR error: {e}", exc_info=True)
            await self._send_status("listening")

        return final_transcript

    async def _handle_audio_end(self):
        """Handle audio end signal with duplicate-call protection."""
        if getattr(self, "_is_processing_audio_end", False):
            logger.debug("Already processing audio end, skipping duplicate call")
            return
        self._is_processing_audio_end = True
        try:
            logger.info("Audio end received, stopping ASR stream")
            await self._stop_streaming_asr()
        finally:
            self._is_processing_audio_end = False

    async def _process_user_text_safe(self, text: str):
        """Wrapper around _process_user_text that catches exceptions.
        
        Used as a fire-and-forget background task. Without this wrapper,
        exceptions from _process_user_text would become unhandled task
        exceptions and log noisy warnings.
        """
        try:
            await self._process_user_text(text)
        except asyncio.CancelledError:
            logger.info("[RESPONSE] Background response task cancelled")
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"[RESPONSE] Background response task error: {e}", exc_info=True)
            await self._send_status("listening")
        finally:
            current_task = asyncio.current_task()
            if self._response_task is current_task:
                self._response_task = None

    # ========== Turn tracking ==========

    async def _start_new_turn(self, interaction_type: str = "audio"):
        """Start a new conversation turn with trace_id."""
        if self._current_turn_initialized:
            logger.debug(f"Turn already initialized for turn_count={self.turn_count}")
            return
        self.turn_count += 1
        new_trace_id = str(uuid.uuid4())
        if self.context:
            self.context.turn_count = self.turn_count
            self.context.trace_id = new_trace_id
        self._current_turn_initialized = True
        logger.info(f"[TURN {self.turn_count}] Started new {interaction_type} interaction, trace_id={new_trace_id}")
        return new_trace_id

    # ========== Text processing (enhanced with capabilities + DB) ==========

    async def _process_user_text(self, text: str):
        """Process user text with capability modules, DB persistence, and interrupt support."""
        self.current_request_id += 1
        current_req_id = self.current_request_id
        logger.info(f"[REQUEST {current_req_id}] Processing user text: {text[:50]}...")

        await self._start_new_turn(interaction_type="text")

        if self.context:
            self.context.add_message("user", text)

        # P1-10: Sliding window
        self.conversation_history.append({"role": "user", "content": text})
        if len(self.conversation_history) > self.MAX_CONVERSATION_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_CONVERSATION_HISTORY:]

        # 1. Save user message (via component)
        user_message_id = None
        if self.session_id and self.persistence:
            user_message_id = await self.persistence.save_message(
                turn_number=self.turn_count,
                role="user",
                content=text,
                db_lock=self._db_lock,
            )

        await self._send_status("thinking")

        # 2. Run capability modules (via component)
        analysis_data: dict[str, Any] = {}
        knowledge_context: str = ""
        if self.capability_processor and self.context:
            analysis_data, knowledge_context = await self.capability_processor.run_and_send_feedback(
                text=text,
                context=self.context,
                websocket=self.websocket,
                manager=self.manager,
                db_lock=self._db_lock,
            )
            self._sync_coach_health_from_processor()

        # 3. Update message analysis data (via component)
        if user_message_id and analysis_data and self.persistence:
            await self.persistence.update_analysis(
                message_id=user_message_id,
                analysis_data=analysis_data,
                db_lock=self._db_lock,
            )

        self._current_turn_initialized = False

        # 4. Check interrupt before LLM
        if self._is_interrupted:
            logger.info("[PROCESS] Aborted - user interrupted")
            await self._send_status("listening")
            return

        kb_lock_decision = await evaluate_kb_lock_decision(
            query=text,
            effective_policy=self._voice_policy_snapshot,
        )
        if kb_lock_decision.lock_required:
            if kb_lock_decision.allow_generation:
                knowledge_context = kb_lock_decision.grounding_context
            else:
                logger.info(
                    "[KB_LOCK] Blocked generation on enhanced path",
                    session_id=self.session_id,
                    status=kb_lock_decision.status,
                )

        # 5. Generate AI response (with knowledge context)
        if kb_lock_decision.lock_required and not kb_lock_decision.allow_generation:
            response_text = kb_lock_decision.user_message
        else:
            self._llm_task = asyncio.create_task(
                self._generate_response(text, knowledge_context=knowledge_context)
            )
            try:
                response_text = await self._llm_task
            except asyncio.CancelledError:
                logger.info("[PROCESS] LLM task was cancelled")
                response_text = None
            finally:
                self._llm_task = None

        logger.info(f"[PROCESS] Response: {response_text[:50] if response_text else 'None'}...")

        if response_text:
            # P1-10: Sliding window
            self.conversation_history.append({"role": "assistant", "content": response_text})
            if len(self.conversation_history) > self.MAX_CONVERSATION_HISTORY:
                self.conversation_history = self.conversation_history[-self.MAX_CONVERSATION_HISTORY:]
            if self.context:
                self.context.add_message("assistant", response_text)

            # 6. Save AI message (via component)
            if self.session_id and self.persistence:
                await self.persistence.save_message(
                    turn_number=self.turn_count,
                    role="assistant",
                    content=response_text,
                    db_lock=self._db_lock,
                )

            # 7. Check interrupt before TTS
            if self._is_interrupted:
                logger.info("[PROCESS] Aborted TTS - user interrupted")
                await self._send_status("listening")
                return

            # 8. Send TTS response (via component)
            current_stream_id = str(uuid.uuid4())
            self.current_stream_id = current_stream_id
            trace_id = self._get_trace_id()

            self._tts_task = asyncio.create_task(
                self.tts_component.send_response_streaming(
                    text=response_text,
                    request_id=current_req_id,
                    stream_id=current_stream_id,
                    websocket=self.websocket,
                    manager=self.manager,
                    trace_id=trace_id,
                    is_interrupted_fn=lambda: self._is_interrupted,
                    current_stream_id_fn=lambda: self.current_stream_id,
                )
            )
            try:
                await self._tts_task
            except asyncio.CancelledError:
                logger.info("[PROCESS] TTS task was cancelled")
            finally:
                self._tts_task = None
        else:
            fallback = self._get_fallback_response()
            self.conversation_history.append({"role": "assistant", "content": fallback})
            await self._send_tts_response(fallback, self.current_request_id)

        await self._send_status("listening")

    # ========== LLM generation ==========

    def _resolve_llm_service(self):
        """Resolve LLM service from agent-level override, falling back to global default."""
        capabilities_config = self.agent_config.get("capabilities_config", {})
        llm_config = capabilities_config.get("llm", {}) if isinstance(capabilities_config, dict) else {}
        config_id = llm_config.get("model_config_id") if isinstance(llm_config, dict) else None

        if not isinstance(config_id, str) or not config_id:
            self._llm_override_service = None
            self._llm_override_config_id = None
            return get_llm_service()

        if self._llm_override_service is not None and self._llm_override_config_id == config_id:
            return self._llm_override_service

        config_manager = get_config_manager()
        model_config = config_manager.get_config_by_id(config_id)
        if (
            model_config is None
            or not model_config.is_active
            or model_config.model_type != ModelType.LLM.value
        ):
            logger.warning(
                f"LLM override config unavailable for agent {self.agent_id}: {config_id}, falling back to default"
            )
            self._llm_override_service = None
            self._llm_override_config_id = None
            return get_llm_service()

        self._llm_override_service = create_llm_service(model_config)
        self._llm_override_config_id = config_id
        logger.info(f"Using agent-level LLM override config: {config_id}")
        return self._llm_override_service

    async def _generate_response(self, user_text: str, **kwargs) -> str | None:
        """Generate LLM response based on Persona configuration and knowledge context."""
        knowledge_context = kwargs.get("knowledge_context", "")
        try:
            logger.info(f"[LLM] Starting generation for: {user_text[:50]}...")

            trace_id = self._get_trace_id()
            if trace_id:
                latency_tracker = get_latency_tracker()
                latency_tracker.record(trace_id, LatencyTracker.STAGE_LLM_START)

            llm_service = self._resolve_llm_service()

            base_instructions = self._base_instructions or self._resolve_base_instructions()
            if not base_instructions:
                base_instructions = "你是一个销售教练。"
            system_prompt = VoiceInstructionCompiler.compose_turn_instructions(
                base_instructions=base_instructions,
                grounding_context=knowledge_context,
            )

            context = {"scenario": "sales", "history": self.conversation_history[-10:]}

            result = await llm_service.generate(
                prompt=user_text,
                session_id=self.session_id,
                system_message=system_prompt,
                context=context,
            )

            if result.is_success:
                if trace_id:
                    latency_tracker = get_latency_tracker()
                    latency_tracker.record(
                        trace_id,
                        LatencyTracker.STAGE_LLM_COMPLETE,
                        {"response_length": len(result.value) if result.value else 0},
                    )
                return result.value
            else:
                logger.warning(f"[LLM] Generation failed: {result.fallback}")
                return None

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"[LLM] Error: {str(e)}", exc_info=True)
            return None

    def _get_fallback_response(self) -> str:
        """Get fallback response based on Persona configuration."""
        behavior = self.persona_config.get("behavior_config", {})
        fallback = behavior.get("fallback_response")
        if fallback:
            return fallback
        return "请继续。"

    # ========== Greeting ==========

    async def _send_greeting(self):
        """Send Persona greeting with TTS."""
        if self.turn_count > 0:
            return

        greeting = self.agent_config.get("welcome_message")
        if not greeting:
            greeting = "你好！准备好练习了吗？"

        logger.info(f"Sending greeting: {greeting[:30] if len(greeting) > 30 else greeting}...")

        self.conversation_history.append({"role": "assistant", "content": greeting})
        if self.context:
            self.context.add_message("assistant", greeting)

        # Save greeting message (via component)
        if self.session_id and self.persistence:
            await self.persistence.save_message(
                turn_number=0,
                role="assistant",
                content=greeting,
                db_lock=self._db_lock,
            )

        # Send TTS
        self.current_request_id += 1
        self.current_stream_id = str(uuid.uuid4())
        trace_id = self._get_trace_id()

        if self.tts_component:
            await self.tts_component.send_response(
                text=greeting,
                websocket=self.websocket,
                manager=self.manager,
                trace_id=trace_id,
                stream_id=self.current_stream_id,
                request_id=self.current_request_id,
                is_interrupted_fn=lambda: self._is_interrupted,
                current_stream_id_fn=lambda: self.current_stream_id,
            )
        await self._send_status("listening")

    # ========== Helper: trace_id ==========

    def _get_trace_id(self) -> str | None:
        """Get current trace_id from context."""
        return self.context.trace_id if self.context else None

    # ========== Enhanced message senders (add trace_id) ==========

    async def _send_transcript(self, text: str, is_final: bool):
        """Send ASR transcript with trace_id."""
        await self.manager.send_json(self.websocket, {
            "type": "asr_transcript",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self._get_trace_id(),
            "data": {"text": text, "is_final": is_final, "confidence": 0.95},
        })

    async def _send_tts_response(self, text: str, request_id: int):
        """Send TTS response via component with trace_id."""
        if self.tts_component:
            await self.tts_component.send_response(
                text=text,
                websocket=self.websocket,
                manager=self.manager,
                trace_id=self._get_trace_id(),
                stream_id=self.current_stream_id,
                request_id=request_id,
                is_interrupted_fn=lambda: self._is_interrupted,
                current_stream_id_fn=lambda: self.current_stream_id,
            )
        else:
            await super()._send_tts_response(text, request_id)

    async def _send_status(self, ai_state: str):
        """Send status update with trace_id."""
        await self.manager.send_json(self.websocket, {
            "type": "status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self._get_trace_id(),
            "data": {
                "session_status": self.session_status,
                "ai_state": ai_state,
                "turn_count": self.turn_count,
            },
        })

    async def _send_backpressure(self, action: str, queue_size: int):
        """Send backpressure signal to client."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self._get_trace_id(),
            "data": {
                "action": action,
                "queue_size": queue_size,
                "high_watermark": self.ASR_HIGH_WATERMARK,
                "low_watermark": self.ASR_LOW_WATERMARK,
            },
        }
        await self.manager.send_json(self.websocket, {
            "type": "backpressure",
            **payload,
        })
        # Legacy alias for old clients during transition window.
        await self.manager.send_json(self.websocket, {
            "type": "system_backpressure",
            **payload,
        })

    async def _send_error(self, code: str, message: str):
        """Send error with trace_id."""
        await self.manager.send_json(self.websocket, {
            "type": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self._get_trace_id(),
            "data": {"code": code, "message": message, "user_action": "请重试"},
        })


def create_enhanced_sales_handler() -> EnhancedSalesHandler:
    """Create a new enhanced sales handler instance."""
    return EnhancedSalesHandler()

"""
Enhanced Sales Bot WebSocket Handler

Extends SimpleSalesHandler with Agent Platform capabilities:
- Dynamic Agent/Persona configuration
- Capability module integration (fuzzy detection, sales stage, scoring)
- Message storage for replay
- Real-time feedback messages

References:
- Requirements: R11 (WebSocket Enhancement)
- Design: Section 20 (EnhancedSalesHandler)
- API Contract: docs/api-contract/websocket.md
"""
import asyncio
import base64
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from agent.capabilities.runner import CapabilityRunner
from agent.context import AgentContext
from agent.services.agent_service import AgentService
from agent.services.persona_service import PersonaService
from common.ai.llm_service import get_llm_service
from common.audio.asr_service import get_asr_service
from common.audio.tts_service import get_tts_service, TTSChunk
from common.conversation.storage import MessageStorageService
from common.knowledge.service import KnowledgeService
from common.monitoring.logger import get_logger
from common.monitoring.latency_tracker import get_latency_tracker, LatencyTracker
from common.websocket.base_handler import BaseWebSocketHandler

logger = get_logger(__name__)


class EnhancedSalesHandler(BaseWebSocketHandler):
    """
    Enhanced WebSocket handler for sales practice with Agent Platform integration.

    Uses composition pattern to integrate:
    - CapabilityRunner: Executes capability modules (fuzzy detection, sales stage, scoring)
    - MessageStorageService: Stores conversation messages for replay
    - AgentContext: Provides runtime context for capabilities

    Maintains backward compatibility with SimpleSalesHandler by supporting
    sessions without agent_id/persona_id (falls back to default behavior).
    """

    def __init__(self):
        super().__init__("sales")
        # Session identifiers
        self.session_id: str | None = None
        self.agent_id: str | None = None
        self.persona_id: str | None = None
        self.user_id: str | None = None

        # Composed components (initialized in initialize())
        self.capability_runner: CapabilityRunner | None = None
        self.message_storage: MessageStorageService | None = None
        self.context: AgentContext | None = None
        self.db: AsyncSession | None = None

        # Configuration
        self.agent_config: dict[str, Any] = {}
        self.persona_config: dict[str, Any] = {}

        # WebSocket state
        self.websocket: WebSocket | None = None
        self.turn_count = 0
        self.conversation_history: list[dict] = []
        self.is_user_speaking = False
        self._pending_process = False

        # Streaming ASR state
        self.asr_queue: asyncio.Queue | None = None  # 音频数据队列
        self.asr_task: asyncio.Task | None = None    # ASR 处理任务
        self.current_transcript = ""                  # 当前识别结果

        # Backpressure control (Requirements: Voice Practice Optimization P0-2)
        # Increased watermarks to reduce false "network slow" warnings
        self.ASR_QUEUE_MAX_SIZE = 200  # Maximum queue size (increased from 100)
        self.ASR_HIGH_WATERMARK = 150  # Trigger slow_down at this level (increased from 80)
        self.ASR_LOW_WATERMARK = 100   # Trigger resume at this level (increased from 50)
        self._backpressure_active = False  # Track backpressure state

        # Audio buffer and sequence tracking (still needed for audio processing)
        self.audio_buffer: bytes = b""
        self.expected_sequence = 0
        self.received_sequences: set[int] = set()
        self.last_sequence: int | None = None
        self.audio_chunks: dict[int, bytes] = {}  # seq -> audio data
        self.SEQUENCE_WAIT_TIMEOUT = 2.0  # 等待缺失序列的超时时间

        # Audio processing parameters
        self.MIN_AUDIO_SIZE = 4800
        self.MIN_SPEECH_DURATION = 0.3

        # Task references for interrupt cancellation (Requirements 3.3, 3.4)
        self._llm_task: asyncio.Task | None = None
        self._tts_task: asyncio.Task | None = None
        self._greeting_task: asyncio.Task | None = None
        self._is_interrupted: bool = False
        self._db_lock = asyncio.Lock()  # Serialize DB access for the same session

        # Critical Fix #2 & #3: 消息版本控制防止乱序和状态不同步
        self.current_request_id: int = 0  # 当前请求ID,递增
        self.current_stream_id: str | None = None  # 当前TTS流ID
        self.uuid = uuid  # 保存uuid模块引用
        
        # Internal state for current turn
        self._current_turn_initialized: bool = False

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

        Loads Agent and Persona from database, initializes capability runner
        and message storage service.

        Args:
            session_id: Practice session UUID
            agent_id: Agent UUID
            persona_id: Persona UUID
            user_id: User UUID
            db: Database session

        Returns:
            True if initialization successful, False otherwise.
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self.persona_id = persona_id
        self.user_id = user_id
        self.db = db

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
        self.persona_config = {
            "id": persona.id,
            "name": persona.name,
            "system_prompt": persona.system_prompt,
            "traits": persona.traits or {},
            "behavior_config": persona.behavior_config or {},
            "scoring_weights": persona.scoring_weights,
            "knowledge_base_ids": persona.knowledge_base_ids or [],
            "tts_config": persona.tts_config or {},
        }

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
            start_time=datetime.utcnow(),
        )

        # Initialize CapabilityRunner
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

        # Initialize MessageStorageService
        self.message_storage = MessageStorageService(db)

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


    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
    ):
        """Handle WebSocket connection for enhanced sales practice."""
        self.websocket = websocket
        self.session_id = session_id

        # Accept connection
        await self.manager.connect(websocket, self.scenario, session_id)

        # Initialize message queue
        self.message_queue = asyncio.Queue()
        self.running = True

        # Start message processing task
        processing_task = asyncio.create_task(self._process_messages())

        # Send initial status
        await self._send_status("listening")

        # Send greeting after a short delay
        self._greeting_task = asyncio.create_task(self._send_delayed_greeting())

        try:
            while self.running:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=30.0,
                    )
                    await self.message_queue.put(data)
                except TimeoutError:
                    await self._send_heartbeat()

        except WebSocketDisconnect:
            logger.info(f"Enhanced Sales WebSocket disconnected: session={session_id}")
        except Exception as e:
            logger.error(f"Enhanced Sales WebSocket error: {str(e)}")
        finally:
            self.running = False
            self.manager.disconnect(self.scenario, session_id)
            if self._greeting_task:
                self._greeting_task.cancel()
            processing_task.cancel()

            # End capability session
            if self.capability_runner and self.context:
                try:
                    await self.capability_runner.on_session_end(self.context)
                except Exception as e:
                    logger.error(f"Error ending capability session: {e}")

    async def _send_delayed_greeting(self):
        """Send greeting after a short delay to ensure client is ready."""
        await asyncio.sleep(0.5)
        await self._send_greeting()

    async def _process_messages(self):
        """Process messages from queue."""
        while self.running:
            try:
                message = await self.message_queue.get()
                await self.handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processing error: {str(e)}")

    async def handle_message(self, message: dict):
        """Handle incoming WebSocket message."""
        msg_type = message.get("type")
        data = message.get("data", {})

        logger.debug(f"Enhanced handler received message type: {msg_type}")

        try:
            if msg_type == "audio_chunk":
                await self._handle_audio_chunk(data)

            elif msg_type == "audio_end":
                # 音频结束信号 - 触发 ASR commit
                await self._handle_audio_end()

            elif msg_type == "user_speaking":
                speaking = data.get("speaking", False)

                if speaking:
                    # 用户开始说话 - 启动流式 ASR
                    await self._start_streaming_asr()
                else:
                    # 用户停止说话 - 触发 ASR commit
                    await self._handle_audio_end()

            elif msg_type == "text":
                text = data.get("text", "")
                if text:
                    await self._process_user_text(text)

            elif msg_type == "pause":
                await self._send_status("idle")

            elif msg_type == "resume":
                await self._send_status("listening")

            elif msg_type == "heartbeat_ack":
                pass

            elif msg_type == "interrupt":
                # Handle user interrupt - stop TTS and LLM tasks
                reason = data.get("reason", "unknown")
                await self._handle_user_interrupt(reason)

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error handling message {msg_type}: {str(e)}")
            await self._send_error("[PROCESSING_ERROR]", "处理消息时出错")

    async def _handle_user_interrupt(self, reason: str = "unknown"):
        """
        Handle user interrupt signal - immediately stop TTS and LLM tasks.
        
        Target: <100ms response time (Constitution Principle II)
        
        Args:
            reason: Reason for interrupt ('user_speaking' or 'manual')
        """
        logger.info(f"[INTERRUPT] User interrupt received (reason: {reason})")
        self._is_interrupted = True
        
        # Cancel greeting if it's still pending
        if self._greeting_task and not self._greeting_task.done():
            self._greeting_task.cancel()
            logger.info("[INTERRUPT] Greeting task cancelled")
        
        # Critical Fix #2: 记录被中断的stream_id
        interrupted_stream_id = self.current_stream_id
        
        # Cancel TTS task if running
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            logger.info("[INTERRUPT] TTS task cancelled")
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass
            self._tts_task = None
        
        # Cancel LLM task if running
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
        
        # Send interrupt confirmation to frontend
        # Critical Fix #2: 附加被中断的stream_id，让前端停止播放该流的音频
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "interrupted",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "stream_id": interrupted_stream_id,  # 添加stream_id
                "data": {"reason": reason},
            },
        )
        
        # Reset interrupt flag for next interaction
        self._is_interrupted = False
        self._current_turn_initialized = False # Reset turn state
        await self._send_status("listening")
        logger.info("[INTERRUPT] Interrupt handling complete")
        
    async def _start_new_turn(self, interaction_type: str = "audio"):
        """
        Unified method to start a new conversation turn.
        Ensures turn_count and trace_id are updated exactly once per interaction.
        """
        if self._current_turn_initialized:
            logger.debug(f"Turn already initialized for turn_count={self.turn_count}")
            return
            
        self.turn_count += 1
        new_trace_id = str(self.uuid.uuid4())
        
        if self.context:
            self.context.turn_count = self.turn_count
            self.context.trace_id = new_trace_id
            
        self._current_turn_initialized = True
        logger.info(f"[TURN {self.turn_count}] Started new {interaction_type} interaction, trace_id={new_trace_id}")
        return new_trace_id

    async def _handle_audio_chunk(self, data: dict):
        """Handle audio chunk - forward to streaming ASR immediately."""
        audio_base64 = data.get("audio", "")
        interrupt = data.get("interrupt", False)

        if interrupt:
            logger.info("User interrupted AI via audio chunk")
            await self._handle_user_interrupt("user_speaking")
            return

        if audio_base64:
            # 如果 ASR 还没启动，自动启动
            if not self.asr_queue:
                logger.info("Auto-starting ASR on first audio chunk")
                # Cancel greeting if user starts speaking
                if self._greeting_task and not self._greeting_task.done():
                    self._greeting_task.cancel()
                await self._start_streaming_asr()

            if self.asr_queue:
                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    
                    # Record latency: audio received
                    trace_id = self.context.trace_id if self.context else None
                    if trace_id:
                        latency_tracker = get_latency_tracker()
                        latency_tracker.record(
                            trace_id,
                            LatencyTracker.STAGE_AUDIO_RECEIVED,
                            {"audio_size": len(audio_bytes)},
                        )
                    
                    # Check queue size for backpressure control
                    queue_size = self.asr_queue.qsize()
                    
                    # Trigger backpressure if queue is getting full
                    if queue_size >= self.ASR_HIGH_WATERMARK and not self._backpressure_active:
                        self._backpressure_active = True
                        await self._send_backpressure("slow_down", queue_size)
                        logger.warning(f"[BACKPRESSURE] Activated - queue size: {queue_size}")
                    
                    # Resume if queue has drained
                    elif queue_size <= self.ASR_LOW_WATERMARK and self._backpressure_active:
                        self._backpressure_active = False
                        await self._send_backpressure("resume", queue_size)
                        logger.info(f"[BACKPRESSURE] Deactivated - queue size: {queue_size}")
                    
                    # Drop audio if queue is at max capacity (prevent memory issues)
                    if queue_size >= self.ASR_QUEUE_MAX_SIZE:
                        logger.warning(f"[BACKPRESSURE] Queue full ({queue_size}), dropping audio chunk")
                        return
                    
                    # 放入队列，流式发送给 ASR
                    await self.asr_queue.put(audio_bytes)
                except Exception as e:
                    logger.error(f"Failed to decode audio: {e}")

    async def _start_streaming_asr(self):
        """Start streaming ASR session."""
        # 停止之前的 ASR 任务（如果有）
        await self._stop_streaming_asr()

        self.is_user_speaking = True
        self.current_transcript = ""
        self.asr_queue = asyncio.Queue()
        
        # Start new turn early (Requirement VII: Observability)
        await self._start_new_turn(interaction_type="audio")

        # 启动 ASR 处理任务
        self.asr_task = asyncio.create_task(self._run_streaming_asr())

        await self._send_status("listening")
        logger.info("Started streaming ASR session")

    async def _stop_streaming_asr(self):
        """Stop streaming ASR session and process the final transcript."""
        self.is_user_speaking = False
        final_transcript = ""

        if self.asr_queue:
            # 发送结束标记
            await self.asr_queue.put(None)

        if self.asr_task and not self.asr_task.done():
            try:
                # 等待 ASR 任务完成（最多 15 秒，因为 ASR commit 后需要等待最终结果）
                final_transcript = await asyncio.wait_for(self.asr_task, timeout=15.0)
            except TimeoutError:
                logger.warning("ASR task timeout, cancelling")
                self.asr_task.cancel()
                # 即使超时，也尝试使用当前的转录结果
                if self.current_transcript and len(self.current_transcript.strip()) > 0:
                    final_transcript = self.current_transcript
                    logger.info(f"[ASR] Using current transcript after timeout: {final_transcript[:50]}...")
            except Exception as e:
                logger.error(f"Error waiting for ASR task: {e}")

        self.asr_task = None
        self.asr_queue = None

        # 处理最终转录结果（在 ASR 任务完成后）
        if final_transcript and len(final_transcript.strip()) > 0:
            logger.info(f"[ASR] Processing final transcript: {final_transcript[:50]}...")
            await self._process_user_text(final_transcript)

    async def _run_streaming_asr(self):
        """Run streaming ASR and process results."""
        asr_service = get_asr_service()
        total_bytes = 0
        trace_id = self.context.trace_id if self.context else None
        latency_tracker = get_latency_tracker()
        
        # Record ASR start
        if trace_id:
            latency_tracker.record(trace_id, LatencyTracker.STAGE_ASR_START)

        async def audio_generator():
            """Generate audio chunks from queue."""
            nonlocal total_bytes
            while True:
                try:
                    chunk = await asyncio.wait_for(self.asr_queue.get(), timeout=30.0)
                    if chunk is None:  # 结束标记
                        logger.info(f"Audio stream ended, total {total_bytes} bytes")
                        break
                    total_bytes += len(chunk)
                    yield chunk
                except TimeoutError:
                    logger.warning("Audio queue timeout")
                    break

        final_transcript = ""
        try:
            # 流式处理 ASR，FunASR 流式模型会返回累积文本
            # 每次返回的是从开始到当前的完整文本，不是增量
            async for result in asr_service.stream_transcribe(audio_generator()):
                if result.is_success and result.value:
                    # FunASR 流式模型返回累积文本，直接使用
                    self.current_transcript = result.value
                    # 发送中间结果给前端
                    await self._send_transcript(result.value, is_final=False)
                    logger.debug(f"ASR interim: {result.value}")

            # ASR 完成，保存最终结果
            if self.current_transcript and len(self.current_transcript.strip()) > 0:
                final_transcript = self.current_transcript
                logger.info(f"ASR final: {final_transcript}")
                await self._send_transcript(final_transcript, is_final=True)
                
                # Record ASR complete
                if trace_id:
                    latency_tracker.record(
                        trace_id, 
                        LatencyTracker.STAGE_ASR_COMPLETE,
                        {"transcript_length": len(final_transcript)},
                    )
            else:
                logger.warning("ASR returned empty transcript")
                await self._send_status("listening")

        except Exception as e:
            logger.error(f"Streaming ASR error: {e}", exc_info=True)
            await self._send_status("listening")

        # 返回最终结果，由调用者处理
        return final_transcript

    async def _handle_audio_end(self):
        """Handle audio end signal - trigger ASR commit."""
        # Use a flag to prevent multiple concurrent processing
        if getattr(self, "_is_processing_audio_end", False):
            logger.debug("Already processing audio end, skipping duplicate call")
            return
            
        self._is_processing_audio_end = True
        try:
            logger.info("Audio end received, stopping ASR stream")
            await self._stop_streaming_asr()
        finally:
            self._is_processing_audio_end = False

    async def _process_user_text(self, text: str):
        """
        Process user text with capability module integration.
        """
        # Critical Fix #2: 递增请求ID
        self.current_request_id += 1
        current_req_id = self.current_request_id
        logger.info(f"[REQUEST {current_req_id}] Processing user text: {text[:50]}...")
        
        # 1. Ensure turn is initialized (for text-only turns or if ASR didn't start)
        await self._start_new_turn(interaction_type="text")
        
        if self.context:
            self.context.add_message("user", text)

        # Add to local conversation history
        self.conversation_history.append({"role": "user", "content": text})

        # 1. Save user message
        user_message_id = None
        if self.message_storage and self.session_id:
            async with self._db_lock:
                save_result = await self.message_storage.save_message(
                    session_id=self.session_id,
                    turn_number=self.turn_count,
                    role="user",
                    content=text,
                )
                if save_result.is_success:
                    user_message_id = save_result.value.id

        await self._send_status("thinking")
        logger.info(f"[PROCESS] Processing user text: {text[:50]}...")

        # 2. Run capability modules in parallel
        analysis_data: dict[str, Any] = {}
        knowledge_context: str = ""  # 知识库检索结果
        logger.info(f"[PROCESS] Running capability modules...")
        if self.capability_runner and self.context:
            # Use lock to prevent concurrent DB access from background tasks (like greeting save)
            async with self._db_lock:
                capability_results = await self.capability_runner.run_all(self.context, text)

            # 3. Process capability results and send real-time feedback
            for i, result in enumerate(capability_results):
                if not result.success:
                    continue

                cap = self.capability_runner.capabilities[i]

                if cap.capability_id == "fuzzy_detection" and result.data:
                    detections = result.data.get("detections", [])
                    if detections:
                        await self._send_fuzzy_detection(detections)
                        analysis_data["fuzzy_words"] = detections

                elif cap.capability_id == "sales_stage" and result.data:
                    await self._send_stage_update(result.data)
                    analysis_data["sales_stage"] = result.data.get("current_stage")

                elif cap.capability_id == "realtime_scoring" and result.data:
                    await self._send_score_update(result.data)
                    analysis_data["score_snapshot"] = result.data

                elif cap.capability_id == "knowledge_retrieval" and result.data:
                    # 获取知识库检索结果
                    knowledge_context = result.data.get("context", "")
                    if knowledge_context:
                        logger.info(
                            f"Knowledge retrieval returned {len(result.data.get('results', []))} results"
                        )

        # 4. Update message with analysis data
        if self.message_storage and user_message_id and analysis_data:
            async with self._db_lock:
                await self.message_storage.update_analysis(user_message_id, **analysis_data)

        # End of turn processing
        self._current_turn_initialized = False
        
        # 5. Generate AI response (with knowledge context)
        logger.info(f"[PROCESS] Calling _generate_response...")
        
        # Check if interrupted before starting LLM
        if self._is_interrupted:
            logger.info("[PROCESS] Aborted - user interrupted")
            await self._send_status("listening")
            return
        
        # Wrap LLM call in a task for cancellation support
        self._llm_task = asyncio.create_task(self._generate_response(text, knowledge_context))
        try:
            response_text = await self._llm_task
        except asyncio.CancelledError:
            logger.info("[PROCESS] LLM task was cancelled")
            response_text = None
        finally:
            self._llm_task = None
        
        logger.info(f"[PROCESS] Response received: {response_text[:50] if response_text else 'None'}...")

        if response_text:
            self.conversation_history.append({"role": "assistant", "content": response_text})
            if self.context:
                self.context.add_message("assistant", response_text)

            # 6. Save AI message
            if self.message_storage and self.session_id:
                async with self._db_lock:
                    await self.message_storage.save_message(
                        session_id=self.session_id,
                        turn_number=self.turn_count,
                        role="assistant",
                        content=response_text,
                    )

            # Check if interrupted before starting TTS
            if self._is_interrupted:
                logger.info("[PROCESS] Aborted TTS - user interrupted")
                await self._send_status("listening")
                return

            # 7. Send TTS response (wrapped in task for cancellation)
            # Critical Fix #2: 为这个TTS流生成新的stream_id
            current_stream_id = str(self.uuid.uuid4())
            self.current_stream_id = current_stream_id
            logger.info(f"[PROCESS] Starting TTS with stream_id={current_stream_id}")
            
            self._tts_task = asyncio.create_task(
                self._send_tts_response_streaming(response_text, current_req_id, current_stream_id)
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
            await self._send_tts_response(fallback)

        await self._send_status("listening")

    async def _generate_response(
        self, user_text: str, knowledge_context: str = ""
    ) -> str | None:
        """Generate LLM response based on Persona configuration and knowledge context."""
        try:
            logger.info(f"[LLM] Starting generation for: {user_text[:50]}...")
            
            # Record LLM start
            trace_id = self.context.trace_id if self.context else None
            if trace_id:
                latency_tracker = get_latency_tracker()
                latency_tracker.record(trace_id, LatencyTracker.STAGE_LLM_START)
            
            llm_service = get_llm_service()
            logger.info(f"[LLM] Service configured: {llm_service.is_configured}, provider: {llm_service.provider}, model: {llm_service.model_name}")

            # Use Persona system prompt if available
            system_prompt = self.persona_config.get("system_prompt", "")
            if not system_prompt:
                system_prompt = self.agent_config.get("system_prompt", "你是一个销售教练。")
            logger.info(f"[LLM] System prompt length: {len(system_prompt)}")

            # Append knowledge context to system prompt if available
            if knowledge_context:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    f"## 参考知识\n"
                    f"以下是与用户问题相关的知识库内容，请在回答时参考：\n\n"
                    f"{knowledge_context}"
                )

            context = {
                "scenario": "sales",
                "history": self.conversation_history[-10:],
            }
            logger.info(f"[LLM] Context history length: {len(self.conversation_history[-10:])}")

            logger.info("[LLM] Calling llm_service.generate()...")
            result = await llm_service.generate(
                prompt=user_text,
                session_id=self.session_id,
                system_message=system_prompt,
                context=context,
            )
            logger.info(f"[LLM] Generate result: is_success={result.is_success}")

            if result.is_success:
                logger.info(f"[LLM] Response received: {result.value[:50] if result.value else 'None'}...")
                
                # Record LLM complete
                if trace_id:
                    latency_tracker.record(
                        trace_id, 
                        LatencyTracker.STAGE_LLM_COMPLETE,
                        {"response_length": len(result.value) if result.value else 0},
                    )
                
                return result.value
            else:
                logger.warning(f"[LLM] Generation failed: {result.fallback}")
                return None

        except Exception as e:
            logger.error(f"[LLM] Error: {str(e)}", exc_info=True)
            return None

    def _get_fallback_response(self) -> str:
        """Get fallback response based on Persona configuration."""
        # Try to get from Persona behavior_config
        behavior = self.persona_config.get("behavior_config", {})
        fallback = behavior.get("fallback_response")
        if fallback:
            return fallback

        # Default fallback
        return "请继续。"

    async def _send_greeting(self):
        """Send Persona greeting with TTS."""
        if self.turn_count > 0:
            return

        # Use Agent welcome_message as greeting (Persona doesn't have greeting field)
        greeting = self.agent_config.get("welcome_message")
        if not greeting:
            greeting = "你好！准备好练习了吗？"

        logger.info(f"Sending greeting: {greeting[:30] if len(greeting) > 30 else greeting}...")

        self.conversation_history.append({"role": "assistant", "content": greeting})
        if self.context:
            self.context.add_message("assistant", greeting)

        # Save greeting message
        if self.message_storage and self.session_id:
            async with self._db_lock:
                await self.message_storage.save_message(
                    session_id=self.session_id,
                    turn_number=0,
                    role="assistant",
                    content=greeting,
                )

        # Critical Fix #2: greeting也需要stream_id和request_id
        self.current_request_id += 1
        self.current_stream_id = str(self.uuid.uuid4())
        await self._send_tts_response(greeting)
        await self._send_status("listening")


    # ========== Real-time Feedback Messages ==========

    async def _send_fuzzy_detection(self, detections: list[dict]):
        """Send fuzzy word detection message to client."""
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "fuzzy_detection",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": {"detections": detections},
            },
        )

    async def _send_stage_update(self, stage_data: dict):
        """Send sales stage update message to client."""
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "stage_update",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": stage_data,
            },
        )

    async def _send_score_update(self, score_data: dict):
        """Send score update message to client."""
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "score_update",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": score_data,
            },
        )

    # ========== Standard WebSocket Messages ==========

    async def _send_transcript(self, text: str, is_final: bool):
        """Send ASR transcript to client."""
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "asr_transcript",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": {"text": text, "is_final": is_final, "confidence": 0.95},
            },
        )

    async def _send_tts_response(self, text: str):
        """
        Send TTS audio response to client using Persona's TTS config.
        
        Critical Fix #2: 添加stream_id和request_id防止消息乱序
        """
        tts_service = get_tts_service()
        trace_id = self.context.trace_id if self.context else None

        # Apply Persona's TTS config if available
        tts_config = self.persona_config.get("tts_config", {})
        if tts_config:
            voice = tts_config.get("voice")
            rate = tts_config.get("rate")
            volume = tts_config.get("volume")
            pitch = tts_config.get("pitch")
            tts_service.set_voice_parameters(rate=rate, volume=volume, pitch=pitch)
            if voice:
                tts_service.voice = voice

        try:
            result = await tts_service.synthesize(text)

            if result.is_success:
                audio_chunks = []
                async for chunk in result.value:
                    audio_chunks.append(chunk)

                audio_data = b"".join(audio_chunks)
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                duration_ms = int(len(audio_data) / 2) if audio_data else len(text) * 100

                # Critical Fix #2: 添加stream_id和request_id到TTS消息
                await self.manager.send_json(
                    self.websocket,
                    {
                        "type": "tts_audio",
                        "timestamp": datetime.utcnow().isoformat(),
                        "trace_id": trace_id,
                        "stream_id": self.current_stream_id,  # 添加stream_id
                        "request_id": self.current_request_id,  # 添加request_id
                        "data": {
                            "text": text,
                            "audio": audio_base64,
                            "duration_ms": duration_ms,
                        },
                    },
                )
            else:
                logger.warning(f"TTS failed: {result.fallback}")
                await self._send_tts_fallback(text, trace_id)

        except Exception as e:
            logger.error(f"TTS error: {str(e)}", exc_info=True)
            await self._send_tts_fallback(text, trace_id)

    async def _send_tts_fallback(self, text: str, trace_id: str | None):
        """
        Send TTS fallback message for browser TTS.
        
        Critical Fix #2: 添加stream_id和request_id防止消息乱序
        """
        await self.manager.send_json(
            self.websocket,
            {
                "type": "tts_audio",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "stream_id": self.current_stream_id,  # 添加stream_id
                "request_id": self.current_request_id,  # 添加request_id
                "data": {
                    "text": text,
                    "audio": "",
                    "duration_ms": len(text) * 100,
                    "fallback": "browser_tts",
                },
            },
        )

    async def _send_tts_response_streaming(self, text: str, request_id: int, stream_id: str):
        """
        Send TTS audio response in streaming chunks.
        
        Requirements: 2.1, 2.4, 2.6 (Streaming TTS Playback)
        Critical Fix #2: 添加stream_id防止TTS消息乱序
        """
        logger.info(f"[TTS] Starting streaming for request {request_id}, stream {stream_id}, text: {text[:30]}...")
        from common.audio.tts_service import get_tts_service, TTSChunk
        tts_service = get_tts_service()
        trace_id = self.context.trace_id if self.context else None
        latency_tracker = get_latency_tracker()
        first_chunk_sent = False

        # Record TTS start
        if trace_id:
            latency_tracker.record(trace_id, LatencyTracker.STAGE_TTS_START)

        # Apply Persona's TTS config if available
        tts_config = self.persona_config.get("tts_config", {})
        if tts_config:
            voice = tts_config.get("voice")
            rate = tts_config.get("rate")
            volume = tts_config.get("volume")
            pitch = tts_config.get("pitch")
            tts_service.set_voice_parameters(rate=rate, volume=volume, pitch=pitch)
            if voice:
                tts_service.voice = voice

        async def on_chunk(chunk: TTSChunk):
            """Callback to send each TTS chunk to the client."""
            nonlocal first_chunk_sent
            
            # Check if interrupted or stream expired
            if self._is_interrupted:
                logger.info(f"[TTS] Interrupted - canceling stream {stream_id}")
                raise asyncio.CancelledError("TTS interrupted by user")
            
            if stream_id != self.current_stream_id:
                logger.warning(f"[TTS] Stream ID mismatch: expected {self.current_stream_id}, got {stream_id}. Stopping.")
                raise asyncio.CancelledError("TTS stream expired")
            
            audio_base64 = base64.b64encode(chunk.audio).decode("utf-8") if chunk.audio else ""
            
            message_data = {
                "chunk_index": chunk.chunk_index,
                "audio": audio_base64,
                "duration_ms": chunk.duration_ms,
                "is_final": chunk.is_final,
            }
            
            # Include text and total_duration_ms only on final chunk
            if chunk.is_final:
                message_data["text"] = chunk.text
                message_data["total_duration_ms"] = chunk.total_duration_ms
            
            # Critical Fix #2: 添加stream_id和request_id到每个TTS chunk
            await self.manager.send_json(
                self.websocket,
                {
                    "type": "tts_chunk",
                    "timestamp": datetime.utcnow().isoformat(),
                    "trace_id": trace_id,
                    "stream_id": stream_id,
                    "request_id": request_id, 
                    "data": message_data,
                },
            )
            
            # Record first chunk latency
            if not first_chunk_sent and chunk.audio:
                first_chunk_sent = True
                if trace_id:
                    latency_tracker.record(
                        trace_id, 
                        LatencyTracker.STAGE_TTS_FIRST_CHUNK,
                        {"chunk_size": len(chunk.audio)},
                    )
                logger.debug(f"[TTS] Sent first chunk for stream {stream_id}")
            
            # Record TTS complete on final chunk
            if chunk.is_final and trace_id:
                latency_tracker.record(
                    trace_id,
                    LatencyTracker.STAGE_TTS_COMPLETE,
                    {"total_duration_ms": chunk.total_duration_ms},
                )
                # Complete the trace
                latency_tracker.complete_trace(trace_id)

        try:
            result = await tts_service.synthesize_streaming(text, on_chunk)

            if result.is_success:
                logger.info(f"[TTS] Streaming complete for stream {stream_id}")
            else:
                logger.warning(f"[TTS] Streaming failed: {result.fallback}")
                await self._send_tts_fallback(text, trace_id)

        except asyncio.CancelledError:
            logger.info(f"[TTS] Stream {stream_id} task was cancelled")
            raise
        except Exception as e:
            logger.error(f"[TTS] Streaming error: {str(e)}", exc_info=True)
            await self._send_tts_fallback(text, trace_id)

    async def _send_status(self, ai_state: str):
        """Send status update to client."""
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "status",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": {
                    "session_status": "in_progress",
                    "ai_state": ai_state,
                    "turn_count": self.turn_count,
                },
            },
        )

    async def _send_backpressure(self, action: str, queue_size: int):
        """
        Send backpressure signal to client.
        
        Used to control audio streaming rate when ASR queue is getting full.
        
        Args:
            action: 'slow_down' or 'resume'
            queue_size: Current queue size for debugging
        
        Requirements: Voice Practice Optimization P0-2
        """
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "backpressure",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": {
                    "action": action,
                    "queue_size": queue_size,
                    "high_watermark": self.ASR_HIGH_WATERMARK,
                    "low_watermark": self.ASR_LOW_WATERMARK,
                },
            },
        )

    async def _send_heartbeat(self):
        """Send heartbeat to client."""
        await self.manager.send_json(
            self.websocket,
            {
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {},
            },
        )

    async def _send_error(self, code: str, message: str):
        """Send error to client."""
        trace_id = self.context.trace_id if self.context else None
        await self.manager.send_json(
            self.websocket,
            {
                "type": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "data": {"code": code, "message": message, "user_action": "请重试"},
            },
        )


def create_enhanced_sales_handler() -> EnhancedSalesHandler:
    """Create a new enhanced sales handler instance."""
    return EnhancedSalesHandler()

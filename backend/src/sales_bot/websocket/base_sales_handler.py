"""
Base Sales Handler - Common functionality for SimpleSalesHandler and EnhancedSalesHandler

NEW-15: Extracted from ~800 lines of duplicated code between the two handlers.

Provides:
- WebSocket connection lifecycle management
- Streaming ASR (audio → text) pipeline
- Message routing (audio_chunk, user_speaking, text, pause, resume, heartbeat_ack)
- TTS response sending (single-shot)
- Status/heartbeat/error messaging
- Conversation history with sliding window (MAX_CONVERSATION_HISTORY)
- Message deduplication (_is_similar_text)
- Audio buffer tracking and minimum speech duration enforcement
- Request/stream ID versioning (Critical Fix #2)

Subclasses override:
- _load_persona_config() → dict
- _generate_response(text, ...) → str | None
- _get_fallback_response() → str
- _send_greeting() → None
- _on_connection_established() → None  (optional hook)
- _on_connection_closed() → None  (optional hook)
- _process_user_text(text) → None  (if enhanced processing needed)
"""
import asyncio
import base64
import json
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from common.audio.asr_service import get_asr_service
from common.audio.pcm_duration import (
    calculate_pcm_duration_ms,
    resolve_pcm_audio_format,
)
from common.db.session import AsyncSessionLocal
from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleService,
)
from common.knowledge.kb_lock_guard import evaluate_kb_lock_decision
from common.monitoring.logger import get_logger, get_trace_id, set_trace_id
from common.monitoring.trace_context import normalize_trace_id
from common.websocket.base_handler import BaseWebSocketHandler
from common.websocket.session_manager import get_session_manager

logger = get_logger(__name__)


class BaseSalesHandler(BaseWebSocketHandler):
    """
    Base class for sales practice WebSocket handlers.
    Implements the common Audio → ASR → LLM → TTS → Audio pipeline.
    """

    # 会话历史最大长度，防止内存泄漏
    MAX_CONVERSATION_HISTORY = 50
    MAX_MESSAGE_QUEUE_SIZE = 300
    ASR_QUEUE_MAX_SIZE = 200
    ASR_HIGH_WATERMARK = 80
    ASR_LOW_WATERMARK = 50

    def __init__(self, scenario: str = "sales"):
        super().__init__(scenario)
        self.websocket: WebSocket | None = None
        self.session_id: str | None = None
        self.turn_count = 0
        self.conversation_history: list[dict] = []
        self.is_user_speaking = False
        self._pending_process = False

        # 状态锁，防止并发状态竞争
        self._state_lock = asyncio.Lock()

        # Streaming ASR state
        self.asr_queue: asyncio.Queue | None = None
        self.asr_task: asyncio.Task | None = None
        self.current_transcript = ""

        # Audio sequence tracking for reliable delivery
        self.received_sequences: set[int] = set()
        self.audio_chunks: dict[int, bytes] = {}  # seq -> audio data
        self.audio_buffer: bytes = b""
        self.audio_buffer_size: int = 0  # 跟踪音频大小

        # 调整参数
        self.MIN_AUDIO_SIZE = 4800  # 最小音频大小（约150ms的16kHz 16-bit音频）
        self.MIN_SPEECH_DURATION = 0.3  # 最小说话时长（秒）
        self.SEQUENCE_WAIT_TIMEOUT = 2.0  # 等待缺失序列的超时时间

        # 消息去重机制
        self.last_user_text: str = ""  # 上一条用户消息
        self.last_user_text_time: float = 0  # 上一条消息时间戳
        self.DUPLICATE_THRESHOLD = 2.0  # 2秒内相同消息视为重复

        # Critical Fix #2 & #3: 消息版本控制防止乱序和状态不同步
        self.current_request_id: int = 0  # 当前请求ID，递增
        self.current_stream_id: str | None = None  # 当前TTS流ID
        self.uuid = uuid
        self.session_status = "preparing"
        self.ai_state = "idle"
        self.session_scenario_type = scenario
        self._greeting_sent = False
        self._voice_policy_snapshot: dict[str, Any] = {}
        self._backpressure_active = False
        self._client_runtime_options: dict[str, Any] = {}
        self._response_task: asyncio.Task | None = None
        self._response_task_lock = asyncio.Lock()

    # ========== Connection Lifecycle ==========

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        **kwargs,
    ):
        """Handle WebSocket connection for sales practice."""
        incoming_trace_id = normalize_trace_id(kwargs.get("trace_id"))
        if incoming_trace_id:
            set_trace_id(incoming_trace_id)

        self.websocket = websocket
        self.session_id = session_id

        # Hook for subclass-specific setup
        await self._on_connection_established(**kwargs)

        # Accept connection
        await self.manager.connect(websocket, self.scenario, session_id)

        # Initialize message queue
        self.message_queue = asyncio.Queue(maxsize=self.MAX_MESSAGE_QUEUE_SIZE)
        self.running = True

        # Start message processing task
        processing_task = asyncio.create_task(self._process_messages())

        await self._sync_session_state()

        # Send initial status from persisted session lifecycle state
        initial_ai_state = "listening" if self.session_status == "in_progress" else "idle"
        await self._send_status(initial_ai_state)

        # Only greet when session is actively running
        if self.session_status == "in_progress":
            asyncio.create_task(self._send_delayed_greeting())

        try:
            while self.running:
                try:
                    # v1-13: Accept both text (JSON) and binary WebSocket frames
                    raw = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=30.0,
                    )
                    if "text" in raw:
                        data = json.loads(raw["text"])
                        try:
                            self.message_queue.put_nowait(data)
                        except asyncio.QueueFull:
                            logger.warning(
                                "Message queue overflow, dropping message: session=%s type=%s",
                                session_id,
                                data.get("type"),
                            )
                            await self._send_error(
                                "[WS_QUEUE_OVERFLOW]",
                                "当前请求过于频繁，请稍后重试",
                            )
                    elif "bytes" in raw:
                        await self._handle_binary_frame(raw["bytes"])
                except TimeoutError:
                    await self._send_heartbeat()

        except WebSocketDisconnect:
            logger.info(f"Sales WebSocket disconnected: session={session_id}")
        except asyncio.CancelledError:
            logger.info(f"Sales WebSocket cancelled: session={session_id}")
            raise
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Sales WebSocket error: {str(e)}")
        finally:
            self.running = False
            await self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()
            with suppress(asyncio.CancelledError):
                await processing_task
            if self._response_task and not self._response_task.done():
                self._response_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._response_task
            await self._on_connection_closed()

    async def _on_connection_established(self, **kwargs):
        """Hook for subclass-specific setup after connection params are set."""
        pass

    async def _on_connection_closed(self):
        """Hook for subclass-specific cleanup on disconnect."""
        if not self.session_id:
            return

        if self.session_status in {"completed", "scoring"}:
            result = await self.state_service.delete_state(self.session_id)
            if not result.is_success:
                logger.warning(
                    "Failed to cleanup terminal session state",
                    session_id=self.session_id,
                    fallback=result.fallback,
                )

    async def _sync_session_state(self):
        """Load current persisted session lifecycle state."""
        if not self.session_id:
            return

        try:
            async with AsyncSessionLocal() as db:
                lifecycle_service = SessionLifecycleService(db)
                session, scenario_type = await lifecycle_service.get_session_with_scenario(self.session_id)
                if session:
                    self.session_status = str(session.status or "preparing")
                    self.session_scenario_type = scenario_type or self.scenario
                    snapshot = getattr(session, "voice_policy_snapshot", None)
                    if isinstance(snapshot, dict):
                        self._voice_policy_snapshot = snapshot
                    else:
                        self._voice_policy_snapshot = {}
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(f"Failed to sync session lifecycle state: {exc}")

    async def _apply_lifecycle_action(self, action: str):
        """Apply one lifecycle action through DB state machine."""
        if not self.session_id:
            return None

        try:
            async with AsyncSessionLocal() as db:
                lifecycle_service = SessionLifecycleService(db)
                session, scenario_type = await lifecycle_service.get_session_with_scenario(self.session_id)
                if not session:
                    await self._send_error("[SESSION_NOT_FOUND]", "会话不存在")
                    return None

                self.session_scenario_type = scenario_type or self.scenario

                try:
                    transition = await lifecycle_service.transition(
                        session=session,
                        scenario_type=self.session_scenario_type,
                        action=action,
                    )
                except InvalidSessionTransitionError as exc:
                    await db.rollback()
                    self.session_status = str(session.status or self.session_status)
                    await self._send_error("[INVALID_SESSION_TRANSITION]", exc.message)
                    await self._send_status("idle" if self.session_status != "in_progress" else "listening")
                    return None

                await db.commit()
                await lifecycle_service.trigger_report_generation_if_needed(transition)
                self.session_status = transition.to_status
                return transition
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error(f"Failed to apply lifecycle action {action}: {exc}")
            await self._send_error("[SESSION_LIFECYCLE_FAILED]", "会话状态更新失败")
            return None

    async def _ensure_input_allowed(self, msg_type: str) -> bool:
        if SessionLifecycleService.is_input_allowed(self.session_status):
            return True

        if self.session_status == "paused":
            code = "[SESSION_PAUSED]"
            message = f"当前会话已暂停，拒绝 {msg_type}"
        elif self.session_status == "preparing":
            code = "[SESSION_NOT_STARTED]"
            message = f"会话尚未开始，拒绝 {msg_type}"
        else:
            code = "[SESSION_NOT_ACTIVE]"
            message = f"会话状态为 {self.session_status}，拒绝 {msg_type}"

        await self._send_error(code, message)
        await self._send_status("idle")
        return False

    async def _send_delayed_greeting(self):
        """Send greeting after a short delay to ensure client is ready."""
        if self._greeting_sent:
            return
        await asyncio.sleep(0.5)
        if self._greeting_sent or self.session_status != "in_progress":
            return
        self._greeting_sent = True
        await self._send_greeting()

    async def sync_lifecycle_transition(self, transition) -> None:
        """Mirror REST lifecycle transitions into the live handler state."""
        await super().sync_lifecycle_transition(transition)
        self.session_scenario_type = transition.scenario_type or self.scenario

        if transition.action == "start" and not self._greeting_sent and self.websocket:
            asyncio.create_task(self._send_delayed_greeting())

        if transition.action in {"pause", "end"}:
            await self._stop_streaming_asr()

    async def _process_messages(self):
        """Process messages from queue."""
        while self.running:
            try:
                message = await self.message_queue.get()
                await self.handle_message(message)
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Message processing error: {str(e)}")

    # ========== Message Routing ==========

    async def handle_message(self, message: dict):
        """Handle incoming WebSocket message."""
        msg_type = message.get("type")
        data = message.get("data", {})

        if self.session_id:
            await get_session_manager().update_activity(self.session_id)

        logger.debug(f"Sales handler received message type: {msg_type}")

        try:
            if msg_type == "audio_chunk":
                if not await self._ensure_input_allowed("audio_chunk"):
                    return
                await self._handle_audio_chunk(data)

            elif msg_type == "audio_end":
                if not await self._ensure_input_allowed("audio_end"):
                    return
                await self._handle_audio_end()

            elif msg_type == "user_speaking":
                speaking = data.get("speaking", False)
                if speaking:
                    if not await self._ensure_input_allowed("user_speaking"):
                        return
                    await self._start_streaming_asr()
                else:
                    if SessionLifecycleService.is_input_allowed(self.session_status):
                        await self._handle_audio_end()

            elif msg_type == "text":
                text = self._extract_text_payload(data)
                if text:
                    if not await self._ensure_input_allowed("text"):
                        return
                    await self._launch_response_task(text, source="text")

            elif msg_type == "interrupt":
                reason = data.get("reason", "manual")
                await self._handle_interrupt(reason)

            elif msg_type == "control":
                action = data.get("action", "")
                if action == "start":
                    transition = await self._apply_lifecycle_action("start")
                    if transition:
                        await self._send_status("listening")
                        if not self._greeting_sent:
                            asyncio.create_task(self._send_delayed_greeting())
                elif action == "end":
                    transition = await self._apply_lifecycle_action("end")
                    if transition:
                        await self._handle_session_end()
                elif action == "pause":
                    transition = await self._apply_lifecycle_action("pause")
                    if transition:
                        await self._stop_streaming_asr()
                        await self._send_status("idle")
                elif action == "resume":
                    transition = await self._apply_lifecycle_action("resume")
                    if transition:
                        await self._send_status("listening")
                else:
                    logger.warning(f"Unknown control action: {action}")

            elif msg_type == "pause":
                transition = await self._apply_lifecycle_action("pause")
                if transition:
                    await self._stop_streaming_asr()
                    await self._send_status("idle")

            elif msg_type == "resume":
                transition = await self._apply_lifecycle_action("resume")
                if transition:
                    await self._send_status("listening")

            elif msg_type == "heartbeat_ack":
                pass

            elif msg_type == "negotiate":
                self._client_runtime_options = data if isinstance(data, dict) else {}
                await self.manager.send_json(
                    self.websocket,
                    {
                        "type": "negotiate_ack",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "trace_id": get_trace_id(),
                        "data": {
                            "accepted": True,
                            "prefer_binary": bool(
                                self._client_runtime_options.get("prefer_binary", False)
                            ),
                        },
                    },
                )

            else:
                await self._handle_custom_message(msg_type, data, message)

        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Error handling message {msg_type}: {str(e)}")
            await self._send_error("[PROCESSING_ERROR]", "处理消息时出错")

    async def _handle_custom_message(self, msg_type: str, data: dict, message: dict):
        """Override in subclasses to handle additional message types."""
        logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_session_end(self):
        """Handle session end request from client.

        Stops ASR, sends session_ended confirmation, and closes the WebSocket.
        Subclasses can override to add capability cleanup, report generation, etc.
        """
        logger.info(f"Session end requested: session_id={self.session_id}")

        # Stop any ongoing ASR
        await self._stop_streaming_asr()

        # Send session_ended confirmation so frontend knows it's safe to navigate
        await self.manager.send_json(self.websocket, {
            "type": "session_ended",
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": get_trace_id(),
            "data": {
                "session_id": self.session_id,
                "turn_count": self.turn_count,
                "session_status": self.session_status,
            },
        })

        # Stop the message processing loop — this will trigger cleanup in handle_connection
        self.running = False

    async def _handle_interrupt(self, reason: str = "manual"):
        """Handle interrupt request and notify client with stable event envelope."""
        logger.info(f"Interrupt received: session_id={self.session_id}, reason={reason}")

        interrupted_stream_id = self.current_stream_id
        await self._stop_streaming_asr()

        await self.manager.send_json(
            self.websocket,
            {
                "type": "interrupted",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "stream_id": interrupted_stream_id,
                "data": {
                    "reason": reason,
                    "session_status": self.session_status,
                    "ai_state": "listening" if self.session_status == "in_progress" else "idle",
                    "turn_count": self.turn_count,
                },
            },
        )

        self.current_stream_id = None
        await self._send_status("listening" if self.session_status == "in_progress" else "idle")

    @staticmethod
    def _extract_text_payload(data: dict) -> str:
        """
        Extract text payload from websocket data.

        Contract baseline is `data.text`; `data.content` is kept as legacy fallback
        to avoid breaking older clients during rollout.
        """
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text

        legacy_text = data.get("content")
        if isinstance(legacy_text, str) and legacy_text.strip():
            return legacy_text

        return ""

    # ========== Audio / ASR Pipeline ==========

    # ── v1-13: Binary frame handling ──

    # Binary frame type constants
    BINARY_AUDIO_CHUNK = 0x01
    BINARY_AUDIO_INTERRUPT = 0x02

    async def _handle_binary_frame(self, data: bytes):
        """
        Handle a binary WebSocket frame (v1-13).

        Protocol:
          Byte 0: Message type (0x01 = audio_chunk, 0x02 = audio_chunk + interrupt)
          Bytes 1+: Raw PCM Int16 LE audio data (16 kHz mono)

        Skips Base64 encoding/decoding entirely → ~33% bandwidth reduction.
        """
        if len(data) < 2:
            logger.warning(f"Binary frame too short: {len(data)} bytes")
            return

        frame_type = data[0]
        audio_bytes = data[1:]

        if frame_type == self.BINARY_AUDIO_INTERRUPT:
            await self._handle_interrupt("user_speaking")
            return

        if frame_type == self.BINARY_AUDIO_CHUNK:
            if not await self._ensure_input_allowed("audio_chunk_binary"):
                return
            await self._enqueue_audio_bytes(audio_bytes)
        else:
            logger.warning(f"Unknown binary frame type: 0x{frame_type:02x}")

    async def _enqueue_audio_bytes(self, audio_bytes: bytes):
        """Enqueue raw PCM audio bytes to the ASR pipeline (shared by binary & JSON paths)."""
        if not audio_bytes:
            return

        need_start = False
        async with self._state_lock:
            if self.asr_queue is None:
                need_start = True

        if need_start:
            logger.info("Auto-starting ASR on first audio chunk")
            await self._start_streaming_asr()

        backpressure_action: str | None = None
        queue_size = 0
        dropped_for_overflow = False
        async with self._state_lock:
            queue = self.asr_queue
            if queue is None:
                logger.warning("Dropping audio chunk: ASR queue unavailable")
                return

            queue_size = queue.qsize()
            if queue_size >= self.ASR_QUEUE_MAX_SIZE:
                dropped_for_overflow = True
            else:
                try:
                    queue.put_nowait(audio_bytes)
                    self.audio_buffer_size += len(audio_bytes)
                    queue_size = queue.qsize()
                except asyncio.QueueFull:
                    dropped_for_overflow = True
                    queue_size = self.ASR_QUEUE_MAX_SIZE

            if queue_size >= self.ASR_HIGH_WATERMARK and not self._backpressure_active:
                self._backpressure_active = True
                backpressure_action = "slow_down"
            elif queue_size <= self.ASR_LOW_WATERMARK and self._backpressure_active:
                self._backpressure_active = False
                backpressure_action = "resume"

        if dropped_for_overflow:
            logger.warning(f"[BACKPRESSURE] Queue full ({queue_size}), dropping audio chunk")
            await self._send_audio_drop_notice(queue_size=queue_size, dropped_chunks=1)

        if backpressure_action is not None:
            await self._send_backpressure(backpressure_action, queue_size)

    async def _handle_audio_chunk(self, data: dict):
        """Handle JSON audio_chunk message (legacy Base64 path, kept for backward compatibility)."""
        audio_base64 = data.get("audio", "")
        interrupt = data.get("interrupt", False)

        if interrupt:
            await self._handle_interrupt("user_speaking")
            return

        if audio_base64:
            try:
                audio_bytes = base64.b64decode(audio_base64)
                await self._enqueue_audio_bytes(audio_bytes)
            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Failed to decode audio: {e}")

    async def _start_streaming_asr(self):
        """Start streaming ASR session."""
        # 停止之前的 ASR 任务（如果有）
        await self._stop_streaming_asr()

        async with self._state_lock:
            self.is_user_speaking = True
            self.current_transcript = ""
            self.audio_buffer_size = 0  # 重置音频大小计数
            self.asr_queue = asyncio.Queue(maxsize=self.ASR_QUEUE_MAX_SIZE)

            # 启动 ASR 处理任务
            self.asr_task = asyncio.create_task(self._run_streaming_asr())

        await self._send_status("listening")
        logger.info("Started streaming ASR session")

    async def _stop_streaming_asr(self):
        """Stop streaming ASR session and process the result."""
        # 使用状态锁防止并发调用导致的竞争条件
        should_send_resume = False
        async with self._state_lock:
            # 防止重复调用
            if not self.is_user_speaking and self.asr_task is None and self.asr_queue is None:
                logger.debug("Ignoring _stop_streaming_asr - already stopped")
                return

            logger.info(f"_stop_streaming_asr called: is_user_speaking={self.is_user_speaking}, has_task={self.asr_task is not None}")
            self.is_user_speaking = False

            # 检查音频是否太短
            if self.audio_buffer_size < self.MIN_AUDIO_SIZE:
                logger.warning(f"Audio too short: {self.audio_buffer_size} bytes, minimum: {self.MIN_AUDIO_SIZE}")
                self.asr_task = None
                self.asr_queue = None
                self.audio_buffer_size = 0
                if self._backpressure_active:
                    self._backpressure_active = False
                    should_send_resume = True
                final_transcript = ""
            else:
                if self.asr_queue:
                    # 发送结束标记；若队列已满则腾挪一个最旧块后再放入终止标记
                    try:
                        self.asr_queue.put_nowait(None)
                    except asyncio.QueueFull:
                        with suppress(asyncio.QueueEmpty):
                            self.asr_queue.get_nowait()
                        with suppress(asyncio.QueueFull):
                            self.asr_queue.put_nowait(None)

                if self.asr_task and not self.asr_task.done():
                    try:
                        # 等待 ASR 任务完成（最多 5 秒）
                        await asyncio.wait_for(self.asr_task, timeout=5.0)
                    except TimeoutError:
                        logger.warning("ASR task timeout, cancelling")
                        self.asr_task.cancel()
                    except asyncio.CancelledError:
                        raise
                    except (RuntimeError, ValueError, OSError) as e:
                        logger.error(f"Error waiting for ASR task: {e}")

                # 保存当前转录结果并立即清空，防止重复处理
                final_transcript = self.current_transcript
                self.current_transcript = ""  # 清空，防止重复处理

                # 清理状态
                self.asr_task = None
                self.asr_queue = None
                self.audio_buffer_size = 0
                if self._backpressure_active:
                    self._backpressure_active = False
                    should_send_resume = True

        if should_send_resume:
            await self._send_backpressure("resume", 0)

        # ASR 完成后，处理 LLM 响应（在锁外执行，避免长时间持有锁）
        # CRITICAL FIX: Fire-and-forget to keep message loop responsive.
        # Previously, _process_user_text blocked the loop for 5-10s (LLM+TTS),
        # causing subsequent recording messages to pile up and ASR to only produce "嗯".
        if final_transcript and len(final_transcript.strip()) > 0:
            logger.info(f"Processing transcript (non-blocking): {final_transcript[:30]}...")
            await self._launch_response_task(final_transcript, source="asr_final")
        else:
            logger.info("No transcript to process")
            await self._send_status("listening")

    async def _run_streaming_asr(self):
        """Run streaming ASR and process results."""
        asr_service = get_asr_service()
        total_bytes = 0

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

        try:
            # 流式处理 ASR，FunASR 流式模型会返回累积文本
            async for result in asr_service.stream_transcribe(audio_generator()):
                if result.is_success and result.value:
                    self.current_transcript = result.value
                    await self._send_transcript(result.value, is_final=False)
                    logger.debug(f"ASR interim: {result.value}")

            # ASR 完成，发送最终结果
            if self.current_transcript and len(self.current_transcript.strip()) > 0:
                logger.info(f"ASR final: {self.current_transcript}")
                await self._send_transcript(self.current_transcript, is_final=True)
            else:
                logger.warning("ASR returned empty transcript")

        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Streaming ASR error: {e}", exc_info=True)

    async def _handle_audio_end(self):
        """Handle audio end signal - trigger ASR commit."""
        if self.asr_task is None or self.asr_task.done():
            logger.debug("Ignoring audio_end - no active ASR task")
            return
        logger.info("Audio end received, stopping ASR stream")
        await self._stop_streaming_asr()

    # ========== Text Processing (override in subclasses for enhanced behavior) ==========

    async def _process_user_text(self, text: str):
        """
        Process user text: generate LLM response and TTS.
        Override in subclasses for capability integration, DB storage, etc.
        """
        # Critical Fix #2: 递增请求ID
        self.current_request_id += 1
        current_req_id = self.current_request_id
        logger.info(f"[REQUEST {current_req_id}] Processing user text: {text[:50]}...")

        # 去重检查
        if self._is_duplicate_text(text):
            return

        # Add to conversation history with size limit
        self.conversation_history.append({"role": "user", "content": text})
        if len(self.conversation_history) > self.MAX_CONVERSATION_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_CONVERSATION_HISTORY:]

        await self._send_status("thinking")

        # Apply KB lock decision before LLM generation.
        response_text: str | None = None
        knowledge_context = ""
        kb_lock_decision = await evaluate_kb_lock_decision(
            query=text,
            effective_policy=self._voice_policy_snapshot,
        )
        if kb_lock_decision.lock_required and not kb_lock_decision.allow_generation:
            response_text = kb_lock_decision.user_message
        elif kb_lock_decision.lock_required:
            knowledge_context = kb_lock_decision.grounding_context

        if response_text is None:
            response_text = await self._generate_response(
                text,
                knowledge_context=knowledge_context,
            )

        logger.info(f"LLM response generated: {response_text[:50] if response_text else 'None'}...")

        if response_text:
            self.conversation_history.append({"role": "assistant", "content": response_text})
            self.turn_count += 1

            # Critical Fix #2: 为这个TTS流生成新的stream_id
            self.current_stream_id = str(self.uuid.uuid4())
            logger.info(f"[REQUEST {current_req_id}] Starting TTS with stream_id={self.current_stream_id}")
            await self._send_tts_response(response_text, current_req_id)
        else:
            fallback = self._get_fallback_response()
            logger.info(f"Using fallback response: {fallback}")
            self.conversation_history.append({"role": "assistant", "content": fallback})

            self.current_stream_id = str(self.uuid.uuid4())
            await self._send_tts_response(fallback, current_req_id)

            await self._send_status("listening")

    async def _launch_response_task(self, text: str, source: str) -> bool:
        """Launch one background response task; reject parallel pipelines."""
        async with self._response_task_lock:
            if self._response_task and not self._response_task.done():
                logger.warning(
                    f"Rejecting concurrent response task from {source}: pipeline busy"
                )
                await self._send_error(
                    "[RESPONSE_BUSY]",
                    "系统正在处理上一轮回复，请稍后再试。",
                )
                return False

            self._response_task = asyncio.create_task(self._process_user_text_safe(text))
            return True

    async def _process_user_text_safe(self, text: str):
        """Background wrapper for _process_user_text to avoid unhandled task exceptions."""
        try:
            await self._process_user_text(text)
        except asyncio.CancelledError:
            logger.info("Background response task cancelled")
            raise
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Background response task error: {e}", exc_info=True)
            await self._send_status("listening")
        finally:
            current_task = asyncio.current_task()
            async with self._response_task_lock:
                if self._response_task is current_task:
                    self._response_task = None

    def _is_duplicate_text(self, text: str) -> bool:
        """Check if text is a duplicate of the last user message."""
        current_time = time.time()
        text_normalized = text.strip().lower()

        if (text_normalized == self.last_user_text.strip().lower() and
            current_time - self.last_user_text_time < self.DUPLICATE_THRESHOLD):
            logger.warning(f"Duplicate message detected, ignoring: {text[:30]}...")
            return True

        # 相似度检查
        if self.last_user_text and self._is_similar_text(text_normalized, self.last_user_text.strip().lower()):
            if current_time - self.last_user_text_time < self.DUPLICATE_THRESHOLD:
                logger.warning(f"Similar message detected, ignoring: {text[:30]}...")
                return True

        # 更新去重状态
        self.last_user_text = text
        self.last_user_text_time = current_time
        return False

    def _is_similar_text(self, text1: str, text2: str) -> bool:
        """Check if two texts are similar (simple similarity check)."""
        if not text1 or not text2:
            return False

        if text1 == text2:
            return True

        # 一个是另一个的子串
        if text1 in text2 or text2 in text1:
            len_diff = abs(len(text1) - len(text2))
            min_len = min(len(text1), len(text2))
            if min_len > 0 and len_diff / min_len < 0.3:
                return True

        # 简单的字符重叠率检查
        set1 = set(text1)
        set2 = set(text2)
        overlap = len(set1 & set2)
        total = len(set1 | set2)
        if total > 0 and overlap / total > 0.8:
            return True

        return False

    # ========== Abstract methods (must be overridden) ==========

    async def _generate_response(self, text: str, **kwargs) -> str | None:
        """Generate LLM response. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _generate_response")

    def _get_fallback_response(self) -> str:
        """Get fallback response. Override in subclasses."""
        return "请继续。"

    async def _send_greeting(self):
        """Send persona greeting. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _send_greeting")

    # ========== WebSocket Message Senders ==========

    async def _send_transcript(self, text: str, is_final: bool):
        """Send ASR transcript to client."""
        await self.manager.send_json(self.websocket, {
            "type": "asr_transcript",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "text": text,
                "is_final": is_final,
                "confidence": 0.95,
            }
        })

    async def _send_tts_response(self, text: str, request_id: int):
        """
        Send TTS audio response to client.
        Override in subclasses for streaming TTS or custom TTS config.

        Critical Fix #2: 添加stream_id和request_id防止消息乱序
        """
        from common.audio.tts_service import get_tts_service
        tts_service = get_tts_service()

        try:
            result = await tts_service.synthesize(text)

            if result.is_success:
                audio_chunks = []
                async for chunk in result.value:
                    audio_chunks.append(chunk)

                audio_data = b"".join(audio_chunks)
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                sample_rate_hz, bytes_per_sample, channels = resolve_pcm_audio_format(
                    self._client_runtime_options.get("tts_audio_format")
                )
                duration_ms = (
                    calculate_pcm_duration_ms(
                        audio_data,
                        sample_rate_hz=sample_rate_hz,
                        bytes_per_sample=bytes_per_sample,
                        channels=channels,
                    )
                    if audio_data
                    else len(text) * 100
                )

                logger.info(f"TTS generated {len(audio_data)} bytes for: {text[:30]}...")

                await self.manager.send_json(self.websocket, {
                    "type": "tts_audio",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "stream_id": self.current_stream_id,
                    "request_id": request_id,
                    "data": {
                        "text": text,
                        "audio": audio_base64,
                        "duration_ms": duration_ms,
                    }
                })
            else:
                logger.warning(f"TTS failed: {result.fallback}")
                await self._send_tts_fallback(text, request_id)

        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"TTS error: {str(e)}", exc_info=True)
            await self._send_tts_fallback(text, request_id)

    async def _send_tts_fallback(self, text: str, request_id: int):
        """Send text-only TTS fallback for browser TTS."""
        await self.manager.send_json(self.websocket, {
            "type": "tts_audio",
            "timestamp": datetime.now(UTC).isoformat(),
            "stream_id": self.current_stream_id,
            "request_id": request_id,
            "data": {
                "text": text,
                "audio": "",
                "duration_ms": len(text) * 100,
                "fallback": "browser_tts",
            }
        })

    async def _send_status(self, ai_state: str):
        """Send status update to client."""
        self.ai_state = ai_state
        await self.manager.send_json(self.websocket, {
            "type": "status",
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": get_trace_id(),
            "data": {
                "session_status": self.session_status,
                "ai_state": ai_state,
                "turn_count": self.turn_count,
            }
        })

    async def _send_heartbeat(self):
        """Send heartbeat to client."""
        await self.manager.send_json(self.websocket, {
            "type": "heartbeat",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {},
        })

    async def _send_error(self, code: str, message: str):
        """Send error to client."""
        await self.manager.send_json(self.websocket, {
            "type": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": get_trace_id(),
            "data": {
                "code": code,
                "message": message,
                "user_action": "请重试",
                "session_status": self.session_status,
                "ai_state": self.ai_state,
                "turn_count": self.turn_count,
            }
        })

    async def _send_backpressure(self, action: str, queue_size: int):
        """Send backpressure signal to client."""
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": get_trace_id(),
            "data": {
                "action": action,
                "queue_size": queue_size,
                "high_watermark": self.ASR_HIGH_WATERMARK,
                "low_watermark": self.ASR_LOW_WATERMARK,
            },
        }
        await self.manager.send_json(
            self.websocket,
            {
                "type": "backpressure",
                **payload,
            },
        )
        # Legacy alias for old clients during transition window.
        await self.manager.send_json(
            self.websocket,
            {
                "type": "system_backpressure",
                **payload,
            },
        )

    async def _send_audio_drop_notice(self, queue_size: int, dropped_chunks: int):
        """Notify client when audio chunk is dropped due to queue overflow."""
        await self.manager.send_json(
            self.websocket,
            {
                "type": "audio_drop_notice",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": get_trace_id(),
                "data": {
                    "reason": "queue_overflow",
                    "queue_size": queue_size,
                    "dropped_chunks": dropped_chunks,
                },
            },
        )

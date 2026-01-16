"""
Simple Sales Bot WebSocket Handler
Full implementation for sales practice sessions with ASR + LLM + TTS

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors handled gracefully
- II. Real-time priority - <300ms end-to-end latency
"""
import asyncio
import base64
import time
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from common.ai.llm_service import get_llm_service
from common.audio.asr_service import get_asr_service
from common.audio.tts_service import get_tts_service
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from common.websocket.base_handler import BaseWebSocketHandler

logger = get_logger(__name__)


# Default persona configurations (fallback when database is unavailable)
# 提示词规范参考: docs/prompt-guidelines.md
DEFAULT_PERSONA_CONFIG = {
    "impatient_ceo": {
        "name": "急躁的CEO",
        "greeting": "好，我只有5分钟时间。直接告诉我你们能为我解决什么问题。",
        "system_prompt": """你是一个急躁的CEO，正在与销售人员对话。

【角色特点】
- 时间宝贵，没耐心听废话
- 只关心：能解决什么问题？带来多少收益？
- 常用语："说重点！"、"我没时间"、"所以呢？"

【回复规范】
- 每次回复不超过30字
- 语气直接、不客气
- 如果对方啰嗦，直接打断

【禁止】
- 不要长篇分析
- 不要给建议
- 不要解释你是AI"""
    },
    "skeptical_buyer": {
        "name": "怀疑的采购",
        "greeting": "你好，我听说过你们公司。不过说实话，我对市面上的解决方案都持保留态度。你能给我一些具体的案例吗？",
        "system_prompt": """你是一个怀疑一切的采购经理，正在与销售人员对话。

【角色特点】
- 对任何承诺都持怀疑态度
- 需要证据、案例、数据才会相信
- 常用语："有数据吗？"、"能证明吗？"、"听起来太好了"

【回复规范】
- 每次回复不超过40字
- 语气质疑但礼貌
- 不断追问细节和证据

【禁止】
- 不要轻易认可对方
- 不要长篇大论
- 不要跳出角色"""
    },
    "price_focused": {
        "name": "价格敏感型",
        "greeting": "你好，我对你们的产品有些兴趣。不过在我们深入讨论之前，能先告诉我大概的价格范围吗？",
        "system_prompt": """你是一个非常关注价格的采购经理，正在与销售人员对话。

【角色特点】
- 只关心价格，总想要折扣
- 对价值不感兴趣，只看价格
- 常用语："太贵了"、"别家更便宜"、"能打几折？"

【回复规范】
- 每次回复不超过30字
- 语气精明、会砍价
- 不断压价、要优惠

【禁止】
- 不要被价值说服
- 不要长篇分析
- 不要跳出角色"""
    },
    "technical_cto": {
        "name": "技术型CTO",
        "greeting": "好的，让我们跳过那些营销话术。你们的技术栈是什么？",
        "system_prompt": """你是一个技术背景很强的CTO，正在与销售人员对话。

【角色特点】
- 只关心技术细节，讨厌营销话术
- 会问架构、安全性、可扩展性
- 常用语："具体怎么实现？"、"用什么技术栈？"、"性能指标是多少？"

【回复规范】
- 每次回复不超过40字
- 语气专业、直接
- 追问技术细节

【禁止】
- 不要接受模糊回答
- 不要长篇大论
- 不要跳出角色"""
    },
}


async def get_persona_from_db(persona_id: str) -> dict | None:
    """Load persona configuration from database."""
    try:
        # Import here to avoid circular imports
        from agent.models import Persona

        async with AsyncSessionLocal() as db:
            stmt = select(Persona).where(Persona.id == persona_id)
            result = await db.execute(stmt)
            persona = result.scalar_one_or_none()

            if persona:
                # Build greeting from behavior_config or use default
                behavior = persona.behavior_config or {}
                typical_questions = behavior.get("typical_questions", [])
                greeting = typical_questions[0] if typical_questions else f"你好，我是{persona.name}。"

                return {
                    "name": persona.name,
                    "greeting": greeting,
                    "system_prompt": persona.system_prompt,
                    "traits": persona.traits or {},
                    "behavior_config": behavior,
                }
    except Exception as e:
        logger.warning(f"Failed to load persona from database: {e}")

    return None


class SimpleSalesHandler(BaseWebSocketHandler):
    """
    Full WebSocket handler for sales practice
    Implements: Audio → ASR → LLM → TTS → Audio
    """

    # 会话历史最大长度，防止内存泄漏
    MAX_CONVERSATION_HISTORY = 50

    def __init__(self):
        super().__init__("sales")
        self.persona_id: str | None = None
        self.persona_config: dict | None = None
        self.turn_count = 0
        self.websocket: WebSocket | None = None
        self.session_id: str | None = None
        self.conversation_history: list[dict] = []
        self.audio_buffer: bytes = b""
        self.audio_buffer_size: int = 0  # 跟踪音频大小
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
        import uuid
        self.uuid = uuid  # 保存uuid模块引用

    async def _load_persona_config(self, persona_id: str | None) -> dict:
        """Load persona configuration from database or use default."""
        # Try to load from database first
        if persona_id:
            db_config = await get_persona_from_db(persona_id)
            if db_config:
                logger.info(f"Loaded persona from database: {persona_id}")
                return db_config

        # Fallback to default config
        default_key = "impatient_ceo"
        logger.info(f"Using default persona: {default_key}")
        return DEFAULT_PERSONA_CONFIG[default_key]

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        persona_id: str | None = None
    ):
        """Handle WebSocket connection for sales practice"""
        self.websocket = websocket
        self.session_id = session_id
        self.persona_id = persona_id

        # Load persona configuration
        self.persona_config = await self._load_persona_config(persona_id)

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
        asyncio.create_task(self._send_delayed_greeting())

        try:
            # Receive messages loop
            while self.running:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=30.0
                    )
                    await self.message_queue.put(data)
                except TimeoutError:
                    # Send heartbeat
                    await self._send_heartbeat()

        except WebSocketDisconnect:
            logger.info(f"Sales WebSocket disconnected: session={session_id}")
        except Exception as e:
            logger.error(f"Sales WebSocket error: {str(e)}")
        finally:
            self.running = False
            self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()

    async def _send_delayed_greeting(self):
        """Send greeting after a short delay to ensure client is ready"""
        await asyncio.sleep(0.5)
        await self._send_greeting()

    async def _process_messages(self):
        """Process messages from queue"""
        while self.running:
            try:
                message = await self.message_queue.get()
                await self.handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processing error: {str(e)}")

    async def handle_message(self, message: dict):
        """Handle incoming WebSocket message"""
        msg_type = message.get("type")
        data = message.get("data", {})

        logger.debug(f"Sales handler received message type: {msg_type}")

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
                # Handle text input directly (for testing)
                text = data.get("text", "")
                if text:
                    await self._process_user_text(text)

            elif msg_type == "pause":
                await self._send_status("idle")

            elif msg_type == "resume":
                await self._send_status("listening")

            elif msg_type == "heartbeat_ack":
                pass

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error handling message {msg_type}: {str(e)}")
            await self._send_error("[PROCESSING_ERROR]", "处理消息时出错")

    async def _handle_audio_chunk(self, data: dict):
        """Handle audio chunk - forward to streaming ASR immediately."""
        audio_base64 = data.get("audio", "")
        interrupt = data.get("interrupt", False)

        if interrupt:
            logger.info("User interrupted AI")
            await self._stop_streaming_asr()
            await self._send_status("listening")
            return

        if audio_base64:
            # 如果 ASR 还没启动，自动启动
            if not self.asr_queue:
                logger.info("Auto-starting ASR on first audio chunk")
                await self._start_streaming_asr()

            if self.asr_queue:
                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    # 跟踪音频大小
                    self.audio_buffer_size += len(audio_bytes)
                    # 直接放入队列，流式发送给 ASR
                    await self.asr_queue.put(audio_bytes)
                except Exception as e:
                    logger.error(f"Failed to decode audio: {e}")

    async def _start_streaming_asr(self):
        """Start streaming ASR session."""
        # 停止之前的 ASR 任务（如果有）
        await self._stop_streaming_asr()

        async with self._state_lock:
            self.is_user_speaking = True
            self.current_transcript = ""
            self.audio_buffer_size = 0  # 重置音频大小计数
            self.asr_queue = asyncio.Queue()

            # 启动 ASR 处理任务
            self.asr_task = asyncio.create_task(self._run_streaming_asr())

        await self._send_status("listening")
        logger.info("Started streaming ASR session")

    async def _stop_streaming_asr(self):
        """Stop streaming ASR session and process the result."""
        # 使用状态锁防止并发调用导致的竞争条件
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
                await self._send_status("listening")
                return

            if self.asr_queue:
                # 发送结束标记
                await self.asr_queue.put(None)

            if self.asr_task and not self.asr_task.done():
                try:
                    # 等待 ASR 任务完成（最多 5 秒）
                    await asyncio.wait_for(self.asr_task, timeout=5.0)
                except TimeoutError:
                    logger.warning("ASR task timeout, cancelling")
                    self.asr_task.cancel()
                except Exception as e:
                    logger.error(f"Error waiting for ASR task: {e}")

            # 保存当前转录结果并立即清空，防止重复处理
            final_transcript = self.current_transcript
            self.current_transcript = ""  # 清空，防止重复处理

            # 清理状态
            self.asr_task = None
            self.asr_queue = None
            self.audio_buffer_size = 0

        # ASR 完成后，处理 LLM 响应（在锁外执行，避免长时间持有锁）
        if final_transcript and len(final_transcript.strip()) > 0:
            logger.info(f"Processing transcript: {final_transcript[:30]}...")
            await self._process_user_text(final_transcript)
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
            # 每次返回的是从开始到当前的完整文本，不是增量
            async for result in asr_service.stream_transcribe(audio_generator()):
                if result.is_success and result.value:
                    # FunASR 流式模型返回累积文本，直接使用
                    self.current_transcript = result.value
                    # 发送中间结果给前端
                    await self._send_transcript(result.value, is_final=False)
                    logger.debug(f"ASR interim: {result.value}")

            # ASR 完成，发送最终结果
            if self.current_transcript and len(self.current_transcript.strip()) > 0:
                logger.info(f"ASR final: {self.current_transcript}")
                await self._send_transcript(self.current_transcript, is_final=True)
            else:
                logger.warning("ASR returned empty transcript")

        except Exception as e:
            logger.error(f"Streaming ASR error: {e}", exc_info=True)

    async def _handle_audio_end(self):
        """Handle audio end signal - trigger ASR commit."""
        # 只有在有活跃的 ASR 任务时才处理
        if self.asr_task is None or self.asr_task.done():
            logger.debug("Ignoring audio_end - no active ASR task")
            return
        logger.info("Audio end received, stopping ASR stream")
        await self._stop_streaming_asr()

    async def _process_user_text(self, text: str):
        """Process user text: generate LLM response and TTS"""

        # Critical Fix #2: 递增请求ID
        self.current_request_id += 1
        current_req_id = self.current_request_id
        logger.info(f"[REQUEST {current_req_id}] Processing user text: {text[:50]}...")

        # 去重检查：相同文本在短时间内重复发送
        current_time = time.time()
        text_normalized = text.strip().lower()

        if (text_normalized == self.last_user_text.strip().lower() and
            current_time - self.last_user_text_time < self.DUPLICATE_THRESHOLD):
            logger.warning(f"Duplicate message detected, ignoring: {text[:30]}...")
            return

        # 相似度检查：文本高度相似（可能是 ASR 略有差异）
        if self.last_user_text and self._is_similar_text(text_normalized, self.last_user_text.strip().lower()):
            if current_time - self.last_user_text_time < self.DUPLICATE_THRESHOLD:
                logger.warning(f"Similar message detected, ignoring: {text[:30]}...")
                return

        # 更新去重状态
        self.last_user_text = text
        self.last_user_text_time = current_time

        logger.info(f"Processing user text: {text[:50]}...")

        # Add to conversation history with size limit to prevent memory leak
        self.conversation_history.append({
            "role": "user",
            "content": text
        })
        if len(self.conversation_history) > self.MAX_CONVERSATION_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_CONVERSATION_HISTORY:]

        # Update status
        await self._send_status("thinking")

        # Generate LLM response
        response_text = await self._generate_response(text)

        logger.info(f"LLM response generated: {response_text[:50] if response_text else 'None'}...")

        if response_text:
            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })

            self.turn_count += 1

            # Send TTS response
            # Critical Fix #2: 为这个TTS流生成新的stream_id
            self.current_stream_id = str(self.uuid.uuid4())
            logger.info(f"[REQUEST {current_req_id}] Starting TTS with stream_id={self.current_stream_id}")
            logger.info(f"Sending TTS response for: {response_text[:30]}...")
            await self._send_tts_response(response_text, current_req_id)
        else:
            # Fallback response
            fallback = self._get_fallback_response()
            logger.info(f"Using fallback response: {fallback}")

            self.conversation_history.append({
                "role": "assistant",
                "content": fallback
            })

            # Critical Fix #2: 为fallback也生成stream_id
            self.current_stream_id = str(self.uuid.uuid4())
            await self._send_tts_response(fallback, current_req_id)

        # Back to listening
        await self._send_status("listening")

    def _is_similar_text(self, text1: str, text2: str) -> bool:
        """Check if two texts are similar (simple similarity check)"""
        if not text1 or not text2:
            return False

        # 完全相同
        if text1 == text2:
            return True

        # 一个是另一个的子串（ASR 可能多识别或少识别几个字）
        if text1 in text2 or text2 in text1:
            # 长度差异不大时才认为相似
            len_diff = abs(len(text1) - len(text2))
            min_len = min(len(text1), len(text2))
            if min_len > 0 and len_diff / min_len < 0.3:  # 差异小于30%
                return True

        # 简单的字符重叠率检查
        set1 = set(text1)
        set2 = set(text2)
        overlap = len(set1 & set2)
        total = len(set1 | set2)
        if total > 0 and overlap / total > 0.8:  # 80%以上字符重叠
            return True

        return False

    async def _generate_response(self, user_text: str) -> str | None:
        """Generate LLM response based on persona"""
        try:
            llm_service = get_llm_service()

            # Get system prompt from loaded persona config
            system_prompt = self.persona_config.get("system_prompt", "你是一个AI助手。")

            # Build context
            context = {
                "scenario": "sales",
                "history": self.conversation_history[-10:]  # Last 10 messages
            }

            # Generate response
            result = await llm_service.generate(
                prompt=user_text,
                session_id=self.session_id,
                system_message=system_prompt,
                context=context
            )

            if result.is_success:
                logger.info(f"LLM response: {result.value[:50]}..." if result.value else "LLM: empty response")
                return result.value
            else:
                logger.warning(f"LLM generation failed: {result.fallback}")
                return None

        except Exception as e:
            logger.error(f"LLM error: {str(e)}", exc_info=True)
            return None

    def _get_fallback_response(self) -> str:
        """Get fallback response based on persona"""
        # Use traits from persona config if available
        traits = self.persona_config.get("traits", {})
        personality = traits.get("性格", "")

        if "急躁" in personality or "impatient" in personality.lower():
            return "说重点！我没时间听这些。"
        elif "怀疑" in personality or "skeptical" in personality.lower():
            return "这听起来不太可信，你能证明吗？"
        elif "价格" in personality or "price" in personality.lower():
            return "好的，但是价格呢？"
        elif "技术" in personality or "technical" in personality.lower():
            return "说得太笼统了，具体是怎么实现的？"
        else:
            return "请继续。"

    async def _send_greeting(self):
        """Send persona greeting with TTS"""
        if self.turn_count > 0:
            return

        greeting = self.persona_config.get("greeting", "你好，请开始吧。")
        persona_name = self.persona_config.get("name", "AI助手")

        logger.info(f"Sending greeting for persona: {persona_name}")

        # Add to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": greeting
        })

        # Send as TTS
        # Critical Fix #2: greeting也需要stream_id和request_id
        self.current_request_id += 1
        self.current_stream_id = str(self.uuid.uuid4())
        await self._send_tts_response(greeting, self.current_request_id)
        self.turn_count += 1

        # Update status to listening
        await self._send_status("listening")

    async def _send_transcript(self, text: str, is_final: bool):
        """Send ASR transcript to client"""
        await self.manager.send_json(self.websocket, {
            "type": "asr_transcript",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "text": text,
                "is_final": is_final,
                "confidence": 0.95
            }
        })

    async def _send_tts_response(self, text: str, request_id: int):
        """
        Send TTS audio response to client using Edge TTS
        
        Critical Fix #2: 添加stream_id和request_id防止消息乱序
        """
        tts_service = get_tts_service()

        try:
            # Generate audio using Edge TTS
            result = await tts_service.synthesize(text)

            if result.is_success:
                # Collect all audio chunks
                audio_chunks = []
                async for chunk in result.value:
                    audio_chunks.append(chunk)

                # Combine all chunks
                audio_data = b"".join(audio_chunks)

                # Encode to base64
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")

                # Estimate duration (Edge TTS returns MP3, roughly 16kbps)
                duration_ms = int(len(audio_data) / 2) if audio_data else len(text) * 100

                logger.info(f"TTS generated {len(audio_data)} bytes for: {text[:30]}...")

                # Critical Fix #2: 添加stream_id和request_id到TTS消息
                await self.manager.send_json(self.websocket, {
                    "type": "tts_audio",
                    "timestamp": datetime.utcnow().isoformat(),
                    "stream_id": self.current_stream_id,  # 添加stream_id
                    "request_id": request_id,  # 添加request_id
                    "data": {
                        "text": text,
                        "audio": audio_base64,
                        "duration_ms": duration_ms
                    }
                })
            else:
                logger.warning(f"TTS failed: {result.fallback}")
                # Send text only with fallback flag
                await self.manager.send_json(self.websocket, {
                    "type": "tts_audio",
                    "timestamp": datetime.utcnow().isoformat(),
                    "stream_id": self.current_stream_id,  # 添加stream_id
                    "request_id": request_id,  # 添加request_id
                    "data": {
                        "text": text,
                        "audio": "",
                        "duration_ms": len(text) * 100,
                        "fallback": "browser_tts"
                    }
                })

        except Exception as e:
            logger.error(f"TTS error: {str(e)}", exc_info=True)
            await self.manager.send_json(self.websocket, {
                "type": "tts_audio",
                "timestamp": datetime.utcnow().isoformat(),
                "stream_id": self.current_stream_id,  # 添加stream_id
                "request_id": request_id,  # 添加request_id
                "data": {
                    "text": text,
                    "audio": "",
                    "duration_ms": len(text) * 100,
                    "fallback": "browser_tts"
                }
            })

    async def _send_status(self, ai_state: str):
        """Send status update to client"""
        await self.manager.send_json(self.websocket, {
            "type": "status",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "session_status": "in_progress",
                "ai_state": ai_state,
                "turn_count": self.turn_count
            }
        })

    async def _send_heartbeat(self):
        """Send heartbeat to client"""
        await self.manager.send_json(self.websocket, {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {}
        })

    async def _send_error(self, code: str, message: str):
        """Send error to client"""
        await self.manager.send_json(self.websocket, {
            "type": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "code": code,
                "message": message,
                "user_action": "请重试"
            }
        })

    async def set_persona(self, persona_id: str):
        """Set the persona for this session"""
        self.persona_id = persona_id
        self.persona_config = await self._load_persona_config(persona_id)
        logger.info(f"Set persona: {self.persona_config.get('name', persona_id)}")

    def set_bot_session(self, session_uuid):
        """Set the bot session UUID for linking with existing session"""
        self.bot_session_uuid = session_uuid
        logger.info(f"Linked to bot session: {session_uuid}")


def create_sales_handler() -> SimpleSalesHandler:
    """Create a new sales handler instance"""
    return SimpleSalesHandler()

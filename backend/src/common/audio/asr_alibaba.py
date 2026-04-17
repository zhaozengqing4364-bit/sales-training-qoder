"""
Alibaba Cloud qwen3-asr-flash-realtime ASR Provider
Constitution Principle II: Real-Time Priority - <200ms streaming latency
Constitution Principle V: Cost Control - ¥0.00033/second

Documentation:
- https://help.aliyun.com/zh/model-studio/qwen-real-time-speech-recognition
"""
import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed

from common.audio.asr_base import ASRProvider
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class AlibabaASRProvider(ASRProvider):
    """
    Alibaba Cloud real-time ASR provider

    Uses WebSocket-based real-time speech recognition API
    Cost: ¥0.00033/second
    Target latency: <200ms (Constitution Principle II)

    Features:
    - Server-side VAD (Voice Activity Detection)
    - Real-time streaming transcription
    - Automatic fallback on error
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        app_key: str | None = None,
        extra_config: dict | None = None,
    ):
        """
        Initialize Alibaba ASR provider.

        Args:
            api_key: API key (required, no fallback to avoid config confusion)
            api_url: WebSocket URL (required)
            app_key: App key / model name (optional)
            extra_config: Additional configuration options

        Note: ConfigManager handles env fallback, this class should not.
        """
        # 不再 fallback 到 settings，由 ConfigManager 统一管理
        self.api_key = api_key if api_key else ""
        base_url = api_url if api_url else "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
        model = app_key if app_key else "qwen3-asr-flash-realtime"

        # WebSocket endpoint for real-time ASR
        self.url = f"{base_url}?model={model}"
        self.sample_rate = 16000
        self.audio_format = "pcm"

        # Extra config options
        self._extra_config = extra_config or {}

    async def stream_transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000
    ) -> AsyncIterator[Result[str]]:
        """
        Stream transcribe using Alibaba Cloud WebSocket API

        使用 Manual 模式（手动断句），适合"按住说话"场景
        基于官方文档: https://help.aliyun.com/zh/model-studio/real-time-speech-recognition

        Args:
            audio_stream: Async iterator of audio bytes (PCM16, 16kHz)
            sample_rate: Audio sample rate (must be 8000 or 16000)

        Yields:
            Result with transcribed text or fallback instruction
        """
        if not self.api_key:
            logger.error("ASR_API_KEY not configured")
            yield Result.fail("[USE_BROWSER_ASR]")
            return

        ws_connection = None
        receive_task: asyncio.Task | None = None
        try:
            # Connect to WebSocket
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }

            logger.info(f"Connecting to ASR WebSocket: {self.url}")
            ws_connection = await asyncio.wait_for(
                websockets.connect(self.url, additional_headers=headers),
                timeout=10.0
            )

            logger.info("Connected to Alibaba Cloud ASR WebSocket")

            # 配置会话 - 使用 Manual 模式（关闭 VAD）
            # 适合"按住说话"场景，用户松开按钮后手动提交
            session_config = {
                "event_id": "session_init",
                "type": "session.update",
                "session": {
                    "input_audio_format": self.audio_format,
                    "sample_rate": sample_rate,
                    "input_audio_transcription": {
                        "language": "zh"  # 中文
                    },
                    # Manual 模式：turn_detection 设为 null
                    "turn_detection": None
                }
            }

            await ws_connection.send(json.dumps(session_config))
            logger.info("Sent session config (Manual mode, turn_detection=null)")

            # 等待 session.created 或 session.updated 响应
            try:
                response = await asyncio.wait_for(ws_connection.recv(), timeout=5.0)
                data = json.loads(response)
                logger.info(f"Session response: {data.get('type')}")
                if data.get('type') == 'error':
                    error_msg = data.get('error', {}).get('message', 'Unknown')
                    logger.error(f"Session config error: {error_msg}")
                    yield Result.fail("[USE_BROWSER_ASR]")
                    return
            except TimeoutError:
                logger.warning("Timeout waiting for session response, continuing...")

            # Start receiving task
            transcript_queue = asyncio.Queue(maxsize=64)
            final_event = asyncio.Event()
            accumulated_text = []

            receive_task = asyncio.create_task(
                self._receive_transcriptions(ws_connection, transcript_queue, final_event, accumulated_text)
            )

            # Send audio chunks
            chunk_count = 0
            total_bytes = 0
            async for chunk in audio_stream:
                if len(chunk) > 0:
                    chunk_count += 1
                    total_bytes += len(chunk)

                    # Encode to base64
                    audio_b64 = base64.b64encode(chunk).decode('utf-8')

                    # Send audio buffer append event
                    event = {
                        "event_id": f"event_{int(asyncio.get_event_loop().time() * 1000)}",
                        "type": "input_audio_buffer.append",
                        "audio": audio_b64
                    }

                    await ws_connection.send(json.dumps(event))

                    # Drain intermediate transcriptions to keep realtime feedback smooth
                    while True:
                        try:
                            transcript = transcript_queue.get_nowait()
                            yield Result.ok(transcript)
                        except asyncio.QueueEmpty:
                            break

            audio_duration = total_bytes / (sample_rate * 2)
            logger.info(f"Sent {chunk_count} audio chunks, total {total_bytes} bytes ({audio_duration:.2f}s)")

            # Manual 模式：发送 commit 事件触发识别
            commit_event = {
                "event_id": f"commit_{int(asyncio.get_event_loop().time() * 1000)}",
                "type": "input_audio_buffer.commit"
            }
            await ws_connection.send(json.dumps(commit_event))
            logger.info("Sent input_audio_buffer.commit (Manual mode)")

            # Wait for final transcription with timeout
            try:
                await asyncio.wait_for(final_event.wait(), timeout=10.0)
                logger.info("Received final transcription event")
            except TimeoutError:
                logger.warning("Timeout waiting for final transcription")

            # Yield the final accumulated text
            if accumulated_text:
                final_text = accumulated_text[-1]
                logger.info(f"Final ASR result: {final_text}")
                yield Result.ok(final_text)
            else:
                logger.warning("No transcription results accumulated")
                # 尝试从队列中获取任何结果
                try:
                    while True:
                        transcript = transcript_queue.get_nowait()
                        logger.info(f"Found queued transcript: {transcript}")
                        yield Result.ok(transcript)
                except asyncio.QueueEmpty:
                    pass

        except TimeoutError:
            logger.error("ASR WebSocket connection timeout")
            yield Result.fail("[USE_BROWSER_ASR]")

        except ConnectionClosed as e:
            logger.error(f"ASR WebSocket closed: {e}")
            yield Result.fail("[USE_BROWSER_ASR]")

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"ASR streaming error: {str(e)}", exc_info=True)
            yield Result.fail("[USE_BROWSER_ASR]")

        finally:
            if receive_task and not receive_task.done():
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
            if ws_connection:
                await ws_connection.close()

    async def _receive_transcriptions(
        self,
        ws_connection,
        transcript_queue: asyncio.Queue,
        final_event: asyncio.Event,
        accumulated_text: list
    ):
        """Receive transcription events from WebSocket"""
        def _offer_transcript(transcript: str) -> None:
            if not transcript:
                return
            try:
                transcript_queue.put_nowait(transcript)
            except asyncio.QueueFull:
                # Keep the queue bounded: drop oldest stale item first.
                try:
                    transcript_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                with contextlib.suppress(asyncio.QueueFull):
                    transcript_queue.put_nowait(transcript)

        try:
            async for message in ws_connection:
                data = json.loads(message)
                event_type = data.get("type")

                logger.debug(f"ASR event: {event_type}, data: {json.dumps(data, ensure_ascii=False)[:200]}")

                if event_type == "conversation.item.input_audio_transcription.completed":
                    # 最终完整的转录结果
                    transcript = data.get("transcript", "")
                    if transcript:
                        accumulated_text.append(transcript)
                        _offer_transcript(transcript)
                        logger.info(f"ASR completed transcript: {transcript}")
                        final_event.set()  # 标记完成

                elif event_type == "conversation.item.input_audio_transcription.delta":
                    # 增量转录结果
                    delta = data.get("delta", "")
                    if delta:
                        logger.debug(f"ASR delta: {delta}")

                elif event_type == "conversation.item.input_audio_transcription.text":
                    # 中间结果 (stash)
                    stash = data.get("stash", "")
                    if stash:
                        accumulated_text.append(stash)
                        _offer_transcript(stash)
                        logger.info(f"ASR stash: {stash}")

                elif event_type == "input_audio_buffer.speech_started":
                    logger.info("ASR: Speech started")

                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.info("ASR: Speech stopped")

                elif event_type == "input_audio_buffer.committed":
                    logger.info("ASR: Audio buffer committed")

                elif event_type == "session.created" or event_type == "session.updated":
                    logger.info(f"ASR session event: {event_type}")

                elif event_type == "error":
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"ASR error: {error_msg}")
                    final_event.set()  # 出错也标记完成

        except ConnectionClosed:
            logger.warning("WebSocket connection closed during receive")
            final_event.set()

    async def _send_silence(self, ws_connection, duration_ms: int = 600):
        """Send silence to trigger VAD finalization"""
        silence_chunks = duration_ms // 20  # 20ms chunks
        for _ in range(silence_chunks):
            silence_b64 = base64.b64encode(bytes(320)).decode('ascii')  # 20ms at 16kHz
            event = {
                "event_id": f"silence_{asyncio.get_event_loop().time()}",
                "type": "input_audio_buffer.append",
                "audio": silence_b64
            }
            await ws_connection.send(json.dumps(event))
            await asyncio.sleep(0.02)

    async def transcribe_file(self, audio_file: str) -> Result[str]:
        """
        Transcribe audio file using streaming interface

        Args:
            audio_file: Path to audio file

        Returns:
            Result with transcribed text or fallback
        """
        async def audio_stream():
            with open(audio_file, 'rb') as f:
                while chunk := f.read(3200):  # 100ms chunks
                    yield chunk

        full_transcript = []
        async for result in self.stream_transcribe(audio_stream()):
            if result.is_success:
                full_transcript.append(result.value)

        if full_transcript:
            return Result.ok(" ".join(full_transcript))
        else:
            return Result.fail("[USE_BROWSER_ASR]")

    async def health_check(self) -> Result[bool]:
        """
        Check if Alibaba Cloud ASR is accessible

        Returns:
            Result indicating if connection can be established
        """
        try:
            # Try to establish WebSocket connection
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }

            async with asyncio.timeout(3.0):
                async with websockets.connect(self.url, additional_headers=headers):
                    pass

            return Result.ok(True)

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"Alibaba ASR health check failed: {str(e)}")
            return Result.fail(False)

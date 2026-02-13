"""
阿里云流式TTS服务
使用 DashScope CosyVoice 模型
延迟: 首包 50ms, 总延迟 80-150ms
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# 尝试导入 dashscope，如果不存在则提供 mock 实现
try:
    from dashscope.audio.tts_v2 import AudioFormat, ResultCallback, SpeechSynthesizer

    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False

    # Mock classes for type checking
    class ResultCallback:  # type: ignore
        """Mock ResultCallback when dashscope is not available"""

    class AudioFormat:  # type: ignore
        """Mock AudioFormat when dashscope is not available"""

        MP3 = "mp3"


class AliyunStreamingTTS:
    """
    阿里云流式TTS服务

    Features:
    - 超低延迟: 首包 50ms
    - 流式输出: 边生成边发送
    - 高质量音色: CosyVoice 模型
    - 自动降级: 失败时回退到 Edge-TTS
    """

    # 可用音色列表
    VOICES = {
        "longxiaochun": "龙小春 (温柔女声)",
        "longfei": "龙飞 (成熟男声)",
        "longyue": "龙悦 (活泼女声)",
        "longxiaoxia": "龙小夏 (甜美女声)",
        "longtian": "龙天 (磁性男声)",
    }

    def __init__(self, api_key: str | None = None, default_voice: str | None = None):
        """
        初始化阿里云TTS服务

        Args:
            api_key: DashScope API Key (如不提供则从环境变量读取)

        Raises:
            ValueError: 如果未提供 API Key 且环境变量未设置
            ImportError: 如果 dashscope 库未安装
        """
        import os

        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY is required")

        if not DASHSCOPE_AVAILABLE:
            raise ImportError(
                "dashscope library is required. Install with: pip install dashscope>=1.25.3"
            )

        self.default_voice = default_voice or "longxiaochun"
        self.default_format = AudioFormat.MP3
        self.default_sample_rate = 16000

        logger.info(f"AliyunStreamingTTS initialized with voice: {self.default_voice}")

    async def synthesize_streaming(
        self,
        text: str,
        on_chunk: Callable[[bytes, int, bool], Awaitable[None]],
        voice: str | None = None,
        stream_id: str | None = None,
    ) -> Result[int]:
        """
        流式语音合成

        Args:
            text: 要合成的文本
            on_chunk: 音频块回调函数 (audio_data, chunk_index, is_final)
            voice: 音色名称 (默认: longxiaochun)
            stream_id: 流ID (用于前端消息版本控制)

        Returns:
            Result[int]: 成功返回总时长(ms), 失败返回错误码
        """
        voice = voice or self.default_voice
        stream_id = stream_id or str(uuid.uuid4())

        try:
            # 创建回调处理器
            callback_handler = StreamCallbackHandler(
                on_chunk=on_chunk, stream_id=stream_id
            )

            # 创建合成器
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v1",  # 超低延迟模型
                voice=voice,
                format=self.default_format,
                sample_rate=self.default_sample_rate,
                callback=callback_handler,
                api_key=self.api_key,
            )

            logger.info(
                f"Starting TTS synthesis: text_length={len(text)}, "
                f"voice={voice}, stream_id={stream_id}"
            )

            # 开始流式合成
            synthesizer.streaming_call(text)

            # 等待合成完成
            await callback_handler.wait_completion()

            total_duration_ms = callback_handler.total_duration_ms

            logger.info(
                f"TTS synthesis completed: stream_id={stream_id}, "
                f"chunks={callback_handler.chunk_index}, "
                f"duration={total_duration_ms}ms"
            )

            return Result.ok(total_duration_ms)

        except Exception as e:
            logger.error(f"TTS synthesis failed: {str(e)}", exc_info=True)
            return Result.fail("[USE_BROWSER_TTS]")

    async def synthesize_to_file(
        self, text: str, output_file: str, voice: str | None = None
    ) -> Result[bool]:
        """
        合成语音到文件

        Args:
            text: 要合成的文本
            output_file: 输出文件路径
            voice: 音色名称

        Returns:
            Result[bool]: 成功返回 True
        """
        voice = voice or self.default_voice

        try:
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v1",
                voice=voice,
                format=self.default_format,
                sample_rate=self.default_sample_rate,
                api_key=self.api_key,
            )

            # 合成到文件
            synthesizer.call(text, output=output_file)

            logger.info(f"TTS saved to file: {output_file}")
            return Result.ok(True)

        except Exception as e:
            logger.error(f"TTS file synthesis failed: {str(e)}")
            return Result.fail("[TTS_FILE_ERROR]")


class StreamCallbackHandler(ResultCallback):
    """流式TTS回调处理器"""

    def __init__(
        self, on_chunk: Callable[[bytes, int, bool], Awaitable[None]], stream_id: str
    ):
        super().__init__()
        self.on_chunk = on_chunk
        self.stream_id = stream_id
        self.chunk_index = 0
        self.total_duration_ms = 0
        self.completion_event = asyncio.Event()
        self.error: Exception | None = None

        # 估算参数 (MP3 @ 16kHz, ~128kbps)
        self.BYTES_PER_MS = 16

    def on_open(self):
        """连接打开"""
        logger.debug(f"TTS stream opened: stream_id={self.stream_id}")

    def on_data(self, data: bytes):
        """接收音频数据块"""
        try:
            # 估算时长
            chunk_duration_ms = max(1, len(data) // self.BYTES_PER_MS)
            self.total_duration_ms += chunk_duration_ms

            # 异步调用回调
            asyncio.create_task(self.on_chunk(data, self.chunk_index, False))

            self.chunk_index += 1

            logger.debug(
                f"TTS chunk received: stream_id={self.stream_id}, "
                f"index={self.chunk_index}, size={len(data)}, "
                f"duration={chunk_duration_ms}ms"
            )

        except Exception as e:
            logger.error(f"Error processing TTS chunk: {e}")
            self.error = e

    def on_close(self):
        """连接关闭"""
        try:
            # 发送最终标记
            asyncio.create_task(self.on_chunk(b"", self.chunk_index, True))

            logger.info(
                f"TTS stream closed: stream_id={self.stream_id}, "
                f"total_chunks={self.chunk_index}, "
                f"total_duration={self.total_duration_ms}ms"
            )

        except Exception as e:
            logger.error(f"Error closing TTS stream: {e}")
            self.error = e
        finally:
            self.completion_event.set()

    def on_error(self, message: str):
        """错误处理"""
        logger.error(f"TTS stream error: {message}")
        self.error = Exception(message)
        self.completion_event.set()

    async def wait_completion(self):
        """等待合成完成"""
        await self.completion_event.wait()
        if self.error:
            raise self.error


# 单例实例
_aliyun_tts_service: AliyunStreamingTTS | None = None


def get_aliyun_tts_service(
    api_key: str | None = None,
    default_voice: str | None = None,
) -> AliyunStreamingTTS:
    """获取单例TTS服务"""
    global _aliyun_tts_service
    if _aliyun_tts_service is None:
        _aliyun_tts_service = AliyunStreamingTTS(api_key=api_key, default_voice=default_voice)
    else:
        if api_key and _aliyun_tts_service.api_key != api_key:
            _aliyun_tts_service = AliyunStreamingTTS(api_key=api_key, default_voice=default_voice)
        elif default_voice:
            _aliyun_tts_service.default_voice = default_voice
    return _aliyun_tts_service

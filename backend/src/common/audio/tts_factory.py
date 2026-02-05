"""
TTS服务统一接口
支持多个提供商: Edge-TTS, 阿里云, 降级方案

Phase 2.2: TTS服务工厂和降级机制
- 支持 Edge-TTS (免费)
- 支持 阿里云TTS (推荐)
- 支持 浏览器TTS (降级)
- 自动降级链: 阿里云 → Edge-TTS → 浏览器TTS
"""

import os
from collections.abc import Awaitable, Callable
from enum import Enum

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class TTSProvider(Enum):
    """TTS提供商"""

    EDGE = "edge"  # Edge-TTS (免费)
    ALIYUN = "aliyun"  # 阿里云 (推荐)
    BROWSER = "browser"  # 浏览器TTS (降级)


class TTSServiceFactory:
    """TTS服务工厂"""

    @staticmethod
    def create(provider: str | None = None) -> object:
        """
        创建TTS服务实例

        Args:
            provider: 提供商名称，可选。如不提供则从环境变量 TTS_PROVIDER 读取

        Returns:
            TTS服务实例

        Raises:
            ValueError: 如果提供商名称未知
        """
        provider = provider or os.getenv("TTS_PROVIDER", TTSProvider.ALIYUN.value)

        if provider == TTSProvider.ALIYUN.value:
            from common.audio.aliyun_streaming_tts import get_aliyun_tts_service

            return get_aliyun_tts_service()
        elif provider == TTSProvider.EDGE.value:
            from common.audio.tts_service import get_tts_service

            return get_tts_service()
        elif provider == TTSProvider.BROWSER.value:
            # 浏览器TTS不需要后端服务
            raise ValueError(
                "Browser TTS is a client-side fallback, "
                "not available as a backend service"
            )
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")


class TTSServiceWithFallback:
    """
    带降级的TTS服务
    降级顺序: 阿里云 → Edge-TTS → 浏览器TTS
    """

    def __init__(self):
        self.primary_service: object | None = None
        self.fallback_service: object | None = None
        self.primary_available = False
        self.fallback_available = False

        # 尝试初始化主服务（阿里云）
        try:
            from common.audio.aliyun_streaming_tts import (
                AliyunStreamingTTS,
                get_aliyun_tts_service,
            )

            self.primary_service = get_aliyun_tts_service()
            # 验证服务是否真正可用（检查API Key等）
            if isinstance(self.primary_service, AliyunStreamingTTS):
                if self.primary_service.api_key:
                    self.primary_available = True
                    logger.info("Aliyun TTS service initialized successfully")
                else:
                    logger.warning("Aliyun TTS initialized but API key is empty")
            else:
                self.primary_available = True
                logger.info("Aliyun TTS service initialized")
        except Exception as e:
            logger.warning(f"Aliyun TTS not available: {e}")
            self.primary_available = False

        # 尝试初始化备用服务（Edge-TTS）
        try:
            from common.audio.tts_service import TTSService, get_tts_service

            self.fallback_service = get_tts_service()
            # 验证服务是否真正可用
            if isinstance(self.fallback_service, TTSService):
                self.fallback_available = True
                logger.info("Edge-TTS service initialized successfully")
            else:
                self.fallback_available = True
                logger.info("Edge-TTS service initialized")
        except Exception as e:
            logger.warning(f"Edge TTS not available: {e}")
            self.fallback_available = False

    async def synthesize_streaming(
        self,
        text: str,
        on_chunk: Callable[[bytes, int, bool], Awaitable[None]],
        voice: str | None = None,
        stream_id: str | None = None,
    ) -> Result[int]:
        """
        流式语音合成（自动降级）

        降级链:
        1. 尝试阿里云TTS (推荐，低延迟)
        2. 降级到 Edge-TTS (免费备用)
        3. 最终降级到浏览器TTS (客户端处理)

        Args:
            text: 要合成的文本
            on_chunk: 音频块回调函数 (audio_data, chunk_index, is_final)
            voice: 音色名称
            stream_id: 流ID

        Returns:
            Result[int]: 成功返回总时长(ms)，失败返回降级指令
        """
        # 1. 尝试阿里云TTS
        if self.primary_available and self.primary_service:
            try:
                result = await self.primary_service.synthesize_streaming(
                    text, on_chunk, voice, stream_id
                )
                if result.is_success:
                    logger.debug("Aliyun TTS synthesis succeeded")
                    return result
                logger.warning(
                    f"Aliyun TTS failed, falling back to Edge-TTS: {result.fallback}"
                )
            except Exception as e:
                logger.warning(f"Aliyun TTS error, falling back: {e}")

        # 2. 降级到 Edge-TTS
        if self.fallback_available and self.fallback_service:
            try:
                # 适配Edge-TTS接口
                from common.audio.tts_service import TTSChunk

                async def edge_on_chunk(chunk: TTSChunk) -> None:
                    await on_chunk(
                        chunk.audio,
                        chunk.chunk_index,
                        chunk.is_final,
                    )

                result = await self.fallback_service.synthesize_streaming(
                    text, edge_on_chunk, voice
                )
                if result.is_success:
                    logger.info("Fallback to Edge-TTS succeeded")
                    return result
                logger.warning(
                    f"Edge-TTS failed, falling back to browser: {result.fallback}"
                )
            except Exception as e:
                logger.error(f"Edge-TTS fallback failed: {e}")

        # 3. 最终降级到浏览器TTS
        logger.error("All TTS services failed, instructing browser TTS")
        return Result.fail("[USE_BROWSER_TTS]")

    async def synthesize_to_file(
        self,
        text: str,
        output_file: str,
        voice: str | None = None,
    ) -> Result[bool]:
        """
        合成语音到文件（自动降级）

        Args:
            text: 要合成的文本
            output_file: 输出文件路径
            voice: 音色名称

        Returns:
            Result[bool]: 成功返回True，失败返回降级指令
        """
        # 1. 尝试阿里云TTS
        if self.primary_available and self.primary_service:
            try:
                result = await self.primary_service.synthesize_to_file(
                    text, output_file, voice
                )
                if result.is_success:
                    logger.debug("Aliyun TTS file synthesis succeeded")
                    return result
                logger.warning(
                    f"Aliyun TTS file synthesis failed, falling back: {result.fallback}"
                )
            except Exception as e:
                logger.warning(f"Aliyun TTS file error, falling back: {e}")

        # 2. 降级到 Edge-TTS
        if self.fallback_available and self.fallback_service:
            try:
                result = await self.fallback_service.synthesize_to_file(
                    text, output_file, voice
                )
                if result.is_success:
                    logger.info("Fallback to Edge-TTS file synthesis succeeded")
                    return result
                logger.warning(f"Edge-TTS file synthesis failed: {result.fallback}")
            except Exception as e:
                logger.error(f"Edge-TTS file fallback failed: {e}")

        # 3. 最终降级
        logger.error("All TTS file services failed")
        return Result.fail("[USE_BROWSER_TTS]")

    def get_status(self) -> dict:
        """
        获取TTS服务状态

        Returns:
            dict: 包含各服务可用状态的字典
        """
        return {
            "primary": {
                "provider": TTSProvider.ALIYUN.value,
                "available": self.primary_available,
            },
            "fallback": {
                "provider": TTSProvider.EDGE.value,
                "available": self.fallback_available,
            },
            "final_fallback": {
                "provider": TTSProvider.BROWSER.value,
                "available": True,  # 浏览器TTS始终可用
            },
        }


# 全局实例
_tts_service_with_fallback: TTSServiceWithFallback | None = None


def get_tts_service_with_fallback() -> TTSServiceWithFallback:
    """
    获取带降级的TTS服务单例

    Returns:
        TTSServiceWithFallback: 带降级机制的TTS服务实例
    """
    global _tts_service_with_fallback
    if _tts_service_with_fallback is None:
        _tts_service_with_fallback = TTSServiceWithFallback()
    return _tts_service_with_fallback


def reset_tts_service_with_fallback() -> None:
    """
    重置TTS服务单例（主要用于测试）
    """
    global _tts_service_with_fallback
    _tts_service_with_fallback = None
    logger.debug("TTS service with fallback reset")

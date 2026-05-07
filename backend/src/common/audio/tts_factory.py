"""
TTS服务统一接口
支持多个提供商: Edge-TTS, 阿里云, 降级方案

Phase 2.2: TTS服务工厂和降级机制
- 支持 Edge-TTS (免费)
- 支持 阿里云TTS (推荐)
- 支持 浏览器TTS (降级)
- 自动降级链: 阿里云 → Edge-TTS → 浏览器TTS
"""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TYPE_CHECKING, Protocol, TypedDict

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelType
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

if TYPE_CHECKING:
    from common.audio.tts_service import TTSChunk

logger = get_logger(__name__)


def _resolve_tts_runtime_config() -> dict[str, object] | None:
    """Resolve runtime TTS config from database default config only."""
    try:
        config_manager = get_config_manager()
        db_config = config_manager.get_default_config(ModelType.TTS)
        if not db_config or not db_config.is_active:
            return None

        provider_raw = str(db_config.provider).lower()
        if provider_raw in {"alibaba", "aliyun"}:
            provider = TTSProvider.ALIYUN.value
        else:
            provider = TTSProvider.EDGE.value

        api_key = ""
        if db_config.api_key_encrypted:
            decrypt_result = config_manager.get_decrypted_api_key(db_config)
            if decrypt_result.is_success and decrypt_result.value:
                api_key = decrypt_result.value

        return {
            "provider": provider,
            "api_key": api_key,
            "voice": db_config.model_name or "",
            "extra_config": db_config.extra_config or {},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to resolve TTS runtime config: {exc}")
        return None


def _apply_edge_voice_config(
    service: object, runtime_config: dict[str, object] | None
) -> None:
    """Apply runtime voice/rate/pitch to Edge TTS service if available."""
    if not runtime_config:
        return

    if runtime_config.get("provider") != TTSProvider.EDGE.value:
        return

    voice = runtime_config.get("voice")
    extra_config = runtime_config.get("extra_config", {})
    if isinstance(voice, str) and voice and hasattr(service, "voice"):
        setattr(service, "voice", voice)

    if isinstance(extra_config, dict) and hasattr(service, "set_voice_parameters"):
        rate = extra_config.get("rate")
        volume = extra_config.get("volume")
        pitch = extra_config.get("pitch")
        service.set_voice_parameters(  # type: ignore[attr-defined]
            rate=rate if isinstance(rate, str) else None,
            volume=volume if isinstance(volume, str) else None,
            pitch=pitch if isinstance(pitch, str) else None,
        )


class TTSProvider(Enum):
    """TTS提供商"""

    EDGE = "edge"  # Edge-TTS (免费)
    ALIYUN = "aliyun"  # 阿里云 (推荐)
    BROWSER = "browser"  # 浏览器TTS (降级)


class _AliyunTTSProvider(Protocol):
    """Runtime contract for the Aliyun streaming TTS provider."""

    api_key: str | None

    async def synthesize_streaming(
        self,
        text: str,
        on_chunk: Callable[[bytes, int, bool], Awaitable[None]],
        voice: str | None = None,
        stream_id: str | None = None,
    ) -> Result[int]: ...

    async def synthesize_to_file(
        self,
        text: str,
        output_file: str,
        voice: str | None = None,
    ) -> Result[bool]: ...


class _EdgeTTSProvider(Protocol):
    """Runtime contract for the Edge-TTS provider."""

    async def synthesize_streaming(
        self,
        text: str,
        on_chunk: Callable[[TTSChunk], Awaitable[None]],
        voice: str | None = None,
    ) -> Result[int]: ...

    async def synthesize_to_file(
        self,
        text: str,
        output_file: str,
        voice: str | None = None,
    ) -> Result[bool]: ...


class _TTSMetrics(TypedDict):
    primary_success: int
    primary_failures: int
    fallback_success: int
    fallback_failures: int
    browser_fallbacks: int
    last_provider: str | None


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
        runtime_config = _resolve_tts_runtime_config()
        runtime_provider = runtime_config.get("provider") if runtime_config else None
        provider_name = (
            provider
            or (runtime_provider if isinstance(runtime_provider, str) else None)
            or os.getenv("TTS_PROVIDER", TTSProvider.ALIYUN.value)
        )

        if provider_name == TTSProvider.ALIYUN.value:
            from common.audio.aliyun_streaming_tts import get_aliyun_tts_service

            api_key = runtime_config.get("api_key") if runtime_config else None
            voice = runtime_config.get("voice") if runtime_config else None
            return get_aliyun_tts_service(
                api_key=api_key if isinstance(api_key, str) else None,
                default_voice=voice if isinstance(voice, str) and voice else None,
            )
        elif provider_name in {TTSProvider.EDGE.value, "local"}:
            from common.audio.tts_service import get_tts_service

            service = get_tts_service()
            _apply_edge_voice_config(service, runtime_config)
            return service
        elif provider_name == TTSProvider.BROWSER.value:
            # 浏览器TTS不需要后端服务
            raise ValueError(
                "Browser TTS is a client-side fallback, "
                "not available as a backend service"
            )
        else:
            raise ValueError(f"Unknown TTS provider: {provider_name}")


class TTSServiceWithFallback:
    """
    带降级的TTS服务
    降级顺序: 阿里云 → Edge-TTS → 浏览器TTS
    """

    def __init__(self) -> None:
        self.primary_service: _AliyunTTSProvider | None = None
        self.fallback_service: _EdgeTTSProvider | None = None
        self.primary_available = False
        self.fallback_available = False
        self.runtime_config = _resolve_tts_runtime_config()
        self.metrics: _TTSMetrics = {
            "primary_success": 0,
            "primary_failures": 0,
            "fallback_success": 0,
            "fallback_failures": 0,
            "browser_fallbacks": 0,
            "last_provider": None,
        }

        runtime_provider = (
            self.runtime_config.get("provider") if self.runtime_config else None
        )
        configured_provider = (
            runtime_provider
            if isinstance(runtime_provider, str)
            else os.getenv("TTS_PROVIDER", TTSProvider.ALIYUN.value)
        )

        # 尝试初始化主服务（阿里云）
        if configured_provider == TTSProvider.ALIYUN.value:
            try:
                from common.audio.aliyun_streaming_tts import AliyunStreamingTTS

                api_key = (
                    self.runtime_config.get("api_key") if self.runtime_config else None
                )
                voice = (
                    self.runtime_config.get("voice") if self.runtime_config else None
                )
                self.primary_service = get_aliyun_tts_service(
                    api_key=api_key if isinstance(api_key, str) else None,
                    default_voice=voice if isinstance(voice, str) and voice else None,
                )
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
        else:
            logger.info("TTS configured to Edge/local provider, skip Aliyun primary")

        # 尝试初始化备用服务（Edge-TTS）
        try:
            from common.audio.tts_service import TTSService

            self.fallback_service = get_tts_service()
            _apply_edge_voice_config(self.fallback_service, self.runtime_config)
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
        start_time = time.perf_counter()

        # 1. 尝试阿里云TTS
        if self.primary_available and self.primary_service:
            try:
                result = await self.primary_service.synthesize_streaming(
                    text, on_chunk, voice, stream_id
                )
                if result.is_success:
                    self.metrics["primary_success"] += 1
                    self.metrics["last_provider"] = TTSProvider.ALIYUN.value
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    logger.debug(f"Aliyun TTS synthesis succeeded in {elapsed_ms}ms")
                    return result
                self.metrics["primary_failures"] += 1
                logger.warning(
                    f"Aliyun TTS failed, falling back to Edge-TTS: {result.fallback}"
                )
            except (ConnectionError, OSError, RuntimeError, ValueError) as e:
                self.metrics["primary_failures"] += 1
                logger.warning(f"Aliyun TTS error, falling back: {e}")

        # 2. 降级到 Edge-TTS
        if self.fallback_available and self.fallback_service:
            try:
                # 适配Edge-TTS接口
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
                    self.metrics["fallback_success"] += 1
                    self.metrics["last_provider"] = TTSProvider.EDGE.value
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    logger.info(f"Fallback to Edge-TTS succeeded in {elapsed_ms}ms")
                    return result
                self.metrics["fallback_failures"] += 1
                logger.warning(
                    f"Edge-TTS failed, falling back to browser: {result.fallback}"
                )
            except (ConnectionError, OSError, RuntimeError, ValueError) as e:
                self.metrics["fallback_failures"] += 1
                logger.error(f"Edge-TTS fallback failed: {e}")

        # 3. 最终降级到浏览器TTS
        self.metrics["browser_fallbacks"] += 1
        self.metrics["last_provider"] = TTSProvider.BROWSER.value
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
        start_time = time.perf_counter()

        # 1. 尝试阿里云TTS
        if self.primary_available and self.primary_service:
            try:
                result = await self.primary_service.synthesize_to_file(
                    text, output_file, voice
                )
                if result.is_success:
                    self.metrics["primary_success"] += 1
                    self.metrics["last_provider"] = TTSProvider.ALIYUN.value
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    logger.debug(
                        f"Aliyun TTS file synthesis succeeded in {elapsed_ms}ms"
                    )
                    return result
                self.metrics["primary_failures"] += 1
                logger.warning(
                    f"Aliyun TTS file synthesis failed, falling back: {result.fallback}"
                )
            except (ConnectionError, OSError, RuntimeError, ValueError) as e:
                self.metrics["primary_failures"] += 1
                logger.warning(f"Aliyun TTS file error, falling back: {e}")

        # 2. 降级到 Edge-TTS
        if self.fallback_available and self.fallback_service:
            try:
                result = await self.fallback_service.synthesize_to_file(
                    text, output_file, voice
                )
                if result.is_success:
                    self.metrics["fallback_success"] += 1
                    self.metrics["last_provider"] = TTSProvider.EDGE.value
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    logger.info(
                        f"Fallback to Edge-TTS file synthesis succeeded in {elapsed_ms}ms"
                    )
                    return result
                self.metrics["fallback_failures"] += 1
                logger.warning(f"Edge-TTS file synthesis failed: {result.fallback}")
            except (ConnectionError, OSError, RuntimeError, ValueError) as e:
                self.metrics["fallback_failures"] += 1
                logger.error(f"Edge-TTS file fallback failed: {e}")

        # 3. 最终降级
        self.metrics["browser_fallbacks"] += 1
        self.metrics["last_provider"] = TTSProvider.BROWSER.value
        logger.error("All TTS file services failed")
        return Result.fail("[USE_BROWSER_TTS]")

    def get_status(self) -> dict[str, object]:
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
            "metrics": dict(self.metrics),
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


def get_tts_service() -> _EdgeTTSProvider:
    """Compatibility wrapper for tests and legacy patch points."""
    from common.audio.tts_service import get_tts_service as _get_tts_service

    return _get_tts_service()


def get_aliyun_tts_service(
    api_key: str | None = None,
    default_voice: str | None = None,
) -> _AliyunTTSProvider:
    """Compatibility wrapper for tests and legacy patch points."""
    from common.audio.aliyun_streaming_tts import get_aliyun_tts_service as _get_aliyun

    return _get_aliyun(api_key=api_key, default_voice=default_voice)

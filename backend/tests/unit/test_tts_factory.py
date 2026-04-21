"""
单元测试: TTS服务工厂和降级机制

测试范围:
- TTSProvider 枚举
- TTSServiceFactory 工厂类
- TTSServiceWithFallback 降级服务
- get_tts_service_with_fallback 单例函数
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.audio.tts_factory import (
    TTSProvider,
    TTSServiceFactory,
    TTSServiceWithFallback,
    get_tts_service_with_fallback,
    reset_tts_service_with_fallback,
)
from common.error_handling.result import Result


class TestTTSProviderEnum:
    """测试TTSProvider枚举"""

    def test_tts_provider_enum_values(self):
        """测试枚举值定义正确"""
        assert TTSProvider.EDGE.value == "edge"
        assert TTSProvider.ALIYUN.value == "aliyun"
        assert TTSProvider.BROWSER.value == "browser"

    def test_tts_provider_enum_members(self):
        """测试枚举成员可访问"""
        assert TTSProvider("edge") == TTSProvider.EDGE
        assert TTSProvider("aliyun") == TTSProvider.ALIYUN
        assert TTSProvider("browser") == TTSProvider.BROWSER


class TestTTSServiceFactory:
    """测试TTSServiceFactory工厂类"""

    @patch.dict(os.environ, {"TTS_PROVIDER": "aliyun"})
    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    def test_factory_create_aliyun(self, mock_get_aliyun):
        """测试创建阿里云服务"""
        mock_service = MagicMock()
        mock_get_aliyun.return_value = mock_service

        service = TTSServiceFactory.create("aliyun")

        assert service == mock_service
        mock_get_aliyun.assert_called_once()

    @patch.dict(os.environ, {"TTS_PROVIDER": "edge"})
    @patch("common.audio.tts_service.get_tts_service")
    def test_factory_create_edge(self, mock_get_edge):
        """测试创建Edge服务"""
        mock_service = MagicMock()
        mock_get_edge.return_value = mock_service

        service = TTSServiceFactory.create("edge")

        assert service == mock_service
        mock_get_edge.assert_called_once()

    @patch.dict(os.environ, {"TTS_PROVIDER": "aliyun"})
    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    def test_factory_create_from_env(self, mock_get_aliyun):
        """测试从环境变量读取默认提供商"""
        mock_service = MagicMock()
        mock_get_aliyun.return_value = mock_service

        # 不提供provider参数，应从环境变量读取
        service = TTSServiceFactory.create()

        assert service == mock_service
        mock_get_aliyun.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    def test_factory_create_default(self, mock_get_aliyun):
        """测试默认提供商为阿里云"""
        mock_service = MagicMock()
        mock_get_aliyun.return_value = mock_service

        # 无环境变量，使用默认值
        service = TTSServiceFactory.create()

        assert service == mock_service
        mock_get_aliyun.assert_called_once()

    def test_factory_create_browser_raises(self):
        """测试创建浏览器TTS抛出异常"""
        with pytest.raises(ValueError, match="Browser TTS"):
            TTSServiceFactory.create("browser")

    def test_factory_create_unknown_provider(self):
        """测试未知提供商抛出异常"""
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            TTSServiceFactory.create("unknown_provider")


class TestTTSServiceWithFallback:
    """测试TTSServiceWithFallback降级服务"""

    def setup_method(self):
        """每个测试前重置单例"""
        reset_tts_service_with_fallback()

    def teardown_method(self):
        """每个测试后重置单例"""
        reset_tts_service_with_fallback()

    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    @patch("common.audio.tts_service.get_tts_service")
    def test_fallback_initialization_both_available(
        self, mock_get_edge, mock_get_aliyun
    ):
        """测试降级服务初始化 - 两个服务都可用"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_get_aliyun.return_value = mock_aliyun

        mock_edge = MagicMock()
        mock_get_edge.return_value = mock_edge

        service = TTSServiceWithFallback()

        assert service.primary_available is True
        assert service.fallback_available is True
        assert service.primary_service == mock_aliyun
        assert service.fallback_service == mock_edge

    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    @patch("common.audio.tts_service.get_tts_service")
    def test_fallback_initialization_aliyun_only(self, mock_get_edge, mock_get_aliyun):
        """测试降级服务初始化 - 只有阿里云可用"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_get_aliyun.return_value = mock_aliyun

        mock_get_edge.side_effect = Exception("Edge not available")

        service = TTSServiceWithFallback()

        assert service.primary_available is True
        assert service.fallback_available is False

    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    @patch("common.audio.tts_service.get_tts_service")
    def test_fallback_initialization_edge_only(self, mock_get_edge, mock_get_aliyun):
        """测试降级服务初始化 - 只有Edge可用"""
        mock_get_aliyun.side_effect = Exception("Aliyun not available")

        mock_edge = MagicMock()
        mock_get_edge.return_value = mock_edge

        service = TTSServiceWithFallback()

        assert service.primary_available is False
        assert service.fallback_available is True

    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    @patch("common.audio.tts_service.get_tts_service")
    def test_fallback_initialization_none_available(
        self, mock_get_edge, mock_get_aliyun
    ):
        """测试降级服务初始化 - 都不可用"""
        mock_get_aliyun.side_effect = Exception("Aliyun not available")
        mock_get_edge.side_effect = Exception("Edge not available")

        service = TTSServiceWithFallback()

        assert service.primary_available is False
        assert service.fallback_available is False

    @pytest.mark.asyncio
    async def test_synthesize_streaming_primary_success(self):
        """测试主服务成功时直接使用"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_aliyun.synthesize_streaming = AsyncMock(return_value=Result.ok(1000))

        mock_edge = MagicMock()

        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            return_value=mock_aliyun,
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                return_value=mock_edge,
            ):
                service = TTSServiceWithFallback()

                async def on_chunk(audio, index, is_final):
                    pass

                result = await service.synthesize_streaming(
                    "测试文本", on_chunk, "longxiaochun", "stream-1"
                )

                assert result.is_success is True
                assert result.value == 1000
                mock_aliyun.synthesize_streaming.assert_called_once()
                mock_edge.synthesize_streaming.assert_not_called()

    @pytest.mark.asyncio
    async def test_synthesize_streaming_fallback_to_edge(self):
        """测试主服务失败时降级到Edge"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_aliyun.synthesize_streaming = AsyncMock(
            return_value=Result.fail("[ALIYUN_ERROR]")
        )

        mock_edge = MagicMock()
        mock_edge.synthesize_streaming = AsyncMock(return_value=Result.ok(800))

        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            return_value=mock_aliyun,
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                return_value=mock_edge,
            ):
                service = TTSServiceWithFallback()

                async def on_chunk(audio, index, is_final):
                    pass

                result = await service.synthesize_streaming("测试文本", on_chunk)

                assert result.is_success is True
                assert result.value == 800
                mock_aliyun.synthesize_streaming.assert_called_once()
                mock_edge.synthesize_streaming.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_streaming_fallback_to_browser(self):
        """测试所有服务失败时降级到浏览器"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_aliyun.synthesize_streaming = AsyncMock(
            return_value=Result.fail("[ALIYUN_ERROR]")
        )

        mock_edge = MagicMock()
        mock_edge.synthesize_streaming = AsyncMock(
            return_value=Result.fail("[EDGE_ERROR]")
        )

        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            return_value=mock_aliyun,
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                return_value=mock_edge,
            ):
                service = TTSServiceWithFallback()

                async def on_chunk(audio, index, is_final):
                    pass

                result = await service.synthesize_streaming("测试文本", on_chunk)

                assert result.is_success is False
                assert result.fallback == "[USE_BROWSER_TTS]"

    @pytest.mark.asyncio
    async def test_synthesize_streaming_no_services_available(self):
        """测试无可用服务时直接返回浏览器降级"""
        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            side_effect=Exception("Not available"),
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                side_effect=Exception("Not available"),
            ):
                service = TTSServiceWithFallback()

                async def on_chunk(audio, index, is_final):
                    pass

                result = await service.synthesize_streaming("测试文本", on_chunk)

                assert result.is_success is False
                assert result.fallback == "[USE_BROWSER_TTS]"

    @pytest.mark.asyncio
    async def test_synthesize_to_file_primary_success(self):
        """测试文件合成主服务成功"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_aliyun.synthesize_to_file = AsyncMock(return_value=Result.ok(True))

        mock_edge = MagicMock()

        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            return_value=mock_aliyun,
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                return_value=mock_edge,
            ):
                service = TTSServiceWithFallback()

                result = await service.synthesize_to_file("测试文本", "/tmp/test.mp3")

                assert result.is_success is True
                assert result.value is True
                mock_aliyun.synthesize_to_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_to_file_fallback(self):
        """测试文件合成降级"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_aliyun.synthesize_to_file = AsyncMock(
            return_value=Result.fail("[ALIYUN_ERROR]")
        )

        mock_edge = MagicMock()
        mock_edge.synthesize_to_file = AsyncMock(return_value=Result.ok(True))

        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            return_value=mock_aliyun,
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                return_value=mock_edge,
            ):
                service = TTSServiceWithFallback()

                result = await service.synthesize_to_file("测试文本", "/tmp/test.mp3")

                assert result.is_success is True
                mock_aliyun.synthesize_to_file.assert_called_once()
                mock_edge.synthesize_to_file.assert_called_once()

    def test_get_status(self):
        """测试获取服务状态"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_edge = MagicMock()

        with patch(
            "common.audio.aliyun_streaming_tts.get_aliyun_tts_service",
            return_value=mock_aliyun,
        ):
            with patch(
                "common.audio.tts_service.get_tts_service",
                return_value=mock_edge,
            ):
                service = TTSServiceWithFallback()
                status = service.get_status()

                assert status["primary"]["provider"] == "aliyun"
                assert status["primary"]["available"] is True
                assert status["fallback"]["provider"] == "edge"
                assert status["fallback"]["available"] is True
                assert status["final_fallback"]["provider"] == "browser"
                assert status["final_fallback"]["available"] is True
                assert status["metrics"]["primary_success"] == 0
                assert status["metrics"]["fallback_success"] == 0
                assert status["metrics"]["last_provider"] is None


class TestSingleton:
    """测试单例函数"""

    def setup_method(self):
        """每个测试前重置单例"""
        reset_tts_service_with_fallback()

    def teardown_method(self):
        """每个测试后重置单例"""
        reset_tts_service_with_fallback()

    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    @patch("common.audio.tts_service.get_tts_service")
    def test_get_tts_service_with_fallback_singleton(
        self, mock_get_edge, mock_get_aliyun
    ):
        """测试单例函数返回同一实例"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_get_aliyun.return_value = mock_aliyun

        mock_edge = MagicMock()
        mock_get_edge.return_value = mock_edge

        service1 = get_tts_service_with_fallback()
        service2 = get_tts_service_with_fallback()

        assert service1 is service2
        assert isinstance(service1, TTSServiceWithFallback)

    @patch("common.audio.aliyun_streaming_tts.get_aliyun_tts_service")
    @patch("common.audio.tts_service.get_tts_service")
    def test_reset_tts_service_with_fallback(self, mock_get_edge, mock_get_aliyun):
        """测试重置单例函数"""
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_get_aliyun.return_value = mock_aliyun

        mock_edge = MagicMock()
        mock_get_edge.return_value = mock_edge

        service1 = get_tts_service_with_fallback()
        reset_tts_service_with_fallback()
        service2 = get_tts_service_with_fallback()

        assert service1 is not service2

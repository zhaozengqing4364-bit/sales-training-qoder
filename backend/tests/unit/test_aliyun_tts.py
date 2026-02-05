"""阿里云TTS单元测试"""

import asyncio
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock dashscope before importing our module
dashscope_mock = MagicMock()
dashscope_mock.audio = MagicMock()
dashscope_mock.audio.tts_v2 = MagicMock()
dashscope_mock.audio.tts_v2.SpeechSynthesizer = Mock()
dashscope_mock.audio.tts_v2.ResultCallback = object


# Mock AudioFormat
class MockAudioFormat:
    MP3 = "mp3"


dashscope_mock.audio.tts_v2.AudioFormat = MockAudioFormat
sys.modules["dashscope"] = dashscope_mock
sys.modules["dashscope.audio"] = dashscope_mock.audio
sys.modules["dashscope.audio.tts_v2"] = dashscope_mock.audio.tts_v2

from common.audio.aliyun_streaming_tts import (
    AliyunStreamingTTS,
    StreamCallbackHandler,
    get_aliyun_tts_service,
)


class TestAliyunStreamingTTS:
    """测试阿里云TTS服务"""

    def test_tts_initialization_with_api_key(self):
        """测试使用显式API Key初始化"""
        tts = AliyunStreamingTTS(api_key="test-key")
        assert tts.api_key == "test-key"
        assert tts.default_voice == "longxiaochun"
        assert tts.default_sample_rate == 16000

    def test_tts_initialization_from_env(self, monkeypatch):
        """测试从环境变量读取API Key"""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "env-test-key")
        tts = AliyunStreamingTTS()
        assert tts.api_key == "env-test-key"

    def test_tts_initialization_without_api_key(self, monkeypatch):
        """测试未提供API Key时抛出异常"""
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY is required"):
            AliyunStreamingTTS()

    def test_voices_dict(self):
        """测试音色字典"""
        assert "longxiaochun" in AliyunStreamingTTS.VOICES
        assert "longfei" in AliyunStreamingTTS.VOICES
        assert "longyue" in AliyunStreamingTTS.VOICES
        assert "longxiaoxia" in AliyunStreamingTTS.VOICES
        assert "longtian" in AliyunStreamingTTS.VOICES

    @pytest.mark.asyncio
    async def test_tts_streaming_success(self):
        """测试流式合成成功"""
        tts = AliyunStreamingTTS(api_key="test-key")

        chunks_received = []

        async def on_chunk(audio, index, is_final):
            chunks_received.append(
                {"index": index, "size": len(audio), "is_final": is_final}
            )

        # Mock SpeechSynthesizer
        mock_synthesizer = MagicMock()
        mock_synthesizer.streaming_call = Mock()

        # Create a mock handler that returns our expected values
        mock_handler = MagicMock()
        mock_handler.wait_completion = Mock(return_value=asyncio.Future())
        mock_handler.wait_completion.return_value.set_result(None)
        mock_handler.total_duration_ms = 1000
        mock_handler.chunk_index = 5

        with patch(
            "common.audio.aliyun_streaming_tts.SpeechSynthesizer",
            return_value=mock_synthesizer,
        ):
            with patch(
                "common.audio.aliyun_streaming_tts.StreamCallbackHandler",
                return_value=mock_handler,
            ):
                result = await tts.synthesize_streaming("测试文本", on_chunk)

                assert result.is_success
                assert result.value == 1000

    @pytest.mark.asyncio
    async def test_tts_streaming_error_handling(self):
        """测试流式合成错误处理"""
        tts = AliyunStreamingTTS(api_key="test-key")

        async def on_chunk(audio, index, is_final):
            pass

        # Mock SpeechSynthesizer to raise exception
        with patch(
            "common.audio.aliyun_streaming_tts.SpeechSynthesizer",
            side_effect=Exception("API Error"),
        ):
            result = await tts.synthesize_streaming("测试文本", on_chunk)

            assert not result.is_success
            assert result.fallback == "[USE_BROWSER_TTS]"

    @pytest.mark.asyncio
    async def test_tts_to_file_success(self):
        """测试合成到文件成功"""
        tts = AliyunStreamingTTS(api_key="test-key")

        mock_synthesizer = MagicMock()
        mock_synthesizer.call = Mock()

        with patch(
            "common.audio.aliyun_streaming_tts.SpeechSynthesizer",
            return_value=mock_synthesizer,
        ):
            result = await tts.synthesize_to_file("测试文本", "/tmp/test_output.mp3")

            assert result.is_success
            assert result.value is True
            mock_synthesizer.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_tts_to_file_error(self):
        """测试合成到文件错误"""
        tts = AliyunStreamingTTS(api_key="test-key")

        with patch(
            "common.audio.aliyun_streaming_tts.SpeechSynthesizer",
            side_effect=Exception("File Error"),
        ):
            result = await tts.synthesize_to_file("测试文本", "/tmp/test_output.mp3")

            assert not result.is_success
            assert result.fallback == "[TTS_FILE_ERROR]"


class TestStreamCallbackHandler:
    """测试流式回调处理器"""

    @pytest.mark.asyncio
    async def test_callback_handler_initialization(self):
        """测试回调处理器初始化"""

        async def on_chunk(audio, index, is_final):
            pass

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        assert handler.stream_id == "test-stream-id"
        assert handler.chunk_index == 0
        assert handler.total_duration_ms == 0
        assert handler.error is None

    @pytest.mark.asyncio
    async def test_on_open(self):
        """测试连接打开回调"""

        async def on_chunk(audio, index, is_final):
            pass

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        # Should not raise
        handler.on_open()

    @pytest.mark.asyncio
    async def test_on_data(self):
        """测试接收数据回调"""
        received_chunks = []

        async def on_chunk(audio, index, is_final):
            received_chunks.append(
                {"audio": audio, "index": index, "is_final": is_final}
            )

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        # Simulate receiving audio data
        test_data = b"test audio data" * 100  # Make it large enough
        handler.on_data(test_data)

        # Wait a bit for async task to complete
        await asyncio.sleep(0.1)

        assert handler.chunk_index == 1
        assert handler.total_duration_ms > 0
        assert len(received_chunks) == 1
        assert received_chunks[0]["index"] == 0
        assert received_chunks[0]["is_final"] is False

    @pytest.mark.asyncio
    async def test_on_close(self):
        """测试连接关闭回调"""
        received_chunks = []

        async def on_chunk(audio, index, is_final):
            received_chunks.append(
                {"audio": audio, "index": index, "is_final": is_final}
            )

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        handler.on_close()

        # Wait a bit for async task to complete
        await asyncio.sleep(0.1)

        # Check that completion event is set
        assert handler.completion_event.is_set()

        # Check final chunk was sent
        assert len(received_chunks) == 1
        assert received_chunks[0]["audio"] == b""
        assert received_chunks[0]["is_final"] is True

    def test_on_error(self):
        """测试错误回调"""

        async def on_chunk(audio, index, is_final):
            pass

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        handler.on_error("Test error message")

        assert handler.error is not None
        assert str(handler.error) == "Test error message"
        assert handler.completion_event.is_set()

    @pytest.mark.asyncio
    async def test_wait_completion_success(self):
        """测试等待完成成功"""

        async def on_chunk(audio, index, is_final):
            pass

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        # Simulate completion
        handler.completion_event.set()

        # Should not raise
        await handler.wait_completion()

    @pytest.mark.asyncio
    async def test_wait_completion_with_error(self):
        """测试等待完成时出错"""

        async def on_chunk(audio, index, is_final):
            pass

        handler = StreamCallbackHandler(on_chunk=on_chunk, stream_id="test-stream-id")

        handler.error = Exception("Test error")
        handler.completion_event.set()

        with pytest.raises(Exception, match="Test error"):
            await handler.wait_completion()


class TestSingleton:
    """测试单例模式"""

    def test_get_aliyun_tts_service_singleton(self, monkeypatch):
        """测试单例函数返回同一实例"""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

        # Reset singleton
        import common.audio.aliyun_streaming_tts as tts_module

        tts_module._aliyun_tts_service = None

        service1 = get_aliyun_tts_service()
        service2 = get_aliyun_tts_service()

        assert service1 is service2
        assert isinstance(service1, AliyunStreamingTTS)

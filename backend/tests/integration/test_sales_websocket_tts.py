"""
Integration tests for Sales WebSocket TTS integration.

Tests the EnhancedSalesHandler integration with TTSServiceWithFallback.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sales_bot.websocket.enhanced_handler import EnhancedSalesHandler


class TestEnhancedSalesHandlerTTS:
    """Test EnhancedSalesHandler TTS integration."""

    @patch("sales_bot.websocket.enhanced_handler.get_tts_service_with_fallback")
    def test_handler_uses_fallback_tts(self, mock_get_fallback):
        """Test that handler uses TTSServiceWithFallback."""
        mock_tts_service = MagicMock()
        mock_get_fallback.return_value = mock_tts_service

        handler = EnhancedSalesHandler()

        assert handler.tts_service == mock_tts_service
        mock_get_fallback.assert_called_once()

    @patch("sales_bot.websocket.enhanced_handler.get_tts_service_with_fallback")
    @pytest.mark.asyncio
    async def test_tts_callback_adapter(self, mock_get_fallback):
        """Test TTS callback adapter with new signature."""
        mock_tts_service = MagicMock()
        mock_get_fallback.return_value = mock_tts_service

        handler = EnhancedSalesHandler()
        handler._is_interrupted = False
        handler.current_stream_id = "test-stream-id"
        handler.websocket = MagicMock()

        # Mock manager.send_json
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()

        # Test callback with audio data using new signature (audio_data, chunk_index, is_final)
        async def test_callback(audio_data: bytes, chunk_index: int, is_final: bool):
            # Simulate the on_chunk callback logic from _send_tts_response_streaming
            if handler._is_interrupted:
                raise asyncio.CancelledError("TTS interrupted by user")

            if handler.current_stream_id != "test-stream-id":
                raise asyncio.CancelledError("TTS stream expired")

            # Calculate duration (new signature calculation)
            duration_ms = len(audio_data) // 16 if audio_data else 0

            import base64

            audio_base64 = (
                base64.b64encode(audio_data).decode("utf-8") if audio_data else ""
            )

            message_data = {
                "chunk_index": chunk_index,
                "audio": audio_base64,
                "duration_ms": duration_ms,
                "is_final": is_final,
            }

            if is_final:
                message_data["text"] = "test text"

            await handler.manager.send_json(
                handler.websocket,
                {
                    "type": "tts_chunk",
                    "timestamp": "2024-01-01T00:00:00",
                    "stream_id": "test-stream-id",
                    "request_id": 1,
                    "data": message_data,
                },
            )

        # Test with audio data
        await test_callback(b"test audio data" * 100, 0, False)
        assert handler.manager.send_json.called

        # Verify the message structure matches new signature
        call_args = handler.manager.send_json.call_args
        message = call_args[0][1]
        assert message["type"] == "tts_chunk"
        assert message["data"]["chunk_index"] == 0
        assert message["data"]["is_final"] is False
        assert message["data"]["duration_ms"] == len(b"test audio data" * 100) // 16

    @patch("sales_bot.websocket.enhanced_handler.get_tts_service_with_fallback")
    @pytest.mark.asyncio
    async def test_tts_interruption(self, mock_get_fallback):
        """Test TTS interruption handling."""
        mock_tts_service = MagicMock()
        mock_get_fallback.return_value = mock_tts_service

        handler = EnhancedSalesHandler()
        handler._is_interrupted = True
        handler.current_stream_id = "test-stream-id"

        async def test_callback(audio_data: bytes, chunk_index: int, is_final: bool):
            if handler._is_interrupted:
                raise asyncio.CancelledError("TTS interrupted by user")

        # Test interruption raises CancelledError
        with pytest.raises(asyncio.CancelledError, match="TTS interrupted"):
            await test_callback(b"test audio", 0, False)

    @patch("sales_bot.websocket.enhanced_handler.get_tts_service_with_fallback")
    @pytest.mark.asyncio
    async def test_tts_stream_expired(self, mock_get_fallback):
        """Test TTS stream expiration handling."""
        mock_tts_service = MagicMock()
        mock_get_fallback.return_value = mock_tts_service

        handler = EnhancedSalesHandler()
        handler._is_interrupted = False
        handler.current_stream_id = "new-stream-id"  # Different from callback

        async def test_callback(audio_data: bytes, chunk_index: int, is_final: bool):
            if handler._is_interrupted:
                raise asyncio.CancelledError("TTS interrupted by user")

            if "test-stream-id" != handler.current_stream_id:
                raise asyncio.CancelledError("TTS stream expired")

        # Test stream expired raises CancelledError
        with pytest.raises(asyncio.CancelledError, match="TTS stream expired"):
            await test_callback(b"test audio", 0, False)

    @patch("sales_bot.websocket.enhanced_handler.get_tts_service_with_fallback")
    @pytest.mark.asyncio
    async def test_tts_final_chunk_includes_text(self, mock_get_fallback):
        """Test that final chunk includes text in message data."""
        mock_tts_service = MagicMock()
        mock_get_fallback.return_value = mock_tts_service

        handler = EnhancedSalesHandler()
        handler._is_interrupted = False
        handler.current_stream_id = "test-stream-id"
        handler.websocket = MagicMock()

        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()

        test_text = "This is the final response text"

        async def test_callback(audio_data: bytes, chunk_index: int, is_final: bool):
            duration_ms = len(audio_data) // 16 if audio_data else 0

            import base64

            audio_base64 = (
                base64.b64encode(audio_data).decode("utf-8") if audio_data else ""
            )

            message_data = {
                "chunk_index": chunk_index,
                "audio": audio_base64,
                "duration_ms": duration_ms,
                "is_final": is_final,
            }

            # Include text only on final chunk
            if is_final:
                message_data["text"] = test_text

            await handler.manager.send_json(
                handler.websocket,
                {
                    "type": "tts_chunk",
                    "timestamp": "2024-01-01T00:00:00",
                    "stream_id": "test-stream-id",
                    "request_id": 1,
                    "data": message_data,
                },
            )

        # Test with is_final=True
        await test_callback(b"final audio", 5, True)

        # Verify text is included in final chunk
        call_args = handler.manager.send_json.call_args
        message = call_args[0][1]
        assert message["data"]["is_final"] is True
        assert message["data"]["text"] == test_text


class TestTTSFallbackChain:
    """Test TTS fallback chain."""

    @patch("sales_bot.websocket.enhanced_handler.get_tts_service_with_fallback")
    @patch("common.audio.tts_factory.get_aliyun_tts_service")
    @patch("common.audio.tts_factory.get_tts_service")
    @pytest.mark.asyncio
    async def test_fallback_chain(
        self, mock_get_edge, mock_get_aliyun, mock_get_fallback
    ):
        """Test fallback chain: Aliyun -> Edge -> Browser."""
        from common.audio.tts_factory import (
            TTSServiceWithFallback,
            reset_tts_service_with_fallback,
        )

        # Reset singleton
        reset_tts_service_with_fallback()

        # Mock services
        mock_aliyun = MagicMock()
        mock_aliyun.api_key = "test-key"
        mock_aliyun.synthesize_streaming = AsyncMock(
            return_value=MagicMock(is_success=False, fallback="[ALIYUN_ERROR]")
        )
        mock_get_aliyun.return_value = mock_aliyun

        mock_edge = MagicMock()
        mock_edge.synthesize_streaming = AsyncMock(
            return_value=MagicMock(is_success=True, value=1000)
        )
        mock_get_edge.return_value = mock_edge

        # Create service with fallback
        service = TTSServiceWithFallback()

        async def on_chunk(audio, index, is_final):
            pass

        result = await service.synthesize_streaming("test text", on_chunk)

        # Should fallback to Edge-TTS after Aliyun fails
        mock_aliyun.synthesize_streaming.assert_called_once()
        mock_edge.synthesize_streaming.assert_called_once()
        assert result.is_success is True

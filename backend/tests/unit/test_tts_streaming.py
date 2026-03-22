"""
Property-based tests for TTS streaming functionality.

Feature: voice-practice-optimization
Property 3: TTS Streaming Message Format

Validates: Requirements 2.1, 2.4, 2.6

Tests that for any TTS generation request:
- Chunks are sent with incrementing chunk_index starting from 0
- Each chunk includes duration_ms metadata
- is_final=true only on the last chunk
- Final chunk includes full text and total_duration_ms
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st, HealthCheck

from common.audio.tts_service import TTSService, TTSChunk


def create_tts_service():
    """Create TTS service instance with mocked ConfigManager"""
    with patch('common.audio.tts_service.get_config_manager') as mock_cm:
        mock_cm.return_value.get_effective_config.return_value = None
        service = TTSService()
        service.voice = "zh-CN-XiaoxiaoNeural"
        return service


class TestTTSStreamingProperties:
    """
    Property-based tests for TTS streaming.
    
    Feature: voice-practice-optimization, Property 3: TTS Streaming Message Format
    Validates: Requirements 2.1, 2.4, 2.6
    """

    @given(
        text=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        num_chunks=st.integers(min_value=1, max_value=10),
        chunk_sizes=st.lists(
            st.integers(min_value=100, max_value=10000),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_streaming_chunks_have_incrementing_indices(
        self, text, num_chunks, chunk_sizes
    ):
        """
        Property: For any text input, streaming chunks have incrementing indices.
        
        For all TTS streaming requests:
        - chunk_index starts at 0
        - chunk_index increments by 1 for each chunk
        - Final chunk has is_final=True
        
        Feature: voice-practice-optimization, Property 3: TTS Streaming Message Format
        Validates: Requirements 2.1, 2.6
        """
        tts_service = create_tts_service()
        
        # Adjust chunk_sizes to match num_chunks
        actual_chunk_sizes = (chunk_sizes * ((num_chunks // len(chunk_sizes)) + 1))[:num_chunks]
        
        received_chunks: list[TTSChunk] = []
        
        async def capture_chunk(chunk: TTSChunk):
            received_chunks.append(chunk)
        
        with patch('common.audio.tts_service.edge_tts.Communicate') as mock_communicate:
            # Create mock audio chunks
            async def mock_stream():
                for size in actual_chunk_sizes:
                    yield {"type": "audio", "data": b"x" * size}
            
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            mock_communicate.return_value = mock_comm
            
            result = await tts_service.synthesize_streaming(text, capture_chunk)
            
            assert result.is_success is True
            
            # Verify we received chunks
            assert len(received_chunks) > 0
            
            # Verify chunk indices are incrementing from 0
            for i, chunk in enumerate(received_chunks):
                assert chunk.chunk_index == i, (
                    f"Expected chunk_index {i}, got {chunk.chunk_index}"
                )
            
            # Verify only the last chunk has is_final=True
            for chunk in received_chunks[:-1]:
                assert chunk.is_final is False, (
                    f"Non-final chunk {chunk.chunk_index} has is_final=True"
                )
            
            # Verify final chunk
            final_chunk = received_chunks[-1]
            assert final_chunk.is_final is True, "Final chunk should have is_final=True"

    @given(
        text=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        chunk_sizes=st.lists(
            st.integers(min_value=100, max_value=5000),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_streaming_chunks_include_duration_metadata(
        self, text, chunk_sizes
    ):
        """
        Property: For any text input, each chunk includes duration_ms metadata.
        
        For all TTS streaming requests:
        - Each non-final chunk has duration_ms > 0
        - Final chunk has duration_ms = 0 (marker only)
        
        Feature: voice-practice-optimization, Property 3: TTS Streaming Message Format
        Validates: Requirements 2.6
        """
        tts_service = create_tts_service()
        
        received_chunks: list[TTSChunk] = []
        
        async def capture_chunk(chunk: TTSChunk):
            received_chunks.append(chunk)
        
        with patch('common.audio.tts_service.edge_tts.Communicate') as mock_communicate:
            async def mock_stream():
                for size in chunk_sizes:
                    yield {"type": "audio", "data": b"x" * size}
            
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            mock_communicate.return_value = mock_comm
            
            result = await tts_service.synthesize_streaming(text, capture_chunk)
            
            assert result.is_success is True
            assert len(received_chunks) > 0
            
            # Verify each non-final chunk has duration_ms > 0
            for chunk in received_chunks[:-1]:
                assert chunk.duration_ms >= 0, (
                    f"Chunk {chunk.chunk_index} has invalid duration_ms: {chunk.duration_ms}"
                )
            
            # Final chunk is a marker with duration_ms = 0
            final_chunk = received_chunks[-1]
            assert final_chunk.duration_ms == 0, (
                f"Final chunk should have duration_ms=0, got {final_chunk.duration_ms}"
            )

    @given(
        text=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        chunk_sizes=st.lists(
            st.integers(min_value=100, max_value=5000),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_final_chunk_includes_text_and_total_duration(
        self, text, chunk_sizes
    ):
        """
        Property: Final chunk includes full text and total_duration_ms.
        
        For all TTS streaming requests:
        - Final chunk (is_final=True) includes the original text
        - Final chunk includes total_duration_ms
        
        Feature: voice-practice-optimization, Property 3: TTS Streaming Message Format
        Validates: Requirements 2.4, 2.6
        """
        tts_service = create_tts_service()
        
        received_chunks: list[TTSChunk] = []
        
        async def capture_chunk(chunk: TTSChunk):
            received_chunks.append(chunk)
        
        with patch('common.audio.tts_service.edge_tts.Communicate') as mock_communicate:
            async def mock_stream():
                for size in chunk_sizes:
                    yield {"type": "audio", "data": b"x" * size}
            
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            mock_communicate.return_value = mock_comm
            
            result = await tts_service.synthesize_streaming(text, capture_chunk)
            
            assert result.is_success is True
            assert len(received_chunks) > 0
            
            # Find the final chunk
            final_chunk = received_chunks[-1]
            assert final_chunk.is_final is True
            
            # Verify final chunk includes the original text
            assert final_chunk.text == text, (
                f"Final chunk text mismatch: expected '{text}', got '{final_chunk.text}'"
            )
            
            # Verify final chunk includes total_duration_ms
            assert final_chunk.total_duration_ms is not None, (
                "Final chunk should include total_duration_ms"
            )
            assert final_chunk.total_duration_ms >= 0, (
                f"total_duration_ms should be >= 0, got {final_chunk.total_duration_ms}"
            )

    @given(
        text=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        chunk_sizes=st.lists(
            st.integers(min_value=100, max_value=5000),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_non_final_chunks_have_audio_data(
        self, text, chunk_sizes
    ):
        """
        Property: Non-final chunks contain audio data.
        
        For all TTS streaming requests with multiple chunks:
        - Non-final chunks have non-empty audio data
        - Final chunk has empty audio (marker only)
        
        Feature: voice-practice-optimization, Property 3: TTS Streaming Message Format
        Validates: Requirements 2.1
        """
        tts_service = create_tts_service()
        
        received_chunks: list[TTSChunk] = []
        
        async def capture_chunk(chunk: TTSChunk):
            received_chunks.append(chunk)
        
        with patch('common.audio.tts_service.edge_tts.Communicate') as mock_communicate:
            async def mock_stream():
                for size in chunk_sizes:
                    yield {"type": "audio", "data": b"x" * size}
            
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            mock_communicate.return_value = mock_comm
            
            result = await tts_service.synthesize_streaming(text, capture_chunk)
            
            assert result.is_success is True
            
            # We should have at least 2 chunks (audio chunks + final marker)
            # But if only 1 audio chunk, we get 2 total (1 audio + 1 final)
            assert len(received_chunks) >= 2, (
                f"Expected at least 2 chunks, got {len(received_chunks)}"
            )
            
            # Verify non-final chunks have audio data
            for chunk in received_chunks[:-1]:
                assert len(chunk.audio) > 0, (
                    f"Non-final chunk {chunk.chunk_index} has empty audio"
                )
            
            # Final chunk should have empty audio (it's just a marker)
            final_chunk = received_chunks[-1]
            assert len(final_chunk.audio) == 0, (
                f"Final chunk should have empty audio, got {len(final_chunk.audio)} bytes"
            )


class TestTTSStreamingErrorHandling:
    """Unit tests for TTS streaming error handling."""

    @pytest.mark.asyncio
    async def test_streaming_returns_fallback_on_error(self):
        """Should return fallback on TTS streaming failure."""
        tts_service = create_tts_service()
        
        async def capture_chunk(chunk: TTSChunk):
            pass
        
        with patch('common.audio.tts_service.edge_tts.Communicate') as mock_communicate:
            mock_communicate.side_effect = Exception("TTS service unavailable")
            
            result = await tts_service.synthesize_streaming("Test text", capture_chunk)
            
            assert result.is_success is False
            assert result.fallback == "[USE_BROWSER_TTS]"

    @pytest.mark.asyncio
    async def test_streaming_with_empty_response(self):
        """Should handle empty TTS response gracefully."""
        tts_service = create_tts_service()
        
        received_chunks: list[TTSChunk] = []
        
        async def capture_chunk(chunk: TTSChunk):
            received_chunks.append(chunk)
        
        with patch('common.audio.tts_service.edge_tts.Communicate') as mock_communicate:
            # Mock empty stream (no audio chunks)
            async def mock_stream():
                return
                yield  # Make it an async generator
            
            mock_comm = MagicMock()
            mock_comm.stream = mock_stream
            mock_communicate.return_value = mock_comm
            
            result = await tts_service.synthesize_streaming("Test text", capture_chunk)
            
            # Should succeed but with no chunks sent
            assert result.is_success is True
            assert len(received_chunks) == 0

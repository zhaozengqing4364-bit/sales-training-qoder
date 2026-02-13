"""
Unit tests for ASR service (T031-T032)
Test ASR Service Wrapper and Delegation
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from common.audio.asr_service import ASRService
from common.audio.asr_base import ASRProvider
from common.error_handling.result import Result

@pytest.fixture
def mock_provider():
    """Create a mock ASR provider"""
    provider = Mock(spec=ASRProvider)
    provider.stream_transcribe = AsyncMock()
    provider.transcribe_file = AsyncMock()
    provider.health_check = AsyncMock()
    return provider

@pytest.fixture
def asr_service(mock_provider):
    """Create ASR service instance with mock provider"""
    # Pass provider directly to avoid ConfigManager initialization
    service = ASRService(provider=mock_provider)
    return service

class TestASRService:
    """Test ASR Service Delegation"""

    def test_asr_service_initialization(self, asr_service, mock_provider):
        """Should initialize ASR service with provider"""
        assert asr_service is not None
        assert asr_service.provider == mock_provider

    @pytest.mark.asyncio
    async def test_stream_transcribe_delegates(self, asr_service, mock_provider):
        """Should delegate stream_transcribe to provider"""
        # Setup mock to yield results
        async def mock_stream_gen(stream, rate):
            yield Result.ok("test")
        
        mock_provider.stream_transcribe = Mock(side_effect=mock_stream_gen)
        
        # Test
        stream = AsyncMock()
        results = []
        async for result in asr_service.stream_transcribe(stream, sample_rate=8000):
            results.append(result)
            
        # Verify
        assert len(results) == 1
        assert results[0].value == "test"
        mock_provider.stream_transcribe.assert_called_once_with(stream, 8000)

    @pytest.mark.asyncio
    async def test_transcribe_file_delegates(self, asr_service, mock_provider):
        """Should delegate transcribe_file to provider"""
        expected_result = Result.ok("file text")
        mock_provider.transcribe_file.return_value = expected_result
        
        result = await asr_service.transcribe_file("test.wav")
        
        assert result == expected_result
        mock_provider.transcribe_file.assert_called_once_with("test.wav")

    @pytest.mark.asyncio
    async def test_health_check_delegates(self, asr_service, mock_provider):
        """Should delegate health_check to provider"""
        expected_result = Result.ok(True)
        mock_provider.health_check.return_value = expected_result
        
        result = await asr_service.health_check()
        
        assert result == expected_result
        mock_provider.health_check.assert_called_once()

    def test_get_asr_service_singleton(self):
        """Should return singleton ASR service instance"""
        # Reset singleton
        import common.audio.asr_service as service_module
        service_module._asr_service = None
        
        # Mock ConfigManager to avoid database access
        with patch('common.audio.asr_service.get_config_manager') as mock_cm:
            mock_cm.return_value.get_effective_config.return_value = None
            
            from common.audio.asr_service import get_asr_service
            
            service1 = get_asr_service()
            service2 = get_asr_service()
            
            assert service1 is service2
            assert isinstance(service1, ASRService)


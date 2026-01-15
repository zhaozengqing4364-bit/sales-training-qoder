"""
Performance Tests for Interruption Detection
Tests that interruption detection meets <100ms latency target
"""
import asyncio
import pytest
import time


@pytest.mark.performance
class TestInterruptionLatency:
    """Performance tests for interruption detection latency"""

    @pytest.mark.asyncio
    async def test_keyword_detection_latency(self):
        """Test keyword detection is <100ms"""
        from presentation_coach.services.interruption_detector import get_interruption_detector

        detector = get_interruption_detector()

        # Test forbidden word detection (should be fast)
        context = {
            "forbidden_words": ["um", "uh", "like"],
            "required_points": [],
            "session_id": "test"
        }

        start = time.perf_counter()
        result = await detector.should_interrupt(
            "I um think this is good",
            context
        )
        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        # Keyword detection should be <100ms
        assert latency_ms < 100, f"Keyword detection took {latency_ms:.2f}ms, expected <100ms"
        assert result.is_success
        assert result.value is not None
        assert result.value["type"] == "forbidden_word"

    @pytest.mark.asyncio
    async def test_missing_point_detection_latency(self):
        """Test missing point detection is <100ms"""
        from presentation_coach.services.interruption_detector import get_interruption_detector

        detector = get_interruption_detector()

        context = {
            "forbidden_words": [],
            "required_points": ["discuss revenue", "mention growth"],
            "session_id": "test"
        }

        start = time.perf_counter()
        result = await detector.should_interrupt(
            "That's all, thank you for listening.",
            context
        )
        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        # Detection should be <100ms
        assert latency_ms < 100, f"Detection took {latency_ms:.2f}ms, expected <100ms"

    @pytest.mark.asyncio
    async def test_no_interruption_latency(self):
        """Test that no-interruption case is also fast"""
        from presentation_coach.services.interruption_detector import get_interruption_detector

        detector = get_interruption_detector()

        context = {
            "forbidden_words": [],
            "required_points": ["discuss revenue"],
            "session_id": "test"
        }

        start = time.perf_counter()
        result = await detector.should_interrupt(
            "Today I want to discuss our revenue growth.",
            context
        )
        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        # Should be <100ms even when no interruption
        assert latency_ms < 100, f"Detection took {latency_ms:.2f}ms, expected <100ms"

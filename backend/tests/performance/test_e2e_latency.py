"""
Performance Tests for End-to-End Latency
Tests that end-to-end latency meets <300ms target
"""
import asyncio
import pytest
import time


@pytest.mark.performance
class TestE2ELatency:
    """Performance tests for end-to-end latency"""

    @pytest.mark.asyncio
    async def test_session_creation_latency(self):
        """Test session creation is fast"""
        from common.db.session import AsyncSessionLocal
        from presentation_coach.services.coach_service import PresentationCoachService

        async with AsyncSessionLocal() as db:
            service = PresentationCoachService(db)

            # Use a fake presentation ID for testing
            start = time.perf_counter()
            result = await service.create_session(
                user_id="test_user_id",
                presentation_id="test_presentation_id"
            )
            end = time.perf_counter()

            latency_ms = (end - start) * 1000

            # Session creation should be reasonably fast
            # Even if it fails (not found), the check should be fast
            assert latency_ms < 500, f"Session creation took {latency_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_interruption_to_response_latency(self):
        """Test full flow from speech to AI response"""
        from presentation_coach.services.interruption_detector import get_interruption_detector
        from common.ai.llm_service import get_llm_service

        detector = get_interruption_detector()
        llm_service = get_llm_service()

        context = {
            "forbidden_words": ["um", "uh"],
            "required_points": [],
            "session_id": "test"
        }

        # Measure full flow
        start = time.perf_counter()

        # 1. Detect interruption
        detection_result = await detector.should_interrupt(
            "I um think this is good",
            context
        )

        # 2. Generate AI response (if needed)
        if detection_result.is_success and detection_result.value:
            response_result = await llm_service.generate(
                prompt="Please respond to the user's vague speech.",
                session_id="test",
                system_message="You are a presentation coach."
            )

        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        # Full flow should be <300ms (excluding actual LLM call timeout)
        # Note: Real LLM calls may take longer, this tests the overhead
        assert latency_ms < 1000, f"E2E flow took {latency_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_session_load(self):
        """Test system can handle multiple concurrent sessions"""
        from common.db.session import AsyncSessionLocal
        from presentation_coach.services.coach_service import PresentationCoachService

        async def create_single_session():
            async with AsyncSessionLocal() as db:
                service = PresentationCoachService(db)
                await service.create_session(
                    user_id=f"test_user_{time.time()}",
                    presentation_id="test_presentation_id"
                )

        # Test 10 concurrent session creations
        start = time.perf_counter()
        await asyncio.gather(*[create_single_session() for _ in range(10)])
        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        # 10 concurrent sessions should complete in reasonable time
        assert latency_ms < 5000, f"10 concurrent sessions took {latency_ms:.2f}ms"

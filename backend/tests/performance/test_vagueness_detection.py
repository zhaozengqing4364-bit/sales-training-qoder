"""
Performance Tests for Vagueness Detection
Tests that vagueness detection meets <2s latency target
"""
import pytest
import time


@pytest.mark.performance
class TestVaguenessDetection:
    """Performance tests for vagueness detection in sales conversations"""

    @pytest.mark.asyncio
    async def test_vague_response_detection_latency(self):
        """Test vagueness detection is <2s for simple responses"""
        from sales_bot.services.vagueness_detector import vagueness_detector

        test_cases = [
            "It's good",  # Vague - no specifics
            "I think so",  # Vague - uncertain
            "Maybe later",  # Vague - no commitment
            "This product has great features and saves money",  # Not vague
        ]

        for test_text in test_cases:
            start = time.perf_counter()
            result = await vagueness_detector.detect_vagueness(test_text)
            end = time.perf_counter()

            latency_ms = (end - start) * 1000

            # Vagueness detection should be <2s
            assert latency_ms < 2000, f"Detection took {latency_ms:.2f}ms for '{test_text}'"

    @pytest.mark.asyncio
    async def test_vagueness_detection_with_context(self):
        """Test vagueness detection with conversation context"""
        from sales_bot.services.vagueness_detector import vagueness_detector

        start = time.perf_counter()
        result = await vagueness_detector.detect_vagueness("It's affordable and worth it")
        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        assert latency_ms < 2000, f"Detection with context took {latency_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_bot_response_generation_latency(self):
        """Test that bot response generation is fast enough"""
        from sales_bot.services.bot_service import sales_bot_service
        from sales_bot.services.bot_service import Persona
        import uuid

        # Test with each persona
        for persona in Persona:
            # 1. Create session
            session_result = await sales_bot_service.create_session(
                user_id=uuid.uuid4(),
                persona=persona,
                scenario_id=uuid.uuid4()
            )
            if not session_result.is_success:
                continue

            session_id = session_result.value

            # 2. Start session
            await sales_bot_service.start_session(session_id)

            # 3. Process user input
            start = time.perf_counter()
            result = await sales_bot_service.process_user_input(
                session_id=session_id,
                user_text="This product costs $500"
            )
            end = time.perf_counter()

            latency_ms = (end - start) * 1000

            # Response generation should be <2s
            assert latency_ms < 2000, f"{persona} response took {latency_ms:.2f}ms"
            assert result.is_success, f"{persona} response failed"

    @pytest.mark.asyncio
    async def test_concurrent_sales_sessions(self):
        """Test that multiple concurrent sales sessions can run"""
        from sales_bot.services.bot_service import sales_bot_service
        from sales_bot.services.bot_service import Persona
        import asyncio
        import uuid

        async def create_single_conversation():
            # 1. Create session
            session_result = await sales_bot_service.create_session(
                user_id=uuid.uuid4(),
                persona=Persona.IMPATIENT_CEO,
                scenario_id=uuid.uuid4()
            )
            if not session_result.is_success:
                return

            session_id = session_result.value

            # 2. Start session
            await sales_bot_service.start_session(session_id)

            # 3. Process user input
            await sales_bot_service.process_user_input(
                session_id=session_id,
                user_text="I'd like to buy"
            )

        # Test 5 concurrent conversations
        start = time.perf_counter()
        await asyncio.gather(*[create_single_conversation() for _ in range(5)])
        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        # 5 concurrent conversations should complete in reasonable time
        assert latency_ms < 5000, f"5 concurrent sessions took {latency_ms:.2f}ms"

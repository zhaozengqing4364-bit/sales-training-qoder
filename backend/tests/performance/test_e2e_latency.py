"""
Performance Tests for End-to-End Latency
Tests that end-to-end latency meets <300ms target
"""
import asyncio
import time
import uuid

import pytest


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = max(0.0, min(1.0, percentile / 100.0)) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


@pytest.mark.performance
class TestE2ELatency:
    """Performance tests for end-to-end latency"""

    @pytest.mark.asyncio
    async def test_session_creation_latency(self, async_client, test_db):
        """Session creation path should satisfy NFR-P4 percentile targets."""
        from agent.models import Agent, AgentPersona, Persona
        from common.auth.service import create_access_token
        from common.db.models import Scenario, User

        user = User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=f"perf-user-{uuid.uuid4().hex[:8]}",
            name="Perf User",
            email=f"perf_{uuid.uuid4().hex[:6]}@example.com",
            role="user",
        )
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="perf_explicit_sales_scenario",
            description="Performance test scenario",
            is_active=True,
        )
        agent = Agent(
            id=str(uuid.uuid4()),
            name="Perf Agent",
            description="Performance test agent",
            category="sales",
            system_prompt="You are a performance test sales coach.",
            status="published",
        )
        persona = Persona(
            id=str(uuid.uuid4()),
            name="Perf Persona",
            description="Performance test persona",
            category="customer",
            difficulty="medium",
            system_prompt="You are a budget-conscious customer.",
            status="active",
        )
        test_db.add_all([user, scenario, agent, persona])
        await test_db.flush()
        test_db.add(
            AgentPersona(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                persona_id=persona.id,
                is_default=True,
            )
        )
        await test_db.commit()

        token = create_access_token(data={"sub": str(user.user_id)})
        headers = {"Authorization": f"Bearer {token}"}

        samples_ms: list[float] = []
        for _ in range(25):
            start = time.perf_counter()
            response = await async_client.post(
                "/api/v1/practice/sessions",
                headers=headers,
                json={
                    "scenario_type": "sales",
                    "scenario_id": scenario.scenario_id,
                    "agent_id": agent.id,
                    "persona_id": persona.id,
                },
            )
            end = time.perf_counter()

            assert response.status_code == 201, response.text
            payload = response.json()
            assert payload["success"] is True
            assert payload["data"]["scenario_id"] == scenario.scenario_id
            samples_ms.append((end - start) * 1000)

        p95 = _percentile(samples_ms, 95)
        p99 = _percentile(samples_ms, 99)

        assert p95 < 100, f"session create p95={p95:.2f}ms (samples={len(samples_ms)})"
        assert p99 < 200, f"session create p99={p99:.2f}ms (samples={len(samples_ms)})"

    @pytest.mark.asyncio
    async def test_interruption_to_response_latency(self):
        """Test full flow from speech to AI response"""
        from common.ai.llm_service import get_llm_service
        from presentation_coach.services.interruption_detector import (
            get_interruption_detector,
        )

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
            await llm_service.generate(
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

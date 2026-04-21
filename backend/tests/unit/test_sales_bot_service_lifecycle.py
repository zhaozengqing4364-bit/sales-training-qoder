"""Lifecycle tests for legacy SalesBotService session cleanup."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sales_bot.services.bot_service import Persona, SalesBotService


def _session(persona: Persona, last_activity_at: datetime) -> dict:
    return {
        "user_id": uuid.uuid4(),
        "scenario_id": uuid.uuid4(),
        "persona": persona,
        "chain": object(),
        "turn_count": 0,
        "total_tokens": 0,
        "start_time": None,
        "last_activity_at": last_activity_at,
    }


def test_cleanup_expired_sessions_removes_legacy_chain_state() -> None:
    service = SalesBotService(session_ttl_seconds=60, max_active_sessions=10)
    now = datetime.now(UTC)
    old_session_id = uuid.uuid4()
    active_session_id = uuid.uuid4()
    service.active_sessions[old_session_id] = _session(
        Persona.IMPATIENT_CEO,
        now - timedelta(seconds=61),
    )
    service.active_sessions[active_session_id] = _session(
        Persona.SKEPTICAL_BUYER,
        now,
    )

    expired = service.cleanup_expired_sessions(now=now)

    assert expired == [old_session_id]
    assert old_session_id not in service.active_sessions
    assert active_session_id in service.active_sessions


def test_enforce_session_limit_evicts_oldest_legacy_session() -> None:
    service = SalesBotService(session_ttl_seconds=3600, max_active_sessions=2)
    now = datetime.now(UTC)
    session_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    for index, session_id in enumerate(session_ids):
        service.active_sessions[session_id] = _session(
            Persona.PRICE_FOCUSED,
            now + timedelta(seconds=index),
        )

    evicted = service._enforce_session_limit()

    assert evicted == [session_ids[0]]
    assert session_ids[0] not in service.active_sessions
    assert set(service.active_sessions) == {session_ids[1], session_ids[2]}

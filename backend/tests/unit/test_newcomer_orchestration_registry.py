from __future__ import annotations

import pytest

from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.registry import ActivityTypeRegistry


class _Handler:
    def __init__(self, type_key: str) -> None:
        self.type_key = type_key


def test_should_register_exactly_six_handlers() -> None:
    keys = (
        "lesson",
        "quiz",
        "audio_assessment",
        "realtime_roleplay",
        "ai_coach",
        "assignment",
    )
    registry = ActivityTypeRegistry([_Handler(key) for key in keys])
    assert registry.type_keys == keys


def test_should_reject_unknown_or_duplicate_handler_types() -> None:
    with pytest.raises(NewcomerOrchestrationError) as unknown:
        ActivityTypeRegistry([_Handler("script")])
    assert unknown.value.code == "[NEWCOMER_ACTIVITY_TYPE_UNSUPPORTED]"

    with pytest.raises(NewcomerOrchestrationError) as duplicate:
        ActivityTypeRegistry([_Handler("lesson"), _Handler("lesson")])
    assert duplicate.value.code == "[NEWCOMER_ACTIVITY_TYPE_DUPLICATE]"

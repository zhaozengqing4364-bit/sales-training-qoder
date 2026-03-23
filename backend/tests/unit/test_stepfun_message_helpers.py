"""Unit tests for StepFun message persistence helper utilities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from common.error_handling.result import Result
from sales_bot.websocket.components import stepfun_message_helpers as helper_module
from sales_bot.websocket.components.stepfun_message_helpers import (
    extract_analysis_patch_fields,
    normalize_message_persistence_payload,
    patch_existing_message_analysis,
    save_stepfun_message,
)


def test_normalize_message_persistence_payload_adds_sales_stage_and_canonicalizes_analysis() -> None:
    payload = normalize_message_persistence_payload(
        turn_number=0,
        content="  用户输入  ",
        sales_stage="discovery",
        analysis_data={
            "fuzzy_words": [{"category": "uncertain"}],
            "score_snapshot": {
                "overall": 81,
                "dimension_scores": {"沟通技巧": 78, "invalid": "bad"},
                "stage_name": "需求探索",
                "ignored": "drop-me",
            },
            "ai_feedback": "建议继续确认预算。",
            "transcript_metadata": {"raw_text": "用户输入"},
            "unexpected": "drop-me",
        },
    )

    assert payload is not None
    turn, content, analysis = payload
    assert turn == 1
    assert content == "用户输入"
    assert analysis == {
        "sales_stage": "discovery",
        "fuzzy_words": [{"category": "uncertain"}],
        "score_snapshot": {
            "overall_score": 81.0,
            "dimension_scores": {"沟通技巧": 78.0},
            "stage_name": "需求探索",
        },
        "ai_feedback": "建议继续确认预算。",
        "transcript_metadata": {"raw_text": "用户输入"},
    }


def test_normalize_message_persistence_payload_returns_none_on_empty_content() -> None:
    assert (
        normalize_message_persistence_payload(
            turn_number=1,
            content="   ",
            sales_stage=None,
            analysis_data=None,
        )
        is None
    )


def test_extract_analysis_patch_fields_filters_invalid_types_and_normalizes_legacy_score() -> None:
    fields = extract_analysis_patch_fields(
        {
            "sales_stage": "presentation",
            "fuzzy_words": "invalid",
            "score_snapshot": {
                "overall": 80,
                "dimension_scores": {"专业度": 88, "invalid": "bad"},
            },
            "ai_feedback": 123,
            "transcript_metadata": {"normalized_text": "更稳定的话术"},
        }
    )

    assert fields == {
        "sales_stage": "presentation",
        "fuzzy_words": None,
        "score_snapshot": {
            "overall_score": 80.0,
            "dimension_scores": {"专业度": 88.0},
        },
        "ai_feedback": None,
        "transcript_metadata": {"normalized_text": "更稳定的话术"},
    }


@pytest.mark.asyncio
async def test_patch_existing_message_analysis_returns_true_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db_lock = MagicMock()
    db_lock.__aenter__ = AsyncMock(return_value=None)
    db_lock.__aexit__ = AsyncMock(return_value=False)

    db_obj = MagicMock()
    db_obj.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: "msg-1")
    )

    class DummyDbSessionContext:
        async def __aenter__(self):
            return db_obj

        async def __aexit__(self, exc_type, exc, tb):
            return False

    storage = MagicMock()
    storage.update_analysis = AsyncMock(return_value=Result.ok({}))

    monkeypatch.setattr(
        helper_module,
        "AsyncSessionLocal",
        lambda: DummyDbSessionContext(),
    )
    monkeypatch.setattr(helper_module, "MessageStorageService", lambda _db: storage)

    ok = await patch_existing_message_analysis(
        session_id="session-1",
        turn_number=1,
        role="user",
        content="同一条消息",
        sales_stage="discovery",
        fuzzy_words=None,
        score_snapshot={"overall": 86, "dimension_scores": {"沟通技巧": 82}},
        ai_feedback=None,
        transcript_metadata={"raw_text": "同一条消息"},
        db_lock=db_lock,
    )

    assert ok is True
    storage.update_analysis.assert_awaited_once_with(
        "msg-1",
        sales_stage="discovery",
        fuzzy_words=None,
        score_snapshot={
            "overall_score": 86.0,
            "dimension_scores": {"沟通技巧": 82.0},
        },
        ai_feedback=None,
        transcript_metadata={"raw_text": "同一条消息"},
    )


@pytest.mark.asyncio
async def test_save_stepfun_message_returns_false_on_save_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    db_lock = MagicMock()
    db_lock.__aenter__ = AsyncMock(return_value=None)
    db_lock.__aexit__ = AsyncMock(return_value=False)

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    storage = MagicMock()
    storage.save_message = AsyncMock(return_value=Result.fail("[SAVE_FAILED]"))

    monkeypatch.setattr(
        helper_module,
        "AsyncSessionLocal",
        lambda: DummyDbSessionContext(),
    )
    monkeypatch.setattr(helper_module, "MessageStorageService", lambda _db: storage)

    ok = await save_stepfun_message(
        session_id="session-1",
        turn_number=2,
        role="assistant",
        content="AI 回复",
        analysis_payload={
            "score_snapshot": {"overall": 72},
            "ignored": "drop-me",
        },
        db_lock=db_lock,
    )

    assert ok is False
    storage.save_message.assert_awaited_once_with(
        session_id="session-1",
        turn_number=2,
        role="assistant",
        content="AI 回复",
        analysis_data={"score_snapshot": {"overall_score": 72.0}},
    )

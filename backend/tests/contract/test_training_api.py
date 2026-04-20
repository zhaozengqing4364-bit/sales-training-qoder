"""Contract tests for the training API response envelope."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from common.api import training as training_api


class _RowsResult:
    def __iter__(self):
        return iter(
            [
                SimpleNamespace(category="sales", count=2),
                SimpleNamespace(category="presentation", count=1),
            ]
        )


class _TrainingCategoriesDb:
    async def execute(self, _stmt):
        return _RowsResult()


class _FailingDb:
    async def execute(self, _stmt):
        raise SQLAlchemyError("training unavailable")


@pytest.mark.asyncio
async def test_training_categories_use_common_success_envelope() -> None:
    payload = await training_api.get_training_categories(db=_TrainingCategoriesDb())

    assert payload["success"] is True
    assert "trace_id" in payload
    assert "data" in payload
    categories = {item["id"]: item for item in payload["data"]}
    assert categories["sales"]["agent_count"] == 2
    assert categories["presentation"]["agent_count"] == 1


@pytest.mark.asyncio
async def test_training_categories_use_common_error_envelope() -> None:
    payload = await training_api.get_training_categories(db=_FailingDb())

    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"] == "[TRAINING_CATEGORIES_FAILED]"
    assert payload["message"] == "获取训练分类失败"
    assert "trace_id" in payload


@pytest.mark.asyncio
async def test_training_sessions_error_uses_common_error_envelope() -> None:
    payload = await training_api.get_sessions(
        limit=20,
        page=1,
        page_size=20,
        sort="start_time:desc",
        current_user=SimpleNamespace(user_id="user-1"),
        db=_FailingDb(),
    )

    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"] == "[SESSIONS_FAILED]"
    assert payload["message"] == "获取会话历史失败"
    assert "trace_id" in payload

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from newcomer_training.application import CommandActor
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.notifications import (
    NotificationInboxQueryService,
    NotificationRecord,
)


class FakeNotificationReader:
    def __init__(self, records: tuple[NotificationRecord, ...]) -> None:
        self.records = records
        self.calls: list[dict[str, object]] = []

    async def list_for_user(self, **kwargs):
        self.calls.append(kwargs)
        return self.records, len(self.records)


@pytest.mark.asyncio
async def test_notification_inbox_is_owner_scoped_and_hides_internal_sources() -> None:
    reader = FakeNotificationReader(
        (
            NotificationRecord(
                notification_id="notice-1",
                notification_type="reminder",
                title="录音评估已完成",
                content="结果已保存，可以返回查看反馈。",
                action_label="查看录音反馈",
                action_path="/newcomer-training/activities/audio-1",
                source="newcomer_training:task:task-1",
                is_read=False,
                created_at=datetime(2026, 7, 17, tzinfo=UTC),
            ),
        )
    )
    actor = CommandActor(
        organization_id="org-1",
        actor_id="learner-1",
        capabilities=frozenset({"newcomer.journey.read"}),
    )

    page = await NotificationInboxQueryService(reader).get_my_notifications(
        actor=actor,
        read_state="unread",
        page=1,
        page_size=20,
    )

    assert reader.calls[0]["user_id"] == "learner-1"
    assert page.total == 1
    assert page.items[0].created_from == "后台任务"
    assert page.items[0].action_path == "/newcomer-training/activities/audio-1"
    assert "task-1" not in page.model_dump_json()


@pytest.mark.asyncio
async def test_notification_inbox_drops_unsafe_result_location() -> None:
    reader = FakeNotificationReader(
        (
            NotificationRecord(
                notification_id="notice-2",
                notification_type="system",
                title="训练提醒",
                content="请返回训练路径。",
                action_label="打开外部页面",
                action_path="https://example.invalid/unsafe",
                source="newcomer_training:review:decision-1",
                is_read=True,
                created_at=datetime(2026, 7, 17, tzinfo=UTC),
            ),
        )
    )
    actor = CommandActor(
        organization_id="org-1",
        actor_id="learner-1",
        capabilities=frozenset({"newcomer.journey.read"}),
    )

    page = await NotificationInboxQueryService(reader).get_my_notifications(
        actor=actor
    )

    assert page.items[0].created_from == "达标复核"
    assert page.items[0].action_label is None
    assert page.items[0].action_path is None


@pytest.mark.asyncio
async def test_notification_inbox_rejects_missing_capability() -> None:
    reader = FakeNotificationReader(())
    actor = CommandActor(
        organization_id="org-1",
        actor_id="learner-1",
        capabilities=frozenset(),
    )

    with pytest.raises(NewcomerTrainingError) as caught:
        await NotificationInboxQueryService(reader).get_my_notifications(actor=actor)

    assert caught.value.status_code == 403
    assert reader.calls == []

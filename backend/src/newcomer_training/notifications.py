"""Owner-scoped, read-only notification inbox contract for foundation learners."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from newcomer_training.application import CommandActor
from newcomer_training.errors import NewcomerTrainingError

NotificationReadState = Literal["all", "unread", "read"]
NotificationSort = Literal["-created_at", "created_at"]


class NotificationRecord(BaseModel):
    """Internal projection returned by an infrastructure adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    notification_id: str
    notification_type: str
    title: str
    content: str
    action_label: str | None
    action_path: str | None
    source: str | None
    is_read: bool
    created_at: datetime


class NotificationItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    notification_id: str
    notification_type: str
    type_label: str
    title: str
    content: str
    action_label: str | None
    action_path: str | None
    created_from: str
    is_read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["notification_page_v1"] = "notification_page_v1"
    items: tuple[NotificationItem, ...]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_more: bool


class FoundationNotificationReadPort(Protocol):
    async def list_for_user(
        self,
        *,
        user_id: str,
        read_state: NotificationReadState,
        notification_type: str | None,
        created_from: datetime | None,
        page: int,
        page_size: int,
        sort: NotificationSort,
    ) -> tuple[tuple[NotificationRecord, ...], int]: ...


class NotificationInboxQueryService:
    """Maps persisted notification records to a learner-safe inbox projection."""

    _TYPE_LABELS = {
        "system": "系统提醒",
        "tip": "训练提示",
        "reminder": "待办提醒",
        "achievement": "训练进展",
        "ai_coach": "教练反馈",
    }

    def __init__(self, reader: FoundationNotificationReadPort) -> None:
        self._reader = reader

    async def get_my_notifications(
        self,
        *,
        actor: CommandActor,
        read_state: NotificationReadState = "all",
        notification_type: str | None = None,
        created_from: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: NotificationSort = "-created_at",
    ) -> NotificationPage:
        if "newcomer.journey.read" not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有查看训练通知的权限。", 403
            )
        records, total = await self._reader.list_for_user(
            user_id=actor.actor_id,
            read_state=read_state,
            notification_type=notification_type,
            created_from=created_from,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        items = tuple(self._safe_item(record) for record in records)
        return NotificationPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

    @classmethod
    def _safe_item(cls, record: NotificationRecord) -> NotificationItem:
        action_path = record.action_path
        if action_path and not action_path.startswith(
            ("/newcomer-training", "/history?source=newcomer-training")
        ):
            action_path = None
        source = record.source or ""
        if source.startswith("newcomer_training:task:"):
            created_from = "后台任务"
        elif source.startswith("newcomer_training:review:"):
            created_from = "达标复核"
        elif source.startswith("newcomer_training:retraining:"):
            created_from = "补练安排"
        else:
            created_from = "新人训练"
        return NotificationItem(
            notification_id=record.notification_id,
            notification_type=record.notification_type,
            type_label=cls._TYPE_LABELS.get(
                record.notification_type, "训练提醒"
            ),
            title=record.title,
            content=record.content,
            action_label=record.action_label if action_path else None,
            action_path=action_path,
            created_from=created_from,
            is_read=record.is_read,
            created_at=record.created_at,
        )


__all__ = [
    "FoundationNotificationReadPort",
    "NotificationInboxQueryService",
    "NotificationPage",
    "NotificationReadState",
    "NotificationRecord",
    "NotificationSort",
]

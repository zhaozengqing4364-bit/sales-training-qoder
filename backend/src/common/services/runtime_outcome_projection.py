from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, User
from common.db.typing import json_dict_or_empty, json_dict_value, orm_scalar


@dataclass(frozen=True, slots=True)
class RuntimeOutcomeProjection:
    source_record_id: str
    user_id: str
    status: str
    score: float | None
    max_score: float | None
    passed: bool | None
    submitted_at: datetime | None
    completed_at: datetime | None
    snapshot: dict[str, Any]
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None


class RuntimeOutcomeProjectionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_completed_for_external_binding(
        self,
        *,
        owner: str,
        user_id: str,
        path_revision_id: str,
        path_revision_no: int,
        module_key: str,
        limit: int = 50,
    ) -> list[RuntimeOutcomeProjection]:
        result = await self._db.execute(
            select(PracticeSession)
            .where(
                PracticeSession.user_id == user_id,
                PracticeSession.voice_mode == "stepfun_realtime",
                PracticeSession.status == "completed",
                PracticeSession.archived.is_(False),
            )
            .order_by(PracticeSession.end_time.desc(), PracticeSession.start_time.desc())
            .limit(limit)
        )
        projections: list[RuntimeOutcomeProjection] = []
        for session in result.scalars().all():
            binding = _external_binding(session)
            if not _binding_matches(
                binding,
                owner=owner,
                path_revision_id=path_revision_id,
                path_revision_no=path_revision_no,
                module_key=module_key,
            ):
                continue
            projections.append(_projection_from_session(session, binding))
        return projections

    def completed_external_binding_window_select(
        self,
        *,
        owner: str,
        record_type: str,
        user_id: str | None = None,
        team_department: str | None = None,
    ) -> Any:
        stmt = select(
            literal(record_type).label("record_type"),
            PracticeSession.session_id.label("record_id"),
            PracticeSession.end_time.label("submitted_at"),
        ).where(*_completed_external_binding_filters(owner=owner))
        if user_id:
            stmt = stmt.where(PracticeSession.user_id == user_id)
        if team_department is not None:
            stmt = stmt.join(User, PracticeSession.user_id == User.user_id)
            stmt = stmt.where(User.department == team_department)
        return stmt

    async def get_completed_external_binding(
        self,
        *,
        owner: str,
        source_record_id: str,
    ) -> RuntimeOutcomeProjection | None:
        result = await self._db.execute(
            select(PracticeSession)
            .where(
                PracticeSession.session_id == source_record_id,
                *_completed_external_binding_filters(owner=owner),
            )
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None
        binding = _external_binding(session)
        return _projection_from_session(session, binding)

    async def list_completed_external_bindings_by_ids(
        self,
        *,
        owner: str,
        source_record_ids: list[str],
    ) -> list[RuntimeOutcomeProjection]:
        if not source_record_ids:
            return []
        result = await self._db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id.in_(source_record_ids),
                *_completed_external_binding_filters(owner=owner),
            )
        )
        projections = [
            _projection_from_session(session, _external_binding(session))
            for session in result.scalars().all()
        ]
        order = {record_id: index for index, record_id in enumerate(source_record_ids)}
        return sorted(
            projections,
            key=lambda item: order.get(item.source_record_id, len(order)),
        )


def _external_binding(session: PracticeSession) -> dict[str, Any]:
    snapshot = json_dict_or_empty(session.voice_policy_snapshot)
    external_binding: dict[str, Any] = json_dict_or_empty(
        snapshot.get("external_binding")
    )
    return external_binding


def _completed_external_binding_filters(*, owner: str) -> tuple[Any, ...]:
    return (
        PracticeSession.voice_mode == "stepfun_realtime",
        PracticeSession.status == "completed",
        PracticeSession.archived.is_(False),
        PracticeSession.voice_policy_snapshot["external_binding"]["owner"].as_string()
        == owner,
    )


def _binding_matches(
    binding: dict[str, Any],
    *,
    owner: str,
    path_revision_id: str,
    path_revision_no: int,
    module_key: str,
) -> bool:
    return (
        str(binding.get("owner") or "") == owner
        and str(binding.get("path_revision_id") or "") == path_revision_id
        and int(binding.get("path_revision_no") or 0) == int(path_revision_no)
        and str(binding.get("module_key") or "") == module_key
    )


def _projection_from_session(
    session: PracticeSession,
    binding: dict[str, Any],
) -> RuntimeOutcomeProjection:
    voice_policy_snapshot = json_dict_value(session.voice_policy_snapshot) or {}
    effectiveness_snapshot = json_dict_value(session.effectiveness_snapshot) or {}
    runtime_state = json_dict_value(session.runtime_state) or {}

    return RuntimeOutcomeProjection(
        source_record_id=orm_scalar(session.session_id, str),
        user_id=orm_scalar(session.user_id, str),
        status="scored",
        score=_overall_score(session),
        max_score=100.0,
        passed=None,
        submitted_at=orm_scalar(session.start_time, datetime, nullable=True),
        completed_at=orm_scalar(session.end_time, datetime, nullable=True),
        path_revision_id=_optional_str(binding.get("path_revision_id")),
        path_revision_no=_optional_int(binding.get("path_revision_no")),
        module_key=_optional_str(binding.get("module_key")),
        snapshot={
            "external_binding": dict(binding),
            "voice_policy_snapshot": voice_policy_snapshot,
            "effectiveness_snapshot": effectiveness_snapshot,
            "runtime_state": runtime_state,
            "scores": {
                "logic_score": orm_scalar(session.logic_score, float, nullable=True),
                "accuracy_score": orm_scalar(
                    session.accuracy_score,
                    float,
                    nullable=True,
                ),
                "completeness_score": orm_scalar(
                    session.completeness_score,
                    float,
                    nullable=True,
                ),
            },
        },
    )


def _overall_score(session: PracticeSession) -> float | None:
    scores = [
        float(score)
        for score in (
            orm_scalar(session.logic_score, float, nullable=True),
            orm_scalar(session.accuracy_score, float, nullable=True),
            orm_scalar(session.completeness_score, float, nullable=True),
        )
        if score is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None

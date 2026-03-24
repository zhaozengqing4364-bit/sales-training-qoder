"""Evidence-backed support runtime release-health aggregation."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.conversation.models import ConversationMessage
from common.conversation.runtime_diagnostics import (
    build_session_runtime_diagnostics,
    extract_voice_policy_snapshot,
)
from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import PracticeSession, SystemLog
from common.monitoring.logger import get_logger
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

logger = get_logger(__name__)

ACTIVE_SESSION_STATUSES = {"preparing", "in_progress", "paused"}
TERMINAL_SCORING_STATUS = "scoring"
TERMINAL_COMPLETED_STATUS = "completed"
DEFAULT_STUCK_SCORING_AFTER = timedelta(minutes=10)


@dataclass(slots=True)
class RuntimeSessionRecord:
    session: Any
    scenario_type: str
    knowledge_diagnostics: dict[str, Any]
    projection: Any | None = None
    projection_error: str | None = None
    presentation_review: dict[str, Any] | None = None


class RuntimeStatusService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        stuck_scoring_after: timedelta = DEFAULT_STUCK_SCORING_AFTER,
    ) -> None:
        self.db = db
        self.stuck_scoring_after = stuck_scoring_after

    async def get_overview(self, *, window_hours: int = 24) -> dict[str, Any]:
        snapshot = await self._build_release_health_snapshot(window_hours=window_hours)
        return snapshot["overview"]

    async def get_faults(
        self,
        *,
        limit: int = 20,
        severity: str | None = None,
        window_hours: int = 24,
    ) -> dict[str, Any]:
        snapshot = await self._build_release_health_snapshot(window_hours=window_hours)
        return self.build_faults_payload(
            snapshot["records"],
            now=snapshot["now"],
            limit=limit,
            severity=severity,
            supplemental_logs=snapshot["supplemental_logs"],
        )

    async def _build_release_health_snapshot(
        self,
        *,
        window_hours: int,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=window_hours)
        sessions = await self._load_recent_sessions(window_start=window_start)
        messages_by_session = await self._load_messages_by_session(
            sessions=[session for session in sessions if session.status == TERMINAL_COMPLETED_STATUS]
        )
        records = await self._build_runtime_records(
            sessions=sessions,
            messages_by_session=messages_by_session,
        )
        supplemental_logs = await self._load_supplemental_logs(window_start=window_start)
        faults = self.build_faults_payload(
            records,
            now=now,
            limit=100,
            severity=None,
            supplemental_logs=supplemental_logs,
        )
        overview = self.build_overview_payload(
            records,
            fault_items=faults["items"],
            now=now,
            window_hours=window_hours,
            supplemental_logs=supplemental_logs,
        )

        logger.info(
            "support_runtime_release_health_built",
            window_hours=window_hours,
            session_count=len(records),
            blocking_count=overview["release_health"]["blocking_count"],
            warning_count=overview["release_health"]["warning_count"],
            supplemental_warning_log_count=overview["release_health"][
                "supplemental_warning_log_count"
            ],
            scoring_sessions=overview["session_health"]["scoring_sessions"],
            stuck_scoring_sessions=overview["session_health"]["stuck_scoring_sessions"],
        )

        return {
            "overview": overview,
            "records": records,
            "supplemental_logs": supplemental_logs,
            "now": now,
        }

    async def _load_recent_sessions(
        self,
        *,
        window_start: datetime,
    ) -> list[PracticeSession]:
        result = await self.db.execute(
            select(PracticeSession)
            .options(selectinload(PracticeSession.scenario))
            .where(
                or_(
                    PracticeSession.start_time >= window_start,
                    PracticeSession.status.in_(tuple(ACTIVE_SESSION_STATUSES | {TERMINAL_SCORING_STATUS})),
                )
            )
            .order_by(PracticeSession.start_time.desc())
        )
        return list(result.scalars().all())

    async def _load_messages_by_session(
        self,
        *,
        sessions: list[PracticeSession],
    ) -> dict[str, list[ConversationMessage]]:
        session_ids = [str(session.session_id) for session in sessions]
        if not session_ids:
            return {}

        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id.in_(session_ids))
            .order_by(
                ConversationMessage.session_id,
                ConversationMessage.turn_number,
                ConversationMessage.timestamp,
            )
        )

        grouped: dict[str, list[ConversationMessage]] = {}
        for message in result.scalars().all():
            grouped.setdefault(str(message.session_id), []).append(message)
        return grouped

    async def _build_runtime_records(
        self,
        *,
        sessions: list[PracticeSession],
        messages_by_session: dict[str, list[ConversationMessage]],
    ) -> list[RuntimeSessionRecord]:
        records: list[RuntimeSessionRecord] = []
        tool_service = VoiceRuntimePolicyService(self.db)
        presentation_report_service = PresentationReportService(self.db)

        for session in sessions:
            snapshot = extract_voice_policy_snapshot(session)
            preview_tools = tool_service.build_stepfun_tools(snapshot)
            effective_tool_types = [
                str(tool.get("type") or "")
                for tool in preview_tools
                if isinstance(tool, dict)
            ]
            knowledge_diagnostics = build_session_runtime_diagnostics(
                session=session,
                snapshot=snapshot,
                effective_tool_types=effective_tool_types,
            )
            scenario_type = SessionEvidenceService.resolve_scenario_type(session)
            projection = None
            projection_error = None
            presentation_review = None

            if session.status == TERMINAL_COMPLETED_STATUS:
                try:
                    projection = SessionEvidenceService.build_projection(
                        session,
                        list(messages_by_session.get(str(session.session_id), [])),
                        scenario_type=scenario_type,
                    )
                except Exception as exc:  # noqa: BLE001
                    projection_error = f"[SESSION_EVIDENCE_FAILED] {exc}"

                if projection_error is None and scenario_type == "presentation":
                    review_result = await presentation_report_service.build_presentation_review(
                        str(session.session_id)
                    )
                    if review_result.is_success:
                        presentation_review = review_result.value
                    else:
                        projection_error = (
                            review_result.fallback or "[PRESENTATION_REVIEW_FAILED]"
                        )

            records.append(
                RuntimeSessionRecord(
                    session=session,
                    scenario_type=scenario_type,
                    knowledge_diagnostics=knowledge_diagnostics,
                    projection=projection,
                    projection_error=projection_error,
                    presentation_review=presentation_review,
                )
            )

        return records

    async def _load_supplemental_logs(
        self,
        *,
        window_start: datetime,
    ) -> list[SystemLog]:
        result = await self.db.execute(
            select(SystemLog)
            .where(
                SystemLog.created_at >= window_start,
                SystemLog.status.in_(("failed", "warning")),
            )
            .order_by(SystemLog.created_at.desc())
            .limit(100)
        )
        return list(result.scalars().all())

    @classmethod
    def build_overview_payload(
        cls,
        records: list[RuntimeSessionRecord],
        *,
        fault_items: list[dict[str, Any]],
        now: datetime,
        window_hours: int,
        supplemental_logs: list[SystemLog],
    ) -> dict[str, Any]:
        typed_items = [item for item in fault_items if item.get("source") == "session"]
        started_in_window = [
            record
            for record in records
            if cls._started_in_window(record.session, now=now, window_hours=window_hours)
        ]
        completed_in_window = [
            record for record in started_in_window if record.session.status == TERMINAL_COMPLETED_STATUS
        ]
        not_evaluable_completed = [
            record
            for record in completed_in_window
            if getattr(record.projection, "evaluable", None) is False
        ]
        scoring_records = [
            record for record in records if str(getattr(record.session, "status", "")) == TERMINAL_SCORING_STATUS
        ]
        active_sessions = [
            record
            for record in records
            if str(getattr(record.session, "status", "")) in ACTIVE_SESSION_STATUSES
        ]
        stuck_scoring_count = sum(
            1 for record in scoring_records if cls._is_stuck_scoring(record.session, now=now)
        )
        blocking_items = [item for item in typed_items if item.get("severity") == "blocking"]
        warning_items = [item for item in typed_items if item.get("severity") == "warning"]

        completion_rate = (
            round((len(completed_in_window) / len(started_in_window)) * 100, 2)
            if started_in_window
            else 0.0
        )

        return {
            "generated_at": now.isoformat(),
            "window_hours": window_hours,
            "session_health": {
                "active_sessions": len(active_sessions),
                "total_sessions_window": len(started_in_window),
                "completed_sessions_window": len(completed_in_window),
                "scoring_sessions": len(scoring_records),
                "stuck_scoring_sessions": stuck_scoring_count,
                "not_evaluable_completed_sessions_window": len(not_evaluable_completed),
                "completion_rate": completion_rate,
            },
            "release_health": {
                "status": cls._resolve_overall_status(
                    blocking_count=len(blocking_items),
                    warning_count=len(warning_items),
                    supplemental_warning_log_count=len(supplemental_logs),
                ),
                "blocking_count": len(blocking_items),
                "warning_count": len(warning_items),
                "typed_anomaly_count": len(typed_items),
                "blocking_sessions_count": len(
                    {item.get("session_id") for item in blocking_items if item.get("session_id")}
                ),
                "warning_sessions_count": len(
                    {item.get("session_id") for item in warning_items if item.get("session_id")}
                ),
                "supplemental_warning_log_count": len(supplemental_logs),
            },
            "anomaly_summary": {
                "blocking": cls._summarize_kinds(blocking_items),
                "warning": cls._summarize_kinds(warning_items),
            },
        }

    @classmethod
    def build_faults_payload(
        cls,
        records: list[RuntimeSessionRecord],
        *,
        now: datetime,
        limit: int,
        severity: str | None = None,
        supplemental_logs: list[SystemLog],
    ) -> dict[str, Any]:
        typed_items = cls._build_fault_items(records, now=now)
        supplemental_items = cls._build_supplemental_log_items(supplemental_logs)
        items = typed_items + supplemental_items
        items.sort(key=lambda item: item.get("detected_at") or "", reverse=True)

        if severity is not None:
            items = [item for item in items if item.get("severity") == severity]

        return {
            "generated_at": now.isoformat(),
            "items": items[:limit],
            "count": len(items),
            "limit": limit,
            "severity": severity,
        }

    @classmethod
    def _build_fault_items(
        cls,
        records: list[RuntimeSessionRecord],
        *,
        now: datetime,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None]] = set()

        for record in records:
            session = record.session
            session_id = str(getattr(session, "session_id", "") or "") or None
            scenario_type = record.scenario_type
            session_status = str(getattr(session, "status", "") or "")
            report_status = str(getattr(session, "report_status", "") or "")
            knowledge = (
                record.knowledge_diagnostics
                if isinstance(record.knowledge_diagnostics, dict)
                else {}
            )

            def add_item(
                *,
                severity: str,
                kind: str,
                summary: str,
                detected_at: datetime | str | None,
                diagnostics: dict[str, Any] | None = None,
            ) -> None:
                key = (kind, session_id)
                if key in seen:
                    return
                seen.add(key)
                items.append(
                    {
                        "source": "session",
                        "severity": severity,
                        "kind": kind,
                        "summary": summary,
                        "detected_at": cls._serialize_timestamp(detected_at),
                        "session_id": session_id,
                        "scenario_type": scenario_type,
                        "session_status": session_status,
                        "report_status": report_status,
                        "diagnostics": diagnostics or {},
                    }
                )

            if session_status == TERMINAL_SCORING_STATUS and cls._is_stuck_scoring(
                session, now=now
            ):
                add_item(
                    severity="blocking",
                    kind="stuck_scoring",
                    summary="会话长时间停留在 scoring，尚未进入 completed。",
                    detected_at=getattr(session, "end_time", None)
                    or getattr(session, "start_time", None),
                    diagnostics={
                        "stuck_for_minutes": cls._stuck_minutes(session, now=now),
                    },
                )

            if record.projection_error:
                add_item(
                    severity="blocking",
                    kind="projection_failed",
                    summary="统一 evidence projection 构建失败，请对照 canonical report diagnostics 排查。",
                    detected_at=getattr(session, "end_time", None)
                    or getattr(session, "start_time", None),
                    diagnostics={
                        "error_code": cls._compact_error_token(record.projection_error),
                    },
                )

            if (
                session_status == TERMINAL_COMPLETED_STATUS
                and scenario_type == "sales"
                and getattr(record.projection, "evaluable", None) is False
            ):
                add_item(
                    severity="blocking",
                    kind="not_evaluable_completed",
                    summary="会话已完成，但 unified evidence 标记为不可评估。",
                    detected_at=getattr(session, "end_time", None)
                    or getattr(session, "start_time", None),
                    diagnostics={
                        "not_evaluable_reason": getattr(
                            record.projection,
                            "not_evaluable_reason",
                            None,
                        )
                    },
                )

            if scenario_type == "presentation" and isinstance(record.presentation_review, dict):
                diagnostics = record.presentation_review.get("diagnostics")
                degraded_reasons = (
                    diagnostics.get("degraded_reasons")
                    if isinstance(diagnostics, dict)
                    else []
                )
                if isinstance(degraded_reasons, list) and "missing_page_metadata" in degraded_reasons:
                    add_item(
                        severity="warning",
                        kind="presentation_degraded_missing_page_metadata",
                        summary="PPT 会后复盘缺少页码证据，逐页总结与覆盖判断已降级。",
                        detected_at=getattr(session, "end_time", None)
                        or getattr(session, "start_time", None),
                        diagnostics={"degraded_reasons": degraded_reasons},
                    )

            if report_status == "failed":
                add_item(
                    severity="warning",
                    kind="optional_report_failed",
                    summary="增强报告生成失败，但 canonical report 仍走统一 evidence 读线。",
                    detected_at=getattr(session, "report_generated_at", None)
                    or getattr(session, "end_time", None)
                    or getattr(session, "start_time", None),
                    diagnostics={
                        "report_error_code": cls._compact_error_token(
                            getattr(session, "report_error", None)
                        )
                    },
                )

            kb_lock_status = str(knowledge.get("kb_lock_status") or "")
            if bool(knowledge.get("kb_lock_required")) and kb_lock_status.startswith(
                "blocked_"
            ):
                add_item(
                    severity="blocking",
                    kind=f"kb_lock_{kb_lock_status}",
                    summary=cls._kb_lock_summary(kb_lock_status),
                    detected_at=knowledge.get("updated_at")
                    or knowledge.get("kb_lock_updated_at")
                    or getattr(session, "end_time", None)
                    or getattr(session, "start_time", None),
                    diagnostics={
                        "kb_lock_status": kb_lock_status,
                        "status": knowledge.get("status"),
                        "last_status": knowledge.get("last_status"),
                    },
                )
            else:
                knowledge_status = str(knowledge.get("status") or "")
                if knowledge_status == "search_failed":
                    add_item(
                        severity="blocking",
                        kind="knowledge_search_failed",
                        summary=str(
                            knowledge.get("summary")
                            or "知识检索触发失败，请检查知识库或 Embedding 服务"
                        ),
                        detected_at=knowledge.get("updated_at")
                        or getattr(session, "end_time", None)
                        or getattr(session, "start_time", None),
                        diagnostics={
                            "last_status": knowledge.get("last_status"),
                            "last_error": cls._compact_error_token(
                                knowledge.get("last_error")
                            ),
                        },
                    )
                elif knowledge_status == "kb_not_ready":
                    add_item(
                        severity="blocking",
                        kind="kb_not_ready",
                        summary=str(
                            knowledge.get("summary") or "知识库文档尚未处理完成"
                        ),
                        detected_at=knowledge.get("updated_at")
                        or getattr(session, "end_time", None)
                        or getattr(session, "start_time", None),
                        diagnostics={
                            "last_status": knowledge.get("last_status"),
                        },
                    )

            if bool(knowledge.get("upstream_unstable")):
                disconnect_count = int(knowledge.get("upstream_disconnect_count_5m") or 0)
                add_item(
                    severity="warning",
                    kind="upstream_unstable",
                    summary=(
                        "上游实时链路最近 5 分钟断连次数偏高，存在不稳定迹象。"
                    ),
                    detected_at=knowledge.get("updated_at")
                    or getattr(session, "end_time", None)
                    or getattr(session, "start_time", None),
                    diagnostics={
                        "upstream_disconnect_count_5m": disconnect_count,
                    },
                )

        return items

    @staticmethod
    def _build_supplemental_log_items(logs: list[SystemLog]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for log in logs:
            items.append(
                {
                    "source": "system_log",
                    "severity": "warning",
                    "kind": f"system_log_{str(log.status)}",
                    "summary": f"系统日志告警：{log.action}",
                    "detected_at": log.created_at.isoformat() if log.created_at else None,
                    "session_id": None,
                    "scenario_type": None,
                    "session_status": None,
                    "report_status": None,
                    "diagnostics": {"log_id": str(log.log_id)},
                }
            )
        return items

    @staticmethod
    def _started_in_window(
        session: Any,
        *,
        now: datetime,
        window_hours: int,
    ) -> bool:
        start_time = getattr(session, "start_time", None)
        if not isinstance(start_time, datetime):
            return False
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        else:
            start_time = start_time.astimezone(UTC)
        return start_time >= now - timedelta(hours=window_hours)

    @classmethod
    def _is_stuck_scoring(cls, session: Any, *, now: datetime) -> bool:
        if str(getattr(session, "status", "") or "") != TERMINAL_SCORING_STATUS:
            return False
        reference_time = getattr(session, "end_time", None) or getattr(session, "start_time", None)
        if not isinstance(reference_time, datetime):
            return False
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        else:
            reference_time = reference_time.astimezone(UTC)
        return now - reference_time >= cls._stuck_scoring_after_delta()

    @classmethod
    def _stuck_minutes(cls, session: Any, *, now: datetime) -> int | None:
        reference_time = getattr(session, "end_time", None) or getattr(session, "start_time", None)
        if not isinstance(reference_time, datetime):
            return None
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        else:
            reference_time = reference_time.astimezone(UTC)
        return max(0, int((now - reference_time).total_seconds() // 60))

    @classmethod
    def _stuck_scoring_after_delta(cls) -> timedelta:
        return DEFAULT_STUCK_SCORING_AFTER

    @staticmethod
    def _serialize_timestamp(value: datetime | str | None) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            else:
                value = value.astimezone(UTC)
            return value.isoformat()
        return None

    @staticmethod
    def _resolve_overall_status(
        *,
        blocking_count: int,
        warning_count: int,
        supplemental_warning_log_count: int,
    ) -> str:
        if blocking_count > 0:
            return "blocking"
        if warning_count > 0 or supplemental_warning_log_count > 0:
            return "warning"
        return "healthy"

    @staticmethod
    def _summarize_kinds(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts = Counter(item.get("kind") for item in items if item.get("kind"))
        return [
            {"kind": kind, "count": counts[kind]}
            for kind in sorted(counts, key=lambda current: (-counts[current], str(current)))
        ]

    @staticmethod
    def _compact_error_token(value: Any) -> str | None:
        if not value:
            return None
        text = str(value)
        matches = re.findall(r"\[[^\]]+\]", text)
        if matches:
            return " ".join(matches[:3])
        compact = text.strip()
        return compact[:120] if compact else None

    @staticmethod
    def _kb_lock_summary(kb_lock_status: str) -> str:
        mapping = {
            "blocked_no_kb": "知识库锁阻塞：当前会话未绑定知识库。",
            "blocked_not_ready": "知识库锁阻塞：知识库文档尚未处理完成。",
            "blocked_search_failed": "知识库锁阻塞：知识检索触发失败。",
            "blocked_empty": "知识库锁阻塞：知识检索未命中有效内容。",
        }
        return mapping.get(
            kb_lock_status,
            f"知识库锁阻塞：{kb_lock_status}",
        )

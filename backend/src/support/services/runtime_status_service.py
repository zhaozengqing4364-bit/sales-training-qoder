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

from agent.models import Persona, VoiceRuntimeProfile
from common.conversation.models import ConversationMessage
from common.conversation.runtime_diagnostics import (
    build_session_runtime_diagnostics,
    extract_voice_policy_snapshot,
)
from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import PracticeSession, Presentation, SystemLog
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.monitoring.logger import get_logger
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from support.services.asset_registry import (
    build_empty_asset_governance_indexes,
    get_asset_registration,
    iter_asset_refs as iter_registered_asset_refs,
    supported_asset_types,
)

logger = get_logger(__name__)

ACTIVE_SESSION_STATUSES = {"preparing", "in_progress", "paused"}
TERMINAL_SCORING_STATUS = "scoring"
TERMINAL_COMPLETED_STATUS = "completed"
DEFAULT_STUCK_SCORING_AFTER = timedelta(minutes=10)


@dataclass(slots=True)
class RuntimeSessionRecord:
    session: Any
    scenario_type: str
    voice_policy_snapshot: dict[str, Any]
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
            asset_change_refs_by_session=snapshot.get("asset_change_refs_by_session"),
        )

    async def build_asset_governance_indexes(
        self,
        *,
        window_hours: int = 24 * 7,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        snapshot = await self._build_release_health_snapshot(window_hours=window_hours)
        return self._build_asset_governance_indexes_from_records(
            snapshot["records"],
            now=snapshot["now"],
            window_hours=window_hours,
        )

    @classmethod
    def build_asset_governance_summary(
        cls,
        base_entry: dict[str, Any] | None,
        *,
        last_changed_at: datetime | str | None,
        latest_change_type: str,
        latest_change_label: str,
        change_count_7d: int,
        extra_anomalies: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        entry = base_entry or {}
        last_changed_dt = cls._coerce_datetime(last_changed_at)
        started_at_values = [
            value
            for value in entry.get("started_at_values", [])
            if isinstance(value, datetime)
        ]
        sessions_since_change = 0
        if last_changed_dt is not None:
            sessions_since_change = sum(
                1
                for started_at in started_at_values
                if started_at >= last_changed_dt
            )

        anomalies = [
            cls._normalize_asset_anomaly_item(item)
            for item in entry.get("fault_items", [])
            if isinstance(item, dict)
        ]
        anomalies.extend(
            cls._normalize_asset_anomaly_item(item)
            for item in (extra_anomalies or [])
            if isinstance(item, dict)
        )
        anomalies.sort(key=lambda item: item.get("detected_at") or "", reverse=True)

        blocking_count = sum(1 for item in anomalies if item.get("severity") == "blocking")
        warning_count = sum(1 for item in anomalies if item.get("severity") == "warning")
        impacted_user_ids = entry.get("impacted_user_ids") or set()
        impacted_user_count = len(impacted_user_ids)
        recent_session_count = int(entry.get("recent_session_count") or 0)
        active_session_count = int(entry.get("active_session_count") or 0)

        return {
            "impact_summary": {
                "impact_level": cls._resolve_asset_impact_level(
                    recent_session_count=recent_session_count,
                    active_session_count=active_session_count,
                    impacted_user_count=impacted_user_count,
                    sessions_since_change=sessions_since_change,
                ),
                "recent_session_count": recent_session_count,
                "active_session_count": active_session_count,
                "impacted_user_count": impacted_user_count,
                "last_session_at": cls._serialize_timestamp(entry.get("last_session_at")),
            },
            "recent_change_summary": {
                "last_changed_at": cls._serialize_timestamp(last_changed_dt),
                "latest_change_type": latest_change_type,
                "latest_change_label": latest_change_label,
                "change_count_7d": max(0, int(change_count_7d or 0)),
                "sessions_since_change": sessions_since_change,
            },
            "health_summary": {
                "status": cls._resolve_overall_status(
                    blocking_count=blocking_count,
                    warning_count=warning_count,
                    supplemental_warning_log_count=0,
                ),
                "anomaly_count": len(anomalies),
                "blocking_count": blocking_count,
                "warning_count": warning_count,
                "sample_anomalies": anomalies[:5],
            },
        }

    @classmethod
    def _build_asset_governance_indexes_from_records(
        cls,
        records: list[RuntimeSessionRecord],
        *,
        now: datetime,
        window_hours: int,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        typed_fault_items = cls._build_fault_items(records, now=now)
        faults_by_session: dict[str, list[dict[str, Any]]] = {}
        for item in typed_fault_items:
            session_id = str(item.get("session_id") or "").strip()
            if not session_id:
                continue
            faults_by_session.setdefault(session_id, []).append(item)

        indexes = build_empty_asset_governance_indexes()

        for record in records:
            session = record.session
            session_id = str(getattr(session, "session_id", "") or "").strip()
            fault_items = faults_by_session.get(session_id, [])
            started_at = cls._coerce_datetime(getattr(session, "start_time", None))
            activity_at = cls._coerce_datetime(getattr(session, "end_time", None)) or started_at
            in_window = cls._started_in_window(session, now=now, window_hours=window_hours)
            is_active = str(getattr(session, "status", "") or "") in (
                ACTIVE_SESSION_STATUSES | {TERMINAL_SCORING_STATUS}
            )
            user_id = str(getattr(session, "user_id", "") or "").strip() or None

            for asset_type, asset_id in iter_registered_asset_refs(record):
                asset_entry = indexes[asset_type].setdefault(
                    asset_id,
                    {
                        "recent_session_count": 0,
                        "active_session_count": 0,
                        "impacted_user_ids": set(),
                        "started_at_values": [],
                        "last_session_at": None,
                        "fault_items": [],
                    },
                )

                if in_window:
                    asset_entry["recent_session_count"] += 1
                if is_active:
                    asset_entry["active_session_count"] += 1
                if user_id:
                    asset_entry["impacted_user_ids"].add(user_id)
                if started_at is not None:
                    asset_entry["started_at_values"].append(started_at)
                if activity_at is not None and (
                    asset_entry["last_session_at"] is None
                    or activity_at > asset_entry["last_session_at"]
                ):
                    asset_entry["last_session_at"] = activity_at
                if fault_items:
                    asset_entry["fault_items"].extend(fault_items)

        return indexes

    async def _build_asset_change_refs_by_session(
        self,
        *,
        records: list[RuntimeSessionRecord],
        governance_indexes: dict[str, dict[str, dict[str, Any]]],
        now: datetime,
    ) -> dict[str, list[dict[str, Any]]]:
        asset_ids: dict[str, set[str]] = {
            asset_type: set() for asset_type in supported_asset_types()
        }
        for record in records:
            for asset_type, asset_id in iter_registered_asset_refs(record):
                asset_ids[asset_type].add(asset_id)

        refs_by_asset: dict[tuple[str, str], dict[str, Any]] = {}
        seven_days_ago = now - timedelta(days=7)

        if asset_ids["knowledge_base"]:
            kb_result = await self.db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id.in_(tuple(asset_ids["knowledge_base"])))
            )
            doc_result = await self.db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.knowledge_base_id.in_(tuple(asset_ids["knowledge_base"]))
                )
            )
            docs_by_kb: dict[str, list[KnowledgeDocument]] = {}
            for document in doc_result.scalars().all():
                docs_by_kb.setdefault(str(document.knowledge_base_id), []).append(document)

            for kb in kb_result.scalars().all():
                kb_id = str(kb.id)
                documents = docs_by_kb.get(kb_id, [])
                kb_updated_at = self._coerce_datetime(getattr(kb, "updated_at", None))
                latest_document = max(
                    documents,
                    key=lambda document: self._coerce_datetime(document.created_at)
                    or datetime.min.replace(tzinfo=UTC),
                    default=None,
                )
                latest_document_created_at = (
                    self._coerce_datetime(latest_document.created_at)
                    if latest_document is not None
                    else None
                )
                last_changed_at = kb_updated_at
                latest_change_type = "knowledge_base_updated"
                latest_change_label = "知识库配置更新"
                if (
                    latest_document is not None
                    and latest_document_created_at is not None
                    and (kb_updated_at is None or latest_document_created_at >= kb_updated_at)
                ):
                    last_changed_at = latest_document_created_at
                    latest_change_type = "document_uploaded"
                    latest_change_label = f"最近文档：{latest_document.title}"

                change_count_7d = sum(
                    1
                    for document in documents
                    if (self._coerce_datetime(document.created_at) or datetime.min.replace(tzinfo=UTC))
                    >= seven_days_ago
                )
                if kb_updated_at is not None and kb_updated_at >= seven_days_ago:
                    change_count_7d += 1

                ref = self._build_asset_change_ref(
                    asset_type="knowledge_base",
                    asset_id=kb_id,
                    asset_name=str(getattr(kb, "name", "") or "知识库"),
                    governance_summary=self.build_asset_governance_summary(
                        governance_indexes.get("knowledge_base", {}).get(kb_id),
                        last_changed_at=last_changed_at,
                        latest_change_type=latest_change_type,
                        latest_change_label=latest_change_label,
                        change_count_7d=change_count_7d,
                    ),
                )
                if ref is not None:
                    refs_by_asset[("knowledge_base", kb_id)] = ref

        if asset_ids["persona"]:
            persona_result = await self.db.execute(
                select(Persona).where(Persona.id.in_(tuple(asset_ids["persona"])))
            )
            for persona in persona_result.scalars().all():
                persona_id = str(persona.id)
                updated_at = self._coerce_datetime(getattr(persona, "updated_at", None))
                ref = self._build_asset_change_ref(
                    asset_type="persona",
                    asset_id=persona_id,
                    asset_name=str(getattr(persona, "name", "") or "角色"),
                    governance_summary=self.build_asset_governance_summary(
                        governance_indexes.get("persona", {}).get(persona_id),
                        last_changed_at=updated_at,
                        latest_change_type="persona_updated",
                        latest_change_label="角色配置更新",
                        change_count_7d=1 if updated_at and updated_at >= seven_days_ago else 0,
                    ),
                )
                if ref is not None:
                    refs_by_asset[("persona", persona_id)] = ref

        if asset_ids["presentation"]:
            presentation_result = await self.db.execute(
                select(Presentation).where(
                    Presentation.presentation_id.in_(tuple(asset_ids["presentation"]))
                )
            )
            for presentation in presentation_result.scalars().all():
                presentation_id = str(presentation.presentation_id)
                upload_date = self._coerce_datetime(getattr(presentation, "upload_date", None))
                latest_change_label = (
                    f"PPT 已替换到 V{presentation.version_number}"
                    if int(getattr(presentation, "version_number", 1) or 1) > 1
                    else "PPT 已上传"
                )
                ref = self._build_asset_change_ref(
                    asset_type="presentation",
                    asset_id=presentation_id,
                    asset_name=str(getattr(presentation, "title", "") or "PPT"),
                    governance_summary=self.build_asset_governance_summary(
                        governance_indexes.get("presentation", {}).get(presentation_id),
                        last_changed_at=upload_date,
                        latest_change_type="presentation_uploaded",
                        latest_change_label=latest_change_label,
                        change_count_7d=1 if upload_date and upload_date >= seven_days_ago else 0,
                    ),
                )
                if ref is not None:
                    refs_by_asset[("presentation", presentation_id)] = ref

        if asset_ids["runtime_profile"]:
            runtime_result = await self.db.execute(
                select(VoiceRuntimeProfile).where(
                    VoiceRuntimeProfile.id.in_(tuple(asset_ids["runtime_profile"]))
                )
            )
            for profile in runtime_result.scalars().all():
                profile_id = str(profile.id)
                updated_at = self._coerce_datetime(getattr(profile, "updated_at", None))
                latest_change_label = (
                    "默认运行时配置已更新"
                    if bool(getattr(profile, "is_default", False))
                    else "运行时配置已更新"
                )
                ref = self._build_asset_change_ref(
                    asset_type="runtime_profile",
                    asset_id=profile_id,
                    asset_name=str(getattr(profile, "name", "") or "运行时配置"),
                    governance_summary=self.build_asset_governance_summary(
                        governance_indexes.get("runtime_profile", {}).get(profile_id),
                        last_changed_at=updated_at,
                        latest_change_type="runtime_profile_updated",
                        latest_change_label=latest_change_label,
                        change_count_7d=1 if updated_at and updated_at >= seven_days_ago else 0,
                    ),
                )
                if ref is not None:
                    refs_by_asset[("runtime_profile", profile_id)] = ref

        refs_by_session: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            session_id = str(getattr(record.session, "session_id", "") or "").strip()
            if not session_id:
                continue
            seen: set[tuple[str, str]] = set()
            linked_refs: list[dict[str, Any]] = []
            for ref_key in iter_registered_asset_refs(record):
                if ref_key in seen:
                    continue
                seen.add(ref_key)
                ref = refs_by_asset.get(ref_key)
                if ref is not None:
                    linked_refs.append(ref)
            linked_refs.sort(
                key=lambda item: (
                    item.get("last_changed_at") or "",
                    item.get("asset_name") or "",
                ),
                reverse=True,
            )
            if linked_refs:
                refs_by_session[session_id] = linked_refs[:3]

        return refs_by_session

    @classmethod
    def _build_asset_change_ref(
        cls,
        *,
        asset_type: str,
        asset_id: str,
        asset_name: str,
        governance_summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        recent_change = governance_summary.get("recent_change_summary") or {}
        impact_summary = governance_summary.get("impact_summary") or {}
        health_summary = governance_summary.get("health_summary") or {}
        change_count_7d = int(recent_change.get("change_count_7d") or 0)
        if change_count_7d <= 0:
            return None

        registration = get_asset_registration(asset_type)

        return {
            "asset_type": asset_type,
            "asset_label": registration.label,
            "asset_id": asset_id,
            "asset_name": asset_name,
            "admin_path": registration.build_admin_path(asset_id),
            "latest_change_label": str(recent_change.get("latest_change_label") or "最近有配置改动"),
            "latest_change_type": str(recent_change.get("latest_change_type") or "updated"),
            "last_changed_at": cls._serialize_timestamp(recent_change.get("last_changed_at")),
            "change_count_7d": change_count_7d,
            "sessions_since_change": int(recent_change.get("sessions_since_change") or 0),
            "impact_level": str(impact_summary.get("impact_level") or "low"),
            "health_status": str(health_summary.get("status") or "healthy"),
        }

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
        governance_indexes = self._build_asset_governance_indexes_from_records(
            records,
            now=now,
            window_hours=window_hours,
        )
        asset_change_refs_by_session = await self._build_asset_change_refs_by_session(
            records=records,
            governance_indexes=governance_indexes,
            now=now,
        )
        supplemental_logs = await self._load_supplemental_logs(window_start=window_start)
        faults = self.build_faults_payload(
            records,
            now=now,
            limit=100,
            severity=None,
            supplemental_logs=supplemental_logs,
            asset_change_refs_by_session=asset_change_refs_by_session,
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
            "governance_indexes": governance_indexes,
            "asset_change_refs_by_session": asset_change_refs_by_session,
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
                    voice_policy_snapshot=snapshot,
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
        asset_change_refs_by_session: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        typed_items = cls._build_fault_items(
            records,
            now=now,
            asset_change_refs_by_session=asset_change_refs_by_session,
        )
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
        asset_change_refs_by_session: dict[str, list[dict[str, Any]]] | None = None,
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
                item_diagnostics = dict(diagnostics or {})
                if session_id:
                    linked_asset_changes = (
                        asset_change_refs_by_session or {}
                    ).get(session_id, [])
                    if linked_asset_changes:
                        item_diagnostics["linked_asset_changes"] = linked_asset_changes
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
                        "diagnostics": item_diagnostics,
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
    def _coerce_datetime(value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return None

    @classmethod
    def _normalize_asset_anomaly_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "kind": str(item.get("kind") or "unknown"),
            "severity": str(item.get("severity") or "warning"),
            "summary": str(item.get("summary") or ""),
            "detected_at": cls._serialize_timestamp(item.get("detected_at")),
            "session_id": str(item.get("session_id") or "").strip() or None,
            "source": str(item.get("source") or "asset"),
        }

    @classmethod
    def _resolve_asset_impact_level(
        cls,
        *,
        recent_session_count: int,
        active_session_count: int,
        impacted_user_count: int,
        sessions_since_change: int,
    ) -> str:
        if (
            active_session_count > 0
            or recent_session_count >= 5
            or impacted_user_count >= 5
            or sessions_since_change >= 3
        ):
            return "high"
        if (
            recent_session_count >= 2
            or impacted_user_count >= 2
            or sessions_since_change >= 1
        ):
            return "medium"
        return "low"

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

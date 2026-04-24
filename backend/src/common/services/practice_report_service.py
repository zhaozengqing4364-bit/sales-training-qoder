"""Practice report and audio-segment application services."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.session_evidence import (
    SESSION_EVIDENCE_RULESET_VERSION,
    SESSION_EVIDENCE_SCORE_BASIS,
    SessionEvidenceService,
)
from common.db.models import PracticeSession, SessionAudioSegment
from common.db.schemas import ScenarioType, SessionReport
from common.db.voice_policy_snapshot import build_voice_policy_snapshot_ref
from common.effectiveness.scoring_rulesets import ScoringRulesetService
from common.monitoring.logger import get_logger
from common.oss.signing import (
    OssConfigError,
    OssSigningService,
    get_oss_signing_service,
)
from common.services.practice_session_service import (
    PracticeRetryEntryAssembler,
    PracticeServiceError,
    ensure_effectiveness_snapshot,
)

if TYPE_CHECKING:
    from common.db.schemas import AudioAuditPayloadSchema

logger = get_logger(__name__)

_AUDIO_FAILURE_TOKENS = frozenset({
    "signing_failed",
    "oss_put_failed",
    "register_failed",
    "network_error",
    "unknown",
})


class PracticeAudioAuditService:
    """Build the shared audio-audit read model used by report and replay."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_session_audio_audit(
        self,
        *,
        session_id: str,
        session: PracticeSession,
    ) -> AudioAuditPayloadSchema | None:
        from common.db.schemas import (
            AudioAuditPayloadSchema,
            AudioAuditSegmentSchema,
            AudioAuditSummarySchema,
        )

        seg_result = await self.db.execute(
            select(SessionAudioSegment)
            .where(SessionAudioSegment.session_id == session_id)
            .order_by(SessionAudioSegment.segment_sequence)
        )
        segments = list(seg_result.scalars().all())
        if not segments:
            return None

        voice_policy = session.voice_policy_snapshot or {}
        runtime_metrics = (
            voice_policy.get("runtime_metrics") if isinstance(voice_policy, dict) else None
        )
        audio_audit_raw: dict[str, Any] = {}
        if isinstance(runtime_metrics, dict):
            raw = runtime_metrics.get("audio_audit")
            if isinstance(raw, dict):
                audio_audit_raw = raw

        uploaded_count = 0
        failed_count = 0
        pending_count = 0
        total_bytes = 0
        latest_sequence: int | None = None
        last_uploaded_at: str | None = None
        segment_schemas: list[AudioAuditSegmentSchema] = []

        for seg in segments:
            if seg.upload_status == "uploaded":
                uploaded_count += 1
                total_bytes += seg.size_bytes or 0
                if latest_sequence is None or seg.segment_sequence > latest_sequence:
                    latest_sequence = seg.segment_sequence
                if seg.created_at is not None:
                    last_uploaded_at = seg.created_at.isoformat()
            elif seg.upload_status == "failed":
                failed_count += 1
            elif seg.upload_status == "pending":
                pending_count += 1

            playback_path = None
            if seg.upload_status == "uploaded":
                playback_path = (
                    f"/api/v1/sessions/{session_id}/audio-segments/{seg.segment_sequence}"
                )

            segment_schemas.append(
                AudioAuditSegmentSchema(
                    segment_sequence=seg.segment_sequence,
                    created_at=seg.created_at.isoformat() if seg.created_at else None,
                    duration_ms=seg.duration_ms,
                    size_bytes=seg.size_bytes,
                    upload_status=seg.upload_status,
                    playback_path=playback_path,
                    error_message=seg.error_message,
                )
            )

        total_segments = len(segments)
        if uploaded_count > 0 and uploaded_count == total_segments:
            learner_status = "available"
        elif uploaded_count > 0:
            learner_status = "partial"
        else:
            learner_status = "missing"

        degraded_reasons: list[str] = []
        if failed_count > 0:
            degraded_reasons.append("upload_failed")
        if pending_count > 0:
            degraded_reasons.append("segments_pending")

        summary = AudioAuditSummarySchema(
            recording_status=audio_audit_raw.get("recording_status", "active"),
            total_segments=total_segments,
            uploaded_segments=uploaded_count,
            failed_segments=failed_count,
            total_bytes=total_bytes,
            latest_segment_sequence=latest_sequence,
            storage_prefix=audio_audit_raw.get("storage_prefix", f"audio/{session_id}/"),
            last_uploaded_at=last_uploaded_at,
            learner_status=learner_status,
            degraded_reasons=degraded_reasons,
        )

        return AudioAuditPayloadSchema(summary=summary, segments=segment_schemas)


class PracticeReportService:
    """Assemble session reports on top of the shared evidence projection seam."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        evidence_service: SessionEvidenceService | None = None,
        audio_audit_service: PracticeAudioAuditService | None = None,
    ) -> None:
        self.db = db
        self.evidence_service = evidence_service or SessionEvidenceService(db)
        self.audio_audit_service = audio_audit_service or PracticeAudioAuditService(db)

    async def build_terminal_report(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        scenario_type: str,
        summary: Any | None,
        snapshot: dict[str, Any] | None,
    ) -> SessionReport:
        resolved_snapshot = snapshot or ensure_effectiveness_snapshot(session)
        if scenario_type == "presentation":
            return SessionReport(
                session_id=session.session_id,
                logic_score=session.logic_score or 0,
                accuracy_score=session.accuracy_score or 0,
                completeness_score=session.completeness_score or 0,
                overall_score=self._overall_score(session),
                suggestions=["Great practice! Keep working on your presentation skills."],
                audio_url=session.audio_url,
                transcript_url=session.transcript_url,
                voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
                    session.voice_policy_snapshot
                ),
                effectiveness_snapshot=resolved_snapshot,
                pass_flags=resolved_snapshot.get("pass_flags"),
                main_capability_passed=resolved_snapshot.get("main_capability_passed"),
                overall_result=resolved_snapshot.get("overall_result"),
                main_issue=resolved_snapshot.get("main_issue"),
                next_goal=resolved_snapshot.get("next_goal"),
                ruleset_version=str(
                    resolved_snapshot.get("version") or SESSION_EVIDENCE_RULESET_VERSION
                ),
                score_basis=SESSION_EVIDENCE_SCORE_BASIS,
                retry_entry=PracticeRetryEntryAssembler.build_retry_entry(
                    session=session,
                    scenario_type="presentation",
                ),
                audio_audit=await self.audio_audit_service.build_session_audio_audit(
                    session_id=session_id,
                    session=session,
                ),
            )

        await self._maybe_generate_comprehensive_sales_report(session_id)
        suggestions = ["会话已结束，可查看历史反馈并继续练习。"]
        if summary is not None:
            suggestions = [*summary.strengths, f"Improvement: {summary.actionable_feedback}"]

        return SessionReport(
            session_id=session_id,
            logic_score=session.logic_score or 0,
            accuracy_score=session.accuracy_score or 0,
            completeness_score=session.completeness_score or 0,
            overall_score=self._overall_score(session),
            suggestions=suggestions,
            audio_url=None,
            transcript_url=None,
            voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
                session.voice_policy_snapshot
            ),
            effectiveness_snapshot=resolved_snapshot,
            pass_flags=resolved_snapshot.get("pass_flags"),
            main_capability_passed=resolved_snapshot.get("main_capability_passed"),
            overall_result=resolved_snapshot.get("overall_result"),
            main_issue=resolved_snapshot.get("main_issue"),
            next_goal=resolved_snapshot.get("next_goal"),
            ruleset_version=str(
                resolved_snapshot.get("version") or SESSION_EVIDENCE_RULESET_VERSION
            ),
            score_basis=SESSION_EVIDENCE_SCORE_BASIS,
            retry_entry=PracticeRetryEntryAssembler.build_retry_entry(
                session=session,
                scenario_type="sales",
                main_issue=resolved_snapshot.get("main_issue"),
                next_goal=resolved_snapshot.get("next_goal"),
            ),
            audio_audit=await self.audio_audit_service.build_session_audio_audit(
                session_id=session_id,
                session=session,
            ),
        )

    async def build_session_report(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        scenario_type: str,
    ) -> SessionReport:
        projection_result = await self.evidence_service.get_projection(
            session_id=session_id,
            session=session,
            scenario_type=scenario_type,
        )
        if not projection_result.is_success:
            raise PracticeServiceError(
                "[SESSION_EVIDENCE_FAILED]",
                status_code=500,
            )

        projection = projection_result.value
        scenario_type_enum = (
            ScenarioType.PRESENTATION
            if scenario_type == "presentation"
            else ScenarioType.SALES
        )
        presentation_review = (
            projection.presentation_review
            if scenario_type_enum == ScenarioType.PRESENTATION
            else None
        )
        logic_score = projection.logic_score
        accuracy_score = projection.accuracy_score
        completeness_score = projection.completeness_score
        overall_score = projection.overall_score
        if scenario_type_enum == ScenarioType.PRESENTATION:
            (
                logic_score,
                accuracy_score,
                completeness_score,
                overall_score,
            ) = self._presentation_review_scores(
                presentation_review=presentation_review,
                fallback_logic_score=logic_score,
                fallback_accuracy_score=accuracy_score,
                fallback_completeness_score=completeness_score,
                fallback_overall_score=overall_score,
            )
        suggestions = self._projection_suggestions(
            scenario_type_enum=scenario_type_enum,
            presentation_review=presentation_review,
        )
        (
            ruleset_version,
            score_basis,
            ruleset_metadata,
        ) = await self._resolve_report_ruleset_metadata(
            scenario_type=scenario_type_enum.value,
            fallback_ruleset_version=projection.ruleset_version,
            fallback_score_basis=projection.score_basis,
        )
        evidence_completeness = projection.evidence_completeness
        canonical_evaluation_kernel = projection.canonical_evaluation_kernel
        if ruleset_metadata is not None:
            evidence_completeness = {
                **projection.evidence_completeness,
                "scoring_ruleset": ruleset_metadata,
            }
            if isinstance(canonical_evaluation_kernel, dict):
                canonical_evaluation_kernel = {
                    **canonical_evaluation_kernel,
                    "scoring_ruleset": ruleset_metadata,
                }

        report = SessionReport(
            session_id=session.session_id,
            scenario_type=scenario_type_enum,
            logic_score=logic_score,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            overall_score=overall_score,
            suggestions=suggestions,
            audio_url=session.audio_url,
            transcript_url=session.transcript_url,
            voice_policy_snapshot_ref=build_voice_policy_snapshot_ref(
                session.voice_policy_snapshot
            ),
            effectiveness_snapshot=(
                None
                if scenario_type_enum == ScenarioType.PRESENTATION
                else projection.effectiveness_snapshot
            ),
            pass_flags=(
                None if scenario_type_enum == ScenarioType.PRESENTATION else projection.pass_flags
            ),
            main_capability_passed=(
                None
                if scenario_type_enum == ScenarioType.PRESENTATION
                else projection.main_capability_passed
            ),
            overall_result=(
                None
                if scenario_type_enum == ScenarioType.PRESENTATION
                else projection.overall_result
            ),
            main_issue=(
                None if scenario_type_enum == ScenarioType.PRESENTATION else projection.main_issue
            ),
            next_goal=(
                None if scenario_type_enum == ScenarioType.PRESENTATION else projection.next_goal
            ),
            stage_summary=(
                [] if scenario_type_enum == ScenarioType.PRESENTATION else projection.stage_summary
            ),
            evaluable=(
                None if scenario_type_enum == ScenarioType.PRESENTATION else projection.evaluable
            ),
            not_evaluable_reason=(
                None
                if scenario_type_enum == ScenarioType.PRESENTATION
                else projection.not_evaluable_reason
            ),
            evidence_completeness=evidence_completeness,
            ruleset_version=ruleset_version,
            score_basis=score_basis,
            canonical_evaluation_kernel=canonical_evaluation_kernel,
            compatibility_readers=projection.compatibility_readers,
            presentation_review=presentation_review,
            retry_entry=PracticeRetryEntryAssembler.build_retry_entry(
                session=session,
                scenario_type=scenario_type,
                main_issue=projection.main_issue,
                next_goal=projection.next_goal,
            ),
            audio_audit=await self.audio_audit_service.build_session_audio_audit(
                session_id=session_id,
                session=session,
            ),
            conclusion_evidence=(
                None
                if scenario_type_enum == ScenarioType.PRESENTATION
                else projection.conclusion_evidence
            ),
            evidence_degradation=(
                None
                if scenario_type_enum == ScenarioType.PRESENTATION
                else projection.evidence_degradation
            ),
        )

        logger.info(
            "practice_session_report_built",
            session_id=session_id,
            scenario_type=scenario_type_enum.value,
            report_overall_score=report.overall_score,
            ruleset_version=report.ruleset_version,
            score_basis=report.score_basis,
            evidence_complete=evidence_completeness.get("complete"),
            presentation_page_metadata_complete=evidence_completeness.get(
                "page_metadata_complete"
            ),
            presentation_degraded_reasons=evidence_completeness.get(
                "degraded_reasons"
            ),
        )
        return report

    async def _resolve_report_ruleset_metadata(
        self,
        *,
        scenario_type: str,
        fallback_ruleset_version: str,
        fallback_score_basis: str,
    ) -> tuple[str, str, dict[str, Any] | None]:
        active = await ScoringRulesetService(self.db).get_active_or_default(scenario_type)
        if active.source == "default":
            return fallback_ruleset_version, fallback_score_basis, None
        metadata = ScoringRulesetService.report_metadata_for_view(active)
        return active.version, active.definition.score_basis, metadata

    @staticmethod
    def _presentation_review_scores(
        *,
        presentation_review: dict[str, Any] | None,
        fallback_logic_score: float,
        fallback_accuracy_score: float,
        fallback_completeness_score: float,
        fallback_overall_score: float,
    ) -> tuple[float, float, float, float]:
        """Map canonical presentation-review dimensions to report rollups."""
        if not isinstance(presentation_review, dict):
            return (
                fallback_logic_score,
                fallback_accuracy_score,
                fallback_completeness_score,
                fallback_overall_score,
            )

        dimension_scores = presentation_review.get("dimension_scores")
        if not isinstance(dimension_scores, list):
            return (
                fallback_logic_score,
                fallback_accuracy_score,
                fallback_completeness_score,
                float(presentation_review.get("overall_score") or fallback_overall_score),
            )

        by_name: dict[str, float] = {}
        for item in dimension_scores:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            try:
                by_name[name] = float(item.get("score"))
            except (TypeError, ValueError):
                continue

        completeness_dimensions = [
            by_name[name]
            for name in ["专业性", "生动性", "互动问答", "其他表现"]
            if name in by_name
        ]
        completeness_score = (
            sum(completeness_dimensions) / len(completeness_dimensions)
            if completeness_dimensions
            else fallback_completeness_score
        )

        return (
            by_name.get("流畅连贯性", fallback_logic_score),
            by_name.get("准确性", fallback_accuracy_score),
            completeness_score,
            float(presentation_review.get("overall_score") or fallback_overall_score),
        )

    @staticmethod
    def _overall_score(session: PracticeSession) -> float:
        return (
            (session.logic_score or 0)
            + (session.accuracy_score or 0)
            + (session.completeness_score or 0)
        ) / 3

    @staticmethod
    def _projection_suggestions(
        *,
        scenario_type_enum: ScenarioType,
        presentation_review: dict[str, Any] | None,
    ) -> list[str]:
        suggestions = ["Review your performance and practice again!"]
        if scenario_type_enum == ScenarioType.PRESENTATION and isinstance(
            presentation_review,
            dict,
        ):
            review_recommendations = presentation_review.get("recommendations")
            if isinstance(review_recommendations, list) and review_recommendations:
                return [str(item) for item in review_recommendations]
            return ["按页回看关键内容，并针对缺失覆盖点再练一轮。"]
        return suggestions

    async def _maybe_generate_comprehensive_sales_report(self, session_id: str) -> None:
        try:
            from common.ai.llm_service import LLMService
            from evaluation.services.comprehensive_report import (
                ComprehensiveReportService,
            )
            from evaluation.services.staged_evaluation import StagedEvaluationService
            from prompt_templates.service import PromptTemplateService

            llm_service = LLMService()
            prompt_service = PromptTemplateService(self.db)
            staged_eval_service = StagedEvaluationService(
                db_session=self.db,
                prompt_service=prompt_service,
                llm_service=llm_service,
            )
            report_service = ComprehensiveReportService(
                db_session=self.db,
                staged_eval_service=staged_eval_service,
                prompt_service=prompt_service,
                llm_service=llm_service,
            )
            comprehensive_result = await report_service.generate_report(
                session_id,
                scenario_type="sales",
            )
            if comprehensive_result.is_success:
                logger.info(
                    "Comprehensive report generated",
                    session_id=session_id,
                )
            else:
                logger.warning(
                    "Comprehensive report generation failed",
                    session_id=session_id,
                    error_code=comprehensive_result.fallback,
                )
        except (RuntimeError, ValueError, OSError, ImportError) as exc:
            logger.warning(
                "Comprehensive report generation skipped",
                session_id=session_id,
                error=str(exc),
            )


class PracticeAudioSegmentService:
    """Encapsulate OSS signing plus session audio-segment persistence."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        get_signing_service: Callable[[], Any] = get_oss_signing_service,
    ) -> None:
        self.db = db
        self.get_signing_service = get_signing_service

    def generate_upload_url(
        self,
        *,
        session_id: str,
        segment_sequence: int,
        content_type: str,
    ) -> dict[str, Any]:
        try:
            svc = self.get_signing_service()
        except OssConfigError as exc:
            raise PracticeServiceError(
                "[OSS_NOT_CONFIGURED]",
                status_code=503,
                message=str(exc),
            ) from exc

        object_key = svc.build_object_key(session_id, segment_sequence)
        presigned = svc.generate_put_url(object_key, content_type=content_type)
        return {
            "url": presigned.url,
            "object_key": presigned.object_key,
            "expires_at": presigned.expires_at,
        }

    async def create_pending_audio_segment(
        self,
        *,
        session_id: str,
        segment_sequence: int,
        object_key: str,
        content_type: str,
    ) -> None:
        existing = await self.db.execute(
            select(SessionAudioSegment).where(
                SessionAudioSegment.session_id == session_id,
                SessionAudioSegment.segment_sequence == segment_sequence,
            )
        )
        segment = existing.scalar_one_or_none()

        if segment and segment.upload_status == "uploaded":
            return

        if segment:
            segment.object_key = object_key
            segment.content_type = content_type
            segment.upload_status = "pending"
            segment.error_message = None
        else:
            self.db.add(
                SessionAudioSegment(
                    session_id=session_id,
                    segment_sequence=segment_sequence,
                    object_key=object_key,
                    content_type=content_type,
                    upload_status="pending",
                )
            )

        await self.db.commit()

    async def register_audio_segment(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        segment_sequence: int,
        object_key: str,
        size_bytes: int | None,
        duration_ms: int | None,
    ) -> dict[str, Any]:
        expected_object_key = OssSigningService.build_object_key(
            session_id,
            segment_sequence,
        )
        if object_key != expected_object_key:
            raise PracticeServiceError(
                "[AUDIO_OBJECT_KEY_MISMATCH]",
                status_code=422,
                message="object_key does not match the session segment key",
                details={
                    "expected_object_key": expected_object_key,
                    "segment_sequence": segment_sequence,
                },
            )

        existing = await self.db.execute(
            select(SessionAudioSegment).where(
                SessionAudioSegment.session_id == session_id,
                SessionAudioSegment.segment_sequence == segment_sequence,
            )
        )
        segment = existing.scalar_one_or_none()

        if segment:
            segment.object_key = object_key
            segment.upload_status = "uploaded"
            segment.error_message = None
            if not segment.content_type:
                segment.content_type = "audio/webm"
            if size_bytes is not None:
                segment.size_bytes = size_bytes
            if duration_ms is not None:
                segment.duration_ms = duration_ms
        else:
            segment = SessionAudioSegment(
                session_id=session_id,
                segment_sequence=segment_sequence,
                object_key=object_key,
                content_type="audio/webm",
                size_bytes=size_bytes,
                duration_ms=duration_ms,
                upload_status="uploaded",
            )
            self.db.add(segment)

        if session.audio_url is None:
            session.audio_url = f"audio/{session_id}/"

        await self.db.flush()
        await self._update_uploaded_audio_audit_metrics(
            session=session,
            session_id=session_id,
            segment_sequence=segment_sequence,
            object_key=object_key,
        )

        await self.db.commit()
        await self.db.refresh(segment)

        logger.info(
            "audio_segment_registered",
            session_id=session_id,
            segment_sequence=segment_sequence,
            object_key=object_key,
            upload_status="uploaded",
        )

        return {
            "id": segment.id,
            "session_id": session_id,
            "segment_sequence": segment.segment_sequence,
            "object_key": segment.object_key,
            "upload_status": segment.upload_status,
            "size_bytes": segment.size_bytes,
            "duration_ms": segment.duration_ms,
            "created_at": segment.created_at.isoformat() if segment.created_at else None,
        }

    async def list_audio_segments(self, *, session_id: str) -> list[dict[str, Any]]:
        seg_result = await self.db.execute(
            select(SessionAudioSegment)
            .where(SessionAudioSegment.session_id == session_id)
            .order_by(SessionAudioSegment.segment_sequence)
        )
        segments = seg_result.scalars().all()
        return [
            {
                "id": s.id,
                "segment_sequence": s.segment_sequence,
                "object_key": s.object_key,
                "content_type": s.content_type,
                "size_bytes": s.size_bytes,
                "duration_ms": s.duration_ms,
                "upload_status": s.upload_status,
                "error_message": s.error_message,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in segments
        ]

    async def register_audio_segment_failure(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        segment_sequence: int,
        error_token: str,
    ) -> dict[str, Any]:
        if error_token not in _AUDIO_FAILURE_TOKENS:
            raise PracticeServiceError(
                "[INVALID_ERROR_TOKEN]",
                status_code=422,
                message=(
                    "error_token must be one of: "
                    f"{', '.join(sorted(_AUDIO_FAILURE_TOKENS))}"
                ),
            )

        existing = await self.db.execute(
            select(SessionAudioSegment).where(
                SessionAudioSegment.session_id == session_id,
                SessionAudioSegment.segment_sequence == segment_sequence,
            )
        )
        segment = existing.scalar_one_or_none()

        if segment:
            if segment.upload_status != "uploaded":
                segment.upload_status = "failed"
                segment.error_message = error_token
        else:
            segment = SessionAudioSegment(
                session_id=session_id,
                segment_sequence=segment_sequence,
                object_key=f"audio/{session_id}/seg_{segment_sequence:04d}.webm",
                content_type="audio/webm",
                upload_status="failed",
                error_message=error_token,
            )
            self.db.add(segment)

        if session.audio_url is None:
            session.audio_url = f"audio/{session_id}/"

        await self.db.flush()
        await self._update_audio_audit_failure_metrics(
            session=session,
            session_id=session_id,
            error_token=error_token,
        )
        await self.db.commit()
        await self.db.refresh(session)
        await self.db.refresh(segment)

        logger.info(
            "audio_segment_failure_registered",
            session_id=session_id,
            segment_sequence=segment_sequence,
            error_token=error_token,
            upload_status="failed",
        )

        return {
            "id": segment.id,
            "session_id": session_id,
            "segment_sequence": segment.segment_sequence,
            "upload_status": segment.upload_status,
            "error_message": segment.error_message,
            "created_at": segment.created_at.isoformat() if segment.created_at else None,
        }

    async def _update_uploaded_audio_audit_metrics(
        self,
        *,
        session: PracticeSession,
        session_id: str,
        segment_sequence: int,
        object_key: str,
    ) -> None:
        audio_audit_result = await self.db.execute(
            select(
                func.count(SessionAudioSegment.id),
                func.coalesce(func.sum(SessionAudioSegment.size_bytes), 0),
            ).where(
                SessionAudioSegment.session_id == session_id,
                SessionAudioSegment.upload_status == "uploaded",
            )
        )
        uploaded_segment_count, total_uploaded_bytes = audio_audit_result.one()

        failed_count_result = await self.db.execute(
            select(func.count(SessionAudioSegment.id)).where(
                SessionAudioSegment.session_id == session_id,
                SessionAudioSegment.upload_status == "failed",
            )
        )
        failed_segment_count = failed_count_result.scalar() or 0

        base_snapshot = (
            deepcopy(session.voice_policy_snapshot)
            if isinstance(session.voice_policy_snapshot, dict)
            else {}
        )
        runtime_metrics = base_snapshot.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            runtime_metrics = {}
        else:
            runtime_metrics = deepcopy(runtime_metrics)

        audio_audit = runtime_metrics.get("audio_audit")
        if not isinstance(audio_audit, dict):
            audio_audit = {}
        else:
            audio_audit = deepcopy(audio_audit)

        audio_audit.update(
            {
                "segment_count": int(uploaded_segment_count or 0),
                "uploaded_segment_count": int(uploaded_segment_count or 0),
                "total_uploaded_bytes": int(total_uploaded_bytes or 0),
                "last_segment_sequence": segment_sequence,
                "last_object_key": object_key,
                "last_uploaded_at": datetime.now(UTC).isoformat(),
                "storage_prefix": f"audio/{session_id}/",
                "failed_segment_count": int(failed_segment_count),
            }
        )
        runtime_metrics["audio_audit"] = audio_audit
        base_snapshot["runtime_metrics"] = runtime_metrics
        session.voice_policy_snapshot = base_snapshot

    async def _update_audio_audit_failure_metrics(
        self,
        *,
        session: PracticeSession,
        session_id: str,
        error_token: str,
    ) -> None:
        failed_count_result = await self.db.execute(
            select(func.count(SessionAudioSegment.id)).where(
                SessionAudioSegment.session_id == session_id,
                SessionAudioSegment.upload_status == "failed",
            )
        )
        failed_segment_count = failed_count_result.scalar() or 0

        base_snapshot = (
            deepcopy(session.voice_policy_snapshot)
            if isinstance(session.voice_policy_snapshot, dict)
            else {}
        )
        runtime_metrics = base_snapshot.get("runtime_metrics")
        if not isinstance(runtime_metrics, dict):
            runtime_metrics = {}
        else:
            runtime_metrics = deepcopy(runtime_metrics)

        audio_audit = runtime_metrics.get("audio_audit")
        if not isinstance(audio_audit, dict):
            audio_audit = {}
        else:
            audio_audit = deepcopy(audio_audit)

        audio_audit.update(
            {
                "failed_segment_count": int(failed_segment_count),
                "last_failure_reason": error_token,
            }
        )
        runtime_metrics["audio_audit"] = audio_audit
        base_snapshot["runtime_metrics"] = runtime_metrics
        session.voice_policy_snapshot = base_snapshot


__all__ = [
    "PracticeAudioAuditService",
    "PracticeAudioSegmentService",
    "PracticeReportService",
]

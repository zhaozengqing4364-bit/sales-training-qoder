"""Minimal durable EvaluationRun state machine."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from common.business_rules.defaults import SALES_COMBINATION_RULES_KEY
from common.db.models import EvaluationRun, EvaluationRunStatus, PracticeSession

CURRICULUM_LINEAGE_KEYS = (
    "practice_template",
    "rubric",
)


def extract_curriculum_lineage(
    curriculum_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(curriculum_snapshot, dict):
        return None

    lineage = {
        key: deepcopy(curriculum_snapshot[key])
        for key in CURRICULUM_LINEAGE_KEYS
        if key in curriculum_snapshot
    }
    lineage["content_assets"] = deepcopy(curriculum_snapshot.get("content_assets") or [])
    lineage["llm_suggestions"] = deepcopy(
        curriculum_snapshot.get("llm_suggestions")
        if "llm_suggestions" in curriculum_snapshot
        else curriculum_snapshot.get("llm_nodes") or []
    )
    return lineage or None


class EvaluationRunService:
    """Persist one evaluation run per practice session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_pending_run(
        self,
        *,
        session_id: str,
        input_evidence_reference: dict[str, Any],
        config_bundle_id: str | None = None,
        config_version_id: str | None = None,
    ) -> EvaluationRun:
        existing = await self._get_run_for_session(session_id)
        if existing is not None:
            return existing

        binding = await self._resolve_config_binding(
            config_bundle_id=config_bundle_id,
            config_version_id=config_version_id,
        )

        evidence_reference = dict(input_evidence_reference)
        curriculum_lineage = await self._get_curriculum_lineage_for_session(session_id)
        if curriculum_lineage is not None:
            evidence_reference["curriculum_lineage"] = curriculum_lineage

        run = EvaluationRun(
            session_id=session_id,
            config_bundle_id=binding["config_bundle_id"],
            config_version_id=binding["config_version_id"],
            status=EvaluationRunStatus.PENDING.value,
            input_evidence_reference=evidence_reference,
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def _resolve_config_binding(
        self,
        *,
        config_bundle_id: str | None,
        config_version_id: str | None,
    ) -> dict[str, str | None]:
        if config_bundle_id is not None or config_version_id is not None:
            return {
                "config_bundle_id": config_bundle_id,
                "config_version_id": config_version_id,
            }

        active_version = await ConfigBundleLifecycleService(
            self.db
        ).resolve_active_version(SALES_COMBINATION_RULES_KEY)
        if active_version is None:
            return {"config_bundle_id": None, "config_version_id": None}
        return {
            "config_bundle_id": str(active_version.bundle_id),
            "config_version_id": str(active_version.version_id),
        }

    async def mark_running(self, run_id: str) -> EvaluationRun:
        run = await self._get_run(run_id)
        now = datetime.now(UTC)
        run.status = EvaluationRunStatus.RUNNING.value
        if run.started_at is None:
            run.started_at = now
        run.updated_at = now
        await self.db.flush()
        return run

    async def mark_succeeded(
        self,
        run_id: str,
        *,
        result_payload: dict[str, Any],
        result_summary: str | None = None,
    ) -> EvaluationRun:
        return await self._mark_terminal(
            run_id,
            status=EvaluationRunStatus.SUCCEEDED,
            result_payload=result_payload,
            result_summary=result_summary,
        )

    async def mark_non_evaluable(
        self,
        run_id: str,
        *,
        reason: str,
        result_payload: dict[str, Any] | None = None,
    ) -> EvaluationRun:
        return await self._mark_terminal(
            run_id,
            status=EvaluationRunStatus.NON_EVALUABLE,
            result_payload=result_payload,
            result_summary=reason,
        )

    async def mark_failed(
        self,
        run_id: str,
        *,
        error_message: str,
        error_trace: str | None = None,
    ) -> EvaluationRun:
        return await self._mark_terminal(
            run_id,
            status=EvaluationRunStatus.FAILED,
            error_message=error_message,
            error_trace=error_trace,
        )

    async def _mark_terminal(
        self,
        run_id: str,
        *,
        status: EvaluationRunStatus,
        result_payload: dict[str, Any] | None = None,
        result_summary: str | None = None,
        error_message: str | None = None,
        error_trace: str | None = None,
    ) -> EvaluationRun:
        run = await self._get_run(run_id)
        now = datetime.now(UTC)
        if run.started_at is None:
            run.started_at = now
        run.status = status.value
        run.finished_at = now
        run.result_payload = result_payload
        run.result_summary = result_summary
        run.error_message = error_message
        run.error_trace = error_trace
        run.updated_at = now
        await self.db.flush()
        return run

    async def _get_run_for_session(self, session_id: str) -> EvaluationRun | None:
        result = await self.db.execute(
            select(EvaluationRun).where(EvaluationRun.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def _get_curriculum_lineage_for_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            select(PracticeSession.curriculum_snapshot).where(
                PracticeSession.session_id == session_id
            )
        )
        return extract_curriculum_lineage(result.scalar_one_or_none())

    async def _get_run(self, run_id: str) -> EvaluationRun:
        result = await self.db.execute(
            select(EvaluationRun).where(EvaluationRun.run_id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise ValueError(f"EvaluationRun not found: {run_id}")
        return run

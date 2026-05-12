"""Persist stable training report snapshots."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ConfigBundle,
    ConfigVersion,
    EvaluationRun,
    TrainingReportSnapshot,
)

LEGACY_UNVERSIONED = "legacy_unversioned"


class TrainingReportSnapshotService:
    """Create one immutable final report snapshot per practice session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_snapshot(
        self,
        *,
        evaluation_run_id: str,
        report_payload: dict[str, Any],
        ruleset_source: str | None,
        ruleset_version: str | None,
        score_basis: str | None,
        non_evaluable_reason: str | None,
    ) -> TrainingReportSnapshot:
        run = await self._get_evaluation_run(evaluation_run_id)
        existing = await self._get_snapshot_for_session(str(run.session_id))
        if existing is not None:
            return existing

        metadata = self._normalized_metadata(
            report_payload=report_payload,
            ruleset_source=ruleset_source,
            ruleset_version=ruleset_version,
            score_basis=score_basis,
            non_evaluable_reason=non_evaluable_reason,
        )
        config_lineage = await self._build_config_lineage_snapshot(run, metadata)
        snapshot = TrainingReportSnapshot(
            session_id=run.session_id,
            evaluation_run_id=run.run_id,
            report_payload=dict(report_payload),
            config_bundle_id=run.config_bundle_id,
            config_bundle_snapshot=config_lineage,
            ruleset_source=metadata["ruleset_source"],
            ruleset_version=metadata["ruleset_version"],
            score_basis=metadata["score_basis"],
            evidence_completeness=metadata["evidence_completeness"],
            non_evaluable_reason=non_evaluable_reason,
            generated_at=datetime.now(UTC),
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    @staticmethod
    def _metadata_or_legacy(value: str | None) -> str:
        normalized = str(value or "").strip()
        return normalized or LEGACY_UNVERSIONED

    def _normalized_metadata(
        self,
        *,
        report_payload: dict[str, Any],
        ruleset_source: str | None,
        ruleset_version: str | None,
        score_basis: str | None,
        non_evaluable_reason: str | None,
    ) -> dict[str, Any]:
        evidence_completeness = report_payload.get("evidence_completeness")
        return {
            "ruleset_source": self._metadata_or_legacy(ruleset_source),
            "ruleset_version": self._metadata_or_legacy(ruleset_version),
            "score_basis": self._metadata_or_legacy(score_basis),
            "evidence_completeness": dict(evidence_completeness)
            if isinstance(evidence_completeness, dict)
            else {},
            "non_evaluable_reason": non_evaluable_reason,
        }

    async def _build_config_lineage_snapshot(
        self,
        run: EvaluationRun,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        legacy_snapshot = {
            "source": LEGACY_UNVERSIONED,
            "config_bundle_id": None,
            "config_version_id": None,
            "ruleset_source": metadata["ruleset_source"],
            "ruleset_version": metadata["ruleset_version"],
            "score_basis": metadata["score_basis"],
            "evidence_completeness": metadata["evidence_completeness"],
        }
        if metadata.get("non_evaluable_reason"):
            legacy_snapshot["non_evaluable_reason"] = metadata["non_evaluable_reason"]

        if not run.config_version_id:
            return legacy_snapshot

        version = await self._get_config_version(str(run.config_version_id))
        if version is None:
            return legacy_snapshot
        bundle = await self._get_config_bundle(str(version.bundle_id))
        if bundle is None:
            return legacy_snapshot

        lineage = {
            "source": "config_version",
            "config_bundle_id": str(version.bundle_id),
            "config_version_id": str(version.version_id),
            "bundle_key": bundle.bundle_key,
            "domain": bundle.domain,
            "version_number": version.version_number,
            "version_label": version.version_label,
            "status": version.status,
            "source_config_id": version.source_config_id,
            "ruleset_source": metadata["ruleset_source"],
            "ruleset_version": metadata["ruleset_version"],
            "score_basis": metadata["score_basis"],
            "evidence_completeness": metadata["evidence_completeness"],
            "config_snapshot": deepcopy(version.snapshot_json or {}),
            "source_updated_at": version.source_updated_at.isoformat()
            if version.source_updated_at
            else None,
        }
        if metadata.get("non_evaluable_reason"):
            lineage["non_evaluable_reason"] = metadata["non_evaluable_reason"]
        return lineage

    async def _get_evaluation_run(self, evaluation_run_id: str) -> EvaluationRun:
        result = await self.db.execute(
            select(EvaluationRun).where(EvaluationRun.run_id == evaluation_run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise ValueError(f"EvaluationRun not found: {evaluation_run_id}")
        return run

    async def _get_config_version(self, config_version_id: str) -> ConfigVersion | None:
        result = await self.db.execute(
            select(ConfigVersion).where(ConfigVersion.version_id == config_version_id)
        )
        return result.scalar_one_or_none()

    async def _get_config_bundle(self, config_bundle_id: str) -> ConfigBundle | None:
        result = await self.db.execute(
            select(ConfigBundle).where(ConfigBundle.bundle_id == config_bundle_id)
        )
        return result.scalar_one_or_none()

    async def _get_snapshot_for_session(
        self,
        session_id: str,
    ) -> TrainingReportSnapshot | None:
        result = await self.db.execute(
            select(TrainingReportSnapshot).where(
                TrainingReportSnapshot.session_id == session_id
            )
        )
        return result.scalar_one_or_none()

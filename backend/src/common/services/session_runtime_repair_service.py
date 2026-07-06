"""Explicit repair surface for historical runtime snapshot drift.

Runtime WebSocket paths must not rebuild missing snapshots implicitly. This
module is an operator-invoked repair path with dry-run as the default.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.db.models import PracticeSession

RUNNABLE_SESSION_STATUSES = {"preparing", "in_progress", "paused", "scoring"}
VOICE_POLICY_SCENARIO_TYPES = {"sales", "presentation"}


class VoiceRuntimePolicyResolver(Protocol):
    async def resolve_effective_policy(
        self,
        *,
        agent_id: str | None = None,
        persona_id: str | None = None,
        voice_mode_override: str | None = None,
        runtime_profile_override: str | None = None,
    ) -> dict[str, Any]: ...


VoiceRuntimePolicyResolverFactory = Callable[[AsyncSession], VoiceRuntimePolicyResolver]
_voice_runtime_policy_resolver_factory: VoiceRuntimePolicyResolverFactory | None = None


def register_voice_runtime_policy_resolver_factory(
    factory: VoiceRuntimePolicyResolverFactory,
) -> None:
    global _voice_runtime_policy_resolver_factory
    _voice_runtime_policy_resolver_factory = factory


def _build_voice_runtime_policy_resolver(db: AsyncSession) -> VoiceRuntimePolicyResolver:
    if _voice_runtime_policy_resolver_factory is None:
        raise RuntimeError("voice runtime policy resolver is not registered")
    return _voice_runtime_policy_resolver_factory(db)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


@dataclass(slots=True)
class SessionRuntimeRepairFinding:
    session_id: str
    code: str
    message: str
    repairable: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "code": self.code,
            "message": self.message,
            "repairable": self.repairable,
            "details": deepcopy(self.details),
        }


@dataclass(slots=True)
class SessionRuntimeRepairResult:
    dry_run: bool
    scanned_sessions: int = 0
    repaired_sessions: int = 0
    findings: list[SessionRuntimeRepairFinding] = field(default_factory=list)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "scanned_sessions": self.scanned_sessions,
            "finding_count": self.finding_count,
            "repaired_sessions": self.repaired_sessions,
            "findings": [finding.to_dict() for finding in self.findings],
        }


class SessionRuntimeRepairService:
    """Audit and explicitly repair historical runtime snapshot drift."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        runtime_policy_service: VoiceRuntimePolicyResolver | None = None,
    ) -> None:
        self.db = db
        self.runtime_policy_service = runtime_policy_service

    async def run(
        self,
        *,
        apply: bool = False,
        session_ids: list[str] | None = None,
        limit: int = 500,
        include_completed: bool = False,
    ) -> SessionRuntimeRepairResult:
        """Audit sessions and optionally apply repairable fixes."""

        sessions = await self._load_sessions(
            session_ids=session_ids,
            limit=limit,
            include_completed=include_completed,
        )
        result = SessionRuntimeRepairResult(dry_run=not apply)
        result.scanned_sessions = len(sessions)

        for session in sessions:
            before_finding_count = result.finding_count
            repaired = await self._audit_and_maybe_repair_session(
                session,
                apply=apply,
                result=result,
            )
            if repaired and result.finding_count > before_finding_count:
                result.repaired_sessions += 1

        if apply and result.repaired_sessions:
            await self.db.commit()
        return result

    async def _load_sessions(
        self,
        *,
        session_ids: list[str] | None,
        limit: int,
        include_completed: bool,
    ) -> list[PracticeSession]:
        stmt = select(PracticeSession).options(selectinload(PracticeSession.scenario))
        normalized_ids = [
            str(session_id).strip()
            for session_id in (session_ids or [])
            if str(session_id).strip()
        ]
        if normalized_ids:
            stmt = stmt.where(PracticeSession.session_id.in_(normalized_ids))
        if not include_completed:
            stmt = stmt.where(PracticeSession.status.in_(RUNNABLE_SESSION_STATUSES))
        stmt = stmt.order_by(PracticeSession.start_time.desc()).limit(max(1, limit))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _audit_and_maybe_repair_session(
        self,
        session: PracticeSession,
        *,
        apply: bool,
        result: SessionRuntimeRepairResult,
    ) -> bool:
        session_id = str(session.session_id)
        repaired = False

        identity_repaired = self._repair_curriculum_runtime_identity(
            session,
            apply=apply,
            result=result,
        )
        repaired = repaired or identity_repaired

        scenario_type = self._scenario_type(session)
        if (
            scenario_type in VOICE_POLICY_SCENARIO_TYPES
            and not isinstance(session.voice_policy_snapshot, dict)
        ):
            if not (session.agent_id and session.persona_id):
                result.findings.append(
                    SessionRuntimeRepairFinding(
                        session_id=session_id,
                        code="VOICE_POLICY_SNAPSHOT_MISSING_UNREPAIRABLE",
                        message=(
                            "会话缺少 voice_policy_snapshot，且缺少 agent_id/persona_id，"
                            "无法安全重建。"
                        ),
                        repairable=False,
                        details={
                            "scenario_type": scenario_type,
                            "agent_id": _optional_text(session.agent_id),
                            "persona_id": _optional_text(session.persona_id),
                        },
                    )
                )
                return repaired

            result.findings.append(
                SessionRuntimeRepairFinding(
                    session_id=session_id,
                    code="VOICE_POLICY_SNAPSHOT_MISSING",
                    message="会话缺少 voice_policy_snapshot，可按会话 runtime identity 显式重建。",
                    repairable=True,
                    details={
                        "scenario_type": scenario_type,
                        "agent_id": _optional_text(session.agent_id),
                        "persona_id": _optional_text(session.persona_id),
                        "runtime_profile_id": _optional_text(
                            session.voice_runtime_profile_id
                        ),
                    },
                )
            )
            if apply:
                await self._rebuild_voice_policy_snapshot(session)
                repaired = True

        return repaired

    def _repair_curriculum_runtime_identity(
        self,
        session: PracticeSession,
        *,
        apply: bool,
        result: SessionRuntimeRepairResult,
    ) -> bool:
        snapshot = session.curriculum_snapshot
        if not isinstance(snapshot, dict):
            return False

        runtime = snapshot.get("runtime")
        if not isinstance(runtime, dict):
            result.findings.append(
                SessionRuntimeRepairFinding(
                    session_id=str(session.session_id),
                    code="CURRICULUM_RUNTIME_MISSING",
                    message="课程会话缺少 curriculum_snapshot.runtime，不能从 live 模板回填。",
                    repairable=False,
                )
            )
            return False

        expected = {
            "agent_id": _optional_text(runtime.get("agent_id")),
            "persona_id": _optional_text(runtime.get("persona_id")),
            "voice_runtime_profile_id": _optional_text(runtime.get("runtime_profile_id")),
        }
        actual = {
            "agent_id": _optional_text(session.agent_id),
            "persona_id": _optional_text(session.persona_id),
            "voice_runtime_profile_id": _optional_text(session.voice_runtime_profile_id),
        }
        mismatches = {
            key: {"session": actual[key], "snapshot": expected[key]}
            for key in expected
            if expected[key] and actual[key] != expected[key]
        }
        if not mismatches:
            return False

        repairable = all(expected.values())
        result.findings.append(
            SessionRuntimeRepairFinding(
                session_id=str(session.session_id),
                code="CURRICULUM_RUNTIME_IDENTITY_MISMATCH",
                message="session runtime identity 与冻结 curriculum_snapshot.runtime 不一致。",
                repairable=repairable,
                details={"mismatches": mismatches},
            )
        )
        if not apply or not repairable:
            return False

        session.agent_id = expected["agent_id"]
        session.persona_id = expected["persona_id"]
        session.voice_runtime_profile_id = expected["voice_runtime_profile_id"]
        return True

    async def _rebuild_voice_policy_snapshot(self, session: PracticeSession) -> None:
        runtime_policy_service = self.runtime_policy_service
        if runtime_policy_service is None:
            runtime_policy_service = _build_voice_runtime_policy_resolver(self.db)
        policy = await runtime_policy_service.resolve_effective_policy(
            agent_id=str(session.agent_id),
            persona_id=str(session.persona_id),
            voice_mode_override=_optional_text(session.voice_mode),
            runtime_profile_override=_optional_text(session.voice_runtime_profile_id),
        )
        setattr(
            session,
            "voice_runtime_profile_id",
            _optional_text(policy.get("runtime_profile_id")),
        )
        setattr(session, "voice_policy_snapshot", deepcopy(policy))

    @staticmethod
    def _scenario_type(session: PracticeSession) -> str:
        scenario = getattr(session, "scenario", None)
        scenario_type = getattr(scenario, "scenario_type", None)
        return str(scenario_type or "").strip().lower()

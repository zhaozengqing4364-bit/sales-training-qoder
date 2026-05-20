"""Shared runtime gates for HTTP preflight and WebSocket connection paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from common.db.models import PracticeSession, Scenario
from common.knowledge.kb_lock_guard import is_kb_lock_unbound_snapshot
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.services.examiner_scoring_service import build_llm_exam_scorer
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    FrozenExamQuestion,
)
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService


@dataclass(slots=True)
class RuntimeGateResult:
    runnable: bool
    runtime_type: str
    code: str | None = None
    missing: list[str] = field(default_factory=list)
    hint: str | None = None

    def as_payload(
        self,
        *,
        runtime_lifecycle_state: str | None = None,
        suggested_action: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "runnable": self.runnable,
            "runtime_type": self.runtime_type,
            "code": self.code,
            "missing": self.missing,
            "hint": self.hint,
        }
        if runtime_lifecycle_state is not None:
            payload["runtime_lifecycle_state"] = runtime_lifecycle_state
        if suggested_action is not None:
            payload["suggested_action"] = suggested_action
        return payload


# Backward-compatible alias for preflight callers and tests.
RuntimePreflightResult = RuntimeGateResult


_GATE_HINTS: dict[str, str] = {
    "KB_LOCK_UNBOUND": "知识库未绑定，请联系管理员配置后再练。",
    "AGENT_PERSONA_REQUIRED": "会话缺少智能体或客户画像，请返回入口重新创建会话。",
    "LEGACY_SALES_RUNTIME_DISABLED": "旧版语音模式已停用，请使用实时语音模式。",
    "SESSION_SCENARIO_MISMATCH": "会话类型不匹配，请从正确入口进入练习。",
    "EXAMINER_RUNTIME_SNAPSHOT_MISSING": "考核会话缺少运行快照，请重新发起考核。",
    "EXAMINER_RUNTIME_CONFIG_MISSING": "考核配置不完整，请联系管理员检查考官与题库。",
    "EXAMINER_RUNTIME_SNAPSHOT_STALE": "考核快照已过期，请重新发起考核。",
    "PRESENTATION_NOT_CONFIGURED": "PPT 演练未绑定演示文稿，请返回入口重新创建会话。",
}


class ExamCompletionWriter(Protocol):
    async def __call__(
        self,
        *,
        session_id: str,
        answers: list[dict[str, object]],
        reason: str,
    ) -> str: ...


def _not_runnable(
    *,
    runtime_type: str,
    code: str,
    missing: list[str] | None = None,
    hint: str | None = None,
) -> RuntimeGateResult:
    return RuntimeGateResult(
        runnable=False,
        runtime_type=runtime_type,
        code=code,
        missing=missing or [],
        hint=hint or _GATE_HINTS.get(code, "当前会话暂不可运行，请返回入口重试。"),
    )


def _runnable(*, runtime_type: str) -> RuntimeGateResult:
    return RuntimeGateResult(runnable=True, runtime_type=runtime_type)


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def merge_snapshot_runtime_overlays(
    *,
    resolved_policy: dict[str, Any],
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(resolved_policy)
    if not isinstance(snapshot, dict):
        return merged
    runtime_metrics = snapshot.get("runtime_metrics")
    if isinstance(runtime_metrics, dict):
        merged["runtime_metrics"] = runtime_metrics
    if "agent_persona_override_config" in snapshot:
        merged["agent_persona_override_config"] = snapshot.get(
            "agent_persona_override_config"
        )
    return merged


def resolve_runtime_type(
    *,
    scenario_type: str | None,
    curriculum_snapshot: object,
) -> str:
    if isinstance(curriculum_snapshot, dict):
        if curriculum_snapshot.get("kind") == "curriculum_examiner_session":
            return "examiner"
        content_assets = curriculum_snapshot.get("content_assets")
        if isinstance(content_assets, list) and any(
            isinstance(item, dict) and item.get("asset_type") == "examiner_agent"
            for item in content_assets
        ):
            return "examiner"
    normalized = str(scenario_type or "sales").lower()
    if normalized == "presentation":
        return "presentation"
    return "sales"


def _asset_refs(content_assets: list[object], asset_type: str) -> list[dict[str, object]]:
    return [
        asset
        for asset in content_assets
        if isinstance(asset, dict)
        and asset.get("asset_type") == asset_type
        and isinstance(asset.get("asset_id"), str)
    ]


def _first_asset_ref(
    content_assets: list[object], asset_type: str
) -> dict[str, object] | None:
    refs = _asset_refs(content_assets, asset_type)
    return refs[0] if refs else None


def _asset_matches_ref(asset: object, ref: dict[str, object]) -> bool:
    return str(getattr(asset, "content_hash", "")) == str(
        ref.get("hash")
    ) and _as_int(getattr(asset, "version", 0)) == _as_int(ref.get("version"))


def _as_int(value: object) -> int:
    if not isinstance(value, int | str):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _timeout_seconds(config: object) -> int:
    if not isinstance(config, dict):
        return 0
    try:
        return max(0, int(config.get("max_seconds") or 0))
    except (TypeError, ValueError):
        return 0


class RuntimeGate:
    """Single authority for sales/examiner/presentation runtime readiness checks."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def evaluate_session(self, session_id: str) -> RuntimeGateResult | None:
        result = await self._db.execute(
            select(PracticeSession, Scenario.scenario_type)
            .join(
                Scenario,
                Scenario.scenario_id == PracticeSession.scenario_id,
                isouter=True,
            )
            .where(PracticeSession.session_id == session_id)
        )
        row = result.first()
        if not row:
            return None
        session, scenario_type = row[0], row[1]
        return await self.evaluate_session_row(session, scenario_type=scenario_type)

    async def evaluate_session_row(
        self,
        session: PracticeSession,
        *,
        scenario_type: str | None,
    ) -> RuntimeGateResult:
        runtime_type = resolve_runtime_type(
            scenario_type=str(scenario_type) if scenario_type else None,
            curriculum_snapshot=getattr(session, "curriculum_snapshot", None),
        )
        if runtime_type == "examiner":
            return await self._check_examiner(session)
        if runtime_type == "presentation":
            return await self._check_presentation(session, scenario_type=scenario_type)
        return await self._check_sales(session, scenario_type=scenario_type)

    async def is_kb_lock_unbound(
        self,
        session: PracticeSession,
        *,
        persist_policy_snapshot: bool = False,
    ) -> bool:
        snapshot_raw = getattr(session, "voice_policy_snapshot", None)
        snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else None
        policy_service = VoiceRuntimePolicyService(self._db)
        resolved_policy = await policy_service.resolve_effective_policy(
            agent_id=_optional_text(getattr(session, "agent_id", None)),
            persona_id=_optional_text(getattr(session, "persona_id", None)),
            voice_mode_override=_optional_text(getattr(session, "voice_mode", None)),
            runtime_profile_override=_optional_text(
                getattr(session, "voice_runtime_profile_id", None)
            ),
        )
        refreshed_policy = merge_snapshot_runtime_overlays(
            resolved_policy=resolved_policy,
            snapshot=snapshot,
        )
        if persist_policy_snapshot and snapshot != refreshed_policy:
            setattr(session, "voice_policy_snapshot", refreshed_policy)
            await self._db.commit()
        return bool(is_kb_lock_unbound_snapshot(refreshed_policy))

    async def is_kb_lock_unbound_for_session_id(self, session_id: str) -> bool:
        result = await self._db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        return await self.is_kb_lock_unbound(
            session,
            persist_policy_snapshot=True,
        )

    async def build_examiner_runtime(
        self,
        session_id: str,
        *,
        completion_writer: ExamCompletionWriter | None = None,
    ) -> tuple[ExaminerRuntime | None, str | None]:
        session = await self._db.get(PracticeSession, session_id)
        if session is None:
            return None, "EXAMINER_RUNTIME_SNAPSHOT_MISSING"

        gate_result = await self._check_examiner(session)
        if not gate_result.runnable:
            return None, gate_result.code or "EXAMINER_RUNTIME_CONFIG_MISSING"

        snapshot = getattr(session, "curriculum_snapshot", None)
        if not isinstance(snapshot, dict):
            return None, "EXAMINER_RUNTIME_SNAPSHOT_MISSING"

        content_assets = snapshot.get("content_assets")
        if not isinstance(content_assets, list):
            return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

        examiner_ref = _first_asset_ref(content_assets, "examiner_agent")
        if examiner_ref is None:
            return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

        agent = await self._db.get(ExaminerAgent, str(examiner_ref["asset_id"]))
        if agent is None:
            return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

        questions = await self._load_frozen_questions(content_assets)
        if not questions:
            return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

        if completion_writer is None:
            return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

        return (
            ExaminerRuntime(
                session_id=session_id,
                examiner_agent_id=str(agent.examiner_agent_id),
                timeout_seconds=_timeout_seconds(agent.timeout_config),
                questions=questions,
                scorer=build_llm_exam_scorer(
                    llm_service=LLMService(),
                    session_id=session_id,
                ),
                completion_writer=completion_writer,
            ),
            None,
        )

    async def _load_frozen_questions(
        self,
        content_assets: list[object],
    ) -> list[FrozenExamQuestion]:
        question_refs = _asset_refs(content_assets, "question_item")
        if not question_refs:
            return []

        questions: list[FrozenExamQuestion] = []
        for question_ref in question_refs:
            question = await self._db.get(QuestionItem, str(question_ref["asset_id"]))
            if (
                question is None
                or getattr(question, "status", None) != "published"
                or bool(getattr(question, "safety_flagged", False))
            ):
                return []
            if not _asset_matches_ref(question, question_ref):
                return []
            questions.append(
                FrozenExamQuestion(
                    question_id=str(question.question_id),
                    title=str(question.title),
                    stem=str(question.stem),
                    reference_answer=getattr(question, "reference_answer", None),
                    scoring_criteria=dict(question.scoring_criteria or {}),
                )
            )
        return questions

    async def _check_sales(
        self,
        session: PracticeSession,
        *,
        scenario_type: str | None,
    ) -> RuntimeGateResult:
        runtime_type = "sales"
        if str(scenario_type or "").lower() not in {"", "sales"}:
            return _not_runnable(
                runtime_type=runtime_type,
                code="SESSION_SCENARIO_MISMATCH",
                missing=["scenario_type"],
            )

        voice_mode = _optional_text(getattr(session, "voice_mode", None)) or ""
        if voice_mode != "stepfun_realtime":
            return _not_runnable(
                runtime_type=runtime_type,
                code="LEGACY_SALES_RUNTIME_DISABLED",
                missing=["voice_mode"],
            )

        agent_id = _optional_text(getattr(session, "agent_id", None))
        persona_id = _optional_text(getattr(session, "persona_id", None))
        missing: list[str] = []
        if not agent_id:
            missing.append("agent_id")
        if not persona_id:
            missing.append("persona_id")
        if missing:
            return _not_runnable(
                runtime_type=runtime_type,
                code="AGENT_PERSONA_REQUIRED",
                missing=missing,
            )

        if await self.is_kb_lock_unbound(session):
            return _not_runnable(
                runtime_type=runtime_type,
                code="KB_LOCK_UNBOUND",
                missing=["persona.knowledge_base_ids"],
            )

        return _runnable(runtime_type=runtime_type)

    async def _check_presentation(
        self,
        session: PracticeSession,
        *,
        scenario_type: str | None,
    ) -> RuntimeGateResult:
        runtime_type = "presentation"
        if str(scenario_type or "").lower() != "presentation":
            return _not_runnable(
                runtime_type=runtime_type,
                code="SESSION_SCENARIO_MISMATCH",
                missing=["scenario_type"],
            )

        if not _optional_text(getattr(session, "presentation_id", None)):
            return _not_runnable(
                runtime_type=runtime_type,
                code="PRESENTATION_NOT_CONFIGURED",
                missing=["presentation_id"],
            )

        if await self.is_kb_lock_unbound(session):
            return _not_runnable(
                runtime_type=runtime_type,
                code="KB_LOCK_UNBOUND",
                missing=["persona.knowledge_base_ids"],
            )

        return _runnable(runtime_type=runtime_type)

    async def _check_examiner(self, session: PracticeSession) -> RuntimeGateResult:
        runtime_type = "examiner"
        snapshot = getattr(session, "curriculum_snapshot", None)
        if not isinstance(snapshot, dict):
            return _not_runnable(
                runtime_type=runtime_type,
                code="EXAMINER_RUNTIME_SNAPSHOT_MISSING",
                missing=["curriculum_snapshot"],
            )

        content_assets = snapshot.get("content_assets")
        if not isinstance(content_assets, list):
            return _not_runnable(
                runtime_type=runtime_type,
                code="EXAMINER_RUNTIME_CONFIG_MISSING",
                missing=["curriculum_snapshot.content_assets"],
            )

        examiner_ref = _first_asset_ref(content_assets, "examiner_agent")
        if examiner_ref is None:
            return _not_runnable(
                runtime_type=runtime_type,
                code="EXAMINER_RUNTIME_CONFIG_MISSING",
                missing=["curriculum_snapshot.examiner_agent"],
            )

        agent = await self._db.get(ExaminerAgent, str(examiner_ref["asset_id"]))
        if agent is None or getattr(agent, "status", None) != "published":
            return _not_runnable(
                runtime_type=runtime_type,
                code="EXAMINER_RUNTIME_CONFIG_MISSING",
                missing=["examiner_agent"],
            )
        if not _asset_matches_ref(agent, examiner_ref):
            return _not_runnable(
                runtime_type=runtime_type,
                code="EXAMINER_RUNTIME_SNAPSHOT_STALE",
                missing=["examiner_agent.version"],
            )

        questions = await self._load_frozen_questions(content_assets)
        if not questions:
            return _not_runnable(
                runtime_type=runtime_type,
                code="EXAMINER_RUNTIME_CONFIG_MISSING",
                missing=["question_item"],
            )

        return _runnable(runtime_type=runtime_type)

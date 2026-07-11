from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from common.db.models import PracticeSession
from common.services.runtime_gate import (
    ExamCompletionWriter,
    RuntimeGateResult,
    _not_runnable,
    _runnable,
    check_snapshot_runtime_identity,
    register_runtime_gate_builder,
    register_runtime_gate_checker,
    register_runtime_gate_diagnostics_contributor,
)
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.services.asset_resolution import (
    resolve_session_asset_resolution,
)
from curriculum_practice.services.examiner_scoring_service import (
    build_llm_exam_scorer,
)
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    FrozenExamQuestion,
)
from roleplay.compiler import roleplay_readiness_from_contract

CURRICULUM_PRACTICE_RUNTIME_GATE_CONTRIBUTOR = "curriculum_practice.runtime_gate"


def build_curriculum_practice_runtime_gate_diagnostics(
    session: PracticeSession,
) -> dict[str, Any]:
    template_id = _optional_text(getattr(session, "practice_template_id", None))
    curriculum_snapshot = getattr(session, "curriculum_snapshot", None)
    voice_snapshot = getattr(session, "voice_policy_snapshot", None)
    published_asset_refs = None
    if isinstance(curriculum_snapshot, dict):
        snapshot_resolution = curriculum_snapshot.get("asset_resolution")
        if isinstance(snapshot_resolution, dict):
            published_asset_refs = snapshot_resolution.get("published_asset_refs")
    if published_asset_refs is None and isinstance(voice_snapshot, dict):
        runtime_metrics = voice_snapshot.get("runtime_metrics")
        if isinstance(runtime_metrics, dict):
            center = runtime_metrics.get("config_asset_center")
            if isinstance(center, dict):
                published_asset_refs = center.get("published_asset_refs")

    asset_resolution = resolve_session_asset_resolution(
        practice_template_id=template_id,
        published_asset_refs=published_asset_refs,
        curriculum_snapshot=curriculum_snapshot,
    )
    if isinstance(curriculum_snapshot, dict):
        return {
            "roleplay_contract": roleplay_readiness_from_contract(
                curriculum_snapshot.get("roleplay_contract")
            ),
            "asset_resolution": asset_resolution,
        }
    if isinstance(voice_snapshot, dict):
        return {
            "roleplay_contract": roleplay_readiness_from_contract(
                voice_snapshot.get("roleplay_contract")
            ),
            "asset_resolution": asset_resolution,
        }
    return {
        "roleplay_contract": roleplay_readiness_from_contract(None),
        "asset_resolution": asset_resolution,
    }


async def check_curriculum_examiner_runtime(
    db: AsyncSession,
    session: PracticeSession,
) -> RuntimeGateResult:
    runtime_type = "examiner"
    snapshot = getattr(session, "curriculum_snapshot", None)
    if not isinstance(snapshot, dict):
        return _not_runnable(
            runtime_type=runtime_type,
            code="EXAMINER_RUNTIME_SNAPSHOT_MISSING",
            missing=["curriculum_snapshot"],
        )
    identity_failure = check_snapshot_runtime_identity(session)
    if identity_failure is not None:
        identity_failure.runtime_type = runtime_type
        return identity_failure

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

    agent = await db.get(ExaminerAgent, str(examiner_ref["asset_id"]))
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

    questions, failure_reason = await _load_frozen_questions(db, content_assets)
    if not questions:
        return _not_runnable(
            runtime_type=runtime_type,
            code=failure_reason or "EXAMINER_RUNTIME_CONFIG_MISSING",
            missing=["question_item"],
        )

    return _runnable(runtime_type=runtime_type)


async def build_curriculum_examiner_runtime(
    db: AsyncSession,
    session_id: str,
    completion_writer: ExamCompletionWriter | None,
) -> tuple[ExaminerRuntime | None, str | None]:
    session = await db.get(PracticeSession, session_id)
    if session is None:
        return None, "EXAMINER_RUNTIME_SNAPSHOT_MISSING"

    gate_result = await check_curriculum_examiner_runtime(db, session)
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

    agent = await db.get(ExaminerAgent, str(examiner_ref["asset_id"]))
    if agent is None:
        return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

    questions, failure_reason = await _load_frozen_questions(db, content_assets)
    if not questions:
        return None, failure_reason or "EXAMINER_RUNTIME_CONFIG_MISSING"

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


def register_curriculum_practice_runtime_gate_contributors() -> None:
    register_runtime_gate_diagnostics_contributor(
        CURRICULUM_PRACTICE_RUNTIME_GATE_CONTRIBUTOR,
        build_curriculum_practice_runtime_gate_diagnostics,
    )
    register_runtime_gate_checker("examiner", check_curriculum_examiner_runtime)
    register_runtime_gate_builder("examiner", build_curriculum_examiner_runtime)


async def _load_frozen_questions(
    db: AsyncSession,
    content_assets: list[object],
) -> tuple[list[FrozenExamQuestion], str | None]:
    question_refs = _asset_refs(content_assets, "question_item")
    if not question_refs:
        return [], "EXAMINER_RUNTIME_CONFIG_MISSING"

    questions: list[FrozenExamQuestion] = []
    for question_ref in question_refs:
        question = await db.get(QuestionItem, str(question_ref["asset_id"]))
        if (
            question is None
            or getattr(question, "status", None) != "published"
            or bool(getattr(question, "safety_flagged", False))
        ):
            return [], "EXAMINER_RUNTIME_CONFIG_MISSING"
        if not _asset_matches_ref(question, question_ref):
            return [], "EXAMINER_RUNTIME_SNAPSHOT_STALE"
        questions.append(
            FrozenExamQuestion(
                question_id=str(question.question_id),
                title=str(question.title),
                stem=str(question.stem),
                reference_answer=getattr(question, "reference_answer", None),
                scoring_criteria=dict(question.scoring_criteria or {}),
            )
        )
    return questions, None


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


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None

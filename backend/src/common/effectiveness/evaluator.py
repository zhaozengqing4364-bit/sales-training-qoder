"""Rule-v1 evaluator for session effectiveness snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from common.effectiveness.schemas import (
    ActionCard,
    ClaimTruth,
    MainIssue,
    NextGoal,
    OverallResult,
    PassFlags,
    SalesClaimTruthStatus,
    SalesCoachingDimension,
    SalesCoachingFocus,
    SalesCoachingFocusType,
    SalesReportAlignment,
    SalesScoreContext,
    SalesStageContext,
    SalesStageKey,
)

RULE_VERSION = "rule_v1"

SALES_DIMENSION_ALIASES: dict[SalesCoachingDimension, tuple[str, ...]] = {
    "价值表达": ("价值表达", "value_expression", "value_articulation"),
    "客户收益连接": ("客户收益连接", "customer_benefit", "benefit_linkage"),
    "证据使用": ("证据使用", "evidence_usage", "proof_usage"),
    "异议处理": ("异议处理", "objection_handling", "objection_response"),
    "推进下一步": ("推进下一步", "next_step", "advance_next_step"),
}

SALES_STAGE_ALIASES: dict[SalesStageKey, tuple[str, ...]] = {
    "discovery": (
        "opening",
        "qualification",
        "discovery",
        "开场破冰",
        "需求确认",
        "需求挖掘",
    ),
    "objection": (
        "objection",
        "negotiation",
        "异议处理",
        "价格博弈",
    ),
    "closing": (
        "closing",
        "commitment",
        "促成成交",
        "成交推进",
        "成交",
    ),
}

SALES_STAGE_PRIORITY_DIMENSIONS: dict[
    SalesStageKey, tuple[SalesCoachingDimension, ...]
] = {
    "discovery": ("客户收益连接", "价值表达", "证据使用"),
    "objection": ("异议处理", "证据使用", "推进下一步"),
    "closing": ("推进下一步", "异议处理", "证据使用"),
}

SALES_COACHING_FOCUS_BY_DIMENSION: dict[
    SalesCoachingDimension,
    SalesCoachingFocusType,
] = {
    "价值表达": "value_translation_gap",
    "客户收益连接": "value_translation_gap",
    "证据使用": "evidence_gap",
    "异议处理": "objection_handling_gap",
    "推进下一步": "next_step_gap",
}

SALES_COACHING_FOCUS_TEMPLATES: dict[SalesCoachingFocusType, SalesCoachingFocus] = {
    "value_translation_gap": {
        "issue": "需求还没被翻译成客户收益，客户暂时感受不到业务价值。",
        "replacement": "先追问现状损失或关键目标，再用一句话复述客户收益。",
        "next_turn_rule": "下一轮先问清现状损失或目标，再复述一个客户收益。",
    },
    "evidence_gap": {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    },
    "objection_handling_gap": {
        "issue": "客户顾虑出现后，承接与重构回应还不够完整。",
        "replacement": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
        "next_turn_rule": "下一轮先复述顾虑，再回应证据，最后给低风险推进方案。",
    },
    "next_step_gap": {
        "issue": "对话快结束了，但下一步动作、时间点和责任人还没定下来。",
        "replacement": "明确试点、会议、报价或负责人确认中的一个动作。",
        "next_turn_rule": "下一轮先锁定动作、时间点和责任人，再结束本轮。",
    },
}

SALES_REPORT_MAIN_ISSUES_BY_FOCUS: dict[SalesCoachingFocusType, MainIssue] = {
    "value_translation_gap": {
        "issue_type": "value_translation_gap",
        "issue_text": "还在讲产品功能，未把产品价值翻译成客户收益或业务结果。",
        "recovery_rule": "下一轮先说客户场景、收益指标和预期变化，再讲方案细节。",
    },
    "evidence_gap": {
        "issue_type": "evidence_gap",
        "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
        "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
    },
    "objection_handling_gap": {
        "issue_type": "objection_handling_gap",
        "issue_text": "面对价格、竞品或风险顾虑时，承接和重构回应还不够到位。",
        "recovery_rule": "下一轮先复述顾虑，再用收益、证据和试点方案回应。",
    },
    "next_step_gap": {
        "issue_type": "next_step_gap",
        "issue_text": "对话结束前没有形成明确的下一步动作、责任人或时间点。",
        "recovery_rule": "下一轮必须落到试点、会议、报价或负责人确认中的一个动作。",
    },
}

SALES_REPORT_NEXT_GOALS_BY_FOCUS: dict[SalesCoachingFocusType, NextGoal] = {
    "value_translation_gap": {
        "goal_type": "value_to_benefit_translation",
        "goal_text": "先把产品价值翻译成客户收益，再进入方案说明。",
        "rule": "至少说清一个客户场景、一个收益指标、一个量化变化。",
    },
    "evidence_gap": {
        "goal_type": "evidence_backing",
        "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
        "rule": "至少补上一条证据和一个明确的下一步动作。",
    },
    "objection_handling_gap": {
        "goal_type": "objection_reframe",
        "goal_text": "下一轮先承接价格/竞品/风险顾虑，再用收益和证据回应。",
        "rule": "先复述顾虑，再给回应，最后落到低风险推进方案。",
    },
    "next_step_gap": {
        "goal_type": "next_step_commitment",
        "goal_text": "下一轮必须把试点、会议、报价或责任人确认成明确下一步。",
        "rule": "每轮结尾至少确认一个动作、一个时间点和一个责任人。",
    },
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: Any, default: float = 0.0) -> float:
    return max(0.0, min(100.0, _to_float(value, default)))


def _has_sales_metrics(metrics: dict[str, Any] | None) -> bool:
    if not isinstance(metrics, dict):
        return False
    return any(
        key in metrics
        for key in (
            "value_expression_score",
            "customer_benefit_score",
            "evidence_usage_score",
            "objection_handling_score",
            "next_step_score",
            "value_articulation_rollup",
            "evidence_benefit_rollup",
            "objection_progress_rollup",
        )
    )


def _normalize_sales_dimension_scores(
    dimension_scores: dict[str, Any] | None,
    overall_score: float,
) -> dict[SalesCoachingDimension, float]:
    raw_scores = dimension_scores if isinstance(dimension_scores, dict) else {}
    normalized: dict[SalesCoachingDimension, float] = {}
    for canonical_name, aliases in SALES_DIMENSION_ALIASES.items():
        resolved_score: float | None = None
        for alias in aliases:
            value = raw_scores.get(alias)
            if isinstance(value, (int, float)):
                resolved_score = _clamp_score(value)
                break
        normalized[canonical_name] = (
            resolved_score
            if resolved_score is not None
            else _clamp_score(overall_score)
        )
    return normalized


def _canonical_sales_dimension_name(value: Any) -> SalesCoachingDimension | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    for canonical_name, aliases in SALES_DIMENSION_ALIASES.items():
        for alias in aliases:
            if candidate == alias.strip().lower():
                return canonical_name  # type: ignore[return-value]
    return None


def _normalize_sales_stage_key(
    stage_context: SalesStageContext | None,
    score_context: SalesScoreContext | None,
) -> SalesStageKey | None:
    raw_candidates: list[Any] = []
    if isinstance(stage_context, dict):
        raw_candidates.extend(
            [stage_context.get("current_stage"), stage_context.get("stage_name")]
        )
    if isinstance(score_context, dict):
        raw_candidates.append(score_context.get("stage_name"))

    for candidate in raw_candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        normalized_candidate = candidate.strip().lower()
        for stage_key, aliases in SALES_STAGE_ALIASES.items():
            if any(
                normalized_candidate == alias.strip().lower()
                or normalized_candidate in alias.strip().lower()
                or alias.strip().lower() in normalized_candidate
                for alias in aliases
            ):
                return stage_key
    return None


def _extract_sales_dimension_context(
    score_context: SalesScoreContext | None,
) -> tuple[
    dict[SalesCoachingDimension, float],
    dict[SalesCoachingDimension, float],
    dict[SalesCoachingDimension, str],
]:
    if not isinstance(score_context, dict):
        return {}, {}, {}

    overall_score = _clamp_score(score_context.get("overall_score"), 0.0)
    raw_dimension_scores = score_context.get("dimension_scores")
    normalized_scores = _normalize_sales_dimension_scores(
        raw_dimension_scores if isinstance(raw_dimension_scores, dict) else None,
        overall_score,
    )

    deltas: dict[SalesCoachingDimension, float] = {}
    trends: dict[SalesCoachingDimension, str] = {}
    raw_dimensions = score_context.get("dimensions")
    if isinstance(raw_dimensions, list):
        for item in raw_dimensions:
            if not isinstance(item, dict):
                continue
            canonical_name = _canonical_sales_dimension_name(item.get("name"))
            if canonical_name is None:
                continue
            delta = item.get("delta")
            if isinstance(delta, (int, float)):
                deltas[canonical_name] = float(delta)
            trend = item.get("trend")
            if isinstance(trend, str) and trend.strip():
                trends[canonical_name] = trend.strip().lower()
            score = item.get("score")
            if isinstance(score, (int, float)):
                normalized_scores[canonical_name] = _clamp_score(score)

    return normalized_scores, deltas, trends


def _coaching_urgency_score(
    dimension_name: SalesCoachingDimension,
    base_score: float,
    deltas: dict[SalesCoachingDimension, float],
    trends: dict[SalesCoachingDimension, str],
) -> float:
    adjusted_score = base_score
    delta = deltas.get(dimension_name)
    if delta is not None and delta < 0:
        adjusted_score += delta

    trend = trends.get(dimension_name)
    if trend in {"down", "declining", "negative", "下降", "下滑"}:
        adjusted_score -= 4.0

    return adjusted_score


def _select_sales_focus_type(
    *,
    stage_context: SalesStageContext | None,
    score_context: SalesScoreContext | None,
    pass_flags: PassFlags | None,
) -> SalesCoachingFocusType | None:
    stage_key = _normalize_sales_stage_key(stage_context, score_context)
    scores, deltas, trends = _extract_sales_dimension_context(score_context)

    if scores:
        urgency_scores = {
            dimension_name: _coaching_urgency_score(
                dimension_name,
                score,
                deltas,
                trends,
            )
            for dimension_name, score in scores.items()
        }
        weakest_dimension, weakest_score = min(
            urgency_scores.items(),
            key=lambda item: item[1],
        )
        if stage_key is not None:
            preferred_dimensions = SALES_STAGE_PRIORITY_DIMENSIONS.get(stage_key, ())
            near_stage_dimensions = [
                dimension_name
                for dimension_name in preferred_dimensions
                if urgency_scores.get(dimension_name, 101.0) <= weakest_score + 6.0
            ]
            if near_stage_dimensions:
                weakest_dimension = min(
                    near_stage_dimensions,
                    key=lambda dimension_name: urgency_scores[dimension_name],
                )
        return SALES_COACHING_FOCUS_BY_DIMENSION[weakest_dimension]

    if not pass_flags:
        return None

    if all(pass_flags.values()):
        return None
    if not pass_flags.get("pass_3min_flow", True):
        return "value_translation_gap"
    if not pass_flags.get("pass_5turn_defense", True):
        return "objection_handling_gap"
    if not pass_flags.get("pass_4step_structure", True):
        return "next_step_gap" if stage_key == "closing" else "evidence_gap"
    return None


def _sales_report_payloads_for_focus(
    focus_type: SalesCoachingFocusType,
) -> tuple[MainIssue, NextGoal]:
    return (
        MainIssue(**SALES_REPORT_MAIN_ISSUES_BY_FOCUS[focus_type]),
        NextGoal(**SALES_REPORT_NEXT_GOALS_BY_FOCUS[focus_type]),
    )


def _coerce_main_issue(value: Any) -> MainIssue | None:
    if not isinstance(value, dict):
        return None
    issue_type = value.get("issue_type")
    issue_text = value.get("issue_text")
    recovery_rule = value.get("recovery_rule")
    if not all(
        isinstance(item, str) and item.strip()
        for item in (issue_type, issue_text, recovery_rule)
    ):
        return None
    issue_type = cast(str, issue_type)
    issue_text = cast(str, issue_text)
    recovery_rule = cast(str, recovery_rule)
    return {
        "issue_type": issue_type.strip(),
        "issue_text": issue_text.strip(),
        "recovery_rule": recovery_rule.strip(),
    }


def _coerce_next_goal(value: Any) -> NextGoal | None:
    if not isinstance(value, dict):
        return None
    goal_type = value.get("goal_type")
    goal_text = value.get("goal_text")
    rule = value.get("rule")
    if not all(
        isinstance(item, str) and item.strip() for item in (goal_type, goal_text, rule)
    ):
        return None
    goal_type = cast(str, goal_type)
    goal_text = cast(str, goal_text)
    rule = cast(str, rule)
    return {
        "goal_type": goal_type.strip(),
        "goal_text": goal_text.strip(),
        "rule": rule.strip(),
    }


SALES_CLAIM_TRUTH_LABELS: dict[SalesClaimTruthStatus, str] = {
    "unsupported_claim": "未被证据支撑",
    "weak_evidence": "证据偏弱",
    "evidence_pending": "证据待补齐",
    "evidence_verified": "证据已验证",
}
SALES_UNSUPPORTED_EVIDENCE_MAX = 55.0
SALES_VERIFIED_EVIDENCE_MIN = 75.0


def _build_claim_truth(
    status: SalesClaimTruthStatus,
    *,
    source: str,
    reason: str,
    evidence_score: float | None = None,
    closure_state: str | None = None,
) -> ClaimTruth:
    payload: ClaimTruth = {
        "status": status,
        "label": SALES_CLAIM_TRUTH_LABELS[status],
        "source": source,
        "reason": reason,
    }
    if evidence_score is not None:
        payload["evidence_score"] = round(_clamp_score(evidence_score), 2)
    if isinstance(closure_state, str) and closure_state.strip():
        payload["closure_state"] = closure_state.strip()
    return payload


def _coerce_claim_truth(value: Any) -> ClaimTruth | None:
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    source = value.get("source")
    reason = value.get("reason")
    if not isinstance(status, str) or not status.strip():
        return None
    if not isinstance(source, str) or not source.strip():
        return None
    normalized_status = status.strip()
    if normalized_status not in SALES_CLAIM_TRUTH_LABELS:
        return None
    claim_status = cast(SalesClaimTruthStatus, normalized_status)

    payload = _build_claim_truth(
        claim_status,
        source=source.strip(),
        reason=str(reason).strip() if reason is not None else "existing_snapshot",
        evidence_score=(
            float(value["evidence_score"])
            if isinstance(value.get("evidence_score"), (int, float))
            else None
        ),
        closure_state=(
            str(value["closure_state"])
            if value.get("closure_state") is not None
            else None
        ),
    )
    label = value.get("label")
    if isinstance(label, str) and label.strip():
        payload["label"] = label.strip()
    return payload


def _resolve_alignment_evidence_score(
    score_snapshot: SalesScoreContext | dict[str, Any] | None,
) -> float | None:
    if not isinstance(score_snapshot, dict):
        return None

    raw_dimension_scores = score_snapshot.get("dimension_scores")
    if isinstance(raw_dimension_scores, dict):
        for alias in SALES_DIMENSION_ALIASES["证据使用"]:
            value = raw_dimension_scores.get(alias)
            if isinstance(value, (int, float)):
                return _clamp_score(value)

    raw_dimensions = score_snapshot.get("dimensions")
    if isinstance(raw_dimensions, list):
        for item in raw_dimensions:
            if not isinstance(item, dict):
                continue
            if _canonical_sales_dimension_name(item.get("name")) != "证据使用":
                continue
            score = item.get("score")
            if isinstance(score, (int, float)):
                return _clamp_score(score)

    return None


def _resolve_claim_truth_from_evidence_score(
    *,
    evidence_score: float,
    source: str,
    reason: str,
    closure_state: str | None = None,
    focus_type: SalesCoachingFocusType | None = None,
) -> ClaimTruth:
    status: SalesClaimTruthStatus
    if evidence_score < SALES_UNSUPPORTED_EVIDENCE_MAX:
        status = "unsupported_claim"
    elif evidence_score < SALES_VERIFIED_EVIDENCE_MIN:
        status = "weak_evidence"
    elif focus_type == "evidence_gap":
        status = "weak_evidence"
    else:
        status = "evidence_verified"
    return _build_claim_truth(
        status,
        source=source,
        reason=reason,
        evidence_score=evidence_score,
        closure_state=closure_state,
    )


def _resolve_sales_claim_truth(
    *,
    score_snapshot: SalesScoreContext | dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    fallback_snapshot: dict[str, Any] | None = None,
    focus_type: SalesCoachingFocusType | None = None,
    objection_ledger: dict[str, Any] | None = None,
    evaluable: bool | None = None,
    not_evaluable_reason: str | None = None,
) -> ClaimTruth | None:
    closure_state = None
    if isinstance(objection_ledger, dict):
        raw_closure_state = objection_ledger.get("closure_state")
        if isinstance(raw_closure_state, str) and raw_closure_state.strip():
            closure_state = raw_closure_state.strip().lower()

    if closure_state == "open":
        return _build_claim_truth(
            "evidence_pending",
            source="objection_ledger",
            reason="open_objection_ledger",
            closure_state=closure_state,
        )
    if closure_state == "gap_acknowledged":
        return _build_claim_truth(
            "unsupported_claim",
            source="objection_ledger",
            reason="gap_acknowledged",
            closure_state=closure_state,
        )

    existing_claim_truth = None
    if isinstance(fallback_snapshot, dict):
        existing_claim_truth = _coerce_claim_truth(fallback_snapshot.get("claim_truth"))

    derived_evaluable = evaluable
    if derived_evaluable is None and isinstance(fallback_snapshot, dict):
        fallback_evaluable = fallback_snapshot.get("evaluable")
        if isinstance(fallback_evaluable, bool):
            derived_evaluable = fallback_evaluable
    derived_reason = not_evaluable_reason
    if derived_reason is None and isinstance(fallback_snapshot, dict):
        fallback_reason = fallback_snapshot.get("not_evaluable_reason")
        if isinstance(fallback_reason, str) and fallback_reason.strip():
            derived_reason = fallback_reason.strip()

    if derived_evaluable is False:
        return _build_claim_truth(
            "evidence_pending",
            source="fallback_snapshot",
            reason=(derived_reason or "insufficient_sales_evidence").lower(),
            closure_state=closure_state,
        )

    evidence_score = _resolve_alignment_evidence_score(score_snapshot)
    evidence_source = "score_snapshot"
    if (
        evidence_score is None
        and isinstance(metrics, dict)
        and _has_sales_metrics(metrics)
    ):
        evidence_score = _resolve_sales_scores(metrics)["证据使用"]
        evidence_source = "metrics"

    if closure_state == "evidence_provided":
        if evidence_score is None:
            return _build_claim_truth(
                "weak_evidence",
                source="objection_ledger",
                reason="evidence_provided_without_strong_score",
                closure_state=closure_state,
            )
        status: SalesClaimTruthStatus = (
            "evidence_verified"
            if evidence_score >= SALES_VERIFIED_EVIDENCE_MIN
            else "weak_evidence"
        )
        return _build_claim_truth(
            status,
            source="objection_ledger",
            reason="evidence_provided",
            evidence_score=evidence_score,
            closure_state=closure_state,
        )

    if evidence_score is not None:
        return _resolve_claim_truth_from_evidence_score(
            evidence_score=evidence_score,
            source=evidence_source,
            reason="low_evidence_score"
            if evidence_score < SALES_VERIFIED_EVIDENCE_MIN
            else "strong_evidence_score",
            closure_state=closure_state,
            focus_type=focus_type,
        )

    if existing_claim_truth is not None:
        return existing_claim_truth

    if isinstance(metrics, dict) and not _has_sales_metrics(metrics):
        return None

    return _build_claim_truth(
        "evidence_pending",
        source="fallback_snapshot"
        if isinstance(fallback_snapshot, dict)
        else "score_snapshot",
        reason="missing_evidence_score",
        closure_state=closure_state,
    )


def _has_alignment_dimension_scores(
    score_snapshot: SalesScoreContext | dict[str, Any] | None,
) -> bool:
    if not isinstance(score_snapshot, dict):
        return False
    raw_dimension_scores = score_snapshot.get("dimension_scores")
    if not isinstance(raw_dimension_scores, dict) or not raw_dimension_scores:
        return False

    resolved_dimensions = {
        canonical_name
        for key, value in raw_dimension_scores.items()
        if isinstance(value, (int, float))
        for canonical_name in [_canonical_sales_dimension_name(key)]
        if canonical_name is not None
    }
    return len(resolved_dimensions) == len(SALES_DIMENSION_ALIASES)


def _resolve_sales_report_alignment_fallback(
    fallback_snapshot: dict[str, Any] | None,
) -> tuple[MainIssue, NextGoal]:
    if isinstance(fallback_snapshot, dict):
        metrics = fallback_snapshot.get("metrics")
        main_capability_passed = fallback_snapshot.get("main_capability_passed")
        not_evaluable_reason = fallback_snapshot.get("not_evaluable_reason")
        if isinstance(metrics, dict) and isinstance(main_capability_passed, bool):
            refreshed_snapshot = evaluate_effectiveness_snapshot(
                metrics=metrics,
                main_capability_passed=main_capability_passed,
                evaluable=bool(fallback_snapshot.get("evaluable", True)),
                not_evaluable_reason=(
                    str(not_evaluable_reason)
                    if not_evaluable_reason is not None
                    else None
                ),
            )
            refreshed_issue = _coerce_main_issue(refreshed_snapshot.get("main_issue"))
            refreshed_goal = _coerce_next_goal(refreshed_snapshot.get("next_goal"))
            if refreshed_issue is not None and refreshed_goal is not None:
                return refreshed_issue, refreshed_goal

        existing_issue = _coerce_main_issue(fallback_snapshot.get("main_issue"))
        existing_goal = _coerce_next_goal(fallback_snapshot.get("next_goal"))
        if existing_issue is not None and existing_goal is not None:
            return existing_issue, existing_goal

    generic_snapshot = evaluate_effectiveness_snapshot(
        metrics={
            "value_articulation_rollup": 0.0,
            "evidence_benefit_rollup": 0.0,
            "objection_progress_rollup": 0.0,
        },
        main_capability_passed=False,
        evaluable=False,
        not_evaluable_reason="INSUFFICIENT_SALES_ALIGNMENT_EVIDENCE",
    )
    generic_issue = _coerce_main_issue(generic_snapshot.get("main_issue"))
    generic_goal = _coerce_next_goal(generic_snapshot.get("next_goal"))
    if generic_issue is None or generic_goal is None:
        raise ValueError(
            "sales alignment fallback should always produce report-compatible payloads"
        )
    return generic_issue, generic_goal


def resolve_sales_report_alignment(
    *,
    sales_stage: str | None,
    score_snapshot: dict[str, Any] | None,
    fallback_snapshot: dict[str, Any] | None = None,
    objection_ledger: dict[str, Any] | None = None,
) -> SalesReportAlignment:
    stage_context: SalesStageContext | None = None
    if isinstance(sales_stage, str) and sales_stage.strip():
        stage_context = {
            "current_stage": sales_stage,
            "stage_name": sales_stage,
        }
    score_context = cast(SalesScoreContext, score_snapshot) if isinstance(score_snapshot, dict) else None
    stage_key = _normalize_sales_stage_key(stage_context, score_context)

    fallback_reason: str | None = None
    focus_type: SalesCoachingFocusType | None = None
    alignment_used = False

    if stage_key is None:
        fallback_reason = "missing_sales_stage"
    elif not _has_alignment_dimension_scores(score_context):
        fallback_reason = "missing_dimension_scores"
    else:
        focus_type = _select_sales_focus_type(
            stage_context=stage_context,
            score_context=score_context,
            pass_flags=None,
        )
        if focus_type is None:
            fallback_reason = "missing_focus_type"
        else:
            alignment_used = True

    if alignment_used and focus_type is not None:
        main_issue, next_goal = _sales_report_payloads_for_focus(focus_type)
    else:
        main_issue, next_goal = _resolve_sales_report_alignment_fallback(
            fallback_snapshot
        )

    claim_truth = _resolve_sales_claim_truth(
        score_snapshot=score_context,
        fallback_snapshot=fallback_snapshot,
        focus_type=focus_type,
        objection_ledger=objection_ledger,
    )

    return {
        "alignment_used": alignment_used,
        "stage_key": stage_key,
        "focus_type": focus_type,
        "fallback_reason": fallback_reason,
        "main_issue": main_issue,
        "next_goal": next_goal,
        "claim_truth": claim_truth,
    }


def build_live_session_conclusion_summary(
    *,
    sales_stage: str | None,
    score_snapshot: dict[str, Any] | None,
    fallback_snapshot: dict[str, Any] | None = None,
    objection_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alignment = resolve_sales_report_alignment(
        sales_stage=sales_stage,
        score_snapshot=score_snapshot,
        fallback_snapshot=fallback_snapshot,
        objection_ledger=objection_ledger,
    )
    return {
        "alignment_used": bool(alignment.get("alignment_used", False)),
        "stage_key": (
            alignment.get("stage_key")
            if alignment.get("stage_key") in SALES_STAGE_ALIASES
            else None
        ),
        "focus_type": (
            alignment.get("focus_type")
            if alignment.get("focus_type") in SALES_COACHING_FOCUS_TEMPLATES
            else None
        ),
        "fallback_reason": (
            str(alignment.get("fallback_reason")).strip()
            if alignment.get("fallback_reason") is not None
            and str(alignment.get("fallback_reason")).strip()
            else None
        ),
        "main_issue": dict(alignment["main_issue"]),
        "next_goal": dict(alignment["next_goal"]),
        "claim_truth": _coerce_claim_truth(alignment.get("claim_truth")),
    }


def coerce_live_session_conclusion_summary(
    value: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    main_issue = _coerce_main_issue(value.get("main_issue"))
    next_goal = _coerce_next_goal(value.get("next_goal"))
    claim_truth = _coerce_claim_truth(value.get("claim_truth"))
    if main_issue is None and next_goal is None and claim_truth is None:
        return None

    stage_key = value.get("stage_key")
    if stage_key not in SALES_STAGE_ALIASES:
        stage_key = None

    focus_type = value.get("focus_type")
    if focus_type not in SALES_COACHING_FOCUS_TEMPLATES:
        focus_type = None

    fallback_reason = value.get("fallback_reason")
    if not isinstance(fallback_reason, str) or not fallback_reason.strip():
        fallback_reason = None
    else:
        fallback_reason = fallback_reason.strip()

    return {
        "alignment_used": bool(value.get("alignment_used", False)),
        "stage_key": stage_key,
        "focus_type": focus_type,
        "fallback_reason": fallback_reason,
        "main_issue": dict(main_issue) if main_issue is not None else None,
        "next_goal": dict(next_goal) if next_goal is not None else None,
        "claim_truth": claim_truth,
    }


def build_sales_rollup_scores(
    *,
    overall_score: float,
    dimension_scores: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = _normalize_sales_dimension_scores(dimension_scores, overall_score)
    logic_score = round(
        normalized["价值表达"] * 0.60 + normalized["客户收益连接"] * 0.40,
        2,
    )
    accuracy_score = round(
        normalized["客户收益连接"] * 0.45 + normalized["证据使用"] * 0.55,
        2,
    )
    completeness_score = round(
        normalized["异议处理"] * 0.60 + normalized["推进下一步"] * 0.40,
        2,
    )
    return {
        "logic_score": logic_score,
        "accuracy_score": accuracy_score,
        "completeness_score": completeness_score,
        "sales_dimension_scores": normalized,
    }


def build_sales_effectiveness_metrics(
    *,
    overall_score: float,
    dimension_scores: dict[str, Any] | None = None,
    logic_score: float | None = None,
    accuracy_score: float | None = None,
    completeness_score: float | None = None,
    turn_count: int | None = None,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    if isinstance(dimension_scores, dict) and dimension_scores:
        rollups = build_sales_rollup_scores(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
        )
        sales_scores = dict(rollups["sales_dimension_scores"])
        logic_value = _clamp_score(
            logic_score if logic_score is not None else rollups["logic_score"]
        )
        accuracy_value = _clamp_score(
            accuracy_score if accuracy_score is not None else rollups["accuracy_score"]
        )
        completeness_value = _clamp_score(
            completeness_score
            if completeness_score is not None
            else rollups["completeness_score"]
        )
    else:
        logic_value = _clamp_score(logic_score, overall_score)
        accuracy_value = _clamp_score(accuracy_score, overall_score)
        completeness_value = _clamp_score(completeness_score, overall_score)
        sales_scores = {
            "价值表达": logic_value,
            "客户收益连接": round((logic_value + accuracy_value) / 2.0, 2),
            "证据使用": accuracy_value,
            "异议处理": completeness_value,
            "推进下一步": completeness_value,
        }

    effective_duration = max(
        int(duration_seconds or 0),
        int((logic_value + accuracy_value + completeness_value) / 3.0 * 2.0),
        int(max(0, int(turn_count or 0)) * 45),
    )
    objection_score = sales_scores["异议处理"]
    next_step_score = sales_scores["推进下一步"]
    value_score = sales_scores["价值表达"]

    return {
        "continuous_speech_seconds": float(effective_duration),
        "filler_rate_per_100_words": round(
            max(0.0, min(30.0, (100.0 - value_score) / 4.0)),
            2,
        ),
        "offtopic_turn_count": float(max(0, round((100.0 - objection_score) / 25.0))),
        "offtopic_max_streak": float(
            2 if objection_score < 55 else (1 if objection_score < 75 else 0)
        ),
        "structure_coverage": round(max(0.0, min(1.0, next_step_score / 100.0)), 4),
        "value_expression_score": round(sales_scores["价值表达"], 2),
        "customer_benefit_score": round(sales_scores["客户收益连接"], 2),
        "evidence_usage_score": round(sales_scores["证据使用"], 2),
        "objection_handling_score": round(sales_scores["异议处理"], 2),
        "next_step_score": round(sales_scores["推进下一步"], 2),
        "value_articulation_rollup": round(logic_value, 2),
        "evidence_benefit_rollup": round(accuracy_value, 2),
        "objection_progress_rollup": round(completeness_value, 2),
    }


def _resolve_sales_scores(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "价值表达": _clamp_score(
            metrics.get("value_expression_score"),
            _to_float(metrics.get("value_articulation_rollup"), 0.0),
        ),
        "客户收益连接": _clamp_score(
            metrics.get("customer_benefit_score"),
            _to_float(metrics.get("value_articulation_rollup"), 0.0),
        ),
        "证据使用": _clamp_score(
            metrics.get("evidence_usage_score"),
            _to_float(metrics.get("evidence_benefit_rollup"), 0.0),
        ),
        "异议处理": _clamp_score(
            metrics.get("objection_handling_score"),
            _to_float(metrics.get("objection_progress_rollup"), 0.0),
        ),
        "推进下一步": _clamp_score(
            metrics.get("next_step_score"),
            _to_float(metrics.get("objection_progress_rollup"), 0.0),
        ),
    }


def evaluate_pass_flags(metrics: dict[str, Any]) -> PassFlags:
    """Evaluate pass flags while preserving the existing key contract."""
    if _has_sales_metrics(metrics):
        sales_scores = _resolve_sales_scores(metrics)
        return {
            "pass_3min_flow": (
                sales_scores["价值表达"] >= 70.0
                and sales_scores["客户收益连接"] >= 68.0
            ),
            "pass_5turn_defense": sales_scores["异议处理"] >= 70.0,
            "pass_4step_structure": (
                sales_scores["证据使用"] >= 68.0 and sales_scores["推进下一步"] >= 65.0
            ),
        }

    continuous_speech_seconds = _to_float(metrics.get("continuous_speech_seconds"), 0.0)
    offtopic_turn_count = _to_float(metrics.get("offtopic_turn_count"), 99.0)
    offtopic_max_streak = _to_float(metrics.get("offtopic_max_streak"), 99.0)
    structure_coverage = _to_float(metrics.get("structure_coverage"), 0.0)

    return {
        "pass_3min_flow": continuous_speech_seconds >= 180.0,
        "pass_5turn_defense": offtopic_turn_count <= 1.0 and offtopic_max_streak < 2.0,
        "pass_4step_structure": structure_coverage >= 0.75,
    }


def _sales_main_issue(metrics: dict[str, Any]) -> MainIssue:
    sales_scores = _resolve_sales_scores(metrics)
    candidates: list[tuple[float, SalesCoachingFocusType]] = [
        (
            min(sales_scores["价值表达"], sales_scores["客户收益连接"]),
            "value_translation_gap",
        ),
        (sales_scores["证据使用"], "evidence_gap"),
        (sales_scores["异议处理"], "objection_handling_gap"),
        (sales_scores["推进下一步"], "next_step_gap"),
    ]
    _, focus_type = min(candidates, key=lambda item: item[0])
    main_issue, _ = _sales_report_payloads_for_focus(focus_type)
    return main_issue


def _sales_next_goal(metrics: dict[str, Any]) -> NextGoal:
    issue_type = _sales_main_issue(metrics)["issue_type"]
    _, next_goal = _sales_report_payloads_for_focus(issue_type)  # type: ignore[arg-type]
    return next_goal


def resolve_sales_coaching_focus(
    *,
    stage_context: SalesStageContext | None = None,
    score_context: SalesScoreContext | None = None,
    pass_flags: PassFlags | None = None,
) -> SalesCoachingFocus | None:
    focus_type = _select_sales_focus_type(
        stage_context=stage_context if isinstance(stage_context, dict) else None,
        score_context=score_context if isinstance(score_context, dict) else None,
        pass_flags=pass_flags,
    )
    if focus_type is None:
        return None

    focus = SALES_COACHING_FOCUS_TEMPLATES[focus_type]
    return {
        "issue": focus["issue"],
        "replacement": focus["replacement"],
        "next_turn_rule": focus["next_turn_rule"],
    }


def resolve_next_goal(
    pass_flags: PassFlags,
    *,
    main_capability_passed: bool,
    metrics: dict[str, Any] | None = None,
) -> NextGoal:
    """Return exactly one next goal for the next training round."""
    if isinstance(metrics, dict) and _has_sales_metrics(metrics):
        return _sales_next_goal(metrics)

    if not main_capability_passed:
        return {
            "goal_type": "main_capability_focus",
            "goal_text": "下一轮只聚焦主能力动作，先完成核心沟通目标。",
            "rule": "保持三项硬指标基础稳定，优先完成主能力关键动作。",
        }
    if not pass_flags["pass_3min_flow"]:
        return {
            "goal_type": "continuous_expression",
            "goal_text": "先完成3分钟连续表达，减少停顿与填充词。",
            "rule": "下一轮先连续表达180秒后再进入追问环节。",
        }
    if not pass_flags["pass_5turn_defense"]:
        return {
            "goal_type": "defense_under_followups",
            "goal_text": "在5轮客户追问中保持不跑题。",
            "rule": "下一轮5轮追问中跑题不超过1次，且不能连续跑题。",
        }
    if not pass_flags["pass_4step_structure"]:
        return {
            "goal_type": "four_step_structure",
            "goal_text": "按开场-需求-价值-下一步完成完整表达。",
            "rule": "下一轮至少覆盖四段中的3段，优先补齐缺失段。",
        }

    return {
        "goal_type": "advance",
        "goal_text": "当前能力通过，进入更高难度角色继续训练。",
        "rule": "下一轮保持三项硬指标达标并尝试更强追问。",
    }


def resolve_main_issue(
    pass_flags: PassFlags,
    *,
    main_capability_passed: bool,
    metrics: dict[str, Any] | None = None,
) -> MainIssue:
    """Return exactly one main issue for current session report."""
    if isinstance(metrics, dict) and _has_sales_metrics(metrics):
        return _sales_main_issue(metrics)

    if not main_capability_passed:
        return {
            "issue_type": "main_capability_not_passed",
            "issue_text": "本场主能力未达标，关键沟通目标尚未完成。",
            "recovery_rule": "下一轮聚焦单一主能力，先完成核心动作再追求高分。",
        }
    if not pass_flags["pass_3min_flow"]:
        return {
            "issue_type": "continuous_expression",
            "issue_text": "连续表达不足，停顿或填充词影响信息完整传达。",
            "recovery_rule": "下一轮先完成180秒连续表达，再进入追问。",
        }
    if not pass_flags["pass_5turn_defense"]:
        return {
            "issue_type": "defense_under_followups",
            "issue_text": "追问阶段出现跑题，主线稳定性不足。",
            "recovery_rule": "下一轮每次先复述问题，再给出回应。",
        }
    if not pass_flags["pass_4step_structure"]:
        return {
            "issue_type": "four_step_structure",
            "issue_text": "表达结构不完整，未形成开场-需求-价值-下一步闭环。",
            "recovery_rule": "下一轮按四段结构完整输出一轮表达。",
        }

    return {
        "issue_type": "no_blocking_issue",
        "issue_text": "本场三项硬指标均达标，无阻断性主问题。",
        "recovery_rule": "下一轮提高客户追问强度，保持稳定达标。",
    }


def evaluate_effectiveness_snapshot(
    *,
    metrics: dict[str, Any],
    main_capability_passed: bool,
    evaluable: bool = True,
    not_evaluable_reason: str | None = None,
) -> dict[str, Any]:
    """Build normalized snapshot payload persisted on practice session."""
    pass_flags = evaluate_pass_flags(metrics)
    passed_count = sum(1 for value in pass_flags.values() if value)

    overall_result: OverallResult
    if not main_capability_passed:
        overall_result = "fail"
    elif passed_count == 3:
        overall_result = "strong_pass"
    elif passed_count >= 2:
        overall_result = "pass"
    else:
        overall_result = "fail"

    if not evaluable and _has_sales_metrics(metrics):
        main_issue: MainIssue = {
            "issue_type": "insufficient_sales_evidence",
            "issue_text": "当前有效销售证据不足，无法判断价值表达、证据使用和异议推进短板。",
            "recovery_rule": "至少完成一轮围绕ROI、价格、竞品或案例的有效问答后再结束。",
        }
        next_goal: NextGoal = {
            "goal_type": "collect_sales_evidence",
            "goal_text": "先补齐一轮价值表达、异议回应和证据引用，再生成报告。",
            "rule": "至少出现一次客户问题、一次销售回应、一次证据引用和一个下一步动作。",
        }
    else:
        main_issue = resolve_main_issue(
            pass_flags,
            main_capability_passed=bool(main_capability_passed),
            metrics=metrics,
        )
        next_goal = resolve_next_goal(
            pass_flags,
            main_capability_passed=bool(main_capability_passed),
            metrics=metrics,
        )

    focus_type = (
        cast(SalesCoachingFocusType, main_issue["issue_type"])
        if main_issue.get("issue_type")
        in {
            "evidence_gap",
            "objection_handling_gap",
            "next_step_gap",
            "value_translation_gap",
        }
        else None
    )
    claim_truth = _resolve_sales_claim_truth(
        metrics=metrics,
        focus_type=focus_type,
        evaluable=bool(evaluable),
        not_evaluable_reason=not_evaluable_reason,
    )

    snapshot = {
        "pass_flags": pass_flags,
        "main_capability_passed": bool(main_capability_passed),
        "overall_result": overall_result,
        "metrics": metrics,
        "main_issue": main_issue,
        "next_goal": next_goal,
        "version": RULE_VERSION,
        "evaluable": bool(evaluable),
        "not_evaluable_reason": not_evaluable_reason,
    }
    if claim_truth is not None:
        snapshot["claim_truth"] = claim_truth
    return snapshot


def build_action_card(
    *,
    fuzzy_detections: Iterable[dict[str, Any]] | None = None,
    suggestions: Iterable[str] | None = None,
    pass_flags: PassFlags | None = None,
    stage_context: SalesStageContext | None = None,
    score_context: SalesScoreContext | None = None,
) -> ActionCard | None:
    """Build a single actionable card from realtime signals."""
    detections = [item for item in (fuzzy_detections or []) if isinstance(item, dict)]
    tips = [
        tip.strip()
        for tip in (suggestions or [])
        if isinstance(tip, str) and tip.strip()
    ]

    has_rich_sales_context = isinstance(stage_context, dict) or isinstance(
        score_context, dict
    )
    if has_rich_sales_context:
        coaching_focus = resolve_sales_coaching_focus(
            stage_context=stage_context if isinstance(stage_context, dict) else None,
            score_context=score_context if isinstance(score_context, dict) else None,
            pass_flags=pass_flags,
        )
        if coaching_focus is not None:
            return {
                "issue": coaching_focus["issue"],
                "replacement": coaching_focus["replacement"],
                "next_turn_rule": coaching_focus["next_turn_rule"],
            }

    issue = ""
    replacement = ""

    if detections:
        first = detections[0]
        matched = first.get("matched")
        if isinstance(matched, list) and matched:
            issue = f"检测到表达问题：{', '.join(str(x) for x in matched[:3])}"
        else:
            issue = "检测到表达不够具体"
        replacement = str(first.get("suggestion") or "请改用更具体的业务表达。").strip()
    elif tips:
        issue = "当前轮次有1个关键改进点"
        replacement = tips[0]

    if not issue or not replacement:
        return None

    if pass_flags and not pass_flags.get("pass_3min_flow", True):
        next_turn_rule = "下一轮先把产品价值翻译成客户收益，再补功能细节。"
    elif pass_flags and not pass_flags.get("pass_5turn_defense", True):
        next_turn_rule = "下一轮先承接价格、竞品或风险顾虑，再给回应。"
    elif pass_flags and not pass_flags.get("pass_4step_structure", True):
        next_turn_rule = "下一轮先补案例或数据证据，并明确下一步动作。"
    else:
        next_turn_rule = "下一轮先问清ROI或预算，再推动明确下一步。"

    return {
        "issue": issue,
        "replacement": replacement,
        "next_turn_rule": next_turn_rule,
    }

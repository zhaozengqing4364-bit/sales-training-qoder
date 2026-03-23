"""Rule-v1 evaluator for session effectiveness snapshots."""

from __future__ import annotations

from typing import Any, Iterable

from common.effectiveness.schemas import ActionCard, NextGoal, OverallResult, PassFlags


RULE_VERSION = "rule_v1"

SALES_DIMENSION_ALIASES: dict[str, tuple[str, ...]] = {
    "价值表达": ("价值表达", "value_expression", "value_articulation"),
    "客户收益连接": ("客户收益连接", "customer_benefit", "benefit_linkage"),
    "证据使用": ("证据使用", "evidence_usage", "proof_usage"),
    "异议处理": ("异议处理", "objection_handling", "objection_response"),
    "推进下一步": ("推进下一步", "next_step", "advance_next_step"),
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
) -> dict[str, float]:
    raw_scores = dimension_scores if isinstance(dimension_scores, dict) else {}
    normalized: dict[str, float] = {}
    for canonical_name, aliases in SALES_DIMENSION_ALIASES.items():
        resolved_score: float | None = None
        for alias in aliases:
            value = raw_scores.get(alias)
            if isinstance(value, (int, float)):
                resolved_score = _clamp_score(value)
                break
        normalized[canonical_name] = (
            resolved_score if resolved_score is not None else _clamp_score(overall_score)
        )
    return normalized


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
            completeness_score if completeness_score is not None else rollups["completeness_score"]
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
                sales_scores["证据使用"] >= 68.0
                and sales_scores["推进下一步"] >= 65.0
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


def _sales_main_issue(metrics: dict[str, Any]) -> dict[str, str]:
    sales_scores = _resolve_sales_scores(metrics)
    candidates = [
        (
            min(sales_scores["价值表达"], sales_scores["客户收益连接"]),
            {
                "issue_type": "value_translation_gap",
                "issue_text": "还在讲产品功能，未把产品价值翻译成客户收益或业务结果。",
                "recovery_rule": "下一轮先说客户场景、收益指标和预期变化，再讲方案细节。",
            },
        ),
        (
            sales_scores["证据使用"],
            {
                "issue_type": "evidence_gap",
                "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
                "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
            },
        ),
        (
            sales_scores["异议处理"],
            {
                "issue_type": "objection_handling_gap",
                "issue_text": "面对价格、竞品或风险顾虑时，承接和重构回应还不够到位。",
                "recovery_rule": "下一轮先复述顾虑，再用收益、证据和试点方案回应。",
            },
        ),
        (
            sales_scores["推进下一步"],
            {
                "issue_type": "next_step_gap",
                "issue_text": "对话结束前没有形成明确的下一步动作、责任人或时间点。",
                "recovery_rule": "下一轮必须落到试点、会议、报价或负责人确认中的一个动作。",
            },
        ),
    ]
    _, issue = min(candidates, key=lambda item: item[0])
    return issue


def _sales_next_goal(metrics: dict[str, Any]) -> NextGoal:
    issue_type = _sales_main_issue(metrics)["issue_type"]
    if issue_type == "value_translation_gap":
        return {
            "goal_type": "value_to_benefit_translation",
            "goal_text": "先把产品价值翻译成客户收益，再进入方案说明。",
            "rule": "至少说清一个客户场景、一个收益指标、一个量化变化。",
        }
    if issue_type == "evidence_gap":
        return {
            "goal_type": "evidence_backing",
            "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
            "rule": "至少补上一条证据和一个明确的下一步动作。",
        }
    if issue_type == "objection_handling_gap":
        return {
            "goal_type": "objection_reframe",
            "goal_text": "下一轮先承接价格/竞品/风险顾虑，再用收益和证据回应。",
            "rule": "先复述顾虑，再给回应，最后落到低风险推进方案。",
        }
    return {
        "goal_type": "next_step_commitment",
        "goal_text": "下一轮必须把试点、会议、报价或责任人确认成明确下一步。",
        "rule": "每轮结尾至少确认一个动作、一个时间点和一个责任人。",
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
) -> dict[str, str]:
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
        main_issue = {
            "issue_type": "insufficient_sales_evidence",
            "issue_text": "当前有效销售证据不足，无法判断价值表达、证据使用和异议推进短板。",
            "recovery_rule": "至少完成一轮围绕ROI、价格、竞品或案例的有效问答后再结束。",
        }
        next_goal = {
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

    return {
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


def build_action_card(
    *,
    fuzzy_detections: Iterable[dict[str, Any]] | None = None,
    suggestions: Iterable[str] | None = None,
    pass_flags: PassFlags | None = None,
) -> ActionCard | None:
    """Build a single actionable card from realtime signals."""
    detections = [item for item in (fuzzy_detections or []) if isinstance(item, dict)]
    tips = [tip.strip() for tip in (suggestions or []) if isinstance(tip, str) and tip.strip()]

    issue = ""
    replacement = ""

    if detections:
        first = detections[0]
        matched = first.get("matched")
        if isinstance(matched, list) and matched:
            issue = f"检测到表达问题：{', '.join(str(x) for x in matched[:3])}"
        else:
            issue = "检测到表达不够具体"
        replacement = str(first.get("suggestion") or "请改用更具体的业务表达。"
        ).strip()
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

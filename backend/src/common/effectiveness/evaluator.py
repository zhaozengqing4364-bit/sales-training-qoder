"""Rule-v1 evaluator for communication training effectiveness."""

from __future__ import annotations

from typing import Any, Iterable

from common.effectiveness.schemas import ActionCard, NextGoal, OverallResult, PassFlags


RULE_VERSION = "rule_v1"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_pass_flags(metrics: dict[str, Any]) -> PassFlags:
    """Evaluate the three hard requirements with 80/20 thresholds."""
    continuous_speech_seconds = _to_float(metrics.get("continuous_speech_seconds"), 0.0)
    offtopic_turn_count = _to_float(metrics.get("offtopic_turn_count"), 99.0)
    offtopic_max_streak = _to_float(metrics.get("offtopic_max_streak"), 99.0)
    structure_coverage = _to_float(metrics.get("structure_coverage"), 0.0)

    return {
        "pass_3min_flow": continuous_speech_seconds >= 180.0,
        "pass_5turn_defense": offtopic_turn_count <= 1.0 and offtopic_max_streak < 2.0,
        "pass_4step_structure": structure_coverage >= 0.75,
    }


def resolve_next_goal(
    pass_flags: PassFlags, *, main_capability_passed: bool
) -> NextGoal:
    """Return exactly one next goal for the next training round."""
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
    pass_flags: PassFlags, *, main_capability_passed: bool
) -> dict[str, str]:
    """Return exactly one main issue for current session report."""
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

    return {
        "pass_flags": pass_flags,
        "main_capability_passed": bool(main_capability_passed),
        "overall_result": overall_result,
        "metrics": metrics,
        "main_issue": resolve_main_issue(
            pass_flags, main_capability_passed=bool(main_capability_passed)
        ),
        "next_goal": resolve_next_goal(
            pass_flags, main_capability_passed=bool(main_capability_passed)
        ),
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
        replacement = str(first.get("suggestion") or "请改用更具体的业务表达。").strip()
    elif tips:
        issue = "当前轮次有1个关键改进点"
        replacement = tips[0]

    if not issue or not replacement:
        return None

    if pass_flags and not pass_flags.get("pass_3min_flow", True):
        next_turn_rule = "下一轮先连续表达至少180秒，再回应客户追问。"
    elif pass_flags and not pass_flags.get("pass_5turn_defense", True):
        next_turn_rule = "下一轮先复述客户问题，再给出回答，避免跑题。"
    elif pass_flags and not pass_flags.get("pass_4step_structure", True):
        next_turn_rule = "下一轮按开场-需求-价值-下一步四段组织表达。"
    else:
        next_turn_rule = "下一轮先问1个具体需求问题，再给价值表达。"

    return {
        "issue": issue,
        "replacement": replacement,
        "next_turn_rule": next_turn_rule,
    }

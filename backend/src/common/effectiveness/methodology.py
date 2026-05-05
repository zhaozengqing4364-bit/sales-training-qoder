"""Methodology-aware sales rubric contract built on top of the canonical kernel.

T01 keeps the first-round methodology additive: we do not replace the existing
`logic / accuracy / completeness` rollups or the shipped `dimension_scores`
payloads. Instead we define one explicit rubric crosswalk that downstream
realtime, report, history, and admin surfaces can all reuse.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from .canonical import (
    CANONICAL_EVALUATION_KERNEL_VERSION,
    get_surface_reader_plan,
)

SalesMethodologyRubricId = Literal[
    "discovery_qualification",
    "value_story",
    "evidence_proof",
    "objection_reframe",
    "next_step_commitment",
]


_SUPPORTED_SURFACE_IDS: tuple[str, ...] = ("realtime", "report", "history", "admin")


_RUBRICS: tuple[dict[str, Any], ...] = (
    {
        "rubric_id": "discovery_qualification",
        "label": "Discovery / Qualification",
        "methodology_concept": "先确认客户现状、目标、优先级和决策线索，再进入价值表达。",
        "stage_ids": ["opening", "discovery"],
        "canonical_dimension_ids": [
            "customer_benefit_connection",
            "value_expression",
        ],
        "focus_type": "value_translation_gap",
        "main_issue_type": "value_translation_gap",
        "next_goal_type": "value_to_benefit_translation",
        "observable_evidence": [
            "客户现状/目标/损失被说清楚，而不是只讲产品功能。",
            "销售话术能把方案翻译成客户收益或业务结果。",
            "对预算、负责人、优先级等 qualification 线索有显式探查。",
        ],
        "calibration": {
            "healthy_min": 75,
            "watch_min": 60,
            "coach_for": "先补现状/目标/损失，再把产品价值翻译成客户收益。",
        },
        "shipped_boundary": (
            "qualification 当前仍并入 opening/discovery，因为现有 sales_stage capability "
            "还没有独立 qualification stage。"
        ),
    },
    {
        "rubric_id": "value_story",
        "label": "Value Story",
        "methodology_concept": "避免功能堆砌，持续把能力翻译成客户场景、收益和结果。",
        "stage_ids": ["discovery", "presentation"],
        "canonical_dimension_ids": ["value_expression"],
        "focus_type": "value_translation_gap",
        "main_issue_type": "value_translation_gap",
        "next_goal_type": "value_to_benefit_translation",
        "observable_evidence": [
            "话术里出现收益、ROI、效率、营收或风险变化。",
            "同一轮表达里能把方案和客户场景绑定，而不是泛泛介绍能力。",
        ],
        "calibration": {
            "healthy_min": 78,
            "watch_min": 62,
            "coach_for": "少讲模块，多讲客户收益、业务结果和目标变化。",
        },
        "shipped_boundary": "首轮仍复用 value_translation_gap 问题族，不再新造第二套 issue schema。",
    },
    {
        "rubric_id": "evidence_proof",
        "label": "Evidence / Proof",
        "methodology_concept": "价值主张必须被案例、数据、ROI 或 benchmark 支撑。",
        "stage_ids": ["presentation", "objection", "closing"],
        "canonical_dimension_ids": ["evidence_usage"],
        "focus_type": "evidence_gap",
        "main_issue_type": "evidence_gap",
        "next_goal_type": "evidence_backing",
        "observable_evidence": [
            "出现案例、数据、ROI、benchmark 等证据表达。",
            "claim_truth 可以区分 unsupported / weak / pending / verified。",
            "异议账本 promise 的证据能被补齐或明确承认缺口。",
        ],
        "calibration": {
            "healthy_min": 80,
            "watch_min": 65,
            "coach_for": "先补一条 ROI / 案例证据，再继续推进价格或方案讨论。",
        },
        "shipped_boundary": "首轮用 claim_truth + objection_ledger 做证据校准，不新增独立 proof engine。",
    },
    {
        "rubric_id": "objection_reframe",
        "label": "Objection Reframe",
        "methodology_concept": "顾虑出现后，先承接再重构，用收益和证据回应。",
        "stage_ids": ["objection", "closing"],
        "canonical_dimension_ids": ["objection_handling", "evidence_usage"],
        "focus_type": "objection_handling_gap",
        "main_issue_type": "objection_handling_gap",
        "next_goal_type": "objection_reframe",
        "observable_evidence": [
            "用户消息或 transcript_metadata 出现 objection_ledger。",
            "销售先复述价格/竞品/风险顾虑，再给证据或低风险推进方案。",
            "claim_truth 与 objection_ledger closure_state 一起解释异议是否真正闭环。",
        ],
        "calibration": {
            "healthy_min": 75,
            "watch_min": 60,
            "coach_for": "先复述顾虑，再给收益与证据回应，最后落到低风险推进。",
        },
        "shipped_boundary": "首轮只覆盖已显式落库的 objection_ledger family，不把所有异议类型都抽象成新 taxonomy。",
    },
    {
        "rubric_id": "next_step_commitment",
        "label": "Next-step Commitment",
        "methodology_concept": "每轮结束都要落到动作、时间点和责任人，而不是模糊收尾。",
        "stage_ids": ["closing"],
        "canonical_dimension_ids": ["next_step_commitment"],
        "focus_type": "next_step_gap",
        "main_issue_type": "next_step_gap",
        "next_goal_type": "next_step_commitment",
        "observable_evidence": [
            "出现试点、会议、报价、负责人、时间点等承诺语言。",
            "report/replay/history/admin 都能读到同一个 next_goal。",
            "closing 阶段不会只剩高分而丢失明确下一步动作。",
        ],
        "calibration": {
            "healthy_min": 72,
            "watch_min": 58,
            "coach_for": "优先锁定动作、时间点和责任人，再结束本轮。",
        },
        "shipped_boundary": "首轮不新增新的 closing-only score 字段，继续复用 next_goal / rule contract。",
    },
)


def _build_surface_contract(
    *,
    surface_id: str,
    evidence_paths: list[str],
    manager_view: str | None = None,
) -> dict[str, Any]:
    plan = get_surface_reader_plan(surface_id=surface_id, scenario_type="sales")
    payload = {
        "surface_id": surface_id,
        "primary_reader_id": plan.primary_reader_id,
        "compatibility_reader_ids": list(plan.compatibility_reader_ids),
        "mode": plan.mode,
        "evidence_paths": evidence_paths,
    }
    if isinstance(manager_view, str) and manager_view.strip():
        payload["manager_view"] = manager_view.strip()
    return payload


def get_sales_methodology_contract() -> dict[str, Any]:
    """Return the first-round methodology-aware rubric contract for sales.

    The contract is additive and intentionally grounded in current shipped
    surfaces so downstream slices can wire it into realtime/report/read-side
    consumers without inventing a second truth source.
    """

    return {
        "contract_id": "sales_methodology_rubric_v1",
        "methodology_id": "sales_execution_method_v1",
        "methodology_name": "首轮销售方法论-aware rubric",
        "scenario_type": "sales",
        "canonical_kernel_version": CANONICAL_EVALUATION_KERNEL_VERSION,
        "supported_surface_ids": list(_SUPPORTED_SURFACE_IDS),
        "compatibility_strategy": {
            "score_schema": "keep current rollups and dimension_scores as additive compatibility readers",
            "report_schema": "reuse main_issue / next_goal / claim_truth instead of introducing a new report payload",
            "stage_schema": "keep qualification merged into opening/discovery until sales_stage grows a dedicated stage",
        },
        "rubrics": [deepcopy(item) for item in _RUBRICS],
        "surface_contracts": [
            _build_surface_contract(
                surface_id="realtime",
                evidence_paths=[
                    "canonical_evaluation_kernel.dimensions[]",
                    "compatibility_readers.sales_realtime_score_snapshot_v1.dimension_scores",
                    "dimensions[]",
                ],
            ),
            _build_surface_contract(
                surface_id="report",
                evidence_paths=[
                    "canonical_evaluation_kernel.dimensions[]",
                    "effectiveness_snapshot.main_issue",
                    "effectiveness_snapshot.next_goal",
                    "effectiveness_snapshot.claim_truth",
                ],
            ),
            _build_surface_contract(
                surface_id="history",
                evidence_paths=[
                    "canonical_evaluation_kernel.dimensions[]",
                    "effectiveness_snapshot.main_issue",
                    "effectiveness_snapshot.next_goal",
                    "feedback_summary",
                ],
                manager_view="cohort_trends",
            ),
            _build_surface_contract(
                surface_id="admin",
                evidence_paths=[
                    "canonical_evaluation_kernel.dimensions[]",
                    "effectiveness_snapshot.main_issue",
                    "effectiveness_snapshot.next_goal",
                    "effectiveness_snapshot.claim_truth",
                ],
                manager_view="intervention_queue",
            ),
        ],
    }


def build_sales_dimension_rubric_map() -> dict[str, list[str]]:
    """Map canonical sales dimensions to the rubric ids they support."""

    mapping: dict[str, list[str]] = {}
    for rubric in _RUBRICS:
        rubric_id = str(rubric["rubric_id"])
        for dimension_id in rubric.get("canonical_dimension_ids", []):
            if not isinstance(dimension_id, str) or not dimension_id:
                continue
            mapping.setdefault(dimension_id, []).append(rubric_id)
    return mapping


def _coerce_methodology_score(value: Any) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = 0.0
    return round(max(0.0, min(100.0, normalized)), 2)


def _resolve_calibration_status(*, score: float, calibration: dict[str, Any]) -> str:
    healthy_min = _coerce_methodology_score(calibration.get("healthy_min"))
    watch_min = _coerce_methodology_score(calibration.get("watch_min"))
    if score >= healthy_min:
        return "healthy"
    if score >= watch_min:
        return "watch"
    return "gap"


def build_sales_methodology_summary(
    *,
    canonical_kernel: dict[str, Any],
    surface_id: str,
    current_stage: str | None = None,
    main_issue: dict[str, Any] | None = None,
    next_goal: dict[str, Any] | None = None,
    claim_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a cross-surface methodology summary from canonical evidence."""

    contract = get_sales_methodology_contract()
    dimensions = (
        canonical_kernel.get("dimensions")
        if isinstance(canonical_kernel, dict)
        else None
    )
    if not isinstance(dimensions, list):
        dimensions = []

    dimensions_by_id = {
        str(item.get("dimension_id")): item
        for item in dimensions
        if isinstance(item, dict) and isinstance(item.get("dimension_id"), str)
    }

    normalized_stage = str(current_stage or "").strip().lower() or None
    issue_type = (
        str(main_issue.get("issue_type")).strip()
        if isinstance(main_issue, dict) and main_issue.get("issue_type") is not None
        else None
    )
    goal_type = (
        str(next_goal.get("goal_type")).strip()
        if isinstance(next_goal, dict) and next_goal.get("goal_type") is not None
        else None
    )
    claim_truth_status = (
        str(claim_truth.get("status")).strip()
        if isinstance(claim_truth, dict) and claim_truth.get("status") is not None
        else None
    )

    rubric_assessments: list[dict[str, Any]] = []
    active_rubric_id: str | None = None

    for rubric in contract["rubrics"]:
        scored_dimensions: list[dict[str, Any]] = []
        for dimension_id in rubric.get("canonical_dimension_ids", []):
            if not isinstance(dimension_id, str):
                continue
            payload = dimensions_by_id.get(dimension_id)
            if not isinstance(payload, dict):
                continue
            scored_dimensions.append(
                {
                    "dimension_id": dimension_id,
                    "label": str(payload.get("label") or dimension_id),
                    "score": _coerce_methodology_score(payload.get("score")),
                }
            )

        rubric_score = round(
            sum(item["score"] for item in scored_dimensions)
            / max(1, len(scored_dimensions)),
            2,
        )
        calibration = dict(rubric.get("calibration") or {})
        calibration_status = _resolve_calibration_status(
            score=rubric_score,
            calibration=calibration,
        )
        stage_match = normalized_stage in {
            str(item).strip().lower()
            for item in (rubric.get("stage_ids") or [])
            if isinstance(item, str) and item.strip()
        }
        issue_match = issue_type == rubric.get("main_issue_type")
        goal_match = goal_type == rubric.get("next_goal_type")
        if active_rubric_id is None and (issue_match or goal_match or stage_match):
            active_rubric_id = str(rubric["rubric_id"])

        rubric_assessments.append(
            {
                "rubric_id": str(rubric["rubric_id"]),
                "label": str(rubric.get("label") or rubric["rubric_id"]),
                "score": rubric_score,
                "status": calibration_status,
                "matched": bool(stage_match or issue_match or goal_match),
                "current_stage_match": bool(stage_match),
                "issue_type_match": bool(issue_match),
                "goal_type_match": bool(goal_match),
                "focus_type": rubric.get("focus_type"),
                "main_issue_type": rubric.get("main_issue_type"),
                "next_goal_type": rubric.get("next_goal_type"),
                "canonical_dimension_ids": list(
                    rubric.get("canonical_dimension_ids") or []
                ),
                "dimension_scores": scored_dimensions,
                "calibration": {
                    "healthy_min": _coerce_methodology_score(
                        calibration.get("healthy_min")
                    ),
                    "watch_min": _coerce_methodology_score(
                        calibration.get("watch_min")
                    ),
                    "coach_for": calibration.get("coach_for"),
                },
            }
        )

    if active_rubric_id is None and rubric_assessments:
        active_rubric_id = min(
            rubric_assessments,
            key=lambda item: (
                float(item.get("score") or 0.0),
                str(item.get("rubric_id") or ""),
            ),
        )["rubric_id"]

    weakest_rubric_id = (
        min(
            rubric_assessments,
            key=lambda item: (
                float(item.get("score") or 0.0),
                str(item.get("rubric_id") or ""),
            ),
        )["rubric_id"]
        if rubric_assessments
        else None
    )

    surface_contracts = {
        str(item["surface_id"]): item
        for item in contract["surface_contracts"]
        if isinstance(item, dict) and isinstance(item.get("surface_id"), str)
    }
    surface_contract = dict(surface_contracts.get(surface_id) or {})

    return {
        "contract_id": contract["contract_id"],
        "methodology_id": contract["methodology_id"],
        "methodology_name": contract["methodology_name"],
        "surface_id": surface_id,
        "surface_reader_id": canonical_kernel.get("primary_reader_id"),
        "current_stage": normalized_stage,
        "main_issue_type": issue_type,
        "next_goal_type": goal_type,
        "claim_truth_status": claim_truth_status,
        "active_rubric_id": active_rubric_id,
        "weakest_rubric_id": weakest_rubric_id,
        "summary": {
            "healthy_count": sum(
                1 for item in rubric_assessments if item["status"] == "healthy"
            ),
            "watch_count": sum(
                1 for item in rubric_assessments if item["status"] == "watch"
            ),
            "gap_count": sum(
                1 for item in rubric_assessments if item["status"] == "gap"
            ),
        },
        "evidence_paths": list(surface_contract.get("evidence_paths") or []),
        "rubric_assessments": rubric_assessments,
    }


__all__ = [
    "SalesMethodologyRubricId",
    "build_sales_dimension_rubric_map",
    "build_sales_methodology_summary",
    "get_sales_methodology_contract",
]

"""Helpers for carrying one unresolved objection across realtime turns."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from common.business_rules.defaults import (
    OBJECTION_LEDGER_RULES_KEY,
    get_default_business_rule_value,
)
from common.business_rules.validators import (
    BusinessRuleValidationError,
    validate_business_rule_value,
)
from common.conversation.storage import normalize_objection_ledger
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

_NUMERIC_SIGNAL_RE = re.compile(r"\d")


def resolve_objection_ledger_ruleset(
    ruleset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the governed objection-ledger ruleset with safe fallback.

    Runtime callers can pass an already-resolved admin/business-rule value.
    Until the WebSocket runtime has a DB-backed injection point, the bundled
    default is the central seed and the admin backlog is captured in metadata.
    """
    raw_ruleset = (
        deepcopy(ruleset)
        if isinstance(ruleset, dict)
        else get_default_business_rule_value(OBJECTION_LEDGER_RULES_KEY)
    )
    try:
        return validate_business_rule_value(OBJECTION_LEDGER_RULES_KEY, raw_ruleset)
    except BusinessRuleValidationError as exc:
        logger.warning(
            "objection_ledger_ruleset_invalid_using_default",
            error=str(exc),
        )
        fallback = get_default_business_rule_value(OBJECTION_LEDGER_RULES_KEY)
        return validate_business_rule_value(OBJECTION_LEDGER_RULES_KEY, fallback)


def resolve_turn_objection_ledger(
    *,
    existing_ledger: dict[str, Any] | None,
    user_text: str,
    stage_context: dict[str, Any] | None,
    score_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the ledger state that should be persisted for the current turn."""
    existing = normalize_objection_ledger(existing_ledger)
    normalized_text = _normalize_text(user_text)

    if existing is not None and existing.get("closure_state") == "open":
        family = str(existing["objection_family"])
        if _looks_like_gap_acknowledgement(normalized_text, family):
            updated = dict(existing)
            updated["closure_state"] = "gap_acknowledged"
            return normalize_objection_ledger(updated)
        if _looks_like_evidence_provided(normalized_text, family):
            updated = dict(existing)
            updated["closure_state"] = "evidence_provided"
            return normalize_objection_ledger(updated)

    detected_family = _detect_objection_family(normalized_text)
    if detected_family and _should_open_new_ledger(
        detected_family=detected_family,
        stage_context=stage_context,
        score_context=score_context,
    ):
        return _build_open_ledger(detected_family)

    return existing


def build_arbiter_override_context(
    *,
    objection_ledger: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return synthetic stage/score context that keeps pressure on one open objection."""
    normalized = normalize_objection_ledger(objection_ledger)
    if normalized is None or normalized.get("closure_state") != "open":
        return None, None

    family = str(normalized["objection_family"])
    config = _LEDGER_FAMILY_CONFIG.get(family)
    if not isinstance(config, dict):
        return None, None

    focus_dimension = str(config["focus_dimension"])
    dimension_scores = dict(_SYNTHETIC_DIMENSIONS_BY_FOCUS[focus_dimension])
    evidence_prompt = str(
        normalized.get("next_expected_evidence")
        or normalized.get("promised_proof")
        or config["next_expected_evidence"]
    ).strip()

    stage_context = {
        "current_stage": "objection",
        "stage_name": "异议处理",
    }
    score_context = {
        "overall_score": 72.0,
        "dimension_scores": dimension_scores,
        "stage_name": "异议处理",
        "suggestions": [evidence_prompt] if evidence_prompt else [],
    }
    return stage_context, score_context


def merge_arbiter_context_with_objection_ledger(
    *,
    objection_ledger: dict[str, Any] | None,
    stage_context: dict[str, Any] | None,
    score_context: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Prefer open-ledger arbiter context; otherwise keep the live runtime context."""
    override_stage, override_score = build_arbiter_override_context(
        objection_ledger=objection_ledger,
    )
    return (
        override_stage if override_stage is not None else stage_context,
        override_score if override_score is not None else score_context,
    )


def _build_open_ledger(family: str) -> dict[str, Any] | None:
    config = _LEDGER_FAMILY_CONFIG.get(family)
    if not isinstance(config, dict):
        return None
    return normalize_objection_ledger(
        {
            "objection_family": family,
            "promised_proof": config["promised_proof"],
            "next_expected_evidence": config["next_expected_evidence"],
            "closure_state": "open",
        }
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def _detect_objection_family(normalized_text: str) -> str | None:
    if not normalized_text:
        return None
    for family in (
        "price_pressure",
        "competitor_alternative",
        "implementation_risk",
        "roi_proof",
    ):
        config = _LEDGER_FAMILY_CONFIG[family]
        if any(token in normalized_text for token in config["detect_any"]):
            return family
    return None


def _should_open_new_ledger(
    *,
    detected_family: str,
    stage_context: dict[str, Any] | None,
    score_context: dict[str, Any] | None,
) -> bool:
    stage_name = _normalize_text(
        (stage_context or {}).get("current_stage")
        or (stage_context or {}).get("stage_name")
    )
    weakest_dimension = _resolve_weakest_sales_dimension(score_context)
    family_focus = _LEDGER_FAMILY_CONFIG[detected_family]["focus_dimension"]

    if detected_family == "roi_proof":
        if not _looks_like_unresolved_roi_pressure(stage_name, score_context):
            return False
    elif stage_name not in {
        "objection",
        "异议处理",
        "价格博弈",
    } and weakest_dimension not in {
        "证据使用",
        "异议处理",
    }:
        return False

    if stage_name in {"objection", "异议处理", "价格博弈"}:
        return True
    if weakest_dimension == family_focus:
        return True
    return weakest_dimension in {"证据使用", "异议处理"}


def _looks_like_new_pressure(normalized_text: str, family: str) -> bool:
    if not normalized_text:
        return False

    if family == "roi_proof":
        return any(
            token in normalized_text
            for token in (
                "证明",
                "凭什么",
                "没有",
                "缺",
                "不足",
                "担心",
                "顾虑",
                "怎么",
                "为何",
            )
        ) and any(
            token in normalized_text
            for token in ("roi", "回本", "案例", "数据", "证据", "收益")
        )
    if family == "price_pressure":
        return any(
            token in normalized_text
            for token in ("价格", "报价", "预算", "折扣", "贵", "成本", "担心", "顾虑")
        )
    if family == "competitor_alternative":
        return any(
            token in normalized_text
            for token in ("竞品", "竞对", "替代", "对比", "差异", "担心", "顾虑")
        )
    if family == "implementation_risk":
        return any(
            token in normalized_text
            for token in (
                "实施",
                "落地",
                "上线",
                "排期",
                "试点",
                "风险",
                "担心",
                "顾虑",
            )
        ) and any(
            token in normalized_text
            for token in ("实施", "落地", "上线", "排期", "试点", "风险")
        )
    return False


def _looks_like_unresolved_roi_pressure(
    stage_name: str,
    score_context: dict[str, Any] | None,
) -> bool:
    if stage_name in {"objection", "异议处理", "价格博弈"}:
        return True
    weakest_dimension = _resolve_weakest_sales_dimension(score_context)
    return weakest_dimension == "证据使用"


def _resolve_weakest_sales_dimension(
    score_context: dict[str, Any] | None,
) -> str | None:
    raw_scores = (score_context or {}).get("dimension_scores")
    if not isinstance(raw_scores, dict) or not raw_scores:
        return None

    canonical_scores: dict[str, float] = {}
    for key, value in raw_scores.items():
        if not isinstance(value, (int, float)):
            continue
        key_text = str(key).strip().lower()
        if key_text in {"价值表达", "value_expression", "value_articulation"}:
            canonical_scores["价值表达"] = float(value)
        elif key_text in {"客户收益连接", "customer_benefit", "benefit_linkage"}:
            canonical_scores["客户收益连接"] = float(value)
        elif key_text in {"证据使用", "evidence_usage", "proof_usage"}:
            canonical_scores["证据使用"] = float(value)
        elif key_text in {"异议处理", "objection_handling", "objection_response"}:
            canonical_scores["异议处理"] = float(value)
        elif key_text in {"推进下一步", "next_step", "advance_next_step"}:
            canonical_scores["推进下一步"] = float(value)

    if not canonical_scores:
        return None
    return min(canonical_scores, key=canonical_scores.get)


def _looks_like_gap_acknowledgement(normalized_text: str, family: str) -> bool:
    config = _LEDGER_FAMILY_CONFIG.get(family)
    if not isinstance(config, dict):
        return False
    if not any(pattern in normalized_text for pattern in _ACK_PATTERNS):
        return False
    return any(token in normalized_text for token in config["evidence_any"])


def _looks_like_evidence_provided(normalized_text: str, family: str) -> bool:
    config = _LEDGER_FAMILY_CONFIG.get(family)
    if not isinstance(config, dict):
        return False

    has_family_signal = any(
        token in normalized_text for token in config["evidence_any"]
    )
    if not has_family_signal:
        return False

    if family == "implementation_risk":
        return True

    if any(pattern in normalized_text for pattern in _ACK_PATTERNS):
        return False

    return bool(_NUMERIC_SIGNAL_RE.search(normalized_text)) or any(
        token in normalized_text
        for token in (
            "benchmark",
            "%",
            "提升",
            "下降",
            "回本周期",
            "回收周期",
            "月内",
            "周内",
        )
    )

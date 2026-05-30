"""Focused tests for persona policy normalization."""

from __future__ import annotations

import json

from agent.services.persona_policy import (
    PersonaPolicyValidator,
    format_persona_policy_validation_failure,
    normalize_persona_policy,
)


def test_normalize_persona_policy_derives_customer_pressure_from_legacy_extensions():
    normalized = normalize_persona_policy(
        {
            "sales_focus": " value_translation ",
            "value_axes": [" 客户收益 ", "ROI", "", "ROI"],
            "objection_axes": ["价格", "竞品", None, "价格"],
            "expected_customer_questions": [
                " 你怎么证明 ROI？ ",
                "",
                "你怎么证明 ROI？",
            ],
        },
        fallback_system_prompt=" legacy prompt ",
        fallback_kb_ids=["kb-1", "", "kb-1"],
    )

    assert normalized["system_prompt"] == "legacy prompt"
    assert normalized["knowledge_base_ids"] == ["kb-1"]
    assert normalized["customer_pressure"] == {
        "source": "legacy_sales_focus_extensions",
        "pressure_direction": {
            "sales_focus": "value_translation",
            "value_axes": ["客户收益", "ROI"],
            "objection_axes": ["价格", "竞品"],
        },
        "follow_up_behavior": {
            "question_strategy": "single_issue",
            "revisit_on_evasion": True,
            "require_evidence": True,
            "expected_customer_questions": ["你怎么证明 ROI？"],
        },
    }
    assert normalized["sales_focus"] == "value_translation"
    assert normalized["value_axes"] == ["客户收益", "ROI"]
    assert normalized["objection_axes"] == ["价格", "竞品"]
    assert normalized["expected_customer_questions"] == ["你怎么证明 ROI？"]


def test_normalize_persona_policy_prefers_explicit_customer_pressure_and_backfills_legacy_fields():
    normalized = normalize_persona_policy(
        {
            "sales_focus": "generic_follow_up",
            "value_axes": ["泛化痛点"],
            "expected_customer_questions": ["旧问题"],
            "customer_pressure": {
                "pressure_direction": {
                    "sales_focus": " proof ",
                    "value_axes": [" 案例证据 ", "ROI", "ROI"],
                    "objection_axes": ["价格", "竞品", ""],
                },
                "follow_up_behavior": {
                    "question_strategy": " single_issue ",
                    "revisit_on_evasion": False,
                    "require_evidence": "true",
                    "expected_customer_questions": [
                        " 你怎么证明这点？ ",
                        "你怎么证明这点？",
                    ],
                },
            },
        },
        fallback_system_prompt="persona prompt",
        fallback_kb_ids=[],
    )

    assert normalized["customer_pressure"] == {
        "source": "explicit",
        "pressure_direction": {
            "sales_focus": "proof",
            "value_axes": ["案例证据", "ROI"],
            "objection_axes": ["价格", "竞品"],
        },
        "follow_up_behavior": {
            "question_strategy": "single_issue",
            "revisit_on_evasion": False,
            "require_evidence": True,
            "expected_customer_questions": ["你怎么证明这点？"],
        },
    }
    assert normalized["sales_focus"] == "proof"
    assert normalized["value_axes"] == ["案例证据", "ROI"]
    assert normalized["objection_axes"] == ["价格", "竞品"]
    assert normalized["expected_customer_questions"] == ["你怎么证明这点？"]


def test_persona_policy_validator_skips_when_role_anchor_missing():
    assert PersonaPolicyValidator.validate({"system_prompt": "prompt"}) == []


def test_persona_policy_validator_requires_bottom_line_min_length():
    errors = PersonaPolicyValidator.validate(
        {
            "role_anchor": {
                "identity_template": "你是{role_name}，{relationship_stage}。{bottom_line}",
                "bottom_line": "太短",
            }
        }
    )

    assert len(errors) == 1
    assert errors[0].field == "persona_policy.role_anchor.bottom_line"
    assert errors[0].reason_code == "role_anchor_bottom_line_required"


def test_persona_policy_validator_rejects_unknown_identity_template_vars():
    errors = PersonaPolicyValidator.validate(
        {
            "role_anchor": {
                "identity_template": "你是{role_name}，预算{budget_limit}。{bottom_line}",
                "bottom_line": "你不认识他，保持初次见面的审慎与距离感。",
            }
        }
    )

    assert len(errors) == 1
    assert errors[0].field == "persona_policy.role_anchor.identity_template"
    assert errors[0].reason_code == "role_anchor_identity_template_invalid_vars"


def test_persona_policy_validator_enforces_must_not_length_limit():
    errors = PersonaPolicyValidator.validate(
        {
            "role_anchor": {
                "bottom_line": "你不认识他，保持初次见面的审慎与距离感。",
                "must_not": "x" * 201,
            }
        }
    )

    assert len(errors) == 1
    assert errors[0].field == "persona_policy.role_anchor.must_not"
    assert errors[0].reason_code == "role_anchor_must_not_too_long"


def test_persona_policy_validator_accepts_valid_role_anchor():
    errors = PersonaPolicyValidator.validate(
        {
            "role_anchor": {
                "identity_template": "你是{role_name}，{relationship_stage}。{bottom_line}",
                "bottom_line": "你不认识他，保持初次见面的审慎与距离感。",
                "must_do": "追问量化 ROI 和落地风险。",
                "must_not": "闲聊叙旧、主动让步。",
            }
        }
    )

    assert errors == []


def test_format_persona_policy_validation_failure_returns_field_level_reason_codes():
    errors = PersonaPolicyValidator.validate(
        {
            "role_anchor": {
                "bottom_line": "短",
                "must_not": "y" * 201,
            }
        }
    )

    payload = json.loads(format_persona_policy_validation_failure(errors))

    assert payload["error"] == "[PERSONA_POLICY_VALIDATION_FAILED]"
    assert {item["reason_code"] for item in payload["errors"]} == {
        "role_anchor_bottom_line_required",
        "role_anchor_must_not_too_long",
    }


def test_normalize_persona_policy_preserves_role_anchor_extension():
    normalized = normalize_persona_policy(
        {
            "role_anchor": {
                "bottom_line": "你不认识他，保持初次见面的审慎与距离感。",
            }
        },
        fallback_system_prompt="prompt",
        fallback_kb_ids=[],
    )

    assert normalized["role_anchor"]["bottom_line"].startswith("你不认识他")

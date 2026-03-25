"""Focused tests for persona policy normalization."""

from __future__ import annotations

from agent.services.persona_policy import normalize_persona_policy


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

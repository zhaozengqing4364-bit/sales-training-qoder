from __future__ import annotations

from foundation_ai_quality import (
    FoundationAIQualityManifest,
    evaluate_foundation_ai_quality,
    load_foundation_ai_quality_manifest,
)


def test_foundation_gold_set_covers_every_frozen_ai_capability_and_passes() -> None:
    report = evaluate_foundation_ai_quality(load_foundation_ai_quality_manifest())

    assert report["status"] == "passed"
    assert report["case_count"] == 8
    assert set(report["capabilities"]) == {
        "question_generation",
        "short_answer_scoring",
        "audio_scoring",
        "coach_card_generation",
        "coach_answer_evaluation",
        "readiness_dossier_summary",
    }
    assert report["metrics"] == {
        "schema_validity_rate": 1.0,
        "invalid_rejection_rate": 1.0,
        "evidence_coverage_rate": 1.0,
        "factual_error_rate": 0.0,
        "hallucination_reference_rate": 0.0,
        "degradation_contract_rate": 1.0,
        "stability_rate": 1.0,
        "total_cost_minor_units": 6,
        "currency": "CNY",
    }


def test_foundation_gold_set_blocks_unknown_evidence_reference() -> None:
    manifest = load_foundation_ai_quality_manifest()
    raw = manifest.model_dump(mode="json")
    first = raw["cases"][0]
    first["output"]["questions"][0]["source_anchor_ids"] = ["unknown-anchor"]
    broken = FoundationAIQualityManifest.model_validate(raw)

    report = evaluate_foundation_ai_quality(broken)

    assert report["status"] == "failed"
    assert report["metrics"]["hallucination_reference_rate"] > 0
    assert "hallucination_reference_rate" in report["gate_failures"]
    result = next(
        item
        for item in report["results"]
        if item["case_id"] == "question_generation_grounded_single_choice"
    )
    assert "unknown_evidence_reference" in result["failures"]


def test_stability_allows_language_variation_when_business_contract_is_unchanged() -> None:
    manifest = load_foundation_ai_quality_manifest()
    raw = manifest.model_dump(mode="json")
    first = raw["cases"][0]
    repeated = first["output"].copy()
    repeated["questions"] = [first["output"]["questions"][0].copy()]
    repeated_question = repeated["questions"][0]
    repeated_question["stem"] = "当客户担心项目交付风险时，销售应先采取哪项行动？"
    repeated_question["explanation"] = "先澄清风险和业务影响，再提出有依据的后续方案。"
    first["repeat_outputs"] = [repeated]

    report = evaluate_foundation_ai_quality(
        FoundationAIQualityManifest.model_validate(raw)
    )

    assert report["status"] == "passed"
    assert report["metrics"]["stability_rate"] == 1.0


def test_stability_rejects_repeat_with_decision_drift() -> None:
    manifest = load_foundation_ai_quality_manifest()
    raw = manifest.model_dump(mode="json")
    case = next(
        item
        for item in raw["cases"]
        if item["case_id"] == "short_answer_scoring_rubric_evidence"
    )
    repeated = case["output"].copy()
    repeated["answers"] = [case["output"]["answers"][0].copy()]
    repeated["answers"][0]["awarded_points"] = 0
    repeated["answers"][0]["rubric_evidence"] = [
        {
            "criterion": "识别风险",
            "met": False,
            "reason": "回答提到了上线计划，但没有说明影响。",
        }
    ]
    case["repeat_outputs"] = [repeated]

    report = evaluate_foundation_ai_quality(
        FoundationAIQualityManifest.model_validate(raw)
    )

    assert report["status"] == "failed"
    result = next(
        item
        for item in report["results"]
        if item["case_id"] == "short_answer_scoring_rubric_evidence"
    )
    assert "unstable_output" in result["failures"]


def test_stability_ignores_non_authoritative_coach_mastered_draft() -> None:
    manifest = load_foundation_ai_quality_manifest()
    raw = manifest.model_dump(mode="json")
    case = next(
        item
        for item in raw["cases"]
        if item["case_id"] == "coach_evaluation_answer_and_source_evidence"
    )
    repeated = case["output"].copy()
    repeated["mastered"] = not repeated["mastered"]
    case["repeat_outputs"] = [repeated]

    report = evaluate_foundation_ai_quality(
        FoundationAIQualityManifest.model_validate(raw)
    )

    assert report["status"] == "passed"
    assert report["metrics"]["stability_rate"] == 1.0

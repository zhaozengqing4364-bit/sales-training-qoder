from __future__ import annotations

from sales_trainer.services.unit_public_payloads import learner_safe_unit_payload


def test_should_remove_ai_coach_admin_config_from_learner_unit_payload() -> None:
    payload = {
        "unit_id": "unit-business",
        "config": {
            "path": {
                "module_key": "business_skills",
                "learning_content_id": "content-1",
                "ai_coach": {
                    "enabled": True,
                    "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                    "prompt_revision_id": "revision-1",
                    "prompt_contract_hash": "hash-internal",
                    "scoring_prompt_template_id": "22222222-2222-2222-2222-222222222222",
                    "scoring_prompt_revision_id": "revision-2",
                    "answer_key": {"option_ids": ["A"]},
                    "scoring_rubric": {"max_score": 100},
                    "interaction_snapshot": {"stem": "internal"},
                    "path_config_snapshot": {"enabled": True},
                    "config_snapshot": {"enabled": True},
                },
            },
            "learner": {"learning_content_id": "content-1"},
        },
    }

    safe_payload = learner_safe_unit_payload(payload)

    assert safe_payload["config"]["path"] == {
        "module_key": "business_skills",
        "learning_content_id": "content-1",
    }
    assert "ai_coach" not in safe_payload["config"]["path"]
    for internal_field in (
        "prompt_template_id",
        "prompt_revision_id",
        "prompt_contract_hash",
        "scoring_prompt_template_id",
        "scoring_prompt_revision_id",
        "answer_key",
        "scoring_rubric",
        "interaction_snapshot",
        "path_config_snapshot",
        "config_snapshot",
    ):
        assert internal_field not in str(safe_payload)
    assert payload["config"]["path"]["ai_coach"]["prompt_template_id"]


def test_should_keep_unit_payload_unchanged_when_ai_coach_config_is_absent() -> None:
    payload = {
        "unit_id": "unit-ppt",
        "config": {
            "path": {
                "module_key": "ppt_delivery",
                "learning_content_id": "content-1",
            },
        },
    }

    safe_payload = learner_safe_unit_payload(payload)

    assert safe_payload is payload


def test_should_strip_internal_fields_even_without_ai_coach_config() -> None:
    payload = {
        "unit_id": "unit-ppt",
        "raw_model_output": {"text": "internal"},
        "config": {
            "path": {
                "module_key": "ppt_delivery",
                "learning_content_id": "content-1",
            },
            "answer_key": {"correct": "A"},
            "nested": {"scoring_rubric": {"max_score": 100}},
        },
    }

    safe_payload = learner_safe_unit_payload(payload)

    assert safe_payload["unit_id"] == "unit-ppt"
    assert "raw_model_output" not in safe_payload
    assert "answer_key" not in safe_payload["config"]
    assert safe_payload["config"]["nested"] == {}
    assert payload["raw_model_output"] == {"text": "internal"}

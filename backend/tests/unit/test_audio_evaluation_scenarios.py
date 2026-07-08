from __future__ import annotations

import pytest

from sales_trainer.models import SalesTrainerUnit
from sales_trainer.services.audio_evaluation_scenarios import (
    resolve_audio_evaluation_scenario,
    resolve_audio_evaluation_scenario_from_config,
)
from sales_trainer.services.audio_submission_service import (
    AudioSubmissionService,
    AudioSubmissionServiceError,
)
from sales_trainer.services.material_service import (
    MaterialServiceError,
    validate_unit_material_and_brief_config,
)


def test_should_resolve_company_product_demo_from_scenario_key() -> None:
    scenario = resolve_audio_evaluation_scenario(
        scenario_key="company_product_demo",
    )

    assert scenario is not None
    assert scenario.purpose_key == "company_product_demo"
    assert scenario.requires_confirmed_material is True
    assert scenario.module_type == "audio_scoring"


def test_should_resolve_legacy_ppt_purpose_to_audio_scenario() -> None:
    scenario = resolve_audio_evaluation_scenario_from_config(
        {"audio": {"purpose": "ppt_pitch"}},
    )

    assert scenario is not None
    assert scenario.scenario_key == "ppt_explanation"
    assert scenario.material_error_code == "[PPT_MATERIAL_BINDING_REQUIRED]"


def test_should_require_confirmed_material_for_company_product_demo() -> None:
    with pytest.raises(MaterialServiceError) as exc:
        validate_unit_material_and_brief_config(
            {
                "audio": {
                    "purpose": "company_product_demo",
                    "scenario_key": "company_product_demo",
                },
                "materials": {"bindings": []},
            },
        )

    assert exc.value.code == "[AUDIO_EVALUATION_MATERIAL_BINDING_REQUIRED]"


def test_should_keep_ppt_legacy_material_error_code() -> None:
    with pytest.raises(MaterialServiceError) as exc:
        validate_unit_material_and_brief_config(
            {
                "audio": {"purpose": "ppt_pitch"},
                "materials": {"bindings": []},
            },
        )

    assert exc.value.code == "[PPT_MATERIAL_BINDING_REQUIRED]"


def test_should_apply_product_demo_material_gate_to_audio_submission() -> None:
    service = AudioSubmissionService(None)  # type: ignore[arg-type]
    unit = SalesTrainerUnit(
        name="公司产品 Demo",
        unit_type="audio_scoring",
        status="published",
        config={
            "audio": {
                "purpose": "company_product_demo",
                "scenario_key": "company_product_demo",
            },
            "materials": {"bindings": []},
        },
    )

    with pytest.raises(AudioSubmissionServiceError) as exc:
        service._require_material_binding_for_audio_scenario(
            unit,
            "company_product_demo",
        )

    assert exc.value.code == "[AUDIO_EVALUATION_MATERIAL_BINDING_REQUIRED]"


def test_should_allow_optional_material_audio_scenario_submission() -> None:
    service = AudioSubmissionService(None)  # type: ignore[arg-type]
    unit = SalesTrainerUnit(
        name="金字塔演讲",
        unit_type="audio_scoring",
        status="published",
        config={
            "audio": {
                "purpose": "elevator_pitch",
                "scenario_key": "elevator_pitch",
            },
            "materials": {"bindings": []},
        },
    )

    service._require_material_binding_for_audio_scenario(unit, "elevator_pitch")

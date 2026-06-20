from __future__ import annotations

import pytest

from admin.config_bundles.adapters import list_config_bundle_adapters
from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY
from common.db.models import PromptTemplate
from common.effectiveness.scoring_rulesets import SCORING_RULESETS_BUNDLE_KEY


@pytest.mark.asyncio
async def test_config_bundle_inventory_includes_governed_surfaces(test_db) -> None:
    prompt = PromptTemplate(
        name="Business etiquette question generator",
        prompt_type="question_generation",
        business_purpose="business_etiquette_question_generation",
        category="business_etiquette",
        template="Generate {{ count }} questions",
        variables=["count"],
        is_active=True,
        is_default=True,
        is_system=False,
    )
    test_db.add(prompt)
    await test_db.flush()

    adapters = list_config_bundle_adapters()
    bundles = {adapter.bundle_key: await adapter.bundle(test_db) for adapter in adapters}

    assert {
        "sales_trainer.newcomer_path_config",
        "sales_trainer.ai_coach_config",
        ROLEPLAY_SITUATION_PACKS_KEY,
        SCORING_RULESETS_BUNDLE_KEY,
        "prompt_templates",
    }.issubset(bundles)
    assert bundles["prompt_templates"].overview["template_count"] == 1
    assert bundles["prompt_templates"].overview["default_template_count"] == 1

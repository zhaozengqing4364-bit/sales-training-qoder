from __future__ import annotations

from types import SimpleNamespace

from agent.schemas import PersonaResponse, normalize_persona_traits


def test_normalize_persona_traits_coerces_list_values() -> None:
    assert normalize_persona_traits({"关注点": ["风险", "交付", "案例"]}) == {
        "关注点": "风险、交付、案例",
    }


def test_persona_response_accepts_legacy_list_trait_values() -> None:
    persona = SimpleNamespace(
        id="persona-1",
        name="测试角色",
        description=None,
        icon=None,
        category="customer",
        difficulty="medium",
        system_prompt="你是客户。",
        traits={"性格": "怀疑", "关注点": ["风险", "交付", "案例"]},
        knowledge_base_ids=[],
        persona_policy={},
        behavior_config={},
        scoring_weights=None,
        tts_config=None,
        is_public=True,
        status="active",
        created_by=None,
        created_at="2026-05-20T10:00:00Z",
        updated_at="2026-05-20T10:00:00Z",
        governance_summary=None,
    )

    response = PersonaResponse.model_validate(persona)

    assert response.traits["关注点"] == "风险、交付、案例"

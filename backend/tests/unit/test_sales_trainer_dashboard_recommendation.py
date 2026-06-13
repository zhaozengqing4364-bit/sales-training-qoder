from __future__ import annotations

from sales_trainer.dashboard_recommendation import (
    build_sales_trainer_path_recommendation,
)


def test_dashboard_sales_trainer_recommendation_uses_goal_context_next_action() -> None:
    recommendation = build_sales_trainer_path_recommendation(
        [
            {
                "path_key": "new_seller",
                "title": "新人销售闯关",
                "goal_context": {
                    "goal_title": "掌握首次客户沟通",
                    "score_basis": "sales_trainer_path_projection_v1",
                    "next_recommendation": {
                        "title": "下一关：价值表达",
                        "reason": "本关还没有训练证据。",
                        "action_label": "开始做题",
                        "target_path": "/sales-trainer/quiz/unit-2",
                        "unit_id": "unit-2",
                        "level_title": "价值表达",
                    },
                },
            },
        ]
    )

    assert recommendation is not None
    assert recommendation["recommendation_kind"] == "sales_trainer_path"
    assert recommendation["scenario_type"] == "sales_trainer"
    assert recommendation["score_basis"] == "sales_trainer_path_projection_v1"
    assert recommendation["title"] == "下一关：价值表达"
    assert recommendation["target_path"] == "/sales-trainer/quiz/unit-2"

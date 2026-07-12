from __future__ import annotations

from sqlalchemy import select

from common.error_handling.result import Result
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAiCoachTurn,
)
from sales_trainer.services.ai_coach_session_service import AiCoachSessionService


class FakeScoring:
    async def score_turn(self, **_):
        return Result.ok(
            {
                "score": 60,
                "max_score": 100,
                "feedback": "请补充客户价值。",
                "missed_points": ["客户价值"],
                "next_question": "它为客户带来什么价值？",
                "passed": False,
                "raw_model_output": {},
            }
        )


async def test_ai_coach_turn_is_scored_and_advances_without_duplicate(
    test_db, test_user
):
    session = SalesTrainerAiCoachSession(
        user_id=str(test_user.user_id),
        module_key="module-1",
        path_key="newcomer_training_path_orchestration",
        article_snapshot={},
        path_config_snapshot={},
        config_snapshot={"max_turns": 3},
        coach_state={"current_question": "产品解决什么问题？", "turn_number": 1},
        status="in_progress",
    )
    test_db.add(session)
    await test_db.flush()
    test_db.add(
        SalesTrainerAiCoachTurn(
            session_id=str(session.session_id),
            turn_number=1,
            question="产品解决什么问题？",
            user_answer="",
            max_score=100,
            missed_points=[],
        )
    )
    await test_db.commit()
    service = AiCoachSessionService(test_db, scoring=FakeScoring())

    first = await service.submit_activity_turn(
        session_id=str(session.session_id), actor=test_user, answer="提升效率", client_token="turn-token"
    )
    repeated = await service.submit_activity_turn(
        session_id=str(session.session_id), actor=test_user, answer="不同的重复请求", client_token="turn-token"
    )

    assert first["feedback"] == "请补充客户价值。"
    assert first["next_question"] == "它为客户带来什么价值？"
    assert repeated == first
    turns = list((
        await test_db.execute(
            select(SalesTrainerAiCoachTurn).where(
                SalesTrainerAiCoachTurn.session_id == str(session.session_id)
            )
        )
    ).scalars())
    assert [str(item.question) for item in turns] == [
        "产品解决什么问题？",
        "它为客户带来什么价值？",
    ]

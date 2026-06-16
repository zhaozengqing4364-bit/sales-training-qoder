from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.ai_coach_chat_models import (
    SalesTrainerAiCoachChatMessage,
    SalesTrainerAiCoachUiEvent,
)
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerPathModuleConfig,
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-ai-progress-api-{uuid.uuid4().hex[:8]}",
        name="Business Etiquette AI Progress API",
        email=f"business-etiquette-ai-progress-api-{uuid.uuid4().hex[:8]}@example.com",
        role="user",
    )


def _module() -> NewcomerPathModuleConfig:
    return NewcomerPathModuleConfig(
        module_key="business_skills",
        module_type="article_exam",
        enabled=True,
        order_index=1,
        title="商务礼仪",
        learning_units=[
            BusinessEtiquetteTrainingUnitConfig(
                unit_key="trust_foundation",
                title="职业信任底座",
                order_index=1,
                enabled=True,
                source_chapter_orders=[1],
                capability_keys=["respect_boundaries"],
                require_ai_coach=True,
            )
        ],
    )


async def _seed_session_with_score(
    test_db: AsyncSession,
    *,
    learner: User,
) -> SalesTrainerAiCoachSession:
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        module_key="business_skills",
        path_key="newcomer_training_path_v1",
        path_config_snapshot=_module().model_dump(mode="json"),
        article_snapshot={},
        config_snapshot={
            "enabled": True,
            "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        },
        coach_state={},
        status="in_progress",
    )
    test_db.add(session)
    await test_db.flush()
    message = SalesTrainerAiCoachChatMessage(
        session_id=session.session_id,
        role="assistant",
        content="开始训练。",
        order_index=1,
    )
    test_db.add(message)
    await test_db.flush()
    event_id = str(uuid.uuid4())
    test_db.add(
        SalesTrainerAiCoachUiEvent(
            event_id=event_id,
            session_id=session.session_id,
            message_id=message.message_id,
            event_type="quiz_card",
            status="scored",
            payload_json={
                "public_interaction": {
                    "schema_version": "ai_coach_interaction_public_v1",
                    "interaction_id": event_id,
                    "session_id": session.session_id,
                    "turn_number": 1,
                    "training_card_type": "scenario_judgment",
                    "interaction_type": "single_choice",
                    "stem": "商务拜访前应该如何体现尊重？",
                    "options": [
                        {"option_id": "A", "text": "提前确认安排"},
                        {"option_id": "B", "text": "临场再说"},
                    ],
                    "answer_constraints": {"min_selected": 1, "max_selected": 1},
                    "capability_keys": ["respect_boundaries"],
                    "source_chapter_orders": [1],
                }
            },
            answer_payload={"variant": "choice", "option_ids": ["A"]},
            score_result={
                "score": 70,
                "max_score": 100,
                "mastery_threshold": 80,
                "mastered": False,
                "feedback": "已批改。",
                "missed_points": [],
                "next_turn_available": True,
                "finished": False,
            },
            order_index=1,
        )
    )
    await test_db.commit()
    return session


@pytest.mark.asyncio
async def test_should_get_business_etiquette_ai_coach_progress_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user()
    test_db.add(learner)
    await test_db.commit()
    session = await _seed_session_with_score(test_db, learner=learner)

    response = await async_client.get(
        "/api/v1/newcomer-training/business-etiquette/ai-coach/progress",
        params={"session_id": session.session_id},
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["session_id"] == session.session_id
    assert data["learning_unit_key"] == "trust_foundation"
    assert data["status"] == "mastered"
    assert data["passed"] is True
    assert data["capability_scores"][0]["mastery_level_key"] == "basic_mastery"

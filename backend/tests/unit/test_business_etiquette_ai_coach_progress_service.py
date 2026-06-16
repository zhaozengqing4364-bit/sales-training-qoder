from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
from sales_trainer.services.business_etiquette_ai_coach_progress_service import (
    BusinessEtiquetteAiCoachProgressService,
)


def _user(role: str = "user") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-ai-progress-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette AI Progress {role}",
        email=f"business-etiquette-ai-progress-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _module(max_attempts: int = 3) -> NewcomerPathModuleConfig:
    return NewcomerPathModuleConfig(
        module_key="business_skills",
        module_type="article_exam",
        enabled=True,
        order_index=1,
        title="商务礼仪",
        guidance_templates={},
        learning_units=[
            BusinessEtiquetteTrainingUnitConfig(
                unit_key="trust_foundation",
                title="职业信任底座",
                description="尊重分寸、第一印象。",
                order_index=1,
                enabled=True,
                source_chapter_orders=[1],
                capability_keys=["respect_boundaries"],
                unlock_after_unit_keys=[],
                require_reading=True,
                require_quiz=True,
                require_ai_coach=True,
                ai_coach_required_capability_keys=[],
                ai_coach_pass_mastery_level_key="basic_mastery",
                ai_coach_ready_mastery_level_key="field_ready",
                ai_coach_max_remediation_attempts=max_attempts,
                ai_coach_manual_review_after_max_attempts=True,
                ai_coach_block_next_until_passed=True,
                ai_coach_remediation_chapter_orders=[],
            )
        ],
    )


async def _seed_session(
    test_db: AsyncSession,
    *,
    learner: User,
    module: NewcomerPathModuleConfig | None = None,
) -> SalesTrainerAiCoachSession:
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        module_key="business_skills",
        path_key="newcomer_training_path_v1",
        path_config_snapshot=(module or _module()).model_dump(mode="json"),
        article_snapshot={},
        config_snapshot={
            "enabled": True,
            "prompt_template_id": "11111111-1111-1111-1111-111111111111",
            "allowed_interaction_types": ["single_choice", "short_answer"],
            "allowed_training_card_types": ["scenario_judgment", "role_response"],
            "scoring_prompt_template_id": "22222222-2222-2222-2222-222222222222",
        },
        coach_state={},
        status="in_progress",
    )
    test_db.add(session)
    await test_db.flush()
    return session


async def _add_scored_event(
    test_db: AsyncSession,
    *,
    session: SalesTrainerAiCoachSession,
    score: float,
    index: int,
    mastered: bool | None = None,
) -> None:
    message = SalesTrainerAiCoachChatMessage(
        session_id=session.session_id,
        role="assistant",
        content=f"第 {index} 张训练卡。",
        order_index=index,
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
                    "turn_number": index,
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
                },
                "explanation": "提前确认体现尊重与分寸。",
            },
            answer_payload={"variant": "choice", "option_ids": ["A"]},
            score_result={
                "score": score,
                "max_score": 100,
                "mastery_threshold": 80,
                "mastered": mastered,
                "feedback": "已批改。",
                "missed_points": [],
                "next_turn_available": True,
                "finished": False,
            },
            order_index=1,
        )
    )
    await test_db.flush()


@pytest.mark.asyncio
async def test_should_mark_unit_mastered_when_required_capability_reaches_pass_level(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    test_db.add(learner)
    await test_db.commit()
    session = await _seed_session(test_db, learner=learner)
    await _add_scored_event(test_db, session=session, score=70, index=1, mastered=False)

    progress = await BusinessEtiquetteAiCoachProgressService(test_db).get_progress(
        session_id=str(session.session_id),
        user_id=str(learner.user_id),
    )

    assert progress.status == "mastered"
    assert progress.passed is True
    assert progress.ready_for_field is False
    assert progress.capability_scores[0].mastery_level_key == "basic_mastery"
    assert progress.weak_capability_keys == []


@pytest.mark.asyncio
async def test_should_mark_unit_ready_when_required_capability_reaches_ready_level(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    test_db.add(learner)
    await test_db.commit()
    session = await _seed_session(test_db, learner=learner)
    await _add_scored_event(test_db, session=session, score=95, index=1, mastered=True)

    progress = await BusinessEtiquetteAiCoachProgressService(test_db).get_progress(
        session_id=str(session.session_id),
        user_id=str(learner.user_id),
    )

    assert progress.status == "ready"
    assert progress.ready_for_field is True
    assert progress.recommended_training_card_types == [
        "scenario_judgment",
        "role_response",
    ]


@pytest.mark.asyncio
async def test_should_require_manual_review_after_configured_failed_attempts(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    test_db.add(learner)
    await test_db.commit()
    session = await _seed_session(
        test_db,
        learner=learner,
        module=_module(max_attempts=2),
    )
    await _add_scored_event(test_db, session=session, score=40, index=1, mastered=False)
    await _add_scored_event(test_db, session=session, score=50, index=2, mastered=False)

    progress = await BusinessEtiquetteAiCoachProgressService(test_db).get_progress(
        session_id=str(session.session_id),
        user_id=str(learner.user_id),
    )

    assert progress.status == "manual_review"
    assert progress.manual_review_required is True
    assert progress.block_next is True
    assert progress.remediation_attempt_count == 2
    assert progress.recommended_chapter_orders == [1]
    assert progress.weak_capability_keys == ["respect_boundaries"]


@pytest.mark.asyncio
async def test_should_persist_progress_snapshot_on_session_coach_state(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    test_db.add(learner)
    await test_db.commit()
    session = await _seed_session(test_db, learner=learner)
    await _add_scored_event(test_db, session=session, score=95, index=1, mastered=True)

    progress = await BusinessEtiquetteAiCoachProgressService(
        test_db
    ).update_session_progress_snapshot(session, actor=learner)

    assert progress.status == "ready"
    assert session.mastery_state == "mastered"
    assert session.total_score == 95
    assert session.max_score == 100
    assert session.coach_state["business_etiquette_progress"]["status"] == "ready"

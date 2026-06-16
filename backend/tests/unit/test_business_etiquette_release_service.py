from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerBusinessEtiquetteQuestionDraft,
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerOperationLog,
)
from sales_trainer.schemas import (
    BusinessEtiquetteReleasePublishRequest,
    BusinessEtiquetteRetrainingAssignmentRequest,
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.business_etiquette_release_service import (
    BusinessEtiquetteReleaseService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.question_bank.contracts import (
    SALES_TRAINER_QUESTION_SCOPE,
)


def _user(role: str = "user", *, name: str | None = None) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-release-{role}-{uuid.uuid4().hex[:8]}",
        name=name or f"Business Etiquette Release {role}",
        email=f"business-etiquette-release-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


async def _seed_path(test_db: AsyncSession, *, admin: User) -> None:
    payload = NewcomerPathConfigPayload(
        path_key=NEWCOMER_PATH_LOGICAL_ID,
        title="新人训练路径",
        modules=[
            NewcomerPathModuleConfig(
                module_key="business_skills",
                module_type="article_exam",
                enabled=True,
                order_index=1,
                title="商务礼仪",
                learning_units=[
                    BusinessEtiquetteTrainingUnitConfig(
                        unit_key="trust_foundation",
                        title="职业信任底座",
                        description="尊重分寸与第一印象。",
                        order_index=1,
                        enabled=True,
                        source_chapter_orders=[1],
                        capability_keys=["respect_boundaries"],
                        unlock_after_unit_keys=[],
                        require_reading=True,
                        require_quiz=True,
                        require_ai_coach=True,
                    )
                ],
            )
        ],
    )
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload.model_dump(mode="json"),
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪路径配置",
    )
    await test_db.commit()


async def _seed_training_pack_revisions(
    test_db: AsyncSession,
    *,
    admin: User,
) -> tuple[str, str]:
    snapshot = default_business_etiquette_capability_snapshot()
    active_payload = {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "book_title": "商务礼仪",
        "original_chapter_count": 1,
        "original_chapters": [
            {
                "title": "礼仪底层逻辑",
                "order_index": 1,
                "content_hash": "old-hash",
            }
        ],
        CAPABILITY_SNAPSHOT_KEY: {
            "schema_version": 1,
            "capabilities": [
                {
                    **snapshot["capabilities"][0],
                    "status": "published",
                }
            ],
            "chapter_bindings": [{
                "chapter_order": 1,
                "capability_keys": ["respect_boundaries"],
            }],
        },
    }
    revisions = SalesTrainerAssetRevisionService(test_db)
    active_result = await revisions.create_published_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=active_payload,
        actor=admin,
        change_class="semantic",
        reason="发布商务礼仪训练包 v1",
    )
    target_payload = {
        **active_payload,
        "original_chapters": [
            {
                "title": "礼仪底层逻辑",
                "order_index": 1,
                "content_hash": "new-hash",
            }
        ],
        CAPABILITY_SNAPSHOT_KEY: {
            **active_payload[CAPABILITY_SNAPSHOT_KEY],
            "capabilities": [
                {
                    **active_payload[CAPABILITY_SNAPSHOT_KEY]["capabilities"][0],
                    "default_threshold": 75,
                }
            ],
        },
    }
    working_revision = await revisions.save_working_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=target_payload,
        actor=admin,
        change_class="semantic",
        source_revision_id=str(active_result.revision.revision_id),
        reason="导入商务礼仪训练包 v2",
    )
    await test_db.commit()
    return str(active_result.revision.revision_id), str(working_revision.revision_id)


async def _seed_question(
    test_db: AsyncSession,
    *,
    admin: User,
) -> QuestionItem:
    category = QuestionCategory(
        name="商务礼仪",
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(category)
    await test_db.flush()
    question = QuestionItem(
        category_id=category.category_id,
        title="尊重分寸题",
        stem="商务拜访前应该如何体现尊重？",
        reference_answer="提前确认安排。",
        difficulty="easy",
        tags=["business_etiquette", "chapter:1", "capability:respect_boundaries"],
        scoring_dimensions=["respect_boundaries"],
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "提前确认"},
                {"value": "B", "label": "临场再说"},
            ],
            "correct_answer": "A",
        },
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(question)
    await test_db.flush()
    return question


async def _seed_training_records(
    test_db: AsyncSession,
    *,
    admin: User,
    learner: User,
    active_revision_id: str,
) -> str:
    question = await _seed_question(test_db, admin=admin)
    converted = SalesTrainerBusinessEtiquetteQuestionDraft(
        batch_id=str(uuid.uuid4()),
        training_pack_key=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        training_pack_revision_id=active_revision_id,
        training_pack_revision_no=1,
        chapter_order=1,
        question_type="single_choice",
        title="尊重分寸题",
        stem="商务拜访前应该如何体现尊重？",
        options=[{"value": "A", "label": "提前确认"}],
        correct_answer="A",
        capability_keys=["respect_boundaries"],
        status="converted",
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        prompt_contract_hash="hash",
        prompt_contract_version="v1",
        prompt_rendered_hash="rendered",
        question_id=str(question.question_id),
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    pending = SalesTrainerBusinessEtiquetteQuestionDraft(
        batch_id=str(uuid.uuid4()),
        training_pack_key=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        training_pack_revision_id=active_revision_id,
        training_pack_revision_no=1,
        chapter_order=1,
        question_type="short_answer",
        title="复盘表达题",
        stem="礼仪失误后如何补救？",
        reference_answer="先致歉，再补救。",
        capability_keys=["respect_boundaries"],
        status="pending_review",
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        prompt_contract_hash="hash",
        prompt_contract_version="v1",
        prompt_rendered_hash="rendered",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([converted, pending])
    attempt = SalesTrainerBusinessEtiquetteQuizAttempt(
        training_pack_key=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        learning_unit_key="trust_foundation",
        learning_unit_title="职业信任底座",
        user_id=str(learner.user_id),
        training_pack_revision_id=active_revision_id,
        training_pack_revision_no=1,
        capability_snapshot={},
        question_snapshots=[],
        answers_snapshot=[],
        capability_scores=[],
        weak_capability_keys=["respect_boundaries"],
        recommended_chapter_orders=[1],
        passed=False,
        status="scored",
    )
    session = SalesTrainerAiCoachSession(
        user_id=str(learner.user_id),
        module_key="business_skills",
        path_key=NEWCOMER_PATH_LOGICAL_ID,
        path_revision_no=1,
        article_snapshot={},
        path_config_snapshot={},
        config_snapshot={},
        coach_state={},
        status="in_progress",
    )
    test_db.add_all([attempt, session])
    await test_db.commit()
    return str(attempt.attempt_id)


class _FakeChatService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def create_session_shell(
        self,
        *,
        user_id: str,
        module_key: str,
        resume_strategy: str | None,
        actor: User | None,
    ) -> object:
        assert module_key == "business_skills"
        assert resume_strategy == "new"
        assert actor is not None
        self.calls.append((user_id, str(actor.user_id)))
        return SimpleNamespace(
            session_id=f"session-{user_id}",
            path_revision_id="path-revision-2",
            path_revision_no=2,
        )


@pytest.mark.asyncio
async def test_should_preview_release_impact_across_assets_and_active_learners(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", name="Learner A")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_path(test_db, admin=admin)
    active_revision_id, target_revision_id = await _seed_training_pack_revisions(
        test_db,
        admin=admin,
    )
    await _seed_training_records(
        test_db,
        admin=admin,
        learner=learner,
        active_revision_id=active_revision_id,
    )

    impact = await BusinessEtiquetteReleaseService(test_db).preview_release_impact()

    assert impact.active_revision_id == active_revision_id
    assert impact.target_revision_id == target_revision_id
    assert impact.summary.changed_chapter_count == 1
    assert impact.summary.impacted_learning_unit_count == 1
    assert impact.summary.impacted_question_count == 1
    assert impact.summary.impacted_question_draft_count == 1
    assert impact.summary.impacted_capability_count == 1
    assert impact.summary.active_learner_count == 1
    assert impact.chapter_changes[0].change_type == "changed"
    assert impact.impacted_learning_units[0].unit_key == "trust_foundation"
    assert impact.impacted_ai_coach_configs[0].unit_key == "trust_foundation"
    assert impact.active_learners[0].user_id == str(learner.user_id)
    assert "assign_retraining" in impact.strategy_options


@pytest.mark.asyncio
async def test_should_publish_future_only_without_overwriting_old_attempt(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_path(test_db, admin=admin)
    active_revision_id, _ = await _seed_training_pack_revisions(test_db, admin=admin)
    attempt_id = await _seed_training_records(
        test_db,
        admin=admin,
        learner=learner,
        active_revision_id=active_revision_id,
    )

    response = await BusinessEtiquetteReleaseService(test_db).publish_release(
        BusinessEtiquetteReleasePublishRequest(
            strategy="future_learners_only",
            reason="发布月度新版",
        ),
        actor=admin,
        trace_id="trace-release",
    )

    assert response.previous_revision_id == active_revision_id
    assert response.active_revision_no == 2
    assert response.created_session_ids == []
    old_attempt = await test_db.get(SalesTrainerBusinessEtiquetteQuizAttempt, attempt_id)
    assert old_attempt is not None
    assert old_attempt.training_pack_revision_id == active_revision_id

    log_result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action
            == "business_etiquette_training_pack.released"
        )
    )
    log = log_result.scalar_one()
    assert log.request_id == "trace-release"
    assert log.metadata_json["strategy"] == "future_learners_only"


@pytest.mark.asyncio
async def test_should_assign_retraining_by_creating_new_sessions(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    fake_chat = _FakeChatService()

    response = await BusinessEtiquetteReleaseService(
        test_db,
        chat_service=fake_chat,  # type: ignore[arg-type]
    ).assign_retraining(
        BusinessEtiquetteRetrainingAssignmentRequest(
            user_ids=[str(learner.user_id)],
            reason="指定重练新版",
        ),
        actor=admin,
        trace_id="trace-retraining",
    )

    assert fake_chat.calls == [(str(learner.user_id), str(admin.user_id))]
    assert response.created_session_ids == [f"session-{learner.user_id}"]
    log_result = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action
            == "business_etiquette_training_pack.retraining_assigned"
        )
    )
    log = log_result.scalar_one()
    assert log.request_id == "trace-retraining"
    assert log.metadata_json["assigned_user_ids"] == [str(learner.user_id)]

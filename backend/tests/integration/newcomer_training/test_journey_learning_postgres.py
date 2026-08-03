from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common.db.models import User
from foundation_standard_pack import (
    COMPETENCIES,
    install_or_verify_standard_pack,
)
from learning.models import (
    LearningQuestion,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
)
from learning.ports import ActivityOutcomePayload
from learning.quiz_runtime import (
    QuizAnswerInput,
    QuizAttemptContext,
    QuizRuntimeService,
)
from newcomer_training.activity import ActivityAttemptService
from newcomer_training.application import CommandActor, PathEnrollmentService
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)

POSTGRES_URL = os.getenv("NEWCOMER_TRAINING_TEST_DATABASE_URL") or os.getenv(
    "TASK_RUNTIME_TEST_DATABASE_URL"
)
BACKEND_ROOT = Path(__file__).resolve().parents[3]
PREVIOUS_REVISION = "20260716_2300_002"
HEAD_REVISION = "b9fc04c1ad65"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not POSTGRES_URL,
        reason=(
            "NEWCOMER_TRAINING_TEST_DATABASE_URL or "
            "TASK_RUNTIME_TEST_DATABASE_URL is required"
        ),
    ),
]


class PostgresHarness:
    def __init__(
        self,
        *,
        schema: str,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.schema = schema
        self.engine = engine
        self.session_factory = session_factory

    async def run_alembic(self, *arguments: str) -> str:
        assert POSTGRES_URL is not None
        migration_url = make_url(POSTGRES_URL).update_query_dict(
            {"options": f"-csearch_path={self.schema}"}
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            *arguments,
            cwd=BACKEND_ROOT,
            env={
                **os.environ,
                "DATABASE_URL": migration_url.render_as_string(
                    hide_password=False
                ),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_bytes, _ = await process.communicate()
        output = output_bytes.decode("utf-8", errors="replace")
        assert process.returncode == 0, output
        return output

class NoopOutcomeWriter:
    async def record(self, payload: ActivityOutcomePayload) -> str:
        return f"outcome:{payload.attempt_id}"


@pytest_asyncio.fixture
async def postgres_harness() -> AsyncIterator[PostgresHarness]:
    assert POSTGRES_URL is not None
    schema = f"slice2_journey_{uuid.uuid4().hex[:12]}"
    admin_engine = create_async_engine(POSTGRES_URL, pool_pre_ping=True)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        POSTGRES_URL,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    harness = PostgresHarness(
        schema=schema,
        engine=engine,
        session_factory=factory,
    )
    try:
        await harness.run_alembic("upgrade", "head")
        yield harness
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            )
        await admin_engine.dispose()


def _path_snapshot(*, label: str, quiz_revision_id: str) -> dict[str, object]:
    return {
        "contract_version": "newcomer_training_path_v2",
        "title": "新人销售基础训练",
        "revision_label": label,
        "stages": [
            {
                "stage_id": "stage-1",
                "sequence": 1,
                "title": "产品基础",
                "objective": "掌握产品基础",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "quiz-1",
                        "type": "quiz",
                        "title": "产品知识测验",
                        "objective": "验证产品知识",
                        "why_it_matters": "确保表达准确",
                        "steps": ["完成答题"],
                        "success_criteria": ["达到通过标准"],
                        "estimated_minutes": 10,
                        "required": True,
                        "prerequisite_activity_ids": [],
                        "competency_keys": ["product_knowledge"],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 1,
                        },
                        "config": {"quiz_revision_id": quiz_revision_id},
                    }
                ],
            }
        ],
    }


async def _seed_foundation(factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    question_content = {
        "question_type": "single_choice",
        "stem": "客户询问产品价值时，首先应该做什么？",
        "options": [
            {"option_id": "a", "text": "澄清客户目标", "is_correct": True},
            {"option_id": "b", "text": "直接报价", "is_correct": False},
        ],
        "reference_answer": None,
        "rubric": None,
        "explanation": "先理解客户目标。",
        "difficulty": "medium",
        "competency_keys": ["product_knowledge"],
        "source_anchor_ids": ["anchor-1"],
    }
    quiz_snapshot = {
        "revision_label": "v1",
        "title": "产品知识测验",
        "questions": [
            {"question_revision_id": "question-revision-1", "points": 1.0}
        ],
        "pass_threshold": 80,
        "max_attempts": 3,
        "retry_interval_seconds": 1,
        "feedback_policy": "after_submit",
        "time_limit_minutes": 10,
        "shuffle_questions": False,
        "shuffle_options": False,
        "short_answer_scoring": None,
    }
    users = [
        User(
            user_id=learner_id,
            wechat_user_id=f"wechat-{learner_id}",
            name=f"学员 {index}",
            email=f"learner-{index}@example.invalid",
            role="user",
            is_active=True,
        )
        for index, learner_id in enumerate(("learner-1", "learner-2"), start=1)
    ]
    question = LearningQuestion(
        question_id="question-1",
        organization_id="org-1",
        stable_key="question-1",
        status="published",
        published_revision_id="question-revision-1",
        version=2,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    question_revision = LearningQuestionRevision(
        revision_id="question-revision-1",
        question_id=question.question_id,
        organization_id="org-1",
        revision_no=1,
        status="published",
        version=2,
        question_type="single_choice",
        content_json=question_content,
        source_anchor_ids_json=["anchor-1"],
        competency_keys_json=["product_knowledge"],
        deterministic_fingerprint="a" * 64,
        content_hash="b" * 64,
        reviewed_by="admin-1",
        review_reason="人工核对",
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    quiz = LearningQuiz(
        quiz_id="quiz-1",
        organization_id="org-1",
        stable_key="quiz-1",
        title="产品知识测验",
        status="active",
        published_revision_id="quiz-revision-1",
        version=2,
        creation_idempotency_key_hash="c" * 64,
        creation_fingerprint="d" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    quiz_revision = LearningQuizRevision(
        revision_id="quiz-revision-1",
        quiz_id=quiz.quiz_id,
        organization_id="org-1",
        revision_no=1,
        revision_label="v1",
        status="published",
        snapshot_json=quiz_snapshot,
        question_revision_ids_json=[question_revision.revision_id],
        content_hash="e" * 64,
        version=2,
        save_idempotency_key_hash="f" * 64,
        save_fingerprint="1" * 64,
        publish_idempotency_key_hash="2" * 64,
        publish_fingerprint="3" * 64,
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    path = NewcomerPath(
        path_id="path-1",
        organization_id="org-1",
        stable_key="foundation",
        title="新人销售基础训练",
        status="active",
        published_revision_id="path-revision-1",
        version=3,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    revisions = [
        NewcomerPathRevision(
            revision_id=f"path-revision-{index}",
            path_id=path.path_id,
            organization_id="org-1",
            revision_no=index,
            revision_label=f"v{index}",
            status="published",
            snapshot_json=_path_snapshot(
                label=f"v{index}", quiz_revision_id=quiz_revision.revision_id
            ),
            content_hash=str(index) * 64,
            version=2,
            save_idempotency_key_hash=str(index + 5) * 64,
            save_fingerprint=str(index + 7) * 64,
            publish_idempotency_key_hash=str(index + 1) * 64,
            publish_fingerprint=str(index + 2) * 64,
            created_by="admin-1",
            published_by="admin-1",
            created_at=now,
            published_at=now,
        )
        for index in (1, 2)
    ]
    cohort = NewcomerCohort(
        cohort_id="cohort-1",
        organization_id="org-1",
        stable_key="cohort-1",
        name="新人班",
        path_revision_id=revisions[0].revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="6" * 64,
        creation_fingerprint="7" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    enrollments = [
        NewcomerEnrollment(
            enrollment_id=f"enrollment-{index}",
            organization_id="org-1",
            learner_id=f"learner-{index}",
            cohort_id=cohort.cohort_id,
            path_revision_id=revisions[0].revision_id,
            status="active",
            version=1,
            creation_idempotency_key_hash=("8" if index == 1 else "9") * 64,
            creation_fingerprint=("a" if index == 1 else "b") * 64,
            assigned_by="admin-1",
            assigned_at=now,
            updated_at=now,
        )
        for index in (1, 2)
    ]
    async with factory() as session:
        session.add_all([*users, question, quiz, path])
        await session.flush()
        session.add_all([question_revision, quiz_revision, *revisions])
        await session.flush()
        session.add(cohort)
        await session.flush()
        session.add_all(enrollments)
        await session.commit()


@pytest.mark.asyncio
async def test_slice2_migration_round_trip(postgres_harness: PostgresHarness) -> None:
    harness = postgres_harness
    async with harness.engine.connect() as connection:
        revision = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        target_count = await connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = current_schema() "
                "AND table_name IN "
                "('newcomer_paths','newcomer_enrollments_v2',"
                "'learning_source_documents','learning_question_candidates',"
                "'learning_quiz_attempts')"
            )
        )
    assert revision == HEAD_REVISION
    assert target_count == 5
    assert "No new upgrade operations detected" in await harness.run_alembic(
        "check"
    )

    await harness.run_alembic("downgrade", PREVIOUS_REVISION)
    async with harness.engine.connect() as connection:
        revision = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        target_count = await connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = current_schema() "
                "AND table_name IN "
                "('newcomer_paths','newcomer_enrollments_v2',"
                "'learning_source_documents','learning_question_candidates',"
                "'learning_quiz_attempts')"
            )
        )
    assert revision == PREVIOUS_REVISION
    assert target_count == 0

    await harness.run_alembic("upgrade", "head")
    async with harness.engine.connect() as connection:
        assert (
            await connection.scalar(text("SELECT version_num FROM alembic_version"))
            == HEAD_REVISION
        )


@pytest.mark.asyncio
async def test_standard_pack_is_repeatable_on_clean_postgres(
    postgres_harness: PostgresHarness,
) -> None:
    factory = postgres_harness.session_factory
    async with factory() as session:
        first = await install_or_verify_standard_pack(
            session,
            organization_id="org-standard-pack",
        )
        await session.commit()
    async with factory() as session:
        second = await install_or_verify_standard_pack(
            session,
            organization_id="org-standard-pack",
        )
        await session.commit()
    async with factory() as session:
        verified = await install_or_verify_standard_pack(
            session,
            organization_id="org-standard-pack",
            verify_only=True,
        )
        await session.rollback()

    expected_keys = tuple(item.key for item in COMPETENCIES)
    assert first.path_revision_id == second.path_revision_id
    assert first.path_revision_id == verified.path_revision_id
    assert first.competency_keys == expected_keys
    assert verified.verified_only is True
    async with factory() as session:
        assert (
            int(await session.scalar(select(func.count(NewcomerPath.path_id))) or 0)
            == 1
        )
        assert (
            int(await session.scalar(select(func.count(LearningQuestion.question_id))) or 0)
            == 7
        )
        assert (
            int(await session.scalar(select(func.count(LearningQuiz.quiz_id))) or 0)
            == 7
        )


@pytest.mark.asyncio
async def test_postgres_attempt_serialization_quiz_snapshot_and_migration_versions(
    postgres_harness: PostgresHarness,
) -> None:
    factory = postgres_harness.session_factory
    await _seed_foundation(factory)
    learner = CommandActor(
        organization_id="org-1",
        actor_id="learner-1",
        capabilities=frozenset({"newcomer.activity.execute"}),
    )

    async def start_attempt(key: str):
        async with factory() as session:
            try:
                result = await ActivityAttemptService(session).start_attempt(
                    actor=learner,
                    activity_id="quiz-1",
                    expected_enrollment_version=1,
                    idempotency_key=key,
                )
                await session.commit()
                return result
            except Exception as exc:
                await session.rollback()
                return exc

    concurrent_starts = await asyncio.gather(
        start_attempt("start-a"), start_attempt("start-b")
    )
    assert sum(not isinstance(item, Exception) for item in concurrent_starts) == 1, (
        concurrent_starts
    )
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(NewcomerActivityAttempt.attempt_id))
            )
            == 1
        )

    context = QuizAttemptContext(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="quiz-1",
        attempt_id="generic-quiz-attempt",
        quiz_revision_id="quiz-revision-1",
    )
    async with factory() as session:
        runtime = QuizRuntimeService(session, outcomes=NoopOutcomeWriter())
        started = await runtime.start_or_resume(
            context=context, idempotency_key="start-quiz-runtime"
        )
        await session.commit()
    original_stem = started.questions[0]["stem"]
    async with factory() as session:
        question = await session.get(
            LearningQuestionRevision, "question-revision-1"
        )
        assert question is not None
        question.content_json = {
            **question.content_json,
            "stem": "被错误修改的后台题干",
        }
        await session.commit()
    async with factory() as session:
        resumed = await QuizRuntimeService(
            session, outcomes=NoopOutcomeWriter()
        ).start_or_resume(
            context=context, idempotency_key="start-quiz-runtime"
        )
        assert resumed.questions[0]["stem"] == original_stem
        saved = await QuizRuntimeService(
            session, outcomes=NoopOutcomeWriter()
        ).save_answers(
            organization_id="org-1",
            learner_id="learner-1",
            detail_id=resumed.detail_id,
            answers=(
                QuizAnswerInput(
                    question_revision_id="question-revision-1",
                    selected_option_ids=("a",),
                ),
            ),
            expected_version=resumed.version,
            idempotency_key="save-answer",
        )
        await session.commit()

    async def submit_quiz():
        async with factory() as session:
            try:
                result = await QuizRuntimeService(
                    session, outcomes=NoopOutcomeWriter()
                ).submit(
                    organization_id="org-1",
                    learner_id="learner-1",
                    detail_id=saved.detail_id,
                    expected_version=saved.version,
                    idempotency_key="submit-answer",
                )
                await session.commit()
                return result
            except Exception as exc:
                await session.rollback()
                return exc

    duplicate_submits = await asyncio.gather(submit_quiz(), submit_quiz())
    assert all(not isinstance(item, Exception) for item in duplicate_submits)
    assert duplicate_submits[0] == duplicate_submits[1]

    admin = CommandActor(
        organization_id="org-1",
        actor_id="admin-1",
        capabilities=frozenset({"newcomer.enrollment.migrate"}),
        trace_id="trace-migration",
    )
    async with factory() as session:
        preview = await PathEnrollmentService(session).preview_revision_migration(
            actor=admin,
            enrollment_ids=["enrollment-1", "enrollment-2"],
            target_revision_id="path-revision-2",
            reason="切换到已审核的新版本",
        )
        await session.commit()
    async with factory() as session:
        changed = await session.get(NewcomerEnrollment, "enrollment-2")
        assert changed is not None
        changed.version += 1
        await session.commit()
    async with factory() as session:
        service = PathEnrollmentService(session)
        result = await service.confirm_revision_migration(
            actor=admin,
            preview_token=preview.preview_token,
            impact_hash=preview.impact_hash,
            idempotency_key="confirm-migration",
            reason="切换到已审核的新版本",
        )
        await session.commit()
    assert result.migrated_count == 1
    assert result.failure_count == 1
    assert {item.status for item in result.items} == {"migrated", "failed"}
    async with factory() as session:
        replay = await PathEnrollmentService(session).confirm_revision_migration(
            actor=admin,
            preview_token=preview.preview_token,
            impact_hash=preview.impact_hash,
            idempotency_key="confirm-migration",
            reason="切换到已审核的新版本",
        )
        assert replay == result
        migrated = await session.get(NewcomerEnrollment, "enrollment-1")
        stale = await session.get(NewcomerEnrollment, "enrollment-2")
        assert migrated is not None and stale is not None
        assert migrated.path_revision_id == "path-revision-2"
        assert migrated.version == 2
        assert stale.path_revision_id == "path-revision-1"
        assert stale.version == 2

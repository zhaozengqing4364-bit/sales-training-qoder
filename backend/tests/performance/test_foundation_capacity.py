from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import sys
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import event, func, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tests.unit.audio_assessment.test_durable_pipeline import (  # noqa: PLC2701
    _AI,
    _ExecutionContext,
    _Media,
    _Outcomes,
    _prompt_compiler,
    _resources,
    _Storage,
)

from audio_assessment.contracts import (
    AudioPipelineTaskInput,
    ConfirmUploadPartInput,
    CreateUploadSessionInput,
    FinalizeUploadInput,
)
from audio_assessment.models import (
    AudioActivityRun,
    AudioSubmission,
    AudioUploadPart,
)
from audio_assessment.pipeline import AudioPipelineTaskHandler
from audio_assessment.runtime import AudioRuntimeService
from audio_assessment.task_definitions import register_audio_task_definition
from common.db.models import User
from common.teams import TeamDataScope
from competency_evidence.contracts import CompetencyEvidenceProjection
from competency_evidence.identifiers import STANDARD_COMPETENCY_KEYS
from foundation_admin_permissions import foundation_admin_actors
from newcomer_training.admin_queries import FoundationLearnerAdminQueryService
from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.journey import JourneyQueryService
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)
from readiness.application import ReadinessService
from readiness.contracts import ReadinessActivityInput, ReadinessProjectionInput
from task_runtime.contracts import (
    ActorContext,
    TaskCommand,
    TaskPolicy,
    TaskProjection,
    TaskReference,
)
from task_runtime.models import DurableTask
from task_runtime.registry import TaskDefinition, TaskRegistry
from task_runtime.repository import SQLAlchemyTaskRuntime

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = (
    BACKEND_ROOT.parent / ".sisyphus/evidence/foundation-capacity-baseline.json"
)
ORGANIZATION_ID = "org-1"
LEARNER_COUNT = 1_000
ONLINE_CONCURRENCY = 100
UPLOAD_CONCURRENCY = 20
AI_JOB_CONCURRENCY = 20
ACTIVITY_COUNT = 100
ATTEMPT_COUNT = 10_000


def _postgres_url() -> str | None:
    candidate = (
        os.getenv("FOUNDATION_CAPACITY_TEST_DATABASE_URL")
        or os.getenv("FOUNDATION_MIGRATION_TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
    )
    if not candidate or not candidate.startswith(
        ("postgresql://", "postgresql+asyncpg://")
    ):
        return None
    parsed = make_url(candidate)
    if parsed.host not in {None, "localhost", "127.0.0.1", "::1"}:
        return None
    return candidate


POSTGRES_URL = _postgres_url()

pytestmark = [
    pytest.mark.performance,
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None,
        reason="A local isolated-schema PostgreSQL URL is required",
    ),
]


class CapacityAIInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    purpose: str


class CapacityAIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_ref: str


class CapacityHarness:
    def __init__(
        self,
        *,
        schema: str,
        engine: AsyncEngine,
        sessions: async_sessionmaker[AsyncSession],
    ) -> None:
        self.schema = schema
        self.engine = engine
        self.sessions = sessions


class _CapturingTaskRuntime:
    def __init__(
        self,
        delegate: SQLAlchemyTaskRuntime,
        commands: list[tuple[str, TaskCommand]],
    ) -> None:
        self._delegate = delegate
        self._commands = commands

    async def enqueue(self, command: TaskCommand) -> TaskReference:
        reference = await self._delegate.enqueue(command)
        self._commands.append((reference.task_id, command))
        return reference

    async def get(self, task_id: str, viewer: ActorContext) -> TaskProjection:
        return await self._delegate.get(task_id, viewer)

    async def request_cancel(
        self,
        task_id: str,
        actor: ActorContext,
        *,
        idempotency_key: str | None = None,
    ) -> TaskProjection:
        return await self._delegate.request_cancel(
            task_id,
            actor,
            idempotency_key=idempotency_key,
        )


async def _run_alembic(schema: str) -> None:
    assert POSTGRES_URL is not None
    migration_url = make_url(POSTGRES_URL).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "upgrade",
        "head",
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": migration_url.render_as_string(hide_password=False),
        },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    assert process.returncode == 0, output.decode("utf-8", errors="replace")


@pytest_asyncio.fixture
async def capacity_harness() -> AsyncIterator[CapacityHarness]:
    assert POSTGRES_URL is not None
    schema = f"foundation_capacity_{uuid.uuid4().hex[:12]}"
    admin_engine = create_async_engine(POSTGRES_URL, pool_pre_ping=True)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    await _run_alembic(schema)
    engine = create_async_engine(
        POSTGRES_URL,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=0,
        connect_args={"server_settings": {"search_path": schema}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield CapacityHarness(schema=schema, engine=engine, sessions=sessions)
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _activity_snapshot(index: int) -> dict[str, Any]:
    activity_id = f"capacity-activity-{index:03d}"
    common: dict[str, Any] = {
        "activity_id": activity_id,
        "title": f"容量训练活动 {index + 1:03d}",
        "objective": "验证大路径下的服务端投影与状态稳定性。",
        "why_it_matters": "首发路径必须在冻结容量基线下保持明确下一步。",
        "steps": ["查看任务", "完成训练"],
        "success_criteria": ["结果持久化且可恢复"],
        "competency_keys": ["communication_structure"],
        "estimated_minutes": 5,
        "required": True,
        "prerequisite_activity_ids": [],
        "retry_policy": {"max_attempts": 1, "retry_interval_seconds": 0},
    }
    if index == 0:
        return {
            **common,
            "type": "audio_assessment",
            "ai_dependency": "required",
            "config": {
                "audio_material_revision_id": "audio-material-v1",
                "scoring_scheme_revision_id": "audio-scoring-v1",
                "allowed_recording_modes": ["browser", "file"],
                "max_duration_seconds": 60,
                "max_size_bytes": 1024 * 1024,
                "language": "zh-CN",
                "baseline_only": False,
            },
        }
    return {
        **common,
        "type": "lesson",
        "ai_dependency": "none",
        "config": {
            "learning_unit_revision_id": f"capacity-unit-{index:03d}",
            "required_checkpoint_ids": [f"capacity-checkpoint-{index:03d}"],
        },
    }


def _path_draft() -> PathRevisionDraft:
    return PathRevisionDraft.model_validate(
        {
            "title": "新人基础训练容量基线",
            "revision_label": "capacity-v1",
            "stages": [
                {
                    "stage_id": "capacity-stage",
                    "sequence": 1,
                    "title": "容量验证阶段",
                    "objective": "验证一条路径包含一百个活动时仍可稳定投影。",
                    "entry_conditions": [],
                    "completion_rule": "all_required",
                    "visibility": "learner",
                    "activities": [
                        _activity_snapshot(index) for index in range(ACTIVITY_COUNT)
                    ],
                }
            ],
        }
    )


async def _seed_capacity_dataset(harness: CapacityHarness) -> dict[str, str]:
    now = datetime.now(UTC)
    path_id = "capacity-path"
    revision_id = "capacity-path-r1"
    cohort_id = "capacity-cohort"
    draft = _path_draft()
    admin = User(
        user_id="capacity-admin",
        wechat_user_id="capacity-admin",
        name="容量验证管理员",
        email="capacity-admin@example.invalid",
        role="admin",
        is_active=True,
    )
    path = NewcomerPath(
        path_id=path_id,
        organization_id=ORGANIZATION_ID,
        stable_key="capacity",
        title=draft.title,
        status="active",
        published_revision_id=revision_id,
        version=1,
        creation_idempotency_key_hash=_hash("capacity-path-create"),
        creation_fingerprint=_hash(draft.model_dump(mode="json")),
        created_by=admin.user_id,
        created_at=now,
        updated_at=now,
    )
    revision = NewcomerPathRevision(
        revision_id=revision_id,
        path_id=path_id,
        organization_id=ORGANIZATION_ID,
        revision_no=1,
        revision_label=draft.revision_label,
        status="published",
        snapshot_json=draft.model_dump(mode="json"),
        content_hash=_hash(draft.model_dump(mode="json")),
        version=2,
        save_idempotency_key_hash=_hash("capacity-revision-save"),
        save_fingerprint=_hash("capacity-revision-save-fingerprint"),
        publish_idempotency_key_hash=_hash("capacity-revision-publish"),
        publish_fingerprint=_hash("capacity-revision-publish-fingerprint"),
        created_by=admin.user_id,
        published_by=admin.user_id,
        created_at=now,
        published_at=now,
    )
    cohort = NewcomerCohort(
        cohort_id=cohort_id,
        organization_id=ORGANIZATION_ID,
        stable_key="capacity-cohort",
        name="容量验证班级",
        path_revision_id=revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash=_hash("capacity-cohort-create"),
        creation_fingerprint=_hash("capacity-cohort-fingerprint"),
        created_by=admin.user_id,
        created_at=now,
        updated_at=now,
    )
    async with harness.sessions() as session:
        session.add(admin)
        await session.flush([admin])
        session.add(path)
        await session.flush([path])
        session.add(revision)
        await session.flush([revision])
        session.add(cohort)
        await session.flush([cohort])
        await _resources(session)
        users = [
            {
                "user_id": f"capacity-learner-{index:04d}",
                "wechat_user_id": f"capacity-wechat-{index:04d}",
                "name": f"容量学员 {index:04d}",
                "email": f"capacity-{index:04d}@example.invalid",
                "credential_status": "active",
                "credential_version": 1,
                "role": "user",
                "created_at": now,
                "is_active": True,
            }
            for index in range(LEARNER_COUNT)
        ]
        await session.execute(insert(User), users)
        enrollments = [
            {
                "enrollment_id": f"capacity-enrollment-{index:04d}",
                "organization_id": ORGANIZATION_ID,
                "learner_id": f"capacity-learner-{index:04d}",
                "cohort_id": cohort_id,
                "path_revision_id": revision_id,
                "status": "active",
                "version": 1,
                "creation_idempotency_key_hash": _hash(f"enroll-{index}"),
                "creation_fingerprint": _hash(f"enroll-fingerprint-{index}"),
                "assigned_by": admin.user_id,
                "assigned_at": now,
                "updated_at": now,
            }
            for index in range(LEARNER_COUNT)
        ]
        await session.execute(insert(NewcomerEnrollment), enrollments)
        attempts: list[dict[str, Any]] = []
        for learner_index in range(LEARNER_COUNT):
            for activity_index in range(10):
                activity = _activity_snapshot(activity_index)
                attempts.append(
                    {
                        "attempt_id": (
                            f"capacity-attempt-{learner_index:04d}-{activity_index:02d}"
                        ),
                        "organization_id": ORGANIZATION_ID,
                        "enrollment_id": f"capacity-enrollment-{learner_index:04d}",
                        "path_revision_id": revision_id,
                        "activity_id": activity["activity_id"],
                        "activity_type": activity["type"],
                        "attempt_no": 1,
                        "status": "started",
                        "version": 1,
                        "activity_snapshot_json": activity,
                        "idempotency_key_hash": _hash(
                            f"attempt-{learner_index}-{activity_index}"
                        ),
                        "command_fingerprint": _hash(
                            f"attempt-fingerprint-{learner_index}-{activity_index}"
                        ),
                        "evidence_status": "pending",
                        "reconcile_status": "pending",
                        "started_at": now,
                    }
                )
        await session.execute(insert(NewcomerActivityAttempt), attempts)
        await session.commit()
    return {
        "path_id": path_id,
        "revision_id": revision_id,
        "cohort_id": cohort_id,
        "admin_id": admin.user_id,
    }


def _percentile(samples: list[float], quantile: float) -> float:
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * quantile + 0.999) - 1))
    return round(ordered[index], 2)


def _metric(samples: list[float], *, failures: int = 0) -> dict[str, Any]:
    return {
        "sample_count": len(samples),
        "failure_count": failures,
        "p50_ms": _percentile(samples, 0.50),
        "p75_ms": _percentile(samples, 0.75),
        "p95_ms": _percentile(samples, 0.95),
        "p99_ms": _percentile(samples, 0.99),
        "max_ms": round(max(samples), 2),
    }


async def _measure_concurrent_journeys(harness: CapacityHarness) -> dict[str, Any]:
    async def read(index: int) -> tuple[float, bool]:
        started = time.perf_counter()
        async with harness.sessions() as session:
            projection = await JourneyQueryService(session).get_my_journey(
                actor=CommandActor(
                    organization_id=ORGANIZATION_ID,
                    actor_id=f"capacity-learner-{index:04d}",
                    capabilities=frozenset({"newcomer.journey.read"}),
                )
            )
        elapsed = (time.perf_counter() - started) * 1_000
        valid = (
            projection.enrollment is not None
            and sum(len(stage.activities) for stage in projection.stages)
            == ACTIVITY_COUNT
            and projection.primary_action is not None
        )
        return elapsed, valid

    results = await asyncio.gather(
        *(read(index) for index in range(ONLINE_CONCURRENCY))
    )
    samples = [elapsed for elapsed, _valid in results]
    failures = sum(1 for _elapsed, valid in results if not valid)
    return _metric(samples, failures=failures)


async def _measure_admin_attempt_page(harness: CapacityHarness) -> dict[str, Any]:
    statements: list[str] = []

    def capture_select(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(harness.engine.sync_engine, "before_cursor_execute", capture_select)
    try:
        samples: list[float] = []
        async with harness.sessions() as session:
            admin = await session.get(User, "capacity-admin")
            assert admin is not None
            service = FoundationLearnerAdminQueryService(
                session,
                actors=foundation_admin_actors(
                    user=admin,
                    organization_id=ORGANIZATION_ID,
                ),
                scope=TeamDataScope.unrestricted_scope(),
            )
            warmup = await service.list_learners(search=None, limit=50, offset=0)
            assert len(warmup["items"]) == 50
            sample_details: list[dict[str, float | int]] = []
            for offset in (0, 50, 500, 950) * 5:
                started = time.perf_counter()
                page = await service.list_learners(
                    search=None,
                    limit=50,
                    offset=offset,
                )
                elapsed_ms = (time.perf_counter() - started) * 1_000
                samples.append(elapsed_ms)
                sample_details.append(
                    {"offset": offset, "elapsed_ms": round(elapsed_ms, 2)}
                )
                assert page["total"] == LEARNER_COUNT
                assert len(page["items"]) == 50
            started = time.perf_counter()
            filtered = await service.list_learners(
                search="容量学员 0999",
                limit=50,
                offset=0,
            )
            filter_ms = (time.perf_counter() - started) * 1_000
            assert filtered["total"] == 1
    finally:
        event.remove(
            harness.engine.sync_engine,
            "before_cursor_execute",
            capture_select,
        )
    normalized = [" ".join(statement.split()).upper() for statement in statements]
    return {
        **_metric(samples),
        "samples": sample_details,
        "filtered_ms": round(filter_ms, 2),
        "select_count": len(statements),
        "server_side_limit_offset": any(
            " LIMIT " in statement and " OFFSET " in statement
            for statement in normalized
        ),
        "attempt_scope_is_page_bounded": any(
            "NEWCOMER_ACTIVITY_ATTEMPTS_V2.ENROLLMENT_ID IN" in statement
            for statement in normalized
        ),
        "server_side_sort": any(" ORDER BY " in statement for statement in normalized),
    }


async def _measure_ai_enqueue(harness: CapacityHarness) -> dict[str, Any]:
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="capacity.foundation_ai",
            schema_version=1,
            input_model=CapacityAIInput,
            result_model=CapacityAIResult,
            policy=TaskPolicy(max_attempts=3, timeout_seconds=30),
        )
    )

    async def enqueue(index: int) -> tuple[float, str]:
        started = time.perf_counter()
        async with harness.sessions() as session:
            task = await SQLAlchemyTaskRuntime(session, registry=registry).enqueue(
                TaskCommand(
                    task_type="capacity.foundation_ai",
                    schema_version=1,
                    organization_id=ORGANIZATION_ID,
                    actor_id=f"capacity-learner-{index:04d}",
                    resource_type="activity_attempt",
                    resource_id=f"capacity-attempt-{index:04d}-01",
                    idempotency_key=f"capacity-ai-{index:04d}",
                    input_payload={
                        "attempt_id": f"capacity-attempt-{index:04d}-01",
                        "purpose": "structured_coach_feedback",
                    },
                    correlation_id=f"capacity-ai-correlation-{index:04d}",
                )
            )
            await session.commit()
        return (time.perf_counter() - started) * 1_000, task.task_id

    results = await asyncio.gather(
        *(enqueue(index) for index in range(AI_JOB_CONCURRENCY))
    )
    async with harness.sessions() as session:
        persisted = int(
            await session.scalar(
                select(func.count(DurableTask.task_id)).where(
                    DurableTask.task_type == "capacity.foundation_ai"
                )
            )
            or 0
        )
    samples = [elapsed for elapsed, _task_id in results]
    unique = len({task_id for _elapsed, task_id in results})
    return {
        **_metric(samples, failures=AI_JOB_CONCURRENCY - persisted),
        "persisted_count": persisted,
        "unique_task_count": unique,
    }


async def _measure_audio_workload(harness: CapacityHarness) -> dict[str, Any]:
    storage = _Storage()
    registry = TaskRegistry()
    register_audio_task_definition(registry)
    task_commands: list[tuple[str, TaskCommand]] = []
    content_by_upload: dict[str, bytes] = {}

    async def upload(index: int) -> tuple[float, str]:
        learner_id = f"capacity-learner-{index:04d}"
        enrollment_id = f"capacity-enrollment-{index:04d}"
        attempt_id = f"capacity-attempt-{index:04d}-00"
        content = f"capacity-audio-{index:04d}".encode()
        sha256 = hashlib.sha256(content).hexdigest()
        declaration = {
            "part_number": 1,
            "size_bytes": len(content),
            "sha256": sha256,
        }
        async with harness.sessions() as session:
            runtime = AudioRuntimeService(
                session,
                task_runtime=cast(
                    Any,
                    _CapturingTaskRuntime(
                        SQLAlchemyTaskRuntime(session, registry=registry),
                        task_commands,
                    ),
                ),
                storage=storage,
            )
            started = await runtime.start(
                organization_id=ORGANIZATION_ID,
                learner_id=learner_id,
                enrollment_id=enrollment_id,
                path_revision_id="capacity-path-r1",
                activity_id="capacity-activity-000",
                activity_type="audio_assessment",
                attempt_id=attempt_id,
                config={
                    "audio_material_revision_id": "audio-material-v1",
                    "scoring_scheme_revision_id": "audio-scoring-v1",
                    "allowed_recording_modes": ["browser", "file"],
                    "max_duration_seconds": 60,
                    "max_size_bytes": 1024 * 1024,
                    "language": "zh-CN",
                    "baseline_only": False,
                },
                competency_keys=("communication_structure",),
                idempotency_key=f"capacity-audio-start-{index}",
            )
            created = await runtime.create_upload_session(
                organization_id=ORGANIZATION_ID,
                learner_id=learner_id,
                attempt_id=attempt_id,
                expected_version=started.version,
                payload=CreateUploadSessionInput(
                    segment_id="primary",
                    recording_mode="browser",
                    original_filename=f"capacity-{index:04d}.webm",
                    content_type="audio/webm",
                    size_bytes=len(content),
                    duration_seconds=3,
                    manifest_sha256=_hash([declaration]),
                    parts=(declaration,),
                ),
                idempotency_key=f"capacity-upload-{index}",
            )
            upload_id = str(created.runner["active_upload"]["upload_session_id"])
            part = await session.scalar(
                select(AudioUploadPart).where(
                    AudioUploadPart.upload_session_id == upload_id
                )
            )
            assert part is not None
            storage.objects[part.object_key] = content
            content_by_upload[upload_id] = content
            confirmed = await runtime.confirm_upload_part(
                organization_id=ORGANIZATION_ID,
                learner_id=learner_id,
                attempt_id=attempt_id,
                expected_version=created.version,
                payload=ConfirmUploadPartInput(
                    upload_session_id=upload_id,
                    part_number=1,
                    size_bytes=len(content),
                    sha256=sha256,
                ),
            )
            finalize_started = time.perf_counter()
            finalized = await runtime.finalize_upload(
                organization_id=ORGANIZATION_ID,
                learner_id=learner_id,
                attempt_id=attempt_id,
                expected_version=confirmed.version,
                payload=FinalizeUploadInput(upload_session_id=upload_id),
                idempotency_key=f"capacity-finalize-{index}",
                trace_id=f"capacity-upload-trace-{index}",
            )
            finalize_ms = (time.perf_counter() - finalize_started) * 1_000
            await session.commit()
        assert finalized.task_id is not None
        return finalize_ms, finalized.task_id

    upload_results = await asyncio.gather(
        *(upload(index) for index in range(UPLOAD_CONCURRENCY))
    )
    assert len(content_by_upload) == UPLOAD_CONCURRENCY
    ai = _AI()
    outcomes = _Outcomes()
    handler = AudioPipelineTaskHandler(
        harness.sessions,
        ai_factory=lambda: ai,
        outcome_writer_factory=lambda _session: outcomes,
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )

    async def process(
        task_id: str,
        command: TaskCommand,
    ) -> tuple[float, bool]:
        started = time.perf_counter()
        result = await handler.execute(
            _ExecutionContext(task_id),
            AudioPipelineTaskInput.model_validate(command.input_payload),
        )
        return (time.perf_counter() - started) * 1_000, bool(result.resource_id)

    pipeline_results = await asyncio.gather(
        *(
            process(task_id, command)
            for task_id, command in task_commands
        )
    )
    async with harness.sessions() as session:
        completed_runs = int(
            await session.scalar(
                select(func.count(AudioActivityRun.run_id)).where(
                    AudioActivityRun.status == "completed"
                )
            )
            or 0
        )
        completed_submissions = int(
            await session.scalar(
                select(func.count(AudioSubmission.submission_id)).where(
                    AudioSubmission.state == "completed"
                )
            )
            or 0
        )
    finalize_samples = [elapsed for elapsed, _task_id in upload_results]
    pipeline_samples = [elapsed for elapsed, _valid in pipeline_results]
    return {
        "finalize": _metric(
            finalize_samples,
            failures=UPLOAD_CONCURRENCY - len({item[1] for item in upload_results}),
        ),
        "pipeline": _metric(
            pipeline_samples,
            failures=sum(1 for _elapsed, valid in pipeline_results if not valid),
        ),
        "completed_run_count": completed_runs,
        "completed_submission_count": completed_submissions,
        "outcome_count": len(outcomes.payloads),
        "provider_mode": "deterministic_fake",
    }


def _readiness_input() -> ReadinessProjectionInput:
    now = datetime.now(UTC)
    evidence = tuple(
        CompetencyEvidenceProjection(
            evidence_id=f"capacity-evidence-{key}",
            organization_id=ORGANIZATION_ID,
            learner_id="capacity-learner-0000",
            enrollment_id="capacity-enrollment-0000",
            competency_revision_id=f"capacity-competency-{key}-v1",
            competency_key=key,
            competency_title=key,
            source_activity_id="capacity-activity-000",
            attempt_id="capacity-attempt-0000-00",
            outcome_id=f"capacity-outcome-{key}",
            outcome_version=1,
            evidence_type="audio_assessment",
            evidence_role="performance",
            observed_score=90,
            observed_max_score=100,
            observed_result="passed",
            confidence=0.95,
            quality="verified",
            validity="valid",
            source_refs=(),
            lineage={},
            critical_flags=(),
            degradations=(),
            supersedes_evidence_id=None,
            observed_at=now,
        )
        for key in STANDARD_COMPETENCY_KEYS
    )
    return ReadinessProjectionInput(
        organization_id=ORGANIZATION_ID,
        learner_id="capacity-learner-0000",
        learner_name="容量学员 0000",
        enrollment_id="capacity-enrollment-0000",
        cohort_id="capacity-cohort",
        cohort_name="容量验证班级",
        path_revision_id="capacity-path-r1",
        path_title="新人基础训练容量基线",
        path_revision_label="capacity-v1",
        enrollment_status="active",
        activities=(
            ReadinessActivityInput(
                activity_id="capacity-activity-000",
                activity_type="audio_assessment",
                title="容量训练活动 001",
                required=True,
                status="completed",
            ),
        ),
        evidence=evidence,
        generated_at=now,
    )


async def _measure_dossier_projection(harness: CapacityHarness) -> dict[str, Any]:
    started = time.perf_counter()
    async with harness.sessions() as session:
        projection = await ReadinessService(session).project(
            _readiness_input(),
            actor_id="capacity-admin",
            trace_id="capacity-dossier-trace",
        )
        await session.commit()
    elapsed = (time.perf_counter() - started) * 1_000
    return {
        "elapsed_ms": round(elapsed, 2),
        "state": projection["status"],
        "snapshot_present": bool(projection["snapshot_id"]),
    }


@pytest.mark.asyncio
async def test_foundation_capacity_baseline_has_no_state_loss(
    capacity_harness: CapacityHarness,
) -> None:
    harness = capacity_harness
    started_at = datetime.now(UTC)
    await _seed_capacity_dataset(harness)
    journey = await _measure_concurrent_journeys(harness)
    admin_page = await _measure_admin_attempt_page(harness)
    ai_jobs = await _measure_ai_enqueue(harness)
    audio = await _measure_audio_workload(harness)
    dossier = await _measure_dossier_projection(harness)
    async with harness.sessions() as session:
        database_version = str(
            await session.scalar(text("SELECT current_setting('server_version')"))
        )
        counts = {
            "learners": int(
                await session.scalar(
                    select(func.count(User.user_id)).where(User.role == "user")
                )
                or 0
            ),
            "enrollments": int(
                await session.scalar(
                    select(func.count(NewcomerEnrollment.enrollment_id))
                )
                or 0
            ),
            "attempts": int(
                await session.scalar(
                    select(func.count(NewcomerActivityAttempt.attempt_id))
                )
                or 0
            ),
        }

    thresholds = {
        "journey_concurrent_p95_ms": 2_000,
        "ordinary_admin_api_p95_ms": 500,
        "ai_job_enqueue_p95_ms": 1_500,
        "audio_finalize_p95_ms": 2_000,
        "audio_pipeline_fake_p95_ms": 90_000,
        "dossier_projection_ms": 2_000,
    }
    checks = {
        "dataset_counts": counts
        == {
            "learners": LEARNER_COUNT,
            "enrollments": LEARNER_COUNT,
            "attempts": ATTEMPT_COUNT,
        },
        "journey_no_state_loss": journey["failure_count"] == 0,
        "journey_slo": journey["p95_ms"] <= thresholds["journey_concurrent_p95_ms"],
        "admin_page_slo": admin_page["p95_ms"]
        <= thresholds["ordinary_admin_api_p95_ms"],
        "admin_server_pagination": all(
            (
                admin_page["server_side_limit_offset"],
                admin_page["attempt_scope_is_page_bounded"],
                admin_page["server_side_sort"],
            )
        ),
        "ai_jobs_no_state_loss": ai_jobs["persisted_count"] == AI_JOB_CONCURRENCY
        and ai_jobs["unique_task_count"] == AI_JOB_CONCURRENCY,
        "ai_job_feedback_slo": ai_jobs["p95_ms"] <= thresholds["ai_job_enqueue_p95_ms"],
        "audio_no_state_loss": audio["completed_run_count"] == UPLOAD_CONCURRENCY
        and audio["completed_submission_count"] == UPLOAD_CONCURRENCY
        and audio["outcome_count"] == UPLOAD_CONCURRENCY,
        "audio_finalize_slo": audio["finalize"]["p95_ms"]
        <= thresholds["audio_finalize_p95_ms"],
        "audio_pipeline_slo": audio["pipeline"]["p95_ms"]
        <= thresholds["audio_pipeline_fake_p95_ms"],
        "dossier_slo": dossier["elapsed_ms"] <= thresholds["dossier_projection_ms"],
        "dossier_snapshot": dossier["snapshot_present"],
    }
    report = {
        "contract_version": "foundation_capacity_baseline_v1",
        "status": "passed" if all(checks.values()) else "failed",
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "environment": {
            "database": "isolated_local_postgresql_schema",
            "database_version": database_version,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "provider_mode": "deterministic_fake_for_audio_pipeline",
            "database_pool_size": 20,
        },
        "dataset": {
            **counts,
            "online_concurrency": ONLINE_CONCURRENCY,
            "upload_concurrency": UPLOAD_CONCURRENCY,
            "ai_job_concurrency": AI_JOB_CONCURRENCY,
            "activities_per_path": ACTIVITY_COUNT,
        },
        "thresholds": thresholds,
        "measurements": {
            "journey": journey,
            "admin_attempt_backed_page": admin_page,
            "ai_jobs": ai_jobs,
            "audio": audio,
            "dossier": dossier,
        },
        "checks": checks,
        "limitations": [
            "Journey concurrency is measured at the application service and PostgreSQL boundary; browser render is measured separately by Playwright.",
            "Audio pipeline uses deterministic fake media/ASR/LLM adapters; real-provider latency is a separate controlled staging gate.",
            "The dataset lives in a disposable PostgreSQL schema and is removed after the test.",
        ],
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert all(checks.values()), EVIDENCE_PATH

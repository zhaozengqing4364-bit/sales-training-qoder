from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    AIWorkloadKind,
    PromptCompilationService,
    PublishedPromptRevisionSnapshot,
    StaticPublishedPromptRevisionResolver,
    StrictPromptCompiler,
    compute_prompt_revision_content_hash,
)
from audio_assessment.contracts import (
    ASSIGNMENT_SEGMENTS,
    AudioPipelineTaskInput,
    AudioSubmissionState,
    ConfirmUploadPartInput,
    CreateUploadSessionInput,
    FinalizeUploadInput,
    UploadSessionState,
)
from audio_assessment.errors import AudioAssessmentError
from audio_assessment.governance import AudioGovernanceService
from audio_assessment.maintenance import AudioUploadMaintenanceService
from audio_assessment.models import (
    AudioActivityResourceRevision,
    AudioActivityRun,
    AudioArtifact,
    AudioCommandAudit,
    AudioScoreOutcomeVersion,
    AudioSubmission,
    AudioTranscriptRevision,
    AudioUploadPart,
    AudioUploadSession,
)
from audio_assessment.pipeline import AudioPipelineTaskHandler
from audio_assessment.ports import (
    AudioMediaInspection,
    AudioObjectMetadata,
    AudioOutcomePayload,
    NormalizedAudio,
    PresignedAudioPart,
    StoredAudioObject,
)
from audio_assessment.runtime import (
    AudioRuntimeService,
)
from audio_assessment.storage import AudioStorageError
from foundation_admin_api import AudioRegradePreviewRequest, preview_audio_regrade
from foundation_admin_permissions import FoundationAdminActors
from foundation_learner_api import get_audio_artifact_playback
from learning.contracts import LearningActor
from newcomer_training.application import CommandActor
from task_runtime import TaskRegistry
from task_runtime.contracts import TaskReference, TaskState
from task_runtime.errors import TaskExecutionError


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


def _ai_contract(*, workload: str) -> dict[str, object]:
    is_asr = workload == "asr"
    return {
        "business_purpose": f"foundation_audio_{workload}",
        "prompt_template_id": None if is_asr else "audio-score-prompt",
        "prompt_revision_id": None if is_asr else "audio-score-prompt-v1",
        "model_routing_profile_id": f"audio-{workload}-routing",
        "model_routing_revision_id": f"audio-{workload}-routing-v1",
        "input_schema_version": f"audio_{workload}_input_v1",
        "output_schema_version": (
            "audio_transcript_output_v1" if is_asr else "audio_scoring_output_v1"
        ),
        "timeout_policy_ref": f"audio-{workload}-timeout-v1",
        "retry_policy_ref": f"audio-{workload}-retry-v1",
    }


def _prompt_compiler() -> PromptCompilationService:
    template = "\n".join(
        (
            "提交：{{ submission_id }}",
            "活动：{{ activity_type }}",
            "分段：{{ segment_id }}",
            "场景：{{ scenario_json }}",
            "转写：{{ transcript }}",
            "分段转写：{{ segments_json }}",
            "质量：{{ quality_json }}",
            "评分维度：{{ dimensions_json }}",
            "知识边界：{{ allowed_knowledge_json }}",
        )
    )
    variables = (
        "activity_type",
        "allowed_knowledge_json",
        "dimensions_json",
        "quality_json",
        "scenario_json",
        "segment_id",
        "segments_json",
        "submission_id",
        "transcript",
    )
    revision = PublishedPromptRevisionSnapshot(
        template_id="audio-score-prompt",
        business_purpose="foundation_audio_scoring",
        revision_id="audio-score-prompt-v1",
        revision_no=1,
        status="published",
        template=template,
        variables=variables,
        input_schema_version="audio_scoring_input_v1",
        output_schema_version="audio_scoring_output_v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="audio-score-prompt",
            business_purpose="foundation_audio_scoring",
            revision_id="audio-score-prompt-v1",
            revision_no=1,
            template=template,
            variables=variables,
            input_schema_version="audio_scoring_input_v1",
            output_schema_version="audio_scoring_output_v1",
        ),
    )
    return PromptCompilationService(
        resolver=StaticPublishedPromptRevisionResolver([revision]),
        compiler=StrictPromptCompiler(),
    )


def _scoring_snapshot(
    *,
    max_size_bytes: int = 1024 * 1024,
    max_duration_seconds: int = 60,
) -> dict[str, object]:
    return {
        "language": "zh-CN",
        "capture": {
            "allowed_recording_modes": ["browser", "file"],
            "allowed_content_types": ["audio/webm"],
            "max_duration_seconds": max_duration_seconds,
            "max_size_bytes": max_size_bytes,
            "part_size_bytes": 256 * 1024,
            "local_draft_ttl_seconds": 604800,
            "upload_ttl_seconds": 3600,
        },
        "quality": {
            "minimum_asr_confidence": 0.65,
            "minimum_speech_ratio": 0.35,
            "maximum_silence_ratio": 0.65,
            "maximum_clipping_ratio": 0.05,
            "minimum_mean_volume_db": -45,
        },
        "asr": _ai_contract(workload="asr"),
        "scoring": _ai_contract(workload="scoring"),
        "dimensions": [
            {
                "key": "structure",
                "label": "表达结构",
                "rubric": "结论、依据和下一步清晰完整。",
                "weight": 1.0,
                "competency_keys": ["communication_structure"],
                "minimum_score": 70,
            }
        ],
        "pass_score": 75,
        "allowed_knowledge": ["只根据已发布基础训练材料评分"],
        "allow_transcript_correction_request": True,
    }


async def _resources(
    session: AsyncSession,
    *,
    max_size_bytes: int = 1024 * 1024,
    max_duration_seconds: int = 60,
) -> None:
    now = datetime.now(UTC)
    material = {
        "title": "公司与方案讲解",
        "task_prompt": "请用清晰结构介绍公司与方案价值。",
        "preparation_hints": ["先说客户问题，再说价值和边界"],
    }
    scenario = {
        "title": "首次客户沟通",
        "segments": [
            {
                "segment_id": "discovery",
                "title": "需求澄清",
                "customer_context": "客户正在梳理当前业务目标。",
                "prompt": "请通过提问确认客户目标和约束。",
                "preparation_hints": ["先确认目标，再确认限制"],
            },
            {
                "segment_id": "objection",
                "title": "异议回应",
                "customer_context": "客户担心方案实施成本。",
                "prompt": "请回应成本异议并说明价值边界。",
                "preparation_hints": ["承认顾虑，给出依据"],
            },
            {
                "segment_id": "commitment",
                "title": "推进承诺",
                "customer_context": "客户愿意继续了解。",
                "prompt": "请确认双方下一步行动。",
                "preparation_hints": ["明确负责人和时间"],
            },
        ],
    }
    scoring = _scoring_snapshot(
        max_size_bytes=max_size_bytes,
        max_duration_seconds=max_duration_seconds,
    )
    session.add_all(
        [
            AudioActivityResourceRevision(
                revision_id="audio-material-v1",
                organization_id="org-1",
                resource_type="audio_material",
                stable_key="foundation-audio-material",
                revision_no=1,
                status="published",
                title="公司与方案讲解",
                snapshot_json=material,
                content_hash=_hash(material),
                created_by="admin-1",
                created_at=now,
                published_at=now,
            ),
            AudioActivityResourceRevision(
                revision_id="audio-scenario-v1",
                organization_id="org-1",
                resource_type="scenario",
                stable_key="foundation-audio-scenario",
                revision_no=1,
                status="published",
                title="首次客户沟通",
                snapshot_json=scenario,
                content_hash=_hash(scenario),
                created_by="admin-1",
                created_at=now,
                published_at=now,
            ),
            AudioActivityResourceRevision(
                revision_id="audio-scoring-v1",
                organization_id="org-1",
                resource_type="scoring_scheme",
                stable_key="foundation-audio-scoring",
                revision_no=1,
                status="published",
                title="公司与方案讲解评分方案",
                snapshot_json=scoring,
                content_hash=_hash(scoring),
                created_by="admin-1",
                created_at=now,
                published_at=now,
            ),
        ]
    )
    await session.flush()


class _TaskRuntime:
    def __init__(self) -> None:
        self.commands = []

    async def enqueue(self, command):
        self.commands.append(command)
        return TaskReference(
            task_id=f"audio-task-{len(self.commands)}",
            state=TaskState.QUEUED,
            organization_id=command.organization_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            created_at=datetime.now(UTC),
        )

    async def request_cancel(self, task_id, actor, *, idempotency_key=None):
        raise AssertionError((task_id, actor, idempotency_key))

    async def get(self, task_id, viewer):
        del task_id, viewer
        return SimpleNamespace(state=TaskState.QUEUED)


class _AttemptInvalidator:
    async def invalidate(self, **values) -> None:
        del values


class _Storage:
    backend_name = "fake"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def presign_part(self, **values) -> PresignedAudioPart:
        return PresignedAudioPart(
            upload_url=f"https://upload.invalid/{values['object_key']}",
            object_key=values["object_key"],
            expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            required_headers={"X-Audio-Sha256": values["sha256"]},
        )

    async def head(self, object_key: str) -> AudioObjectMetadata:
        value = self.objects[object_key]
        return AudioObjectMetadata(
            object_key=object_key,
            size_bytes=len(value),
            sha256=hashlib.sha256(value).hexdigest(),
            content_type="audio/webm",
        )

    async def materialize(self, object_keys, destination: Path) -> None:
        with destination.open("wb") as target:
            for key in object_keys:
                target.write(self.objects[key])

    async def store_file(
        self,
        *,
        object_key: str,
        source: Path,
        content_type: str,
        sha256: str,
    ) -> StoredAudioObject:
        value = source.read_bytes()
        assert hashlib.sha256(value).hexdigest() == sha256
        self.objects[object_key] = value
        return StoredAudioObject(
            artifact_ref=f"artifact://audio/fake/{object_key}",
            object_key=object_key,
            size_bytes=len(value),
            sha256=sha256,
            content_type=content_type,
        )

    def signed_get_url(self, object_key: str, *, expires_seconds: int) -> str:
        return f"https://download.invalid/{object_key}?ttl={expires_seconds}"

    async def delete(self, object_keys) -> None:
        for key in object_keys:
            self.objects.pop(key, None)


class _FailingStorage(_Storage):
    async def head(self, object_key: str) -> AudioObjectMetadata:
        del object_key
        raise AudioStorageError(
            "audio_storage_unavailable",
            "录音存储暂时不可用，已保留上传记录，可稍后重试。",
            retryable=True,
        )


class _FailingDeleteStorage(_Storage):
    def __init__(self) -> None:
        super().__init__()
        self.fail_delete = True

    async def delete(self, object_keys) -> None:
        if self.fail_delete:
            raise AudioStorageError(
                "audio_storage_delete_failed",
                "暂时无法清理未完成录音。",
                retryable=True,
            )
        await super().delete(object_keys)


class _Media:
    async def inspect_and_normalize(
        self,
        *,
        source: Path,
        destination: Path,
        declared_content_type: str,
        max_duration_seconds: int,
    ) -> NormalizedAudio:
        assert max_duration_seconds == 60
        shutil.copyfile(source, destination)
        return NormalizedAudio(
            path=destination,
            content_type="audio/wav",
            inspection=AudioMediaInspection(
                content_type=declared_content_type,
                duration_seconds=3.0,
                sample_rate_hz=48_000,
                channels=1,
                speech_ratio=0.9,
                silence_ratio=0.1,
                clipping_ratio=0.0,
                mean_volume_db=-20,
                tool_version="fake-media-v1",
            ),
        )


class _AI:
    def __init__(
        self,
        *,
        confidence: float = 0.95,
        fail_asr: bool = False,
        invalid_score_schema: bool = False,
    ) -> None:
        self.confidence = confidence
        self.fail_asr = fail_asr
        self.invalid_score_schema = invalid_score_schema
        self.requests = []
        self.results: dict[str, AIInvocationResult] = {}

    async def invoke(self, request):
        self.requests.append(request)
        if request.idempotency_key in self.results:
            return self.results[request.idempotency_key]
        if request.workload_kind is AIWorkloadKind.ASR and self.fail_asr:
            result = AIInvocationResult(
                invocation_id="asr-timeout-1",
                workload_kind=AIWorkloadKind.ASR,
                status=AIInvocationStatus.FAILED,
                failure=AIInvocationFailure(
                    code="provider_timeout",
                    classification=AIErrorClassification.TIMEOUT,
                    retryable=True,
                    message="转写服务暂时超时。",
                ),
                model_routing_profile_id=request.model_routing_profile_id,
                model_routing_revision_id=request.model_routing_revision_id,
                usage=AIUsageSummary(),
                created_at=datetime.now(UTC),
            )
        elif request.workload_kind is AIWorkloadKind.ASR:
            result = AIInvocationResult(
                invocation_id=f"asr-{len(self.results) + 1}",
                workload_kind=AIWorkloadKind.ASR,
                status=AIInvocationStatus.SUCCEEDED,
                validated_output={
                    "transcript": "我们先确认客户目标，再说明方案价值和下一步。",
                    "confidence": self.confidence,
                    "language": "zh-CN",
                    "segments": [
                        {
                            "sequence": 1,
                            "start_ms": 0,
                            "end_ms": 3000,
                            "text": "我们先确认客户目标，再说明方案价值和下一步。",
                            "confidence": self.confidence,
                            "speaker": None,
                        }
                    ],
                },
                model_routing_profile_id=request.model_routing_profile_id,
                model_routing_revision_id=request.model_routing_revision_id,
                provider="fake-asr",
                model="fake-asr-v1",
                usage=AIUsageSummary(),
                created_at=datetime.now(UTC),
            )
        else:
            result = AIInvocationResult(
                invocation_id=f"score-{len(self.results) + 1}",
                workload_kind=AIWorkloadKind.LLM,
                status=AIInvocationStatus.SUCCEEDED,
                validated_output=(
                    {"dimension_scores": "invalid"}
                    if self.invalid_score_schema
                    else {
                        "dimension_scores": [
                            {
                                "dimension_key": "structure",
                                "score": 88,
                                "uncertainty": 0.08,
                            }
                        ],
                        "evidence_spans": [
                            {
                                "dimension_key": "structure",
                                "segment_sequence": 1,
                                "quote": "先确认客户目标",
                                "rationale": "先目标后价值，结构清晰。",
                            }
                        ],
                        "missing_points": [],
                        "uncertainty": 0.08,
                        "feedback": ["继续保留明确的下一步。"],
                        "recommended_remediation": [],
                        "critical_flags": [],
                    }
                ),
                prompt_template_id=request.prompt_template_id,
                prompt_revision_id=request.prompt_revision_id,
                prompt_contract_hash=request.prompt_contract_hash,
                model_routing_profile_id=request.model_routing_profile_id,
                model_routing_revision_id=request.model_routing_revision_id,
                provider="fake-llm",
                model="fake-score-v1",
                usage=AIUsageSummary(),
                created_at=datetime.now(UTC),
            )
        self.results[request.idempotency_key] = result
        return result


class _Outcomes:
    def __init__(self) -> None:
        self.payloads: dict[str, AudioOutcomePayload] = {}

    async def record(self, payload: AudioOutcomePayload) -> str:
        self.payloads.setdefault(payload.idempotency_key, payload)
        return f"generic-{len(self.payloads)}"


class _Fence:
    async def assert_current(self) -> None:
        return None


class _ExecutionContext:
    def __init__(self, task_id: str) -> None:
        self.claim = SimpleNamespace(task_id=task_id)
        self.progress = []

    async def report_progress(self, **values) -> None:
        self.progress.append(values)

    async def checkpoint(self) -> None:
        return None

    def fenced(self, session) -> _Fence:
        del session
        return _Fence()


async def _uploaded_run(
    session: AsyncSession,
    *,
    storage: _Storage,
    tasks: _TaskRuntime,
) -> tuple[AudioActivityRun, AudioSubmission]:
    await _resources(session)
    runtime = AudioRuntimeService(session, task_runtime=tasks, storage=storage)
    started = await runtime.start(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="audio-explanation-1",
        activity_type="audio_assessment",
        attempt_id="attempt-1",
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
        idempotency_key="start-1",
    )
    content = b"durable-audio"
    declaration = {
        "part_number": 1,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    created = await runtime.create_upload_session(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-1",
        expected_version=started.version,
        payload=CreateUploadSessionInput(
            segment_id="primary",
            recording_mode="browser",
            original_filename="讲解录音.webm",
            content_type="audio/webm",
            size_bytes=len(content),
            duration_seconds=3,
            manifest_sha256=_hash([declaration]),
            parts=(declaration,),
        ),
        idempotency_key="upload-1",
    )
    part = await session.scalar(select(AudioUploadPart).limit(1))
    assert part is not None
    storage.objects[part.object_key] = content
    confirmed = await runtime.confirm_upload_part(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-1",
        expected_version=created.version,
        payload=ConfirmUploadPartInput(
            upload_session_id=created.runner["active_upload"]["upload_session_id"],
            part_number=1,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
    )
    finalized = await runtime.finalize_upload(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-1",
        expected_version=confirmed.version,
        payload=FinalizeUploadInput(
            upload_session_id=created.runner["active_upload"]["upload_session_id"]
        ),
        idempotency_key="finalize-1",
        trace_id="trace-1",
    )
    assert "create_upload_session" not in finalized.available_commands
    assert finalized.available_commands == ("cancel",)
    await session.commit()
    run = await session.scalar(select(AudioActivityRun).limit(1))
    submission = await session.scalar(select(AudioSubmission).limit(1))
    assert run is not None and submission is not None
    return run, submission


@pytest.mark.asyncio
async def test_upload_pipeline_is_recoverable_and_reconcile_is_idempotent(
    test_db: AsyncSession,
    test_engine,
) -> None:
    storage = _Storage()
    tasks = _TaskRuntime()
    run, submission = await _uploaded_run(test_db, storage=storage, tasks=tasks)
    ai = _AI()
    outcomes = _Outcomes()
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    handler = AudioPipelineTaskHandler(
        sessions,
        ai_factory=lambda: ai,
        outcome_writer_factory=lambda session: outcomes,
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )
    context = _ExecutionContext("audio-task-1")
    run_id = run.run_id
    submission_id = submission.submission_id

    first = await handler.execute(
        context,
        AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
    )
    restarted_handler = AudioPipelineTaskHandler(
        sessions,
        ai_factory=lambda: ai,
        outcome_writer_factory=lambda session: outcomes,
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )
    second = await restarted_handler.execute(
        context,
        AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
    )

    test_db.expire_all()
    refreshed_run = await test_db.get(AudioActivityRun, run_id)
    refreshed_submission = await test_db.get(AudioSubmission, submission_id)
    assert refreshed_run is not None and refreshed_run.status == "completed"
    assert refreshed_submission is not None
    assert refreshed_submission.state == AudioSubmissionState.COMPLETED.value
    assert first.structured_payload == second.structured_payload
    assert (
        int(
            await test_db.scalar(
                select(func.count(AudioTranscriptRevision.revision_id))
            )
            or 0
        )
        == 1
    )
    assert (
        int(
            await test_db.scalar(
                select(func.count(AudioScoreOutcomeVersion.outcome_version_id))
            )
            or 0
        )
        == 1
    )
    score_request = next(
        request
        for request in ai.requests
        if request.workload_kind is AIWorkloadKind.LLM
    )
    assert score_request.prompt_contract_hash is not None
    assert score_request.prompt_contract_hash.startswith("sha256:")
    assert len(outcomes.payloads) == 1
    assert next(iter(outcomes.payloads.values())).passed is True
    normalized = await test_db.scalar(
        select(AudioArtifact)
        .where(AudioArtifact.submission_id == submission_id)
        .where(AudioArtifact.kind == "normalized")
    )
    assert normalized is not None
    denied_playback = await get_audio_artifact_playback(
        normalized.artifact_id,
        actor=CommandActor(
            organization_id="org-2",
            actor_id="learner-1",
            capabilities=frozenset({"newcomer.activity.execute"}),
        ),
        db=test_db,
    )
    assert denied_playback.status_code == 404
    denied_audit = await test_db.scalar(
        select(AudioCommandAudit)
        .where(AudioCommandAudit.object_id == normalized.artifact_id)
        .where(AudioCommandAudit.command == "listen_audio_artifact")
        .where(AudioCommandAudit.result == "denied")
    )
    assert denied_audit is not None
    assert denied_audit.organization_id == "org-2"
    projection = await AudioRuntimeService(
        test_db,
        task_runtime=tasks,
        storage=storage,
    ).workspace(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-1",
    )
    assert projection is not None
    segment = projection.runner["segments"][0]
    assert segment["transcript"]["text"] == (
        "我们先确认客户目标，再说明方案价值和下一步。"
    )
    assert segment["transcript"]["segments"][0]["start_ms"] == 0
    assert segment["transcript"]["language"] == "zh-CN"
    assert segment["result"]["dimension_scores"][0]["label"] == "表达结构"
    assert segment["result"]["evidence_spans"][0]["quote"]
    assert segment["quality"]["scorable"] is True


@pytest.mark.asyncio
async def test_low_confidence_is_not_scored_as_competency_failure(
    test_db: AsyncSession,
    test_engine,
) -> None:
    storage = _Storage()
    tasks = _TaskRuntime()
    _, submission = await _uploaded_run(test_db, storage=storage, tasks=tasks)
    submission_id = submission.submission_id
    ai = _AI(confidence=0.2)
    outcomes = _Outcomes()
    handler = AudioPipelineTaskHandler(
        async_sessionmaker(test_engine, expire_on_commit=False),
        ai_factory=lambda: ai,
        outcome_writer_factory=lambda session: outcomes,
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )
    submission_id = submission.submission_id

    result = await handler.execute(
        _ExecutionContext("audio-task-1"),
        AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
    )

    test_db.expire_all()
    refreshed = await test_db.get(AudioSubmission, submission_id)
    assert refreshed is not None
    assert refreshed.state == AudioSubmissionState.NEEDS_REVIEW.value
    assert result.structured_payload["state"] == "needs_review"
    assert len(ai.requests) == 1
    assert outcomes.payloads == {}
    assert (
        int(
            await test_db.scalar(
                select(func.count(AudioScoreOutcomeVersion.outcome_version_id))
            )
            or 0
        )
        == 0
    )


@pytest.mark.asyncio
async def test_asr_timeout_preserves_audio_in_recoverable_state(
    test_db: AsyncSession,
    test_engine,
) -> None:
    storage = _Storage()
    tasks = _TaskRuntime()
    _, submission = await _uploaded_run(test_db, storage=storage, tasks=tasks)
    handler = AudioPipelineTaskHandler(
        async_sessionmaker(test_engine, expire_on_commit=False),
        ai_factory=lambda: _AI(fail_asr=True),
        outcome_writer_factory=lambda session: _Outcomes(),
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )
    submission_id = submission.submission_id

    with pytest.raises(TaskExecutionError):
        await handler.execute(
            _ExecutionContext("audio-task-1"),
            AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
        )

    test_db.expire_all()
    refreshed = await test_db.get(AudioSubmission, submission_id)
    assert refreshed is not None
    assert refreshed.state == AudioSubmissionState.FAILED_RECOVERABLE.value
    assert refreshed.failed_stage == "transcription"
    assert refreshed.original_artifact_id is not None
    assert refreshed.normalized_artifact_id is not None

    governance = AudioGovernanceService(
        test_db,
        task_runtime=tasks,
        attempt_invalidator=_AttemptInvalidator(),
    )
    repaired = await governance.repair_pipeline(
        actor=CommandActor(
            organization_id="org-1",
            actor_id="reviewer-1",
            capabilities=frozenset({"newcomer.audio.review"}),
            trace_id="trace-repair-1",
        ),
        submission_id=submission_id,
        reason="转写服务恢复后从失败步骤继续",
        idempotency_key="repair-1",
    )
    await test_db.commit()
    assert repaired.state == AudioSubmissionState.TRANSCRIBING.value
    assert repaired.task_id == "audio-task-2"
    repair_audit = await test_db.scalar(
        select(AudioCommandAudit)
        .where(AudioCommandAudit.object_id == submission_id)
        .where(AudioCommandAudit.command == "repair_audio_pipeline")
    )
    assert repair_audit is not None
    assert repair_audit.result == "succeeded"


@pytest.mark.asyncio
async def test_invalid_scoring_schema_is_recoverable_and_keeps_lineage(
    test_db: AsyncSession,
    test_engine,
) -> None:
    storage = _Storage()
    tasks = _TaskRuntime()
    _, submission = await _uploaded_run(test_db, storage=storage, tasks=tasks)
    submission_id = submission.submission_id
    handler = AudioPipelineTaskHandler(
        async_sessionmaker(test_engine, expire_on_commit=False),
        ai_factory=lambda: _AI(invalid_score_schema=True),
        outcome_writer_factory=lambda session: _Outcomes(),
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )

    with pytest.raises(TaskExecutionError):
        await handler.execute(
            _ExecutionContext("audio-task-1"),
            AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
        )

    test_db.expire_all()
    refreshed = await test_db.get(AudioSubmission, submission_id)
    assert refreshed is not None
    assert refreshed.state == AudioSubmissionState.FAILED_RECOVERABLE.value
    assert refreshed.failed_stage == "scoring"
    assert refreshed.error_classification == "schema_validation"
    assert refreshed.current_transcript_revision_id is not None
    assert refreshed.current_score_outcome_version_id is None
    assert refreshed.original_artifact_id is not None
    assert refreshed.normalized_artifact_id is not None


@pytest.mark.asyncio
async def test_storage_failure_is_recoverable_and_keeps_uploaded_parts(
    test_db: AsyncSession,
    test_engine,
) -> None:
    storage = _FailingStorage()
    tasks = _TaskRuntime()
    _, submission = await _uploaded_run(test_db, storage=storage, tasks=tasks)
    submission_id = submission.submission_id
    handler = AudioPipelineTaskHandler(
        async_sessionmaker(test_engine, expire_on_commit=False),
        ai_factory=_AI,
        outcome_writer_factory=lambda session: _Outcomes(),
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )

    with pytest.raises(TaskExecutionError):
        await handler.execute(
            _ExecutionContext("audio-task-1"),
            AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
        )

    test_db.expire_all()
    refreshed = await test_db.get(AudioSubmission, submission_id)
    assert refreshed is not None
    assert refreshed.state == AudioSubmissionState.FAILED_RECOVERABLE.value
    assert refreshed.failed_stage == "validation"
    assert refreshed.error_classification == "audio_storage_unavailable"
    assert refreshed.original_artifact_id is None
    assert storage.objects


@pytest.mark.asyncio
async def test_manual_correction_retranscription_and_regrade_append_history(
    test_db: AsyncSession,
    test_engine,
) -> None:
    storage = _Storage()
    tasks = _TaskRuntime()
    _, submission = await _uploaded_run(test_db, storage=storage, tasks=tasks)
    submission_id = submission.submission_id
    ai = _AI()
    outcomes = _Outcomes()
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    handler = AudioPipelineTaskHandler(
        sessions,
        ai_factory=lambda: ai,
        outcome_writer_factory=lambda session: outcomes,
        prompt_compiler=_prompt_compiler(),
        storage=storage,
        media=_Media(),
    )
    await handler.execute(
        _ExecutionContext("audio-task-1"),
        AudioPipelineTaskInput.model_validate(tasks.commands[0].input_payload),
    )
    test_db.expire_all()
    actor = CommandActor(
        organization_id="org-1",
        actor_id="reviewer-1",
        capabilities=frozenset(
            {
                "newcomer.audio.transcript.correct",
                "newcomer.audio.regrade",
            }
        ),
        trace_id="trace-review-1",
    )
    governance = AudioGovernanceService(
        test_db,
        task_runtime=tasks,
        attempt_invalidator=_AttemptInvalidator(),
    )
    correction = await governance.preview_transcript_correction(
        actor=actor,
        submission_id=submission_id,
        transcript="我们先确认客户目标，再说明经过核对的方案价值和下一步。",
        reason="人工核对录音后修正同音词",
    )
    corrected = await governance.confirm_transcript_correction(
        actor=actor,
        submission_id=submission_id,
        preview_token=correction.preview_token,
        impact_hash=correction.impact_hash,
        idempotency_key="correct-1",
    )
    await test_db.commit()
    assert corrected.task_id == "audio-task-2"

    await handler.execute(
        _ExecutionContext("audio-task-2"),
        AudioPipelineTaskInput.model_validate(tasks.commands[1].input_payload),
    )
    test_db.expire_all()
    retranscription = await governance.preview_regrade(
        actor=actor,
        submission_id=submission_id,
        mode="retranscribe",
        target_scoring_scheme_revision_id=None,
        reason="使用已校准转写路由重新处理",
    )
    queued = await governance.confirm_regrade(
        actor=actor,
        submission_id=submission_id,
        preview_token=retranscription.preview_token,
        impact_hash=retranscription.impact_hash,
        idempotency_key="retranscribe-1",
    )
    await test_db.commit()
    assert queued.task_id == "audio-task-3"
    await handler.execute(
        _ExecutionContext("audio-task-3"),
        AudioPipelineTaskInput.model_validate(tasks.commands[2].input_payload),
    )
    test_db.expire_all()

    revisions = list(
        (
            await test_db.execute(
                select(AudioTranscriptRevision)
                .where(AudioTranscriptRevision.submission_id == submission_id)
                .order_by(AudioTranscriptRevision.revision_no)
            )
        ).scalars()
    )
    scores = list(
        (
            await test_db.execute(
                select(AudioScoreOutcomeVersion)
                .where(AudioScoreOutcomeVersion.submission_id == submission_id)
                .order_by(AudioScoreOutcomeVersion.version_no)
            )
        ).scalars()
    )
    correction_audit = await test_db.scalar(
        select(AudioCommandAudit)
        .where(AudioCommandAudit.object_id == submission_id)
        .where(AudioCommandAudit.command == "correct_audio_transcript")
    )
    assert [item.source for item in revisions] == [
        "automatic",
        "manual_correction",
        "retranscription",
    ]
    assert [item.version_no for item in scores] == [1, 2, 3]
    assert scores[1].supersedes_outcome_version_id == scores[0].outcome_version_id
    assert scores[2].supersedes_outcome_version_id == scores[1].outcome_version_id
    assert len(outcomes.payloads) == 3
    assert correction_audit is not None
    assert correction_audit.capability == "newcomer.audio.transcript.correct"

    with pytest.raises(AudioAssessmentError) as hidden:
        await governance.preview_regrade(
            actor=actor.model_copy(update={"organization_id": "org-2"}),
            submission_id=submission_id,
            mode="regrade",
            target_scoring_scheme_revision_id=None,
            reason="跨组织请求应被隐藏",
        )
    assert hidden.value.code == "[AUDIO_SUBMISSION_NOT_FOUND]"

    cross_org_actor = actor.model_copy(update={"organization_id": "org-2"})
    denied_regrade = await preview_audio_regrade(
        submission_id=submission_id,
        payload=AudioRegradePreviewRequest(
            mode="regrade",
            reason="验证跨组织重评必须拒绝并留痕",
        ),
        actors=FoundationAdminActors(
            newcomer=cross_org_actor,
            learning=LearningActor(
                organization_id="org-2",
                actor_id=cross_org_actor.actor_id,
                capabilities=frozenset(),
            ),
        ),
        db=test_db,
        registry=TaskRegistry(),
    )
    assert denied_regrade.status_code == 404
    denied_regrade_audit = await test_db.scalar(
        select(AudioCommandAudit)
        .where(AudioCommandAudit.object_id == submission_id)
        .where(AudioCommandAudit.command == "preview_audio_regrade")
        .where(AudioCommandAudit.result == "denied")
    )
    assert denied_regrade_audit is not None
    assert denied_regrade_audit.organization_id == "org-2"


@pytest.mark.asyncio
async def test_server_enforces_frozen_limits_and_part_layout(
    test_db: AsyncSession,
) -> None:
    await _resources(test_db, max_size_bytes=300_000, max_duration_seconds=10)
    runtime = AudioRuntimeService(
        test_db,
        task_runtime=_TaskRuntime(),
        storage=_Storage(),
    )
    started = await runtime.start(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="audio-explanation-1",
        activity_type="audio_assessment",
        attempt_id="attempt-1",
        config={
            "audio_material_revision_id": "audio-material-v1",
            "scoring_scheme_revision_id": "audio-scoring-v1",
            "max_duration_seconds": 10,
            "max_size_bytes": 300_000,
        },
        competency_keys=(),
        idempotency_key="start-limit",
    )
    first = {"part_number": 1, "size_bytes": 200_000, "sha256": "a" * 64}
    second = {"part_number": 2, "size_bytes": 100_000, "sha256": "b" * 64}

    with pytest.raises(AudioAssessmentError) as invalid_layout:
        await runtime.create_upload_session(
            organization_id="org-1",
            learner_id="learner-1",
            attempt_id="attempt-1",
            expected_version=started.version,
            payload=CreateUploadSessionInput(
                segment_id="primary",
                original_filename="audio.webm",
                content_type="audio/webm",
                size_bytes=300_000,
                duration_seconds=10,
                manifest_sha256=_hash([first, second]),
                parts=(first, second),
            ),
            idempotency_key="bad-layout",
        )

    assert invalid_layout.value.code == "[AUDIO_UPLOAD_PART_LAYOUT_INVALID]"

    declaration = {
        "part_number": 1,
        "size_bytes": 300_001,
        "sha256": "c" * 64,
    }
    with pytest.raises(AudioAssessmentError) as too_large:
        await runtime.create_upload_session(
            organization_id="org-1",
            learner_id="learner-1",
            attempt_id="attempt-1",
            expected_version=started.version,
            payload=CreateUploadSessionInput(
                segment_id="primary",
                original_filename="audio.webm",
                content_type="audio/webm",
                size_bytes=300_001,
                duration_seconds=10,
                manifest_sha256=_hash([declaration]),
                parts=(declaration,),
            ),
            idempotency_key="too-large",
        )

    assert too_large.value.code == "[AUDIO_SIZE_LIMIT_EXCEEDED]"


@pytest.mark.asyncio
async def test_upload_session_expires_resumes_and_can_be_cancelled(
    test_db: AsyncSession,
    test_engine,
) -> None:
    await _resources(test_db)
    storage = _FailingDeleteStorage()
    runtime = AudioRuntimeService(
        test_db,
        task_runtime=_TaskRuntime(),
        storage=storage,
    )
    started = await runtime.start(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="audio-explanation-1",
        activity_type="audio_assessment",
        attempt_id="attempt-expiry",
        config={
            "audio_material_revision_id": "audio-material-v1",
            "scoring_scheme_revision_id": "audio-scoring-v1",
        },
        competency_keys=(),
        idempotency_key="start-expiry",
    )
    content = b"resumable-audio"
    declaration = {
        "part_number": 1,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    payload = CreateUploadSessionInput(
        segment_id="primary",
        original_filename="audio.webm",
        content_type="audio/webm",
        size_bytes=len(content),
        duration_seconds=3,
        manifest_sha256=_hash([declaration]),
        parts=(declaration,),
    )
    created = await runtime.create_upload_session(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-expiry",
        expected_version=started.version,
        payload=payload,
        idempotency_key="upload-expiry-1",
    )
    upload_id = created.runner["active_upload"]["upload_session_id"]
    upload = await test_db.get(AudioUploadSession, upload_id)
    assert upload is not None
    first_part = await test_db.scalar(
        select(AudioUploadPart).where(AudioUploadPart.upload_session_id == upload_id)
    )
    assert first_part is not None
    storage.objects[first_part.object_key] = content
    upload.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await test_db.flush([upload])

    assert await runtime.expire_uploads() == 1
    await test_db.refresh(upload)
    assert upload.state == UploadSessionState.EXPIRED.value
    expired_workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-expiry",
    )
    assert expired_workspace is not None
    assert "create_upload_session" in expired_workspace.available_commands

    resumed = await runtime.create_upload_session(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-expiry",
        expected_version=expired_workspace.version,
        payload=payload,
        idempotency_key="upload-expiry-2",
    )
    with pytest.raises(AudioAssessmentError) as fake_part:
        await runtime.confirm_upload_part(
            organization_id="org-1",
            learner_id="learner-1",
            attempt_id="attempt-expiry",
            expected_version=resumed.version,
            payload=ConfirmUploadPartInput(
                upload_session_id=resumed.runner["active_upload"]["upload_session_id"],
                part_number=1,
                size_bytes=len(content),
                sha256="f" * 64,
            ),
        )
    assert fake_part.value.code == "[AUDIO_UPLOAD_PART_MISMATCH]"

    cancelled = await runtime.cancel_run(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-expiry",
        expected_version=resumed.version,
        idempotency_key="cancel-expiry",
    )
    assert cancelled.status == "cancelled"
    resumed_upload = await test_db.get(
        AudioUploadSession,
        resumed.runner["active_upload"]["upload_session_id"],
    )
    assert resumed_upload is not None
    assert resumed_upload.state == UploadSessionState.CANCELLED.value
    resumed_part = await test_db.scalar(
        select(AudioUploadPart).where(
            AudioUploadPart.upload_session_id == resumed_upload.upload_session_id
        )
    )
    assert resumed_part is not None
    storage.objects[resumed_part.object_key] = content
    resumed_upload_id = resumed_upload.upload_session_id
    await test_db.commit()

    maintenance = AudioUploadMaintenanceService(
        async_sessionmaker(test_engine, expire_on_commit=False),
        storage=storage,
    )
    failed = await maintenance.run_once()
    assert failed.claimed_count == 2
    assert failed.failed_count == 2
    storage.fail_delete = False
    cleaned = await maintenance.run_once()
    assert cleaned.claimed_count == 2
    assert cleaned.cleaned_count == 2
    assert not storage.objects

    test_db.expire_all()
    refreshed = await test_db.get(AudioUploadSession, resumed_upload_id)
    assert refreshed is not None
    assert refreshed.cleanup_attempts == 2
    assert refreshed.cleanup_completed_at is not None
    assert (await maintenance.run_once()).claimed_count == 0


@pytest.mark.asyncio
async def test_assignment_uses_fixed_segments_and_enforces_sequence(
    test_db: AsyncSession,
) -> None:
    await _resources(test_db)
    runtime = AudioRuntimeService(
        test_db,
        task_runtime=_TaskRuntime(),
        storage=_Storage(),
    )
    started = await runtime.start(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="assignment-1",
        activity_type="assignment",
        attempt_id="attempt-assignment",
        config={
            "scenario_revision_id": "audio-scenario-v1",
            "scoring_scheme_revision_id": "audio-scoring-v1",
        },
        competency_keys=("communication_structure",),
        idempotency_key="start-assignment",
    )
    assert (
        tuple(item["segment_id"] for item in started.runner["segments"])
        == ASSIGNMENT_SEGMENTS
    )
    assert "create_upload_session" in started.available_commands
    content = b"assignment-audio"
    declaration = {
        "part_number": 1,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }

    with pytest.raises(AudioAssessmentError) as locked:
        await runtime.create_upload_session(
            organization_id="org-1",
            learner_id="learner-1",
            attempt_id="attempt-assignment",
            expected_version=started.version,
            payload=CreateUploadSessionInput(
                segment_id="commitment",
                original_filename="commitment.webm",
                content_type="audio/webm",
                size_bytes=len(content),
                duration_seconds=3,
                manifest_sha256=_hash([declaration]),
                parts=(declaration,),
            ),
            idempotency_key="skip-segments",
        )
    assert locked.value.code == "[AUDIO_ASSIGNMENT_SEGMENT_LOCKED]"

    discovery = await runtime.create_upload_session(
        organization_id="org-1",
        learner_id="learner-1",
        attempt_id="attempt-assignment",
        expected_version=started.version,
        payload=CreateUploadSessionInput(
            segment_id="discovery",
            original_filename="discovery.webm",
            content_type="audio/webm",
            size_bytes=len(content),
            duration_seconds=3,
            manifest_sha256=_hash([declaration]),
            parts=(declaration,),
        ),
        idempotency_key="discovery-upload",
    )
    assert "create_upload_session" not in discovery.available_commands
    assert "finalize_upload" in discovery.available_commands

# Newcomer Training Activity Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Do not dispatch subagents; the user explicitly requires single-agent inline execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unpublished fixed newcomer-training prototype with one configurable `Path → Phase → Module → Activity` orchestration system whose existing activity types can be composed without source changes.

**Architecture:** Store the complete path as an immutable, validated revision aggregate using the existing sales-trainer revision authority, and add enrollment plus unified activity-attempt persistence. A closed activity-handler registry owns execution mechanics; business modules and scenarios remain data. Replace the fixed admin card wall and learner journey page with a focused path editor and next-action learner experience.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, pytest; Next.js 16, React 19, TypeScript 5, Tailwind CSS, Vitest, Playwright.

## Global Constraints

- Treat the current newcomer-training path, compatibility structures, seed configuration, and test results as disposable prototype data.
- Perform one direct replacement. Do not build V1/V2 dual-read, dual-write, compatibility adapters, fallback projections, or legacy route redirects.
- Keep one logical path: `resource_type="newcomer_training_path_orchestration"`, `logical_id="default"`.
- Reuse `SalesTrainerAssetRevision` and `SalesTrainerAssetActiveRevision` as the physical implementation of logical `TrainingPath` and `TrainingPathRevision`; do not create a duplicate active-pointer authority.
- Reuse LearningContent, ExamPaper, material/version, audio scoring, AI Coach, StepAudio realtime, audit, and revision engines.
- Do not add a frontend or backend dependency. Implement outline reordering with native drag events plus keyboard-accessible move buttons.
- Existing activity types are exactly `lesson`, `quiz`, `audio_assessment`, `realtime_roleplay`, `ai_coach`, and `assignment`.
- Business labels such as PPT, Demo, business etiquette, FAQ, and product names must not appear in backend branching or type unions.
- Config must never contain arbitrary executable code, component names, URLs, or API routes.
- Learners read only published revisions. First access creates an enrollment pinned to that revision.
- Historical attempts freeze activity and result snapshots. Regrade appends evidence; it never overwrites history.
- Drafts may be incomplete; publish must fail closed with field-addressable business-language issues.
- Backend permissions, object scope, idempotency, audit events, structured errors, and secret-safe logging are mandatory.
- Ordinary UI must not show database IDs, raw JSON, Prompt, traceId, runtime binding, internal enums, or internal error codes.
- Follow CodeGraph-first discovery before changing shared functions and run affected tests after every task.
- Preserve unrelated working-tree changes, especially `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`.
- Design authority: `docs/superpowers/specs/2026-07-12-newcomer-training-activity-orchestration-design.md`.

---

## Target File Structure

### Backend orchestration package

```text
backend/src/sales_trainer/orchestration/
├── __init__.py                    # Public orchestration exports only
├── contracts.py                   # Pydantic discriminated unions and API DTOs
├── errors.py                      # Typed orchestration errors
├── graph.py                       # Ordering, dependency and completion validation
├── repository.py                  # Enrollment and attempt persistence
├── revision_service.py            # Draft, validate, publish, restore
├── resource_validator.py          # Published asset and runtime readiness validation
├── registry.py                    # Closed ActivityHandler registry
├── completion.py                  # Activity/module/phase/path state aggregation
├── journey_service.py             # Learner/admin journey projection
├── admin_api.py                   # Canonical admin orchestration API
├── learner_api.py                 # Canonical learner orchestration API
├── assignment_storage.py          # Assignment file storage seam
└── activities/
    ├── __init__.py
    ├── base.py                     # Handler protocol and execution context
    ├── lesson.py
    ├── quiz.py
    ├── audio_assessment.py
    ├── realtime_roleplay.py
    ├── ai_coach.py
    └── assignment.py
```

### Frontend feature structure

```text
web/src/components/admin/newcomer-training/
├── path-editor.tsx
├── path-outline.tsx
├── path-inspector.tsx
├── path-preview.tsx
├── path-validation-panel.tsx
├── resource-picker-drawer.tsx
└── activity-editors/
    ├── lesson-editor.tsx
    ├── quiz-editor.tsx
    ├── audio-assessment-editor.tsx
    ├── realtime-roleplay-editor.tsx
    ├── ai-coach-editor.tsx
    └── assignment-editor.tsx

web/src/components/newcomer-training/
├── journey-home.tsx
├── journey-outline.tsx
├── module-detail.tsx
├── activity-shell.tsx
└── activity-runners/
    ├── lesson-runner.tsx
    ├── quiz-runner.tsx
    ├── audio-assessment-runner.tsx
    ├── realtime-roleplay-runner.tsx
    ├── ai-coach-runner.tsx
    └── assignment-runner.tsx

web/src/lib/newcomer-training/
├── editor-state.ts
├── activity-registry.ts
└── presentation.ts
```

The page files remain composition roots only:

```text
web/src/app/admin/newcomer-training/path/page.tsx
web/src/app/(dashboard)/newcomer-training/page.tsx
web/src/app/(dashboard)/newcomer-training/modules/[moduleId]/page.tsx
web/src/app/(dashboard)/newcomer-training/activities/[activityId]/page.tsx
```

---

### Task 1: Define the orchestration contract and graph validator

**Files:**
- Create: `backend/src/sales_trainer/orchestration/__init__.py`
- Create: `backend/src/sales_trainer/orchestration/contracts.py`
- Create: `backend/src/sales_trainer/orchestration/errors.py`
- Create: `backend/src/sales_trainer/orchestration/graph.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_contracts.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_graph.py`

**Interfaces:**
- Produces: `TrainingPathPayload`, `PhaseConfig`, `ModuleConfig`, `ActivityConfig`, six typed activity configs, `PathIssue`, `validate_path_graph(payload) -> tuple[PathIssue, ...]`.
- Consumes: no new application interfaces.

- [x] **Step 1: Write failing contract tests**

```python
from pydantic import ValidationError
import pytest

from sales_trainer.orchestration.contracts import TrainingPathPayload


def test_should_accept_three_product_modules_without_business_key_enum() -> None:
    payload = TrainingPathPayload.model_validate({
        "title": "新人训练路径",
        "phases": [{
            "phase_id": "phase-product",
            "title": "产品能力",
            "order_index": 1,
            "required": True,
            "modules": [
                {
                    "module_id": f"module-product-{name}",
                    "title": f"产品 {name}",
                    "order_index": index,
                    "required": True,
                    "completion_policy": {"mode": "all_required"},
                    "activities": [{
                        "activity_id": f"activity-product-{name}-lesson",
                        "type": "lesson",
                        "title": "学习资料",
                        "order_index": 1,
                        "required": True,
                        "config": {"learning_content_id": f"content-{name}"},
                    }],
                }
                for index, name in enumerate(("a", "b", "c"), start=1)
            ],
        }],
    })

    assert [module.title for module in payload.phases[0].modules] == [
        "产品 a", "产品 b", "产品 c"
    ]


def test_should_reject_unknown_activity_type() -> None:
    with pytest.raises(ValidationError):
        TrainingPathPayload.model_validate({
            "title": "新人训练路径",
            "phases": [{
                "phase_id": "phase-1",
                "title": "阶段",
                "order_index": 1,
                "required": True,
                "modules": [{
                    "module_id": "module-1",
                    "title": "模块",
                    "order_index": 1,
                    "required": True,
                    "completion_policy": {"mode": "all_required"},
                    "activities": [{
                        "activity_id": "activity-1",
                        "type": "arbitrary_script",
                        "title": "非法活动",
                        "order_index": 1,
                        "required": True,
                        "config": {"script": "rm -rf /"},
                    }],
                }],
            }],
        })
```

- [x] **Step 2: Run contract tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_contracts.py -q`

Expected: collection fails with `ModuleNotFoundError: sales_trainer.orchestration`.

- [x] **Step 3: Implement the discriminated contract**

Add these exact public shapes in `contracts.py`:

```python
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

ActivityType = Literal[
    "lesson", "quiz", "audio_assessment",
    "realtime_roleplay", "ai_coach", "assignment",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LessonConfig(StrictModel):
    learning_content_id: str = Field(min_length=1, max_length=36)
    completion_mode: Literal["all_chapters", "learner_confirmed"] = "all_chapters"


class QuizConfig(StrictModel):
    exam_paper_id: str = Field(min_length=1, max_length=36)
    pass_score: float = Field(ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)


class AudioAssessmentConfig(StrictModel):
    scoring_rubric_id: str = Field(min_length=1, max_length=36)
    material_id: str | None = Field(default=None, min_length=1, max_length=36)
    pass_score: float = Field(ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)


class RealtimeRoleplayConfig(StrictModel):
    practice_template_id: str = Field(min_length=1, max_length=36)
    runtime_profile_id: str = Field(min_length=1, max_length=120)
    completion_mode: Literal["session_completed", "scored"] = "session_completed"


class AiCoachActivityConfig(StrictModel):
    coach_profile_id: str = Field(min_length=1, max_length=120)
    completion_mode: Literal["session_completed", "goal_reached"] = "session_completed"


class AssignmentConfig(StrictModel):
    submission_type: Literal["text", "file", "text_or_file"]
    review_mode: Literal["automatic_complete", "manual_review"]
    max_file_size_bytes: int = Field(default=10_485_760, ge=1, le=52_428_800)


class ActivityBase(StrictModel):
    activity_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    order_index: int = Field(ge=1)
    required: bool = True
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    prerequisites: list[str] = Field(default_factory=list, max_length=50)


class LessonActivity(ActivityBase):
    type: Literal["lesson"]
    config: LessonConfig


class QuizActivity(ActivityBase):
    type: Literal["quiz"]
    config: QuizConfig


class AudioAssessmentActivity(ActivityBase):
    type: Literal["audio_assessment"]
    config: AudioAssessmentConfig


class RealtimeRoleplayActivity(ActivityBase):
    type: Literal["realtime_roleplay"]
    config: RealtimeRoleplayConfig


class AiCoachActivity(ActivityBase):
    type: Literal["ai_coach"]
    config: AiCoachActivityConfig


class AssignmentActivity(ActivityBase):
    type: Literal["assignment"]
    config: AssignmentConfig


ActivityConfig = Annotated[
    LessonActivity | QuizActivity | AudioAssessmentActivity |
    RealtimeRoleplayActivity | AiCoachActivity | AssignmentActivity,
    Field(discriminator="type"),
]


class CompletionPolicy(StrictModel):
    mode: Literal["all_required", "at_least_count"]
    activity_ids: list[str] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=1)


class ModuleConfig(StrictModel):
    module_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    order_index: int = Field(ge=1)
    required: bool = True
    estimated_minutes: int | None = Field(default=None, ge=1, le=10_080)
    audience_rule: dict[str, list[str]] = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list, max_length=50)
    completion_policy: CompletionPolicy
    activities: list[ActivityConfig] = Field(default_factory=list, max_length=200)


class PhaseConfig(StrictModel):
    phase_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    order_index: int = Field(ge=1)
    required: bool = True
    modules: list[ModuleConfig] = Field(default_factory=list, max_length=100)


class TrainingPathPayload(StrictModel):
    schema_version: Literal["newcomer_training_orchestration_v1"] = (
        "newcomer_training_orchestration_v1"
    )
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    phases: list[PhaseConfig] = Field(default_factory=list, max_length=50)
```

Add typed errors in `errors.py`:

```python
class NewcomerOrchestrationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PathValidationError(NewcomerOrchestrationError):
    def __init__(self, issues: tuple[PathIssue, ...]) -> None:
        self.issues = issues
        super().__init__(
            "[NEWCOMER_PATH_VALIDATION_FAILED]",
            "训练路径还有需要处理的配置问题。",
            422,
        )
```

- [x] **Step 4: Write graph-validation tests**

```python
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.graph import validate_path_graph


def test_should_report_duplicate_order_and_cycle_with_field_paths() -> None:
    payload = TrainingPathPayload.model_validate(path_payload_with_cycle())

    issues = validate_path_graph(payload)

    assert {(issue.code, issue.object_id) for issue in issues} == {
        ("duplicate_order_index", "module-b"),
        ("cyclic_prerequisite", "activity-a"),
        ("cyclic_prerequisite", "activity-b"),
    }


def test_should_require_at_least_count_membership() -> None:
    payload = TrainingPathPayload.model_validate(path_payload_with_invalid_count())

    issues = validate_path_graph(payload)

    assert issues[0].code == "completion_policy_invalid"
    assert issues[0].field_path.endswith("completion_policy.activity_ids")
```

- [x] **Step 5: Implement deterministic graph validation**

Add in `graph.py`:

```python
from dataclasses import dataclass

from .contracts import TrainingPathPayload


@dataclass(frozen=True, slots=True)
class PathIssue:
    code: str
    message: str
    object_id: str
    field_path: str
    severity: str = "error"


def validate_path_graph(payload: TrainingPathPayload) -> tuple[PathIssue, ...]:
    issues: list[PathIssue] = []
    # Build one ID index across phases/modules/activities, reject duplicates,
    # validate unique sibling order_index, validate prerequisite existence and
    # topological order, then validate completion-policy membership and count.
    # Return sorted issues by field_path/code/object_id for stable API and tests.
    return tuple(sorted(issues, key=lambda item: (item.field_path, item.code, item.object_id)))
```

Implement the body with explicit ID indexes and Kahn topological sorting; do not use recursion or infer dependencies from order alone.

- [x] **Step 6: Run focused tests**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_contracts.py tests/unit/test_newcomer_orchestration_graph.py -q`

Expected: all tests pass.

- [x] **Step 7: Commit**

```bash
git add backend/src/sales_trainer/orchestration backend/tests/unit/test_newcomer_orchestration_contracts.py backend/tests/unit/test_newcomer_orchestration_graph.py
git commit -m "feat(newcomer): define activity orchestration contract"
```

---

### Task 2: Add enrollment and unified attempt persistence

**Files:**
- Modify: `backend/src/sales_trainer/models.py`
- Create: `backend/src/sales_trainer/orchestration/repository.py`
- Create: `backend/alembic/versions/20260712_1300_092_newcomer_activity_orchestration.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_repository.py`
- Test: `backend/tests/integration/test_newcomer_orchestration_migration.py`

**Interfaces:**
- Consumes: `ActivityConfig` from Task 1.
- Produces: `NewcomerTrainingEnrollment`, `NewcomerTrainingActivityAttempt`, `EnrollmentRepository`, `AttemptRepository`.

- [x] **Step 1: Write failing repository tests**

```python
@pytest.mark.asyncio
async def test_should_pin_first_enrollment_to_published_revision(test_db, test_user):
    repository = EnrollmentRepository(test_db)

    first = await repository.get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id="revision-1",
    )
    second = await repository.get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id="revision-2",
    )

    assert second.enrollment_id == first.enrollment_id
    assert second.path_revision_id == "revision-1"


@pytest.mark.asyncio
async def test_should_make_attempt_creation_idempotent(test_db, enrollment):
    repository = AttemptRepository(test_db)
    activity_snapshot = {"activity_id": "activity-a", "type": "quiz"}

    first = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot=activity_snapshot,
        client_token="client-token-1",
    )
    second = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot=activity_snapshot,
        client_token="client-token-1",
    )

    assert second.attempt_id == first.attempt_id
```

- [x] **Step 2: Run repository tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_repository.py -q`

Expected: import fails for the new models/repositories.

- [x] **Step 3: Add ORM models and migration**

Add ORM columns matching these contracts:

```python
class NewcomerTrainingEnrollment(Base):
    __tablename__ = "newcomer_training_enrollments"
    enrollment_id = Column(String(36), primary_key=True, default=_uuid)
    learner_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    path_id = Column(String(80), nullable=False, default="default")
    path_revision_id = Column(
        String(36), ForeignKey("sales_trainer_asset_revisions.revision_id"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="active", index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class NewcomerTrainingActivityAttempt(Base):
    __tablename__ = "newcomer_training_activity_attempts"
    attempt_id = Column(String(36), primary_key=True, default=_uuid)
    enrollment_id = Column(
        String(36), ForeignKey("newcomer_training_enrollments.enrollment_id"), nullable=False, index=True
    )
    path_revision_id = Column(
        String(36), ForeignKey("sales_trainer_asset_revisions.revision_id"), nullable=False, index=True
    )
    activity_id = Column(String(80), nullable=False, index=True)
    activity_type = Column(String(40), nullable=False, index=True)
    attempt_no = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="not_started", index=True)
    score = Column(Numeric(8, 2), nullable=True)
    max_score = Column(Numeric(8, 2), nullable=True)
    passed = Column(Boolean, nullable=True)
    evidence_type = Column(String(50), nullable=True)
    evidence_id = Column(String(120), nullable=True)
    client_token = Column(String(100), nullable=False)
    activity_snapshot = Column(JSON, nullable=False)
    result_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)
```

The migration must create check constraints for the six activity types, attempt statuses, and enrollment statuses; unique indexes for `(learner_id, path_id, status)` active enrollment, `(enrollment_id, activity_id, attempt_no)`, and `client_token`; and an index for `(evidence_type, evidence_id)`.

- [x] **Step 4: Implement repositories**

```python
class EnrollmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create(
        self, *, learner_id: str, path_id: str, path_revision_id: str
    ) -> NewcomerTrainingEnrollment:
        existing = await self.active_for_learner(learner_id=learner_id, path_id=path_id)
        if existing is not None:
            return existing
        enrollment = NewcomerTrainingEnrollment(
            learner_id=learner_id,
            path_id=path_id,
            path_revision_id=path_revision_id,
            status="active",
        )
        self._db.add(enrollment)
        await self._db.flush()
        return enrollment

    async def active_for_learner(
        self, *, learner_id: str, path_id: str
    ) -> NewcomerTrainingEnrollment | None:
        return await self._db.scalar(
            select(NewcomerTrainingEnrollment).where(
                NewcomerTrainingEnrollment.learner_id == learner_id,
                NewcomerTrainingEnrollment.path_id == path_id,
                NewcomerTrainingEnrollment.status == "active",
            )
        )


class AttemptRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        enrollment_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        activity_snapshot: dict[str, object],
        client_token: str,
    ) -> NewcomerTrainingActivityAttempt:
        existing = await self._db.scalar(
            select(NewcomerTrainingActivityAttempt).where(
                NewcomerTrainingActivityAttempt.client_token == client_token
            )
        )
        if existing is not None:
            return existing
        latest_no = await self._db.scalar(
            select(func.max(NewcomerTrainingActivityAttempt.attempt_no)).where(
                NewcomerTrainingActivityAttempt.enrollment_id == enrollment_id,
                NewcomerTrainingActivityAttempt.activity_id == activity_id,
            )
        )
        attempt = NewcomerTrainingActivityAttempt(
            enrollment_id=enrollment_id,
            path_revision_id=path_revision_id,
            activity_id=activity_id,
            activity_type=activity_type,
            attempt_no=int(latest_no or 0) + 1,
            client_token=client_token,
            activity_snapshot=activity_snapshot,
        )
        self._db.add(attempt)
        await self._db.flush()
        return attempt

    async def latest_for_activity(
        self, *, enrollment_id: str, activity_id: str
    ) -> NewcomerTrainingActivityAttempt | None:
        return await self._db.scalar(
            select(NewcomerTrainingActivityAttempt)
            .where(
                NewcomerTrainingActivityAttempt.enrollment_id == enrollment_id,
                NewcomerTrainingActivityAttempt.activity_id == activity_id,
            )
            .order_by(NewcomerTrainingActivityAttempt.attempt_no.desc())
            .limit(1)
        )

    async def attach_evidence(
        self,
        *,
        attempt_id: str,
        evidence_type: str,
        evidence_id: str,
        status: str,
    ) -> NewcomerTrainingActivityAttempt:
        attempt = await self._db.get(NewcomerTrainingActivityAttempt, attempt_id)
        if attempt is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_ATTEMPT_NOT_FOUND]", "训练记录不存在。", 404
            )
        attempt.evidence_type = evidence_type
        attempt.evidence_id = evidence_id
        attempt.status = status
        await self._db.flush()
        return attempt
```

Use `select()` and `with_for_update()` where supported. Catch unique-key races, rollback only the failed savepoint, and return the already-created row for the same client token.

- [x] **Step 5: Run migration and persistence tests**

Run:

```bash
cd backend
./.venv/bin/alembic upgrade head
./.venv/bin/pytest tests/unit/test_newcomer_orchestration_repository.py tests/integration/test_newcomer_orchestration_migration.py -q
```

Expected: migration reaches `20260712_1300_092`; all focused tests pass.

- [x] **Step 6: Commit**

```bash
git add backend/src/sales_trainer/models.py backend/src/sales_trainer/orchestration/repository.py backend/alembic/versions/20260712_1300_092_newcomer_activity_orchestration.py backend/tests/unit/test_newcomer_orchestration_repository.py backend/tests/integration/test_newcomer_orchestration_migration.py
git commit -m "feat(newcomer): persist enrollments and activity attempts"
```

---

### Task 3: Implement draft, publish, restore, resource validation, and permissions

**Files:**
- Modify: `backend/src/sales_trainer/orchestration/contracts.py`
- Create: `backend/src/sales_trainer/orchestration/resource_validator.py`
- Create: `backend/src/sales_trainer/orchestration/revision_service.py`
- Create: `backend/src/sales_trainer/orchestration/admin_api.py`
- Modify: `backend/src/sales_trainer/permissions.py`
- Modify: `backend/src/sales_trainer/router_registration.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_revision_service.py`
- Test: `backend/tests/integration/test_newcomer_orchestration_admin_api.py`

**Interfaces:**
- Consumes: `TrainingPathPayload`, `PathIssue`, `validate_path_graph`.
- Produces: `TrainingPathConfigResponse`, `PathValidationResponse`, `TrainingPathRevisionService`, `PathResourceValidator`, `admin_router`.

- [x] **Step 1: Write failing revision-service tests**

```python
@pytest.mark.asyncio
async def test_should_allow_incomplete_draft_but_block_publish(test_db, admin_user):
    service = TrainingPathRevisionService(test_db)
    payload = valid_path_payload().model_copy(update={
        "phases": [phase_with_missing_quiz_paper()]
    })

    draft = await service.save_draft(payload=payload, actor=admin_user, reason="编辑产品训练")
    preview = await service.validate_draft()

    assert draft.status == "working"
    assert preview.can_publish is False
    assert preview.issues[0].field_path.endswith("config.exam_paper_id")


@pytest.mark.asyncio
async def test_should_restore_history_as_new_draft_not_move_active_pointer(test_db, admin_user):
    service = TrainingPathRevisionService(test_db)
    first = await publish_payload(service, admin_user, path_title="版本一")
    second = await publish_payload(service, admin_user, path_title="版本二")

    restored = await service.restore_as_draft(
        revision_id=str(first.revision_id), actor=admin_user, reason="恢复版本一"
    )
    active = await service.active_revision()

    assert active.revision_id == second.revision_id
    assert restored.status == "working"
    assert restored.payload_json["title"] == "版本一"
```

- [x] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_revision_service.py -q`

Expected: imports fail for the new services.

- [x] **Step 3: Implement resource validation**

`PathResourceValidator.validate(payload)` must return `PathIssue` values and perform batched reads:

```python
class PathResourceValidator:
    async def validate(self, payload: TrainingPathPayload) -> tuple[PathIssue, ...]:
        # lesson: published LearningContent with at least one chapter
        # quiz: published ExamPaper with at least one published question revision
        # audio: published scoring rubric; optional material must have current published version
        # realtime: published PracticeTemplate + enabled runtime profile + provider readiness
        # ai_coach: existing enabled coach profile and governed prompt/model configuration
        # assignment: declared submission/review modes only; no external asset required
        return tuple(sorted(issues, key=lambda issue: (issue.field_path, issue.code)))
```

Use one query per resource type, never one query per activity. Error messages must be Chinese business copy such as `产品 A 小测没有已发布考卷`.

Add the admin DTOs to `contracts.py`:

```python
class PathValidationResponse(StrictModel):
    can_publish: bool
    issues: list[PathIssueResponse] = Field(default_factory=list)


class TrainingPathConfigResponse(StrictModel):
    active_revision_id: str | None
    active_revision_no: int | None
    working_revision_id: str | None
    payload: TrainingPathPayload
    validation: PathValidationResponse | None = None
```

`PathIssueResponse` mirrors `PathIssue` fields exactly. Construct these DTOs inside the revision service; do not add ORM-aware classmethods to transport models.

- [x] **Step 4: Implement revision service**

```python
PATH_RESOURCE_TYPE = "newcomer_training_path_orchestration"
PATH_LOGICAL_ID = "default"


class TrainingPathRevisionService:
    async def active_revision(self) -> SalesTrainerAssetRevision | None:
        return await self._revisions.active_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )

    async def working_revision(self) -> SalesTrainerAssetRevision | None:
        return await self._revisions.latest_working_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )

    async def get_config(self) -> TrainingPathConfigResponse:
        active = await self.active_revision()
        working = await self.working_revision()
        source = working or active
        payload = (
            TrainingPathPayload.model_validate(source.payload_json)
            if source is not None
            else TrainingPathPayload(title="新人训练路径", phases=[])
        )
        return TrainingPathConfigResponse(
            active_revision_id=str(active.revision_id) if active else None,
            active_revision_no=int(active.revision_no) if active else None,
            working_revision_id=str(working.revision_id) if working else None,
            payload=payload,
        )
    async def save_draft(
        self, *, payload: TrainingPathPayload, actor: User, reason: str, trace_id: str | None = None
    ) -> SalesTrainerAssetRevision:
        graph_issues = validate_path_graph(payload)
        if graph_issues:
            raise PathValidationError(graph_issues)
        return await self._revisions.save_working_revision(
            resource_type=PATH_RESOURCE_TYPE,
            logical_id=PATH_LOGICAL_ID,
            payload=payload.model_dump(mode="json"),
            actor=actor,
            change_class="semantic",
            reason=reason,
            trace_id=trace_id,
        )

    async def validate_draft(self) -> PathValidationResponse:
        working = await self.working_revision()
        if working is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_DRAFT_MISSING]", "当前没有可检查的草稿。", 404
            )
        payload = TrainingPathPayload.model_validate(working.payload_json)
        issues = (*validate_path_graph(payload), *await self._resources.validate(payload))
        return PathValidationResponse(can_publish=not issues, issues=list(issues))
    async def publish(
        self, *, actor: User, reason: str, trace_id: str | None = None
    ) -> AssetPublishResult:
        preview = await self.validate_draft()
        if not preview.can_publish:
            raise PathValidationError(tuple(preview.issues))
        working = await self.working_revision()
        if working is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_DRAFT_MISSING]", "当前没有可发布的草稿。", 404
            )
        return await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
    async def restore_as_draft(
        self, *, revision_id: str, actor: User, reason: str, trace_id: str | None = None
    ) -> SalesTrainerAssetRevision:
        source = await self._revisions.revision_by_id(revision_id)
        if (
            source is None
            or source.resource_type != PATH_RESOURCE_TYPE
            or source.logical_id != PATH_LOGICAL_ID
        ):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_REVISION_NOT_FOUND]", "训练路径历史版本不存在。", 404
            )
        payload = TrainingPathPayload.model_validate(source.payload_json)
        return await self.save_draft(
            payload=payload, actor=actor, reason=reason, trace_id=trace_id
        )
```

`save_draft` validates Pydantic and graph shape but permits resource issues. `publish` rejects any graph or resource issue before calling the existing revision publish authority. Record operation-log actions `newcomer_path.draft_saved`, `newcomer_path.published`, and `newcomer_path.revision_restored`.

- [x] **Step 5: Add explicit permission helpers and admin API**

Add helpers:

```python
def can_manage_newcomer_training_path(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_content_admin(user)


def can_publish_newcomer_training_path(user: User) -> bool:
    return is_sales_trainer_admin(user)


def can_learn_newcomer_training_path(user: User) -> bool:
    return can_enter_sales_trainer_learning_path(user)
```

Expose exact routes under `APIRouter(prefix="/admin/newcomer-training/path")`:

```text
GET    /
PUT    /draft
DELETE /draft
POST   /validate
POST   /publish
GET    /revisions
POST   /revisions/{revision_id}/restore
GET    /activity-types
```

Require manage permission for reads/draft, publish permission for publish, and write actor/reason/request ID to audit records.

- [x] **Step 6: Run service and API tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_newcomer_orchestration_revision_service.py tests/integration/test_newcomer_orchestration_admin_api.py -q
```

Expected: all tests pass, including 403 object-capability cases and business-language issue payloads.

- [x] **Step 7: Commit**

```bash
git add backend/src/sales_trainer/orchestration/contracts.py backend/src/sales_trainer/orchestration/resource_validator.py backend/src/sales_trainer/orchestration/revision_service.py backend/src/sales_trainer/orchestration/admin_api.py backend/src/sales_trainer/permissions.py backend/src/sales_trainer/router_registration.py backend/tests/unit/test_newcomer_orchestration_revision_service.py backend/tests/integration/test_newcomer_orchestration_admin_api.py
git commit -m "feat(newcomer): govern activity path revisions"
```

---

### Task 4: Implement the handler registry, completion engine, and attempt projection

**Files:**
- Create: `backend/src/sales_trainer/orchestration/activities/__init__.py`
- Create: `backend/src/sales_trainer/orchestration/activities/base.py`
- Create: `backend/src/sales_trainer/orchestration/registry.py`
- Create: `backend/src/sales_trainer/orchestration/completion.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_registry.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_completion.py`

**Interfaces:**
- Consumes: contracts and repositories from Tasks 1–2.
- Produces: `ActivityExecutionContext`, `ActivityProjection`, `ActivityHandler`, `ActivityTypeRegistry`, `aggregate_path_progress`.

- [ ] **Step 1: Write failing registry and completion tests**

```python
def test_should_register_exactly_six_handlers() -> None:
    registry = build_activity_registry(fake_dependencies())
    assert registry.type_keys == (
        "lesson", "quiz", "audio_assessment",
        "realtime_roleplay", "ai_coach", "assignment",
    )


def test_should_complete_module_when_all_required_activities_complete() -> None:
    module = module_config(required_activity_ids=("lesson", "quiz"), optional_ids=("coach",))
    states = {
        "lesson": activity_projection("completed"),
        "quiz": activity_projection("passed"),
        "coach": activity_projection("not_started"),
    }

    result = aggregate_module_progress(module, states)

    assert result.completed is True
    assert result.completed_count == 2
    assert result.total_required == 2
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_registry.py tests/unit/test_newcomer_orchestration_completion.py -q`

Expected: new interfaces are missing.

- [ ] **Step 3: Define the handler protocol**

```python
@dataclass(frozen=True, slots=True)
class ActivityExecutionContext:
    learner_id: str
    enrollment_id: str
    path_revision_id: str
    phase_id: str
    module_id: str
    activity: ActivityConfig


@dataclass(frozen=True, slots=True)
class ActivityProjection:
    activity_id: str
    activity_type: str
    status: str
    completed: bool
    score: float | None
    max_score: float | None
    passed: bool | None
    next_action: dict[str, object] | None
    message: str | None


class ActivityHandler(Protocol):
    type_key: str
    async def validate_config(self, activity: ActivityConfig) -> tuple[PathIssue, ...]:
        raise NotImplementedError
    async def check_access(self, context: ActivityExecutionContext) -> None:
        raise NotImplementedError
    async def project(self, context: ActivityExecutionContext) -> ActivityProjection:
        raise NotImplementedError
    async def refresh_attempt(
        self, context: ActivityExecutionContext, attempt: NewcomerTrainingActivityAttempt
    ) -> NewcomerTrainingActivityAttempt:
        raise NotImplementedError
```

- [ ] **Step 4: Implement closed registry and aggregation**

`ActivityTypeRegistry.handler_for(type_key)` must raise `[NEWCOMER_ACTIVITY_TYPE_UNSUPPORTED]` for unknown values and must not dynamically import from config. `aggregate_activity/module/phase/path_progress` must treat `passed`, `completed`, and configured `submitted` completion as handler-owned results; required failures block, optional failures do not.

- [ ] **Step 5: Run tests**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_registry.py tests/unit/test_newcomer_orchestration_completion.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/sales_trainer/orchestration/activities backend/src/sales_trainer/orchestration/registry.py backend/src/sales_trainer/orchestration/completion.py backend/tests/unit/test_newcomer_orchestration_registry.py backend/tests/unit/test_newcomer_orchestration_completion.py
git commit -m "feat(newcomer): add activity handler registry"
```

---

### Task 5: Implement lesson and quiz activities

**Files:**
- Create: `backend/src/sales_trainer/orchestration/activities/lesson.py`
- Create: `backend/src/sales_trainer/orchestration/activities/quiz.py`
- Modify: `backend/src/sales_trainer/services/exam_paper_service.py`
- Modify: `backend/src/sales_trainer/services/curriculum_practice_adapter.py`
- Create: `backend/tests/unit/test_newcomer_lesson_activity.py`
- Create: `backend/tests/unit/test_newcomer_quiz_activity.py`

**Interfaces:**
- Consumes: `ActivityHandler`, repositories, LearningProgress adapter, ExamPaper service.
- Produces: `LessonActivityHandler`, `QuizActivityHandler`, activity-aware paper submission.

- [ ] **Step 1: Write failing lesson and quiz tests**

```python
@pytest.mark.asyncio
async def test_should_complete_lesson_when_all_published_chapters_are_read(test_db, learner, lesson_context):
    await mark_all_chapters_complete(test_db, learner, lesson_context.activity.config.learning_content_id)

    projection = await LessonActivityHandler(test_db).project(lesson_context)

    assert projection.status == "completed"
    assert projection.completed is True


@pytest.mark.asyncio
async def test_should_submit_quiz_from_activity_without_business_module_key(test_db, learner, quiz_context):
    handler = QuizActivityHandler(test_db)

    attempt = await handler.submit(
        quiz_context,
        answers=correct_answers(),
        client_token="quiz-activity-token",
        actor=learner,
    )

    assert attempt.evidence_type == "quiz_attempt"
    assert attempt.passed is True
    assert attempt.activity_snapshot["activity_id"] == quiz_context.activity.activity_id
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_lesson_activity.py tests/unit/test_newcomer_quiz_activity.py -q`

Expected: handlers do not exist.

- [ ] **Step 3: Implement lesson handler**

The handler must load the published LearningContent through `LearningProgressAdapter`, reject archived/draft content, expose chapter progress, and create/update one unified attempt when completion is reached.

```python
class LessonActivityHandler:
    type_key = "lesson"

    async def mark_chapter_complete(
        self,
        context: ActivityExecutionContext,
        *,
        chapter_id: str,
        actor: User,
        client_token: str,
    ) -> ActivityProjection:
        await self._progress.complete_chapter(
            user_id=context.learner_id,
            content_id=context.activity.config.learning_content_id,
            chapter_id=chapter_id,
        )
        await self._attempts.create(
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            activity_snapshot=context.activity.model_dump(mode="json"),
            client_token=client_token,
        )
        return await self.project(context)
```

For `learner_confirmed`, expose a confirm action and complete the attempt idempotently without writing chapter progress.

- [ ] **Step 4: Refactor quiz submission around activity context**

Add an optional execution context to the paper service:

```python
async def submit_paper_attempt(
    self,
    payload: PaperAttemptCreate,
    *,
    actor: User,
    execution_context: ActivityExecutionContext | None = None,
) -> SalesTrainerQuizAttempt:
```

When context is present, validate the paper ID and prerequisites against the pinned activity revision, skip `ArticleExamPrerequisiteService`, freeze the activity context into the answer attempt context, then attach the resulting quiz evidence to the unified attempt. Keep non-newcomer callers functional without reading old newcomer path config.

- [ ] **Step 5: Run focused and affected tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_newcomer_lesson_activity.py tests/unit/test_newcomer_quiz_activity.py tests/unit/test_newcomer_training_path_papers.py -q
```

Expected: activity tests pass; generic paper tests remain green.

- [ ] **Step 6: Commit**

```bash
git add backend/src/sales_trainer/orchestration/activities/lesson.py backend/src/sales_trainer/orchestration/activities/quiz.py backend/src/sales_trainer/services/exam_paper_service.py backend/src/sales_trainer/services/curriculum_practice_adapter.py backend/tests/unit/test_newcomer_lesson_activity.py backend/tests/unit/test_newcomer_quiz_activity.py
git commit -m "feat(newcomer): execute lesson and quiz activities"
```

---

### Task 6: Implement audio assessment and assignment activities

**Files:**
- Create: `backend/src/sales_trainer/orchestration/activities/audio_assessment.py`
- Create: `backend/src/sales_trainer/orchestration/activities/assignment.py`
- Create: `backend/src/sales_trainer/orchestration/assignment_storage.py`
- Create: `backend/src/sales_trainer/services/activity_audio_snapshot_service.py`
- Modify: `backend/src/sales_trainer/services/audio_submission_service.py`
- Modify: `backend/src/sales_trainer/schemas.py`
- Test: `backend/tests/unit/test_newcomer_audio_assessment_activity.py`
- Test: `backend/tests/unit/test_newcomer_assignment_activity.py`
- Test: `backend/tests/unit/test_sales_trainer_services.py`

**Interfaces:**
- Consumes: audio submission/scoring pipeline, material and scoring-rubric assets, attempt repository.
- Produces: activity-context audio submission and assignment submission.

- [ ] **Step 1: Write failing audio activity test**

```python
@pytest.mark.asyncio
async def test_should_freeze_audio_rubric_and_material_without_sales_trainer_unit(
    test_db, learner, audio_context
):
    handler = AudioAssessmentActivityHandler(test_db)

    result = await handler.submit_file(
        audio_context,
        file=fake_wav_upload(),
        confirmed_material_version_id=published_material_version_id(),
        client_token="audio-token-1",
        actor=learner,
    )

    submission = await test_db.get(SalesTrainerAudioSubmission, result.evidence_id)
    assert submission.unit_id is None
    assert submission.score_scheme_snapshot["prompt_id"] == audio_context.activity.config.scoring_rubric_id
    assert submission.task_brief_snapshot["activity_id"] == audio_context.activity.activity_id
```

- [ ] **Step 2: Write failing assignment test**

```python
@pytest.mark.asyncio
async def test_should_mark_manual_assignment_as_needs_review(test_db, learner, assignment_context):
    handler = AssignmentActivityHandler(test_db, storage=FakeAssignmentStorage())

    attempt = await handler.submit(
        assignment_context,
        text="完成技术环境搭建",
        file=None,
        client_token="assignment-token-1",
        actor=learner,
    )

    assert attempt.status == "needs_review"
    assert attempt.result_snapshot["text"] == "完成技术环境搭建"
```

- [ ] **Step 3: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_audio_assessment_activity.py tests/unit/test_newcomer_assignment_activity.py -q`

Expected: handlers and snapshot service are missing.

- [ ] **Step 4: Add direct activity audio snapshots**

```python
@dataclass(frozen=True, slots=True)
class ActivityAudioSnapshots:
    material_snapshot: dict[str, object] | None
    score_scheme_snapshot: dict[str, object]
    task_brief_snapshot: dict[str, object]


class ActivityAudioSnapshotService:
    async def freeze(
        self,
        *,
        context: ActivityExecutionContext,
        confirmed_material_version_id: str | None,
    ) -> ActivityAudioSnapshots:
        rubric = await self._published_rubric(context.activity.config.scoring_rubric_id)
        material = await self._published_material_snapshot(
            context.activity.config.material_id,
            confirmed_material_version_id,
        )
        return ActivityAudioSnapshots(
            material_snapshot=material,
            score_scheme_snapshot=self._rubric_snapshot(rubric, context.activity.config.pass_score),
            task_brief_snapshot=self._activity_snapshot(context),
        )
```

Resolve the published scoring rubric by `scoring_rubric_id`; require the confirmed version when a material is configured; freeze revision IDs, threshold, activity ID, enrollment ID, and path revision ID. Never construct a `SalesTrainerUnit` or scenario purpose.

- [ ] **Step 5: Extend audio submission service with activity context**

```python
async def create_submission(
    self,
    payload: AudioSubmissionCreate,
    *,
    actor: User,
    execution_context: ActivityExecutionContext | None = None,
) -> SalesTrainerAudioSubmission:
```

Require exactly one authority: old generic unit caller or new activity context. For activity context, require `unit_id is None`, use frozen activity snapshots, and rely on the existing snapshot-first scoring path. Attach `audio_submission` evidence to the unified attempt before optional processing.

- [ ] **Step 6: Implement assignment storage and handler**

`AssignmentStorage` supports local and configured COS storage, validates allowlisted MIME types (`text/plain`, PDF, common image types, Office documents), normalizes filenames, enforces `max_file_size_bytes`, and returns `{storage_key, filename, content_type, size_bytes, sha256}`. The handler stores only metadata in `result_snapshot`; it never logs file bytes or text contents.

- [ ] **Step 7: Run focused and affected tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_newcomer_audio_assessment_activity.py tests/unit/test_newcomer_assignment_activity.py tests/unit/test_sales_trainer_services.py -q
```

Expected: all focused tests and generic audio submission tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/src/sales_trainer/orchestration/activities/audio_assessment.py backend/src/sales_trainer/orchestration/activities/assignment.py backend/src/sales_trainer/orchestration/assignment_storage.py backend/src/sales_trainer/services/activity_audio_snapshot_service.py backend/src/sales_trainer/services/audio_submission_service.py backend/src/sales_trainer/schemas.py backend/tests/unit/test_newcomer_audio_assessment_activity.py backend/tests/unit/test_newcomer_assignment_activity.py backend/tests/unit/test_sales_trainer_services.py
git commit -m "feat(newcomer): execute audio and assignment activities"
```

---

### Task 7: Refactor AI Coach and StepAudio realtime around activity identity

**Files:**
- Create: `backend/src/sales_trainer/orchestration/activities/ai_coach.py`
- Create: `backend/src/sales_trainer/orchestration/activities/realtime_roleplay.py`
- Modify: `backend/src/sales_trainer/services/ai_coach_chat_runtime.py`
- Modify: `backend/src/sales_trainer/services/ai_coach_session_service.py`
- Modify: `backend/src/sales_trainer/services/realtime_roleplay_start_service.py`
- Test: `backend/tests/unit/test_newcomer_ai_coach_activity.py`
- Test: `backend/tests/unit/test_newcomer_realtime_activity.py`
- Test: `backend/tests/unit/test_sales_trainer_realtime_roleplay_start.py`

**Interfaces:**
- Consumes: existing AI Coach session service and `ExternalSessionStartService`.
- Produces: activity-keyed AI Coach/realtime sessions with frozen external bindings.

- [ ] **Step 1: Write failing AI Coach activity test**

```python
@pytest.mark.asyncio
async def test_should_create_ai_coach_session_from_activity_profile(test_db, learner, coach_context):
    handler = AiCoachActivityHandler(test_db)

    attempt = await handler.start(
        coach_context, actor=learner, client_token="coach-token-1"
    )

    assert attempt.evidence_type == "ai_coach_session"
    assert attempt.activity_snapshot["config"]["coach_profile_id"] == "coach-profile-product"
```

- [ ] **Step 2: Write failing realtime activity test**

```python
@pytest.mark.asyncio
async def test_should_freeze_activity_binding_when_starting_stepaudio(test_db, learner, realtime_context):
    result = await RealtimeRoleplayActivityHandler(test_db).start(
        realtime_context, actor=learner, client_token="realtime-token-1"
    )

    session = await load_practice_session(test_db, result.evidence_id)
    binding = session.voice_policy_snapshot["external_binding"]
    assert binding["owner"] == "newcomer_training"
    assert binding["activity_id"] == realtime_context.activity.activity_id
    assert binding["path_revision_id"] == realtime_context.path_revision_id
```

- [ ] **Step 3: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_ai_coach_activity.py tests/unit/test_newcomer_realtime_activity.py -q`

Expected: new handlers are missing.

- [ ] **Step 4: Remove module-key authority from AI Coach runtime**

Replace `NewcomerPathModuleConfig` lookup with:

```python
def config_from_activity(context: ActivityExecutionContext) -> AiCoachConfig:
    activity = context.activity
    if activity.type != "ai_coach":
        raise AiCoachChatServiceError("[NEWCOMER_ACTIVITY_TYPE_MISMATCH]", "当前任务不是 AI 辅导。", 422)
    return resolve_governed_coach_profile(activity.config.coach_profile_id)
```

Freeze the activity snapshot into the session config snapshot. Session completion refreshes the unified attempt using evidence ID; it does not inspect `business_skills` or learning-topic keys.

- [ ] **Step 5: Refactor realtime start service**

Change the public method to:

```python
async def start(
    self,
    *,
    actor: User,
    execution_context: ActivityExecutionContext,
    client_token: str,
    trace_id: str | None = None,
) -> dict[str, object]:
```

Validate pinned activity access, published PracticeTemplate, runtime profile, provider registry and StepAudio readiness; pass an external binding containing `owner`, `enrollment_id`, `path_revision_id`, `phase_id`, `module_id`, `activity_id`, and `attempt_id` to `ExternalSessionStartService`.

- [ ] **Step 6: Run focused and existing realtime tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_newcomer_ai_coach_activity.py tests/unit/test_newcomer_realtime_activity.py tests/unit/test_sales_trainer_realtime_roleplay_start.py -q
```

Expected: all tests pass with no fixed `realtime_roleplay` module key.

- [ ] **Step 7: Commit**

```bash
git add backend/src/sales_trainer/orchestration/activities/ai_coach.py backend/src/sales_trainer/orchestration/activities/realtime_roleplay.py backend/src/sales_trainer/services/ai_coach_chat_runtime.py backend/src/sales_trainer/services/ai_coach_session_service.py backend/src/sales_trainer/services/realtime_roleplay_start_service.py backend/tests/unit/test_newcomer_ai_coach_activity.py backend/tests/unit/test_newcomer_realtime_activity.py backend/tests/unit/test_sales_trainer_realtime_roleplay_start.py
git commit -m "feat(newcomer): bind coach and realtime to activities"
```

---

### Task 8: Build canonical learner/admin journey APIs and downstream projections

**Files:**
- Modify: `backend/src/sales_trainer/orchestration/contracts.py`
- Create: `backend/src/sales_trainer/orchestration/journey_service.py`
- Create: `backend/src/sales_trainer/orchestration/learner_api.py`
- Modify: `backend/src/sales_trainer/orchestration/registry.py`
- Modify: `backend/src/sales_trainer/router_registration.py`
- Modify: `backend/src/sales_trainer/services/readiness_dossier_service.py`
- Modify: `backend/src/sales_trainer/services/training_record_service.py`
- Modify: `backend/src/sales_trainer/api.py`
- Test: `backend/tests/unit/test_newcomer_orchestration_journey_service.py`
- Test: `backend/tests/integration/test_newcomer_orchestration_learner_api.py`
- Test: `backend/tests/unit/test_sales_trainer_readiness_dossier_service.py`

**Interfaces:**
- Consumes: active revision, enrollment/attempt repositories, registry and completion engine.
- Produces: `JourneyResponse`, `ModuleDetailResponse`, `ActivityDetailResponse`, canonical journey/action endpoints, admin journey projection.

- [ ] **Step 1: Write failing journey tests**

```python
@pytest.mark.asyncio
async def test_should_pin_revision_and_return_one_primary_next_action(test_db, learner, published_path):
    journey = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=learner
    )

    assert journey.path_revision_id == published_path.revision_id
    assert journey.primary_next_action.activity_id == "activity-product-a-lesson"
    assert sum(
        1 for phase in journey.phases for module in phase.modules
        for activity in module.activities if activity.is_primary_next_action
    ) == 1


@pytest.mark.asyncio
async def test_should_keep_existing_enrollment_on_old_revision_after_publish(test_db, learner):
    first = await publish_path(test_db, title="版本一")
    before = await NewcomerJourneyService(test_db).get_or_create_for_learner(learner=learner)
    await publish_path(test_db, title="版本二")

    after = await NewcomerJourneyService(test_db).get_or_create_for_learner(learner=learner)

    assert before.path_revision_id == first.revision_id
    assert after.path_revision_id == first.revision_id
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/unit/test_newcomer_orchestration_journey_service.py -q`

Expected: service is missing.

- [ ] **Step 3: Implement journey projection**

First add transport DTOs to `contracts.py`: `JourneyActivityProgress`, `JourneyModuleProgress`, `JourneyPhaseProgress`, `JourneyProgressSummary`, `JourneyNextAction`, `JourneyResponse`, `ModuleDetailResponse`, and `ActivityDetailResponse`. Each activity DTO contains stable IDs, business labels, status, completion fields and a server-generated action key; it contains no arbitrary route.

```python
class NewcomerJourneyService:
    async def get_or_create_for_learner(self, *, learner: User) -> JourneyResponse:
        revision = await self._required_active_revision()
        enrollment = await self._enrollments.get_or_create(
            learner_id=str(learner.user_id),
            path_id=PATH_LOGICAL_ID,
            path_revision_id=str(revision.revision_id),
        )
        return await self._project(enrollment=enrollment, learner=learner)

    async def module_detail(
        self, *, learner: User, module_id: str
    ) -> ModuleDetailResponse:
        journey = await self.get_or_create_for_learner(learner=learner)
        return require_module_from_journey(journey, module_id)

    async def activity_detail(
        self, *, learner: User, activity_id: str
    ) -> ActivityDetailResponse:
        context = await self.context_for_activity(learner=learner, activity_id=activity_id)
        projection = await self._registry.handler_for(context.activity.type).project(context)
        return activity_detail_from(context=context, projection=projection)

    async def context_for_activity(
        self, *, learner: User, activity_id: str
    ) -> ActivityExecutionContext:
        revision, enrollment, payload = await self._pinned_payload(learner)
        location = require_activity_location(payload, activity_id)
        return ActivityExecutionContext(
            learner_id=str(learner.user_id),
            enrollment_id=str(enrollment.enrollment_id),
            path_revision_id=str(revision.revision_id),
            phase_id=location.phase.phase_id,
            module_id=location.module.module_id,
            activity=location.activity,
        )
```

On every read, refresh attempts with handler projections, aggregate progress, and select the first unlocked incomplete required activity by phase/module/activity order. If no required task remains, select an optional recommendation; otherwise return no primary action after completion.

Implement `require_module_from_journey(journey, module_id)` and `activity_detail_from(context, projection)` as pure mappers in `journey_service.py`; missing IDs raise `[NEWCOMER_MODULE_NOT_FOUND]` or `[NEWCOMER_ACTIVITY_NOT_FOUND]` with 404.

- [ ] **Step 4: Add learner endpoints**

Mount under `APIRouter(prefix="/newcomer-training")`:

```text
GET  /journey
GET  /modules/{module_id}
GET  /activities/{activity_id}
POST /activities/{activity_id}/lesson/chapters/{chapter_id}/complete
POST /activities/{activity_id}/lesson/confirm
POST /activities/{activity_id}/quiz/attempts
POST /activities/{activity_id}/audio/submissions
POST /activities/{activity_id}/realtime/sessions
POST /activities/{activity_id}/ai-coach/sessions
POST /activities/{activity_id}/assignments
```

Every write accepts or derives a client token, repeats object-level access checks, and returns the updated activity projection.

- [ ] **Step 5: Adapt readiness, records, and admin journey consumers**

Replace `module_key + kind` evidence identity with stable `activity_id + activity_type`. Readiness competencies derive from activity snapshots and configured rubric/quiz capability metadata, not product names. Training records expose phase/module/activity titles from frozen snapshots. Admin list/analytics filter by `activity_id`, `activity_type`, phase, and module.

- [ ] **Step 6: Run focused and downstream tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_newcomer_orchestration_journey_service.py tests/integration/test_newcomer_orchestration_learner_api.py tests/unit/test_sales_trainer_readiness_dossier_service.py tests/unit/test_sales_trainer_training_record_service.py -q
```

Expected: all tests pass; no test fixture needs a fixed business module key.

- [ ] **Step 7: Commit**

```bash
git add backend/src/sales_trainer/orchestration/contracts.py backend/src/sales_trainer/orchestration/journey_service.py backend/src/sales_trainer/orchestration/learner_api.py backend/src/sales_trainer/orchestration/registry.py backend/src/sales_trainer/router_registration.py backend/src/sales_trainer/services/readiness_dossier_service.py backend/src/sales_trainer/services/training_record_service.py backend/src/sales_trainer/api.py backend/tests/unit/test_newcomer_orchestration_journey_service.py backend/tests/integration/test_newcomer_orchestration_learner_api.py backend/tests/unit/test_sales_trainer_readiness_dossier_service.py backend/tests/unit/test_sales_trainer_training_record_service.py
git commit -m "feat(newcomer): project activity-based journeys"
```

---

### Task 9: Replace prototype seed/reset and remove fixed backend path code

**Files:**
- Replace: `backend/scripts/seed_newcomer_training_path.py`
- Create: `backend/scripts/reset_newcomer_training_prototype.py`
- Modify: `backend/src/sales_trainer/router_registration.py`
- Delete: `backend/src/sales_trainer/path_config_api.py`
- Delete: `backend/src/sales_trainer/article_api.py`
- Delete: `backend/src/sales_trainer/business_etiquette_api.py`
- Delete: `backend/src/sales_trainer/customer_faq_api.py`
- Delete: `backend/src/sales_trainer/services/path_config_models.py`
- Delete: `backend/src/sales_trainer/services/path_config_service.py`
- Delete: `backend/src/sales_trainer/services/training_journey_service.py`
- Delete: `backend/src/sales_trainer/services/training_journey_projection.py`
- Delete: `backend/src/sales_trainer/services/learning_topic_config_service.py`
- Delete: `backend/src/sales_trainer/services/learning_topic_projection_service.py`
- Delete: `backend/src/sales_trainer/services/learner_unit_access.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_ai_coach_progress_service.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_capability_service.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_import_service.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_learning_service.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_learning_unit_defaults.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_question_draft_service.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_quiz_service.py`
- Delete: `backend/src/sales_trainer/services/business_etiquette_release_service.py`
- Delete: `backend/src/sales_trainer/services/customer_faq_parser.py`
- Delete: `backend/src/sales_trainer/services/customer_faq_short_answer_service.py`
- Delete: fixed-topic tests under `backend/tests/unit/test_newcomer_learning_topic_*` and superseded fixed-path tests
- Create: `backend/tests/integration/test_newcomer_orchestration_seed.py`
- Create: `backend/tests/scripts/test_reset_newcomer_training_prototype.py`

**Interfaces:**
- Consumes: orchestration admin/revision APIs and shared asset services.
- Produces: idempotent representative seed and bounded dry-run/apply reset.

- [ ] **Step 1: Write failing reset and seed tests**

```python
@pytest.mark.asyncio
async def test_should_seed_three_composable_product_modules(test_db):
    summary = await seed(test_db)
    active = await TrainingPathRevisionService(test_db).active_revision()

    payload = TrainingPathPayload.model_validate(active.payload_json)
    product_modules = payload.phases[1].modules
    assert [module.title for module in product_modules] == [
        "产品 A 核心功能", "产品 B 核心功能", "标准产品 Demo"
    ]
    assert [activity.type for activity in product_modules[0].activities] == [
        "lesson", "quiz", "audio_assessment"
    ]
    assert summary.verified is True


@pytest.mark.asyncio
async def test_should_report_without_mutating_in_dry_run(test_db):
    before = await count_newcomer_rows(test_db)
    report = await reset_newcomer_prototype(test_db, apply=False)
    after = await count_newcomer_rows(test_db)

    assert report.total_rows > 0
    assert after == before
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/pytest tests/integration/test_newcomer_orchestration_seed.py tests/scripts/test_reset_newcomer_training_prototype.py -q`

Expected: new seed/reset contract is absent.

- [ ] **Step 3: Replace the seed with orchestration data**

Seed one path with phases `入门认知`, `产品能力`, `实战演练`; include PPT lesson/audio, product A/B lesson/quiz/audio, standard Demo audio, technical lesson/quiz, optional AI Coach, assignment, and StepAudio realtime when the published runtime profile is ready. Use existing asset services to create and publish content, papers, rubrics, materials, and templates. Publish via `TrainingPathRevisionService`, then verify journey projection for the seed learner.

- [ ] **Step 4: Implement bounded reset**

CLI:

```bash
cd backend
./.venv/bin/python scripts/reset_newcomer_training_prototype.py --dry-run
./.venv/bin/python scripts/reset_newcomer_training_prototype.py --apply --confirm RESET_NEWCOMER_PROTOTYPE
```

Delete only orchestration/path resource types, legacy newcomer path/topic revisions, newcomer enrollments/attempts, and known newcomer seed records. Never delete shared LearningContent, papers, materials, prompts, PracticeTemplates, users, or runtime profiles if another domain references them. Print per-table affected counts and rollback the transaction on any failure.

- [ ] **Step 5: Remove fixed backend authority**

Before deleting, run:

```bash
codegraph callers TrainingJourneyService
codegraph callers NewcomerPathModuleConfig
rg -n "CANONICAL_NEWCOMER_MODULE_KEYS|business_etiquette|customer_faq|company_product_demo|business_skills" backend/src/sales_trainer
```

Update every remaining consumer to orchestration contracts, then delete the listed fixed-path files and remove their router registrations. Keep generic asset, scoring, record, revision, and runtime services.

- [ ] **Step 6: Run backend newcomer suite**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_newcomer_* tests/integration/test_newcomer_* tests/scripts/test_reset_newcomer_training_prototype.py -q
./.venv/bin/ruff check src/sales_trainer scripts/seed_newcomer_training_path.py scripts/reset_newcomer_training_prototype.py
```

Expected: all new orchestration tests pass; `rg` finds no fixed business module authority in runtime code.

- [ ] **Step 7: Commit**

```bash
git add -A backend/src/sales_trainer backend/scripts/seed_newcomer_training_path.py backend/scripts/reset_newcomer_training_prototype.py backend/tests
git commit -m "refactor(newcomer): remove fixed path prototype"
```

---

### Task 10: Replace frontend API contracts and implement pure editor state

**Files:**
- Replace: `web/src/lib/api/types/newcomer-training.ts`
- Replace: `web/src/lib/api/domains/newcomer-training.ts`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client-domains.ts`
- Modify: `web/src/lib/api/client.ts`
- Create: `web/src/lib/newcomer-training/editor-state.ts`
- Create: `web/src/lib/newcomer-training/activity-registry.ts`
- Create: `web/src/lib/newcomer-training/presentation.ts`
- Test: `web/src/lib/newcomer-training/editor-state.test.ts`
- Test: `web/src/lib/api/newcomer-training-orchestration.test.ts`

**Interfaces:**
- Consumes: canonical backend DTOs from Task 8.
- Produces: typed `api.newcomerTraining` and `api.admin.newcomerTraining`, immutable editor-state operations.

- [ ] **Step 1: Write failing editor-state tests**

```typescript
it("duplicates a product module with new stable IDs and unchanged activity types", () => {
  const next = duplicateModule(pathPayload(), "module-product-a", () => nextId());
  const modules = next.phases[0].modules;

  expect(modules).toHaveLength(2);
  expect(modules[1].module_id).not.toBe(modules[0].module_id);
  expect(modules[1].activities.map((item) => item.type)).toEqual([
    "lesson", "quiz", "audio_assessment",
  ]);
});

it("reorders siblings and normalizes order indexes", () => {
  const next = moveModule(pathPayloadWithThreeModules(), "module-c", "before", "module-a");
  expect(next.phases[0].modules.map((item) => [item.module_id, item.order_index])).toEqual([
    ["module-c", 1], ["module-a", 2], ["module-b", 3],
  ]);
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd web && npx vitest run src/lib/newcomer-training/editor-state.test.ts src/lib/api/newcomer-training-orchestration.test.ts`

Expected: modules/types are missing.

- [ ] **Step 3: Replace transport types**

Define a discriminated `ActivityConfig` union matching backend field names exactly. Export `TrainingPathPayload`, `TrainingPathConfigResponse`, `PathValidationResponse`, `JourneyResponse`, `ModuleDetailResponse`, `ActivityDetailResponse`, and activity action request/response types from `types/newcomer-training.ts`. Remove fixed topic/module-key exports.

- [ ] **Step 4: Replace API domain methods**

Expose exactly:

```typescript
api.newcomerTraining.getJourney()
api.newcomerTraining.getModule(moduleId)
api.newcomerTraining.getActivity(activityId)
api.newcomerTraining.completeLessonChapter(activityId, chapterId, clientToken)
api.newcomerTraining.confirmLesson(activityId, clientToken)
api.newcomerTraining.submitQuiz(activityId, payload)
api.newcomerTraining.submitAudio(activityId, payload)
api.newcomerTraining.startRealtime(activityId, clientToken)
api.newcomerTraining.startAiCoach(activityId, clientToken)
api.newcomerTraining.submitAssignment(activityId, payload)

api.admin.newcomerTraining.getPath()
api.admin.newcomerTraining.saveDraft(payload, reason)
api.admin.newcomerTraining.deleteDraft(reason)
api.admin.newcomerTraining.validateDraft()
api.admin.newcomerTraining.publish(reason)
api.admin.newcomerTraining.listRevisions()
api.admin.newcomerTraining.restoreRevision(revisionId, reason)
api.admin.newcomerTraining.listActivityTypes()
```

- [ ] **Step 5: Implement pure editor operations**

Export immutable operations for add/duplicate/delete/move phase/module/activity, update selected object, normalize sibling order indexes, and collect selected IDs. Use `crypto.randomUUID()` only through an injected `IdFactory` so tests remain deterministic.

- [ ] **Step 6: Run tests and type-check focused surfaces**

Run:

```bash
cd web
npx vitest run src/lib/newcomer-training/editor-state.test.ts src/lib/api/newcomer-training-orchestration.test.ts
npx tsc --noEmit
```

Expected: tests and type-check pass after all old consumers compile or are temporarily updated in the same task to the new type exports.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/api web/src/lib/newcomer-training
git commit -m "feat(newcomer): add orchestration frontend contract"
```

---

### Task 11: Build the focused admin path editor shell

**Files:**
- Create: `web/src/app/admin/newcomer-training/path/page.tsx`
- Create: `web/src/app/admin/newcomer-training/path/page.test.tsx`
- Create: `web/src/components/admin/newcomer-training/path-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/path-outline.tsx`
- Create: `web/src/components/admin/newcomer-training/path-inspector.tsx`
- Create: `web/src/components/admin/newcomer-training/path-preview.tsx`
- Create: `web/src/components/admin/newcomer-training/path-validation-panel.tsx`
- Create: `web/src/components/admin/newcomer-training/path-editor.test.tsx`

**Interfaces:**
- Consumes: API and editor state from Task 10.
- Produces: three-pane path editor, draft/save/validate/publish workflow.

- [ ] **Step 1: Write failing page and editor tests**

```tsx
it("shows one outline, one focused inspector, and one learner preview", async () => {
  render(<PathEditor initialModel={pathConfigResponse()} />);

  expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeInTheDocument();
  expect(screen.getByRole("form", { name: "模块设置" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "学员预览" })).toBeInTheDocument();
  expect(screen.queryByText("fallback_applied=true")).not.toBeInTheDocument();
});

it("moves a module with keyboard controls", async () => {
  const user = userEvent.setup();
  render(<PathEditor initialModel={pathWithThreeModules()} />);

  await user.click(screen.getByRole("button", { name: "上移 产品 C" }));

  expect(outlineModuleNames()).toEqual(["产品 A", "产品 C", "产品 B"]);
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd web && npx vitest run src/app/admin/newcomer-training/path/page.test.tsx src/components/admin/newcomer-training/path-editor.test.tsx`

Expected: components do not exist.

- [ ] **Step 3: Implement the page workflow**

The page loads the config once, initializes a local immutable draft, tracks dirty state, and exposes sticky actions `保存草稿`, `检查并预览`, `发布`. Require a non-empty change reason only for save/publish. Use inline error and Toast; never `alert`, `confirm`, or `prompt`.

- [ ] **Step 4: Implement outline and inspector**

Use a semantic tree with native `draggable` mouse support plus explicit `上移/下移` buttons. Only the selected phase/module/activity editor renders in the inspector. Add actions create from six module templates and six activity types. Delete uses the shared `ConfirmDialog`.

- [ ] **Step 5: Implement preview and validation panel**

Preview renders the learner-facing title, progress outline and one next-step example from the local draft. Validation issues group by phase/module/activity and focus the referenced object on click. Show business messages only.

- [ ] **Step 6: Run component tests, accessibility assertions, and type-check**

Run:

```bash
cd web
npx vitest run src/app/admin/newcomer-training/path/page.test.tsx src/components/admin/newcomer-training/path-editor.test.tsx
npx tsc --noEmit
```

Expected: all tests pass; all icon buttons have accessible names and focus remains visible.

- [ ] **Step 7: Commit**

```bash
git add web/src/app/admin/newcomer-training/path web/src/components/admin/newcomer-training
git commit -m "feat(newcomer): build focused path editor"
```

---

### Task 12: Add typed activity editors and in-flow resource creation

**Files:**
- Create: `web/src/components/admin/newcomer-training/resource-picker-drawer.tsx`
- Create: `web/src/components/admin/newcomer-training/resource-picker-drawer.test.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/lesson-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/quiz-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/audio-assessment-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/realtime-roleplay-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/ai-coach-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/assignment-editor.tsx`
- Create: `web/src/components/admin/newcomer-training/activity-editors/activity-editors.test.tsx`
- Modify: `web/src/components/admin/newcomer-training/path-inspector.tsx`

**Interfaces:**
- Consumes: existing asset APIs/forms and typed activity config.
- Produces: six ordinary forms and resource quick-create drawer.

- [ ] **Step 1: Write failing editor tests**

```tsx
it("edits audio assessment without exposing prompt IDs or JSON", async () => {
  render(<AudioAssessmentEditor value={audioActivity()} resources={resourceOptions()} onChange={onChange} />);

  expect(screen.getByLabelText("评分标准")).toBeInTheDocument();
  expect(screen.getByLabelText("通过分")).toBeInTheDocument();
  expect(screen.queryByText(/prompt_id|raw JSON|runtime_binding/i)).not.toBeInTheDocument();
});

it("creates a missing paper in flow and binds it", async () => {
  const user = userEvent.setup();
  render(<ResourcePickerDrawer kind="exam_paper" open onCreated={onCreated} />);

  await user.click(screen.getByRole("button", { name: "快速组卷" }));
  await user.type(screen.getByLabelText("试卷名称"), "产品 A 小测");
  await user.click(screen.getByRole("button", { name: "创建并绑定" }));

  expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ title: "产品 A 小测" }));
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd web && npx vitest run src/components/admin/newcomer-training/resource-picker-drawer.test.tsx src/components/admin/newcomer-training/activity-editors/activity-editors.test.tsx`

Expected: editors are missing.

- [ ] **Step 3: Implement six typed editors**

Each editor receives `{value, disabled, resources, onChange, onQuickCreate}`. Render only business fields from the approved spec. Put audience, prerequisites, AI/runtime diagnostics and retry policy under an `高级设置` disclosure. Do not implement a generic JSON-schema form.

- [ ] **Step 4: Implement quick-create drawer**

Reuse existing API methods and form logic to create/publish the minimal asset, refresh options, call `onCreated`, and close without route changes:

- lesson: content + non-empty first chapter + publish;
- quiz: choose published questions + create/publish paper;
- audio: create material/version and structured scoring rubric;
- realtime: select published PracticeTemplate and runtime profile;
- AI Coach: select governed coach profile;
- assignment: no asset creation.

- [ ] **Step 5: Run tests and type-check**

Run:

```bash
cd web
npx vitest run src/components/admin/newcomer-training/resource-picker-drawer.test.tsx src/components/admin/newcomer-training/activity-editors/activity-editors.test.tsx
npx tsc --noEmit
```

Expected: tests pass, duplicate submissions are disabled while pending, server errors remain in the drawer.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/admin/newcomer-training
git commit -m "feat(newcomer): add activity editors and quick create"
```

---

### Task 13: Build the learner next-action journey and generic activity page

**Files:**
- Create: `web/src/app/(dashboard)/newcomer-training/page.tsx`
- Create: `web/src/app/(dashboard)/newcomer-training/page.test.tsx`
- Create: `web/src/app/(dashboard)/newcomer-training/modules/[moduleId]/page.tsx`
- Create: `web/src/app/(dashboard)/newcomer-training/activities/[activityId]/page.tsx`
- Create: `web/src/components/newcomer-training/journey-home.tsx`
- Create: `web/src/components/newcomer-training/journey-outline.tsx`
- Create: `web/src/components/newcomer-training/module-detail.tsx`
- Create: `web/src/components/newcomer-training/activity-shell.tsx`
- Create: six files under `web/src/components/newcomer-training/activity-runners/`
- Create: `web/src/components/newcomer-training/journey-home.test.tsx`
- Create: `web/src/components/newcomer-training/activity-shell.test.tsx`

**Interfaces:**
- Consumes: canonical journey/activity API.
- Produces: learner home, module detail and one generic activity route.

- [ ] **Step 1: Write failing learner-home tests**

```tsx
it("shows exactly one primary continue action", () => {
  render(<JourneyHome journey={journeyWithThirtyModules()} />);

  expect(screen.getAllByRole("link", { name: "继续学习" })).toHaveLength(1);
  expect(screen.getByText("当前阶段：产品能力")).toBeInTheDocument();
  expect(screen.queryByText("我的全部录音")).not.toBeInTheDocument();
});

it("collapses completed and future phases", () => {
  render(<JourneyHome journey={journeyWithPastCurrentFuturePhases()} />);
  expect(screen.getByRole("button", { name: /入门认知.*已完成/ })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: /产品能力.*当前/ })).toHaveAttribute("aria-expanded", "true");
});
```

- [ ] **Step 2: Write failing activity dispatch test**

```tsx
it.each([
  ["lesson", "学习内容"],
  ["quiz", "开始答题"],
  ["audio_assessment", "上传讲解录音"],
  ["realtime_roleplay", "开始实时对练"],
  ["ai_coach", "进入 AI 辅导"],
  ["assignment", "提交作业"],
])("dispatches %s to its trusted runner", (type, label) => {
  render(<ActivityShell detail={activityDetail(type)} />);
  expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
});
```

- [ ] **Step 3: Run tests and verify RED**

Run: `cd web && npx vitest run src/components/newcomer-training/journey-home.test.tsx src/components/newcomer-training/activity-shell.test.tsx`

Expected: components are missing.

- [ ] **Step 4: Implement learner home and module detail**

Home renders current phase, overall progress, estimated duration and one primary action above a progressive phase outline. Module detail renders ordered activity steps, feedback and one next action. Move recording history, all scores and remediation history out of home; link them to the existing records surface filtered by enrollment/module.

- [ ] **Step 5: Implement trusted runner registry**

```typescript
export const ACTIVITY_RUNNERS: Record<ActivityType, ComponentType<ActivityRunnerProps>> = {
  lesson: LessonRunner,
  quiz: QuizRunner,
  audio_assessment: AudioAssessmentRunner,
  realtime_roleplay: RealtimeRoleplayRunner,
  ai_coach: AiCoachRunner,
  assignment: AssignmentRunner,
};
```

The activity route reads `activityId`, fetches server-authoritative detail, and dispatches by returned type. It never accepts a component or target URL from config.

- [ ] **Step 6: Reuse mature interaction components**

Extract reusable content from old audio/quiz/coach pages into the six runners, replacing `unitId`, module keys and scenario slugs with `activityId`. Keep polling, recorder cleanup, question validation, StepAudio start, streaming coach messages and accessible upload states.

- [ ] **Step 7: Run learner tests and type-check**

Run:

```bash
cd web
npx vitest run src/app/\(dashboard\)/newcomer-training/page.test.tsx src/components/newcomer-training/journey-home.test.tsx src/components/newcomer-training/activity-shell.test.tsx
npx tsc --noEmit
```

Expected: tests and type-check pass.

- [ ] **Step 8: Commit**

```bash
git add web/src/app/\(dashboard\)/newcomer-training web/src/components/newcomer-training
git commit -m "feat(newcomer): build next-action learner journey"
```

---

### Task 14: Switch navigation and downstream views, then remove fixed frontend code

**Files:**
- Modify: `web/src/components/layout/admin-sidebar.tsx`
- Modify: `web/src/components/layout/admin-shell.tsx`
- Modify: `web/src/components/layout/sidebar.tsx`
- Modify: `web/src/app/(dashboard)/training/page.tsx`
- Modify: `web/src/app/(dashboard)/page.tsx`
- Modify: `web/src/app/(dashboard)/team/page.tsx`
- Modify: `web/src/app/(dashboard)/team/[learnerId]/page.tsx`
- Modify: `web/src/lib/team-journey/view-models.ts`
- Delete: `web/src/app/admin/sales-trainer/paths/`
- Delete: fixed-topic admin pages under `web/src/app/admin/sales-trainer/learning-topics/`
- Delete: fixed learner pages under `web/src/app/(dashboard)/sales-trainer/`
- Delete: `web/src/lib/sales-trainer/module-path.ts`
- Delete: `web/src/lib/sales-trainer/config-center.ts`
- Delete: `web/src/lib/sales-trainer/config-center-definitions.ts`
- Delete: `web/src/lib/sales-trainer/config-center-types.ts`
- Delete: `web/src/lib/sales-trainer/path-config-editing.ts`
- Delete: `web/src/lib/sales-trainer/audio-evaluation-scenarios.ts`
- Delete: `web/src/lib/sales-trainer/config-center-audio.ts`
- Delete: `web/src/lib/sales-trainer/config-center-audio-bindings.test.ts`
- Delete: `web/src/lib/sales-trainer/business-etiquette-units.ts`
- Delete: superseded path-config components under `web/src/components/admin/sales-trainer/`
- Test: `web/src/components/layout/admin-sidebar.test.tsx`
- Test: `web/src/components/layout/sidebar.test.tsx`
- Test: `web/src/lib/newcomer-training/no-legacy-authority.test.ts`

**Interfaces:**
- Consumes: new routes/components.
- Produces: one canonical user/admin entry and no fixed frontend path authority.

- [ ] **Step 1: Write failing navigation and legacy-boundary tests**

```typescript
it("links learner and admin navigation to canonical newcomer routes", () => {
  expect(learnerNavHref("新人训练路径")).toBe("/newcomer-training");
  expect(adminNavHref("新人训练路径")).toBe("/admin/newcomer-training/path");
});

it("contains no fixed newcomer module keys in runtime frontend source", () => {
  const forbidden = [
    "ppt_explanation", "company_product_demo", "business_skills",
    "elevator_pitch", "customer_faq_oral_drill",
  ];
  const source = runtimeNewcomerSource();
  for (const key of forbidden) expect(source).not.toContain(key);
});
```

- [ ] **Step 2: Switch all entry links and team projections**

Use `/newcomer-training` and `/admin/newcomer-training/path` everywhere. Team views consume phase/module/activity projections and use activity titles/types for filtering; they do not reconstruct old module cards.

- [ ] **Step 3: Delete fixed frontend authority**

Run before deletion:

```bash
rg -l "module-path|config-center|ppt_explanation|business_skills|customer_faq" web/src
```

Move reusable recorder/result/quiz/coach UI into the new activity runners, update every caller, then delete the listed old pages/libs/components and their superseded tests. Do not add redirects.

- [ ] **Step 4: Run frontend unit boundary and full type checks**

Run:

```bash
cd web
npx vitest run src/components/layout/admin-sidebar.test.tsx src/components/layout/sidebar.test.tsx src/lib/newcomer-training/no-legacy-authority.test.ts
npx tsc --noEmit
npx eslint . --quiet
```

Expected: all pass; the runtime-source boundary test finds no fixed module authority.

- [ ] **Step 5: Commit**

```bash
git add -A web/src
git commit -m "refactor(newcomer): remove fixed frontend path"
```

---

### Task 15: Replace E2E coverage, update contracts/ADR, reset prototype data, and run final gates

**Files:**
- Replace: `web/tests/e2e/newcomer-training-route-manifest.ts`
- Replace: `web/tests/e2e/newcomer-training-admin.spec.ts`
- Replace: `web/tests/e2e/newcomer-training-learner.spec.ts`
- Replace: `web/tests/e2e/newcomer-training-closed-loop.spec.ts`
- Modify: `docs/api-contract/sales-trainer.md`
- Modify: `docs/architecture.md`
- Create: `docs/adr/2026-07-12-newcomer-training-activity-orchestration.md`
- Modify: `docs/testing.md`
- Modify: `docs/ai-governance.md`

**Interfaces:**
- Consumes: completed backend/frontend implementation.
- Produces: executable product proof, canonical documentation, clean prototype database.

- [ ] **Step 1: Write the new closed-loop E2E before deleting old assertions**

The admin spec must prove through UI:

```typescript
test("admin creates and publishes product A, B, and C without source-specific forms", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/newcomer-training/path");

  for (const product of ["产品 A", "产品 B", "产品 C"]) {
    await createModuleFromTemplate(page, "学习、考试加录音讲解", product);
    await bindPublishedLessonPaperAndRubric(page, product);
  }

  await page.getByLabel("本次变更说明").fill("配置三套产品训练");
  await page.getByRole("button", { name: "检查并预览" }).click();
  await expect(page.getByText("可以发布")).toBeVisible();
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.getByText("新人训练路径已发布")).toBeVisible();
});
```

The learner spec must prove one primary next action, lesson → quiz → audio unlock, pinned revision, failed audio retry, optional activity non-blocking, and clear realtime unavailable state. Use fake/local providers in ordinary CI; keep real StepAudio coverage behind the existing explicit real-provider gate.

- [ ] **Step 2: Run reset dry-run, apply, and seed verification**

Run:

```bash
cd backend
./.venv/bin/python scripts/reset_newcomer_training_prototype.py --dry-run
./.venv/bin/python scripts/reset_newcomer_training_prototype.py --apply --confirm RESET_NEWCOMER_PROTOTYPE
./.venv/bin/python scripts/seed_newcomer_training_path.py
```

Expected: dry-run and apply counts match; seed reports verified active revision, three phases, representative six activity types, and no skipped required binding.

- [ ] **Step 3: Update canonical documentation**

Rewrite the newcomer path sections of `sales-trainer.md` around activity IDs/types and the new API. Remove fixed module/topic matrices and compatibility notes. Add the ADR decision: direct replacement, revision aggregate, closed handler registry, pinned enrollment, no arbitrary executable config, and explicit rejection of V1/V2 dual track. Update architecture and test commands.

- [ ] **Step 4: Run backend quality gates**

Run:

```bash
cd backend
./.venv/bin/ruff check src/ tests/ scripts/
./.venv/bin/mypy src/
./.venv/bin/pytest tests/unit/ -q
./.venv/bin/pytest tests/integration/ -m integration -q
./.venv/bin/pytest tests/contract/ -m contract -q
./.venv/bin/alembic current
```

Expected: all commands pass; Alembic current is `20260712_1300_092`.

- [ ] **Step 5: Run frontend quality gates**

Run:

```bash
cd web
npx tsc --noEmit
npx eslint . --quiet
npx vitest run
npx next build
npx playwright test tests/e2e/newcomer-training-admin.spec.ts tests/e2e/newcomer-training-learner.spec.ts tests/e2e/newcomer-training-closed-loop.spec.ts
```

Expected: type-check, lint, unit tests, build, and all newcomer E2E tests pass.

- [ ] **Step 6: Run structural closure checks**

Run:

```bash
rg -n "CANONICAL_NEWCOMER_MODULE_KEYS|NewcomerPathModuleConfig|ppt_explanation|company_product_demo|business_skills|elevator_pitch|customer_faq_oral_drill" backend/src/sales_trainer web/src
rg -n "/sales-trainer|/admin/sales-trainer/paths" web/src web/tests/e2e
git diff --check
git status --short
```

Expected: first two searches return no runtime route/business authority matches; only intentionally retained historical documentation may mention old terms. `git diff --check` is clean; status contains only this implementation plus pre-existing unrelated user changes.

- [ ] **Step 7: Commit final contracts and verification**

```bash
git add web/tests/e2e docs/api-contract/sales-trainer.md docs/architecture.md docs/adr/2026-07-12-newcomer-training-activity-orchestration.md docs/testing.md docs/ai-governance.md
git commit -m "test(newcomer): verify activity orchestration closure"
```

---

## Definition of Done

- Admin creates, duplicates, removes, reorders, validates and publishes phases/modules/activities without source changes.
- Product A/B/C each compose lesson + quiz + audio assessment through the same six activity editors/handlers.
- PPT and Demo are configuration data, not code branches.
- Learner home exposes one primary next action and remains usable with 30 modules.
- Enrollment pins an immutable revision; attempts freeze activity/result snapshots.
- Lesson, quiz, audio, realtime, AI Coach and assignment handlers pass the shared contract suite.
- Quick-create stays in the path editor and automatically binds the created resource.
- Backend permissions, idempotency, audit, object scope and fail-closed errors are verified.
- Fixed newcomer module/topic keys, compatibility projections and old route pages are removed.
- Reset dry-run/apply and the new seed are repeatable and verified.
- Backend tests/lint/types/migration and frontend tests/lint/types/build/E2E all pass.
- Existing unrelated working-tree changes remain untouched.

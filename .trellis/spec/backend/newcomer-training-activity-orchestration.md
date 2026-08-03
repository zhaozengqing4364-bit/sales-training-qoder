# Newcomer Training Activity Orchestration

> Target contract accepted 2026-07-16; implementation status updated 2026-07-17. Slice 6 implements Path/Stage/ActivityDefinition, frozen Enrollment, Journey, generic Attempt/Outcome, five first-launch activities, Readiness review, the unified admin workspace and ReleasePlan governance. Phase/Module, realtime, auto-rollout and subtype-route behavior are Legacy migration input only.

## 1. Scope / Authority

Apply to Path/Revision, Stage, ActivityDefinition, Cohort, Enrollment, ActivityAttempt/Outcome, Journey, activity execution, admin publishing, and migration from the current Sales Trainer orchestration.

Normative sources:

- `docs/newcomer-foundation-contract-index.md`
- `docs/architecture/newcomer-foundation-contract.md`
- `docs/architecture/newcomer-foundation-state-machines.md`
- `docs/api-contract/newcomer-training-v2.md`

Executable entry points include `newcomer_training.PathEnrollmentService`, `JourneyQueryService`, `ActivityAttemptService`, `learning.LessonRuntimeService`, `QuizRuntimeService`, `audio_assessment.AudioAssessmentRuntime` and `ai_coach.StructuredCoachRuntime`. Cross-domain execution is composed through `PublishedActivityResourcePort`, `ActivityRuntimePort` and `ActivityOutcomeWriterPort`; activity domains do not import each other's ORM to infer completion. Admin API、role projection and standard-pack installation are application-root composition modules, not domain-owned backdoors. The executable Coach contract is [Structured AI Coach](./structured-ai-coach.md).

## 2. Target Signatures

```text
Path -> PathRevision -> Stage[] -> ActivityDefinition[]
```

```python
ActivityType = Literal[
    "lesson", "quiz", "audio_assessment", "ai_coach", "assignment"
]

class ActivityRuntime(Protocol):
    type_key: ActivityType
    async def project(self, context: ActivityExecutionContext) -> ActivityProjection: ...
    async def execute(self, command: ActivityCommand, context: ActivityExecutionContext) -> ActivityExecutionAccepted: ...
    async def reconcile(self, attempt: ActivityAttemptSnapshot, evidence: ActivityEvidenceSnapshot) -> ActivityOutcome: ...

class ActivityDefinitionCompiler(Protocol):
    async def validate(self, definition: ActivityDefinition) -> tuple[ValidationIssue, ...]: ...
    async def preview(self, definition: ActivityDefinition, actor: ActorContext) -> ActivityPreview: ...
    async def compile(self, definition: ActivityDefinition) -> CompiledActivityDefinition: ...
```

Target namespaces are `/api/v1/newcomer-training/**` and `/api/v1/admin/newcomer-training/**`. Writes require `Idempotency-Key`; mutable revisions/decisions use `If-Match`.

## 3. Contracts

### Path and definitions

- `PathRevision` working content may change; published content is immutable.
- Phase and Module are forbidden in the target schema. A Stage directly owns ordered ActivityDefinitions.
- Realtime is forbidden from the first-launch union, seed, navigation, permission matrix, and acceptance tests.
- Definitions store typed declarative config and published resource revision IDs/hashes only. Executable code, component names, routes, URLs, scripts, arbitrary dictionaries, and Provider secrets are rejected.
- Unknown activity types or fields fail validation; no silent ignore or dynamic import.
- Final publication runs through ReleasePlan dependency validation and atomic business publication. The former direct Path/resource publish HTTP tombstones were deleted after the Slice 8 consumer/OpenAPI inventory proved no remaining callers; they must not be restored as forwarding or dual-write routes.

### Enrollment and attempts

- Cohort binds one published PathRevision; Enrollment freezes it.
- Publishing a new revision does not modify active Enrollments. Journey reads never self-heal to latest.
- Revision movement requires `MigrateEnrollmentRevision` preview + confirm, expected version, reason, permission, audit, and `EnrollmentRevisionMigrated` Outbox event.
- ActivityAttempt freezes PathRevision, ActivityDefinition, resource revisions, scoring/Prompt/model contracts as required.
- Technical retry reuses the same Attempt and idempotency key. A learner retry creates a new attempt number only after an explicit command.
- Activity modules own detailed writes. Journey receives one normalized ActivityOutcome and never queries another module's ORM to infer completion.

### Five activity contracts

| Type | Required frozen authority | Completion |
|---|---|---|
| lesson | LearningUnit revision + completion policy | deterministic confirmation/progress rule |
| quiz | QuizRevision + answer/scoring/red-line contract | rule score plus completed async short-answer results |
| audio_assessment | task brief + material + scoring scheme + limits | durable pipeline yields Outcome or needs review |
| ai_coach | profile + Prompt/model/rubric + card/round limits | required checkpoints/mastery gates or human review |
| assignment | exactly three asynchronous customer-scenario audio segments, per-segment goal/material, and scoring/review contract | all three valid segment outcomes plus configured rule/human review |

AI failure never fabricates a score or completion. Audio technical quality failure does not become competency failure. First-launch `assignment` is not a generic text/file homework type: it is the three-segment asynchronous customer-scenario recording activity, and cannot complete with missing, low-confidence, or unreviewed segments.

### Read projection and UI

- Journey, Activity Workspace, Task Status, Evidence Dossier, and Admin Queue use the v2 ViewModels.
- Exactly one primary next action is projected.
- Frontend follows DTO -> Domain -> ViewModel -> UI and never calculates readiness from raw activity payloads.
- User-facing copy excludes internal codes, Prompt/Provider, trace IDs, raw JSON, database IDs, Phase/Module, and Realtime-first-launch messaging.

## 4. Validation / Error Matrix

| Condition | Required behavior |
|---|---|
| Phase/Module or realtime in target payload | 422 typed validation failure |
| Unknown activity/config field | 422; do not ignore |
| Referenced resource missing/draft/stale | ReleasePlan blocked with object/field issue |
| No assigned Enrollment | explicit unassigned state; no learner self-enrollment |
| Enrollment revision missing | typed configuration failure; never substitute latest |
| Publish while active Enrollments exist | publish succeeds without moving them; impact reports counts |
| Migration preview/version/hash stale | 409/412, no write |
| Duplicate logical command | original result returned |
| Same idempotency key with different input | 409 `[IDEMPOTENCY_KEY_REUSED]` |
| Provider unavailable | persisted retryable/needs-review state; no fake completion |
| Outcome arrives twice | consumer idempotency returns current Attempt/Outcome pointer |

## 5. Good / Base / Bad Cases

- **Good**: an Assignment definition freezes exactly three customer-scenario recording segments; each segment finalizes through a durable Task, produces a normalized segment Outcome, and the common Attempt completes only after all three are valid and any configured human review is recorded.
- **Base**: a learner opens Journey with a frozen Enrollment, starts one Lesson Attempt, repeats an uncertain network write with the same idempotency key, receives the original result, and publishing a new PathRevision leaves that Enrollment unchanged.
- **Bad**: a route imports another module's ORM, accepts a generic text/file Assignment, resolves a resource from latest after Attempt creation, moves active Enrollments during publish, or marks completion directly from model output.

## 6. Tests Required

- Schema/registry exhaustiveness proves exactly five activity types and no dynamic import.
- Published revision immutability; new publish leaves existing Enrollment unchanged.
- Explicit migration preview/confirm, conflict, permission, idempotency, audit, and event tests.
- Attempt concurrency, same-token uncertain retry, new learner attempt, immutable snapshots, and Outcome reconcile tests.
- Unit contract for every Runtime/Compiler Adapter through the stable interface.
- PostgreSQL integration for business write + Outbox atomicity and duplicate delivery.
- OpenAPI/DTO/ViewModel parity; frontend states; one-primary-action and no internal-term leakage.
- E2E for five activities, background recovery, manager review, cross-organization denial, and absence of Realtime.

## 7. Wrong vs Correct

### Wrong: subtype route owns business state and generic Assignment

```python
@router.post("/activities/{activity_id}/assignments")
async def submit_assignment(text: str | None, file: UploadFile | None) -> None:
    attempt.status = "completed"
    await db.commit()
```

This bypasses the ActivityRuntime/Outcome seam, permits a non-contract submission, and makes the delivery layer the state-machine writer.

### Correct: typed command enters the application seam

```python
accepted = await activity_application.execute(
    ActivityCommandV1(
        command_type="finalize_assignment_segment",
        attempt_id=attempt_id,
        expected_attempt_version=expected_version,
        payload=FinalizeAssignmentSegmentV1(
            segment_id=segment_id,
            upload_ref=upload_ref,
        ),
    ),
    actor=actor,
    idempotency_key=idempotency_key,
)
```

The application service validates the frozen three-segment contract, delegates to the registered Runtime/Task port, and reconciles only a schema-valid ActivityOutcome. The route maps the accepted result; it never writes status itself.

## Scenario: Full-File Audio Upload And Durable Assessment

### 1. Scope / Trigger

- Trigger: implementing or changing recording/upload, media normalization, ASR, scoring, reconciliation, regrade or incomplete-upload cleanup for `audio_assessment` or `assignment`.
- Excludes realtime streams, realtime customer roleplay, voice cloning and emotion/voiceprint analysis.

### 2. Signatures

```http
POST /api/v1/newcomer-training/activities/{activity_id}/commands
PUT  /api/v1/newcomer-training/audio-upload-sessions/{upload_session_id}/parts/{part_number}/content
GET  /api/v1/newcomer-training/audio-artifacts/{artifact_id}/playback
GET  /api/v1/admin/newcomer-training/audio-assessments/queue
POST /api/v1/admin/newcomer-training/audio-submissions/{submission_id}/commands/repair
POST /api/v1/admin/newcomer-training/audio-submissions/{submission_id}/{regrade|transcript-correction|invalidation}/{preview|confirm}
```

Learner command union: `start | create_upload_session | confirm_upload_part | finalize_upload | retry_stage | cancel`.

```text
task_type = "audio_assessment.pipeline.process"
states = uploaded -> validating -> normalizing -> transcribing -> scoring -> reconciling
AUDIO_ASSESSMENT_STORAGE_BACKEND = local | oss | cos
NEWCOMER_AUDIO_ASSESSMENT_ENABLED = true | false
NEWCOMER_ASYNC_ASSIGNMENT_ENABLED = true | false
```

Upload persistence includes immutable part declarations plus `cleanup_started_at`, `cleanup_claim_token`, `cleanup_completed_at` and `cleanup_attempts` on the UploadSession.

### 3. Contracts

- Attempt start freezes material/scenario, Scorecard, language, ASR/scoring route, quality thresholds, competency mapping and capture limits. Backend snapshot is authoritative; the frontend only prevents obvious invalid input early.
- Application-level multipart uses backend-generated organization/Run/UploadSession object keys. Each part is independently uploaded and declared by number, size and SHA-256; client callbacks never establish completion.
- Local development streams one part through the protected PUT route. OSS/COS returns signed direct-upload URLs; cloud files never traverse API memory.
- `confirm_upload_part` re-HEADs one object. `finalize_upload` only verifies registered completeness and enqueues the durable task; the Worker re-HEADs/materializes all parts and validates complete size/hash/ownership.
- Every slow boundary (object IO, ffmpeg/ffprobe, ASR, LLM) runs outside a database transaction. Prepare/apply phases use fenced short transactions and store an exact retry stage.
- Original and normalized artifacts are separate immutable rows. TranscriptRevision and ScoreOutcomeVersion are append-only; manual correction, retranscription, regrade and invalidation retain history.
- Quality `not_scorable/needs_review` is distinct from competency failure and never emits zero-score evidence.
- Expired/cancelled upload parts are claimed in bounded batches with row locks, stale-claim recovery and a UUID fence. Claim commits before object deletion; completion/release requires the same token. Finalized artifacts are never selected.
- Cleanup runs from a deployment scheduler, not an API-process `asyncio.create_task`; formal evidence retention is a separate governed task/policy.

### 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Size/duration/content type/part layout exceeds frozen policy | 422 typed error before session creation |
| Part object size/hash differs from declaration | reject confirm/finalize; keep draft and recoverable position |
| Upload expires or is cancelled | no formal result; cleanup claim deletes only unfinished objects |
| Empty/corrupt/unsupported media | terminal failure and explicit re-upload path; original reference retained when materialized |
| Storage/ffmpeg tool temporarily unavailable | `failed_recoverable` at exact stage |
| ASR timeout/429/invalid schema | recoverable transcription failure; no empty Transcript |
| Low speech/confidence/language mismatch | `needs_review/not_scorable`; no score/competency failure |
| Scoring Prompt/provider/schema/evidence invalid | recoverable scoring failure; no ScoreOutcomeVersion |
| Reconcile interrupted or duplicated | `reconciling`; safe replay produces one normalized Outcome/event effect |
| Cross-organization playback/regrade | hidden 404/denial plus requesting-scope audit |

### 5. Good / Base / Bad Cases

- Good: a 30-minute-capable browser recording persists one-second chunks locally, resumes missing 5MB parts, finalizes quickly and completes after a restarted Worker without duplicate Outcome.
- Base: ASR is temporarily unavailable; original/normalized artifacts and task location remain, an authorized repair command requeues transcription, and the learner can leave the page.
- Bad: call `UploadFile.read()` for the whole recording, trust a client complete callback, run ffmpeg inside an open transaction, overwrite a Transcript row, or mark task success as business completion before reconcile.

### 6. Tests Required

- Runtime: frozen 30-minute/100MB policy, part layout, hash/size mismatch, resume, cancel, expiry and cleanup retry/fencing.
- Worker: new Handler instance replays persisted state; validation/storage, ASR timeout, invalid scoring Schema and reconcile duplication preserve the exact recovery contract.
- Media: real ffprobe/ffmpeg fixture validates decode, duration, silence/volume, normalization and corrupt/overlong rejection.
- Governance: automatic/manual/retranscribed revisions and regrade versions append; stale preview/idempotency/cross-org commands reject and audit.
- Delivery: canonical learner/admin route inventory and legacy writer/BackgroundTask importer inventory.
- Frontend: chunk persistence/recovery, one-part-at-a-time upload, missing-part resume, pause/cancel, truthful processing/not-scorable/terminal states and no internal terms.
- Migration: audio tables, constraints, indexes and Attempt outcome extension upgrade/downgrade in the targeted fixture.

### 7. Wrong vs Correct

#### Wrong

```python
contents = await upload.read()
result = await transcribe_and_score(contents)
submission.status = "completed"
```

This buffers the full file, binds Provider latency to the request and makes process death lose the recovery point.

#### Correct

```python
upload = await audio_runtime.create_upload_session(frozen_manifest)
# browser streams/direct-uploads each declared part
accepted = await audio_runtime.finalize_upload(upload.upload_session_id)
# durable Worker: prepare transaction -> external IO -> fenced apply transaction
```

The request returns task/result references quickly; all formal writes are idempotent and recoverable from PostgreSQL truth.

## Scenario: Atomic Foundation Release And Rollback

### 1. Scope / Trigger

- Trigger: adding or changing Path/resource publication, release validation, active-version selection, rollback, Enrollment impact reporting or an admin endpoint that can make a training revision formally effective.
- Excludes mutable working saves, learner execution, Enrollment revision migration and Realtime customer voice roleplay.

### 2. Signatures

```http
POST /api/v1/admin/newcomer-training/release-plans/preview
GET  /api/v1/admin/newcomer-training/release-plans
POST /api/v1/admin/newcomer-training/release-plans/{release_plan_id}/commands/publish
POST /api/v1/admin/newcomer-training/release-plans/{release_plan_id}/rollback-preview
POST /api/v1/admin/newcomer-training/release-plans/{release_plan_id}/commands/rollback
```

```python
class ReleaseDependencyPort(Protocol):
    async def inspect(self, *, organization_id: str, activity_type: str, revision_id: str) -> ReleaseDependency: ...
    async def publish(self, *, organization_id: str, target: ReleaseTarget, actor: CommandActor) -> None: ...
```

`ReleasePlan` freezes `path_revision_id`, target revisions, dependency graph, validation report, impact preview/hash, runtime contract hash, reason, actor and version. Confirm commands require the short-lived preview token, identical impact hash, `If-Match` and `Idempotency-Key`.

### 3. Contracts

- `ReleasePlanService` is the sole HTTP-reachable coordinator for formal Path/Source/Question/LearningUnit/Quiz publication. Routes and UI never call a domain publish method directly.
- Preview resolves the complete exact-revision graph and validates organization, approval/status, source anchors, competency mappings, runtime contract, required governed configuration and Enrollment impact before activation.
- Working children may be composed into one plan, but publish order follows the dependency graph: Source and Question before LearningUnit and Quiz, all resources before Path. The final validation sees only exact revisions published inside the same transaction.
- Publish is one database transaction. A blocker, stale target, hash/version conflict or domain failure rolls back every pointer and keeps the previous active plan serving learners.
- Publishing a PathRevision never mutates active Enrollment. Migration remains a separate preview/confirm command with its own scope, reason and audit.
- Rollback reactivates a previously published plan for the same organization and Path. It never edits or deletes a published revision.
- The direct Path/resource publish compatibility routes return `[NEWCOMER_RELEASE_PLAN_REQUIRED]` and write nothing. They are not forwarding adapters.

### 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Missing/unapproved/stale/cross-org dependency | preview contains a blocker; publish is unavailable |
| Missing competency mapping or incompatible runtime hash | blocker tied to Path activity/field |
| Preview token expired or impact hash changed | 409, no pointer or status changes |
| `If-Match` no longer matches plan | 412, no write |
| Any target publish fails inside closure | transaction rollback; old active plan remains effective; failure is persisted/audited without partial activation |
| Publish retried with same key and same input | original plan/result returned |
| Same key with different input | 409 `[IDEMPOTENCY_KEY_REUSED]` |
| New Path published with active Enrollments | impact reports them; their frozen revision remains unchanged |
| Rollback target belongs to another Path/organization | hidden denial; no write; rejection audited |
| Direct publish tombstone called | 409 `[NEWCOMER_RELEASE_PLAN_REQUIRED]`; no domain publish call |

### 5. Good / Base / Bad Cases

- **Good**: one plan contains a working Source, approved Question, dependent LearningUnit and Quiz, then the Path; all publish atomically in dependency order and the exact active pointer changes once.
- **Base**: a new PathRevision publishes while 120 active Enrollments remain frozen on the prior revision; only future explicit Cohort binding or migration uses the new revision.
- **Bad**: a resource route publishes first, the Path route publishes later, a failure leaves half the graph effective, or rollback mutates old revision content.

### 6. Tests Required

- Unit: dependency closure/order, blocker classification, immutable target set and runtime/competency validation.
- Transaction integration: successful atomic closure, injected mid-closure failure keeps all old pointers, concurrent/stale publish and same-key replay.
- Rollback: preview/hash/version/reason, same-Path and cross-organization rules, frozen Enrollment behavior and audit history.
- Delivery: ReleasePlan route/DTO contract and direct publish tombstone assertions.
- Frontend: dependency/blocker/impact rendering, publish/rollback preview-confirm, conflict/permission/partial failure and persistent result location.

### 7. Wrong vs Correct

#### Wrong

```python
await learning.publish_resource(resource_id)
await path.publish_revision(path_revision_id)
```

Two independent commits create a partial release and bypass the frozen impact contract.

#### Correct

```python
preview = await release_plans.preview(
    actor=actor,
    path_revision_id=path_revision_id,
    reason=reason,
    idempotency_key=idempotency_key,
)
result = await release_plans.publish(
    actor=actor,
    release_plan_id=preview.release_plan_id,
    preview_token=preview.preview_token,
    impact_hash=preview.impact_hash,
    expected_version=preview.version,
    idempotency_key=idempotency_key,
)
```

The service owns one transaction, validates the frozen graph and changes formal authority only after the complete closure succeeds.

## 8. Legacy History Appendix (superseded, not runtime authority)

Historical source and audit tests may still describe `TrainingPathPayload.phases[].modules[].activities[]`, six Handler/Renderer types, `/admin/newcomer-training/path`, subtype learner routes, publish-time Enrollment movement, Journey self-heal and realtime binding snapshots. Their routers are no longer registered, are absent from OpenAPI and have no Foundation frontend consumers. Retained tables/services are read-only migration evidence; they do not authorize a writer or compatibility facade.

`docs/api-contract/sales-trainer.md` and ADRs dated 2026-07-12/13 are superseded for Foundation runtime design. Do not add target behavior to those structures or restore them to application composition.

Retirement owner and deadline are recorded in `docs/architecture/newcomer-foundation-clean-cut.md` and `newcomer-foundation-guard-policy.yaml`.

# Newcomer Training Activity Orchestration

## 1. Scope / Trigger

Use this contract whenever newcomer training paths, activities, enrollment progress, admin editing, in-flow scoring-standard binding, or a new execution capability changes. Business content such as product names, PPT/Demo topics, and technical courses is configuration data; it must not become a route, enum, `module_key`, or service branch.

## 2. Signatures

- Data hierarchy: `TrainingPathPayload.phases[].modules[].activities[]`.
- Activity types: `lesson`, `quiz`, `audio_assessment`, `realtime_roleplay`, `ai_coach`, `assignment`.
- Admin API root: `/api/v1/admin/newcomer-training/path`.
- Learner API root: `/api/v1/newcomer-training`.
- Audio scoring-standard administration:
  - `GET|POST /api/v1/admin/newcomer-training/path/scoring-rubrics`
  - `PUT /api/v1/admin/newcomer-training/path/draft`
  - `PUT /api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}`
  - `POST /api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}/publish`
- Enrollment uniqueness: one active row per `(learner_id, path_id)`; publish atomically moves every active enrollment to the new `path_revision_id`.
- Attempts are idempotent by `client_token` and freeze `activity_snapshot` plus result/evidence snapshots.
- `realtime_roleplay.config` may carry server-owned `practice_template_revision_id`, `practice_template_version`, `practice_template_content_hash`, `runtime_profile_snapshot_hash`, `governed_assets_snapshot_hash`, and learner-safe `runner_snapshot`; clients round-trip these fields but never author them.
- Readiness detail and workbench share `contract_version=readiness_dossier_v1`; review decisions are `approve`, `require_retraining`, or `mark_manual_follow_up` (legacy `reject`/`retrain` inputs normalize before persistence).

## 3. Contracts

- Only configuration and governed resource IDs may be stored. Never store code, component names, routes, URLs, scripts, or request definitions in path payloads.
- Draft save, validate, publish, restore, and high-risk resource creation require backend permission checks and audit records.
- Publish validates every referenced resource against the responsible module through adapters.
- Draft save freezes realtime template/runtime identity and learner preparation data into the path payload. Publish rejects a missing or stale freeze with `realtime_binding_snapshot_stale`; it never silently switches an already-saved path to a newer template/runtime.
- A learner's first journey read may create an enrollment; the API transaction must explicitly commit it because `get_db()` never auto-commits.
- Admin resource pickers use existing engines (`LearningContent`, papers, materials, rubrics, practice templates, runtime profiles, coach profiles). Content, papers, materials, and rubrics support safe in-flow creation; governed execution profiles are selectable here but must never be fabricated from placeholder defaults.
- Candidate validation is read-only. Candidate publish saves and activates one immutable revision in the same request transaction.
- Publish synchronizes all active enrollments in the same transaction and records `rollout_scope=all_active_learners` plus the affected count. Journey reads self-heal a stale active enrollment to the current published revision to cover publish/read races.
- Existing attempts never move with the enrollment: their `path_revision_id`, `activity_snapshot`, evidence, submissions, scores, and external bindings remain immutable historical evidence.
- Retrying one logical browser write reuses its `client_token` after a timeout or lost response. Rotate the token only after confirmed success or when the user changes the submitted input; a pending-button guard alone is insufficient.
- Readiness `GET /readiness/dossiers/{learner_id}` returns the full detail DTO (`path`, `status_label`, `status_reason`, `summary`, `modules`, `competencies`, `evidence`, `review_actions`, `retraining_tasks`, `realtime_gate`, `diagnostics`, `next_actions`). The workbench must derive its rows from the same projection.
- Draft save and candidate publish accept `expected_revision_id`; a mismatch returns `[NEWCOMER_PATH_REVISION_CONFLICT]` with HTTP 409 and never overwrites the newer revision.
- Journey module/activity projections carry configured `estimated_minutes`; only one activity is marked as the primary next action.
- Journey reads load the latest unified attempts for one enrollment as a single grouped projection and pass those frozen rows into handlers. Do not restore one `latest_for_activity` query per activity; handlers may query directly only for standalone activity execution contexts that were not preloaded.
- Admin journey **list** `GET /admin/newcomer-training/journeys` returns an explicit `summary` DTO per row (`path_revision_id`, `path_title`, `current_phase`, `progress`, `primary_next_action`, ≤2 `risk_labels`) via a batch read service. It must not call per-learner `get_or_create_for_learner()` or full `_project()`. List only includes learners that already have an enrollment; it must not bulk-create enrollments for team completeness. Commit only when a one-shot stale-revision heal actually wrote. Detail `GET .../journeys/{learner_id}` keeps full Journey + first-read create/heal semantics.
- Supervisor team **workbench** must use a light projection with SQL date bounds on task `created_at` / session `start_time`. Do not build full team insights then drop fields; do not per-learner score refresh. Keep risk fallback / common-issues semantics and parallel current+previous period calls for `/team` comparison UX.
- Learner-facing copy is controlled configuration, not presentation code: `PhaseConfig.outcome`, `ModuleConfig.outcome`, and activity `objective`, `why_it_matters`, `steps`, `success_criteria`, `primary_action_label` are optional additive fields in schema v1.
- Journey projections carry these fields unchanged. Old revisions return null/empty defaults and the frontend may apply trusted activity-type guidance; it must never execute or render HTML/CSS/script from configuration.
- `audio_assessment.config.example_transcript` is optional plain text (maximum 8,000 characters). Blank content normalizes to null. It is learner-facing configuration, not a prompt or scoring instruction.
- An audio activity detail projects one learner-safe preparation pack from governed resources: published material version metadata, the active scoring-rubric revision identity, rubric title, and normalized scoring focuses. Internal dimension keys and raw rubric JSON must never enter the learner UI.
- `audio_assessment.config.scoring_rubric_id` binds a published `SalesTrainerAudioScorePrompt.prompt_id` (field name kept for API compatibility). Path publish validation rejects legacy `audio_scoring_rubric` asset IDs with an actionable rebind message.
- Path `GET /scoring-rubrics` and the recording scoring-standard console must read the same `SalesTrainerAudioScorePrompt` authority. Path `POST /scoring-rubrics` creates and publishes that same resource from the minimum in-flow fields; it must not create a parallel rubric asset.
- After in-flow creation and binding, the editor must persist the updated `scoring_rubric_id` through `PUT /draft` and accept the returned working revision before reporting “草稿已保存”. A later path reload must recover the same binding from the service-side working revision.
- “去完善提示词” is a cross-surface continuation, not a disposable navigation shortcut. The browser window must be reserved synchronously from the user click, then navigate only after any required draft save succeeds; save failure, revision conflict, drawer close, or unmount must close the reserved window and expose a recoverable error.
- Updating a published audio score prompt writes a working revision; it does not make that revision runtime-effective by itself. The operator edit flow must perform `PUT` followed by `POST .../publish`, label the action “保存并发布”, and keep an inline outcome record. If publish fails after update succeeds, the UI must state that the previous published revision remains effective.
- `scoring_template` must contain `{transcript}` and must round-trip without client or API truncation. Runtime scoring replaces the placeholder with the submitted transcript and freezes the full prompt snapshot; later prompt publication must not mutate historical attempts.
- Audio submission may carry `confirmed_scoring_rubric_revision_id`. When present, the backend must verify that exact revision is published, has resource type `sales_trainer_audio_score_prompt`, and belongs to the configured prompt_id before freezing `prompt_id` + `prompt_snapshot`. Missing confirmation remains compatible with legacy clients by freezing the current published prompt; an invalid explicit revision never falls back silently.
- Material confirmation continues to freeze the exact published material version. A later material or rubric publication must not change historical submission evidence.
- Admin candidate preview and the real learner journey must adapt into the same learner mission ViewModel and render the same mission component.
- Alembic runs before application startup; `create_all` is bootstrap-only and must not precede pending migrations.

## 4. Validation & Error Matrix

| Condition | Behavior |
|---|---|
| Unsupported activity type or unknown config field | Reject the payload; do not ignore it |
| Duplicate IDs/order or invalid prerequisite | Validation issue blocks publish |
| Missing/draft/archived bound resource | Validation issue identifies object and field |
| No active published path | Journey returns `NEWCOMER_PATH_ACTIVE_REVISION_MISSING` |
| Enrollment revision missing | Journey returns `NEWCOMER_PATH_PINNED_REVISION_MISSING` |
| Duplicate enrollment request | Return the existing active enrollment |
| Duplicate activity `client_token` | Return the existing attempt/evidence |
| Same logical input retried after an uncertain client failure | Reuse the previous `client_token`; do not create a second attempt/session |
| Realtime runner snapshot missing or no longer matches the published template/runtime | Block path publish with `realtime_binding_snapshot_stale`; an already-published activity reports configuration unavailable and start returns `[NEWCOMER_REALTIME_PINNED_BINDING_STALE]` |
| Readiness review uses legacy `reject` or `retrain` | Normalize to `mark_manual_follow_up` or `require_retraining` before audit persistence and response |
| Concurrent draft/publish conflict | Fail explicitly; never overwrite silently |
| In-flow score prompt was created but the bound path draft save fails | Keep the editor state and created prompt truthful, do not navigate or claim the path binding was saved, and offer retry |
| Browser blocks the reserved “去完善提示词” window | Show a recoverable popup-blocked message; do not pretend that the edit page opened |
| Prompt update succeeds but prompt publication fails | Preserve the working revision, report partial failure inline, and state that the previous published revision is still effective |
| `scoring_template` omits `{transcript}` | Reject create/update with a typed prompt validation error; never publish an unusable scoring revision |
| Confirmed audio rubric revision is missing, unpublished, wrong type, or wrong logical resource | Return `[NEWCOMER_AUDIO_RUBRIC_VERSION_INVALID]` with HTTP 409; never substitute another revision |
| Provider unavailable | Keep evidence truthful and expose a retryable failure; never fabricate completion |

## 5. Good / Base / Bad Cases

- Good: an admin adds products A, B, and C with the same module/activity editor and no source change; publishing synchronizes every active learner while completed attempts retain their original snapshots.
- Good: an admin creates a minimal scoring standard inside the path, the path working revision persists the returned `prompt_id`, then “去完善提示词” opens the full editor; saving and publishing there makes the new revision available to future scoring while old attempts keep their snapshots.
- Good: path revision R1 keeps showing its frozen realtime preparation pack; after the template changes, R1 becomes explicitly unavailable until an admin saves and publishes a new path revision.
- Base: prompt update succeeds but publish fails; the working revision remains retryable and the UI clearly says the old published prompt still drives scoring.
- Bad: `if product == "PPT"`, fixed `module_key` branches, executable configuration, route redirects to a retired path, fallback to an old config authority, reading mutable current assets for a frozen path revision, claiming a path draft was saved before the server returns its working revision, or treating prompt `PUT` as publication.

## 6. Tests Required

- Contract validation and publish resource validation for all six activity types.
- Repository concurrency/idempotency and immutable revision tests.
- Repository tests prove the enrollment-level latest-attempt projection returns only the highest `attempt_no` per activity; journey tests cover the preloaded and standalone handler paths.
- Journey **list** performance/contract tests: SQL count stays O(1) vs returned row count (1/50/100), no N× full project, heal-once commit, summary↔full Journey parity for progress/next/risk on the same fixture.
- Workbench tests: captured SQL contains date predicates; query count does not grow linearly with 50/100/500-scope seeds under `limit=100` list semantics.
- Unit tests for every Handler plus unified registry completeness.
- Integration tests for admin draft/validate/publish/restore and learner journey/activity APIs.
- Reset dry-run/apply, seed idempotency, and verify-mode evidence.
- Frontend Vitest for editor state, in-flow resource creation, renderer registry, and one-primary-action projection.
- Frontend tests for synchronous popup reservation, draft-save-before-navigation, blocked popup recovery, save failure, and update-success/publish-failure messaging.
- Integration tests reload the path working revision after in-flow score-prompt creation and assert the same `scoring_rubric_id`; prompt revision tests assert long `scoring_template` content round-trips without truncation and becomes effective only after publish.
- Contract and frontend tests for learner-copy defaults, configured-copy round trips, and the shared admin/learner mission preview.
- Audio preparation tests for material metadata, learner-safe rubric normalization, configured/legacy example labels, confirmation gating, and exact material/rubric revision freezing.
- Realtime tests assert draft-time snapshot fields, learner-safe projection, stale-template rejection, start-binding audit metadata, and that a later template update never changes the old runner payload silently.
- Browser runner tests simulate “server accepted, response lost” and assert the retry sends exactly the same `client_token` for quiz, audio, assignment, lesson, AI coach, and realtime start.
- Readiness API integration tests validate the full `readiness_dossier_v1` detail payload and every review decision/response shape used by the frontend.
- Playwright for admin editor, learner journey, all-active enrollment rollout, and immutable attempt evidence.
- Alembic head, OpenAPI parity, Ruff, Mypy, TypeScript, ESLint, Vitest, and production build.

## 7. Wrong vs Correct

### Wrong

```python
if module_key == "ppt_explanation":
    return PptRecordingPage()
```

### Correct

```python
handler = activity_registry.require(activity.type)
return await handler.project(execution_context)
```

The stable registry selects execution capability; titles and product/topic identities remain data.

```python
# Wrong: a frozen path reads the mutable current template.
template = await db.get(PracticeTemplate, config.practice_template_id)

# Correct: learner display uses the path-owned snapshot and current assets are
# checked only to decide whether that frozen binding can still run safely.
runner = await realtime_runner_descriptor(db, config)
```

```typescript
// Wrong: after the await, browsers may no longer treat this as a user gesture.
await persistDraft()
window.open(editHref, "_blank")

// Correct: reserve the window synchronously, then navigate only after persistence.
const refineWindow = window.open("about:blank", "_blank")
await persistDraft()
refineWindow?.location.replace(editHref)
```

```typescript
// Wrong: updating a published prompt only saves a working revision.
await updateScorePrompt(promptId, payload)
showSuccess("已生效")

// Correct: publish explicitly, and distinguish partial failure.
await updateScorePrompt(promptId, payload)
await publishScorePrompt(promptId)
showSuccess("新修订已发布，后续评分将使用该版本")
```

# Newcomer Training Activity Orchestration

## 1. Scope / Trigger

Use this contract whenever newcomer training paths, activities, enrollment progress, admin editing, or a new execution capability changes. Business content such as product names, PPT/Demo topics, and technical courses is configuration data; it must not become a route, enum, `module_key`, or service branch.

## 2. Signatures

- Data hierarchy: `TrainingPathPayload.phases[].modules[].activities[]`.
- Activity types: `lesson`, `quiz`, `audio_assessment`, `realtime_roleplay`, `ai_coach`, `assignment`.
- Admin API root: `/api/v1/admin/newcomer-training/path`.
- Learner API root: `/api/v1/newcomer-training`.
- Enrollment uniqueness: one active row per `(learner_id, path_id)`; `path_revision_id` is immutable after creation.
- Attempts are idempotent by `client_token` and freeze `activity_snapshot` plus result/evidence snapshots.

## 3. Contracts

- Only configuration and governed resource IDs may be stored. Never store code, component names, routes, URLs, scripts, or request definitions in path payloads.
- Draft save, validate, publish, restore, and high-risk resource creation require backend permission checks and audit records.
- Publish validates every referenced resource against the responsible module through adapters.
- A learner's first journey read may create an enrollment; the API transaction must explicitly commit it because `get_db()` never auto-commits.
- Admin resource pickers use existing engines (`LearningContent`, papers, materials, rubrics, practice templates, runtime profiles, coach profiles). Content, papers, materials, and rubrics support safe in-flow creation; governed execution profiles are selectable here but must never be fabricated from placeholder defaults.
- Candidate validation is read-only. Candidate publish saves and activates one immutable revision in the same request transaction.
- Draft save and candidate publish accept `expected_revision_id`; a mismatch returns `[NEWCOMER_PATH_REVISION_CONFLICT]` with HTTP 409 and never overwrites the newer revision.
- Journey module/activity projections carry configured `estimated_minutes`; only one activity is marked as the primary next action.
- Learner-facing copy is controlled configuration, not presentation code: `PhaseConfig.outcome`, `ModuleConfig.outcome`, and activity `objective`, `why_it_matters`, `steps`, `success_criteria`, `primary_action_label` are optional additive fields in schema v1.
- Journey projections carry these fields unchanged. Old revisions return null/empty defaults and the frontend may apply trusted activity-type guidance; it must never execute or render HTML/CSS/script from configuration.
- Admin candidate preview and the real learner journey must adapt into the same learner mission ViewModel and render the same mission component.
- Alembic runs before application startup; `create_all` is bootstrap-only and must not precede pending migrations.

## 4. Validation & Error Matrix

| Condition | Behavior |
|---|---|
| Unsupported activity type or unknown config field | Reject the payload; do not ignore it |
| Duplicate IDs/order or invalid prerequisite | Validation issue blocks publish |
| Missing/draft/archived bound resource | Validation issue identifies object and field |
| No active published path | Journey returns `NEWCOMER_PATH_ACTIVE_REVISION_MISSING` |
| Pinned revision missing | Journey returns `NEWCOMER_PATH_PINNED_REVISION_MISSING` |
| Duplicate enrollment request | Return the existing active enrollment |
| Duplicate activity `client_token` | Return the existing attempt/evidence |
| Concurrent draft/publish conflict | Fail explicitly; never overwrite silently |
| Provider unavailable | Keep evidence truthful and expose a retryable failure; never fabricate completion |

## 5. Good / Base / Bad Cases

- Good: an admin adds products A, B, and C with the same module/activity editor and no source change; existing learners stay on their pinned revision.
- Base: an optional activity is unavailable and the journey explains its state without changing required progress.
- Bad: `if product == "PPT"`, fixed `module_key` branches, executable configuration, route redirects to a retired path, or fallback to an old config authority.

## 6. Tests Required

- Contract validation and publish resource validation for all six activity types.
- Repository concurrency/idempotency and immutable revision tests.
- Unit tests for every Handler plus unified registry completeness.
- Integration tests for admin draft/validate/publish/restore and learner journey/activity APIs.
- Reset dry-run/apply, seed idempotency, and verify-mode evidence.
- Frontend Vitest for editor state, in-flow resource creation, renderer registry, and one-primary-action projection.
- Contract and frontend tests for learner-copy defaults, configured-copy round trips, and the shared admin/learner mission preview.
- Playwright for admin editor, learner journey, and immutable enrollment closed loop.
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

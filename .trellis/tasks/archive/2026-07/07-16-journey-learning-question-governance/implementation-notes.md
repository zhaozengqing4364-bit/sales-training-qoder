# Implementation Notes — Journey / Learning / Question Governance

## Scope Contract

- Target users: learner completing the newcomer foundation path; training administrator governing path, learning content, questions, and quizzes.
- Primary learner flow: one `/newcomer-training` entry projects the learner's frozen `PathRevision`, exposes one primary next action, and executes lesson/quiz commands without leaving the journey.
- Primary administrator flow in this slice: create immutable source/learning/question/quiz revisions, review AI-produced question candidates, publish governed revisions, enroll learners, and explicitly preview/confirm revision migrations. The full unified admin workspace and release-plan UX remain slice 6.
- Formal write authorities:
  - `newcomer_training`: Path/PathRevision, Cohort, Enrollment, generic ActivityAttempt, Journey projection.
  - `learning`: SourceDocumentRevision, LearningUnitRevision, QuestionGenerationBatch/Candidate, Question/QuestionRevision, Quiz/QuizRevision and lesson/quiz detail outcomes.
  - durable `tasks` runtime owns execution state; AI platform owns governed invocation records only.
- Scope exclusions: audio assessment implementation, AI Coach implementation, competency readiness, realtime roleplay, full visual redesign, and unrelated legacy cleanup.

## Repository Facts Before Implementation

- The current path is a legacy `SalesTrainerAssetRevision` JSON payload shaped `Phase -> Module -> Activity`; publish calls `EnrollmentRepository.sync_active_path_revision` and silently migrates every active enrollment.
- `EnrollmentRepository.get_or_create` also rewrites an existing enrollment to the newest published revision, violating frozen assignment semantics.
- Current generic attempts persist an activity snapshot and evidence fields, but idempotency is only a global client token and there is no normalized outcome reference contract.
- Current learner Journey is projected from legacy phases/modules and directly reaches legacy lesson/quiz services.
- Current activity union still includes `realtime_roleplay`; the target closed union is `lesson | quiz | audio_assessment | ai_coach | assignment`.
- Current question generation saves generated drafts directly as formal `QuestionItem` rows. The target pipeline must stop at `QuestionCandidate` until deterministic gates and human approval create an immutable `QuestionRevision`.
- No target `newcomer_training` or `learning` package exists. New deep modules minimize overlap with the heavily modified legacy worktree and establish the target ownership seams without permanent cross-domain ORM use.
- Slice 1 already provides durable task runtime, AI invocation governance, stable public ports, migration head `20260716_2300_002`, and authoritative model registration.

## Implementation Plan

1. Add failing contract/domain tests for immutable revisions, frozen enrollment, explicit idempotent migration, typed path activities, Journey primary-action/gates, unified attempt snapshots/outcome references, and organization/permission/stale-write rejection.
2. Implement the `newcomer_training` deep module and migration: typed contracts and state machines, ORM models, repositories, application services, delivery routers, and root composition. Use explicit dependency ports for learning activity execution.
3. Add failing learning-governance tests for source anchors, immutable learning revisions, candidate-only AI generation, deterministic gates plus human approval, immutable question/quiz revisions, frozen quiz attempt snapshots, deterministic grading, and asynchronous short-answer pending/failure behavior.
4. Implement the `learning` deep module, durable question-generation and short-answer task handlers, governed AI invocation adapter, stable standard-pack seed/verify command, and lesson/quiz adapters registered at the composition root.
5. Replace the learner route and required API contracts with the new Journey authority; retire legacy path/question write routes and realtime newcomer registration only after the new path works end-to-end. Preserve read-only history only where the frozen clean-cut contract permits it.
6. Run only slice-focused static checks, unit/contract tests, PostgreSQL integration tests, migration round-trip, seed verify, targeted frontend tests/type checks, and CodeGraph affected checks. Update OpenAPI, ADR/spec/API/runbook evidence, close every slice acceptance criterion, run Trellis check, and finish without commit.

## Success Evidence Required

- Publishing a new path never changes an existing enrollment; migration requires preview plus confirm, is permission-scoped, stale-safe, idempotent, audited, and reports per-enrollment failures.
- Journey uses only the enrollment's frozen revision, returns one primary action and complete lock/remediation/retry/stale states, and has a single learner entry.
- Lesson progress supports save/resume/checkpoint/complete/invalidate/relearn with explicit lifecycle states.
- AI question generation creates candidates only; deterministic gates and an authorized human decision are prerequisites for a formal immutable question revision.
- Quiz attempts freeze question/rule snapshots; objective scoring is deterministic; short-answer AI scoring is durable and a failed task never becomes completed.
- The idempotent standard pack covers all seven foundation competencies and passes verify-only mode.
- Legacy auto-migration, duplicate learner entry, old formal question writer, and realtime newcomer path surface are no longer writable/reachable.

## Minimal Verification / Rollback

- Verification: modified-file Ruff/mypy; focused backend unit/contract/PostgreSQL tests; migration upgrade/downgrade/upgrade; standard-pack seed twice plus verify-only; targeted frontend unit/type checks for changed files; OpenAPI contract assertions; CodeGraph impact/affected.
- No full repository test/build/format in slice 2. Full quality gates are reserved for slice 8 unless a changed global seam makes a narrower proof impossible.
- Rollback: disable/register old router only through deployment rollback, downgrade the slice migration after confirming no target writes must be retained, and restore the previous application artifact. Published immutable records are not mutated in-place.

## Deviations, Conservative Assumptions, and Historical Issues

- The worktree contains extensive user-owned changes, including overlapping legacy newcomer/curriculum/frontend files. New modules are preferred; every overlapping file is read with callers before a minimal patch. No unrelated change will be reset or reformatted.
- Older documents reference missing `.kiro/steering/*-principles.md`; current `AGENTS.md`, `DESING.md`, Trellis specs, and frozen parent contracts are treated as authoritative. This documentation gap is not repaired in this slice.
- Full release-plan orchestration and polished unified admin workspace are intentionally deferred to slice 6; full learner responsive/performance hardening is deferred to slice 7. Slice 2 still supplies working APIs and the minimal coherent learner/admin interactions required by its acceptance criteria.
- No commit, push, or PR is authorized by the GOAL.

## Implemented Result (2026-07-17)

- Added the `newcomer_training` and `learning` authorities, their SQLAlchemy models, migration `b9fc04c1ad65`, root composition, learner/admin routers, frozen revision services, Journey/workspace projections, Lesson/Quiz runtimes, candidate governance, standard pack and durable task handlers.
- Trellis cross-layer review found that the first draft placed the cross-domain admin delivery and standard-pack installer inside `newcomer_training`. They were moved to `foundation_admin_api.py`, `foundation_admin_permissions.py` and `foundation_standard_pack.py`; a source import check now proves neither domain package imports the other's ORM/application implementation.
- New learner namespace exposes only Journey, Activity Workspace, unified Activity commands and owned Task status/cancel. Workspace reads enforce Enrollment, Stage and prerequisite gates and perform no implicit enrollment, attempt creation or revision migration.
- Path publication no longer changes existing Enrollments. Explicit migration persists a preview with impact hash and expiry, requires capability/reason/version/confirm, returns per-item failures, and writes audit plus `EnrollmentRevisionMigrated` Outbox in the same transaction.
- Question generation and short-answer scoring now execute through the production governed AI composition. OpenAI-compatible `openai`/`alibaba` connections fail closed, receive only the strictly compiled published Prompt, carry idempotency/trace headers, classify timeout/rate-limit/unavailable/invalid JSON, and record usage/cost. Registered schema versions are `question-generation-input-v1`, `question-generation-output-v1`, `short-answer-input-v1`, and `short-answer-output-v1`; Prompt hashes are `sha256:<64 lowercase hex>`.
- Candidate generation receives the complete learning-unit content and source anchors. Short-answer scoring receives the frozen prompt/rubric and learner answer. Neither path allows Provider output to become a formal question or completed outcome without schema/governance checks.
- Learner UI uses the current design foundation and one canonical entry. Quiz start now discloses server-projected count, threshold, attempts, retry wait, duration and time limit. The admin resource library exposes only Slice 2 governed learning/question scopes; the retired legacy Path page redirects there, and Realtime/AI Coach/legacy writers are absent from launch navigation.
- The deterministic standard pack covers the seven frozen competencies, contains no Realtime activity, detects drift, and preserves stable IDs/revisions across repeat install and verify-only.

## Time-bounded Deviations / Later-slice Owners

- Slice 2 exposes direct Path/resource publish commands only to make the Lesson/Quiz vertical slice independently operable. Slice 6 owns ReleasePlan atomic publication and must delete those two transitional commands after consumer cutover; they are not a compatibility authority.
- The old `path-page-client.tsx` and editor components remain as unreachable source files because deleting broad legacy UI is Slice 8 cleanup. The mounted page redirects and the backend legacy writers are unmounted, so they are not reachable write authorities.
- A real external Provider network call was not executed because this workspace does not supply an authorized test credential or disposable Provider account. Production composition, request shape, failure classifications and both supported provider configurations are covered with deterministic adapters; deployment smoke remains an environment validation.
- CodeGraph's current index predates the new untracked modules, so impact output covers edited indexed frontend callers but cannot enumerate the new backend files. Source imports, route contracts, focused tests and PostgreSQL integration provide the slice evidence; re-indexing is not performed because indexing is user-owned.

## Verification Evidence So Far

- Focused backend unit/contract suite: `60 passed` for `tests/unit/newcomer_training`, `tests/unit/learning`, the production provider/composition tests and Worker service tests.
- Focused backend Ruff: all checks passed for the new AI, learning, newcomer-training, composition, Worker, migration and related unit/integration paths.
- Focused backend mypy: `Success: no issues found in 46 source files`; fixes use typed narrowing and explicit dynamic SQLAlchemy boundaries rather than ignore comments.
- PostgreSQL migration/runtime/seed suite: `3 passed`; proves upgrade/downgrade/upgrade, Alembic drift check, concurrent Attempt start, frozen quiz snapshot, duplicate submit, partial/idempotent Enrollment migration, and repeat install plus verify-only on a clean isolated schema.
- Post-boundary-move regression: `12 passed` for the moved foundation admin API, permissions, standard-pack installer and route contract; the isolated PostgreSQL suite was rerun and remained `3 passed`.
- Shared API/application/OpenAPI regression selected for the edited response/router seams: `17 passed` across response envelopes, app factory, generated OpenAPI contract and newcomer route contract.
- Focused frontend Vitest: `5 files / 20 tests passed` for Quiz disclosure, resource library, admin sidebar/shell and retired Path redirect. Targeted ESLint passed for the same changed surface.
- CodeGraph `affected` selected four additional frontend callers; their `16` tests passed. A further seven clean-cut/Journey/Lesson/API presenter files ran `20` passing tests.
- The first PostgreSQL invocation used the placeholder URL from `alembic.ini` and failed authentication before schema creation. It made no database changes and was rerun with the workspace's configured development URL against per-test isolated schemas; the rerun passed.
- An attempted CLI subprocess against the isolated test schema used a libpq-style `options` URL parameter that asyncpg does not accept; it failed before any seed write. The maintained PostgreSQL test therefore invokes the same seed service through the isolated engine, while the CLI wrapper remains covered by its previously successful local idempotency/verify run. Supporting arbitrary test `search_path` URL parameters is outside the product CLI contract and was not added.
- The accepted newcomer guard policy is explicitly `design_only_not_enforced` until Slice 8. Passing it to the current legacy architecture-guard CLI therefore fails schema validation before scanning code; this is not repaired in Slice 2. The current slice instead enforces the intended boundary with direct import inventory, ports, mypy and integration tests; Slice 8 owns wiring the new policy into the canonical guard.

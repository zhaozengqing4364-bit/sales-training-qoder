# Sales Training Full Learning Examiner Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the full Sales Training learning and AI examiner loop from structured lecture content to learner study, question bank, AI exam runtime, frontend exam experience, reports, validation, and COO delivery pack.

**Architecture:** Extend the existing `curriculum_practice` deep module with `LearningContent`, `TestBank`, `LearnerProfile`, and runtime snapshot bindings while preserving the current `PracticeSession` and `TrainingTask` state machines. Add `ExaminerAgent` as an isolated Agent interaction mode under `agent/`, with WebSocket runtime in `backend/src/agent/websocket/examiner_handler.py`, never inside `sales_bot/`. All runtime reads use frozen `RuntimeSnapshotService` output, not latest admin content.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, Result[T], structlog, pytest, ruff, Next.js 16, React 19, TypeScript 5, Vitest, Playwright, Tailwind 4, existing UI components.

---

## Source Read Note

Read successfully: PRD file, root `CLAUDE.md`, `.kiro/steering/backend-principles.md`, `.kiro/steering/frontend-principles.md`, `.kiro/steering/QUICK-REFERENCE.md`, `docs/api-contract/README.md`, `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, key ADRs, issue #65 and issues #66-#77 full bodies.

Could not read because files do not exist in this checkout: `docs/architecture.md`, `docs/roadmap/backend-gap-analysis.md`, `docs/roadmap/sales-coach-upgrade.md`.

## Critical Constraints

- All user-facing backend operations return `Result[T]`; do not expose naked exceptions.
- Do not use `print()`; use existing logger/structlog.
- Do not create `SessionV2`.
- Do not extend `PracticeSession.status` or `TrainingTask.status`.
- Do not change `User.role` DB constraints; use action-level RBAC and department-scope checks.
- Do not recalculate historical reports or mutate old report snapshots.
- Runtime must read frozen `RuntimeSnapshotService` snapshots, never latest learning content, latest questions, or latest examiner config.
- `ExaminerAgent` must remain isolated from `sales_bot`; no imports from `sales_bot` internals for examiner runtime.
- Add examiner WebSocket handling at `backend/src/agent/websocket/examiner_handler.py`.
- `BaseWebSocketHandler.on_connect` must be default no-op and preserve existing sales/presentation behavior.
- Feature flag `curriculum.examiner` gates rollout; disabled state displays `即将上线`.
- Reuse existing UI: `DashboardShell`, `GlassCard`, `Button`, `EmptyState`, `ChatBubble`, `AudioVisualizer`, `GlassSheet`, `ErrorBoundary`, `StatusIndicator`, `ResponsiveTableWrapper`, `MobileTableCard`.
- No new design tokens, no new third-party component library, no `alert()`.
- Mobile study page uses top `<select>` for chapter switching.
- Mobile examiner right panel collapses into bottom `GlassSheet`.
- TypeScript: no `as any`, no `@ts-ignore`, no `@ts-expect-error`.
- Asset references must stay DRY: extract a shared `AssetRef` schema/interface pattern and reuse it for `LearningContentRef` and `TestBankRef`; do not duplicate `asset_type/asset_id/version/hash/snapshot_label` logic across content and question-bank snapshots.
- Examiner runtime must prewarm the first-question path in #75, not defer it to #77: load frozen snapshot assets and prepare/render the examiner prompt before sending the first `exam.question`, so #77 can measure first-question latency after prewarm.
- `ExaminerSessionState` persistence must be decided in the first #75 implementation commit; default recommendation is a DB-backed state table/model for reconnect/idempotency unless existing runtime evidence proves a simpler persisted JSON field is safer.
- CSV import supports RFC 4180 CSV plus JSONL, 10MB limit, background task.
- External blocker: 昱博的“大类→子类→考察维度”分类体系 affects final taxonomy and business scoring labels only; it must not block #69 technical tree/category construction.

## Issue Summary

| Issue | One-Sentence Summary |
|---|---|
| #66 | Add the minimal WebSocket `on_connect` infrastructure and `curriculum.examiner` feature flag without changing existing handler behavior. |
| #67 | Build admin LearningContent and chapter management with publish/archive gates and seed-data accountability. |
| #68 | Build learner lecture reading, progress tracking, and LearningPath/Dashboard study-state transitions. |
| #69 | Build TestBank category and question lifecycle foundation with flexible tree categories and publish gates. |
| #70 | Build CSV/JSONL background import for TestBank with structured validation and row-level errors. |
| #71 | Generate editable QuestionItem drafts from lecture chapters using LLM infrastructure and safety checks. |
| #72 | Add LearnerProfile, bind learning/exam assets into PracticeTemplate/CurriculumPlan, and freeze study/exam runtime snapshots. |
| #73 | Add department-scoped batch assignment for full study/exam/practice templates with idempotent skip behavior. |
| #74 | Add admin ExaminerAgent config CRUD, publish gates, and simulation testing. |
| #75 | Add server-driven AI examiner WebSocket runtime with scoring, timeout, duplicate/out-of-order handling, reconnect, and report writes. |
| #76 | Add learner AI exam frontend with WebSocket flow, timers, feedback, reconnect states, mobile layout, and completion view. |
| #77 | Execute final E2E, security, performance, baseline, documentation, screenshots/GIFs, deployment notes, and COO demo acceptance gate. |

## Acceptance Criteria Summary

| Issue | Acceptance Criteria Summary |
|---|---|
| #66 | `BaseWebSocketHandler` has default no-op `on_connect`; sales and presentation WebSocket contracts do not regress; `curriculum.examiner` flag is readable by backend/frontend; tests cover default, override, and enabled/disabled flag reads. |
| #67 | Admin can CRUD/publish/archive LearningContent and chapters; publish rejects no chapters, empty chapters, non-contiguous order, security flags; admin UI supports list/detail/edit/chapter operations and empty/error states; seed-data owner/source/import path recorded; backend and frontend tests cover lifecycle and UI states. |
| #68 | Learner can read lectures, switch chapters, view progress, mark complete; progress API is current-user scoped and idempotent; LearningPath/Dashboard CTAs reflect study state; tests cover loading/empty/error/partial/mobile, transitions, and IDOR. |
| #69 | Admin can manage category tree safely; admin can CRUD/filter/publish/archive questions; publish rejects missing reference answer, invalid scoring dimensions, security flags; tests cover tree, lifecycle, filters, gates, version/snapshot immutability, and shared `AssetRef` reuse for `LearningContentRef`/`TestBankRef`. |
| #70 | CSV supports RFC 4180 escaped single-line content; JSONL supports multi-line Markdown; import validates size, encoding, required fields, category, difficulty, dimensions; background task returns result; admin UI shows counts and row errors; tests cover valid, mixed invalid, oversize, encoding, CSV escaping, JSONL errors, frontend error table. |
| #71 | Admin can trigger AI question generation from lecture chapters and edit preview drafts; saving creates draft QuestionItems with source chapter data; malformed/empty/injection outputs produce actionable errors and do not auto-save; tests cover normal, malformed JSON, empty, safety rejection, edited preview save. |
| #72 | LearnerProfile supports self-assessment, admin override, conservative default; PracticeTemplate binds learning content, examiner agent, learner level, timeout; CurriculumPlan `stage_type` supports `study/exam/practice/report`; publish gates validate published references; RuntimeSnapshot freezes study/exam assets and preserves historical sessions. |
| #73 | `POST /api/v1/training-tasks/batch-assign` accepts `user_ids`, `template_id`, `curriculum_plan_id`; returns assigned/skipped/failed with reasons; duplicate template assignment is skipped idempotently; department scope blocks cross-department assignment; admin UI supports filter/select/assign/result display; tests cover all. |
| #74 | Admin can manage ExaminerAgent configs through API/UI; publish rejects empty sources, unpublished questions, invalid scoring policy, security flags; simulation endpoint runs without writing learner certification records; tests cover CRUD, gates, learner-level policy, simulation, snapshot immutability. |
| #75 | WebSocket prewarms frozen snapshot assets and the first-question prompt before sending `session.init` and first `exam.question` in `on_connect`; accepts only current `active_question_index`; ignores duplicate/out-of-order answers; emits feedback, next question, completion; `ExaminerSessionState` supports reconnect and no rescore; AI scoring uses frozen criteria and degrades safely; tests cover normal, empty bank, prewarm, wrong index, duplicate, timeouts, reconnect, completion idempotency. |
| #76 | ExamPage handles connecting, first question, answer submit, feedback, next question, complete; shows progress, remaining time, scored questions, final result; disconnect/reconnect, voice fallback, empty bank, feature flag off all have clear UI; mobile uses bottom `GlassSheet`; tests cover mocked WebSocket, key states, and TypeScript strict validation with no suppression comments or `as any`. |
| #77 | E2E covers study-to-exam-to-report-to-dashboard and import-to-bind-to-exam; security covers IDOR, prompt injection, Markdown XSS, batch assignment RBAC; seed data validates 7 chapters and 20 questions across 3+ dimensions; performance covers first question <300ms, scoring <2s, import concurrency within 10MB; baseline collection and regression checks pass; deliver Swagger/API docs, screenshots/GIFs, deployment notes, known issues, COO demo script. |

## Per-Issue File/Module Map

| Issue | Existing Files / Hotspots | New Files |
|---|---|---|
| #66 | ★ `backend/src/common/websocket/base_handler.py`; `backend/tests/unit/test_websocket_handler.py`; `backend/tests/integration/test_websocket_status_contract.py`; ★ `backend/src/common/config.py`; ★ `web/src/lib/api/*` | + `backend/tests/unit/test_websocket_on_connect.py`; + `backend/tests/unit/test_curriculum_examiner_feature_flag.py` |
| #67 | ★ `backend/src/curriculum_practice/models.py`; `backend/src/curriculum_practice/schemas.py`; `backend/src/curriculum_practice/api.py`; ★ `backend/alembic/versions/`; `backend/src/router_registry.py`; `web/src/components/layout/admin-shell.tsx`; `web/src/components/ui/*` | + `backend/src/curriculum_practice/services/learning_content_service.py`; + `backend/src/curriculum_practice/services/content_security.py`; + `backend/tests/integration/test_learning_content_api.py`; + `web/src/app/admin/learning-contents/page.tsx`; + `web/src/app/admin/learning-contents/[contentId]/page.tsx`; + `web/src/lib/api/learning-content.ts`; + `web/src/lib/api/learning-content.test.ts` |
| #68 | ★ `backend/src/curriculum_practice/api.py`; `backend/src/curriculum_practice/services/*`; `backend/tests/integration/test_learning_path_flow.py`; `backend/tests/contract/test_learning_path_api_contract.py`; `web/src/components/layout/dashboard-shell.tsx`; `web/src/components/ui/*` | + `backend/src/curriculum_practice/services/learning_progress_service.py`; + `backend/tests/integration/test_learning_progress_api.py`; + `backend/tests/contract/test_learner_study_api_contract.py`; + `web/src/app/(user)/study/[learningContentId]/page.tsx`; + `web/src/lib/api/learner-study.ts`; + `web/src/lib/api/learner-study.test.ts` |
| #69 | ★ `backend/src/curriculum_practice/models.py`; ★ `backend/src/curriculum_practice/schemas.py` (`AssetRef`, `LearningContentRef`, `TestBankRef`); ★ `backend/alembic/versions/`; `backend/src/curriculum_practice/api.py`; `backend/tests/integration/test_curriculum_snapshot_immutability.py`; ★ `web/src/lib/api/types.ts` (`AssetRef` frontend interface) | + `backend/src/curriculum_practice/services/test_bank_service.py`; + `backend/tests/unit/test_asset_ref_schema.py`; + `backend/tests/integration/test_test_bank_api.py`; + `backend/tests/contract/test_test_bank_api_contract.py`; + `web/src/app/admin/test-bank/page.tsx`; + `web/src/app/admin/test-bank/questions/[questionId]/page.tsx`; + `web/src/lib/api/test-bank.ts` |
| #70 | ★ `backend/src/curriculum_practice/services/test_bank_service.py`; `backend/src/curriculum_practice/api.py`; background task pattern to confirm in repo; `web/src/components/ui/responsive-table-wrapper.tsx`; `web/src/components/ui/mobile-table-card.tsx` | + `backend/src/curriculum_practice/services/test_bank_importer.py`; + `backend/tests/unit/test_test_bank_importer.py`; + `backend/tests/integration/test_test_bank_import_api.py`; + `web/src/app/admin/test-bank/import/page.tsx`; + `web/src/lib/api/test-bank-import.ts`; + `web/src/lib/api/test-bank-import.test.ts` |
| #71 | ★ `backend/src/curriculum_practice/services/learning_content_service.py`; ★ `backend/src/curriculum_practice/services/test_bank_service.py`; `backend/src/common/ai/*`; `backend/src/prompt_templates/*`; `web/src/app/admin/learning-contents/[contentId]/page.tsx` | + `backend/src/curriculum_practice/services/question_generation_service.py`; + `backend/tests/unit/test_question_generation_service.py`; + `backend/tests/integration/test_question_generation_api.py`; + `web/src/components/admin/question-generation-preview.tsx`; + `web/src/components/admin/question-generation-preview.test.tsx` |
| #72 | ★ `backend/src/curriculum_practice/models.py`; ★ `backend/src/curriculum_practice/schemas.py`; ★ `backend/src/curriculum_practice/services/snapshots.py`; ★ `backend/src/curriculum_practice/services/session_snapshots.py`; ★ `backend/alembic/versions/`; `backend/tests/unit/test_curriculum_runtime_snapshot_service.py`; `backend/tests/integration/test_curriculum_practice_session_snapshot.py` | + `backend/src/curriculum_practice/services/learner_profile_service.py`; + `backend/tests/integration/test_learner_profile_api.py`; + `backend/tests/unit/test_runtime_snapshot_study_exam_assets.py` |
| #73 | ★ `backend/src/common/api/training_tasks.py`; `backend/src/common/training_tasks/schemas.py`; ★ `backend/src/common/db/models.py`; `backend/tests/contract/test_training_tasks.py`; `web/src/components/layout/admin-shell.tsx` | + `backend/src/common/training_tasks/batch_assignment_service.py`; + `backend/tests/integration/test_training_task_batch_assign.py`; + `web/src/app/admin/training-tasks/batch-assign/page.tsx`; + `web/src/lib/api/training-task-batch.ts`; + `web/src/lib/api/training-task-batch.test.ts` |
| #74 | ★ `backend/src/agent/models.py`; `backend/src/agent/schemas.py`; `backend/src/agent/api/agents.py`; ★ `backend/src/curriculum_practice/models.py`; `backend/src/curriculum_practice/services/test_bank_service.py`; `web/src/app/admin/agents/*` | + `backend/src/agent/api/examiners.py`; + `backend/src/agent/services/examiner_config_service.py`; + `backend/tests/integration/test_examiner_agent_api.py`; + `web/src/app/admin/examiners/page.tsx`; + `web/src/app/admin/examiners/[examinerId]/page.tsx`; + `web/src/lib/api/examiners.ts` |
| #75 | ★ `backend/src/common/websocket/base_handler.py`; ★ `backend/src/agent/websocket/`; ★ `backend/src/websocket_routes.py`; ★ `backend/src/curriculum_practice/services/snapshots.py`; `backend/src/evaluation/*`; `backend/src/supervisor/*`; `backend/tests/e2e/test_websocket_flow.py`; `backend/tests/unit/test_websocket_handler.py`; reference warmup pattern: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` `_maybe_start_kb_lock_warmup()` / `_run_kb_lock_warmup()` (pattern only; do not import `sales_bot`) | + `backend/src/agent/websocket/examiner_handler.py`; + `backend/src/agent/services/examiner_runtime_service.py`; + `backend/src/agent/services/examiner_prewarm_service.py`; + `backend/src/agent/services/examiner_scoring_service.py`; + `backend/src/agent/models.py` additions for explicit `ExaminerSessionState` persistence decision; + `backend/tests/integration/test_examiner_websocket_runtime.py`; + `backend/tests/contract/test_examiner_websocket_contract.py`; + `backend/tests/unit/test_examiner_prewarm_service.py` |
| #76 | ★ `web/src/hooks/use-practice-websocket.ts`; `web/src/app/(user)/practice/[sessionId]/*`; `web/src/components/ui/chat-bubble.tsx`; `web/src/components/ui/audio-visualizer.tsx`; `web/src/components/ui/glass-sheet.tsx`; `web/src/components/ui/status-indicator.tsx`; `web/src/components/layout/dashboard-shell.tsx` | + `web/src/app/(user)/exam/[sessionId]/page.tsx`; + `web/src/hooks/use-examiner-websocket.ts`; + `web/src/hooks/use-examiner-websocket.test.ts`; + `web/src/components/examiner/exam-progress-panel.tsx`; + `web/src/components/examiner/exam-progress-panel.test.tsx`; + `web/src/lib/api/examiner-session.ts` |
| #77 | ★ `backend/tests/e2e/`; ★ `backend/tests/performance/`; ★ `web` Playwright tests; `docs/api-contract/`; `backend/src/admin/api/release_verification.py`; `docs/superpowers/plans/` | + `backend/tests/e2e/test_sales_training_learning_examiner_flow.py`; + `backend/tests/performance/test_examiner_runtime_performance.py`; + `web/tests/e2e/sales-training-learning-examiner.spec.ts`; + `docs/api-contract/learning-content.md`; + `docs/api-contract/test-bank.md`; + `docs/api-contract/examiners.md`; + `docs/delivery/sales-training-learning-examiner-coo-demo.md`; + `docs/delivery/sales-training-learning-examiner-deployment.md` |

## DB Migration Ordering

- Current migration base includes `practice_templates`, `case_items`, `role_profiles`, `practice_sessions.curriculum_snapshot`, and `practice_templates.curriculum_plan`.
- Phase 1 Lane A and Lane B both touch ★ `backend/src/curriculum_practice/models.py` and ★ `backend/alembic/versions/`; coordinate before merging.
- Lane A migration order: `066 feature flag config if persisted` -> `067 LearningContent/LearningChapter/LearningProgress tables` -> `068 any learner progress indexes or constraints`.
- Lane B migration order: `069 QuestionCategory/QuestionItem/ScoringDimension or JSON criteria tables` -> `070 import task/result storage if not using existing task infrastructure`.
- Coordination rule: Lane A should land first or reserve the next Alembic revision number; Lane B must rebase after Lane A and regenerate migration heads to avoid parallel heads.
- Phase 2 migration order after merge: `072 LearnerProfile + PracticeTemplate bindings + CurriculumPlan stage_type schema-compatible fields + snapshot schema support` -> `073 batch assignment indexes if needed` -> `074 ExaminerAgent config tables/fields`.
- Phase 3 migration order: `075 ExaminerSessionState persistence` -> `076 no DB migration unless frontend needs route-independent persisted preferences` -> `077 seed/e2e fixtures only`.
- Verification after each migration-producing issue: run from `backend`: `alembic upgrade head`.
- Expected: exits 0, one linear Alembic head, no check constraint changes to `PracticeSession.status`, `TrainingTask.status`, or `User.role`.

## Dependency Graph

```text
Phase 1 Lane A: #66 -> #67 -> #68
Phase 1 Lane B: #69 -> #70
Phase 2 after merge: #71 depends on #67 + #69
Phase 2 after merge: #72 depends on #66 + #67 + #69
Phase 2 after #72: #73 depends on #72
Phase 2 after #69 + #72: #74 depends on #69 + #72
Phase 3 serial: #75 depends on #66 + #72 + #74
Phase 3 serial: #76 depends on #75
Phase 3 serial: #77 depends on #66-#76
```

## Phased Execution Plan

| Phase | Work | Parallelism |
|---|---|---|
| Phase 0 | Record baseline, confirm current migration head, confirm existing tests collect. | Single read-only/prep pass. |
| Phase 1 Lane A | #66, #67, #68. | Can run in worktree A. |
| Phase 1 Lane B | #69, #70. | Can run in worktree B, but coordinate migration head with Lane A. |
| Phase 2 | #71, #72, #73, #74. | #71 can run after #67/#69; #72 should start after Phase 1 merge; #73 after #72; #74 after #69/#72. |
| Phase 3 | #75, #76, #77. | Serial because runtime, frontend, and final acceptance build on each other. |

## Atomic Commit Strategy

- Use one issue per branch/worktree where possible.
- Use commit prefixes only: `feat(module):`, `fix(module):`, `test(module):`.
- For each issue, commit in this order: failing tests, migration/models, service/API, frontend if applicable, validation/docs.
- Do not mix Lane A and Lane B migrations in the same commit.
- Suggested commit examples: `test(websocket): cover on_connect hook behavior`, `feat(curriculum): add learning content lifecycle`, `feat(test-bank): add question category tree`, `test(examiner): cover duplicate answer handling`.
- After each issue, run baseline collection `pytest backend/tests/ --co -q`.
- Expected: collection succeeds and remains around 1622 existing tests plus new tests.

## Phase 0: Baseline and Readiness

- [ ] Run from repo root: `git status --short`
  Expected: inspect only; do not revert unrelated changes.
- [ ] Run from `backend`: `pytest backend/tests/ --co -q` if invoked from repo root, or `pytest tests/ --co -q` if invoked from `backend`.
  Expected: collection succeeds, baseline around 1622 plus any already-landed tests.
- [ ] Run from `backend`: `alembic heads`
  Expected: one migration head.
- [ ] Run from `backend`: `ruff check src/`
  Expected: exit 0 or known pre-existing failures recorded before work.
- [ ] Run from `web`: `npm run lint`
  Expected: exit 0 or known pre-existing failures recorded before work.
- [ ] Run from `web`: `npm run test`
  Expected: exit 0 or known pre-existing failures recorded before work.

## #66 TDD Tasks: on_connect and Feature Flag

- [ ] Write failing test `backend/tests/unit/test_websocket_on_connect.py` proving `BaseWebSocketHandler.on_connect()` exists, is awaitable, returns no message by default, and is called once after connection setup.
  Run: `cd backend && pytest tests/unit/test_websocket_on_connect.py -v`
  Expected: fails because `on_connect` is missing or not called.
- [ ] Write failing override test using a fake subclass that sends `exam.question` from `on_connect`.
  Run: `cd backend && pytest tests/unit/test_websocket_on_connect.py -v -k override`
  Expected: fails until hook is called.
- [ ] Add minimal `async def on_connect(self) -> None: pass` to `BaseWebSocketHandler` and call it after queue initialization/reconnect restore, before receive loop.
  Run: `cd backend && pytest tests/unit/test_websocket_on_connect.py -v`
  Expected: pass.
- [ ] Write feature flag tests for enabled/disabled reads of `curriculum.examiner`.
  Run: `cd backend && pytest tests/unit/test_curriculum_examiner_feature_flag.py -v`
  Expected: fail before config surface exists.
- [ ] Add minimal feature flag read path using existing config/settings pattern; expose a backend response shape consumable by frontend.
  Run: `cd backend && pytest tests/unit/test_curriculum_examiner_feature_flag.py -v`
  Expected: pass.
- [ ] Run regression WebSocket tests.
  Run: `cd backend && pytest tests/unit/test_websocket_handler.py tests/unit/test_sales_websocket_router.py tests/integration/test_websocket_status_contract.py -v`
  Expected: pass; sales/presentation behavior unchanged.
- [ ] Run baseline collection.
  Run: `cd backend && pytest tests/ --co -q`
  Expected: collection succeeds.
- [ ] Commit.
  Message: `feat(websocket): add examiner connect hook and feature flag`

## #67 TDD Tasks: LearningContent Admin

- [ ] Write failing model/migration tests for `LearningContent`, `LearningChapter`, statuses, order constraints, and security flag.
  Run: `cd backend && pytest tests/integration/test_learning_content_api.py -v -k model`
  Expected: fail because models/tables do not exist.
- [ ] Add Alembic migration and models in `curriculum_practice/models.py`, coordinating with #69 migration head.
  Run: `cd backend && alembic upgrade head`
  Expected: migration applies; no status constraint changes to unrelated tables.
- [ ] Write failing service tests for create/edit/detail/chapter add/delete/reorder.
  Run: `cd backend && pytest tests/integration/test_learning_content_api.py -v`
  Expected: fail before service/API.
- [ ] Implement `LearningContentService` and API routes under `/api/v1/curriculum/learning-contents`.
  Run: `cd backend && pytest tests/integration/test_learning_content_api.py -v`
  Expected: CRUD and chapter operations pass.
- [ ] Write failing publish gate tests for no chapters, empty content, non-contiguous order, security flagged content, archive protection.
  Run: `cd backend && pytest tests/integration/test_learning_content_api.py -v -k publish`
  Expected: fail before gates.
- [ ] Implement publish/archive gates inside the service, not duplicated in routers.
  Run: `cd backend && pytest tests/integration/test_learning_content_api.py -v -k publish`
  Expected: pass.
- [ ] Write failing frontend tests for admin list, detail/edit, chapter states, empty/error.
  Run: `cd web && npm run test -- learning-content`
  Expected: fail before UI/API client.
- [ ] Implement admin pages and API client using `AdminShell`, `GlassCard`, `Button`, `EmptyState`, `StatusIndicator`.
  Run: `cd web && npm run test -- learning-content`
  Expected: pass.
- [ ] Record seed-data accountability in implementation notes or delivery doc path owned by #77: owner, source, import/create method, validation route.
  Expected: #77 can verify 7 chapters without guessing.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/integration/test_learning_content_api.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass or documented pre-existing failures only.
- [ ] Commit.
  Message: `feat(curriculum): add learning content management`

## #68 TDD Tasks: Learner Lecture Reading and Progress

- [ ] Write failing backend tests for current-user scoped progress fetch, complete chapter, repeated completion idempotency, all-chapters-complete transition, and IDOR.
  Run: `cd backend && pytest tests/integration/test_learning_progress_api.py -v`
  Expected: fail before progress service.
- [ ] Implement `LearningProgress` persistence/service/API without using `PracticeSession.status`.
  Run: `cd backend && pytest tests/integration/test_learning_progress_api.py -v`
  Expected: pass.
- [ ] Update LearningPath API contract tests for `continue learning`, `completed`, and `start exam` next CTA.
  Run: `cd backend && pytest tests/contract/test_learning_path_api_contract.py tests/integration/test_learning_path_flow.py -v`
  Expected: pass.
- [ ] Write failing frontend tests for StudyPage loading, empty, error, partial, mobile `<select>`, chapter switch, completion CTA.
  Run: `cd web && npm run test -- study`
  Expected: fail before page.
- [ ] Implement `web/src/app/(user)/study/[learningContentId]/page.tsx` and `learner-study` API client.
  Run: `cd web && npm run test -- study`
  Expected: pass.
- [ ] Run mobile-focused test or Playwright viewport check for chapter `<select>`.
  Run: `cd web && npm run test -- study`
  Expected: mobile test asserts select is visible and sidebar is not required.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/integration/test_learning_progress_api.py tests/contract/test_learning_path_api_contract.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass.
- [ ] Commit.
  Message: `feat(curriculum): add learner study progress`

## #69 TDD Tasks: TestBank Foundation

- [ ] Write failing schema tests for shared asset references: `AssetRef`, `LearningContentRef`, and `TestBankRef` must serialize `asset_type`, `asset_id`, `version`, `hash`, and `snapshot_label` consistently, while existing `PublishedTemplateRef` and `CurriculumVersionRef` continue to validate their narrower types.
  Run: `cd backend && pytest tests/unit/test_asset_ref_schema.py -v`
  Expected: fail because shared `AssetRef`, `LearningContentRef`, and `TestBankRef` do not exist yet.
- [ ] Extract `AssetRef` in `backend/src/curriculum_practice/schemas.py`, make `PublishedTemplateRef` and `CurriculumVersionRef` reuse the base fields, and add `LearningContentRef(AssetRef)` plus `TestBankRef(AssetRef)` for #67/#69 snapshot code.
  Run: `cd backend && pytest tests/unit/test_asset_ref_schema.py tests/unit/test_curriculum_runtime_snapshot_service.py tests/unit/test_curriculum_plan_publish_gates.py -v`
  Expected: pass; existing snapshot refs keep identical JSON shape while the new content/question refs share the base field definitions.
- [ ] Mirror the DRY reference shape in `web/src/lib/api/types.ts` by adding an `AssetRef` interface and making `PublishedPracticeTemplateRef`, `CurriculumVersionRef`, `LearningContentRef`, and `TestBankRef` reuse it without `as any` or suppression comments.
  Run: `cd web && npx tsc --noEmit && grep -R "@ts-ignore\|@ts-expect-error\|as any" web/src/lib/api/types.ts web/src/lib/api/test-bank.ts || true`
  Expected: TypeScript succeeds; grep prints no matches from changed API type files.
- [ ] Write failing migration/model tests for `QuestionCategory`, `QuestionItem`, scoring criteria/dimensions, tags, difficulty, lifecycle status, department field reservation.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k model`
  Expected: fail before models.
- [ ] Add TestBank models and migration after coordinating with #67 migration head.
  Run: `cd backend && alembic upgrade head && alembic heads`
  Expected: migration applies and there is one head.
- [ ] Write failing category tree tests: create/edit/delete, child protection, question reference protection.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k category`
  Expected: fail before service.
- [ ] Implement category service and API under `/api/v1/curriculum/test-bank/categories`.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k category`
  Expected: pass.
- [ ] Write failing QuestionItem tests for create/edit/list/filter/publish/archive and version/hash immutability.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k question`
  Expected: fail before service.
- [ ] Implement `TestBankService` and question API under `/api/v1/curriculum/test-bank/questions`.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k question`
  Expected: pass.
- [ ] Write failing publish gate tests for missing reference answer, invalid scoring criteria, security flag.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k publish`
  Expected: fail before gates.
- [ ] Implement gates in the TestBank service.
  Run: `cd backend && pytest tests/integration/test_test_bank_api.py -v -k publish`
  Expected: pass.
- [ ] Write failing admin UI/API client tests for category tree and question filters.
  Run: `cd web && npm run test -- test-bank`
  Expected: fail before UI.
- [ ] Implement admin TestBank list/edit pages with existing UI components.
  Run: `cd web && npm run test -- test-bank`
  Expected: pass.
- [ ] Explicitly document that 昱博的“大类→子类→考察维度” affects final taxonomy labels and seed data, not the parent/child technical category tree.
  Expected: #69 can ship flexible tree without blocking on taxonomy.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/integration/test_test_bank_api.py tests/contract/test_test_bank_api_contract.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass.
- [ ] Commit.
  Message: `feat(test-bank): add question bank foundation`

## #70 TDD Tasks: CSV/JSONL Import

- [ ] Write failing importer unit tests for RFC 4180 commas/quotes, JSONL Markdown, missing required fields, invalid difficulty, unknown category, invalid scoring criteria.
  Run: `cd backend && pytest tests/unit/test_test_bank_importer.py -v`
  Expected: fail before importer.
- [ ] Implement `test_bank_importer.py` parser returning imported/failed/errors with row, field, message.
  Run: `cd backend && pytest tests/unit/test_test_bank_importer.py -v`
  Expected: pass.
- [ ] Write failing API tests for 10MB limit, illegal encoding, background task `task_id`, final result polling.
  Run: `cd backend && pytest tests/integration/test_test_bank_import_api.py -v`
  Expected: fail before endpoint/task integration.
- [ ] Implement import endpoint and background task integration using existing task infrastructure if present; otherwise add minimal import-job persistence inside curriculum_practice.
  Run: `cd backend && pytest tests/integration/test_test_bank_import_api.py -v`
  Expected: pass.
- [ ] Write failing frontend tests for upload success count, failed row table, invalid file, oversize.
  Run: `cd web && npm run test -- test-bank-import`
  Expected: fail before UI.
- [ ] Implement import page using `ResponsiveTableWrapper`, `MobileTableCard`, `StatusIndicator`, no alert.
  Run: `cd web && npm run test -- test-bank-import`
  Expected: pass.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/unit/test_test_bank_importer.py tests/integration/test_test_bank_import_api.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass.
- [ ] Commit.
  Message: `feat(test-bank): add csv jsonl import`

## #71 TDD Tasks: AI Question Generation From Lectures

- [ ] Write failing service tests for normal LLM JSON output producing 3-5 editable drafts with `content`, `reference_answer`, `scoring_criteria`, `source_chapter_id`.
  Run: `cd backend && pytest tests/unit/test_question_generation_service.py -v -k normal`
  Expected: fail before service.
- [ ] Write failing tests for malformed JSON, empty output, prompt injection rejection, content-quality rejection.
  Run: `cd backend && pytest tests/unit/test_question_generation_service.py -v`
  Expected: fail before parsing/safety logic.
- [ ] Implement `QuestionGenerationService` using existing LLM infrastructure, returning `Result[T]` and not auto-saving.
  Run: `cd backend && pytest tests/unit/test_question_generation_service.py -v`
  Expected: pass.
- [ ] Write failing API tests for preview, edited preview save, and no save on unsafe output.
  Run: `cd backend && pytest tests/integration/test_question_generation_api.py -v`
  Expected: fail before routes.
- [ ] Implement generation and confirm-save endpoints.
  Run: `cd backend && pytest tests/integration/test_question_generation_api.py -v`
  Expected: pass.
- [ ] Write failing frontend preview tests.
  Run: `cd web && npm run test -- question-generation-preview`
  Expected: fail before component.
- [ ] Implement preview/edit/save UI from lecture chapter detail.
  Run: `cd web && npm run test -- question-generation-preview`
  Expected: pass.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/unit/test_question_generation_service.py tests/integration/test_question_generation_api.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass.
- [ ] Commit.
  Message: `feat(test-bank): generate draft questions from lectures`

## #72 TDD Tasks: LearnerProfile, Template Binding, RuntimeSnapshot

- [ ] Write failing model/migration tests for `LearnerProfile` fields: user, self-assessed background, admin override, effective level, conservative default.
  Run: `cd backend && pytest tests/integration/test_learner_profile_api.py -v -k model`
  Expected: fail before model.
- [ ] Add migration for `LearnerProfile` and PracticeTemplate binding fields for learning content, examiner agent, target learner level, timeout config.
  Run: `cd backend && alembic upgrade head`
  Expected: migration applies; no forbidden status/role constraint changes.
- [ ] Write failing API/service tests for self-assessment, admin override, default level.
  Run: `cd backend && pytest tests/integration/test_learner_profile_api.py -v`
  Expected: fail before service/API.
- [ ] Implement learner profile service/API.
  Run: `cd backend && pytest tests/integration/test_learner_profile_api.py -v`
  Expected: pass.
- [ ] Write failing schema/publish-gate tests for `stage_type: study|exam|practice|report` and published-asset validation.
  Run: `cd backend && pytest tests/unit/test_curriculum_plan_schema.py tests/unit/test_curriculum_plan_publish_gates.py -v`
  Expected: fail before schema/gates.
- [ ] Extend CurriculumPlan schema and gates minimally.
  Run: `cd backend && pytest tests/unit/test_curriculum_plan_schema.py tests/unit/test_curriculum_plan_publish_gates.py -v`
  Expected: pass.
- [ ] Write failing snapshot tests that study snapshots include learning content/chapters and exam snapshots include examiner config, question source, reference answers, criteria, target level.
  Run: `cd backend && pytest tests/unit/test_runtime_snapshot_study_exam_assets.py -v`
  Expected: fail before snapshot extension.
- [ ] Extend `RuntimeSnapshotService` and `session_snapshots` without reading latest content at runtime.
  Run: `cd backend && pytest tests/unit/test_runtime_snapshot_study_exam_assets.py tests/integration/test_curriculum_practice_session_snapshot.py tests/integration/test_curriculum_snapshot_immutability.py -v`
  Expected: pass.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/unit/test_curriculum_runtime_snapshot_service.py tests/integration/test_curriculum_practice_session_snapshot.py tests/integration/test_curriculum_snapshot_immutability.py -v && pytest tests/ --co -q`
  Expected: pass.
- [ ] Commit.
  Message: `feat(curriculum): bind learner levels and exam snapshots`

## #73 TDD Tasks: Batch Assignment

- [ ] Write failing service tests for assigned/skipped/failed counts, duplicate template skip, invalid template/plan, cross-department rejection.
  Run: `cd backend && pytest tests/integration/test_training_task_batch_assign.py -v`
  Expected: fail before service.
- [ ] Implement `batch_assignment_service.py` using existing TrainingTask model and action-level department scope.
  Run: `cd backend && pytest tests/integration/test_training_task_batch_assign.py -v`
  Expected: pass.
- [ ] Write failing contract test for `POST /api/v1/training-tasks/batch-assign`.
  Run: `cd backend && pytest tests/contract/test_training_tasks.py -v -k batch`
  Expected: fail before route contract.
- [ ] Add route in existing training tasks API.
  Run: `cd backend && pytest tests/contract/test_training_tasks.py -v -k batch`
  Expected: pass.
- [ ] Write failing frontend tests for department filter, multi-select, partial success/failure details.
  Run: `cd web && npm run test -- training-task-batch`
  Expected: fail before UI.
- [ ] Implement admin batch assignment page.
  Run: `cd web && npm run test -- training-task-batch`
  Expected: pass.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/integration/test_training_task_batch_assign.py tests/contract/test_training_tasks.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass.
- [ ] Commit.
  Message: `feat(training-tasks): add batch assignment`

## #74 TDD Tasks: ExaminerAgent Config Management

- [ ] Write failing API tests for ExaminerAgent CRUD and list/detail.
  Run: `cd backend && pytest tests/integration/test_examiner_agent_api.py -v -k crud`
  Expected: fail before examiner API/service.
- [ ] Implement `agent/api/examiners.py` and `ExaminerConfigService`, registering router in `router_registry.py`.
  Run: `cd backend && pytest tests/integration/test_examiner_agent_api.py -v -k crud`
  Expected: pass.
- [ ] Write failing publish gate tests for empty question source, unpublished questions, invalid scoring policy, security-flagged content.
  Run: `cd backend && pytest tests/integration/test_examiner_agent_api.py -v -k publish`
  Expected: fail before gates.
- [ ] Implement publish gates.
  Run: `cd backend && pytest tests/integration/test_examiner_agent_api.py -v -k publish`
  Expected: pass.
- [ ] Write failing simulation endpoint test proving no learner certification/report record is created.
  Run: `cd backend && pytest tests/integration/test_examiner_agent_api.py -v -k simulation`
  Expected: fail before simulation.
- [ ] Implement simulation endpoint using frozen-like config validation but no official learner record writes.
  Run: `cd backend && pytest tests/integration/test_examiner_agent_api.py -v -k simulation`
  Expected: pass.
- [ ] Write failing frontend tests for examiner admin list/edit/publish/test.
  Run: `cd web && npm run test -- examiners`
  Expected: fail before UI.
- [ ] Implement admin examiner pages.
  Run: `cd web && npm run test -- examiners`
  Expected: pass.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/integration/test_examiner_agent_api.py -v && pytest tests/ --co -q`
  Expected: pass.
  Run: `cd web && npm run lint && npm run test`
  Expected: pass.
- [ ] Commit.
  Message: `feat(examiner): add examiner agent configuration`

## #75 TDD Tasks: AI Examiner WebSocket Runtime

- [ ] Write failing WebSocket contract test for connect sending `session.init` and first `exam.question` through `on_connect`.
  Run: `cd backend && pytest tests/contract/test_examiner_websocket_contract.py -v -k on_connect`
  Expected: fail before handler.
- [ ] Add `backend/src/agent/websocket/examiner_handler.py`, route registration, and minimal `on_connect` using frozen snapshot.
  Run: `cd backend && pytest tests/contract/test_examiner_websocket_contract.py -v -k on_connect`
  Expected: pass.
- [ ] Decide and document `ExaminerSessionState` persistence in the first #75 implementation commit: prefer an explicit DB-backed state model/table for reconnect, idempotency, `active_question_index`, answered question hashes, timeout timestamps, and finalization marker; only choose a persisted JSON field if repository constraints prove it safer.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v -k state_persistence`
  Expected: fail before the chosen persistence contract exists; the test names and model/service code make the chosen persistence strategy explicit.
- [ ] Write failing prewarm tests proving `ExaminerRuntimeService.prewarm_examiner_prompt()` loads the frozen `RuntimeSnapshotService` exam assets, builds/renders the first-question prompt, stores the warmed snapshot/prompt bundle in memory for the session, and avoids reading latest LearningContent/TestBank records during `on_connect`.
  Run: `cd backend && pytest tests/unit/test_examiner_prewarm_service.py -v && pytest tests/contract/test_examiner_websocket_contract.py -v -k prewarm`
  Expected: fail because `prewarm_examiner_prompt()` and the warmed first-question cache do not exist.
- [ ] Implement prompt/snapshot prewarm in `on_connect`: add `backend/src/agent/services/examiner_prewarm_service.py` or a focused method inside `ExaminerRuntimeService`, follow the existing `kb_lock_warmup` lifecycle pattern for timing/logging/cancellation discipline without importing `sales_bot`, and send the first `exam.question` from the warmed prompt/snapshot bundle.
  Run: `cd backend && pytest tests/unit/test_examiner_prewarm_service.py tests/contract/test_examiner_websocket_contract.py -v -k "prewarm or on_connect"`
  Expected: pass; `on_connect` sends `session.init` and first `exam.question` after prewarm, with structured log fields including `duration_ms` and `session_id`.
- [ ] Write failing runtime tests for active index, wrong index ignore, duplicate answer ignore, answer after completion ignore.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v -k index`
  Expected: fail before state machine.
- [ ] Implement `ExaminerSessionState` persistence/service without touching `PracticeSession.status`.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v -k index`
  Expected: pass.
- [ ] Write failing scoring tests for frozen reference answer/scoring criteria, malformed LLM JSON fallback, retry once on timeout.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v -k scoring`
  Expected: fail before scoring service.
- [ ] Implement `ExaminerScoringService` using frozen snapshot criteria and `Result[T]`.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v -k scoring`
  Expected: pass.
- [ ] Write failing tests for per-question timeout zero score, session timeout completion, reconnect restoring active question, no rescore, final report idempotency.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v`
  Expected: fail before recovery/completion logic.
- [ ] Implement timeout, reconnect, completion, evaluation/report integration without recalculating historical reports.
  Run: `cd backend && pytest tests/integration/test_examiner_websocket_runtime.py -v`
  Expected: pass.
- [ ] Run broader WebSocket regressions.
  Run: `cd backend && pytest tests/unit/test_websocket_handler.py tests/unit/test_sales_websocket_router.py tests/e2e/test_websocket_flow.py tests/integration/test_websocket_status_contract.py -v`
  Expected: pass.
- [ ] Run validations.
  Run: `cd backend && ruff check src/ && pytest tests/integration/test_examiner_websocket_runtime.py tests/contract/test_examiner_websocket_contract.py -v && pytest tests/ --co -q`
  Expected: pass.
- [ ] Run prewarm performance smoke test before handing #75 to #77.
  Run: `cd backend && pytest tests/performance/test_examiner_runtime_performance.py -m performance -v -k first_question`
  Expected: first question is measured after prewarm and stays below 300ms in the controlled test harness, or the result is recorded as an environment-bound performance blocker before #77.
- [ ] Commit.
  Message: `feat(examiner): add server driven websocket runtime with prewarm`

## #76 TDD Tasks: Learner AI Exam Frontend

- [ ] Write failing hook tests for WebSocket connect, `session.init`, first question, answer submit, feedback, next question, completed.
  Run: `cd web && npm run test -- use-examiner-websocket`
  Expected: fail before hook.
- [ ] Implement `use-examiner-websocket.ts` with typed messages and no `as any`.
  Run: `cd web && npm run test -- use-examiner-websocket`
  Expected: pass.
- [ ] Write failing page/component tests for loading, empty bank, feature flag off `即将上线`, timeout warning, reconnect banner, completed view.
  Run: `cd web && npm run test -- examiner`
  Expected: fail before UI.
- [ ] Implement `ExamPage`, progress panel, feedback list, text/voice fallback, and final result entry using existing UI components.
  Run: `cd web && npm run test -- examiner`
  Expected: pass.
- [ ] Write failing mobile layout test asserting right panel appears as bottom `GlassSheet`.
  Run: `cd web && npm run test -- examiner -t mobile`
  Expected: fail before responsive layout.
- [ ] Implement responsive behavior.
  Run: `cd web && npm run test -- examiner -t mobile`
  Expected: pass.
- [ ] Run validations.
  Run: `cd web && npm run lint && npm run test && npx tsc --noEmit`
  Expected: pass.
  Run: `grep -R "@ts-ignore\|@ts-expect-error\|as any" web/src/app web/src/components web/src/hooks web/src/lib/api || true`
  Expected: no matches in files touched by #76; if pre-existing matches exist elsewhere, list them separately and do not add new suppressions.
  Run: `cd backend && pytest tests/ --co -q`
  Expected: collection succeeds.
- [ ] Commit.
  Message: `feat(examiner): add learner exam page`

## #77 TDD Tasks: E2E, Performance, Security, COO Pack

- [ ] Write failing E2E for learner study -> complete -> exam -> report -> Dashboard/LearningPath update.
  Run: `cd backend && pytest tests/e2e/test_sales_training_learning_examiner_flow.py -v`
  Expected: fail before full seeded path wiring.
- [ ] Add backend fixtures/seeds for published learning content, questions, examiner config, template, learner profile.
  Run: `cd backend && pytest tests/e2e/test_sales_training_learning_examiner_flow.py -v`
  Expected: pass.
- [ ] Write failing E2E for admin import -> bind examiner -> learner exam.
  Run: `cd web && npm run e2e -- sales-training-learning-examiner.spec.ts`
  Expected: fail before browser flow support/fixtures.
- [ ] Implement or adjust E2E fixtures and selectors.
  Run: `cd web && npm run e2e -- sales-training-learning-examiner.spec.ts`
  Expected: pass.
- [ ] Add security tests/evidence for IDOR, prompt injection rejection, Markdown XSS sanitization, batch assignment department RBAC.
  Run: `cd backend && pytest tests/integration/test_learning_progress_api.py tests/integration/test_test_bank_api.py tests/integration/test_training_task_batch_assign.py -v`
  Expected: pass security cases.
  Run: `cd web && npm run test -- study examiner test-bank`
  Expected: Markdown rendering and no alert/popup tests pass.
- [ ] Add performance tests for first question <300ms after prewarm, scoring <2s, imports under 10MB concurrent stability.
  Run: `cd backend && pytest tests/performance/test_examiner_runtime_performance.py -m performance -v`
  Expected: pass thresholds or produce explicit blocker if environment cannot measure reliably.
- [ ] Run final backend baseline.
  Run: `cd backend && pytest tests/ --co -q`
  Expected: collection succeeds, expected baseline around 1622 plus new tests.
- [ ] Run final backend quality.
  Run: `cd backend && ruff check src/ && pytest`
  Expected: pass.
- [ ] Run final frontend quality.
  Run: `cd web && npm run lint && npm run test && npx tsc --noEmit`
  Expected: pass.
- [ ] Deliver docs and COO materials.
  Expected files: `docs/api-contract/learning-content.md`, `docs/api-contract/test-bank.md`, `docs/api-contract/examiners.md`, `docs/delivery/sales-training-learning-examiner-coo-demo.md`, `docs/delivery/sales-training-learning-examiner-deployment.md`, screenshots/GIF paths, known issues list.
- [ ] Verify seed data acceptance.
  Expected: owner/source/import method documented; at least 7 lecture chapters and 20 presales questions covering 3+ scoring dimensions.
- [ ] Commit.
  Message: `test(examiner): add full learning exam acceptance gate`

## Validation Matrix

| Area | Command | Expected Result |
|---|---|---|
| Backend baseline collection | `cd backend && pytest tests/ --co -q` | Collection succeeds; baseline around 1622 existing tests plus new tests. |
| Backend lint | `cd backend && ruff check src/` | Exit 0. |
| Backend unit/integration/contract | `cd backend && pytest tests/unit/ tests/integration/ tests/contract/ -v` | Exit 0. |
| Backend full | `cd backend && pytest` | Exit 0 before final acceptance. |
| Migrations | `cd backend && alembic upgrade head && alembic heads` | Upgrade succeeds; one head. |
| Frontend lint | `cd web && npm run lint` | Exit 0. |
| Frontend tests | `cd web && npm run test` | Exit 0. |
| Frontend types | `cd web && npx tsc --noEmit` | Exit 0. |
| Frontend E2E | `cd web && npm run e2e -- sales-training-learning-examiner.spec.ts` | Study/exam/report and admin-import-to-exam paths pass. |
| Security | Backend integration/security cases plus frontend sanitizer tests | IDOR blocked, prompt injection rejected, Markdown XSS sanitized, batch RBAC enforced. |
| Performance | `cd backend && pytest tests/performance/test_examiner_runtime_performance.py -m performance -v` | First question <300ms after #75 prewarm, scoring <2s, stable concurrent imports under 10MB. |
| COO deliverables | Manual review of delivery docs and screenshots/GIFs | API docs, deployment notes, known issues, COO script, visual evidence present. |

## Daily Summary Format

Use this after each issue or end-of-day checkpoint:

```markdown
## Daily Summary YYYY-MM-DD

Completed:
- #NN: <completed behavior and verification evidence>

Blockers:
- <issue/blocker, owner, next action>

External Inputs:
- 昱博 taxonomy status: <not needed for #69 technical tree | needed for final taxonomy/seed data>
- Seed data owner/source: <owner and path>
- COO demo timing: <confirmed or pending>
```

## Self-Review

- Spec coverage: #66-#77 are all represented with summaries, acceptance summaries, file/module maps, migration ordering, dependency graph, phased execution, TDD tasks, validation matrix, external taxonomy blocker, and final delivery gate; the review gaps for #75 prewarm, #69 AssetRef DRY, #76 TypeScript suppression checks, and #75 `ExaminerSessionState` persistence decision are explicitly covered.
- Placeholder scan: No task uses vague instructions such as TODO/TBD/implement later/add appropriate tests; each issue has concrete tests, implementation target, commands, expected outcomes, and commit prefix.
- Type/signature consistency: Plan consistently uses `LearningContent`, `LearningChapter`, `LearningProgress`, `AssetRef`, `LearningContentRef`, `TestBankRef`, `QuestionCategory`, `QuestionItem`, `LearnerProfile`, `ExaminerAgent`, `ExaminerSessionState`, `RuntimeSnapshotService`, `PracticeTemplate`, `CurriculumPlan.stage_type`, `BaseWebSocketHandler.on_connect`, `ExaminerRuntimeService.prewarm_examiner_prompt()`, and WebSocket messages `session.init`, `exam.question`, `exam.answer`, `exam.feedback`, `exam.completed`.
- Constraint consistency: Plan does not introduce `SessionV2`, does not extend `PracticeSession.status` or `TrainingTask.status`, does not alter `User.role`, does not couple examiner to `sales_bot`, does not permit latest-content runtime reads, does not recalculate historical reports, and preserves the required user dependency order.

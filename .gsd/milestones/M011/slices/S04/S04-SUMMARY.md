---
id: S04
parent: M011
milestone: M011
provides:
  - A fixture-driven knowledge-answer evaluation harness with deterministic intro, pricing, version-comparison, coaching, and blocked-timeout cases on the real engine seam.
  - A read-only `/api/v1/knowledge-debug` inspection surface that lists persisted runs, returns one run’s audit detail, and exposes ordered step payloads for admin/support.
  - Seedable active knowledge-answer config plus compat-seam rollout controls for legacy default, enabled cutover, and dual-run shadow audit.
  - Rollout diagnostics that surface mode selection on existing runtime inspection seams and persist shadow/live audit runs when a real session_id exists.
requires:
  - slice: S03
    provides: Persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` audit rows plus compatibility payload fields that S04 now evaluates, inspects, and rolls out safely.
affects:
  []
key_files:
  - backend/src/common/knowledge_engine/evaluation.py
  - backend/src/common/api/knowledge_debug.py
  - backend/src/common/knowledge_engine/compat.py
  - backend/scripts/seed_knowledge_answer_config.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/evaluation/test_knowledge_answer_engine_eval.py
  - backend/tests/integration/test_knowledge_debug_api.py
  - backend/tests/unit/common/test_seed_knowledge_answer_config.py
  - backend/tests/unit/common/test_knowledge_answer_feature_flag.py
  - docs/plans/knowledge-answer-config-seed-notes.md
key_decisions:
  - D153: evaluate the new knowledge-answer engine through a fixture-driven harness on the real engine seam and preserve exact multiline `final_text` expectations.
  - D154: build the debug surface directly on persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows and keep it read-only behind existing admin/support RBAC.
  - D155: own rollout at the compat seam with explicit legacy, enabled, and dual-run modes; keep dual-run learner-visible behavior on legacy output while shadow-persisting audits when `session_id` exists.
patterns_established:
  - Treat persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows as the single inspection authority for recent-run debugging rather than rebuilding execution stories from handler-local state.
  - Keep rollout control in `common.knowledge_engine.compat` so legacy, enabled, and dual-run modes are decided in one seam and surfaced through the same diagnostics contract.
  - Preserve exact assembler output in eval fixtures; do not whitespace-normalize learner-facing numbered answers.
  - Seed active config versions idempotently by `version_name` so bootstrap can reactivate canonical starter profiles without duplicating control-plane rows.
observability_surfaces:
  - `GET /api/v1/knowledge-debug/runs` for recent run list inspection.
  - `GET /api/v1/knowledge-debug/runs/{run_id}` for single-run audit detail.
  - `GET /api/v1/knowledge-debug/runs/{run_id}/steps` for ordered execution-step inspection.
  - `_diagnostics.knowledge_answer_rollout` on the compat/runtime path for enabled and dual-run visibility.
  - Persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows, including shadow audits in dual-run mode when `session_id` is present.
  - Focused backend/web verification gates covering eval, debug API RBAC, rollout flags, StepFun compatibility, runtime diagnostics, replay, and learner report/replay consumers.
drill_down_paths:
  - .gsd/milestones/M011/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M011/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M011/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T06:40:27.903Z
blocker_discovered: false
---

# S04: 评测、debug API 与 rollout

**S04 added deterministic evals, a recent-run debug API, seedable starter config, and compat-seam rollout controls so the new knowledge-answer engine can be inspected and rolled out safely.**

## What Happened

S04 turned the S03 grounded-answer seam into an operable subsystem. The slice first added a fixture-driven evaluation harness with deterministic intro, pricing, version-comparison, coaching, and blocked-timeout cases that run against the real `KnowledgeAnswerEngine` seam and preserve exact learner-facing multiline `final_text` formatting. It then added a read-only `/api/v1/knowledge-debug` router that lists recent persisted `KnowledgeAnswerRun` rows, returns single-run audit detail, and exposes ordered `KnowledgeAnswerRunStep` payloads directly from durable storage for admin/support inspection. Finally, it completed the rollout story by adding an idempotent seed script for active starter configs and extracting feature-flag control into `common.knowledge_engine.compat`, where legacy default, engine-enabled cutover, and dual-run shadow audit are now decided in one place. In dual-run mode the visible payload remains legacy while the engine executes in shadow, emits rollout diagnostics, and persists audit rows only when a real `session_id` exists. Fresh slice-close verification reran the eval suite, the debug API integration suite, the full focused backend compatibility gate, and the paired web compatibility suite; all passed, proving the roadmap demo is now real: operators can inspect recent knowledge-answer traces and the product-introduction-class query behavior can be regression-tested before or during rollout.

## Verification

Fresh slice-close verification reran all S04 plan gates from repo root and all passed: eval harness 6/6, debug API integration 5/5, focused backend compatibility+rollout suite 197/197, and paired web compatibility suite 68/68. Verification also confirmed the intended observability surfaces: `/api/v1/knowledge-debug` list/detail/steps inspection, persisted run/step rows, and `_diagnostics.knowledge_answer_rollout` on the compat/runtime path. Non-blocking known warnings remained visible during backend/web verification: repo-root pytest-cov no-data warnings, the existing replay audio-audit AsyncMock warning from `backend/src/common/conversation/replay.py:292`, and the replay page’s intentional `[SESSION_NOT_COMPLETED]` stderr log in the passing web test.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T03 extracted rollout gating into `backend/src/common/knowledge_engine/compat.py` instead of layering more branching directly into the existing StepFun helper path, because one compat seam was the smallest truthful way to keep legacy, enabled, and dual-run modes aligned. The seed script also needed its own sync SQLAlchemy bootstrap since the shared DB helpers are async-only. These changes preserved the planned behavior while slightly shifting implementation shape.

## Known Limitations

There is still no milestone-level aggregate rollout dashboard beyond the new debug API and compat diagnostics, and canonical completed-session report payloads are not yet first-class readers of the full knowledge-answer debug/audit seam. Narrow repo-root backend pytest also still emits known pytest-cov warnings, and the replay backend suite still emits the pre-existing `AsyncMockMixin._execute_mock_call` warning from the graceful audio-audit fallback path.

## Follow-ups

M011 milestone close-out should decide whether any broader rollout-health dashboard or canonical report-surface mirroring is still needed, but S04 itself closed the planned eval/debug/rollout gap. If future work extends observability, it should reuse `/api/v1/knowledge-debug`, persisted run rows, and `_diagnostics.knowledge_answer_rollout` rather than inventing a second rollout truth line.

## Files Created/Modified

- `backend/src/common/knowledge_engine/evaluation.py` — Added the reusable deterministic evaluation harness on the real engine seam.
- `backend/tests/evaluation/test_knowledge_answer_engine_eval.py` — Added focused eval-harness regression coverage.
- `backend/tests/fixtures/knowledge_answer_eval_cases.json` — Added starter intro/pricing/comparison/coaching/blocked fixture cases.
- `backend/src/common/api/knowledge_debug.py` — Added the read-only recent-run debug router for admin/support.
- `backend/src/main.py` — Registered the new debug router on the live FastAPI app.
- `backend/tests/integration/test_knowledge_debug_api.py` — Added integration coverage for list/detail/steps, RBAC, and not-found behavior.
- `backend/src/common/knowledge_engine/compat.py` — Centralized rollout-mode control and compat-seam execution for legacy, enabled, and dual-run modes.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — Routed the StepFun search seam through compat rollout control and rollout diagnostics.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Forwarded `session_id` so enabled/dual-run execution can persist truthful shadow/live audit runs.
- `backend/scripts/seed_knowledge_answer_config.py` — Added idempotent starter config seeding/reactivation.
- `backend/tests/unit/common/test_seed_knowledge_answer_config.py` — Added focused regression coverage for seed-script bootstrap behavior.
- `backend/tests/unit/common/test_knowledge_answer_feature_flag.py` — Added focused rollout-mode tests.
- `docs/plans/knowledge-answer-config-seed-notes.md` — Documented seeded profiles, CLI usage, activation behavior, and rollout order.
- `.gsd/PROJECT.md` — Updated project state to record M011/S04 completion.
- `.gsd/KNOWLEDGE.md` — Captured the rollout/debug gotcha about compat-mode authority and session-backed shadow audits.

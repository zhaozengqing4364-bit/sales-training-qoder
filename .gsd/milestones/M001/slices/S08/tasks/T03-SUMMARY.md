---
id: T03
parent: S08
milestone: M001
provides:
  - S08 release-wave UAT script with fresh automated verification evidence, partial live-proof capture, and precise resume notes
key_files:
  - .gsd/milestones/M001/slices/S08/S08-UAT.md
  - .gsd/milestones/M001/slices/S08/tasks/T03-PLAN.md
  - .gsd/milestones/M001/slices/S08/S08-PLAN.md
key_decisions: []
patterns_established:
  - Slice-close UAT artifacts should record carried-forward automated blockers separately from unfinished live-wave evidence so the next unit can resume without re-reading all prior slice summaries.
observability_surfaces:
  - .gsd/milestones/M001/slices/S08/S08-UAT.md
  - /api/v1/support/runtime/overview
  - /api/v1/support/runtime/faults
  - /api/v1/practice/sessions/{id}/report
  - /api/v1/admin/users/{id}/progress
duration: 1h05m
verification_result: partial
completed_at: 2026-03-24T17:58:35+0800
# Set blocker_discovered: true only if execution revealed the remaining slice plan
# is fundamentally invalid (wrong API, missing capability, architectural mismatch).
# Do NOT set true for ordinary bugs, minor deviations, or fixable issues.
blocker_discovered: false
---

# T03: 复用既有 UAT 路径完成桌面端发布波次验收并落盘 S08 证据

**Recorded the S08 release-close UAT plan, ran the full automated slice gate, and left exact resume evidence for the unfinished localhost waves.**

## What Happened

I first fixed the task-plan omission by adding the missing `## Observability Impact` section to `.gsd/milestones/M001/slices/S08/tasks/T03-PLAN.md`, because this task is explicitly about release-health inspection surfaces and typed anomaly visibility.

Then I wrote `.gsd/milestones/M001/slices/S08/S08-UAT.md` as a fresh S08 release-wave artifact instead of copying old slice text. The file now composes the prior S01/S05/S06/S07 recipes into one five-wave localhost release script, includes the preflight gotchas the slice requires (`alembic upgrade head`, `localhost` host alignment, `python-socks`, no PPT `type:"text"` shortcut), and captures the current run’s automated verification evidence plus exact resume notes.

For verification, I ran the full S08 automated gate. All backend commands passed. The only failing automated command is still the carried-forward web regression in `src/app/(user)/practice/[sessionId]/report/page.test.tsx`: the sales report page does not render the expected degraded enhanced-report copy `综合洞察暂不可用，当前页面仅展示统一训练证据。`. That same failure was already known at T02; it is not a new support/runtime regression.

I also brought up fresh backend and web servers on `localhost:3444` and `localhost:3445`, verified dev-login, discovered a usable published sales agent/persona pair, created a fresh realtime sales session (`9fcc3299-724b-4bdd-8a8b-22c98d87d97a`), and sampled the live support-runtime overview/faults API. The support-runtime API currently reports a real blocking state with typed anomalies (`stuck_scoring`, `kb_lock_blocked_*`, `projection_failed`) plus warning-only anomalies (`upstream_unstable`, `presentation_degraded_missing_page_metadata`).

A context-budget stop signal arrived before I could finish the remaining live browser waves. I converted the in-progress work into durable evidence in `S08-UAT.md` instead of guessing at a release verdict.

## Verification

I verified the slice-close automated commands first, then checked the localhost stack and release-health APIs. Backend verification is green across support-runtime, knowledge-check, runtime reconnect/lifecycle, admin progress, canonical report, and PPT report suites. The web slice command remains red on the single carried-forward report-page degraded-copy expectation.

`S08-UAT.md` now records:
- the exact automated results from this run;
- the partial live-wave progress captured before stopping;
- the current blocking vs warning release conclusion;
- the precise resume recipe for the next unit, including the fresh sales session, the supervisor user id, and the PPT happy/degraded reference sessions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/alembic upgrade head` | 0 | ✅ pass | 3.34s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py` | 0 | ✅ pass | 11.23s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses` | 0 | ✅ pass | 10.74s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` | 0 | ✅ pass | 12.65s |
| 5 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'` | 1 | ❌ fail | 3.35s |

## Diagnostics

Future agents should start with `.gsd/milestones/M001/slices/S08/S08-UAT.md`. It already contains the current automated gate results, the live support-runtime API snapshot, the fresh sales session id (`9fcc3299-724b-4bdd-8a8b-22c98d87d97a`), the published sales agent/persona ids used to create it, and the exact browser-wave order to resume.

If you need to inspect the current release-health truth line, use:
- `/api/v1/support/runtime/overview`
- `/api/v1/support/runtime/faults`
- `/api/v1/practice/sessions/{id}/report`
- `/api/v1/admin/users/{id}/progress`

The current support-runtime backend snapshot is already useful evidence: release status is `blocking`, with typed blocking anomalies (`stuck_scoring`, `kb_lock_blocked_*`, `projection_failed`) and warning anomalies (`upstream_unstable`, `presentation_degraded_missing_page_metadata`).

## Deviations

I did not finish the five-wave browser/live proof in this unit. The context-budget warning arrived after the automated verification gate, localhost server startup, sales-session creation, and support-runtime API sampling. I recorded the partial state and precise resume notes in `S08-UAT.md` instead of continuing into incomplete browser work.

## Known Issues

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' ...` still fails because the sales report page is missing the degraded enhanced-report copy `综合洞察暂不可用，当前页面仅展示统一训练证据。` expected by `page.test.tsx:434-436`.
- The remaining live/browser waves are still unfinished in this unit: sales reconnect/end-failure, canonical sales report, `/admin/users/{id}`, PPT happy/degraded pages, and `/support/runtime` browser cross-check.
- Because those waves are incomplete, S08 does **not** yet have a final release-pass verdict in this summary. The current durable conclusion is partial and blocking.

## Files Created/Modified

- `.gsd/milestones/M001/slices/S08/tasks/T03-PLAN.md` — added the missing `## Observability Impact` section required by the task pre-flight note.
- `.gsd/milestones/M001/slices/S08/S08-UAT.md` — wrote the S08 release-wave UAT artifact, then updated it with current automated results, support-runtime API evidence, blocking/warning conclusion, and resume notes.
- `.gsd/milestones/M001/slices/S08/tasks/T03-SUMMARY.md` — recorded the task outcome, verification evidence, and exact next steps for the next unit.

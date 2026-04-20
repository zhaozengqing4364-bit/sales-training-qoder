---
id: S08
parent: M001
milestone: M001
provides:
  - Release-grade desktop launch proof: evidence-backed `/support/runtime`, typed blocking/warning anomaly surfacing, repo-root verification compatibility, and a fresh localhost UAT wave across sales runtime, canonical report, supervisor trend, PPT postmortem, and support runtime.
requires:
  - slice: S01
    provides: Stable sales session lifecycle, reconnect semantics, and end-failure visibility on the real `/practice/{sessionId}` page.
  - slice: S03
    provides: Canonical learner/supervisor single-session report entrypoint on `/practice/{sessionId}/report`.
  - slice: S05
    provides: Sales value-expression / objection-handling evidence semantics used by the canonical sales report and runtime diagnostics.
  - slice: S06
    provides: Projection-backed supervisor progress and score summaries for `/admin/users/{id}`.
  - slice: S07
    provides: Scenario-aware PPT postmortem on the shared report route, including explicit degraded reasons for missing page metadata.
affects:
  - M002/S01
  - M004/S01
key_files:
  - backend/src/support/services/runtime_status_service.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - web/src/app/(dashboard)/support/runtime/page.tsx
  - backend/src/common/config.py
  - alembic.ini
  - pyproject.toml
  - .gsd/milestones/M001/slices/S08/S08-UAT.md
key_decisions:
  - D030
  - D031
patterns_established:
  - `/support/runtime` must read persisted session evidence plus shared runtime diagnostics, then classify anomalies with the same semantics the learner/admin/report surfaces already use instead of inventing a second support-only truth line.
  - Final auto verification for this repo can execute repo-root `venv/bin/*` commands, so repo-root Alembic/pytest shims and backend `.env` fallback must stay in sync with the canonical `backend/` config.
  - Slice-close localhost UAT is most reliable when the proof uses deterministic seeded sessions for report/progress/PPT/support surfaces and records exact session/user IDs alongside the matching backend diagnostics.
observability_surfaces:
  - `/api/v1/support/runtime/overview`
  - `/api/v1/support/runtime/faults`
  - `/support/runtime`
  - `practice_session_evidence_projection_built`
  - `practice_session_report_built`
  - `practice_history_projection_query`
  - `support_runtime_release_health_built`
drill_down_paths:
  - .gsd/milestones/M001/slices/S08/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S08/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S08/tasks/T03-SUMMARY.md
duration: 5h
verification_result: passed
completed_at: 2026-03-24T18:24:30+08:00
---

# S08: 桌面端发布验收与可观测性收口

**`/support/runtime` now acts as a truthful desktop release-health gate backed by persisted session evidence, and a fresh localhost release wave re-proved sales runtime failure visibility, canonical sales reporting, supervisor progress, PPT happy/degraded postmortems, and support-runtime anomaly mapping on the same evidence line.**

## What Happened

S08 closed M001 at the assembly layer rather than adding another isolated feature. On the backend, T01 replaced the old SystemLog-counting support runtime reader with `RuntimeStatusService`: recent sessions plus `ConversationMessage` rows are batch-loaded, projections come from `SessionEvidenceService.build_projection(...)`, knowledge/runtime states reuse the shared helper extracted into `backend/src/common/conversation/runtime_diagnostics.py`, and PPT degradation comes from the same presentation-review semantics already used by the canonical report route. That means support runtime now classifies `stuck_scoring`, `projection_failed`, `not_evaluable_completed`, `knowledge_search_failed`, `kb_lock_blocked_*`, `presentation_degraded_missing_page_metadata`, and `optional_report_failed` from the same persisted fact line the product already trusts.

T02 then pulled the web support page onto that typed contract. `/support/runtime` now renders release health as blocking vs warning, keeps overview/fault fetches independent so local empty/error states remain local, and surfaces typed anomaly rows with severity, kind, summary, detected time, scenario, session id, and compact diagnostics instead of raw log spill. The page stays intentionally read-only and does not add learner-report deep links that would bypass the existing RBAC/report entrypoints.

The closer turn had to fix one more non-product mismatch before slice closure: the final verification gate was running repo-root `venv/bin/alembic upgrade head` and repo-root `venv/bin/python -m pytest -c pyproject.toml tests/...`, while the project’s canonical Python config lived under `backend/`. To make the actual gate truthfully exercise the backend layout, the slice now includes a repo-root `alembic.ini`, a repo-root `pyproject.toml`, a `tests -> backend/tests` shim, and a small `backend/src/common/config.py` hardening change so repo-root execution can still load `backend/.env`. That fixed the false-negative gate without changing the product behavior.

With the gate path repaired, the full slice verification matrix passed, and the localhost release wave was rerun against fresh deterministic data. I started backend/web on `localhost:3444/3445`, dev-logged in as the stable local admin, seeded one dedicated verification user plus known-good sales/PPT/support sessions into the real DB, and then walked the actual browser surfaces:

- `/practice/f10c769e-c655-41fb-9478-76bc30f97f3d` stayed on the practice page, showed reconnect copy, and surfaced `AGENT_PERSONA_REQUIRED` through the real websocket loop instead of silently redirecting.
- `/practice/56f9a8a7-ba5f-4f65-9adf-ec5600df3f7a/report` rendered the canonical sales report with the expected degraded enhanced-report copy while the backend still emitted the canonical `practice_session_evidence_projection_built` / `practice_session_report_built` signals.
- `/admin/users/b9b4dd28-75cb-4885-8e87-311c112113a9` showed the supervisor-readable repeated blocker (`异议回应不够具体。`) and next-goal guidance (`下一轮继续把异议回应说完整。`) from the same projection-backed progress data used by the admin APIs.
- `/practice/31e244b6-1006-4ecd-a15b-7c8a673bff17/report` and `/practice/0767567f-43ca-493d-a855-5cc6262e19ba/report` stayed presentation-shaped on both happy and degraded paths, with the degraded session explicitly carrying `missing_page_metadata` through the canonical report route instead of falling back to sales semantics.
- `/support/runtime` showed the seeded blocking and warning anomalies on the page and through the API: `stuck_scoring` and `knowledge_search_failed` / `not_evaluable_completed` for sales, `presentation_degraded_missing_page_metadata` and `optional_report_failed` for the degraded PPT session.

That final wave is what makes S08 materially different from the earlier slices: support/admin/report/runtime all now agree on what is broken, what is merely degraded, and which session proves it.

## Verification

Fresh verification evidence for the slice-close state:

- Repo-root gate fix:
  - `venv/bin/alembic upgrade head` — pass
  - `venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` — pass
- Slice-plan backend/web matrix:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py` — pass
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses` — pass
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py` — pass
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py` — pass
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts'` — pass
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'` — pass
  - `cd backend && venv/bin/alembic upgrade head` — pass
- Live localhost UAT:
  - browser assertions passed for the seeded runtime page, canonical sales report, admin user progress page, PPT happy/degraded report pages, and `/support/runtime`
  - backend logs emitted `practice_session_evidence_projection_built`, `practice_session_report_built`, `practice_history_projection_query`, and `support_runtime_release_health_built` during the same run
  - support-runtime API cross-check matched the browser proof for seeded sessions `9beffdcd-cac2-47cb-ab54-cc4e1dc7c840`, `cd18a276-980b-4400-9ccc-6c3b24a801d5`, and `0767567f-43ca-493d-a855-5cc6262e19ba`

## Requirements Advanced

- R011 — S08 extended the shared evidence-line proof into the launch-health surface: `/support/runtime`, canonical reports, and supervisor progress now all read persisted session evidence plus shared runtime diagnostics rather than drifting into a separate release console truth source.

## Requirements Validated

- R001 — The live `/practice/{sessionId}` page still keeps runtime failure on the practice surface with reconnect/error visibility instead of fake terminal redirects, and the lifecycle/reconnect suites stayed green.
- R002 — Failure visibility now spans the user page, canonical report degradation, supervisor projection reads, and the support-runtime anomaly surface on one shared diagnostic line.
- R003 — The canonical sales report live check still surfaced value-translation main issue and next goal from the sales-specific evidence contract.
- R005 — The learner report remained readable and authoritative even when optional enhanced-report endpoints returned 404/500.
- R007 — The supervisor page and admin progress API still answered recent-change / repeated-blocker questions from the projection-backed evidence line.
- R008 — Happy and degraded PPT sessions remained presentation-shaped on the shared report route, with explicit degraded reasons when page evidence was incomplete.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The only material deviation from the written slice plan was verification-path hardening: the final gate executed repo-root Python commands instead of the `cd backend` variants in the plan, so I had to add repo-root Alembic/pytest shims and backend `.env` fallback support before the slice could be truthfully closed. That changed the delivery surface for verification, not the product scope.

## Known Limitations

- The repo-root verification shims (`alembic.ini`, `pyproject.toml`, `tests` symlink, backend `.env` fallback) are now part of the real closeout path. If a future slice moves backend config again, those shims must be updated too or the final gate will regress while task-level verification stays green.
- Optional enhanced-report endpoints still emit 404/500 noise for sessions without staged report data. The product now degrades correctly, but the noisy enhancement layer is still noisy.
- A locally blocking `/support/runtime` status does not automatically mean the shipped support surface is wrong; in this slice-close run it correctly reflected both pre-existing historical anomalies and the seeded verification faults used to prove blocking/warning mapping.

## Follow-ups

- M002 can reuse the S08 seeded localhost proof pattern when it needs deterministic evidence for runtime/coach/report/admin interactions without depending on whatever stale local data already exists.
- If future slices add more backend verification commands, add them to the repo-root shim path early instead of waiting for the final gate to expose the mismatch.

## Files Created/Modified

- `backend/src/common/conversation/runtime_diagnostics.py` — shared knowledge/runtime diagnostic helper now reused by both canonical knowledge-check and support runtime.
- `backend/src/support/services/runtime_status_service.py` — evidence-backed release-health aggregator and typed anomaly classifier.
- `backend/src/support/api/runtime_status.py` — thin RBAC/response shaping layer on top of the new support runtime service.
- `web/src/app/(dashboard)/support/runtime/page.tsx` — blocking/warning release-health UI with typed anomaly rows and local empty/error handling.
- `web/src/app/(dashboard)/support/runtime/page.test.tsx` — focused support-runtime UI coverage.
- `backend/src/common/config.py` — loads `backend/.env` even when verification runs from repo root.
- `alembic.ini` — repo-root Alembic shim for the final auto verification gate.
- `pyproject.toml` — repo-root pytest shim for the final auto verification gate.
- `tests` — repo-root symlink to `backend/tests` so gate paths resolve.
- `.gsd/milestones/M001/slices/S08/S08-UAT.md` — fresh S08 UAT script plus the completed localhost release-wave evidence.
- `.gsd/milestones/M001/slices/S08/S08-SUMMARY.md` — slice-close summary artifact.
- `.gsd/PROJECT.md` — refreshed current state to mark M001 closed and capture the shipped S08 release-health surface.
- `.gsd/REQUIREMENTS.md` — reinforced R011 with S08’s support-runtime evidence-line proof.
- `.gsd/KNOWLEDGE.md` — recorded the repo-root gate/shim pitfall.
- `.gsd/milestones/M001/M001-ROADMAP.md` — marked S08 complete.

## Forward Intelligence

### What the next slice should know
- M001 is now closed. The most reusable asset from S08 is not a component; it is the proof recipe: deterministic seed data + localhost browser checks + backend signal cross-checks on the same evidence line.

### What's fragile
- Repo-root verification compatibility — the slice will look finished from inside `backend/`, then fail at the final gate if the root shims drift out of sync with backend config.
- Optional enhanced-report endpoints — they still fail noisily and rely on the report page’s degraded copy to avoid confusing users.

### Authoritative diagnostics
- `support_runtime_release_health_built` — quickest trustworthy release-health signal because it already reflects the typed anomaly classification shown on `/support/runtime`.
- `practice_session_report_built` and `practice_history_projection_query` — best first stop when report, admin progress, and support runtime disagree, because all three surfaces now converge there.

### What assumptions changed
- We started S08 assuming the existing slice-plan verification commands were the whole story. In practice, the real closeout path also required repo-root compatibility because auto verification does not guarantee a `cd backend` context for final gate commands.

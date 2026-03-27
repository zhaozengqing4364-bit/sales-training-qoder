---
id: S03
parent: M006
milestone: M006
provides:
  - A dedicated `ManagerInterventionWriteService` that now owns supervisor intervention create/update/remind/list lifecycle rules behind the existing admin API.
  - A shared `manager_intervention_results` analytics seam that makes latest-evaluable-after-creation supervisor outcome semantics explicit and reusable.
  - A locked `/admin/users/[id]` UI contract for pending supervisor results, proving that waiting-state copy remains visible and report drill-ins appear only when a real follow-up completed session exists.
requires:
  - slice: S01
    provides: The shared `/admin/users/[id]` drill-in/read-side seam on the current user-detail page, which S03 preserved while moving workflow logic behind extracted services.
affects:
  - S05
key_files:
  - backend/src/admin/services/manager_intervention_service.py
  - backend/src/admin/api/interventions.py
  - backend/src/common/analytics/manager_intervention_results.py
  - backend/src/common/analytics/history_service.py
  - backend/tests/integration/test_admin_interventions_api.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/app/admin/users/[id]/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D091: Keep `/api/v1/admin/interventions` as transport/auth wrappers and move supervisor write-side lifecycle rules into `ManagerInterventionWriteService`.
  - D092: Keep HistoryService as the query/projection orchestrator and delegate supervisor intervention result semantics to `common.analytics.manager_intervention_results`.
  - D093: Render pending supervisor intervention results on `/admin/users/[id]` as `最近结果：等待新训练` with no report drill-in until a follow-up completed session exists.
patterns_established:
  - Keep FastAPI admin handlers as transport/auth wrappers and move workflow lifecycle rules into dedicated services instead of leaving state transitions in route functions.
  - Keep workflow-specific read semantics in a dedicated analytics resolver and let HistoryService remain the query/projection orchestrator.
  - Lock service seams with integration tests that monkeypatch the route/history module’s imported service symbol, so delegation is proven through the real HTTP authority path instead of drifting into unit-only coverage.
  - Treat pending supervisor intervention results as a first-class contract branch: waiting-state copy is valid only when there is no completed session after the intervention, and that branch must not render a report drill-in.
observability_surfaces:
  - backend/tests/integration/test_admin_interventions_api.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/app/admin/users/[id]/page.test.tsx
  - Structured logs `manager_intervention_created` and `manager_lite_reminder_logged` from the extracted write service
  - Fresh localhost `/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2` browser proof after reload: pending-result text visible, no `查看对应统一报告` link, and no fresh console/network failures
drill_down_paths:
  - .gsd/milestones/M006/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T10:38:56.601Z
blocker_discovered: false
---

# S03: 主管 workflow service seam 抽取

**S03 extracted dedicated supervisor workflow write/read seams while preserving the current `/api/v1/admin/interventions` and `/admin/users/[id]` contract, including the pending-result-without-report-link behavior.**

## What Happened

S03 closed the supervisor-workflow seam without changing the shipped admin contract. On the write side, T01 extracted `ManagerInterventionWriteService` so `manager_interventions` list/create/update/remind behavior, due-state transitions, reminder-state normalization, resolving-session validation, and latest-open lookup now live behind one dedicated service. The FastAPI routes in `/api/v1/admin/interventions` were intentionally reduced to transport/auth wrappers, and the integration suite now monkeypatches the route module’s imported service symbol so future refactors cannot silently pull logic back into the handlers.

On the read side, T02 extracted the latest-evaluable supervisor-result rule into `common.analytics.manager_intervention_results`. That seam now owns issue-family normalization plus the key semantic that the latest evaluable completed session after intervention creation wins over a later thin non-evaluable session. `HistoryService` still owns the admin query/projection orchestration, but it now delegates intervention outcome construction to a dedicated resolver, which keeps the current `/api/v1/admin/users/{id}/sessions` payload stable while making the workflow semantics explicit and reusable.

T03 then re-verified the current `/admin/users/[id]` authority surface and tightened the UI proof around the branch that was easiest to miss: when a newer intervention exists but no completed session follows it yet, the page must keep showing `最近结果：等待新训练` and must not offer a report drill-in. Focused web regression now locks that behavior, and a fresh localhost live proof confirmed the real page still renders the waiting-state copy on the seeded S03 verification learner while producing no fresh console or failed-network signals after reload.

The net slice outcome is a smaller edit surface for the supervisor workflow. Downstream slices now have one write-side authority and one read-side result resolver to build on, instead of route-local lifecycle logic plus embedded HistoryService-specific heuristics. At the same time, the current admin user-detail surface still behaves the same for supervisors: they can create and remind focus areas from the existing page, inspect result semantics on the same page, and only get a report drill-in when a real follow-up completed session exists.

## Verification

Fresh slice verification passed.

Commands run:
- `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_interventions_api.py tests/integration/test_admin_users_api.py` — passed (23/23 tests, real 8.27s).
- `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'` — passed (1 file, 11/11 tests, real 1.95s).
- Fresh LSP diagnostics were clean for `backend/src/admin/api/interventions.py`, `backend/src/admin/services/manager_intervention_service.py`, `backend/src/common/analytics/history_service.py`, `backend/src/common/analytics/manager_intervention_results.py`, `backend/tests/integration/test_admin_interventions_api.py`, and `backend/tests/integration/test_admin_users_api.py`.
- Fresh localhost live proof passed after starting temporary backend/web servers on `:3444` / `:3445`, authenticating via local dev-login, and opening `http://localhost:3445/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2`: the page showed `最近结果：等待新训练`, `browser_find` confirmed no `查看对应统一报告` link on the pending card, and a reload finished with explicit browser assertions for pending text plus zero fresh console/network failures.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Added delegation-focused regression cases inside the existing backend integration suites and one extra `/admin/users/[id]` page regression for the pending-result branch after live proof showed that waiting-state copy + missing report drill-in were not explicitly anchored yet. No shipped API/UI contract changes were introduced.

## Known Limitations

This slice extracts only the current supervisor workflow seam on the existing `/api/v1/admin/interventions` and `/admin/users/[id]` authority surfaces. It does not yet generalize that seam across the rest of the admin read-model family, and there is still no dedicated production alert if pending/improved/still-blocked branch selection drifts while payloads remain syntactically valid. Correctness is currently protected by focused backend/web regressions, structured logs, and targeted manual page proof.

## Follow-ups

S05 should reuse `ManagerInterventionWriteService` and `common.analytics.manager_intervention_results` instead of re-embedding workflow rules when it assembles the broader shared admin read-model regression pack.

If later slices need supervisor result text or report drill-ins on other admin surfaces, they should consume the existing `manager_intervention_results` payload rather than recomputing pending/improved/still-blocked semantics locally.

Production detection is still mostly regression- and log-driven; if this workflow becomes an operational hotspot, add targeted telemetry for pending-result counts, resolver branch distribution, and missing/incorrect drill-in rendering on admin surfaces.

## Files Created/Modified

- `backend/src/admin/services/manager_intervention_service.py` — Extracted the write-side supervisor workflow authority for list/create/update/remind, including due/reminder normalization, resolving-session validation, and latest-open lookup.
- `backend/src/admin/services/__init__.py` — Exported the new write service seam for admin workflow consumers.
- `backend/src/admin/api/interventions.py` — Reduced the admin intervention routes to transport/auth wrappers that delegate to `ManagerInterventionWriteService` while preserving the existing payload contract.
- `backend/src/common/analytics/manager_intervention_results.py` — Introduced the shared resolver for latest-evaluable-after-creation supervisor intervention outcomes, including pending/not-evaluable/improved/still-blocked semantics.
- `backend/src/common/analytics/history_service.py` — Delegated workflow-specific intervention result resolution to the new analytics seam while keeping HistoryService as the query/projection orchestrator.
- `backend/tests/integration/test_admin_interventions_api.py` — Locked the route-to-service seam with delegation regressions while preserving existing create/remind/update/list API behavior assertions.
- `backend/tests/integration/test_admin_users_api.py` — Locked the read-side resolver seam and latest-evaluable result semantics on the `/api/v1/admin/users/{id}/sessions` authority path.
- `web/src/app/admin/users/[id]/page.test.tsx` — Added pending-result regression coverage so the user-detail page keeps showing waiting-state copy without a report drill-in when no follow-up completed session exists.
- `.gsd/DECISIONS.md` — Recorded D093 for the pending supervisor-result render contract on `/admin/users/[id]`.
- `.gsd/KNOWLEDGE.md` — Captured the pending-result/no-report-link gotcha for future supervisor workflow and regression work.
- `.gsd/PROJECT.md` — Refreshed project state to mark M006/S03 complete and describe the new workflow service/result seams.

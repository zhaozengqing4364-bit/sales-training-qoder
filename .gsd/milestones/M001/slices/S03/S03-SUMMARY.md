---
id: S03
parent: M001
milestone: M001
provides:
  - Learner/supervisor single-session reports that lead with unified evidence verdicts, deterministic next-step coaching, and canonical report drill-ins from admin surfaces
requires:
  - slice: S02
    provides: Unified session evidence projection shared by report/replay/history/trends
affects:
  - S06
  - S08
key_files:
  - backend/src/common/api/practice.py
  - backend/src/admin/api/users.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
key_decisions:
  - Learner and supervisor single-session reads stay on one evidence line: deterministic suggestions come from unified backend evidence and all supervisor drill-ins target /practice/{sessionId}/report.
patterns_established:
  - Treat unified evidence as the only top-line fact source; enhanced reports/highlights remain optional layers and must never displace the core verdict/issue/next-goal/evidence reading path.
  - Any supervisor-facing completed-session preview must be projection-backed and deep-link to the canonical learner report instead of inventing a separate weighted admin summary.
observability_surfaces:
  - GET /api/v1/practice/sessions/{id}/report
  - GET /api/v1/admin/users/{userId}/sessions
  - GET /api/v1/admin/interventions/lists
  - [Report] Loaded unified evidence contract / Enhanced report unavailable / Highlights unavailable browser logs
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_admin_users_api.py
  - web focused report/admin tests
drill_down_paths:
  - .gsd/milestones/M001/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T02-SUMMARY.md
duration: 2h10m
verification_result: passed
completed_at: 2026-03-23T15:18:00+08:00
---

# S03: 单次报告可读化（学员 + 主管）

**Shipped one canonical single-session report surface that now answers “练得怎么样 / 卡在哪 / 下一轮练什么 / 证据是什么” for learners and supervisors, with deterministic coaching copy and admin drill-ins sourced from the same unified evidence projection.**

## What Happened

S03 finished the job S02 started: instead of merely storing shared evidence, the slice now translates that evidence into a readable learner/supervisor decision surface.

On the learner side, `backend/src/common/api/practice.py` now builds deterministic `report.suggestions` from `overall_result`, `main_issue`, `next_goal`, evaluability, and stage evidence instead of placeholder English copy. `web/src/app/(user)/practice/[sessionId]/report/page.tsx` was restructured so the first screen leads with unified-evidence result, main issue, next goal, and evidence, while enhanced report/highlights/knowledge-check remain downstream optional layers. During close-out, I found the dead `导出报告` affordance had reappeared in the current branch despite T01’s intent; I removed it again and locked that absence in the focused report test so the main reading path stays honest.

On the supervisor side, `backend/src/admin/api/users.py` now batch-projects completed sessions through `SessionEvidenceService.build_projection(...)` and returns preview fields like `overall_result`, `evaluable`, `not_evaluable_reason`, `main_issue`, `next_goal`, `feedback_summary`, and `suggestions` instead of relying on the old 0.4/0.3/0.3 admin summary. `web/src/app/admin/users/[id]/page.tsx` and `web/src/components/admin/manager-lite-panel.tsx` both expose a direct `查看报告` path to `/practice/{sessionId}/report`, so supervisors drill into the same authority page learners see.

During live runtime verification I hit one environment blocker that mattered for future operators: the local database was still on Alembic revision `20260317_2200_019`, so admin session preview reads failed with `conversation_messages.transcript_metadata does not exist`. Running `cd backend && venv/bin/alembic upgrade head` applied revision `20260317_2310_020` and unblocked the runtime proof. After that migration, seeded completed sessions proved both the evaluable and not-evaluable report states and showed that admin preview/list endpoints point at the same canonical session ids.

## Verification

Fresh slice verification reruns passed:

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_admin_users_api.py` → **15 passed**
- `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` → **4 passed**

Live/runtime checks completed during recovery:

- Ran `cd backend && venv/bin/alembic upgrade head` to bring the local DB to revision `20260317_2310_020` so admin evidence reads could execute.
- Seeded one completed evaluable-fail sales session and one completed not-evaluable sales session for local user `s03.verification@example.com`.
- Opened `/practice/1398bea9-c25a-454f-ad1c-f645edcb3350/report` and confirmed the first screen leads with `沟通闭环结果` → main issue → next goal, while `导出报告` is absent and unified-evidence fallback remains usable even when enhanced report generation returns `[NO_STAGE_RESULTS]`.
- Opened `/practice/eda38292-9b64-4a8a-a271-c8f237477e9c/report` and confirmed the explicit not-evaluable banner/reason stays visible instead of falling back to normal coaching.
- Queried live admin endpoints after migration and confirmed `/api/v1/admin/users/{userId}/sessions` and `/api/v1/admin/interventions/lists` expose the same projection-backed supervisor preview fields and canonical report session ids for the seeded completed rows.

## New Requirements Surfaced

- none

## Deviations

- Local runtime UAT required applying Alembic migration `20260317_2310_020` because the environment lagged behind the code and admin preview reads hard-failed on missing `conversation_messages.transcript_metadata`.
- The dead `导出报告` affordance had drifted back into `web/src/app/(user)/practice/[sessionId]/report/page.tsx`; I removed it during close-out and tightened the report test so this slice’s must-have is actually enforced.
- The stale recovery artifact `.gsd/milestones/M001/slices/S03/tasks/T02-VERIFY.json` still referenced broken repo-root commands (`pytest tests/...` and `cd ../web`); close-out verification was rerun from the correct root with explicit backend/web paths instead of trusting that stale record.

## Known Limitations

- Enhanced comprehensive report generation can still return `[NO_STAGE_RESULTS]` for thin stage data; the core unified-evidence report remains valid, but the enhanced layer is still best-effort.
- In this local dev setup, server-rendered admin pages are sensitive to auth-cookie host alignment, so the runtime supervisor proof relied on live admin API payloads plus focused UI tests rather than a full browser walk of `/admin/users/[id]`.

## Follow-ups

- Before future runtime UAT on supervisor views, run `cd backend && venv/bin/alembic upgrade head`; otherwise admin session preview failures can masquerade as CORS/browser issues.
- When S06 aggregates trends, reuse the S03 preview dimensions (`overall_result`, `main_issue`, `next_goal`, `evaluable`) instead of inventing a new supervisor vocabulary.
- If future work revives report export, treat it as a separately verified feature rather than a placeholder button.

## Files Created/Modified

- `backend/src/common/api/practice.py` — deterministic learner-facing coaching suggestions now come from unified evidence fields.
- `backend/src/admin/api/users.py` — completed admin session rows now use projection-backed preview fields and canonical report drill-in ids.
- `backend/tests/contract/test_practice_evidence_contract.py` — locks shared report/replay evidence semantics and degraded-state contract.
- `backend/tests/integration/test_admin_users_api.py` — locks supervisor preview fields for completed rows and protects against legacy summary drift.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — first screen leads with result/issue/next goal/evidence and no longer shows the dead export affordance.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — now asserts the report trusts unified evidence and that `导出报告` is absent.
- `web/src/app/admin/users/[id]/page.tsx` — shows projection-backed supervisor preview copy and `查看报告` CTA.
- `web/src/components/admin/manager-lite-panel.tsx` — exposes canonical report drill-in from the not-passed list.
- `.gsd/milestones/M001/slices/S03/S03-SUMMARY.md` — durable slice closure record.
- `.gsd/milestones/M001/slices/S03/S03-UAT.md` — tailored mixed-mode UAT script.

## Forward Intelligence

### What the next slice should know
- S03’s top-line supervisor/learner judgment vocabulary is now stable: `overall_result`, `evaluable`, `not_evaluable_reason`, `main_issue`, `next_goal`, and `feedback_summary` are the fields S06 should aggregate instead of recomputing from raw scores.
- Runtime admin preview failures can stem from schema drift, not frontend regressions. If you see browser-side CORS-looking failures on `/admin/users/{id}/sessions`, check backend logs for missing `transcript_metadata` first.

### What's fragile
- Enhanced report generation remains a thin layer — if stage results are missing it returns `[NO_STAGE_RESULTS]`, so future work must keep the unified-evidence report path independent from comprehensive-report success.
- Local admin runtime walkthroughs depend on auth-cookie host alignment — the data path is correct, but local browser proof can still fail if the frontend SSR request lacks the backend session cookie.

### Authoritative diagnostics
- `backend/tests/integration/test_admin_users_api.py::test_user_sessions_completed_rows_expose_projection_backed_preview_fields` — best guard against supervisor preview drift back to legacy weighting.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — best guard against report-page regressions that reintroduce dead affordances or let enhanced content override unified evidence.
- Backend log + `cd backend && venv/bin/alembic current` — fastest way to distinguish slice regressions from schema-drift runtime blockers.

### What assumptions changed
- “T01 already removed the dead export affordance” — in the assembled slice branch that affordance had reappeared, so close-out had to remove it again and add an explicit regression assertion.
- “Admin preview runtime failures here are probably frontend/CORS issues” — in this environment the first real blocker was a lagging DB migration (`20260317_2310_020`), not the S03 projection logic itself.

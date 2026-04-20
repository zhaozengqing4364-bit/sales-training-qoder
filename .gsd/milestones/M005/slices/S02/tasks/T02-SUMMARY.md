---
id: T02
parent: S02
milestone: M005
provides: []
requires: []
affects: []
key_files: ["web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/users/page.tsx", "web/src/components/admin/manager-lite-panel.tsx", "web/src/app/admin/users/[id]/page.test.tsx", "web/src/components/admin/manager-lite-panel.test.tsx", "web/src/lib/api/client.ts", "web/src/lib/api/types.ts"]
key_decisions: ["Use `/admin/users/[id]` as the primary create/inspect surface for manager interventions, and keep manager-lite as a deep-link launcher with prefilled focus query params."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan verifier fresh under timing: `cd web && /usr/bin/time -p npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` passed all 6 focused tests, covering the manager-lite deep links plus the detail-page intervention inspect/create/remind flow. Also brought up short-lived backend/frontend servers on `:3444` and `:3445` and attempted browser verification, but the local Playwright/browser harness failed before navigation with a module error (`Cannot find module './registry'`), so live browser interaction remained environment-blocked rather than app-blocked."
completed_at: 2026-03-26T07:36:39.551Z
blocker_discovered: false
---

# T02: Added in-place supervisor intervention create/remind UI on the admin user detail page, with manager-lite deep links into that same surface.

> Added in-place supervisor intervention create/remind UI on the admin user detail page, with manager-lite deep links into that same surface.

## What Happened
---
id: T02
parent: S02
milestone: M005
key_files:
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
key_decisions:
  - Use `/admin/users/[id]` as the primary create/inspect surface for manager interventions, and keep manager-lite as a deep-link launcher with prefilled focus query params.
duration: ""
verification_result: passed
completed_at: 2026-03-26T07:36:39.552Z
blocker_discovered: false
---

# T02: Added in-place supervisor intervention create/remind UI on the admin user detail page, with manager-lite deep links into that same surface.

**Added in-place supervisor intervention create/remind UI on the admin user detail page, with manager-lite deep links into that same surface.**

## What Happened

Extended the current frontend API seam with typed manager-intervention list/create/remind methods so the web layer can consume the T01 backend routes without ad-hoc fetches. On the admin user detail page, the page now loads persisted interventions in parallel with stats, sessions, and progress; pre-fills the intervention form from manager-lite query params; renders the current intervention cards with due/reminder state; and lets supervisors create a new focus or record another reminder without leaving the current detail surface. The shared manager-lite panel now deep-links supervisors into `/admin/users/[id]` instead of owning a second workflow surface, and the admin users list now explicitly points supervisors into the detail-page intervention flow.

## Verification

Ran the task-plan verifier fresh under timing: `cd web && /usr/bin/time -p npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` passed all 6 focused tests, covering the manager-lite deep links plus the detail-page intervention inspect/create/remind flow. Also brought up short-lived backend/frontend servers on `:3444` and `:3445` and attempted browser verification, but the local Playwright/browser harness failed before navigation with a module error (`Cannot find module './registry'`), so live browser interaction remained environment-blocked rather than app-blocked.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && /usr/bin/time -p npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` | 0 | ✅ pass | 2060ms |


## Deviations

Extended `web/src/lib/api/client.ts` and `web/src/lib/api/types.ts` beyond the planned page/component files because the frontend had no typed intervention client seam yet. Also updated `web/src/app/admin/users/page.tsx` copy/action labeling so the list surface visibly points supervisors into the detail-page workflow.

## Known Issues

Local browser verification is currently blocked by the agent browser harness failing before navigation with `Cannot find module './registry'`. Focused Vitest verification passed and short-lived backend/frontend server bring-up succeeded, but in-tool browser interaction could not be completed from this environment.

## Files Created/Modified

- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`


## Deviations
Extended `web/src/lib/api/client.ts` and `web/src/lib/api/types.ts` beyond the planned page/component files because the frontend had no typed intervention client seam yet. Also updated `web/src/app/admin/users/page.tsx` copy/action labeling so the list surface visibly points supervisors into the detail-page workflow.

## Known Issues
Local browser verification is currently blocked by the agent browser harness failing before navigation with `Cannot find module './registry'`. Focused Vitest verification passed and short-lived backend/frontend server bring-up succeeded, but in-tool browser interaction could not be completed from this environment.

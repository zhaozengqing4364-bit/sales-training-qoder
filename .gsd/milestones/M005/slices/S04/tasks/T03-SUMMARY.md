---
id: T03
parent: S04
milestone: M005
provides: []
requires: []
affects: []
key_files: ["web/src/app/admin/users/page.tsx", "web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/users/[id]/page.test.tsx", "web/src/components/admin/manager-lite-panel.tsx", "web/src/components/admin/manager-lite-panel.test.tsx", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Preserve admin weekly drill context with explicit `focusBucket` plus `focusIssueFamily` / `focusNote` query params.", "Mirror the weekly risk / inactive / improving lists on `/admin/users` from the existing operating-pack `manager_lists` payload instead of adding a new admin-users API."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the focused manager-lite + admin user-detail Vitest suite after implementation, then reran the task-plan command exactly. `cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed fresh, and `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'` also passed fresh. A live browser smoke attempt against `http://localhost:3445/admin/users` was blocked by `ERR_CONNECTION_REFUSED` because no local frontend server was running."
completed_at: 2026-03-26T13:59:28.482Z
blocker_discovered: false
---

# T03: Aligned admin users drill-ins with the weekly operating pack by preserving bucket and issue-family context through manager-lite, /admin/users, and /admin/users/[id].

> Aligned admin users drill-ins with the weekly operating pack by preserving bucket and issue-family context through manager-lite, /admin/users, and /admin/users/[id].

## What Happened
---
id: T03
parent: S04
milestone: M005
key_files:
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Preserve admin weekly drill context with explicit `focusBucket` plus `focusIssueFamily` / `focusNote` query params.
  - Mirror the weekly risk / inactive / improving lists on `/admin/users` from the existing operating-pack `manager_lists` payload instead of adding a new admin-users API.
duration: ""
verification_result: passed
completed_at: 2026-03-26T13:59:28.484Z
blocker_discovered: false
---

# T03: Aligned admin users drill-ins with the weekly operating pack by preserving bucket and issue-family context through manager-lite, /admin/users, and /admin/users/[id].

**Aligned admin users drill-ins with the weekly operating pack by preserving bucket and issue-family context through manager-lite, /admin/users, and /admin/users/[id].**

## What Happened

Added a weekly drill-in section to `/admin/users` that reads the existing fixed-7-day operating-pack manager lists and shows current risk members, inactive streak members, and improving members directly on the users page. Each drill-in now routes into the current user detail surface with explicit `focusBucket`, and risk members also carry the real `focusIssueFamily` plus a matching supervisor note instead of collapsing to a hardcoded `evidence_gap` focus. Updated `/admin/users/[id]` so the detail page renders a visible weekly drill-context card when it is opened from one of those buckets, while preserving the existing intervention-form prefill on risk flows. Added a focused regression in `web/src/app/admin/users/[id]/page.test.tsx` for the risk-bucket banner and note-prefill behavior. The existing manager-lite drill source also needed a local contract fix: `web/src/components/admin/manager-lite-panel.tsx` now passes the actual issue family from the weekly not-passed list and includes the new `focusBucket` param for all three manager buckets, with a focused test to keep that contract from regressing. Recorded the shared drill contract in D083 and appended a knowledge note so later admin work keeps the operating-pack bucket vocabulary intact across analytics → users → detail.

## Verification

Ran the focused manager-lite + admin user-detail Vitest suite after implementation, then reran the task-plan command exactly. `cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed fresh, and `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'` also passed fresh. A live browser smoke attempt against `http://localhost:3445/admin/users` was blocked by `ERR_CONNECTION_REFUSED` because no local frontend server was running.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1220ms |
| 2 | `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 952ms |


## Deviations

Touched `web/src/components/admin/manager-lite-panel.tsx` and its focused test even though the task plan only listed the admin users pages, because the upstream drill link was still hardcoding `evidence_gap` and would have broken the intended weekly issue-family carry-through.

## Known Issues

Live browser proof is still blocked locally when no frontend server is running. The attempted smoke test against `http://localhost:3445/admin/users` failed with `ERR_CONNECTION_REFUSED`, so this task closes with focused Vitest evidence only.

## Files Created/Modified

- `web/src/app/admin/users/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`
- `.gsd/KNOWLEDGE.md`


## Deviations
Touched `web/src/components/admin/manager-lite-panel.tsx` and its focused test even though the task plan only listed the admin users pages, because the upstream drill link was still hardcoding `evidence_gap` and would have broken the intended weekly issue-family carry-through.

## Known Issues
Live browser proof is still blocked locally when no frontend server is running. The attempted smoke test against `http://localhost:3445/admin/users` failed with `ERR_CONNECTION_REFUSED`, so this task closes with focused Vitest evidence only.

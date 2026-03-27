---
id: T02
parent: S02
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/api/client.ts", "web/src/components/admin/asset-governance.tsx", "web/src/lib/admin/linked-assets.ts", "web/src/lib/api/client-governance.test.ts", "web/src/app/admin/asset-governance.test.tsx", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M006/slices/S02/tasks/T02-SUMMARY.md"]
key_decisions: ["Kept `web/src/lib/api/client.ts` as the sole normalization boundary for `governance_summary` and `linked_asset_changes`, then removed duplicate unknown/dict parsing from `asset-governance.tsx` and `linked-assets.ts`.", "Preserved compatibility for existing admin page imports by re-exporting the shared governance types from the component module while making the component itself consume typed props directly."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Passed the focused frontend normalization suite (`src/lib/api/client-governance.test.ts`, `src/lib/admin/linked-assets.test.ts`, `src/app/admin/asset-governance.test.tsx`) and the slice-planned admin verification suite (`src/app/admin/asset-governance.test.tsx`, `src/app/admin/analytics/page.test.tsx`, `src/app/admin/users/[id]/page.test.tsx`) from `web/`. LSP diagnostics were clean for `web/src/lib/api/client.ts`, `web/src/components/admin/asset-governance.tsx`, `web/src/lib/admin/linked-assets.ts`, and `web/src/app/admin/asset-governance.test.tsx`. A local browser smoke check also confirmed `/admin/analytics` booted the app and redirected to `/login` without an authenticated session, and the temporary Next dev server was shut down afterward."
completed_at: 2026-03-27T08:10:12.448Z
blocker_discovered: false
---

# T02: Centralized admin governance and linked-asset normalization in the frontend API client and switched downstream admin UI helpers to the shared typed contract.

> Centralized admin governance and linked-asset normalization in the frontend API client and switched downstream admin UI helpers to the shared typed contract.

## What Happened
---
id: T02
parent: S02
milestone: M006
key_files:
  - web/src/lib/api/client.ts
  - web/src/components/admin/asset-governance.tsx
  - web/src/lib/admin/linked-assets.ts
  - web/src/lib/api/client-governance.test.ts
  - web/src/app/admin/asset-governance.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M006/slices/S02/tasks/T02-SUMMARY.md
key_decisions:
  - Kept `web/src/lib/api/client.ts` as the sole normalization boundary for `governance_summary` and `linked_asset_changes`, then removed duplicate unknown/dict parsing from `asset-governance.tsx` and `linked-assets.ts`.
  - Preserved compatibility for existing admin page imports by re-exporting the shared governance types from the component module while making the component itself consume typed props directly.
duration: ""
verification_result: passed
completed_at: 2026-03-27T08:10:12.449Z
blocker_discovered: false
---

# T02: Centralized admin governance and linked-asset normalization in the frontend API client and switched downstream admin UI helpers to the shared typed contract.

**Centralized admin governance and linked-asset normalization in the frontend API client and switched downstream admin UI helpers to the shared typed contract.**

## What Happened

I verified the local slice contract first and found that the shared frontend governance interfaces were already present in `web/src/lib/api/types.ts`, but the real contract leak remained in the frontend client and helper layer: admin knowledge-base and voice-runtime methods were returning raw governance payloads, while the governance card and linked-asset helper still reparsed `unknown` values locally. I used the existing focused client-governance tests as the red state, added a type-level governance overview assertion in the admin page suite, and then fixed the client methods to normalize knowledge-base and runtime-profile payloads centrally through the existing normalization helpers. After that, I removed the duplicate unknown parsing from `web/src/components/admin/asset-governance.tsx` and `web/src/lib/admin/linked-assets.ts`, leaving those modules to consume typed contracts only. I preserved compatibility for existing page imports by re-exporting the shared governance types from the component module, recorded the normalization-boundary decision in GSD, and added a knowledge note about `apiFetch<T>()` generics not performing runtime coercion. Focused normalization tests, the planned admin page suites, and touched-file LSP diagnostics all passed. I also performed a quick local browser smoke check by starting `web` on port 3445 and confirming the unauthenticated admin route redirected to `/login`, then shut the temporary dev server down so no background processes were left behind.

## Verification

Passed the focused frontend normalization suite (`src/lib/api/client-governance.test.ts`, `src/lib/admin/linked-assets.test.ts`, `src/app/admin/asset-governance.test.tsx`) and the slice-planned admin verification suite (`src/app/admin/asset-governance.test.tsx`, `src/app/admin/analytics/page.test.tsx`, `src/app/admin/users/[id]/page.test.tsx`) from `web/`. LSP diagnostics were clean for `web/src/lib/api/client.ts`, `web/src/components/admin/asset-governance.tsx`, `web/src/lib/admin/linked-assets.ts`, and `web/src/app/admin/asset-governance.test.tsx`. A local browser smoke check also confirmed `/admin/analytics` booted the app and redirected to `/login` without an authenticated session, and the temporary Next dev server was shut down afterward.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run src/lib/api/client-governance.test.ts src/lib/admin/linked-assets.test.ts src/app/admin/asset-governance.test.tsx` | 0 | ✅ pass | 1720ms |
| 2 | `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1960ms |


## Deviations

`web/src/lib/api/types.ts` already contained the shared frontend governance and linked-asset interfaces locally, so execution reused those existing types and focused on consuming them consistently instead of creating new ones.

## Known Issues

Unauthenticated local browser access to `/admin/*` still redirects to `/login`, so this task only performed a smoke check on app boot/routing and did not run authenticated admin browser UAT.

## Files Created/Modified

- `web/src/lib/api/client.ts`
- `web/src/components/admin/asset-governance.tsx`
- `web/src/lib/admin/linked-assets.ts`
- `web/src/lib/api/client-governance.test.ts`
- `web/src/app/admin/asset-governance.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M006/slices/S02/tasks/T02-SUMMARY.md`


## Deviations
`web/src/lib/api/types.ts` already contained the shared frontend governance and linked-asset interfaces locally, so execution reused those existing types and focused on consuming them consistently instead of creating new ones.

## Known Issues
Unauthenticated local browser access to `/admin/*` still redirects to `/login`, so this task only performed a smoke check on app boot/routing and did not run authenticated admin browser UAT.

---
id: T02
parent: S04
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/admin/assets.ts", "web/src/lib/admin/linked-assets.ts", "web/src/components/admin/asset-governance.tsx", "web/src/app/admin/analytics/page.tsx", "web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/knowledge/page.tsx", "web/src/app/admin/personas/page.tsx", "web/src/app/admin/presentations/page.tsx", "web/src/app/admin/voice-runtime/page.tsx", "web/src/lib/admin/assets.test.ts", "web/src/app/admin/analytics/page.test.tsx", "web/src/app/admin/users/[id]/page.test.tsx", "web/src/app/admin/asset-governance.test.tsx", ".gsd/DECISIONS.md", ".gsd/milestones/M006/slices/S04/tasks/T02-SUMMARY.md"]
key_decisions: ["Recorded D095 to make a shared frontend asset metadata registry the single source of truth for the current four asset labels and admin list routes.", "Changed `AssetGovernanceOverview` to derive its display label from `assetType` so governance pages stop repeating literal asset-label strings."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh frontend helper regressions passed for the new registry seam, and the planned slice verification suite passed across analytics, admin user detail, and governance surfaces. Specifically, `src/lib/admin/assets.test.ts` and `src/lib/admin/linked-assets.test.ts` passed 6/6, and the planned `src/app/admin/analytics/page.test.tsx`, `src/app/admin/users/[id]/page.test.tsx`, and `src/app/admin/asset-governance.test.tsx` suite passed 22/22."
completed_at: 2026-03-27T10:57:14.253Z
blocker_discovered: false
---

# T02: Added a shared frontend asset metadata registry and routed linked-asset plus governance UI through it for the current four asset types.

> Added a shared frontend asset metadata registry and routed linked-asset plus governance UI through it for the current four asset types.

## What Happened
---
id: T02
parent: S04
milestone: M006
key_files:
  - web/src/lib/admin/assets.ts
  - web/src/lib/admin/linked-assets.ts
  - web/src/components/admin/asset-governance.tsx
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/knowledge/page.tsx
  - web/src/app/admin/personas/page.tsx
  - web/src/app/admin/presentations/page.tsx
  - web/src/app/admin/voice-runtime/page.tsx
  - web/src/lib/admin/assets.test.ts
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/app/admin/asset-governance.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/milestones/M006/slices/S04/tasks/T02-SUMMARY.md
key_decisions:
  - Recorded D095 to make a shared frontend asset metadata registry the single source of truth for the current four asset labels and admin list routes.
  - Changed `AssetGovernanceOverview` to derive its display label from `assetType` so governance pages stop repeating literal asset-label strings.
duration: ""
verification_result: passed
completed_at: 2026-03-27T10:57:14.253Z
blocker_discovered: false
---

# T02: Added a shared frontend asset metadata registry and routed linked-asset plus governance UI through it for the current four asset types.

**Added a shared frontend asset metadata registry and routed linked-asset plus governance UI through it for the current four asset types.**

## What Happened

I followed TDD by first adding a focused frontend registry regression in `web/src/lib/admin/assets.test.ts`, verifying it failed because the planned `web/src/lib/admin/assets.ts` file did not exist locally, then creating that shared registry to mirror the backend asset labels and admin list routes for knowledge bases, personas, presentations, and runtime profiles. I refactored `web/src/lib/admin/linked-assets.ts` to delegate label and admin-path fallback resolution to the new registry, switched the analytics and admin user-detail pages to use the shared link helper instead of generic `/admin` fallbacks, and changed `AssetGovernanceOverview` plus the four governance pages to pass `assetType` so governance labels now come from the same shared metadata seam rather than page-specific string literals. I also tightened the analytics and user-detail tests so runtime-profile linked assets still resolve the correct label and route when `asset_label` and `admin_path` are blank in the payload, then reran the helper suite and the planned slice verification command successfully.

## Verification

Fresh frontend helper regressions passed for the new registry seam, and the planned slice verification suite passed across analytics, admin user detail, and governance surfaces. Specifically, `src/lib/admin/assets.test.ts` and `src/lib/admin/linked-assets.test.ts` passed 6/6, and the planned `src/app/admin/analytics/page.test.tsx`, `src/app/admin/users/[id]/page.test.tsx`, and `src/app/admin/asset-governance.test.tsx` suite passed 22/22.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/assets.test.ts' 'src/lib/admin/linked-assets.test.ts'` | 0 | ✅ pass | 1150ms |
| 2 | `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/admin/asset-governance.test.tsx'` | 0 | ✅ pass | 1780ms |


## Deviations

The planner snapshot expected `web/src/lib/admin/assets.ts` to already exist; it did not, so I created it and updated the four governance pages to pass `assetType` into `AssetGovernanceOverview` so the shared registry could own the label mapping.

## Known Issues

None.

## Files Created/Modified

- `web/src/lib/admin/assets.ts`
- `web/src/lib/admin/linked-assets.ts`
- `web/src/components/admin/asset-governance.tsx`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/knowledge/page.tsx`
- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/presentations/page.tsx`
- `web/src/app/admin/voice-runtime/page.tsx`
- `web/src/lib/admin/assets.test.ts`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/app/admin/asset-governance.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/milestones/M006/slices/S04/tasks/T02-SUMMARY.md`


## Deviations
The planner snapshot expected `web/src/lib/admin/assets.ts` to already exist; it did not, so I created it and updated the four governance pages to pass `assetType` into `AssetGovernanceOverview` so the shared registry could own the label mapping.

## Known Issues
None.

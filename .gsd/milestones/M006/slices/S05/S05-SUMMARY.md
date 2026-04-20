---
id: S05
parent: M006
milestone: M006
provides:
  - A shared route-shaped frontend admin read-model seam in `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` for analytics, users list, and user detail.
  - A users-page fallback path that now survives missing `manager_lists` and shared display-label derivation without introducing a second client-state abstraction.
  - A canonical acceptance rule that future admin read-model seam changes must pass the full current M005 admin regression pack, not only helper-local tests.
requires:
  - slice: S02
    provides: The typed governance-summary and linked-asset contract from backend schemas through frontend normalization, which the shared admin read-model seam now consumes instead of reparsing page-local raw payloads.
  - slice: S03
    provides: The extracted manager intervention service/result seam that keeps admin user-detail workflow semantics stable while the read-model glue moved into shared frontend adapters.
  - slice: S04
    provides: The backend/frontend asset registry and linked-asset fallback seam that the new runtime-fault read-model helpers continue to consume for analytics and user-detail linked assets.
affects:
  []
key_files:
  - web/src/lib/admin/read-models.ts
  - web/src/lib/admin/runtime-faults.ts
  - web/src/lib/admin/read-models.test.ts
  - web/src/lib/admin/runtime-faults.test.ts
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/page.test.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M006/M006-RESEARCH.md
  - .gsd/DECISIONS.md
  - .gsd/PROJECT.md
key_decisions:
  - D096: keep the admin seam route-shaped by splitting shared page adapters into `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` instead of introducing a generic dashboard abstraction.
  - D097: reuse `web/src/lib/admin/read-models.ts` for users-page operating-pack and display-label derivation instead of adding a new users-specific hook/store abstraction.
  - D098: use the current full M005 admin regression pack as the canonical acceptance bar for future admin read-model seam refactors.
patterns_established:
  - Keep shared admin read-model glue route-shaped around the shipped admin route family; add focused helpers/adapters for real pages instead of inventing a cross-domain dashboard framework.
  - Route sparse operating-pack fallbacks and users-page display labels through `buildOperatingPackReadModel(...)` plus shared formatter helpers rather than direct raw-payload dereferences in pages.
  - Treat backend + web route-family regression packs as the minimum acceptance bar for any future change to the shared admin read-model seam.
observability_surfaces:
  - web/src/lib/admin/read-models.test.ts
  - web/src/lib/admin/runtime-faults.test.ts
  - web/src/app/admin/users/page.test.tsx
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/unit/test_support_runtime_service.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/integration/test_admin_interventions_api.py
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/integration/test_rbac_access_control_api.py
  - backend/tests/contract/test_analytics.py
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/asset-governance.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/components/admin/manager-lite-panel.test.tsx
drill_down_paths:
  - .gsd/milestones/M006/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S05/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T11:57:11.705Z
blocker_discovered: false
---

# S05: 共享 admin read-model adapter 与全链回归证明

**S05 closed the remaining admin page-level read-model glue behind shared route-shaped adapters and re-proved the full shipped admin route family with the canonical M005 regression pack.**

## What Happened

S05 finished the seam reduction that M006 intentionally deferred until the typed governance contract, supervisor workflow service seam, and asset registry seam were already stable. T01 extracted `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` as the shared frontend authority for the current admin route family’s operating-pack summaries, manager-lite cards, runtime-fault linked-asset enrichment, user progress summaries, and user session/intervention derived state. Analytics, users list, and user detail stopped carrying their own copies of that branching logic and instead consumed shared pure adapters that stay route-shaped around the shipped admin surfaces.

T02 then verified the last real duplication hotspot on `web/src/app/admin/users/page.tsx`. The page was still dereferencing `manager_lists` directly and deriving display labels inline, which meant sparse or missing operating-pack payloads could drift away from analytics and manager-lite semantics. The fix was deliberately small: move users-page fallback and label derivation onto `buildOperatingPackReadModel(...)` and the shared formatter helpers, add a regression for the missing-`manager_lists` path, and keep user-detail type usage aligned with the same seam instead of introducing a new hook/store abstraction.

T03 treated acceptance as route-family proof, not helper-local proof. The slice re-ran the full current M005 admin regression pack across backend analytics/support-runtime/users/interventions/asset-governance/RBAC/contract suites plus the web analytics/asset-governance/user-detail/manager-lite pack. Everything stayed green after the seam migration, which is the strongest evidence that duplication actually dropped without changing the shipped admin behavior. The resulting handoff rule is now explicit for downstream work: if future slices touch `web/src/lib/admin/read-models.ts`, `web/src/lib/admin/runtime-faults.ts`, or their analytics/users/detail consumers, acceptance must still be the full route-family regression pack rather than one helper test or one page snapshot.

For downstream readers, the important architectural boundary is that this seam is intentionally route-shaped, not a generic dashboard framework. Extend it by adding focused adapters and formatters that match the existing admin route family, and only widen it when a real route consumes the new shape. Do not reintroduce page-local operating-pack fallbacks, display-label maps, or linked-runtime-fault parsing. Do not replace it with a second client-side store.

### Operational Readiness
- **Health signal:** the shared seam stays healthy when the focused adapter tests (`read-models.test.ts`, `runtime-faults.test.ts`, `users/page.test.tsx`) and the full M005 admin regression pack all stay green together.
- **Failure signal:** `/admin/users` crashes or renders blank manager-lite sections when `manager_lists` is absent, analytics/user-detail drift on runtime-fault linked assets, or backend analytics/intervention/governance/RBAC suites fail after a seam change.
- **Recovery procedure:** compare the failing route against `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts`, move any duplicated page-local derivation back onto the shared adapters, then rerun the full backend + web admin regression pack before considering the seam restored.
- **Monitoring gaps:** this slice still relies on regression coverage rather than production telemetry for adapter fallback-hit rates or cross-route read-model drift; live detection remains limited to route errors and test coverage.

## Verification

Fresh slice-plan verification passed end to end. `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` passed (3 files, 18 tests). `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'` passed twice fresh (4 files, 28 tests) covering the T02 plan command and the T03 web command. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py` passed fresh (60 tests). Focused LSP diagnostics were also clean for the touched web seam files, and the only remaining backend notes were the already-known Passlib `crypt` deprecation warning plus the duplicate FastAPI operation-id warning for `admin/api/model_configs.py`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor local adaptation only: T02’s remaining work narrowed to `/admin/users` because analytics and user detail were already on the shared seam after T01, and T03 used the shell’s available `python3`-compatible timing wrapper while keeping the planned backend/web regression commands themselves unchanged.

## Known Limitations

The seam is intentionally scoped to the current admin route family rather than a generic dashboard framework. There is still no production telemetry for adapter fallback-hit rates or cross-route read-model drift, and the backend regression pack still emits the pre-existing Passlib `crypt` deprecation warning plus the duplicate FastAPI operation-id warning for `admin/api/model_configs.py`.

## Follow-ups

Use the shared seam as the only extension point for future admin route-family read models, and keep the full backend+web M005 regression pack updated in one place if the shipped admin authority surfaces materially change during milestone validation or later admin expansion work.

## Files Created/Modified

- `web/src/lib/admin/read-models.ts` — Became the shared route-shaped adapter layer for operating-pack summaries, manager-lite buckets, users-page display labels, and user progress/session/intervention derived state.
- `web/src/lib/admin/runtime-faults.ts` — Centralized shared runtime-fault to linked-asset enrichment so analytics and admin user detail consume one linked-fault read model.
- `web/src/lib/admin/read-models.test.ts` — Locked the shared read-model seam with focused regressions, including the users-page missing-`manager_lists` fallback and shared label formatting behavior.
- `web/src/lib/admin/runtime-faults.test.ts` — Locked the shared runtime-fault helper behavior used by the admin route family.
- `web/src/app/admin/analytics/page.tsx` — Switched analytics page-level read-model glue onto the shared operating-pack and runtime-fault adapter seam.
- `web/src/app/admin/users/page.tsx` — Removed the remaining direct `manager_lists` dereference and inline display-label derivation in favor of the shared admin read-model seam.
- `web/src/app/admin/users/page.test.tsx` — Added users-page regression proof for sparse operating-pack payloads and shared display-label behavior.
- `web/src/app/admin/users/[id]/page.tsx` — Kept user-detail progress/session/intervention rendering aligned with the shared seam and corrected local typed read-model usage.
- `.gsd/KNOWLEDGE.md` — Recorded the non-obvious rule that any future shared admin read-model change must still pass the full backend+web admin regression pack.
- `.gsd/milestones/M006/M006-RESEARCH.md` — Captured the post-refactor proof and next-milestone seam lessons for future admin extension work.
- `.gsd/DECISIONS.md` — Recorded D096-D098 covering the route-shaped seam boundary, users-page reuse choice, and canonical full-pack acceptance bar.
- `.gsd/PROJECT.md` — Updated project state to mark S05 delivered and note that M006 is now ready for milestone validation/close-out.

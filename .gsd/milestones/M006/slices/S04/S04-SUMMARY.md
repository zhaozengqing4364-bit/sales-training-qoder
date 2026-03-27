---
id: S04
parent: M006
milestone: M006
provides:
  - A shared backend asset registry that owns the current four asset types’ labels, admin routes, empty governance summary seed, and runtime-reference extraction rules.
  - A matching shared frontend asset metadata registry plus linked-asset helper seam so governance pages, analytics, and user-detail views use the same label/admin-path fallbacks.
  - Fresh regression proof that support/runtime faults and admin linked-asset surfaces still render correct governance labels and admin links for all four shipped asset types, even when payload metadata is sparse.
requires:
  - slice: S02
    provides: The typed `governance_summary` and `linked_asset_changes` contract from backend schema through frontend normalization, which S04 now routes through shared registry/adapter seams instead of page/service-local conditionals.
affects:
  - S05
key_files:
  - backend/src/support/services/asset_registry.py
  - backend/src/support/services/runtime_status_service.py
  - backend/tests/unit/test_support_runtime_service.py
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/contract/test_support_runtime.py
  - web/src/lib/admin/assets.ts
  - web/src/lib/admin/linked-assets.ts
  - web/src/components/admin/asset-governance.tsx
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - web/src/app/admin/asset-governance.test.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D094: backend asset-type metadata for support/runtime governance and linked-change payloads now resolves through a shared `support.services.asset_registry` seam instead of inline service-local conditionals.
  - D095: frontend admin surfaces now resolve supported asset labels and admin routes through the shared `web/src/lib/admin/assets.ts` registry, keeping analytics, user detail, and governance overviews on one metadata vocabulary.
  - T03 intentionally kept the shipped registry/adapter implementation unchanged once backend contract proof was green; the close-out work hardened regression coverage and documented the repeated-badge/fallback-link testing rule instead of adding more indirection.
patterns_established:
  - Treat asset types as registry-first metadata on both backend and frontend: services/helpers/pages consume the registry, but do not own duplicated label/path/ref conditionals.
  - Keep `RuntimeStatusService` as the query/orchestration layer and keep the registry focused on metadata plus reference extraction hooks, so future asset-type additions stay additive instead of smearing business logic into the registry.
  - Resolve linked-asset label/admin-path fallbacks through shared helpers (`asset_registry.py`, `assets.ts`, and `linked-assets.ts`) rather than page-local defaults, so sparse support/runtime payloads still map to the correct current admin surface.
  - When admin UIs legitimately render repeated badges or labels, lock regressions with multi-match assertions and per-type fallback-link checks rather than assuming one visible occurrence.
observability_surfaces:
  - backend/tests/unit/test_support_runtime_service.py
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/contract/test_support_runtime.py
  - web/src/app/admin/asset-governance.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - Current `/api/v1/support/runtime/faults` typed `linked_asset_changes` contract, which remains the authority surface feeding analytics and admin user-detail linked-asset views
drill_down_paths:
  - .gsd/milestones/M006/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T11:11:42.466Z
blocker_discovered: false
---

# S04: 资产 registry 与 adapter seam 收口

**S04 closed the current four asset types behind shared backend/frontend registry seams so governance summaries, linked asset changes, and admin-link fallbacks now resolve through one metadata contract instead of scattered conditionals.**

## What Happened

S04 finished the asset-type seam reduction that M005 left spread across support/runtime services and admin pages. T01 introduced `backend/src/support/services/asset_registry.py` as the backend authority for the four currently shipped asset types — knowledge bases, personas, presentations, and runtime profiles. That registry now owns each type’s display label, admin path builder, empty governance summary seed, and runtime-record reference extraction. `RuntimeStatusService` was intentionally kept as the consumer/orchestrator for change queries and anomaly assembly, but it now pulls metadata, linked asset ids, and enrichment rules from the registry instead of repeating inline per-type maps and conditionals.

T02 mirrored that seam on the frontend. `web/src/lib/admin/assets.ts` became the shared metadata registry for current asset labels and admin list routes, `web/src/lib/admin/linked-assets.ts` now resolves fallback labels/links through that registry, and `AssetGovernanceOverview` switched to deriving display labels from `assetType` rather than page-local literal strings. The result is that the four existing governance pages plus the `/admin/analytics` and `/admin/users/[id]` fault-linked views now share one label/path vocabulary. When support/runtime payloads omit `asset_label` or `admin_path`, the UI no longer falls back to generic `/admin` assumptions; it still renders the correct current asset-specific route for presentation and runtime-profile references, alongside the already-shipped knowledge/persona paths.

T03 then locked the seam with fresh regression proof instead of expanding the abstraction further. The backend verification set proved the shared registry still satisfies the typed `governance_summary` and `linked_asset_changes` contracts on support/runtime and asset-governance API surfaces. The frontend verification set exposed the only real follow-up gap: analytics assertions were assuming a single `中影响` badge, which was stale once the page rendered multiple linked items. Those assertions were updated to multi-match checks, and explicit presentation fallback-link coverage was added to both analytics and admin user-detail tests so all four current asset types now have an anchored admin-link proof when payload metadata is blank. The shipped implementation stayed small: a registry seam for metadata, helpers/components/services that consume it, and focused regressions that ensure future asset-type extensions start at the registry rather than hunting for switch statements.

For downstream work, S05 should treat the new registries as the only supported extension points for current asset metadata. If a future slice adds another asset type or widens admin read models, it should first register the type in backend `asset_registry.py` and frontend `assets.ts`, then thread `assetType`/typed linked-asset payloads through existing consumers, rather than reopening page-local label maps or service-local admin-path branches.

## Operational Readiness
- **Health signal:** the focused backend support/runtime suite plus asset-governance contract/integration tests stay green, and the focused web analytics/user-detail/governance suites keep proving that blank `asset_label`/`admin_path` payloads still render the correct current asset label and admin route for all four shipped asset types.
- **Failure signal:** support/runtime faults or admin linked-asset cards start rendering generic `/admin` links, wrong asset labels, or lose the typed `linked_asset_changes` shape after a new asset-type change.
- **Recovery procedure:** compare the failing asset type against backend `backend/src/support/services/asset_registry.py` and frontend `web/src/lib/admin/assets.ts`, add or repair the missing registry entry and any `assetType` plumbing, then rerun the four S04 verification commands before touching page-local fallback logic.
- **Monitoring gaps:** there is still no production telemetry for unknown asset types, registry fallback-hit counts, or label/path drift; correctness is currently protected by the focused backend/frontend regression pack and support/runtime contract tests rather than live counters.

## Verification

Fresh slice verification passed.

Commands run:
- `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py` — passed (3/3 tests, real 3.97s).
- `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/admin/asset-governance.test.tsx'` — passed (3 files, 26/26 tests, real 1.75s).
- `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/integration/test_asset_governance_api.py tests/contract/test_support_runtime.py` — passed (14/14 tests, real 6.91s).
- `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` — passed (3 files, 26/26 tests, real 1.70s).
- Fresh LSP diagnostics were clean for `backend/src/support/services/asset_registry.py`, `backend/src/support/services/runtime_status_service.py`, `web/src/lib/admin/assets.ts`, `web/src/lib/admin/linked-assets.ts`, `web/src/components/admin/asset-governance.tsx`, and `web/src/app/admin/analytics/page.tsx`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice plan assumed a frontend `web/src/lib/admin/assets.ts` metadata helper already existed, but it did not. S04 created that registry, then threaded `assetType` through the governance pages so the new shared seam could own label mapping instead of page-local strings.

## Known Limitations

The seam is intentionally scoped to the four currently shipped asset types. Adding a fifth asset type still requires mirrored backend/frontend registry entries and regression coverage, and there is no dedicated runtime telemetry yet for unknown asset types or fallback-hit frequency beyond the focused support/runtime and admin page regression pack.

## Follow-ups

S05 should reuse the backend/frontend asset registries as the current metadata authority when it extracts broader shared admin read-model adapters, instead of reintroducing asset-type label/path branching in new adapters or page hooks.

If future work needs live production diagnostics for metadata drift, add explicit telemetry for unknown asset types and registry fallback usage on support/runtime faults and admin linked-asset renders.

## Files Created/Modified

- `backend/src/support/services/asset_registry.py` — Introduced the shared backend asset registry that now owns current asset labels, admin-path builders, and runtime-record reference extraction for the four shipped asset types.
- `backend/src/support/services/runtime_status_service.py` — Refactored support/runtime governance and linked-change enrichment to consume registry metadata instead of inline asset-type conditionals.
- `backend/tests/unit/test_support_runtime_service.py` — Locked the backend registry seam and four-asset reference extraction behavior with focused unit coverage.
- `backend/tests/integration/test_asset_governance_api.py` — Verified that existing asset-governance routes continue exposing the shared typed governance summary contract after the seam extraction.
- `backend/tests/contract/test_support_runtime.py` — Verified that `/api/v1/support/runtime` still exposes typed `linked_asset_changes` contract data on the current authority surface.
- `web/src/lib/admin/assets.ts` — Added the shared frontend asset metadata registry for current asset labels and admin list routes.
- `web/src/lib/admin/linked-assets.ts` — Moved linked-asset fallback label and admin-path resolution onto the shared frontend registry seam.
- `web/src/components/admin/asset-governance.tsx` — Changed the governance overview component to derive its display label from `assetType` rather than repeated literal strings.
- `web/src/app/admin/analytics/page.tsx` — Kept analytics linked-asset rendering on the shared helper path so runtime fault-linked references resolve through the registry seam.
- `web/src/app/admin/users/[id]/page.tsx` — Kept admin user-detail linked-asset rendering on the same shared fallback helper path used by analytics.
- `web/src/app/admin/analytics/page.test.tsx` — Updated analytics assertions for repeated badges and added explicit fallback-link proof so all current asset types stay covered when payload metadata is sparse.
- `web/src/app/admin/users/[id]/page.test.tsx` — Added matching user-detail fallback-link proof for the current four asset types.
- `web/src/app/admin/asset-governance.test.tsx` — Preserved governance UI proof around the shared asset metadata seam.
- `.gsd/KNOWLEDGE.md` — Captured the non-obvious linked-asset testing gotchas and extension rule for future asset-type additions.
- `.gsd/PROJECT.md` — Refreshed project state to mark M006/S04 complete and describe the new asset registry/adapter seam.

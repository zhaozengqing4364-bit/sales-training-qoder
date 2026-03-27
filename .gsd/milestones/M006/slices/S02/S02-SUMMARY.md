---
id: S02
parent: M006
milestone: M006
provides:
  - A shared typed backend contract for `governance_summary` and `linked_asset_changes` across asset routes and support/runtime diagnostics.
  - Centralized frontend normalization for governance and linked-asset payloads so admin pages consume typed data instead of reparsing unknown objects.
  - An end-to-end regression baseline that locks current asset-governance cards and analytics/user-detail fault-linked views to the shared typed contract.
requires:
  - slice: S01
    provides: Shared frontend linked-asset helper and admin route-family seam that S02 now hardens into typed backend/client/UI contracts.
affects:
  - S03
  - S04
  - S05
key_files:
  - backend/src/common/db/schemas.py
  - backend/src/common/knowledge/schemas.py
  - backend/src/agent/schemas.py
  - backend/src/admin/api/voice_runtime.py
  - backend/src/support/api/runtime_status.py
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
  - web/src/components/admin/asset-governance.tsx
  - web/src/lib/admin/linked-assets.ts
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/contract/test_analytics.py
  - backend/tests/contract/test_support_runtime.py
  - web/src/app/admin/asset-governance.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
key_decisions:
  - D089: Anchor the shared backend governance/link-change contract in `backend/src/common/db/schemas.py` and reuse it through explicit response envelopes without changing shipped JSON keys.
  - D090: Normalize `governance_summary` and `linked_asset_changes` only in `web/src/lib/api/client.ts`, with admin helpers/components consuming the typed contracts from `web/src/lib/api/types.ts`.
  - Lock this seam end-to-end with field-level backend contract assertions and typed admin page fixtures rather than letting pages keep their own raw-object fallback parsers.
patterns_established:
  - When a nested admin payload becomes cross-route infrastructure, promote it to one shared backend schema model instead of leaving it as `dict` fields on each response model.
  - `apiFetch<T>()` is not runtime validation: normalize unknown governance/admin payloads exactly once in the API client, then keep downstream helpers and components typed-only.
  - Hardening a shared contract should pair backend OpenAPI/field assertions with typed frontend page fixtures so schema drift is caught before it reaches shipped admin routes.
observability_surfaces:
  - backend/tests/integration/test_asset_governance_api.py
  - backend/tests/contract/test_analytics.py
  - backend/tests/contract/test_support_runtime.py
  - web/src/app/admin/asset-governance.test.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
drill_down_paths:
  - .gsd/milestones/M006/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-27T09:50:16.184Z
blocker_discovered: false
---

# S02: 治理与 admin contract 强类型化

**S02 hardened `governance_summary` and `linked_asset_changes` into one typed backend→client→UI contract, so admin asset pages plus analytics/user-detail fault views now consume the same normalized shapes without changing the shipped JSON keys.**

## What Happened

S02 closed the second M006 seam by replacing weakly typed governance/admin payload handling with one shared contract that now spans backend schemas, frontend normalization, and admin UI consumption.

T01 established the backend anchor. Shared `AssetGovernanceSummary` and `LinkedAssetChangeReference` models now live in `backend/src/common/db/schemas.py`, and the knowledge, persona, presentation, voice-runtime, and support/runtime response models reuse those nested types instead of plain `dict` fields. The implementation preserved the shipped payload keys and JSON shape, but the contract is now explicit in Python types and OpenAPI instead of being inferred from ad-hoc dictionaries.

T02 carried the same seam through the frontend boundary. `web/src/lib/api/types.ts` now exposes shared governance and linked-asset interfaces, `web/src/lib/api/client.ts` performs the only normalization step for these admin payloads, and downstream consumers such as `AssetGovernanceSummaryCard` and `web/src/lib/admin/linked-assets.ts` now read already-typed data instead of reparsing `Record<string, unknown>` or page-local raw objects. That removes a drift path where backend routes, client parsing, and UI helpers could silently disagree on field shapes.

T03 then locked the seam end to end. Backend contract tests now assert the shared governance/link-change field shapes directly, and the focused admin page fixtures for asset-governance, analytics, and user-detail are typed against the shared contract so current knowledge/persona/presentation/runtime rows and fault-linked asset sections still render the same behavior after the type hardening.

The net effect is not a new admin surface; it is a lower-drift extension seam. Downstream slices can now build workflow extraction, asset registries, and shared read adapters on top of one explicit governance/change contract instead of raw nested dictionaries split across backend response models, client normalization, and page helpers.

## Verification

Fresh slice verification passed.

Commands run:
- `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py` — passed (24/24 tests, real 7.42s).
- `cd web && /usr/bin/time -p pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` — passed (3 files, 21/21 tests, real 2.43s).
- Fresh LSP diagnostics were clean for `backend/src/common/db/schemas.py`, `backend/src/common/knowledge/schemas.py`, `backend/src/agent/schemas.py`, `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/components/admin/asset-governance.tsx`, `backend/tests/integration/test_asset_governance_api.py`, `backend/tests/contract/test_analytics.py`, `backend/tests/contract/test_support_runtime.py`, `web/src/app/admin/asset-governance.test.tsx`, `web/src/app/admin/analytics/page.test.tsx`, and `web/src/app/admin/users/*/page.test.tsx`.

Observability/diagnostic coverage was confirmed through the support-runtime contract suite and the analytics/user-detail admin page regressions that still render typed linked-asset diagnostics from the shared contract.

## Operational Readiness (Q8)

- **Health signal:** `backend/tests/integration/test_asset_governance_api.py`, `backend/tests/contract/test_support_runtime.py`, and the focused admin page tests stay green, proving the shared contract still reaches both backend OpenAPI/route envelopes and frontend admin surfaces.
- **Failure signal:** admin asset pages start rendering raw objects/empty cards, support/runtime faults lose valid linked asset rows or admin paths, or contract tests begin failing on shared schema refs / field shapes.
- **Recovery procedure:** first inspect any route still emitting raw dict-shaped governance/link-change payloads; restore shared model validation in `backend/src/common/db/schemas.py` and centralized normalization in `web/src/lib/api/client.ts`; then rerun the full backend + web S02 verification set.
- **Monitoring gaps:** production detection is still mostly regression-test based. There is no dedicated runtime alert today for malformed `governance_summary` / `linked_asset_changes` payloads that stay syntactically valid enough to avoid hard page failures.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

This slice only hardens the current `governance_summary` and `linked_asset_changes` seams. It does not yet extract supervisor workflow services (`S03`), introduce the asset registry/adapter seam (`S04`), or close the full shared admin read-model regression pack (`S05`). Detection of malformed governance payloads is still primarily via focused contract/page regressions rather than live production telemetry.

## Follow-ups

S03 should keep using the centralized typed admin contracts instead of reintroducing raw-object parsing while extracting workflow services on `/admin/users/[id]`.

S04 should build the asset registry/adapter seam on top of the typed governance and linked-asset contracts rather than inventing a second asset-label or admin-path mapping layer.

S05 should preserve these typed fixtures and contract assertions inside the broader admin regression pack so future shared read-model work cannot silently loosen the governance/change seam.

## Files Created/Modified

- `backend/src/common/db/schemas.py` — Introduced shared typed governance-summary and linked-asset reference models that now anchor the backend admin contract.
- `backend/src/common/knowledge/schemas.py` — Switched knowledge response models to the shared typed governance contract instead of weak dict fields.
- `backend/src/agent/schemas.py` — Updated persona/admin-support envelopes to reuse the shared governance/link-change schema types.
- `backend/src/admin/api/voice_runtime.py` — Kept current voice-runtime payload keys while routing them through explicit typed governance response models.
- `backend/src/support/api/runtime_status.py` — Exposed support/runtime faults through the shared typed linked-asset contract.
- `web/src/lib/api/types.ts` — Defined shared frontend governance and linked-asset interfaces for admin consumers.
- `web/src/lib/api/client.ts` — Centralized runtime normalization for `governance_summary` and `linked_asset_changes` at the API boundary.
- `web/src/components/admin/asset-governance.tsx` — Switched the governance summary card to consume typed props directly instead of reparsing unknown payloads.
- `web/src/lib/admin/linked-assets.ts` — Kept linked-asset rendering on the shared helper path while moving it onto the typed client contract.
- `backend/tests/integration/test_asset_governance_api.py` — Locked backend governance schema reuse and route/OpenAPI behavior with stronger field-level contract assertions.
- `backend/tests/contract/test_analytics.py` — Kept analytics/admin contract coverage aligned to the typed linked-asset payload used by admin consumers.
- `backend/tests/contract/test_support_runtime.py` — Locked the support/runtime fault contract and linked-asset OpenAPI schema to the shared typed models.
- `web/src/app/admin/asset-governance.test.tsx` — Typed asset-governance fixtures against the shared contract to prove knowledge/persona/runtime cards still render.
- `web/src/app/admin/analytics/page.test.tsx` — Proved analytics fault-linked asset rendering still works from the shared typed contract.
- `web/src/app/admin/users/[id]/page.test.tsx` — Proved admin user-detail fault-linked asset rendering still matches analytics semantics on the typed contract.

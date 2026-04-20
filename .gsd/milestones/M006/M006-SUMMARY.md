---
id: M006
title: "后台共享 seam 收口"
status: complete
completed_at: 2026-03-27T12:12:32.983Z
key_decisions:
  - D086/D088: Keep admin drill-in query construction and read-side fallback-note recovery in `web/src/lib/admin/drill-in.ts` so launcher and destination semantics cannot drift independently.
  - D087: Keep linked-asset parsing and label formatting in `web/src/lib/admin/linked-assets.ts` and preserve the full `LinkedAssetChangeReference` contract in shared helpers.
  - D089/D090: Promote `governance_summary` and `linked_asset_changes` to shared typed backend models and normalize them exactly once in `web/src/lib/api/client.ts` before UI consumption.
  - D091/D092/D093: Keep admin intervention routes as transport/auth wrappers, move workflow lifecycle rules into `ManagerInterventionWriteService`, and keep pending supervisor results on `/admin/users/[id]` as `最近结果：等待新训练` with no report drill-in until a real follow-up completed session exists.
  - D094/D095: Resolve current asset metadata through shared backend/frontend registries instead of page-local or service-local label/path conditionals.
  - D096/D097/D098: Keep the shared admin read-model seam route-shaped (`read-models.ts` and `runtime-faults.ts`) and require the full current backend+web M005 admin regression pack as the acceptance bar for future seam changes.
key_files:
  - web/src/lib/admin/drill-in.ts
  - web/src/lib/admin/linked-assets.ts
  - backend/src/common/db/schemas.py
  - web/src/lib/api/client.ts
  - backend/src/admin/services/manager_intervention_service.py
  - backend/src/common/analytics/manager_intervention_results.py
  - backend/src/support/services/asset_registry.py
  - backend/src/support/services/runtime_status_service.py
  - web/src/lib/admin/assets.ts
  - web/src/lib/admin/read-models.ts
  - web/src/lib/admin/runtime-faults.ts
  - web/src/app/admin/users/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/analytics/page.tsx
lessons_learned:
  - Shared admin seams stayed maintainable only when they were kept route-shaped around the current shipped surfaces; a generic dashboard abstraction would have added indirection without removing real duplication.
  - Backend and frontend asset metadata must be registered in both `backend/src/support/services/asset_registry.py` and `web/src/lib/admin/assets.ts`; changing only one side reintroduces label/path drift immediately.
  - For FastAPI seam extractions, the most trustworthy regression is still a real HTTP integration test that monkeypatches the route module’s imported service symbol instead of only adding unit coverage.
  - For any future change to the shared admin read-model seam, the minimum credible acceptance bar is the full backend+web admin regression pack, not helper-local green tests.
---

# M006: 后台共享 seam 收口

**M006 closed the current admin route family behind shared drill-in, linked-asset, typed-governance, workflow, asset-registry, and read-model seams, then re-proved the whole stack with the canonical backend+web admin regression pack.**

## What Happened

M006 was an internal hardening milestone for the existing admin route family rather than a feature-expansion milestone. S01 first removed page-local drift on the shipped drill-in and linked-asset contracts by centralizing admin user-detail query construction and linked-asset parsing in shared frontend helpers. S02 hardened the same seam end to end by promoting `governance_summary` and `linked_asset_changes` into shared backend schema models, centralizing frontend normalization in the API client, and making the consuming admin surfaces typed instead of raw-object driven. S03 then extracted the supervisor workflow into dedicated write-side and read-side seams while preserving the current `/api/v1/admin/interventions` and `/admin/users/[id]` authority surfaces, including the pending-result branch that must not show a report drill-in before a real follow-up completed session exists. S04 closed the current four asset types behind shared backend/frontend registries so governance labels, admin routes, and linked-change fallback references resolve from one metadata vocabulary instead of scattered conditionals. S05 finished the route-family seam reduction by moving analytics, users list, and user detail read-model glue into shared route-shaped adapters and then rerunning the full current M005 admin regression pack as the canonical acceptance bar.

Milestone-level verification confirmed that the assembled slices work together as intended. `find .gsd/milestones/M006 ...` showed all five slice plan/summary/UAT artifacts on disk. `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` showed extensive non-`.gsd/` implementation changes, so M006 is not a planning-only milestone. Fresh close-out verification reran the canonical backend admin regression pack (`cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py`) and passed 60/60 tests. Fresh close-out verification also reran the canonical web admin regression pack (`cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`) and passed 28/28 tests. Together with the slice summaries and M006 validation artifact, that fresh evidence shows the current admin route family still behaves the same while the shared extension seams are now explicit and reusable.

Validation did surface one documentation-quality gap worth carrying forward: the operational edit-surface reduction is real in code, but future close-out packets should quote the late-slice demo/UAT evidence and show a short explicit “new seam extension touches these authorities only” proof note so the operational claim is retired as directly as the contract and regression claims.

## Success Criteria Results

## Success criteria

1. **Shared admin drill-in contract is centralized and preserved across manager-lite, weekly users list, and user detail** — **Met.** S01 introduced `web/src/lib/admin/drill-in.ts` as the single drill-in authority, and the fresh web regression pack passed `src/components/admin/manager-lite-panel.test.tsx` plus `src/app/admin/users/[id]/page.test.tsx`, confirming launcher and destination semantics still align on the shipped `/admin/users/[id]?focusBucket=...` contract.
2. **Shared linked-asset helper path is used by analytics and user detail without semantic drift** — **Met.** S01 introduced `web/src/lib/admin/linked-assets.ts`, and the fresh web regression pack passed `src/app/admin/analytics/page.test.tsx` and `src/app/admin/users/[id]/page.test.tsx`, confirming linked assets still render with the same labels, status wording, and admin links on both surfaces.
3. **Governance and linked-asset payloads are hardened into one typed backend → client → UI contract** — **Met.** S02 promoted the shared schema into `backend/src/common/db/schemas.py` and centralized normalization in `web/src/lib/api/client.ts`; the fresh backend regression pack passed `tests/integration/test_asset_governance_api.py`, `tests/unit/test_support_runtime_service.py`, and `tests/contract/test_analytics.py`, while the fresh web regression pack passed `src/app/admin/asset-governance.test.tsx` and the analytics/user-detail admin tests.
4. **Supervisor intervention workflow logic is extracted behind a service seam while `/admin/users/[id]` keeps the same result semantics** — **Met.** S03 extracted `ManagerInterventionWriteService` and `manager_intervention_results`; the fresh backend regression pack passed `tests/integration/test_admin_interventions_api.py` and `tests/integration/test_admin_users_api.py`, and the fresh web regression pack passed the user-detail page tests that keep the pending-result contract visible on the current authority surface.
5. **Asset governance labels, admin paths, and linked-change references resolve through one registry/adapter seam across the current four asset types** — **Met.** S04 introduced the shared backend/frontend registries; the fresh backend regression pack passed `tests/unit/test_support_runtime_service.py` and `tests/integration/test_asset_governance_api.py`, and the fresh web regression pack passed `src/app/admin/asset-governance.test.tsx`, `src/app/admin/analytics/page.test.tsx`, and `src/app/admin/users/[id]/page.test.tsx`, which cover the four shipped asset types and sparse-payload fallback links.
6. **Analytics, users list, and user detail are migrated to shared admin read-model adapters/hooks and the M005 regression pack reruns green** — **Met.** S05 established `web/src/lib/admin/read-models.ts` and `web/src/lib/admin/runtime-faults.ts` as the shared route-shaped seam, and the fresh milestone close-out reran the canonical backend+web M005 admin regression pack successfully: 60/60 backend tests and 28/28 web tests passed.

## Horizontal checklist

No separate Horizontal Checklist section was present in `M006-ROADMAP.md`; no unchecked horizontal items were found during close-out review.

## Definition of Done Results

## Definition of done

- **All roadmap slices are complete** — Met. The roadmap slice table shows S01-S05 as complete, and the milestone directory contains `S01` through `S05` plan/summary/UAT artifacts.
- **All slice summaries exist on disk** — Met. File-system verification found `S01-SUMMARY.md` through `S05-SUMMARY.md` under `.gsd/milestones/M006/slices/`.
- **Cross-slice integration works correctly** — Met. The M006 validation artifact found the S01→S02→S03/S04→S05 dependency chain coherent, and fresh milestone close-out verification reran the full backend+web admin regression pack successfully, proving the combined seam extraction still preserves current route-family behavior.
- **Code change verification passed** — Met. `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` produced extensive non-`.gsd/` implementation changes across backend and web admin surfaces, so M006 delivered real code rather than planning-only artifacts.

## Requirement Outcomes

No requirement status transitions were claimed or evidenced during M006. This milestone was an internal admin seam-hardening and regression-proof phase for the existing route family, so `.gsd/REQUIREMENTS.md` remains unchanged.

## Deviations

No material milestone-level deviation from the planned route family. Slice-level adaptations stayed within scope: S04 created the missing frontend asset registry seam that the plan assumed, and close-out validation noted a documentation-proof gap rather than a delivered-behavior gap.

## Follow-ups

Future milestone close-out packets should surface a short explicit operational proof note that shows the edit-surface reduction directly (for example: what files a new drill-in entry or a new asset type now touches) and should quote late-slice demo/UAT evidence as directly as the contract/test evidence.

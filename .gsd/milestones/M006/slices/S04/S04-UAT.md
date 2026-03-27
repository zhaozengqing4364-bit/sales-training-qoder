# S04: 资产 registry 与 adapter seam 收口 — UAT

**Milestone:** M006
**Written:** 2026-03-27T11:11:42.466Z

# S04: 资产 registry 与 adapter seam 收口 — UAT

**Milestone:** M006  
**Written:** 2026-03-27

## UAT Type

- UAT mode: focused asset-registry regression + current admin authority-surface proof
- Why this mode is sufficient: S04 does not introduce a new end-user workflow. It reduces metadata drift behind the existing support/runtime, governance, analytics, and admin user-detail surfaces. Acceptance is therefore whether the current four asset types still resolve the right governance labels, admin routes, and linked-change references through one backend/frontend seam.

## Preconditions

- Repo root: `/Users/zhaozengqing/github/销售训练qoder`
- Backend dependencies installed in `backend/venv`; frontend dependencies installed in `web/node_modules`.
- Planned verification commands available from repo root:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/admin/asset-governance.test.tsx'`
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/integration/test_asset_governance_api.py tests/contract/test_support_runtime.py`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`
- Asset types in scope for this slice:
  - `knowledge_base`
  - `persona`
  - `presentation`
  - `runtime_profile`
- The accepted admin authority surfaces remain:
  - backend support/runtime contracts (`/api/v1/support/runtime/overview`, `/api/v1/support/runtime/faults`)
  - existing governance pages (`/admin/knowledge`, `/admin/personas`, `/admin/presentations`, `/admin/voice-runtime`)
  - existing fault-linked views (`/admin/analytics`, `/admin/users/[id]`)

## Smoke Test

1. Run the backend focused unit command.
2. **Expected:** all 3 tests pass, including `test_asset_registry_covers_current_asset_types_and_extracts_refs`.
3. Run the focused frontend slice command.
4. **Expected:** all 26 tests pass across `asset-governance`, analytics, and admin user-detail.
5. Run the backend contract/integration command.
6. **Expected:** all 14 tests pass, including support/runtime contract checks and asset-governance response model checks.
7. Rerun the web command with the planned T03 order.
8. **Expected:** the same 26 tests pass, proving the final slice gate is green in the exact planned command shape.

## Test Cases

### 1. Backend registry covers the current four asset types

1. Open `backend/tests/unit/test_support_runtime_service.py` and run the focused backend unit suite.
2. Inspect the registry-focused test.
3. **Expected:** the shared registry recognizes `knowledge_base`, `persona`, `presentation`, and `runtime_profile`.
4. **Expected:** each type has a stable display label and an admin path builder.
5. **Expected:** runtime-record reference extraction still returns the correct linked asset ids for the current support/runtime paths.
6. **Expected:** no asset-type-specific label/path/ref logic remains duplicated only inside `RuntimeStatusService`.

### 2. Support/runtime and governance APIs still expose typed asset metadata

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/integration/test_asset_governance_api.py tests/contract/test_support_runtime.py`.
2. Inspect the passing integration/contract cases.
3. **Expected:** knowledge base, persona, presentation, and runtime profile response models all still expose the shared `governance_summary` shape.
4. **Expected:** `/api/v1/support/runtime/faults` still exposes typed `linked_asset_changes` payloads.
5. **Expected:** invalid severity filters are still rejected by the support/runtime contract, proving the seam did not loosen the current API surface.

### 3. Governance pages derive labels from shared asset metadata instead of page-local strings

1. Run the focused web suite covering `src/app/admin/asset-governance.test.tsx`.
2. Inspect the governance overview assertions for the four asset pages.
3. **Expected:** governance cards render the correct current asset label for knowledge bases, personas, presentations, and runtime profiles.
4. **Expected:** the shared component gets that label from `assetType`, not from repeated per-page literal strings.
5. **Expected:** changing the label mapping in the shared frontend registry would be sufficient to update all four governance pages.

### 4. Analytics linked-asset views keep correct fallback labels and routes when payload metadata is blank

1. Run `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx'`.
2. Inspect the linked-asset regression cases.
3. **Expected:** when a linked asset arrives with blank `asset_label` and blank `admin_path`, analytics still renders the correct fallback label and route through the shared registry seam.
4. **Expected:** explicit coverage exists for presentation fallback to `/admin/presentations` and runtime-profile fallback to `/admin/voice-runtime`.
5. **Expected:** the page does not fall back to a generic `/admin` link.

### 5. Admin user-detail linked-asset views keep the same fallback behavior

1. Run `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'`.
2. Inspect the linked-asset and fault-card assertions.
3. **Expected:** the user-detail page uses the same linked-asset helper as analytics.
4. **Expected:** knowledge, persona, presentation, and runtime-profile references each still resolve to the correct admin route even when payload metadata is sparse.
5. **Expected:** analytics and user-detail stay on one fallback vocabulary rather than maintaining separate per-page label/path assumptions.

## Edge Cases

### Repeated badges must not create false regressions

1. Run the analytics suite after rendering a state with multiple linked items that share the same severity badge text such as `中影响`.
2. **Expected:** the test uses multi-match assertions and still passes.
3. **Expected:** the acceptance decision is based on the presence of the correct linked entries and routes, not on a stale assumption that the badge text appears exactly once.

### Sparse payload metadata must still preserve asset-specific admin drill-ins

1. Use the analytics or user-detail fallback regression data where `asset_label` and `admin_path` are intentionally blank.
2. **Expected:** presentation references still point to `/admin/presentations` and runtime-profile references still point to `/admin/voice-runtime`.
3. **Expected:** the UI remains asset-specific rather than degrading to a shared generic admin destination.

### New asset types must fail closed until registered on both sides

1. Attempt to reason about adding a new asset type without updating the shared backend/frontend registries.
2. **Expected:** this is treated as incomplete work, because the accepted extension path is registry-first on both sides.
3. **Expected:** downstream work updates `backend/src/support/services/asset_registry.py`, `web/src/lib/admin/assets.ts`, and the relevant regression coverage before claiming support for the new type.

## Failure Signals

- `RuntimeStatusService` or frontend pages regain asset-type switch statements or page-local label/path maps.
- `/api/v1/support/runtime/faults` loses the typed `linked_asset_changes` contract or starts returning payloads that force UI-local reparsing.
- Analytics or admin user-detail starts rendering generic `/admin` fallbacks for blank metadata instead of the current asset-specific routes.
- Governance pages drift to inconsistent labels between knowledge/persona/presentation/runtime views.
- The analytics regression starts failing because of duplicate badge text and no longer has explicit per-type fallback-link proof.

## Requirements Proved By This UAT

- None directly change status in this slice. S04 hardens the current admin asset-governance seam so downstream slices can reuse it safely.

## Not Proven By This UAT

- Full shared admin read-model adapter closure planned for S05.
- Any new fifth asset type; this slice only proves the current four shipped asset types.

## Notes for Tester

- Treat support/runtime faults plus the current admin analytics and user-detail pages as the accepted authority surfaces. Do not create a second temporary governance console just for validation.
- If a future change appears to break only one asset type, compare backend `backend/src/support/services/asset_registry.py` and frontend `web/src/lib/admin/assets.ts` first; that is the intended single-source-of-truth seam on each side.
- If analytics assertions fail around repeated badge text rather than wrong routes/labels, check whether the test accidentally reverted to a single-match assumption before investigating the registry implementation itself.

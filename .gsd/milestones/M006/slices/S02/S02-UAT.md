# S02: 治理与 admin contract 强类型化 — UAT

**Milestone:** M006  
**Written:** 2026-03-27

## UAT Type

- UAT mode: focused contract + admin route regression
- Why this mode is sufficient: this slice intentionally preserves the shipped admin routes and payload keys while hardening the shared `governance_summary` / `linked_asset_changes` contract from backend schema through client normalization to UI props. The acceptance question is whether current asset-governance cards and analytics/user-detail fault sections still render correctly from one typed contract, not whether a new workflow was introduced.

## Preconditions

- Use an admin account that can access `/admin/knowledge`, `/admin/personas`, `/admin/presentations`, `/admin/voice-runtime`, `/admin/analytics`, and `/admin/users/{id}`.
- Seed/admin data should include:
  - at least one knowledge base, persona, presentation, and voice runtime profile with a non-empty `governance_summary`,
  - at least one support/runtime fault whose `diagnostics.linked_asset_changes` points at real knowledge/persona/presentation/runtime admin paths,
  - at least one admin user detail page that surfaces the same linked asset context through runtime anomalies.
- Automated proof commands available from repo root:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_asset_governance_api.py tests/contract/test_analytics.py tests/contract/test_support_runtime.py`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/asset-governance.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`

## Smoke Test

1. Log in as an admin.
2. Open `/admin/knowledge`, `/admin/personas`, `/admin/presentations`, and `/admin/voice-runtime`.
3. Open `/admin/analytics` and then `/admin/users/{id}` for a seeded learner.
4. **Expected:** all pages load without schema/runtime errors, governance cards still render on asset pages, and analytics/user detail still show runtime-linked asset sections.

## Test Cases

### 1. Knowledge governance card renders the typed shared contract

1. Open a knowledge asset page that shows governance summary content.
2. Inspect the governance card.
3. **Expected:** impact/health/recent-change/session-count style fields render normally; no raw JSON, `undefined`, or fallback object text appears.
4. Refresh the page and verify the card still renders.
5. **Expected:** the card behavior is stable because the page now consumes normalized typed data instead of parsing a raw object locally.

### 2. Persona / presentation / voice-runtime surfaces stay on the same governance contract

1. Open one persona entry, one presentation entry, and one voice-runtime profile that each expose governance summary data.
2. Compare the governance cards/summary rows across these pages.
3. **Expected:** they use the same core field family (health, impact, latest change, session/change counts) and no page requires a custom parser or page-specific fallback to stay readable.
4. **Expected:** pages with sparse/empty values still render a stable empty/neutral state rather than throwing because the contract is typed at the API boundary.

### 3. Analytics runtime faults still render typed linked asset references

1. Open `/admin/analytics` with a seeded runtime/support anomaly carrying `linked_asset_changes`.
2. Go to the linked asset section on the anomaly card.
3. **Expected:** each linked asset row shows the current asset label, admin path link, latest change label, and any impact/status copy derived from the shared typed contract.
4. Click one linked asset.
5. **Expected:** the link opens the expected admin route instead of a broken or guessed path.

### 4. User-detail runtime faults reuse the same linked asset contract

1. Open `/admin/users/{id}` for a learner whose runtime anomaly references linked assets.
2. Find the runtime anomaly / fault section.
3. **Expected:** the linked asset rows match analytics semantics: same asset naming, same recent-change wording, and same admin path behavior.
4. Click a linked asset from user detail.
5. **Expected:** it reaches the same admin asset route represented in analytics for the same reference type.

### 5. Governance summary survives normalization without key-shape drift

1. Open an asset page, then inspect the corresponding network/API response in the browser devtools or API client.
2. Confirm `governance_summary` still uses the existing shipped JSON keys.
3. **Expected:** backend typing did not rename or restructure the public payload; the page still renders correctly because normalization happens in `web/src/lib/api/client.ts`.

## Edge Cases

### Incomplete linked asset rows are ignored rather than rendered as broken diagnostics

1. Use a seeded or mocked runtime fault payload that includes an incomplete `linked_asset_changes` entry, for example missing `admin_path` or `latest_change_label`.
2. Open `/admin/analytics` or `/admin/users/{id}`.
3. **Expected:** the incomplete row is filtered out or omitted; the UI does not show partial labels, `undefined`, or broken links.

### Governance summary with zero / empty counts still renders safely

1. Use an asset whose governance summary contains zero counts or sparse optional fields.
2. Open the corresponding asset page.
3. **Expected:** the governance card renders a neutral/empty state without crashing, proving the shared typed contract handles sparse-but-valid payloads.

## Failure Signals

- Any admin asset page starts rendering raw objects, `undefined`, or empty cards because `governance_summary` is no longer normalized into the typed contract.
- `/admin/analytics` and `/admin/users/{id}` disagree on linked asset labels or one page stops generating valid admin links.
- A backend route changes `governance_summary` or `linked_asset_changes` JSON keys and the UI only works because a page-local parser patched around it.
- Partial linked-asset rows begin rendering as broken diagnostics instead of being filtered.

## Requirements Proved By This UAT

- None — S02 hardens shared admin contracts and regression proof, but it does not by itself change a requirement status.

## Not Proven By This UAT

- Supervisor workflow service extraction planned for S03.
- Asset registry / adapter seam planned for S04.
- Full M006 regression-pack closure planned for S05.

## Notes for Tester

- Keep using `pnpm dlx npm@11.6.1 test -- --run ...` for focused web verification in this environment.
- The acceptance bar is semantic preservation plus typed-contract closure: current pages should behave the same while all governance and linked-asset parsing responsibility has been centralized into shared backend/frontend contracts.

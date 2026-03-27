# S01: 前端 drill-in 与 linked-asset 共享协议收口 — UAT

**Milestone:** M006  
**Written:** 2026-03-27T15:49:24+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: this slice refactors the current admin route family onto shared frontend helpers, so acceptance is proving the exact query-string contract, destination prefill behavior, and linked-asset rendering on the shipped pages plus the focused helper/page regression pack that locks those seams.

## Preconditions

- Use an admin account that can access `/admin/analytics`, `/admin/users`, and `/admin/users/{id}`.
- Have data that includes:
  - at least one user in the current `not_passed` bucket with a real `issue_family`,
  - at least one user in `inactive_streak` or `improving`,
  - at least one support/runtime fault carrying `diagnostics.linked_asset_changes`.
- If running the artifact-driven proof instead of the live UI path, the following repo-root commands must be runnable:
  - `pnpm --dir web dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'`
  - `pnpm --dir web dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'`
  - `pnpm --dir web dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`
  - `pnpm --dir web dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/lib/admin/linked-assets.test.ts' 'src/components/admin/manager-lite-panel.test.tsx' 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`
- For local live UI checks, keep frontend and backend on the same loopback host family so admin auth cookies persist across the web boundary.

## Smoke Test

1. Open `/admin/analytics` as an admin.
2. Scroll to the manager-lite panel and click a `查看详情` link from one of the weekly buckets.
3. **Expected:** the link opens `/admin/users/{id}` with a `focusBucket=...` drill-in query string, and the detail page shows the matching drill-in banner instead of a blank/default state.

## Test Cases

### 1. Manager-lite and users list generate the same current drill-in contract

1. Open `/admin/analytics` and copy a `查看详情` link from the manager-lite `未达标名单`.
2. Open `/admin/users` and copy the matching `查看详情` link for the same bucket/user from the weekly operating drill-in section.
3. Compare the query string.
4. **Expected:** both links use the same `/admin/users/{id}?focusBucket=...` route family; `not_passed` links carry the same `focusIssueFamily` and `focusNote`, while `inactive_streak` and `improving` links keep only the bucket param.

### 2. User detail recovers the shared not-passed note when the URL omits `focusNote`

1. Open `/admin/users/{id}?focusBucket=not_passed&focusIssueFamily=objection_response` directly.
2. Inspect the drill-in banner and the supervisor intervention textarea.
3. Inspect the focus selector.
4. **Expected:** the page still shows the `异议回应` family banner, restores the shared default note text into the recommendation line and textarea, and preselects the matching intervention focus instead of leaving the form blank.

### 3. Non-risk buckets keep their current lightweight drill-in behavior

1. Open `/admin/users/{id}?focusBucket=inactive_streak`.
2. Open `/admin/users/{id}?focusBucket=improving`.
3. **Expected:** both pages show the correct current bucket banner copy, but they do not inject a synthetic risk note or overwrite an existing supervisor note the way a `not_passed` drill-in does.

### 4. Analytics and user detail render linked assets from the same helper path

1. Open `/admin/analytics` and find a fault card that includes linked asset references.
2. Open `/admin/users/{id}` for a user affected by the same fault family.
3. Compare the linked asset labels, health/impact wording, and recent-change line.
4. **Expected:** both pages use the same asset label formatting and change copy, and each linked asset entry includes a working admin path plus the same latest-change text.

### 5. Artifact-driven helper proof keeps the full shared linked-asset contract intact

1. Run `pnpm --dir web dlx npm@11.6.1 test -- --run 'src/lib/admin/linked-assets.test.ts'`.
2. Inspect the `returns the full shared linked-asset contract from runtime diagnostics` assertion.
3. **Expected:** the helper preserves `latest_change_type`, `last_changed_at`, and `sessions_since_change` alongside the fields currently rendered by analytics/user-detail, so downstream typed seams can reuse the same contract without re-parsing the payload.

## Edge Cases

### Manual not-passed URL is partial but still reconstructable

1. Manually remove `focusNote` from a known-good `not_passed` URL while keeping `focusIssueFamily`.
2. Reload the page.
3. **Expected:** the shared helper reconstructs the default note and the page still prefills the current intervention form correctly.

### Linked-asset entry is incomplete

1. Inspect a fault payload or test fixture that contains a `linked_asset_changes` item missing `asset_name`, `admin_path`, or `latest_change_label`.
2. Open the affected analytics/user-detail surface.
3. **Expected:** the incomplete entry is filtered out entirely; the UI does not render broken labels, placeholder admin links, or page-local fallback copy.

## Failure Signals

- Manager-lite and `/admin/users` generate different query strings for the same drill-in bucket.
- `/admin/users/{id}` loses the not-passed recommendation line or textarea prefill when `focusNote` is omitted but `focusIssueFamily` is present.
- `inactive_streak` or `improving` drill-ins start behaving like risk buckets and inject unrelated focus notes.
- `/admin/analytics` and `/admin/users/{id}` show different linked-asset labels or one page renders incomplete entries that the other suppresses.
- `web/src/lib/admin/linked-assets.ts` stops returning the full normalized linked-asset contract even though current pages still appear to work.

## Requirements Proved By This UAT

- None — this UAT proves M006/S01 slice acceptance on the shipped admin route family but does not change formal requirement status.

## Not Proven By This UAT

- The typed governance/admin contract work planned for S02.
- The supervisor workflow service extraction planned for S03.
- The asset registry/shared adapter regression work planned for S04-S05.
- A fresh same-session live browser proof on the local dev stack when admin auth is crossing mismatched host boundaries.

## Notes for Tester

- If the live local admin check redirects back to `/login` after dev-login, verify frontend/backend host alignment first; this slice does not change auth handling.
- The artifact-driven helper/page regression suite is the most trustworthy acceptance signal for this slice because it exercises the exact shared seams introduced in `web/src/lib/admin/drill-in.ts` and `web/src/lib/admin/linked-assets.ts`.

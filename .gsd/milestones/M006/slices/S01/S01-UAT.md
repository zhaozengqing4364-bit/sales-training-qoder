# S01: 前端 drill-in 与 linked-asset 共享协议收口 — UAT

**Milestone:** M006  
**Written:** 2026-03-27

## UAT Type

- UAT mode: focused route-contract + UI regression
- Why this mode is sufficient: this slice intentionally preserves the shipped admin route family and support/runtime payloads while moving duplicated frontend logic into shared helpers. The acceptance question is whether launcher and destination pages still agree on the same drill-in contract, and whether analytics/user-detail now render linked assets through one helper path without semantic drift.

## Preconditions

- Use an admin account that can access `/admin/analytics`, `/admin/users`, and `/admin/users/{id}`.
- The web app is running with seeded admin analytics / user-detail data.
- Seed data should include:
  - at least one `not_passed` user with `issue_family=value_expression` or `objection_response`,
  - at least one `inactive_streak` user,
  - at least one `improving` user,
  - at least one support/runtime fault carrying `diagnostics.linked_asset_changes` pointing at a real admin asset path.
- Automated proof commands available from repo root:
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'`
  - `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`

## Smoke Test

1. Log in as an admin.
2. Open `/admin/analytics` and confirm the manager-lite / weekly operating surfaces load.
3. Open `/admin/users` and confirm the weekly drill-in cards load.
4. Open `/admin/users/{id}` for a seeded learner.
5. **Expected:** all three surfaces render without route errors, and the user-detail page still exposes the current intervention form and linked runtime anomaly section.

## Test Cases

### 1. Manager-lite `not_passed` launcher builds the shared drill-in href

1. Open `/admin/analytics` and locate a `not_passed` manager-lite row.
2. Click `查看并设重点`.
3. Inspect the target URL.
4. **Expected:** the URL is `/admin/users/{userId}?focusBucket=not_passed&focusIssueFamily={issueFamily}&focusNote={sharedDefaultOrExplicitNote}`.
5. On the destination page, confirm the banner reads `本周风险成员` and the issue-family copy matches the launcher row.
6. **Expected:** the intervention form is prefilled with the same issue family and note that the launcher implied.

### 2. Shared fallback note survives partial not-passed drill-in URLs

1. Manually open `/admin/users/{id}?focusBucket=not_passed&focusIssueFamily=objection_response` (omit `focusNote`).
2. Wait for the page to load.
3. **Expected:** the banner still explains `当前这条 drill-in 仍落在「异议回应」这个问题家族。`.
4. **Expected:** the suggested note is auto-recovered as `先对照最近统一报告把异议回应说完整。`.
5. **Expected:** the intervention form uses `objection_response` as the selected focus and the recovered shared note as the textarea value.

### 3. `inactive_streak` drill-ins stay on the current route family and do not overwrite notes

1. From either manager-lite or `/admin/users`, open a `连续未练` entry via `查看详情`.
2. Inspect the target URL.
3. **Expected:** the URL is exactly `/admin/users/{userId}?focusBucket=inactive_streak` with no forced `focusIssueFamily` or `focusNote`.
4. On the destination page, confirm the banner reads `本周连续未练`.
5. **Expected:** the explanatory text says the member came from the continuous-inactive list, and the intervention note field is left unchanged/blank instead of being overwritten by a fallback note.

### 4. `improving` drill-ins keep the same shared destination semantics

1. From manager-lite or `/admin/users`, open an `显著回升` entry via `查看详情`.
2. Inspect the target URL.
3. **Expected:** the URL is exactly `/admin/users/{userId}?focusBucket=improving`.
4. On the destination page, confirm the banner reads `本周显著回升`.
5. **Expected:** the detail page tells the supervisor to review the recent effective action and solidify the next round, and the intervention note field is not force-filled.

### 5. Weekly users list and manager-lite produce the same `not_passed` contract

1. In `/admin/analytics`, note one `not_passed` user and the issue family shown there.
2. Open `/admin/users` and locate the same user in the weekly risk list.
3. Click `查看并设重点` from both surfaces in separate tabs/windows.
4. Compare the query strings.
5. **Expected:** both launchers resolve to the same `/admin/users/{id}?focusBucket=not_passed...` contract for the same issue family and note semantics; neither surface falls back to a page-local or mismatched default.

### 6. Analytics linked-asset section renders shared labels from runtime diagnostics

1. Open `/admin/analytics` with a seeded support/runtime fault carrying `linked_asset_changes`.
2. Go to the `异常关联资产变更` section.
3. **Expected:** each linked asset row shows the shared asset label (for example `知识库 · 石犀产品知识库`), the shared impact label (`高影响` / `中影响` / `低影响`), the shared health label (`阻塞` / `告警` / `健康`), and the latest change label.
4. Click the asset link.
5. **Expected:** it opens the existing admin path from the payload (for example `/admin/knowledge`).

### 7. User-detail linked-asset section renders the same shared helper path

1. Open `/admin/users/{id}` for a user whose runtime fault section includes `linked_asset_changes`.
2. Find the recent runtime anomaly card.
3. **Expected:** the linked asset rows use the same asset-type labels and latest-change copy as analytics, without page-specific fallback wording.
4. Click one linked asset.
5. **Expected:** it opens the same admin asset path exposed in analytics.

## Edge Cases

### Direct issue-family prefill without `focusBucket`

1. Open `/admin/users/{id}?focusIssueFamily=evidence_gap&focusNote=先补ROI与客户案例证据。`.
2. **Expected:** the page does not show a weekly bucket banner, but the intervention form still prefills the issue family and note.
3. **Expected:** this keeps the direct prefill affordance working even when the page is not opened from a weekly bucket launcher.

### Linked-asset fault list has no usable recent asset changes

1. Open `/admin/analytics` or `/admin/users/{id}` with a runtime anomaly set that has no complete linked asset entries.
2. **Expected:** the page falls back to its current empty-state wording instead of rendering partial rows with guessed labels or broken links.

## Failure Signals

- Manager-lite and `/admin/users` produce different query-string shapes for the same drill-in bucket.
- `/admin/users/{id}` loses the not-passed fallback note when `focusIssueFamily` is present but `focusNote` is omitted.
- `inactive_streak` or `improving` drill-ins start forcing issue-family/note fields that were previously blank.
- Analytics and user-detail show different asset-type labels or impact/status wording for the same `linked_asset_changes` payload.
- Linked asset rows render incomplete diagnostics as if they were valid asset links.

## Requirements Proved By This UAT

- None — S01 hardens frontend shared seams for the existing admin route family, but it does not change a requirement status on its own.

## Not Proven By This UAT

- Backend governance typing and client normalization closure planned for S02.
- Supervisor workflow service extraction planned for S03.
- Asset registry / adapter seam planned for S04.

## Notes for Tester

- Keep using `pnpm dlx npm@11.6.1 test -- --run ...` for focused web verification in this environment; the global Volta `npm` wrapper is known to be unreliable.
- The acceptance bar here is semantic preservation: the slice should keep the current admin URLs and copy stable while proving those semantics now come from shared helpers instead of page-local implementations.

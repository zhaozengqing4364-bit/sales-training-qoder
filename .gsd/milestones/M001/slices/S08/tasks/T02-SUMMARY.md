---
id: T02
parent: S08
milestone: M001
provides:
  - typed support/runtime release-health panel with blocking/warning cards and typed anomaly rows
key_files:
  - web/src/app/(dashboard)/support/runtime/page.tsx
  - web/src/app/(dashboard)/support/runtime/page.test.tsx
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
key_decisions: []
patterns_established:
  - Support runtime UI now trusts backend-provided release_health/anomaly_summary/severity fields instead of inferring severity from coarse counts or raw logs.
  - Overview and faults load independently via Promise.allSettled so local empty/error states stay visible without taking down the dashboard shell.
observability_surfaces:
  - /support/runtime
  - /api/v1/support/runtime/overview
  - /api/v1/support/runtime/faults
  - web/src/app/(dashboard)/support/runtime/page.test.tsx
  - .gsd/KNOWLEDGE.md
duration: 32m
verification_result: passed
completed_at: 2026-03-24T17:44:00+0800
blocker_discovered: false
---

# T02: 把 `/support/runtime` 升级成 blocking/warning 发布健康面板

**Reworked `/support/runtime` into a typed blocking/warning release-health panel with local empty/error refresh states.**

## What Happened

I added the missing focused page spec first, locked the blocking-heavy, warning-only, empty, local-failure, and refresh behaviors, then replaced the old coarse support-runtime consumer with the typed T01 contract.

`web/src/lib/api/types.ts` now models `release_health`, `anomaly_summary`, typed `severity`, and compact session/runtime diagnostics. `web/src/lib/api/client.ts` now sends the backend’s `severity` filter instead of the old `status` query. In `web/src/app/(dashboard)/support/runtime/page.tsx`, the top section is now a release-health readout instead of “active/completion/log count”: it shows release status, active/scoring separation, blocking count, warning count, and server-provided kind summaries. The anomaly list now renders `severity`, `kind`, `summary`, `session_id`, `scenario_type`, `session_status`, `report_status`, `detected_at`, and compact diagnostics directly from the API payload.

I also split overview and faults loading with `Promise.allSettled(...)` so `/support/runtime` keeps the shell and the unaffected section visible when only one request fails. The page stays read-only and does not add any learner-report deep links.

## Verification

I ran the focused support-runtime page suite first and got it green. Then I reran the slice’s two web verification commands. The lifecycle/websocket suite passed, and the report/admin/support suite still fails because `src/app/(user)/practice/[sessionId]/report/page.test.tsx` is already red on the missing “综合洞察暂不可用...” fallback copy. I isolated that report test alone and got the same failure, so the slice-level red is a neighboring pre-existing regression, not from the support/runtime panel change.

For browser proof, I started local backend/web servers on `localhost:3444` and `localhost:3445`, authenticated via `/api/v1/auth/dev-login`, and verified `/support/runtime` in three states:
- live blocking/warning state against real backend data;
- mocked healthy-empty state by overriding `window.fetch` for support runtime endpoints and clicking `刷新`;
- mocked local anomaly-list error state the same way, again via `刷新`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(dashboard)/support/runtime/page.test.tsx'` | 0 | ✅ pass | 0.86s |
| 2 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts'` | 0 | ✅ pass | 0.92s |
| 3 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'` | 1 | ❌ fail | 1.16s |
| 4 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 1 | ❌ fail | 0.97s |
| 5 | `Browser UAT — localhost dev-login -> /support/runtime; assert live blocking/warning; override window.fetch for healthy-empty and local faults-error; click 刷新` | 0 | ✅ pass | ~3m |

## Diagnostics

Future agents can inspect `web/src/app/(dashboard)/support/runtime/page.test.tsx` for the intended UI contract, then compare the rendered page with `/api/v1/support/runtime/overview` and `/api/v1/support/runtime/faults`.

The page now exposes three useful diagnostic surfaces without leaving the dashboard:
- release-health status plus blocking/warning counts from `overview.release_health`;
- scoring/stuck/not-evaluable rollups from `overview.session_health`;
- typed anomaly rows with compact diagnostics from `faults.items`.

For local browser verification, don’t route-mock the cross-origin support-runtime endpoints directly; use an in-page `window.fetch` override and hit the page’s `刷新` button.

## Deviations

I did not rerun the unchanged backend slice commands in this frontend-only task. Instead, I reused T01’s fresh backend evidence and reran the slice’s web verification commands plus browser UAT for the changed UI surface.

## Known Issues

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` is already failing on the missing “综合洞察暂不可用，当前页面仅展示统一训练证据。” copy. The broader slice web command remains red until that report-page regression is handled.
- No TypeScript language server is configured in this repo, so I could not use LSP diagnostics; verification relied on the Vitest suites and browser checks above.

## Files Created/Modified

- `web/src/app/(dashboard)/support/runtime/page.tsx` — replaced the coarse support-runtime cards/log list with typed release-health cards, typed anomaly rows, and split local empty/error handling.
- `web/src/app/(dashboard)/support/runtime/page.test.tsx` — added focused coverage for blocking-heavy, warning-only, empty, local faults failure, and refresh behavior.
- `web/src/lib/api/types.ts` — aligned frontend support-runtime types to the backend’s typed overview/fault contract.
- `web/src/lib/api/client.ts` — switched support-runtime faults fetching to the backend `severity` filter and updated typing.
- `.gsd/KNOWLEDGE.md` — recorded the support/runtime browser verification gotcha around cross-origin route mocks vs in-page `window.fetch` overrides.
- `.gsd/milestones/M001/slices/S08/S08-PLAN.md` — marked T02 complete.

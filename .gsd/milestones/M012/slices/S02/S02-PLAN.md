# S02: 导航与系统体验基础

**Goal:** 锁定 learner 共享导航与反馈入口、清理首页死路按钮、补齐 practice 路由错误边界，让新人从首页进入训练闭环时不会因为隐藏入口、空壳操作或白屏而卡住。
**Demo:** After this: 侧边栏有历史入口，所有 learner 页面有 error boundary，首页空壳按钮已处理，有反馈入口

## Tasks
- [x] **T01: Added a shared frontend-only learner help entry to dashboard and practice shells while keeping 历史记录 anchored in SidebarContent.** — ## Description
Close R032 at the real authority seam (`SidebarContent`) instead of page-by-page, then add one lightweight learner help/feedback entry that is reused by both learner shells (`DashboardShell` and `web/src/app/(user)/practice/layout.tsx`). Keep this frontend-only: no new backend/support-email dependency, no admin settings wiring, and no ticketing workflow.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `useCurrentUser` / dashboard shell auth state | Preserve the static nav/help affordance shape and let the existing auth redirect behavior continue; do not add new fetch-dependent UI. | Same as error: help entry stays local/static and does not block shell render. | Ignore malformed user fields and keep help entry copy/path rendering bounded. |
| `next/navigation` route state | Fall back to route-agnostic help copy if pathname/session context is unavailable. | Render the entry without contextual metadata. | Never echo raw query-string/token-like data; only show bounded route/session identifiers. |

## Load Profile

- **Shared resources**: Client render cost in the two learner shells only; no new network or shared backend resources.
- **Per-operation cost**: One extra local dialog/entry render per shell; trivial.
- **10x breakpoint**: N/A — the first risk is visual clutter, not runtime resource exhaustion.

## Negative Tests

- **Malformed inputs**: Missing `currentUser`, missing pathname/context, and collapsed-sidebar/mobile-shell states still render the history nav/help affordance safely.
- **Error paths**: Existing auth redirect path remains intact; the help entry does not depend on support-email config or async fetches.
- **Boundary conditions**: Desktop sidebar, collapsed sidebar, mobile drawer, and practice shell all expose the intended affordance.

## Steps

1. Add a shared learner help/feedback entry component under `web/src/components/layout/` that uses bounded frontend-only copy plus current route/session context, without reading admin support-email settings.
2. Keep `SidebarContent` as the R032 authority seam and add/adjust shell wiring so the help entry appears in both dashboard and practice learner shells.
3. Add focused Vitest coverage proving `历史记录` remains in the shared nav and the help entry appears in dashboard/practice shells across the intended display modes.

## Must-Haves

- [ ] `SidebarContent` remains the source of truth for learner nav and explicitly covers `历史记录`.
- [ ] Dashboard and practice shells both expose the same learner help/feedback affordance.
- [ ] The help/feedback affordance is frontend-only and does not bind to mock admin support-email config.
- [ ] Tests lock desktop/collapsed/mobile/practice visibility for the shared nav/help seams.
  - Estimate: 1.5h
  - Files: web/src/components/layout/sidebar.tsx, web/src/components/layout/dashboard-shell.tsx, web/src/app/(user)/practice/layout.tsx, web/src/components/layout/learner-help-entry.tsx, web/src/components/layout/sidebar.test.tsx, web/src/components/layout/dashboard-shell.test.tsx, web/src/app/(user)/practice/layout.test.tsx
  - Verify: npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx" "src/app/(user)/practice/layout.test.tsx"
- [ ] **T02: Replace dashboard-home dead ends with real history/report actions** — ## Description
Remove the remaining hollow learner actions from `web/src/app/(dashboard)/page.tsx`. Reuse the already-working `/history` and `/practice/{sessionId}/report` route family instead of inventing dashboard-only filter/detail APIs. Any learner-visible control that cannot perform a real action in this slice must become explicitly disabled with clear copy.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `api.dashboard.getHistory()` / dashboard payload | Keep the existing empty/degraded state and route users to `/history`; never strand them behind a fake filter/detail UI. | Keep loading fallback, then degrade to existing empty-state/retry behavior. | Guard missing `session_id`, `scenario_type`, or reportability fields by hiding or disabling the dependent CTA with explicit copy. |
| Existing `/history` + `/practice/{sessionId}/report` routes | Use those routes as the only active destinations; if an item is not reportable yet, keep the CTA explicit/disabled rather than inert. | Same as error: no fake modal flow. | Never synthesize unsupported filter parameters or unsupported detail routes. |

## Load Profile

- **Shared resources**: Existing dashboard stats/recommendation/history API calls only.
- **Per-operation cost**: No new network requests; only client-side link/disabled-state decisions on already-fetched history items.
- **10x breakpoint**: The existing dashboard history list rendering would degrade before this task adds any new cost.

## Negative Tests

- **Malformed inputs**: Missing `session_id`, pending/incomplete sessions, or empty history still produce clear learner-safe CTAs.
- **Error paths**: Failed dashboard history load falls back to empty/retry states without reintroducing hollow controls.
- **Boundary conditions**: Sales + presentation entries keep the existing shared report/history route family.

## Steps

1. Replace the fake homepage filter flow with a real action (for example, routing to `/history`) or an explicitly disabled affordance that explains filtering belongs on the history page.
2. Replace the inert detail/overflow affordances in recent-history cards and dialogs with real report/history links or explicit disabled states driven by the current session data.
3. Extend the existing homepage tests (and any route-family regression assertions they need) so no learner-visible dashboard CTA is left as a silent no-op.

## Must-Haves

- [ ] No learner-visible homepage CTA silently does nothing.
- [ ] Active homepage actions only target already-working `/history` or `/practice/{sessionId}/report` routes.
- [ ] Unsupported detail/filter behaviors are explicit disabled states, not fake interactive UI.
- [ ] Existing dynamic greeting/version and empty-history behavior stay intact.
  - Estimate: 1.25h
  - Files: web/src/app/(dashboard)/page.tsx, web/src/app/(dashboard)/page.test.tsx, web/src/app/(dashboard)/history/page.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"
- [ ] **T03: Add a shared learner route fallback and cover the live practice error boundary** — ## Description
Close the remaining learner white-screen gap by adding `web/src/app/(user)/practice/[sessionId]/error.tsx`, then unify the learner route fallback presentation used by practice/report/replay behind one shared component. Keep the framework-native App Router boundary seam (`error.tsx`), not the legacy class `ErrorBoundary`, and preserve the existing dev-only raw-message diagnostics rule.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Next App Router `error.tsx` + `reset()` contract | Render a friendly fallback with retry and safe navigation; do not bubble to a blank shell. | Same as error — fallback stays local and retryable. | Ignore malformed/non-Error values and show generic copy in production. |
| Shared learner error presenter | If route-specific props are missing, fall back to generic title/body/navigation copy. | Same as error. | Never expose raw stacks outside dev; only show bounded `error.message` in development. |

## Load Profile

- **Shared resources**: Client-side fallback render only.
- **Per-operation cost**: One extra small presenter render when a route throws; trivial in the success path.
- **10x breakpoint**: N/A — if many route failures happen, diagnosis clarity matters more than render cost.

## Negative Tests

- **Malformed inputs**: Missing `error.message`, unexpected thrown values, and absent route metadata still render safe fallback copy.
- **Error paths**: `reset()` can be triggered from the live practice boundary; production mode hides raw diagnostics while development mode shows bounded detail.
- **Boundary conditions**: Practice, report, and replay each keep route-appropriate title/navigation while sharing the same fallback presenter.

## Steps

1. Create a shared learner route-error presenter component with configurable title/body/back-link copy plus dev-only diagnostic rendering and tagged console logging.
2. Add `web/src/app/(user)/practice/[sessionId]/error.tsx` and migrate report/replay `error.tsx` files to reuse the shared presenter.
3. Add focused Vitest coverage proving the live practice route fallback renders retry + safe navigation and that production/dev diagnostic behavior stays bounded.

## Must-Haves

- [ ] `/practice/[sessionId]` gets a real App Router `error.tsx` boundary.
- [ ] Practice/report/replay reuse one shared learner fallback presenter instead of drifting copy/behavior.
- [ ] Production hides raw error diagnostics; development keeps bounded visibility for debugging.
- [ ] Tests lock retry + safe navigation behavior for the live practice fallback.
  - Estimate: 1.25h
  - Files: web/src/components/learner/learner-route-error-state.tsx, web/src/app/(user)/practice/[sessionId]/error.tsx, web/src/app/(user)/practice/[sessionId]/report/error.tsx, web/src/app/(user)/practice/[sessionId]/replay/error.tsx, web/src/app/(user)/practice/[sessionId]/error.test.tsx
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/error.test.tsx"

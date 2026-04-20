# M012/S02 — Research

## Summary

S02 is a targeted web-shell slice centered on **R032** plus adjacent learner-experience gaps already called out in the roadmap and prior audit notes. The good news is that the codebase already has most of the substrate: `web/src/components/layout/sidebar.tsx` already declares `历史记录` in `navItems`, `web/src/app/(dashboard)/history/page.tsx` is a real learner history page with retry/degraded-state handling, and desktop/mobile dashboard navigation both flow through the same `SidebarContent` inside `DashboardShell`. That means R032 is likely **code-shipped but not yet locked/proven**; the slice should not invent a new history feature.

The remaining work is concentrated in three places. First, the homepage still has obvious hollow learner actions in `web/src/app/(dashboard)/page.tsx` (`筛选` dialog with no effective state/API path, inert `查看详情`, inert overflow button). Second, the learner route tree is split: dashboard pages live under `DashboardShell`, but live practice/report/replay live under `(user)/practice`, so any “统一反馈入口” or learner-wide resilience work must account for **both shells**, not only `(dashboard)`. Third, App Router error coverage is incomplete: `(dashboard)/error.tsx` exists, and report/replay each have local `error.tsx`, but the live learner route `web/src/app/(user)/practice/[sessionId]/page.tsx` has no segment error boundary today.

## Recommendation

Treat S02 as a **minimum-safe closure slice**, following the repository’s safe-grow rule to make the smallest direct change and verify immediately. Concretely:

1. **Do not rebuild history navigation.** Keep `SidebarContent` as the authority seam for R032 and add verification around it. Because desktop and mobile both reuse `SidebarContent`, one shell-level test buys parity across both surfaces.
2. **Close hollow homepage actions by routing to existing working surfaces or disabling them explicitly** instead of inventing new APIs. The existing dashboard history API only supports `limit` and optional `scenarioType`; it does not support the homepage’s fake date-range filter. The safer move is to point users to `/history` (which already has a real scenario filter/retry flow) or trim/remove inert controls.
3. **Use Next App Router `error.tsx` boundaries, not the legacy `components/ErrorBoundary.tsx`,** for learner route resilience. Add the missing practice-route segment boundary at `[sessionId]/error.tsx`; optionally extract a tiny shared error-state presenter only if all three learner error files are touched together.
4. **Implement feedback as a lightweight learner-safe entry, not a new backend feature.** I found no real learner feedback API or persisted support-contact setting. The visible “支持邮箱” in `web/src/app/admin/settings/page.tsx` is mock UI only. Prefer a shared frontend affordance (copy/dialog/mailto/static contact text) mounted where learners actually are.

Relevant skill guidance:
- **safe-grow**: select exactly one high-value unresolved issue at a time, make the minimum safe change, verify immediately. That argues against a broad nav redesign or new ticketing subsystem.
- **react-best-practices / `bundle-conditional`**: do not add a heavy third-party feedback widget for this slice; keep the feedback entry lightweight and local to the shell.

## Implementation Landscape

### Key Files

- `web/src/components/layout/sidebar.tsx` — Shared learner navigation authority seam. `navItems` already contains `{ label: "历史记录", href: "/history" }`. Also a natural place for a learner feedback entry if it should live in the shell.
- `web/src/components/layout/dashboard-shell.tsx` — Wraps every `(dashboard)` learner page and reuses `SidebarContent` for both desktop and mobile. Best place to prove navigation parity and to mount a dashboard-wide feedback affordance.
- `web/src/app/(dashboard)/layout.tsx` — Server-authenticated learner dashboard shell entry point; no business logic, but confirms every dashboard page inherits `DashboardShell`.
- `web/src/app/(dashboard)/history/page.tsx` — Real history surface already in production. Has working scenario filter + retry/degraded-state messaging. Good target for homepage CTA redirection instead of implementing fake dashboard-local filtering.
- `web/src/lib/api/client.ts` — Confirms current API capability: `dashboard.getHistory(limit, scenarioType?)` is limited; `user.getMyHistory(...)` powers `/history`. There is no existing learner feedback/contact API.
- `web/src/app/(dashboard)/page.tsx` — Main homepage with the remaining hollow actions: fake `筛选` dialog, inert `查看详情`, inert overflow button. Also already loads recent history, so it can route users to existing report/history surfaces without new data plumbing.
- `web/src/app/(user)/practice/layout.tsx` — Separate learner shell for live/report/replay pages. If feedback is supposed to be available on all learner pages, this tree must be included too.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — Live learner practice route. Large client page, currently no route-local `error.tsx` coverage.
- `web/src/app/(user)/practice/[sessionId]/report/error.tsx` — Existing App Router error boundary for learner report route; can serve as copy/structure baseline.
- `web/src/app/(user)/practice/[sessionId]/replay/error.tsx` — Existing App Router error boundary for learner replay route; same pattern as report.
- `web/src/components/ErrorBoundary.tsx` — Legacy class boundary. Exists, but it is **not** the preferred seam for App Router route failures in this slice.
- `web/src/app/(dashboard)/page.test.tsx` — Existing homepage test file; natural place to add assertions that hollow actions are now routed/disabled correctly.
- `web/src/app/(dashboard)/history/page.test.tsx` — Existing history test pattern already locks learner history/report/replay affordances.
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — Existing live practice test harness; natural place for learner-shell error/fallback related assertions if an error test companion is added.

### Build Order

1. **Lock R032 at the shared shell seam first.** Add/extend a shell/sidebar test proving `历史记录` is visible from learner navigation (ideally against `SidebarContent` or `DashboardShell`, not one page). This retires the risk that the requirement is “present in code but unprotected.”
2. **Close homepage hollow actions with existing routes, not new backend work.** Update `web/src/app/(dashboard)/page.tsx` so every visible learner CTA is either real or explicitly disabled. The safest closures are to reuse `/history` or `/practice/{id}/report` rather than build new filtering/detail flows.
3. **Add the missing learner practice error boundary.** Create `web/src/app/(user)/practice/[sessionId]/error.tsx` (or a tiny shared presenter used by it + report/replay). This closes the largest remaining white-screen risk in the learner tree.
4. **Add a lightweight feedback entry across learner shells.** If the roadmap intent is truly “all learner pages,” mount a shared component in both `DashboardShell` and `practice/layout.tsx`. If the product only requires dashboard discoverability, keep it in `DashboardShell` and document the scope clearly.
5. **Backfill tests around the chosen feedback/hollow-action behavior.** Keep verification close to the touched page/shell tests; do not introduce a new framework.

### Verification Approach

- Shell/nav + homepage:
  - `npm --prefix web test -- --run dashboard`
  - If a dedicated shell/sidebar test file is added, keep its name searchable (for example `sidebar.test.tsx`) so `npm --prefix web test -- --run sidebar` is sufficient.
- History route continuity after CTA changes:
  - `npm --prefix web test -- --run history`
- Live learner page resilience:
  - `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx"`
  - If a dedicated error-boundary test file is added, keep it near the route and run it explicitly.
- Static safety:
  - LSP diagnostics on `web/src/components/layout/sidebar.tsx`, `web/src/app/(dashboard)/page.tsx`, and `web/src/app/(user)/practice/[sessionId]/page.tsx`/new error file.
- Observable behavior to confirm manually if needed:
  - Logged-in dashboard shows `历史记录` in shared nav.
  - Homepage contains no learner-facing dead-end CTA.
  - A thrown error on `/practice/[sessionId]` yields friendly fallback UI instead of a white screen.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Learner history discoverability | `SidebarContent` in `web/src/components/layout/sidebar.tsx` + real `/history` route | R032 is already materially present; safest work is to prove and preserve it rather than create page-local history links. |
| Route-level learner error handling | Next App Router `error.tsx` files (`(dashboard)/error.tsx`, report/replay error files) | These are the framework-native boundaries for route failures; the legacy class `ErrorBoundary` is the wrong seam for this slice’s route resilience goal. |
| Homepage history filtering/detail exploration | `/history` page + `user.getMyHistory(...)` scenario filter | Avoid inventing dashboard-only date filtering/detail APIs just to make hollow homepage controls look real. |

## Constraints

- **R032 is already partially implemented in code.** `sidebar.tsx` already ships the history nav item; the slice should validate/protect it, not redesign it.
- **Learner UI is split across two shells.** `(dashboard)` uses `DashboardShell`; live/report/replay use `practice/layout.tsx`. Any truly learner-wide affordance must consider both trees.
- **Current dashboard history API is limited.** `dashboard.getHistory()` only supports `limit` and optional `scenarioType`; the homepage’s fake date-range filter has no matching backend contract today.
- **No real support-contact config surfaced.** The admin settings “支持邮箱” field is mock UI and should not be treated as a persisted source of truth for learner feedback in this slice.
- **Project constraint:** preserve existing stack, prefer the smallest direct change, and verify immediately after each change.

## Common Pitfalls

- **Fixing R032 in the wrong place** — Adding a history button to one page does not close the requirement. The authority seam is the shared learner nav in `SidebarContent`.
- **Using `components/ErrorBoundary.tsx` for App Router route failures** — It may help for component-local crashes, but it does not replace segment-level `error.tsx` coverage.
- **Turning the homepage filter modal into a mini product** — There is no date-range API path behind it. Prefer rerouting/removing/disabling over inventing unsupported filtering behavior.
- **Sourcing learner contact info from admin settings** — The visible support-email field is not wired to a real persisted config surface.

## Open Risks

- The one unresolved product choice is the exact shape of the “反馈入口”: static “联系管理员” copy, `mailto:`, a small dialog, or a future real support system. The current codebase supports a lightweight frontend-only entry cleanly, but not a real ticketing workflow.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js App Router | `react-best-practices` | available |
| Browser/UAT verification | `browse` | available |
| TanStack Query | `tanstack-query-best-practices` | available |
---
id: T01
parent: S02
milestone: M012
provides: []
requires: []
affects: []
key_files: ["web/src/components/layout/learner-help-entry.tsx", "web/src/components/layout/sidebar.tsx", "web/src/components/layout/dashboard-shell.tsx", "web/src/app/(user)/practice/layout.tsx", "web/src/components/layout/sidebar.test.tsx", "web/src/components/layout/dashboard-shell.test.tsx", "web/src/app/(user)/practice/layout.test.tsx", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Mounted learner help through shared shell seams via a Sidebar/SidebarContent footer slot instead of page-local buttons.", "Kept the help entry frontend-only and only surfaced bounded pathname/sessionId context without reading admin support-email configuration."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh focused shell Vitest verification passed for `sidebar`, `dashboard-shell`, and `practice/layout`. The current slice-level dashboard/history Vitest command also passed in repo state. LSP diagnostics reported no issues on the T01-touched shell files plus `web/src/app/(dashboard)/page.tsx`. Slice-plan diagnostics for the future `practice/*/error.tsx` files remain pending T03 because those files do not exist yet."
completed_at: 2026-04-09T03:36:13.467Z
blocker_discovered: false
---

# T01: Added a shared frontend-only learner help entry to dashboard and practice shells while keeping 历史记录 anchored in SidebarContent.

> Added a shared frontend-only learner help entry to dashboard and practice shells while keeping 历史记录 anchored in SidebarContent.

## What Happened
---
id: T01
parent: S02
milestone: M012
key_files:
  - web/src/components/layout/learner-help-entry.tsx
  - web/src/components/layout/sidebar.tsx
  - web/src/components/layout/dashboard-shell.tsx
  - web/src/app/(user)/practice/layout.tsx
  - web/src/components/layout/sidebar.test.tsx
  - web/src/components/layout/dashboard-shell.test.tsx
  - web/src/app/(user)/practice/layout.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Mounted learner help through shared shell seams via a Sidebar/SidebarContent footer slot instead of page-local buttons.
  - Kept the help entry frontend-only and only surfaced bounded pathname/sessionId context without reading admin support-email configuration.
duration: ""
verification_result: passed
completed_at: 2026-04-09T03:36:13.468Z
blocker_discovered: false
---

# T01: Added a shared frontend-only learner help entry to dashboard and practice shells while keeping 历史记录 anchored in SidebarContent.

**Added a shared frontend-only learner help entry to dashboard and practice shells while keeping 历史记录 anchored in SidebarContent.**

## What Happened

Created `web/src/components/layout/learner-help-entry.tsx` as a shared learner help/feedback dialog that only uses local route/session context and static copy. Preserved `SidebarContent` as the learner navigation authority seam by keeping `历史记录` in the shared nav and introducing a footer-slot seam on `Sidebar` / `SidebarContent` for shell-level affordances instead of page-local duplication. Mounted the same help component in dashboard desktop sidebar, dashboard mobile drawer, and practice layout. Added focused Vitest coverage for history-nav preservation, collapsed-sidebar help rendering, dashboard desktop/mobile reuse, auth-redirect non-blocking behavior, and practice-shell route/session sanitization. Recorded the shell-mounting decision in `.gsd/DECISIONS.md` and the shared-nav `menuitem` testing gotcha in `.gsd/KNOWLEDGE.md`.

## Verification

Fresh focused shell Vitest verification passed for `sidebar`, `dashboard-shell`, and `practice/layout`. The current slice-level dashboard/history Vitest command also passed in repo state. LSP diagnostics reported no issues on the T01-touched shell files plus `web/src/app/(dashboard)/page.tsx`. Slice-plan diagnostics for the future `practice/*/error.tsx` files remain pending T03 because those files do not exist yet.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx" "src/app/(user)/practice/layout.test.tsx"` | 0 | ✅ pass | 1724ms |
| 2 | `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"` | 0 | ✅ pass | 1722ms |
| 3 | `LSP diagnostics on web/src/components/layout/sidebar.tsx, web/src/components/layout/dashboard-shell.tsx, web/src/app/(user)/practice/layout.tsx, web/src/components/layout/learner-help-entry.tsx, web/src/app/(dashboard)/page.tsx` | 0 | ✅ pass | 0ms |


## Deviations

None.

## Known Issues

Slice-level diagnostics for the future `web/src/app/(user)/practice/[sessionId]/error.tsx`, `report/error.tsx`, and `replay/error.tsx` files remain pending T03 because those files do not exist yet.

## Files Created/Modified

- `web/src/components/layout/learner-help-entry.tsx`
- `web/src/components/layout/sidebar.tsx`
- `web/src/components/layout/dashboard-shell.tsx`
- `web/src/app/(user)/practice/layout.tsx`
- `web/src/components/layout/sidebar.test.tsx`
- `web/src/components/layout/dashboard-shell.test.tsx`
- `web/src/app/(user)/practice/layout.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
None.

## Known Issues
Slice-level diagnostics for the future `web/src/app/(user)/practice/[sessionId]/error.tsx`, `report/error.tsx`, and `replay/error.tsx` files remain pending T03 because those files do not exist yet.

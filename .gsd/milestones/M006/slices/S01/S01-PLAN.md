# S01: 前端 drill-in 与 linked-asset 共享协议收口

**Goal:** Extract the current admin drill-in context (`focusBucket` / `focusIssueFamily` / `focusNote`) and linked-asset parsing/labeling into single-source frontend helpers reused by the shipped admin pages.
**Demo:** After this: Show manager-lite and users-list drill-ins generating the same `/admin/users/[id]?focusBucket=...` context, and show analytics/user-detail linked asset sections both rendered from the same shared helper path.

## Tasks
- [x] **T01: Extracted a shared admin drill-in href builder and migrated manager-lite plus users-list launchers onto it without changing the shipped route contract.** — Inventory the current `focusBucket` / `focusIssueFamily` / `focusNote` URL builders in manager-lite and users list, then create `web/src/lib/admin/drill-in.ts` exporting the shared bucket type, default-note resolution, and href builder. Migrate launcher code to call the helper while preserving the exact query-string shape used today.
  - Estimate: 0.5d
  - Files: web/src/lib/admin/drill-in.ts, web/src/components/admin/manager-lite-panel.tsx, web/src/app/admin/users/page.tsx, web/src/components/admin/manager-lite-panel.test.tsx
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/components/admin/manager-lite-panel.test.tsx'
- [x] **T02: Made admin user-detail drill-ins recover shared not-passed guidance text and locked the banner/prefill contract in tests.** — Move current user-detail `focusBucket` parsing and banner-context derivation onto the shared drill-in helper. Preserve the shipped badge/copy behavior for `not_passed` / `inactive_streak` / `improving`, and update focused tests so the context contract is locked from both launcher and destination sides.
  - Estimate: 0.5d
  - Files: web/src/lib/admin/drill-in.ts, web/src/app/admin/users/[id]/page.tsx, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'
- [ ] **T03: 抽出 shared linked-asset parser** — Create `web/src/lib/admin/linked-assets.ts` with shared linked-asset change typing, parsing, filtering, and label helpers. Migrate `/admin/analytics` and `/admin/users/[id]` to use it so fault-linked asset sections stop owning duplicate parser code.
  - Estimate: 0.5d
  - Files: web/src/lib/admin/linked-assets.ts, web/src/app/admin/analytics/page.tsx, web/src/app/admin/users/[id]/page.tsx, web/src/app/admin/analytics/page.test.tsx, web/src/app/admin/users/[id]/page.test.tsx
  - Verify: cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/analytics/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'

# App Router Guide — `web/src/app/`

Scope: Next.js App Router pages and layouts only. For component/UI rules, see `.kiro/steering/frontend-principles.md`.

## Route-Group Map

- `(auth)/` — Unauthenticated surface (`login/`, `forgot-password/`, `reset-password/`). No shell layout; minimal wrappers.
- `(dashboard)/` — Authenticated learner dashboard surface (`page.tsx`, `training/`, `history/`, `leaderboard/`, `profile/`, `support/`, `agents/`). Wrapped by `layout.tsx` → `DashboardShell` + `requireServerSession`.
- `(user)/practice/[sessionId]/` — Dense learner practice surface. The heaviest route-local code lives here (page, replay, report, hooks, tests).
- `admin/` — Dense operator surface. Wrapped by `layout.tsx` → `AdminShell` with `requiredRoles: ["admin"]`. Contains `analytics/`, `agents/`, `knowledge/`, `personas/`, `presentations/`, `prompts/`, `rag-profiles/`, `records/`, `retrieval-strategies/`, `settings/`, `users/`, `voice-runtime/`.

## Layout Boundaries

Layouts in this tree are authorization + shell boundaries. Do not add heavy data fetching in them.

- `layout.tsx` (root) — global providers, background, metadata.
- `(dashboard)/layout.tsx` — `DashboardShell` + session gate.
- `admin/layout.tsx` — `AdminShell` + admin role gate.
- `(user)/practice/layout.tsx` — practice-specific chrome.

## Local Conventions

- **Co-location encouraged**: route-local hooks, tests, and small utilities live next to the pages that use them (e.g., `use-practice-recording-hotkeys.ts`, `page.test.tsx`, `runtime-lock.ts`).
- **No `route.ts` handlers** in this tree; API calls go to `backend/` via `web/src/lib/api/`.
- **Error/loading states** are owned per segment (`error.tsx`, `loading.tsx`). Mirror siblings when adding new routes.
- **Tests** at route level validate shell behavior and page render, not full integration.

## Where to Look

- Dashboard logic & learner entry: `(dashboard)/page.tsx`
- Practice session (dense learner UX): `(user)/practice/[sessionId]/page.tsx`
- Admin entry: `admin/page.tsx`
- Shared shell components: `web/src/components/layout/`
- Detailed frontend rules: `.kiro/steering/frontend-principles.md`

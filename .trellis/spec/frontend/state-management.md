# State Management

> Local state, server state, and global UI state in this project.

---

## Overview

**Document reality first**: most admin and dashboard pages load data with **`useEffect` + `useState` + `api.*`**, not React Query. **TanStack React Query v5** is wired (`lib/query/client.ts`) but today primarily powers **current user** via `useCurrentUser`. **Zustand** is used only for sidebar persistence. Practice session state stays in **route-level hooks** with `useState` / `useRef`. Transient feedback uses **React Context** (toast).

Reference: `lib/query/client.ts`, `lib/query/auth.ts`, `hooks/use-current-user.ts`, `hooks/use-sidebar.ts`, `app/admin/users/page.tsx`.

---

## Layered Model (current codebase)

| Layer | Technology | Owns |
|-------|------------|------|
| Server data (most pages) | `useEffect` + `api.*` + local `useState` | Admin lists, analytics, knowledge CRUD |
| Server data (auth user) | React Query | `hooks/use-current-user.ts` only |
| Global UI prefs | Zustand + persist | Sidebar collapsed state |
| Transient UI | Context | Toast queue |
| Auth bridge | Custom handler | 401 → clear query + redirect |
| Practice / exam runtime | Local hook state | WS phase, recording, playback |

When adding new admin CRUD pages, **follow the existing `useEffect` + reload pattern** unless the team explicitly migrates that surface to React Query.

---

## React Query (narrow usage today)

### QueryClient factory

`lib/query/client.ts` — `createAppQueryClient()`:

- Configures default stale times and retry behavior.
- **401/403**: do not retry; delegate to auth handler.

### Current query modules

Only `lib/query/auth.ts` exists today (not a `{domain}.ts` file per feature):

```tsx
export const currentUserQueryKey = ["auth", "current-user"] as const;

export function getCurrentUserQueryOptions() {
  return {
    queryKey: currentUserQueryKey,
    queryFn: () => api.auth.getCurrentUser(),
    // ...
  };
}
```

Consume via `hooks/use-current-user.ts` (`useQuery(getCurrentUserQueryOptions())`).

`useQueryClient` appears in `AppProviders` (auth clear) and profile page (`setQueryData`).

### Server → client hydration

Dashboard layouts fetch session on server and pass initial data to shells:

- `(dashboard)/layout.tsx` — `requireServerSession()` → props to `DashboardShell`.
- `admin/layout.tsx` — same pattern with admin role gate.

Shells pass server user into `useCurrentUser(initialUser)`.

---

## Zustand

Current usage is **narrow**:

- `hooks/use-sidebar.ts` — exports **`useSidebarStore`** (with `persist`) for collapse state.
- Consumers: `components/layout/sidebar.tsx`, `dashboard-shell.tsx`, `admin-shell.tsx`, `admin-sidebar.tsx`.

**Do not** add new Zustand stores for each admin CRUD page — match existing local state + `api.*` reload.

---

## Auth State Bridge

- `lib/auth-handler.ts` registered in `AppProviders` (`AuthQueryBridge`).
- On auth failure: invalidate/clear auth query, redirect to login — no error modal.

`use-auth-protection.ts` for optional client-side guards (e.g. support runtime page). Admin routes rely primarily on server `requireServerSession()` in layouts.

---

## Practice / Exam Session State

High-churn state stays inside route-scoped hooks:

- Practice WebSocket — `hooks/use-practice-websocket.ts` (+ `hooks/websocket/*`).
- Examiner WebSocket — `hooks/use-examiner-websocket.ts`.
- Recording FSM — `app/(user)/practice/[sessionId]/use-recording-state-machine.ts` (co-located, not under `hooks/`).
- Session lifecycle — `app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`.
- Types — `hooks/websocket/types.ts` (`PracticeState`, etc.).

Avoid lifting this into global stores — sessions are route-scoped and disposable.

---

## Toast / Feedback

- `ToastProvider` in root layout.
- `useToast()` in admin pages for success/failure feedback (e.g. `app/admin/users/page.tsx`).

During **live practice**, prefer non-blocking `StatusIndicator` over toast floods.

---

## Anti-Patterns

| Avoid | Prefer |
|-------|--------|
| Zustand for every admin list | `useEffect` + `api.*` + local state (current pattern) |
| Assuming all server data uses React Query | Match surrounding page pattern |
| Raw `fetch` in page components | `api` facade from `lib/api/client.ts` |
| Global store for WS session | Route co-located hooks |
| Modal on 401 | Auth handler + redirect |

Allowed `fetch` exceptions: core `client.ts`, upload helpers, server-side `lib/server-auth.ts`.

---

## Common Mistakes

- Introducing `useQuery` on admin pages without team decision — inconsistent with most of `app/admin/`.
- Duplicating `currentUserQueryKey` — import from `lib/query/auth.ts`.
- Storing server entities in Zustand when local state + reload suffices.

---

## Examples

| Concern | Path |
|---------|------|
| Query client | `lib/query/client.ts` |
| Auth query (only domain module) | `lib/query/auth.ts` |
| Admin reload pattern | `app/admin/users/page.tsx` |
| Sidebar store | `hooks/use-sidebar.ts` |
| Toast | `components/ui/toast.tsx` |
| Practice WS state | `hooks/use-practice-websocket.ts` |

---

## Verification

```bash
cd web && npm test -- lib/query/
cd web && npm test -- hooks/use-sidebar
```

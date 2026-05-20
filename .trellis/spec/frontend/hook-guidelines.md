# Hook Guidelines

> Custom hooks and client-side orchestration patterns.

---

## Overview

Hooks live in `src/hooks/` (shared) or **co-located** next to routes for page-specific lifecycle. Complex flows (especially WebSocket + audio) split into an orchestrator hook plus `hooks/websocket/` submodules.

Reference: `hooks/use-current-user.ts`, `hooks/use-practice-websocket.ts`, `hooks/use-examiner-websocket.ts`, `app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`.

---

## Hook Structure

### Shared hook file

```
hooks/use-<domain>.ts       # implementation
hooks/use-<domain>.test.ts  # co-located test (optional)
```

Export a single primary hook: `useCamelCase`.

### WebSocket module layout

```
hooks/websocket/
├── types.ts              # shared types (PracticeState, events)
├── transport.ts          # connect, send, reconnect
├── message-handlers.ts   # dispatch by message type
├── use-audio-playback.ts # audio-specific sub-hook
└── index.ts              # re-exports types, handlers, audio (transport imported directly by orchestrator)
```

Orchestrators:

- `hooks/use-practice-websocket.ts` — sales/practice WS
- `hooks/use-examiner-websocket.ts` — curriculum examiner WS

Both wire `transport.ts` directly (not via `index.ts`).

---

## Naming Conventions

| Item | Rule | Example |
|------|------|---------|
| File | `use-<domain>.ts` (kebab-case) | `use-auth-protection.ts` |
| Export | `useCamelCase` | `useAuthProtection` |
| Params type | `UseXxxParams` | `UsePracticeSessionLifecycleParams` |
| Return type | explicit interface when non-trivial | `PracticeLifecycleError` |

---

## Patterns

### Thin React Query wrapper

```tsx
export function useCurrentUser() {
  return useQuery(getCurrentUserQueryOptions());
}
```

Reference: `hooks/use-current-user.ts`, `lib/query/auth.ts`.

### Auth guard

`use-auth-protection.ts` — combines `useRouter`, `useCurrentUser`, role checks; redirects on 401 instead of showing modal errors.

### Route lifecycle hook

Large practice pages delegate to hooks like `use-practice-session-lifecycle.ts`:

- Session phase machine (connect → ready → recording → report).
- Keeps `page.tsx` as composition root.

### Recording / audio

- `app/(user)/practice/[sessionId]/use-recording-state-machine.ts` (route co-located)
- `hooks/use-streaming-audio-player.ts`
- `hooks/websocket/use-audio-playback.ts`

---

## Rules

- Hooks that touch DOM, WebSocket, or browser APIs must live in files consumed by `"use client"` components.
- Reuse query keys from `lib/query/` — do not duplicate `["auth", "current-user"]` tuples.
- Export types needed by pages from the hook file or `websocket/types.ts`.

---

## Anti-Patterns

- Reimplementing WebSocket lifecycle inside `page.tsx`.
- Calling `fetch` directly in hooks — use `api` from `lib/api/client.ts`.
- Creating a new global hook for one-off page state — co-locate under the route.
- Hooks importing server-only modules.

---

## Common Mistakes

- Missing cleanup in `useEffect` for WS/audio — causes leaks on route change.
- Splitting websocket types across page and hook — centralize in `websocket/types.ts`.
- Circular imports between `message-handlers.ts` and orchestrator — use typed callbacks.

---

## Examples

| Hook | Path |
|------|------|
| Current user | `hooks/use-current-user.ts` |
| Auth guard | `hooks/use-auth-protection.ts` |
| Practice WS | `hooks/use-practice-websocket.ts` |
| Examiner WS | `hooks/use-examiner-websocket.ts` |
| Session lifecycle | `app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` |
| Recording FSM | `app/(user)/practice/[sessionId]/use-recording-state-machine.ts` |
| Sidebar (Zustand) | `hooks/use-sidebar.ts` (`useSidebarStore`) |

---

## Verification

```bash
cd web && npm test -- hooks/
```

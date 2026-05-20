# Directory Structure

> How frontend code is organized in this project.

---

## Overview

Next.js 16 **App Router** frontend. No Next.js API routes — all HTTP goes to the Python backend via `src/lib/api/`. Code splits by **route groups** (auth, dashboard, user practice, admin) and **domain components**.

Reference: `web/AGENTS.md`, `web/src/app/AGENTS.md`.

Note: `.kiro/steering/frontend-principles.md` describes a future `design-system/tokens/features/` layout; **current reality** is `components/ui/` + domain folders below. The tree below is **non-exhaustive** — see `web/src/app/AGENTS.md` for the full route map.

---

## Directory Layout

```
web/src/
├── app/                        # App Router
│   ├── (auth)/                 # login, forgot-password, reset-password
│   ├── (dashboard)/            # learner dashboard (training, history, profile)
│   ├── (user)/                 # practice, exam, learning-path, study
│   ├── admin/                  # admin console (large subtree)
│   ├── test-mic/               # dev/debug mic page (outside route groups)
│   ├── layout.tsx              # root layout, AppProviders, ToastProvider
│   └── globals.css
├── components/
│   ├── ui/                     # atoms: button, glass-modal, status-indicator
│   ├── layout/                 # DashboardShell, AdminShell, Sidebar
│   ├── practice/, admin/, analytics/, learner/, ...
│   └── providers/
├── hooks/
│   ├── use-*.ts                # shared hooks
│   └── websocket/              # WS transport, handlers, audio playback
├── lib/
│   ├── api/                    # client.ts, types.ts, domain builders
│   ├── query/                  # QueryClient factory, auth query keys
│   ├── auth/, observability/
│   └── utils.ts                # cn()
└── instrumentation*.ts
```

---

## Module Organization

### New page / route

1. Add under the correct route group: `(auth)`, `(dashboard)`, `(user)`, or `admin/`.
2. Use `page.tsx`, optional `layout.tsx`, `loading.tsx`, `error.tsx`.
3. Keep layouts thin: auth gate + shell only — no heavy data fetching in layout.
4. Co-locate route-specific hooks next to the page when complex.

Example: `app/(user)/practice/[sessionId]/page.tsx` + `use-practice-session-lifecycle.ts`.

### New shared component

- Reusable UI atoms → `components/ui/`.
- Domain-specific → `components/{domain}/` (e.g. `components/practice/`).
- Export via barrel `index.ts` when the folder has multiple public components.

### New API access

- Types in `lib/api/types.ts`.
- Domain methods in `lib/api/client-domains.ts` (or sibling).
- Consume via `api` facade from `lib/api/client.ts` — not raw `fetch` in pages.

### WebSocket client logic

- Orchestrator hook: e.g. `hooks/use-practice-websocket.ts`.
- Submodules: `hooks/websocket/transport.ts`, `message-handlers.ts`, `types.ts`.

---

## Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Route files | Next defaults | `page.tsx`, `layout.tsx` |
| Shared hooks (file) | `use-<domain>.ts` | `use-current-user.ts` |
| Hook exports | `useCamelCase` | `usePracticeWebSocket` |
| UI components (file) | kebab-case in `ui/` | `glass-modal.tsx` |
| Domain components (file) | PascalCase or kebab-case (follow sibling files) | `ScorePanel.tsx`, `manager-lite-panel.tsx` |
| Path alias | `@/*` → `./src/*` | `@/components/ui/button` |

---

## Examples

| Pattern | Reference |
|---------|-----------|
| Route group + shell | `(dashboard)/layout.tsx`, `components/layout/dashboard-shell.tsx` |
| Practice co-location | `app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts` |
| API facade | `lib/api/client.ts`, `lib/api/client-domains.ts` |
| WS modular hook | `hooks/use-practice-websocket.ts`, `hooks/websocket/` |

---

## Anti-Patterns

- Adding `route.ts` under `app/` (forbidden — `web/src/app/AGENTS.md`).
- Importing `client-domains.ts` directly from pages — use `api` from `client.ts`.
- Heavy data fetching in `layout.tsx`.
- Putting practice-only logic in `components/ui/`.

---

## Common Mistakes

- Creating pages outside route groups without updating auth expectations.
- Duplicating API types in page files instead of `lib/api/types.ts`.
- Mixing admin and learner shells on the same route tree.

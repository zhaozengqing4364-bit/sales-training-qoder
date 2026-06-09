# web/ — Frontend Domain Router

Concise guide for the Next.js/React frontend. Read this before touching `web/`.

## Overview

- Stack: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, Radix UI, Zustand
- Test runner: Vitest (config at `web/vitest.config.ts`)
- Tests are co-located next to source files (`.test.ts` / `.test.tsx`)
- No API routes in `app/` — this frontend is a pure consumer of the Python backend

## Structure / Where to Look

| Path | Purpose |
|------|---------|
| `src/app/` | App Router pages, layouts, route groups, and loading states |
| `src/components/` | Shared React components (UI + domain) |
| `src/hooks/` | Shared custom hooks |
| `src/lib/api/` | API client, types, and contract adapters |
| `src/lib/query/` | Query-client and cache configuration |
| `public/` | Static assets |
| `docs/` (inside `web/`) | Local frontend docs and decisions |

## Code Rules & Contracts

- Detailed UI/code rules: `.kiro/steering/frontend-principles.md`
- Backend API contracts: `docs/api-contract/README.md`
- Prefer server components by default; mark `'use client'` only when needed
- Keep `src/lib/api/*` and `src/hooks/*` as stable surfaces — changes ripple widely

## Frontend Hard Rules

- NEVER use `alert()`, `confirm()`, or `prompt()` in production UI — use `ConfirmDialog`, `StatusIndicator`, `Toast`, or inline error states (Constitution: UX never interrupted during practice).
- NEVER use raw `console.log` / `console.error` in `app/`, `components/`, `hooks/`, or `lib/` — allowed only in `lib/debug.ts` and `instrumentation*.ts` (enforced by `lib/console-boundary.test.ts`).
- NEVER use full-page `bg-white` canvas — use `bg-slate-50` for page background; white/glass for cards and inputs (see `.kiro/steering/frontend-principles.md`).
- NEVER add Next.js API routes under `src/app/**/route.ts` — frontend consumes the Python backend only.

## Workflow / Verification

- Run type checks from `web/`: `npx tsc --noEmit`
- Run tests from `web/`: `npx vitest run` (or `npm test`)
- Run lint from `web/`: `npx eslint . --quiet`
- Verify in browser after significant UI changes

## Child Routing

Enter the route-group AGENTS before page-level work:

- `web/src/app/AGENTS.md` — App Router specifics, page conventions, and route-group rules
- `.trellis/spec/frontend/admin-console-patterns.md` — admin intent-based routes, layout, and compliance (read before new admin modules)
- `web/src/components/AGENTS.md` — UI primitives & domain widgets
- `web/src/hooks/AGENTS.md` — WebSocket & media hooks
- `web/src/lib/AGENTS.md` — API façade, auth, query, support copy
- `web/src/app/admin/sales-trainer/AGENTS.md` — 新人训练路径 admin 子域 (`/admin/sales-trainer/*`)

## Cross-Domain Links

- **新人训练路径 (Newcomer Training Path)** is a **separate product** from realtime sales practice. Routes: `/sales-trainer/*` (learner) and `/admin/sales-trainer/*` (admin). API: `/api/v1/sales-trainer` + `/api/v1/admin/sales-trainer`. See [`backend/src/sales_trainer/AGENTS.md`](../backend/src/sales_trainer/AGENTS.md) + [`docs/api-contract/sales-trainer.md`](../docs/api-contract/sales-trainer.md). Do NOT treat these routes as part of the realtime `sales_bot` practice flow (`/practice/[sessionId]`).
- 实时对练 (realtime) is `sales_bot` + `training_runtime` + `practice_sessions`; 异步学习是 `sales_trainer`。两条轨道使用不同 API 前缀与 WebSocket 协议, 不要混用.

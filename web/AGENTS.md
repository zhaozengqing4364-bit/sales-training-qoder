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

## Workflow / Verification

- Run type checks from `web/`: `npx tsc --noEmit`
- Run tests from `web/`: `npx vitest run` (or `npm test`)
- Run lint from `web/`: `npx eslint . --quiet`
- Verify in browser after significant UI changes

## Child Routing

Enter the route-group AGENTS before page-level work:

- `web/src/app/AGENTS.md` — App Router specifics, page conventions, and route-group rules

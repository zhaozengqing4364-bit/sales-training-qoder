# Frontend Development Guidelines

> Coding guidance for the Next.js frontend (`web/`). Source of truth for `trellis-implement` / `trellis-check` when working on frontend tasks.

---

## Pre-Development Checklist

Before writing frontend code, read the guides relevant to your change:

| Change type | Read first |
|-------------|------------|
| Any frontend work | This index + `web/AGENTS.md` |
| Any user-visible behavior | `DESING.md` + [Product Design and UI Engineering](../guides/product-design-engineering.md) |
| App Router pages / layouts | `web/src/app/AGENTS.md` |
| Admin pages / new admin modules | [Admin Console Patterns](./admin-console-patterns.md) |
| UI patterns / Radix / Tailwind | [Component Guidelines](./component-guidelines.md) |
| New hooks / WebSocket client | [Hook Guidelines](./hook-guidelines.md) |
| State / data fetching | [State Management](./state-management.md) |
| Types / API shapes | [Type Safety](./type-safety.md) |
| Tests / lint / a11y | [Quality Guidelines](./quality-guidelines.md) |
| File placement | [Directory Structure](./directory-structure.md) |
| API / WS contract changes | `docs/api-contract/README.md`, `docs/api-contract/websocket.md` |

Also read `.kiro/steering/frontend-principles.md` for UX constitution (no error popups during practice).

### Project non-negotiables (from CLAUDE.md Constitution)

- **UX never interrupted** — no error popups during practice; use status/toast/inline UI.
- **Modular scenarios** — sales vs PPT vs curriculum evolve independently.
- **Observability** — propagate `trace_id` via `lib/observability/trace-context.ts`.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | App Router, components, hooks, lib | Ready |
| [Admin Console Patterns](./admin-console-patterns.md) | Intent-based admin routes plus the unified newcomer foundation workspace and ReleasePlan interaction contract | Slice 6 implemented |
| [Component Guidelines](./component-guidelines.md) | UI primitives, Radix, Tailwind glass | Ready |
| [Hook Guidelines](./hook-guidelines.md) | Custom hooks, WebSocket modules | Ready |
| [State Management](./state-management.md) | useEffect + api (most pages), React Query (auth), Zustand (sidebar) | Ready |
| [Quality Guidelines](./quality-guidelines.md) | Vitest, ESLint, forbidden patterns | Ready |
| [Type Safety](./type-safety.md) | TypeScript, API types, snake_case | Ready |
| [Domain Locality and Report ViewModels](./domain-locality-and-report-view-models.md) | Gate 5 domain DTO/transport authority, report/readiness ViewModels, and encoded route actions | Ready |
| [Newcomer Foundation ViewModels](./newcomer-foundation-view-models.md) | DTO → Domain → ViewModel contract; Journey, five activity runners, Dossier, readiness queue and governed human decisions implemented | Slice 5 implemented |
| [Product Design and UI Engineering](../guides/product-design-engineering.md) | Cross-layer page contract, in-flow completion, state/resilience matrix, AI gate, and rendered verification | Ready |

---

## Verification Commands

Run from `web/`:

```bash
npx tsc --noEmit          # type check
npm run lint              # eslint
npm test                  # vitest run
npm run test:coverage     # coverage thresholds
```

---

**Language**: English (matches codebase and AGENTS docs).

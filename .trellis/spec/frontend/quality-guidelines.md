# Quality Guidelines

> Linting, testing, and forbidden patterns for the frontend.

---

## Overview

Quality gates: **ESLint 9** (Next core-web-vitals), **Vitest 4** + Testing Library, **TypeScript strict**. Tests are **co-located** with source. E2E uses **Playwright** separately from Vitest.

Reference: `web/vitest.config.ts`, `web/eslint.config.mjs`, `web/AGENTS.md`.

---

## Test Structure

### Co-location

```
components/layout/dashboard-shell.tsx
components/layout/dashboard-shell.test.tsx

hooks/use-streaming-audio-player.ts
hooks/use-streaming-audio-player.test.ts

lib/api/client-domains.ts
lib/api/client-domains.test.ts
lib/api/domains/newcomer-training.ts
lib/api/newcomer-training.test.ts
```

Route tests may live next to pages: `app/(user)/practice/[sessionId]/page.test.tsx`.

### Vitest config highlights

- Environment: `jsdom`
- Alias: `@` → `./src`
- `globals: true`
- Excludes: `tests/e2e/**` (Playwright only)

### Coverage thresholds

From `vitest.config.ts` (minimum):

- lines / functions / statements: **30%**
- branches: **25%**

Run: `npm run test:coverage`

---

## Testing Patterns

| Pattern | Example |
|---------|---------|
| Mock Next.js navigation | `vi.mock("next/navigation")` in layout tests |
| Mock heavy UI deps | mock `glass-modal` in shell tests |
| API facade/domain tests | `lib/api/client-domains.test.ts`, feature-specific `lib/api/*.test.ts` |
| Property-based audio tests | `fast-check` in `hooks/use-audio-recorder.test.ts` |
| Console boundary guard | `lib/console-boundary.test.ts` scans app/components/hooks/lib |

Route tests verify **shell/render/ownership** — not full backend integration (`web/src/app/AGENTS.md`).

---

## Lint

```bash
cd web && npm run lint     # eslint
```

Config: `eslint.config.mjs` — extends `eslint-config-next/core-web-vitals` + TypeScript.

---

## Type Check

```bash
cd web && npx tsc --noEmit
```

Required before merging typed API or hook changes.

---

## E2E

```bash
cd web && npm run e2e      # playwright, tests/e2e/
```

Keep E2E out of Vitest (`vitest.config.ts` exclude).

---

## Forbidden Patterns

From `.kiro/steering/frontend-principles.md` and project Constitution (not all repeated in `web/AGENTS.md`):

| Never | Always |
|-------|--------|
| `alert()` / `confirm()` / `prompt()` in practice flows | `ConfirmDialog`, toast, status UI |
| `console.log` in app/components/hooks/lib | `lib/debug.ts` or instrumentation files only |
| Next.js `route.ts` API handlers in `app/` | Python backend + `lib/api/` |
| Raw API errors shown to learners during practice | Friendly mapped messages |
| Full-stack integration in unit/route tests | mocks + contract tests |

`lib/console-boundary.test.ts` enforces the console rule.

---

## Accessibility and UX Quality

- Practice routes must degrade gracefully — loading and error UI without blocking dialogs.
- Prefer visible status components over toast-only critical failures during voice sessions.
- After significant UI changes, verify in browser (per `web/AGENTS.md`).

---

## Code Review Checklist

- [ ] `tsc --noEmit` clean.
- [ ] Co-located or domain tests updated for behavior changes.
- [ ] API changes mirrored in `lib/api/types.ts` and facade/domain tests (`lib/api/client-domains.test.ts`, feature-specific `lib/api/*.test.ts`; backend: `tests/contract/` + `docs/api-contract/` when backend behavior changes).
- [ ] UI layers still import API through `lib/api/client.ts`; `client-domains.test.ts` must keep rejecting imports from `client-domains.ts` or `lib/api/domains/*`.
- [ ] No native dialogs in user/practice paths.
- [ ] `"use client"` boundary minimal.

---

## Common Mistakes

- Running Vitest from repo root without `cd web`.
- Adding E2E specs under `src/` — use `tests/e2e/`.
- Mocking entire API client when testing one normalizer — test normalizers directly in `lib/api/*.test.ts`.

---

## Verification Commands

```bash
cd web && npm run lint
cd web && npm test
cd web && npx tsc --noEmit
```

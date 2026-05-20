# Type Safety

> TypeScript conventions and API typing in this project.

---

## Overview

**Strict TypeScript** (`strict: true` in `web/tsconfig.json`). API types mirror the **Python backend's snake_case** JSON. Normalization and error parsing live in `lib/api/client.ts` — pages should not re-parse raw responses.

Reference: `lib/api/types.ts`, `lib/api/client.ts`, `lib/api/client-domains.ts`.

---

## Compiler and Paths

- Path alias: `@/*` → `./src/*`.
- JSX: `react-jsx`.
- Stack: Next.js 16, React 19.

Run type check:

```bash
cd web && npx tsc --noEmit
```

---

## API Types

Central definitions in `lib/api/types.ts`:

```tsx
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  trace_id?: string;
}
```

- Field names match backend: `weekly_activity`, `session_id`, etc.
- Central types file is large (~4000+ lines) — add new DTOs in the appropriate feature section; do not duplicate in pages.

Domain API builders live in `lib/api/client-domains.ts` (and domain sections inside `lib/api/client.ts`). Tests: `lib/api/client-domains.test.ts`, `lib/api/client-learning-content.test.ts`.

---

## Client Facade

Pages and hooks import **`api`** from `lib/api/client.ts`, not low-level fetch helpers.

Utilities in `client.ts`:

- `isAuthenticationError()`
- `getApiErrorMessage()` — user-safe strings, no raw stack traces
- Normalizers e.g. `normalizeQuestionCategory()`

---

## Component and Hook Types

- Props: `interface XxxProps`.
- Discriminated unions for UI states when helpful (loading / error / ready).
- Hook params: `UseXxxParams`; hook errors: dedicated types like `PracticeLifecycleError`.
- Re-export public hook types from orchestrator files when submodules define them.

---

## Query Keys

Use `as const` tuples for stable keys:

```tsx
export const currentUserQueryKey = ["auth", "current-user"] as const;
```

Define next to query options in `lib/query/`.

---

## Runtime Validation

Project does **not** use Zod/Yup at the boundary today. Validation is:

- TypeScript compile-time checks.
- Client-side normalize functions in `lib/api/client.ts`.
- Contract tests: `lib/api/client-domains.test.ts`.

When adding new API surfaces, add types + normalizer + test together.

---

## Anti-Patterns

| Avoid | Prefer |
|-------|--------|
| `any` on API responses | Typed `ApiResponse<T>` + normalizer |
| camelCase API fields in TS types | snake_case matching backend |
| Duplicated DTO interfaces in pages | `lib/api/types.ts` |
| Inline `fetch` without typed wrapper | `api` domain methods |

---

## Common Mistakes

- Typing mock data in camelCase while production API is snake_case.
- Missing `| undefined` on optional query data before render.
- Exporting huge types from page files — move to `lib/api/types.ts` or hook types file.

---

## Examples

| Artifact | Path |
|----------|------|
| Core API types | `lib/api/types.ts` |
| Client + guards | `lib/api/client.ts` |
| Domain methods | `lib/api/client-domains.ts` |
| Contract tests | `lib/api/client-domains.test.ts` |
| Trace typing | `lib/observability/trace-context.ts` |

---

## Cross-Layer Note

Backend error codes use bracketed strings (`"[SESSION_NOT_FOUND]"`). Frontend maps these via `getApiErrorMessage()` — do not hardcode English prose in multiple components.

See also: [guides/cross-layer-thinking-guide.md](../guides/cross-layer-thinking-guide.md).

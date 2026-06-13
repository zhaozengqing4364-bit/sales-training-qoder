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

### SSE API Streams

Server-sent event APIs must still flow through the central `api` facade. Pages must not create page-local `fetch`, `EventSource`, CSRF, trace, authentication, retry, or stream-parsing logic.

Required pattern:

- Define the stream event discriminated union in `lib/api/types.ts`.
- Add a domain method in `lib/api/client-domains.ts` that receives the shared `ApiStream` dependency.
- Implement parsing, auth headers, loopback retry, session-expired handling, and `ApiRequestError` mapping in `lib/api/client.ts`.
- Keep `event:` names aligned with `data.type`; treat malformed frames as typed API errors instead of silently dropping them.
- Add a client-domain test proving the stream method calls the expected endpoint and yields typed events.

UI pages may render intermediate stream phases, but business defaults such as timeouts, recovery prompts, or resume strategy must come from backend configuration/API payloads, not page-local constants.

### Scenario: AI Coach Learner Score Projection

#### 1. Scope / Trigger

- Trigger: AI Coach `quiz_card.score_result` crosses backend scoring, SSE/JSON session snapshots, TypeScript API types, and learner card rendering.
- The backend may keep numeric `score/max_score` for state-machine decisions, but learner UI must not expose choice-card results as raw exam scores.

#### 2. Signatures

Backend response type:

```python
class AiCoachScoreResultV1(BaseModel):
    score: float
    max_score: float
    mastery_threshold: float | None
    mastered: bool | None
    feedback: str
    missed_points: list[str]
    next_turn_available: bool
    finished: bool
```

Frontend type:

```ts
export interface AiCoachScoreResultV1 {
  readonly score: number;
  readonly max_score: number;
  readonly mastery_threshold?: number | null;
  readonly mastered?: boolean | null;
  readonly feedback: string;
  readonly missed_points: readonly string[];
  readonly next_turn_available: boolean;
  readonly finished: boolean;
}
```

#### 3. Contracts

- `score/max_score` are internal mastery numeric values used by backend progression.
- `mastery_threshold` comes from backend AI Coach config snapshot; pages must not hardcode it.
- `mastered` is the learner-facing pass/mastery projection for that card.
- Historical events may lack `mastery_threshold/mastered`; UI must degrade gracefully.

#### 4. Validation & Error Matrix

| Condition | Expected UI behavior |
|---|---|
| choice card + `mastered=true` | Show “答对” / “已达到本轮掌握标准” |
| choice card + `mastered=false` | Show “未掌握” / “未达到本轮掌握标准” |
| `mastery_threshold` present | Include the percent from API, e.g. `80%` |
| `mastery_threshold` missing | Do not invent a default threshold |
| legacy `mastered` missing | Fall back to existing score comparison only for visual state |

#### 5. Good/Base/Bad Cases

- Good: learner sees `答对` and `已达到本轮掌握标准：80%`.
- Base: legacy record shows `答对` without a threshold number.
- Bad: learner sees `100 / 100` for a single-choice drill and treats it as an exam score.

#### 6. Tests Required

- Backend unit: scored event stores `mastery_threshold` and `mastered`.
- Frontend route/component: choice result does not render `100 / 100`.
- Browser verification: after submitting a card, layout remains viewport-bound and result uses mastery wording.

#### 7. Wrong vs Correct

##### Wrong

```tsx
<p>{result.score} / {result.max_score}</p>
```

##### Correct

```tsx
<span>{result.mastered ? "答对" : "未掌握"}</span>
{typeof result.mastery_threshold === "number" ? (
  <span>掌握标准：{Math.round(result.mastery_threshold)}%</span>
) : null}
```

### Governed Policy Payloads

Backend-managed policies must be typed once in `lib/api/types.ts` and consumed through the `api` facade. Page components must not define their own DTOs or local threshold constants.

Example:

```tsx
export interface SalesTrainerPhase2Policy {
  key: string;
  version: string;
  enabled: boolean;
  low_score_threshold: number;
  repeat_practice_threshold: number;
  dashboard_record_limit: number;
  source: string;
  config_id: string | null;
  config_version: number | null;
  status: string | null;
  fallback_applied: boolean;
  fallback_reason: string | null;
  management_entry: string;
  permission: string;
  effective_timing: string;
}
```

Display pages may format missing values as `"--"`, but they must not substitute business defaults locally. Defaults belong to backend business-rule validators/resolvers and are surfaced through the API.

---

## Anti-Patterns

| Avoid | Prefer |
|-------|--------|
| `any` on API responses | Typed `ApiResponse<T>` + normalizer |
| camelCase API fields in TS types | snake_case matching backend |
| Duplicated DTO interfaces in pages | `lib/api/types.ts` |
| Inline `fetch` without typed wrapper | `api` domain methods |
| Page-local policy thresholds/labels | Backend policy payload + centralized API types |

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

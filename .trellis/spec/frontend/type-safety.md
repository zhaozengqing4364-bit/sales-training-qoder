# Type Safety

> TypeScript conventions and API typing in this project.

---

## Overview

**Strict TypeScript** (`strict: true` in `web/tsconfig.json`). API types mirror the **Python backend's snake_case** JSON. Normalization and error parsing live in `lib/api/client.ts` — pages should not re-parse raw responses.

Reference: `lib/api/types.ts`, `lib/api/client.ts`, `lib/api/client-domains.ts`, `lib/api/domains/shared.ts`, `lib/api/domains/*`.

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
- Central types file is large (~8000+ lines) — add new DTOs in the appropriate feature section; do not duplicate in pages.
- Extracted domains use a two-tier convention: DTOs are still **authored** in `types.ts`, then **re-exported** through a per-domain barrel in `lib/api/types/<domain>.ts` (e.g. `types/newcomer-training.ts`, `types/sales-trainer.ts`). The domain factory in `lib/api/domains/<domain>.ts` imports its types from `../types/<domain>`, not directly from `types.ts`. Add a new `types/<domain>.ts` barrel when you extract a domain, and re-export only the DTOs that domain owns.

Domain API builders are split between the legacy aggregation seam `lib/api/client-domains.ts` and extracted modules under `lib/api/domains/*`. Tests: `lib/api/client-domains.test.ts`, feature-specific `lib/api/*.test.ts`, and page tests where the API result drives UI behavior.

---

## Client Facade

Pages and hooks import **`api`** from `lib/api/client.ts`, not low-level fetch helpers.

Utilities in `client.ts`:

- `isAuthenticationError()`
- `getApiErrorMessage()` — user-safe strings, no raw stack traces
- Normalizers e.g. `normalizeQuestionCategory()`

### Scenario: API Facade And Extracted Domain Builders

#### 1. Scope / Trigger

- Trigger: adding or moving frontend API methods, API streams, upload helpers, domain DTOs, or client normalizers.
- Scope: `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/lib/api/client-domains.ts`, `web/src/lib/api/domains/*`, and tests under `web/src/lib/api/*.test.ts`.
- UI layers in scope: `web/src/app`, `web/src/components`, and `web/src/hooks`, because they must consume only the public `api` facade.

#### 2. Signatures

Shared domain dependencies:

```ts
export type ApiRequest = <T>(endpoint: string, options?: ApiRequestOptions) => Promise<T>;
export type ApiStream = <T>(endpoint: string, options?: ApiRequestOptions) => AsyncIterable<T>;
export type ApiUpload = <T>(
  endpoint: string,
  formData: FormData,
  signal?: AbortSignal,
  options?: { skipSessionExpiredHandling?: boolean },
) => Promise<T>;
```

Extracted domain factory shape:

```ts
type NewcomerTrainingDomainDependencies = {
  request: ApiRequest;
  stream: ApiStream;
};

export function createNewcomerTrainingDomain({
  request,
  stream,
}: NewcomerTrainingDomainDependencies) {
  return {
    startChatStream: (payload: AiCoachChatSessionCreateRequest) =>
      stream<AiCoachChatStreamEvent>("/newcomer-training/ai-coach/chat/sessions/stream", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  };
}
```

Facade wiring:

```ts
const newcomerTrainingDomain = createNewcomerTrainingDomain({
  request: apiFetch,
  stream: apiStream,
});

export const api = {
  newcomerTraining: newcomerTrainingDomain,
};
```

#### 3. Contracts

- `client.ts` owns cross-cutting behavior: auth/session expiry, trace headers, CSRF/auth headers, loopback retry, SSE parsing, upload transport, `ApiRequestError`, and `getApiErrorMessage()`.
- `client-domains.ts` is the aggregation seam. It exports extracted domain factories and may still host legacy/low-growth domain builders.
- New high-growth domains should live in `lib/api/domains/<domain>.ts` and receive only typed dependencies (`ApiRequest`, `ApiStream`, `ApiUpload`, plus explicit normalizers or URL helpers when needed).
- Pages, hooks, and components import from `@/lib/api/client` only. They must not import `client-domains.ts` or `lib/api/domains/*` directly.
- DTOs remain snake_case in `types.ts`; domain factories may normalize defensive `unknown` values, but they must not invent business defaults that belong to backend configs.
- SSE stream methods must use the shared `ApiStream` dependency, not `EventSource`, page-local `fetch`, or ad hoc stream parsers.

#### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| UI imports `client-domains.ts` or `lib/api/domains/*` | `client-domains.test.ts` boundary test fails |
| New extracted domain bypasses `client.ts` transport | Review failure; auth, trace, retry, and error mapping are no longer guaranteed |
| Stream method uses page-local `fetch`/`EventSource` | Reject; move stream parsing to `apiStream` and expose a typed `AsyncIterable<T>` |
| New API response type is declared in a page | Reject; define DTO in `lib/api/types.ts` |
| Domain factory needs uploads or base URL | Inject `ApiUpload` / `resolveApiBaseUrl` explicitly instead of importing transport internals |
| Backend returns bracketed error code | Surface through `ApiRequestError` and `getApiErrorMessage()`, not page-local string parsing |

#### 5. Good/Base/Bad Cases

- Good: `newcomer-training.ts` receives `request` and `stream`, exposes typed methods, and is wired into the public `api.newcomerTraining` facade.
- Base: a small legacy admin method remains in `client-domains.ts` until the domain grows enough to justify extraction.
- Bad: a page imports `createNewcomerTrainingDomain` directly and passes a custom `fetch`, bypassing shared auth and trace handling.

#### 6. Tests Required

- Boundary: keep `client-domains.test.ts` asserting UI layers do not import `client-domains` or `domains/*`.
- Domain: add or update a `lib/api/*.test.ts` case proving the factory calls the expected endpoint, HTTP method, body, upload dependency, or stream dependency.
- Type: add DTOs to `types.ts` and ensure `npx tsc --noEmit` covers the facade shape.
- UI: when a new API payload drives visible behavior, add a page/component test that mocks `api` from `client.ts`, not internal domain factories.

#### 7. Wrong vs Correct

##### Wrong

```tsx
import { createNewcomerTrainingDomain } from "@/lib/api/domains/newcomer-training";

const api = createNewcomerTrainingDomain({ request: localFetch, stream: localStream });
```

This bypasses shared auth, trace, retry, stream parsing, and error semantics.

##### Correct

```tsx
import { api } from "@/lib/api/client";

const events = api.newcomerTraining.startChatStream(payload);
```

The page consumes the public facade, while transport and domain wiring remain centralized.

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
- Add a domain method in `lib/api/domains/<domain>.ts` for extracted domains, or `lib/api/client-domains.ts` for legacy domains, that receives the shared `ApiStream` dependency.
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

### Scenario: Prompt Governance Admin Payloads

#### 1. Scope / Trigger

- Trigger: adding prompt-template governance fields, impact previews, clone flows, default repair, or scenario binding UI.
- Scope: `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `/admin/prompts*`, and prompt binding components.

#### 2. Signatures

Frontend API facade methods:

```ts
api.getPromptTemplateImpact(templateId: string): Promise<PromptTemplateImpactResponse>;
api.repairPromptTemplateDefaults(params?: { dry_run?: boolean }): Promise<PromptTemplateRepairDefaultsResponse>;
api.clonePromptTemplate(templateId: string, payload: PromptTemplateCloneRequest): Promise<PromptTemplate>;
```

#### 3. Contracts

- API DTOs stay snake_case and live in `lib/api/types.ts`; pages must not declare local prompt DTOs.
- List and detail pages display `display_name`, `display_type`, and `display_category`; raw enum keys are advanced/debug context only.
- System templates are rendered read-only. The primary action is `复制为自定义模板`, not inline edit.
- Governance repair must be a two-step action: dry-run preview first, formal repair second.
- Scenario binding UI filters candidate templates by `prompt_type`, previews current effective template and after-save template, and explains fallback to default after deleting a binding.

#### 4. Validation & Error Matrix

| Condition | Expected UI behavior |
|---|---|
| `can_edit_directly=false` | Hide save form and show copy action with `edit_block_reason` |
| `can_deactivate=false` from impact | Disable stop action and show block reason |
| Default conflict count > 0 | Show governance repair entry, not a silent warning only |
| `repairDefaults(dry_run=true)` returns items | Show preview count and require explicit execute click |
| Scenario binding type mismatch error | Show backend message; keep user in wizard with selected business domain/type |

#### 5. Good/Base/Bad Cases

- Good: operator sees Chinese template names, opens impact, understands whether a template is default/bound/runtime-effective, then clones before editing a system template.
- Base: no scenario bindings exist; page shows “未配置场景绑定”，not an empty technical table.
- Bad: page asks an operator to paste a `PromptTemplate` UUID or shows raw `fuzzy_detection` as the primary label.

#### 6. Tests Required

- Page test: prompt list renders Chinese display fields and governance stats.
- Page test: repair flow calls dry-run before formal execution.
- Detail test: system template route is read-only and clone action calls `clonePromptTemplate`.
- Binding component test: selected prompt type filters templates and delete copy mentions fallback default.

#### 7. Wrong vs Correct

##### Wrong

```tsx
<td>{template.prompt_type}</td>
<button onClick={() => api.updatePromptTemplate(template.id, { template })}>保存</button>
```

##### Correct

```tsx
<td>{template.display_type}</td>
{template.can_edit_directly ? (
  <Link href={`/admin/prompts/${template.id}/edit`}>编辑</Link>
) : (
  <button onClick={() => cloneTemplate(template.id)}>复制为自定义模板</button>
)}
```

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
| Per-domain type re-export barrels | `lib/api/types/<domain>.ts` |
| Client + guards | `lib/api/client.ts` |
| Domain aggregation seam | `lib/api/client-domains.ts` |
| Extracted domain factories | `lib/api/domains/*` |
| Shared domain dependencies | `lib/api/domains/shared.ts` |
| Contract tests | `lib/api/client-domains.test.ts` |
| Trace typing | `lib/observability/trace-context.ts` |

---

## Cross-Layer Note

Backend error codes use bracketed strings (`"[SESSION_NOT_FOUND]"`). Frontend maps these via `getApiErrorMessage()` — do not hardcode English prose in multiple components.

See also: [guides/cross-layer-thinking-guide.md](../guides/cross-layer-thinking-guide.md).

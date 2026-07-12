# Domain Locality and Report ViewModels

> Executable contract for Gate 5 frontend DTO, transport, ViewModel, and route-action ownership.

## 1. Scope / Trigger

Read this spec before changing:

- Journey, Readiness, session report, replay, highlight, supervisor, or diagnostics DTOs;
- session report/replay/history/highlight/media endpoints;
- report or Readiness detail labels, tones, evidence summaries, or retry routes;
- `types.ts`, `client-domains.ts`, or outward `api` composition.

The route root renders state. Domain type modules own transport shape, domain builders own request mechanics,
ViewModels own interpretation, and action modules own URL/storage mechanics.

## 2. Signatures

```typescript
// Transport authority
export function createSessionsDomain(deps: SessionsDomainDependencies): {
    getReport(sessionId: string): Promise<PracticeSessionReport>;
    getReportTrends(sessionId: string, limit?: number): Promise<ReportTrendsResponse>;
    getReplay(sessionId: string): Promise<ReplayData>;
    // history, highlights, shares and media helpers remain in the same domain
};

// Route actions
export function buildReplayDeepLink(
    sessionId: string,
    options: { focus: ReplayDeepLinkFocus; anchor?: ReplayAnchor | null; turnNumber?: number | null },
): string;

export function buildRetrySessionPath(
    sessionId: string,
    retry: NonNullable<PracticeSessionReport["retry_entry"]>,
    extra?: Record<string, string>,
): string;

export function buildSessionReportPath(sessionId: string): string;

// Pure mapping
export function readinessDisplayMessage(message: string | null | undefined): string;
export function formatReplayAnchorHint(anchor?: ReplayAnchor | null): string;
```

## 3. Contracts

### Type authority

- `types/training-journey.ts` owns Journey, Readiness, realtime-entry, and analytics DTOs.
- `types/session-report.ts` owns session evidence, report, replay, highlight, diagnostics, supervisor, calibration,
  and retraining DTOs.
- Neither domain type file imports the global `types.ts` barrel.
- `types.ts` is a type-only compatibility re-export and may import a small set of moved names used by its legacy
  declarations. It must not redeclare moved interfaces.
- Gate 5 consumers import domain types directly; old external consumers may use the compatibility barrel.

### Transport and façade

- `domains/sessions.ts` owns report/replay/history/highlight/share/media request paths and loopback/error behavior.
- `client-domains.ts` composes/re-exports builders; it contains no session endpoint literals.
- UI pages call `api` from `@/lib/api/client`; they never import a domain builder.
- Request paths, credentials, headers, timeout, error normalization, and returned snake_case payloads stay stable.

### ViewModels and actions

- ViewModels are deterministic and may import DTOs plus pure formatting helpers only.
- ViewModels do not call `api`, router, storage, React hooks, time/network, or mutate DTOs.
- Unknown/internal enum and diagnostic fallbacks use user language (`待确认`, `未记录`, `训练证据`), never raw
  error codes, `trace_id`, provider/runtime vocabulary, or database identifiers.
- `report-actions.ts` owns `URLSearchParams`, path construction, route-ID encoding, and highlight-review storage.
- All path-segment identifiers use `encodeURIComponent`; query values use `URLSearchParams`.
- Route roots keep loading, empty, error, partial, permission, submitting, and retry states visible.

## 4. Validation & Error Matrix

| Input / condition | Required result |
|---|---|
| Unknown Readiness status | `待确认` |
| Unknown evidence record type | `训练证据` |
| Unknown roleplay status | `未记录` |
| Diagnostic contains internal code/trace/runtime terms | redact/translate to user language |
| Invalid date | `--` |
| Non-finite score | `--` |
| Missing replay anchor | disabled/missing hint; no fabricated target |
| Degraded anchor with turn | explain degraded fallback and preserve turn |
| Reserved route ID (`/`, `?`, `&`) | encoded path/query value |
| Corrupt highlight storage payload | remove entry and return empty list |
| Storage unavailable | non-blocking empty/no-op with diagnostic logging |
| API request failure | existing inline/retry page state; never silently empty |

## 5. Good / Base / Bad Cases

- **Good:** add a Readiness DTO field in `training-journey.ts`, map it in `readiness-view-model.ts`, and render the
  ViewModel without adding DTO interpretation to JSX.
- **Base:** add a session read endpoint to `domains/sessions.ts`, expose it through the existing outward `api`
  composition, and add an exact request-contract test.
- **Bad:** add `getReport` back to `client-domains.ts` or import `createSessionsDomain` from a page.
- **Bad:** define `TrainingJourneyResponse` again in `types.ts`.
- **Bad:** concatenate `/practice/${sessionId}` or query strings in JSX/event handlers.
- **Bad:** render unknown raw enum values or backend diagnostic codes as labels.

## 6. Tests Required

Run from `web/`:

```bash
npm exec tsc -- --noEmit
npx eslint --quiet <changed-files>
npx vitest run \
  src/lib/api/gate5-locality.test.ts \
  src/lib/api/client-domains.test.ts \
  src/lib/api/sales-trainer.test.ts \
  'src/app/(user)/practice/[sessionId]/report/report-actions.test.ts' \
  'src/app/(user)/practice/[sessionId]/report/report-view-model.test.ts' \
  'src/app/admin/sales-trainer/readiness/[learnerId]/readiness-view-model.test.ts'
npx vitest run --reporter=dot
```

Assertion points:

- old and new type import paths compile to the same structural contracts;
- global barrels contain re-exports but no moved definitions or endpoint literals;
- exact endpoint path/options are unchanged;
- ViewModels cover score/status/evidence/degradation/unknown-value language;
- action tests cover reserved identifiers, anchor fallbacks, retry query order, corrupt storage, and limits;
- source-report navigation uses `buildSessionReportPath`; route roots do not interpolate session identifiers;
- route tests retain loading/error/permission/submitting/retry behavior.

## 7. Wrong vs Correct

### Wrong

```tsx
router.push(`/practice/${created.session_id}?scenario_type=${retry.scenario_type}`);
return <span>{evidence.status}</span>;
```

This duplicates route mechanics, fails reserved identifiers, and leaks transport vocabulary.

### Correct

```tsx
router.push(buildRetrySessionPath(created.session_id, retry));
return <span>{statusLabel(evidence.status)}</span>;
```

Actions own URL semantics; ViewModels own user language; JSX stays focused on rendering.

## Gate 6 Retirement Conditions

Remove global type/client compatibility exports only after repository import inventory reaches the approved
adoption floor, all pages/hooks/tests use direct domain types and the outward `api`, deprecation tests are Green,
and no generated client or external package depends on the old symbol. Gate 6 may shrink barrels; it must not
replace them with another global runtime barrel.

# 2026-04-24 Frontend/Admin Sales Rule Governance and Report/Practice Decomposition Plan

## 0. Scope and source artifacts

- Source PRD: `/Users/zhaozengqing/github/销售训练qoder/.omx/plans/prd-sales-training-roadmap-20260424.md`.
- Source test spec: `/Users/zhaozengqing/github/销售训练qoder/.omx/plans/test-spec-sales-training-roadmap-20260424.md`.
- Lane owner: frontend/admin planning lane.
- This document is an implementation plan only. It does not enable adaptive difficulty, external sharing, visual redesign, PWA, dark mode, or a StepFun rewrite.

This lane covers the Phase 3 frontend/admin requirements from the roadmap:

1. Move sales-training combinations from page-local hard-coded defaults toward governed server configuration with a safe client fallback.
2. Add the admin surfaces required to draft, validate, preview, publish, roll back, and audit governed business rules.
3. Decompose the dense report and practice pages contract-first by extracting data hooks before presentation components.
4. Define low-risk tests that lock current behavior before any structural changes.

## 1. Current evidence from the repo

### 1.1 Sales combinations

- Current UI entry: `web/src/app/(dashboard)/training/sales/page.tsx`.
- Current tests: `web/src/app/(dashboard)/training/sales/page.test.tsx`.
- Current behavior:
  - `CORE_COMBINATIONS` is a page-local static array of ten `capability × role` pairs.
  - The page fetches sales agents, scenarios, personas, the latest recommendation, and recent sales history through `api.training`, `api.scenarios`, `api.dashboard`, and `api.user`.
  - A recommendation or recent history can reorder one matching combination to the top.
  - Missing agent/persona data makes a combination visibly unavailable rather than silently inert.
- Governance gap:
  - Combination defaults, version, validation, publish state, and fallback reason are not represented as a typed API contract.
  - Admins cannot preview the effect of a draft combination set against current agents/personas before publishing.

### 1.2 Admin settings

- Current admin settings UI: `web/src/app/admin/settings/page.tsx`.
- Existing tests: `web/src/app/admin/settings/page.test.tsx`.
- Current behavior:
  - Non-model settings are intentionally read-only, so this lane must not add fake persistence to the existing generic settings controls.
  - Admin governance patterns already exist for knowledge and voice-runtime read models in `web/src/lib/api/client-governance.test.ts` and related admin pages.
- Governance gap:
  - There is no dedicated business-rule admin section for sales combinations, AI coach rules, achievement rules, next-practice recommendations, or scoring rulesets.

### 1.3 Report and practice pages

- Report UI: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`.
- Practice UI: `web/src/app/(user)/practice/[sessionId]/page.tsx` plus route-local hooks.
- Existing route-local hook pattern:
  - `use-practice-recording-hotkeys.ts`
  - `use-practice-session-lifecycle.ts`
  - `use-recording-state-machine.ts`
  - colocated tests for those hooks.
- Current report behavior:
  - The report page owns many independent data requests and states: unified report, enhanced report, replay anchors, highlights, trends, next recommendation, local highlight review state, and retry routing.
  - Highlight review localStorage already uses a schema version (`highlight_review_v1`) and should keep safe fallback semantics.
- Decomposition gap:
  - Report data loading and view rendering are still tightly coupled.
  - Practice page decomposition should continue the existing route-local hook style and avoid a broad visual rewrite.

## 2. Contract-first target state

### 2.1 Sales combination rule contract

Introduce a backend-owned read contract before changing rendering behavior. The initial frontend type should be shaped to tolerate server absence and preserve the current array as a fallback.

```ts
type SalesCombinationRuleSet = {
  rule_set_id: string;
  version: string;
  status: "draft" | "published" | "archived";
  effective_at: string | null;
  combinations: SalesCombinationRule[];
  fallback_policy: "client_default_v1" | "hide_all";
  audit_summary?: {
    published_by: string | null;
    published_at: string | null;
    reason: string | null;
  };
};

type SalesCombinationRule = {
  id: string;
  capability: string;
  role: string;
  priority: number;
  enabled: boolean;
  required_agent_match?: string[];
  required_persona_match?: string[];
};
```

Initial frontend endpoint assumptions, pending backend lane confirmation:

- Learner read: `GET /api/v1/business-rules/sales-combinations/active`.
- Admin list/detail: `GET /api/v1/admin/business-rules/sales-combinations` and `GET /api/v1/admin/business-rules/sales-combinations/{id}`.
- Admin mutation: draft/create/update/validate/preview/publish/rollback under `/api/v1/admin/business-rules/...`.

If backend names differ, the frontend should adapt in `web/src/lib/api/` only; pages should consume typed domain methods rather than raw paths.

### 2.2 Frontend fallback contract

The learner sales page must distinguish these cases:

| Case | UI behavior | Observability |
| --- | --- | --- |
| Active server ruleset loads | Render enabled combinations sorted by server priority, then personalized reorder within that list | Include ruleset version in debug context when routing |
| Active server ruleset missing | Render current ten-combination fallback | Show a small non-blocking admin/config fallback note only if existing page copy pattern supports it |
| Server ruleset invalid | Reject at adapter layer, use current fallback | `debug.warn` with invalid reason and ruleset version |
| Agent/persona missing | Keep current unavailable-card behavior | Show explicit unavailable reason |
| Empty published ruleset | Treat as invalid unless backend explicitly returns `fallback_policy: "hide_all"` | Record fallback reason |

The first code slice should keep the current `CORE_COMBINATIONS` as `CLIENT_DEFAULT_SALES_COMBINATIONS_V1`; do not delete it until the server contract and rollback path are proven.

### 2.3 Admin rule governance surface

Add a dedicated admin route instead of extending read-only generic settings:

- Route: `web/src/app/admin/business-rules/sales-combinations/page.tsx`.
- Navigation label: “业务规则 / 销售训练组合” only after backend route and permissions exist.
- Page responsibilities:
  1. Show active version, draft versions, archived/published history.
  2. Validate each row: capability, role, priority, enabled state, duplicate id, duplicate `capability × role` pair.
  3. Preview matching coverage against active sales agents and personas: matched, missing agent, missing persona, disabled.
  4. Publish requires a reason and displays before/after summary.
  5. Rollback requires selecting a previous published version and records reason.
  6. Display audit fields: actor, action, before version, after version, reason, trace id, timestamp.
- Permission behavior:
  - Non-admin users must not see mutation controls.
  - If a user can view but not mutate, controls are disabled with explicit copy; no fake save buttons.

## 3. Implementation sequence

### Slice A — Characterization and API adapter only

Files likely touched:

- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts` or a new/appropriate domain module under `web/src/lib/api/`
- `web/src/lib/api/*business-rules*.test.ts`
- `web/src/app/(dashboard)/training/sales/page.tsx`
- `web/src/app/(dashboard)/training/sales/page.test.tsx`

Steps:

1. Move the page-local combination shape into a route-local helper or shared frontend rule module without changing rendered output.
2. Add adapter tests for active-rule normalization, invalid-rule rejection, and fallback reason mapping.
3. Add a sales-page test where the API fails and the existing ten-combination fallback still renders.
4. Add a sales-page test where a valid server ruleset changes ordering without breaking personalized recommendation priority.
5. Keep route URL shape and `focus_intent` version stable unless a backend contract explicitly requires a version bump.

Exit criteria:

- Existing sales-page tests still pass.
- New adapter tests cover hit, missing, invalid, and disabled cases.
- No admin UI is introduced in this slice.

### Slice B — Learner page reads governed rules

Files likely touched:

- `web/src/app/(dashboard)/training/sales/page.tsx`
- `web/src/app/(dashboard)/training/sales/page.test.tsx`
- `web/src/lib/debug.ts` only if existing logging helper requires typed event support; otherwise do not touch.

Steps:

1. Fetch active sales-combination rules in the existing `Promise.allSettled` data load.
2. Normalize results through the adapter from Slice A.
3. Use server rules when valid; otherwise use `CLIENT_DEFAULT_SALES_COMBINATIONS_V1`.
4. Preserve partial failure semantics: rule config failure must not make agent/persona counts look like real zeroes.
5. Preserve visible unavailable reasons for missing agents/personas.

Exit criteria:

- `SalesTrainingPage` still supports current no-backend behavior.
- The page can explain whether combinations are server-governed or fallback-driven.
- No visual redesign; only small status copy is allowed if necessary.

### Slice C — Admin sales-combination governance page

Files likely touched:

- `web/src/app/admin/business-rules/sales-combinations/page.tsx`
- `web/src/app/admin/business-rules/sales-combinations/page.test.tsx`
- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts` or the chosen admin business-rule domain
- Admin navigation/shell file only after backend permissions are ready.

Steps:

1. Build a read-first page showing active version, drafts, history, and audit summary.
2. Add a preview panel that calls backend validation/preview; if backend is unavailable, show an explicit unavailable state rather than saving locally.
3. Add mutation controls only when backend mutation endpoints and admin permission checks exist.
4. Publish/rollback flows must require reason text and must not optimistically mark a version active until the API confirms.
5. Route all errors through existing admin-page error/empty-state patterns.

Exit criteria:

- Non-admin mutation denial is represented in tests by API `403` or permission flag.
- Invalid schema publish is blocked before confirmation UI.
- Preview does not modify active version.
- Publish and rollback tests assert actor/reason/version fields are surfaced from the response.

### Slice D — Report data hook extraction

Files likely touched:

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- New route-local hook files such as:
  - `use-report-unified-evidence.ts`
  - `use-report-enhanced-evidence.ts`
  - `use-report-highlights.ts`
  - `use-report-next-action.ts`
- Matching `*.test.ts` / `*.test.tsx` files.

Steps:

1. Extract one data concern at a time, starting with the least coupled concern: next recommendation or trends.
2. Keep hook return values explicit: `{ data, loading, errorHint, reload }`.
3. Do not move JSX sections in the same commit as the first data-hook extraction.
4. Preserve `highlight_review_v1` localStorage schema and mismatch fallback.
5. After hooks are stable, split presentation sections only along existing UI boundaries: score summary, evidence completeness, trends, highlights, retry/next action.

Exit criteria:

- Before/after report render tests assert the same key headings and retry CTA behavior.
- Highlight review schema-mismatch behavior remains safe.
- Retry fallback continues to route presentation reports to `/training/presentation` and sales reports to `/training/sales`.

### Slice E — Practice page hook/component continuation

Files likely touched:

- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- Existing route-local hooks in `web/src/app/(user)/practice/[sessionId]/`
- New route-local component files only after behavior tests exist.

Steps:

1. Continue the existing pattern: hooks own recording state, hotkeys, lifecycle, and future websocket/session state boundaries.
2. Add characterization tests before moving any JSX that controls recording, hotkeys, status labels, or mobile quick actions.
3. Split UI only after hooks are stable: status header, transcript panel, controls, mobile shortcuts.
4. Keep external API calls, websocket message shape, keyboard behavior, and mobile quick-entry behavior unchanged.

Exit criteria:

- Existing hotkey, lifecycle, recording state-machine, and page tests pass.
- No behavior-only page refactor lands without a corresponding route-level test.

## 4. Test plan mapped to source test spec

| Requirement | Low-risk test before implementation | Later full test |
| --- | --- | --- |
| Sales combination API success renders server config | Adapter unit test with two enabled rules and one disabled rule | Page test verifies server priority plus personalized reorder |
| API failure uses fallback array | Page test with active-rules fetch rejection | E2E smoke starts a fallback combination |
| Missing persona visible | Existing `page.test.tsx` covers unavailable cards | Keep after server config migration |
| Admin draft creation | Mock API page test asserts draft list refresh | Backend integration test owns persistence |
| Non-admin mutation denied | Admin page test renders disabled/denied state | Backend permission test returns 403 |
| Invalid schema publish rejected | Adapter/page test displays validation errors | Backend schema publish test rejects |
| Preview does not affect active version | Page test compares active version before/after preview | Backend test asserts no active mutation |
| Publish/rollback audit fields | Page test renders actor/before/after/version/reason/trace id | Backend integration test asserts audit write |
| Report hook extraction | Existing report page render assertions before extraction | Hook tests for success/failure/loading per concern |
| Practice decomposition | Existing route-local hook tests stay green | Page tests for status label, recording, hotkeys, mobile shortcut |

Recommended frontend verification commands for each slice:

```bash
pnpm --dir web exec tsc --noEmit --pretty false
pnpm --dir web exec vitest run 'src/app/(dashboard)/training/sales/page.test.tsx' --reporter=dot
pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/**/*.test.ts*' --reporter=dot
pnpm --dir web exec eslint 'src/app/(dashboard)/training/sales/page.tsx' 'src/app/(user)/practice/[sessionId]' --quiet
```

Run the admin-route test command once Slice C creates the route:

```bash
pnpm --dir web exec vitest run 'src/app/admin/business-rules/sales-combinations/**/*.test.tsx' --reporter=dot
```

## 5. Rollback and safety rules

- Keep `CLIENT_DEFAULT_SALES_COMBINATIONS_V1` until at least one release proves the active server ruleset read path.
- Any invalid active server config falls back to safe client defaults; it must not block learners from starting existing combinations.
- Admin publish and rollback must be backend-confirmed; do not persist draft state only in localStorage.
- Do not add new dependencies for forms, tables, validation, or charts in these slices without a separate ADR.
- Do not mix report/practice visual redesign with data-hook extraction.
- Do not enable adaptive difficulty, external sharing, or supervisor/coach access from this lane.

## 6. Open dependencies for backend/verification lanes

- Confirm final backend endpoint names for business-rule active reads and admin mutations.
- Confirm whether business-rule audit uses an existing audit table or a new rule-publication audit table.
- Confirm permission payload shape for read-only admin users versus full admin mutators.
- Confirm whether `ruleset_version`, `score_basis`, and `evidence_completeness` appear in report API responses before the report page displays them as governed fields.

## 7. Definition of done for this frontend/admin lane

A later implementation of this plan is complete only when:

1. Sales combinations can render a valid active server ruleset and safely fall back to current defaults.
2. Admins have a permission-gated draft/preview/publish/rollback UI with audit fields.
3. Report and practice pages have data hooks extracted with behavior locked by tests before visual component splits.
4. Phase 3 tests from the roadmap are represented in Vitest/RTL or explicitly delegated to backend integration tests.
5. Full typecheck, targeted tests, and targeted lint pass, with any environment blockers documented.

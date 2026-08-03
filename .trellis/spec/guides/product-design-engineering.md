# Product Design and UI Engineering

> Project-specific execution contract for work that changes what users see, understand, choose, enter, approve, or execute. The normative design source is the repository-root `DESING.md` (the filename is intentionally recorded as it exists on disk).

> **Newcomer target note (2026-07-16):** `docs/newcomer-foundation-contract-index.md` is the accepted product/domain baseline. It is a target contract, not proof that the v2 pages exist.

## Newcomer Foundation Page Contract

- Learner navigation has one foundation-training entry: current training, history, profile, and notifications. Realtime is absent from first-launch navigation and empty-state promotion.
- The learner work object is Stage/Activity, never Phase/Module. First-launch `assignment` means exactly three asynchronous customer-scenario recordings, not generic homework.
- Admin `/admin/newcomer-training` starts from work queues, not KPI cards. Path editing uses outline/editor/inspector and ReleasePlan preview; missing governed resources are selected or minimally created and bound in-flow.
- Journey, Activity Workspace, Task Status, Evidence Dossier, and Admin Queue use the v2 ViewModels. UI does not assemble readiness from raw cross-domain DTOs.
- `foundation_ready` is labeled basic-training readiness, never real-sales competence. AI assessment, deterministic rule, evidence limitation and human decision remain visually distinct.
- Background work has a persistent result location, real stage, cancellation where supported, and refresh recovery. No spinner-only long task or toast-only important outcome.
- All target surfaces include applicable loading, first-use empty, filtered no-result, permission, partial, failure/retry, stale/conflict, cancelled, offline/degraded and background-pending states.

## 1. Scope and authority

Read this guide before changing pages, navigation, forms, tables, filters, settings, permissions, user-facing API results, AI-assisted workflows, or any loading/error/recovery state.

Resolve conflicts in this order:

1. Security, privacy, legal, and data-governance requirements.
2. Approved domain rules, permission policies, ADRs, and API contracts.
3. Existing project tokens, primitives, and proven page patterns.
4. `DESING.md` and this executable project projection.
5. Historical screenshots and external product references.

`DESING.md` does not authorize a new visual system. The current frontend uses Tailwind, Radix wrappers, Lucide icons, and the established canvas/surface language under `web/src/components/ui/`. Preserve that foundation unless a project decision explicitly replaces it.

## 2. Required page contract

Before implementation, record the following in the task PRD, implementation notes, or design artifact:

| Field | Required decision |
|---|---|
| User and context | Who is working, where, and under which role or permission scope? |
| Primary task | What must the user complete before leaving, and what proves success? |
| Work object | Which course, activity, learner, report, asset, rule, revision, or run is being handled? |
| Page model | List-detail, editor-preview, process-approval, settings-configuration, dashboard-drilldown, or conversation-workspace? |
| Actions | One dominant action per scope; secondary and destructive actions have lower or risk-specific emphasis. |
| Data and authority | API/domain source, lifecycle state, permission policy, freshness, and audit requirements. |
| State matrix | Default, loading, empty, no-result, success, partial, failure, permission, stale/conflict, submitting, retrying, and cancelled where applicable. |
| Resilience | Input preservation, duplicate-submit protection, retry/idempotency, recovery, and long-running result location. |
| Presentation | Responsive rearrangement, keyboard/focus behavior, long text, large values, and realistic density. |

The task sentence should fit this form: “当【角色】处于【场景】时，帮助其基于【对象/证据】完成【任务】，并得到【可验证结果】。” Do not invent a role, metric, lifecycle state, or permission to complete this table.

## 3. Local page and component patterns

Use the repository's intent-based page shells instead of starting from a generic dashboard or card grid:

- `web/src/components/admin/admin-layout-shells.tsx` owns `AdminIndexShell`, `AdminDetailShell`, `AdminFormShell`, `PolicyPageShell`, `AdminPageHeader`, and `AdminContextBar`. Its header API separates primary and secondary actions.
- `.trellis/spec/frontend/admin-console-patterns.md` defines the existing Assets, Policy, Analytics, and Org/System route models. Keep create/edit/import workflows in their established routes rather than combining unrelated intents into one page.
- `web/src/components/ui/glass-modal.tsx`, `confirm-dialog.tsx`, `tabs.tsx`, `responsive-table-wrapper.tsx`, and `status-indicator.tsx` are the approved primitives for their current semantics.
- A `GlassCard` is a surface primitive, not the default wrapper for every section. Prefer alignment, spacing, tables, lists, and the page shells; avoid nested cards and card-per-field layouts.
- Links navigate and retain browser semantics; buttons perform actions. Labels use precise verb + object wording such as “发布课程” or “保存规则”, not generic “确定” or “处理”.

Existing production code is evidence, not automatic approval. For example, `web/src/components/ui/empty-state.tsx` is reusable but currently presents one generic card-shaped state; new work must still distinguish first-use empty, filtered no-result, normal zero, and no-permission states when those meanings differ.

## 4. In-flow completion

Missing related data must not force users out of the primary workflow. The default sequence is:

1. Select an existing governed object.
2. Offer a minimal quick-create path in the current page, dialog, drawer, or inline region when permitted.
3. Validate permissions and duplicates on the backend.
4. Create and automatically bind the object to the current context.
5. Keep the entered data and show actionable failure feedback if any step fails.
6. Record the write and expose a stable result; allow later enrichment where the domain permits it.

Current evidence: `web/src/components/admin/newcomer-training/activity-resource-drawer.tsx` creates or selects Foundation resource revisions without leaving the v2 path editor. The governed `POST /api/v1/admin/newcomer-training/resources` route in `backend/src/foundation_admin_api.py` delegates to the resource application services, validates organization/capability and idempotency context, commits once, and returns the created revision for immediate binding.

Do not fabricate a missing governed execution profile, scoring policy, role, or model configuration. When safe quick creation is unavailable, keep the user in context with a clear unavailable/permission state and the valid next action.

## 5. Frontend data and state contract

Keep the existing boundary:

```text
API DTO -> domain type/model -> pure ViewModel or presentation helper -> UI component
```

- Pages call the outward `api` facade from `web/src/lib/api/client.ts`; request and transport mechanics stay out of JSX.
- Domain DTO ownership and ViewModel rules are defined in `.trellis/spec/frontend/domain-locality-and-report-view-models.md`.
- Unknown enums, internal error codes, trace IDs, raw JSON, provider/runtime terms, database identifiers, and seed/test language do not reach ordinary user UI. Translate them into established business language; retain technical detail only in authorized diagnostics or audit views.
- Preserve filters, tabs, pagination, sort, selected objects, and other shareable state in the URL where the route model supports it.
- Do not display partial failure as success. Show successful, failed, and skipped scopes plus a retry or compensation path.
- Recoverable failures keep user input. Submitting controls prevent duplicate writes and retain their label while showing progress.

`web/src/lib/api/client.ts` is the shared normalization boundary for request errors, CSRF, trace propagation, timeout, and cancellation. Do not bypass it with page-local `fetch`.

## 6. Backend support for user-visible behavior

Backend work that changes visible behavior is part of the product contract:

- Routes handle protocol and dependencies; application/domain services own state changes, transactions, permission decisions, and audit behavior.
- Enforce role and object scope on the backend. A hidden frontend control is never authorization.
- Return stable error codes for programmatic handling plus user-safe messages and structured details where the UI needs field/object recovery.
- Critical writes accept or derive the expected revision/idempotency context, commit atomically, roll back on failure, and emit traceable audit records.
- High-risk changes expose preview/diff, reason, approval or explicit confirmation as appropriate; preserve version and rollback/compensation paths.

Project evidence: `backend/src/foundation_admin_api.py` and `backend/src/foundation_readiness_api.py` expose strict request models, capability/object scope, expected revision and idempotency context, service-owned transactions, audited preview/confirm commands and structured validation details. Contract and integration tests must assert these behaviors, not only HTTP 200.

## 7. AI feature gate

Before adding AI, test whether rules, validation, SQL/calculation, search/ranking, or workflow automation solve the task more reliably. Use AI only for language understanding, ambiguous judgment, generation, multi-source synthesis, or open-ended reasoning.

When AI is justified:

- Choose the smallest surface: inline assist, object action, inspector, structured workspace, agent run, and conversation only when multi-turn clarification is intrinsic.
- Show the governed context scope and relevant inputs.
- Distinguish fact, rule, calculation, inference, recommendation, and draft.
- Preserve sources, version/freshness, limitations, and verification state.
- Provide review, edit, reject, cancel, takeover, undo/compensation, and approval according to risk.
- Persist formal results into the relevant course, activity, report, review, task, revision, or audit object; do not trap them only in chat.
- Never execute arbitrary model-generated HTML, JavaScript, CSS, commands, or tool calls without a typed allowlist, permission/policy validation, runtime validation, fallback, and audit.

Sales-training scoring and readiness decisions affect employees and therefore require evidence and human review. See `backend/src/foundation_readiness_api.py` (`record-decision` and exception preview/confirm commands), `backend/src/readiness/application.py` and `.trellis/spec/frontend/domain-locality-and-report-view-models.md` for the current evidence-to-review projection.

## 8. Verification matrix

Verification must inspect the rendered interface as well as code. Select the relevant rows and record evidence:

| Area | Minimum check |
|---|---|
| Primary task | Current object, status, dominant action, and next step are apparent without reading implementation terminology. |
| States | Loading, empty, no-result, error/retry, permission, success/partial, and stale/conflict branches match the API contract. |
| Forms | Labels, helper/error association, dirty/input preservation, duplicate-submit protection, server errors, and unsaved-exit behavior. |
| Accessibility | Keyboard completion, visible focus, semantic controls, icon accessible names, focus entry/return for overlays, and non-color status cues. |
| Responsive | Narrow viewport, 200% zoom, long Chinese/English text, large values, stable tables/toolbars, and no hidden primary action. |
| Resilience | Slow network, timeout-after-possible-write, retry safety, refresh/back restoration, and long-task result recovery. |
| AI | Context, evidence, uncertainty, human control, cancellation, partial failure, and persisted formal result. |

Run the frontend gates from `web/` (`npx tsc --noEmit`, `npm run lint`, focused Vitest, then the relevant Playwright path). Run backend focused unit/integration/contract tests plus Ruff and mypy for changed contracts. Use CodeGraph `affected` to select additional regression tests.

## 9. Anti-patterns and known gaps

Reject these patterns unless a documented business reason overrides the rule:

- KPI/dashboard theater without a decision, anomaly, drilldown, and action.
- Card walls, nested cards, modal chains, settings dumps, and oversized chrome.
- Generic actions, raw enums/codes, hidden filters or permission state, and toast-only important outcomes.
- Desktop layouts merely compressed on mobile.
- AI visual decoration, chat for deterministic workflows, or model inference presented as verified fact.
- Requiring navigation to another module merely to create or associate a missing object.

Known documentation gap: root instructions refer to `design.md`/`DESIGN.md`, while the normative file currently present is `DESING.md`. This guide uses the real path and does not silently rename it; a repository-wide rename requires a separate compatibility decision because external automation may reference the current filename.

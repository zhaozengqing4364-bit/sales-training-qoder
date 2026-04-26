# Worker-3 Review / Documentation Closeout — Team Fix Audit Errors Frontend Optimization

- Worker: `worker-3`
- Task: `3` — Review code quality and update documentation
- Timestamp: 2026-04-26 18:18 Asia/Shanghai
- Inputs:
  - PRD: `/Users/zhaozengqing/github/销售训练qoder/.omx/plans/prd-team-fix-audit-errors-frontend-optimization-20260426.md`
  - Test spec: `/Users/zhaozengqing/github/销售训练qoder/.omx/plans/test-spec-team-fix-audit-errors-frontend-optimization-20260426.md`
  - Source audit report: `/Users/zhaozengqing/github/销售训练qoder/.omx/reports/audit-errors-frontend-optimization-20260426T093026Z/REPORT.md`
- Scope performed: review/documentation only. No business-source files were modified by this worker.

## 1. Implementation-Before Configuration Judgment

### 1.1 Stable code logic

These should remain centralized in code and covered by tests because they represent system contracts or security boundaries:

| Area | Stable logic | Required central owner |
| --- | --- | --- |
| WebSocket authentication | Cookie/session-vs-query-token resolution order and compatibility semantics. | Backend auth / websocket resolver and integration tests. |
| Business-rule infrastructure | `BusinessRuleConfig` lifecycle, status transitions, audit snapshots, validation failure handling. | `backend/src/common/business_rules/**` and DB model constraints. |
| Prompt template safety | Template type enum, variables schema, validation on save/read, safe rendering. | `backend/src/prompt_templates/**` plus admin prompt UI contracts. |
| Presentation thumbnail authorization | Minimum access-control floor for thumbnail upload/read. | Presentation router permission dependency + endpoint ownership checks. |
| Runtime fault contract | Severity/kind schema, fault payload shape, window semantics. | `backend/src/support/**` and `web/src/lib/api/types.ts`. |

### 1.2 Configurable business rules / content

The following must not be scattered as long-term hardcoded rules:

| Rule/content | Why configurable | Required configuration source |
| --- | --- | --- |
| Sales training combinations: capability × role, priority, enabled state, fallback policy. | Product/operation/admin likely needs to adjust training menu and targeting. | `BusinessRuleConfig` definition `sales.training.combinations.ruleset` with default seed, active resolver, admin publish/rollback API. |
| Runtime fault display copy and action suggestions. | Support wording/action routing may change without code deploy. | Central display dictionary initially; later system config/admin setting. |
| Admin settings persistence capabilities. | Each setting needs explicit read-only vs editable capabilities, permissions, audit, rollback. | Capability/config registry consumed by `/admin/settings`. |
| Prompt template runtime types and variable schemas. | Prompt governance is an admin-managed domain, but schema safety is code-enforced. | Prompt template enum/schema + migration/validation registry. |
| UX/error copy for business-rule fallback. | User-facing text should stay business-readable and consistent. | Central frontend message/dictionary module or backend metadata. |

### 1.3 Current configuration gap to close before release

Current worktree evidence still shows `sales.training.combinations.ruleset` is not defined in the backend business-rule registry:

- `backend/src/common/business_rules/defaults.py:9-12` defines only growth/recommendation keys.
- `backend/src/common/business_rules/defaults.py:134-186` registers only achievement, AI coach, and next-practice recommendation definitions.
- `backend/src/common/business_rules/validators.py:23-35` dispatches only those existing keys.
- `backend/src/router_registry.py:8-40,66-202` does not import/include `admin.api.business_rules.router`.
- `web/src/lib/api/client.ts:2026-2028` still calls `/business-rules/sales-combinations/active`.
- `web/src/lib/api/client.ts:2215-2249` still calls `/admin/business-rules/sales-combinations*`.
- `web/src/lib/api/sales-combinations.ts:43-56,162-175` still contains client-side default combinations; this is acceptable only as a short-term audited fallback, not as the long-term source of truth.

## 2. Code Quality Review Findings

### R-001 — Business-rule router exists but remains unreachable in this worktree

- Evidence:
  - `backend/src/admin/api/business_rules.py:27` defines `APIRouter(prefix="/business-rules")`.
  - `backend/src/admin/api/business_rules.py:131-204` exposes definitions, seed-defaults, list, and active endpoints.
  - `backend/src/router_registry.py` currently imports/mounts many admin routers but not `admin.api.business_rules.router`.
- Release impact: A-003 remains open; generic admin business-rule endpoints will 404 unless another lane mounts the router.
- Required close condition: `GET /api/v1/admin/business-rules/definitions` returns 200 and includes `sales.training.combinations.ruleset`.

### R-002 — Sales combinations still need backend-owned default, validator, active endpoint, and admin adapter

- Evidence:
  - Client contract exists in `web/src/lib/api/client.ts:2026-2028` and `web/src/lib/api/client.ts:2215-2249`.
  - Frontend validation/default fallback exists in `web/src/lib/api/sales-combinations.ts:115-196`.
  - Backend default definitions currently do not include sales combinations.
- Risk: frontend can render with `CLIENT_DEFAULT_SALES_COMBINATIONS_V1`, but admin cannot publish/rollback and operators cannot manage role/capability rules.
- Required close condition:
  1. `sales.training.combinations.ruleset` default is seeded by backend.
  2. Active user endpoint resolves DB published config, bundled default fallback, and invalid-config fallback with auditable `source/fallback_reason`.
  3. Admin endpoints match current frontend contract or frontend contract is intentionally migrated with tests.

### R-003 — `/admin/settings` read-only mitigation is partially present but still documents a product gap

- Evidence:
  - `web/src/app/admin/settings/page.tsx:87-100` defines read-only tabs and a clear notice.
  - `web/src/app/admin/settings/page.tsx:711-719` disables discard/save buttons for read-only tabs.
- Assessment: This improves trust compared with a silently editable non-persistent form. The remaining limitation is intentional: settings are displayed as target-state placeholders until persistence APIs, validation, permissions, audit, and rollback are implemented.
- Required close condition: Either keep these tabs explicitly read-only in UX/tests, or implement persistence through a governed settings API with audit trail.

### R-004 — Runtime diagnostics avoid raw `[object Object]`, but display-policy governance remains open

- Evidence:
  - `web/src/app/(dashboard)/support/runtime/page.tsx:26-36` formats objects with `JSON.stringify`.
  - `web/src/app/(dashboard)/support/runtime/page.tsx:341-386` renders diagnostic entries as structured chips.
- Assessment: This addresses the most visible `[object Object]` symptom in the current page code, but kind-specific actions/copy are still code-local and should be dictionary/config-governed when product/support wants to tune guidance.
- Required close condition: runtime page test must cover nested object/array diagnostics and unknown kind fallback; backend should preserve structured data in `RuntimeStatusService.build_faults_payload`.

### R-005 — Playwright audit spec path from the test spec is absent in this worktree

- Evidence: `find web -type f | grep -i audit` returns only `web/src/components/audio/AudioAuditCard.tsx`; `web/tests/e2e/audit/audit.spec.ts` is not present.
- Impact: E1 cannot be satisfied until the audit spec is restored/added or the test spec path is amended by leader/integration.
- Required close condition: add `web/tests/e2e/audit/audit.spec.ts` with same-origin/dev-login-safe behavior and structured JSON artifacts, or update the test spec with the actual path and equivalent coverage.

### R-006 — Verification gates are intentionally failing until implementation lanes land

This worker did not attempt to mask or skip tests. The original audit already documents expected failures:

- backend non-performance tests: 6 failures tied to A-005..A-008.
- `pip check`: missing `packaging` for `wheel 0.46.3`.
- npm audit: PostCSS/Next moderate vulnerability chain.
- Playwright audit: absent/broken audit spec path.

These should remain visible until fixed by the responsible implementation lanes.

## 3. A-001..A-015 Closeout Matrix for Integration Lead

Status meanings:

- `OPEN`: current worktree still shows the defect or no integrated fix is visible.
- `PARTIAL`: current worktree shows mitigation, but release acceptance still needs tests/full gate.
- `PENDING-INTEGRATION`: this worker cannot verify because another lane owns the source change.
- `DEFER-ADR`: acceptable only with a written ADR/risk owner.

| ID | Current review status | Required evidence before final close |
| --- | --- | --- |
| A-001 | OPEN | `GET /api/v1/business-rules/sales-combinations/active` 200; `/training/sales` no network 404; no `[HTTP_404]` user-facing text. |
| A-002 | OPEN | `GET /api/v1/admin/business-rules/sales-combinations` 200 for admin; validate/preview/publish/rollback covered by component/API tests. |
| A-003 | OPEN | Router registry mounts business-rule router; `definitions` route returns `sales.training.combinations.ruleset`. |
| A-004 | PARTIAL | Runtime UI test proves no `[object Object]`; backend runtime faults contract tests cover structured diagnostics and unknown kind fallback. |
| A-005 | PENDING-INTEGRATION | Targeted backend regression command in test spec B3 passes. |
| A-006 | PENDING-INTEGRATION | WebSocket auth test proves cookie session wins when both cookie/query are present, unless security-reviewed ADR changes contract. |
| A-007 | PENDING-INTEGRATION | Thumbnail tests cover authorized 200 and unauthorized 401/403 without broad permission bypass. |
| A-008 | PENDING-INTEGRATION | `score_basis`/`ruleset_version` either removed from old contract or versioned with compatible frontend/test coverage. |
| A-009 | PENDING-INTEGRATION | PromptTemplate invalid historical records become visible/disabled/migrated; save API rejects invalid `prompt_type`/variables with readable 400. |
| A-010 | PENDING-INTEGRATION or DEFER-ADR | `npm audit --audit-level=moderate --json` is green, or ADR records why safe upgrade is deferred. |
| A-011 | PENDING-INTEGRATION | `cd backend && venv/bin/python -m pip check` is green; dependency source updated. |
| A-012 | OPEN | `web/tests/e2e/audit/audit.spec.ts` exists and uses `context.request.post` or same-origin flow; structured JSON artifacts are produced. |
| A-013 | PENDING-INTEGRATION | Full vitest run has no new React `act(...)` warning or unasserted expected-error stderr pollution. |
| A-014 | PENDING-INTEGRATION or DEFER-ADR | Python support policy documented; dev/CI aligns to supported Python or 3.14 upgrade plan exists. |
| A-015 | PARTIAL | Team worktree baseline remains clean except intentional committed changes; dirty state owner recorded before integration. |

## 4. Required Configuration Item Register

| Config item | Type | Default | Read location | Management entry | Validation | Permission | Audit | Fallback/rollback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sales.training.combinations.ruleset` | `BusinessRuleConfig` / `rule_json` | Backend bundled migration of the current 10 client default combinations, versioned as `sales_combinations_v1`. | User active resolver plus `/api/v1/business-rules/sales-combinations/active`. | `/admin/business-rules/sales-combinations`. | `rule_set_id`, `version`, `combinations`, `fallback_policy`; unique id; unique capability×role; positive priority; enabled/non-empty unless `hide_all`. | admin view/mutate/publish split; user active endpoint requires authenticated user/admin. | draft/validate/preview/publish/rollback/disable/delete_draft with actor, reason, before/after, trace_id. | Missing/invalid DB config returns bundled default with `source/fallback_reason`; rollback to prior published/archive. |
| `support.runtime.fault_display_policy` | dictionary/config | Safe generic title/action for unknown kind; specific entries for blocking/warning kinds. | Runtime status page or API metadata. | Later system config/admin runtime governance. | kind allowlist, copy length, object-safe rendering. | support/admin. | Actor/reason when changed after config-backed. | Unknown kind uses safe fallback and structured diagnostic viewer. |
| `admin.settings.persistence_capabilities` | capability registry/config | General/security/notifications read-only unless persistence API exists. | `/admin/settings` page. | System settings module. | Each setting declares type/default/range/required/effective scope. | admin. | save/disable/rollback/test-connection. | Read-only disabled controls when API missing. |
| `prompt_templates.allowed_runtime_types` | enum/schema registry | Existing prompt types plus explicit decision on `realtime_scoring`. | PromptTemplateService and admin prompt forms. | `/admin/prompts`. | variables are list/schema-valid; template variables resolvable; illegal type rejected or migrated inactive. | admin prompt manager. | create/update/default/disable/migrate. | Invalid historical template disabled/visible; runtime logs but does not crash core flow. |

## 5. Final Acceptance Command Checklist

Run these after implementation lanes are merged into the integration branch/worktree. Do not skip, loosen, or delete failing tests to force green.

```bash
git status --short
git diff --check

cd backend && venv/bin/ruff check src tests --quiet
cd backend && venv/bin/python -m pytest \
  tests/integration/test_history_evidence_flow.py::test_history_statistics_and_trends_share_same_session_evidence_projection \
  tests/integration/test_presentation_thumbnail_api.py::test_upload_presentation_sets_page_image_url \
  tests/integration/test_presentation_thumbnail_api.py::test_thumbnail_endpoint_returns_image_payload \
  tests/integration/test_websocket_status_contract.py::test_websocket_auth_prefers_session_cookie_before_query_token_compatibility \
  tests/integration/test_websocket_status_contract.py::test_presentation_handler_status_error_and_session_end_include_trace_id \
  tests/unit/test_effectiveness_canonical_kernel.py::test_projection_kernel_contract_exposes_shared_kernel_metadata \
  -q --no-cov
cd backend && venv/bin/python -m pytest tests -q --no-cov -m "not performance"
cd backend && venv/bin/python -m pip check

cd web && npm exec -- tsc --noEmit --pretty false
cd web && npm exec -- eslint . --quiet
cd web && npm exec -- vitest run --reporter=dot
cd web && npm run build
cd web && npm audit --audit-level=moderate --json
cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 \
  npm exec -- playwright test tests/e2e/audit/audit.spec.ts --reporter=line
```

## 6. Review Recommendations for Leader / Integration

1. Assign a single owner for `backend/src/router_registry.py` and `backend/src/common/business_rules/**` before integrating Lane 1 changes; these are shared files and easy to conflict.
2. Require Lane 1 and Lane 2 to agree whether frontend keeps sales-specific admin endpoints or migrates to generic business-rule endpoints. Do not leave both partially implemented without tests.
3. Treat the missing `web/tests/e2e/audit/audit.spec.ts` as an integration blocker for E1. If another worktree has it, merge that file before running final full gate.
4. Keep `/admin/settings` read-only mitigation unless a real persistence API with validation/permission/audit/rollback lands in the same release.
5. Convert any deferred security/dependency item (A-010/A-014) into an ADR with owner, expiry date, impact, and compensating control; do not silently mark it fixed.

## 7. Verification Performed by Worker-3

| Check | Result | Evidence |
| --- | --- | --- |
| Inbox/task lifecycle | PASS | Startup ACK sent; task 3 claimed with claim token through `omx team api claim-task`. |
| Baseline git status | PASS | `git status --short` initially empty in worker-3 worktree. |
| Whitespace baseline | PASS | `git diff --check` passed before documentation edit. |
| Plan/report inputs read | PASS | PRD/test spec and source audit report read from leader `.omx` paths. |
| Code review sampling | PASS | Reviewed router registry, business-rule defaults/validators, sales-combinations frontend contract, runtime status diagnostics, admin settings read-only UX. |

Full product verification is intentionally not claimed here because worker-3 performed the documentation/review slice and did not integrate the implementation lanes. The final acceptance checklist above must be executed by the integration lead after source fixes are merged.

# 2026-05-01 Review Remediation Lane 0 Matrix

Generated: `2026-05-01T11:45:00+08:00`  
Team: `execute-the-remediation-progra`  
Worker: `worker-3`  
Task: `3` — review code quality and update documentation  
Source of truth: `/Users/zhaozengqing/github/销售训练qoder/.omx/specs/deep-interview-review-remediation-team-plan.md`

## 1. Non-negotiable boundaries

- Scope is **all-staged**: CRITICAL, HIGH, MEDIUM, and LOW findings are tracked below.
- Destructive or external-production actions remain **approval-gated**. This plan records them as release gates; it does not rotate real credentials, rewrite remote history, delete production secrets, or change production settings.
- First-pass non-goal remains **no product UI redesign**. Frontend work is limited to contract alignment, functional fixes, disabled-state correctness, and existing layout-preserving behavior.
- Team workers must not touch `/Users/zhaozengqing/github/销售训练qoder/.omx/preteam-untracked-20260501T033414Z`; this document only records that it is a preteam untracked backup path.
- Green tests are necessary but not sufficient: release remains blocked until external gates and release evidence are complete.

## 2. Baseline workspace note

Initial worker-3 worktree status before this documentation change:

```text
## HEAD (no branch)
```

No unrelated changes were reverted or normalized by this task.

## 3. Release-blocker order

1. **Secret blast-radius control** — scrub committed examples/docs, add secret scan, and track approval-gated real rotation/history remediation.
2. **Direct security fixes** — SSRF/API-key exfiltration, PPT path traversal, and RAG key plaintext storage.
3. **User-facing governance bypasses** — sales-combination governance, unsafe recommendation routes, scoring ruleset governance, objection-ledger rules, and growth-goal config.
4. **Verification/runtime gates** — verification runner runtime errors, API envelope drift, CORS/query token fail-closed behavior, app assembly authority, startup schema authority, and runtime status failures.
5. **Management/release hygiene** — Alembic graph evidence, route inventory, final targeted tests, lint/typecheck evidence, and any remaining explicit backlog.

## 4. Issue-to-lane matrix

Status vocabulary for this matrix:

- `planned`: local reversible code/tests/docs/CI work is required and assigned to a lane.
- `approval-gated`: required release action is external/destructive and must not be executed by this team without explicit authorization.
- `evidence-gate`: verification/integration evidence is required before release readiness can be claimed.

| Issue ID | Severity | Finding | Lane / owner | Primary write scope | Required evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CRIT-1 | CRITICAL | Credential exposure in working tree and git history | Lane 1 — security backend/ops | `.env.example`, credential-bearing docs/examples, secret-scan CI/config/scripts/tests | Secret scan passes on committed docs/env examples; release checklist names OpenRouter/StepFun/model encryption/OSS rotation and history cleanup as approval-gated gates | `planned` + `approval-gated` |
| HIGH-1 | HIGH | Admin model-config SSRF and API-key exfiltration | Lane 2 — backend security | `backend/src/common/ai/schemas.py`, `backend/src/admin/api/model_configs.py`, centralized URL/policy helper/tests | Unsafe/private/redirected endpoints rejected before Authorization-bearing calls; allowed provider probe works under mocked HTTP client; errors redact secrets | `planned` |
| HIGH-2 | HIGH | PPT upload path traversal | Lane 3 — backend file safety | `backend/src/admin/api/admin.py`, shared upload validator/storage helper, tests | Traversal/absolute/nested/wrong-extension uploads fail safely; valid `.ppt`/`.pptx` use server-generated names under upload root | `planned` |
| HIGH-3 | HIGH | RAG cross-encoder API key stored/returned as plaintext | Lane 4 — backend knowledge/security | `backend/src/admin/api/rag_profiles.py`, `backend/src/common/knowledge/rag_profile_*`, encryption helper usage, tests/migration if needed | Raw DB value differs from plaintext; API responses expose only `has_api_key`; runtime decrypt path is controlled; legacy plaintext migration is operator-gated or safely lazy | `planned` |
| HIGH-4 | HIGH | Sales-combination governance bypass at learning entry | Lane 5 — frontend + backend business rules | `web/src/app/(dashboard)/training/sales/page.tsx`, `web/src/lib/api/client.ts`, sales-combination resolver/tests; backend only if fallback/API missing | Active published rules affect learner entry; invalid/missing rules fall back safely; publish/rollback visibility is covered | `planned` |
| HIGH-5 | HIGH | Unsafe recommendation `target_path` reaches frontend `Link` | Lane 6 — frontend security | New `web/src/lib/routing` or `web/src/lib/recommendations` utility, dashboard/report recommendation surfaces, tests | Absolute/protocol-relative/encoded external/`javascript:`/traversal/unsupported paths normalize to safe fallback; valid internal routes still work | `planned` |
| HIGH-6 | HIGH | Release verification runner has deterministic runtime errors | Lane 7 — backend reliability | `backend/src/common/analytics/verification_runner.py`, tests | Verification runner imports and executes missing-doc, docs-error, API-contract, README, deploy-doc, and exception paths with dataclass-compatible result fields | `planned` |
| HIGH-7 | HIGH | Real report scoring bypasses scoring-ruleset governance | Lane 8 — backend evaluation | `backend/src/evaluation/services/comprehensive_report.py`, `backend/src/presentation_coach/services/presentation_report_service.py`, scoring metadata/tests | Report generation resolves active/default ruleset, persists/discloses id/version/source/basis, and records observable legacy fallback only when no valid ruleset exists | `planned` |
| MED-1 | MEDIUM | Frontend API envelope drift/double unwrap | Lane 9 — frontend API | `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, client contract tests | Contract fixtures prove `apiFetch` returns unwrapped payload; RAG/chunking and other domain methods no longer double-unwrap `result.data` | `planned` |
| MED-2 | MEDIUM | Objection ledger trigger/score rules hardcoded | Lane 10 — backend business-rule/config | `backend/src/sales_bot/websocket/components/objection_ledger_helpers.py`, business-rule config seed/validator/admin API if available, tests | Default seed mirrors current behavior; missing/invalid/configured override cases are tested; admin/config gap is explicitly documented if current infrastructure cannot wire it | `planned` |
| MED-3 | MEDIUM | Production CORS appends dev origins / fails open | Lane 11 — backend architecture/reliability | `backend/src/app_factory.py`, settings adapter/tests | Dev/test origins are only appended in dev/test; production with credentials fails closed without explicit valid origins | `planned` |
| MED-4 | MEDIUM | `backend/src/main.py` app assembly authority drift | Lane 11 — backend architecture/reliability | `backend/src/main.py`, `backend/src/router_registry.py`, route inventory tests | One app assembly authority is documented/tested; critical admin/business/scoring routes exist at canonical paths | `planned` |
| MED-5 | MEDIUM | Startup `create_all` masks migration gaps | Lane 11 — backend architecture/reliability | `backend/src/common/db/session.py`, app startup/lifespan tests | Production startup does not silently `create_all`; dev/test/local bootstrap path remains explicit; Alembic is the production authority | `planned` |
| MED-6 | MEDIUM | Runtime status swallows dependency/calculation failures | Lane 11 — backend architecture/reliability | `backend/src/support/api/runtime_status.py`, tests | Dependency failure returns `503` or explicit `degraded=true` with error/trace id instead of empty healthy success | `planned` |
| MED-7 | MEDIUM | History disabled report action remains clickable through parent `Link` | Lane 12 — frontend functional | `web/src/app/(dashboard)/history/page.tsx`, existing tests | When `canOpenReport` is false there is no active ancestor `Link`; true path preserves existing layout via established button/link pattern | `planned` |
| MED-8 | MEDIUM | Dashboard weekly goal hardcoded in page code | Lane 12 — frontend functional | `web/src/app/(dashboard)/page.tsx`, frontend config adapter/tests | Goal reads through centralized adapter with default `3`; invalid/missing/configured values are validated and covered without UI redesign | `planned` |
| LOW-1 | LOW | Alembic merge/test artifacts may be untracked or stale | Lane 13 — test/build/verifier | Alembic merge/test files if needed, evidence docs | `alembic heads` reports a single release-ready head or stale artifacts are explicitly removed with rationale; migration graph test evidence is recorded | `evidence-gate` |
| LOW-2 | LOW | WebSocket query-token compatibility mode needs production gate | Lane 11 — backend architecture/reliability | WebSocket auth files/config/tests | Query token is disabled in production by default and enabled only in development/test or explicit guarded config; cookie/header path remains | `planned` |

Completeness check: this matrix covers 18 findings exactly once: 1 CRITICAL, 7 HIGH, 8 MEDIUM, and 2 LOW.

## 5. External / approval-gated release gates

| Gate | Why it is gated | Required operator evidence before release |
| --- | --- | --- |
| Real credential rotation | The review indicates exposed provider/model/storage secrets may already be compromised; only authorized operators can rotate live secrets. | Rotation records for OpenRouter, StepFun, model encryption keys, Alibaba OSS, and any other discovered secret; old values revoked. |
| Remote git history cleanup | History rewrite/force-push is destructive and coordination-heavy. | Approved history-remediation plan, protected-branch coordination, post-cleanup secret scan, and contributor re-clone instructions. |
| Production configuration changes | Live CORS/query-token/provider allowlist changes can affect customers. | Approved production config diff, rollback path, and observed startup/runtime status after deploy. |

## 6. Quality review guardrails for implementation lanes

- Stable security invariants belong in code with regression tests: SSRF IP class rejection, upload path containment, secret redaction, route normalization, and production fail-closed defaults.
- Business-adjustable values must not be scattered into pages/controllers/helpers. Use existing governance/config services first; if absent, add a centralized adapter/validator/seed and document: **“基于当前提供的代码，暂无法确认现有配置体系，需要补充配置模块、后台管理模块、字典表、权限模块或系统设置相关代码。”**
- UI changes must be functional and layout-preserving. Do not introduce new visual systems, copy rewrites, or redesigns while fixing history disabled states, recommendations, training entry, or dashboard goal behavior.
- Every lane final report must list changed files, config item touched, fallback/invalid behavior, tests run, and residual risks.
- A final verifier must run or explicitly classify every required command from the source spec, including secret scan, backend targeted tests, Alembic evidence, backend lint, web typecheck, and frontend targeted Vitest.

## 7. Minimum verification plan

| Domain | Command / check | Expected release interpretation |
| --- | --- | --- |
| Documentation artifact | Parse this matrix and verify the 18 expected issue IDs are unique | Required for Lane 0 completeness. |
| Markdown/text hygiene | `git diff --check` | No whitespace errors in docs. |
| Backend tests | Targeted pytest suites named by implementation lanes plus `tests/unit/test_verification_runner.py` and release-gate tests where present | Changed backend domains must pass; unrelated historical failures must be documented with owners. |
| Backend lint | `cd backend && .venv/bin/python -m ruff check src tests` or narrowed command with documented historical failures | No new diagnostics from changed files. |
| Alembic | `cd backend && alembic heads && alembic current` | Single head or explicit release-blocking migration note. |
| Frontend typecheck | `cd web && npx tsc --noEmit` | Must pass before frontend contract/UI-functional fixes are release-ready. |
| Frontend tests | Relevant Vitest suites for API client, sales combinations, recommendations, history, dashboard config | Changed frontend domains must pass. |
| Secret scan | Repo script/CI gate added by Lane 1 | Committed docs/env examples contain placeholders only. |

## 8. Current task outcome

This worker-3 task is documentation-only and intentionally avoids code changes that overlap the implementation/test lanes. It establishes the Lane 0 matrix, release-blocker order, approval-gated external actions, no-UI-redesign boundary, and verification checklist needed for the rest of the remediation program to proceed without reopening requirements discovery.

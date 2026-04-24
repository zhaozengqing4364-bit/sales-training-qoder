# 2026-04-24 Sales Training Verification / Security Matrix

## Scope

This matrix validates the sales-training trust/governance roadmap against:

- PRD: `.omx/plans/prd-sales-training-roadmap-20260424.md`
- Test spec: `.omx/plans/test-spec-sales-training-roadmap-20260424.md`
- Governance artifacts created for this slice:
  - `docs/adr/2026-04-24-scoring-ruleset-governance.md`
  - `docs/plans/2026-04-24-business-rule-config-admin-plan.md`
  - `docs/plans/2026-04-24-realtime-risk-decomposition-plan.md`

This is a verification/security lane artifact only. It does not change runtime behavior.

## Non-goal Guardrail Result

| Guardrail | Result | Evidence |
| --- | --- | --- |
| No StepFun big rewrite | PASS | Realtime plan allows only contract-first, one-responsibility extraction after payload snapshots. No backend runtime code changed in this lane. |
| No adaptive difficulty enablement | PASS | Adaptive difficulty remains dry-run only in the PRD/test matrix; no feature flag or runtime behavior changed. |
| No external/WeCom sharing enablement | PASS | Sharing remains ADR/planning-only with TTL, revocation, access audit, and desensitization requirements before implementation. |
| No visual redesign/PWA/dark mode | PASS | Only governance/verification markdown files changed. |
| No new dependency without justification | PASS | No package manifest or lockfile changes were made. Backend `uv run` created a local ignored `.venv` only for checks. |

## Permissions Matrix

| Capability | Learner | 教研/运营 | Admin | Supervisor/Coach | Required tests |
| --- | --- | --- | --- | --- | --- |
| View own training report and score explanation | allow own data only | no broad learner data access by default | allow for support/admin workflows | future allow only with explicit authorization | owner-only report access, supervisor overreach denied |
| Create/edit scoring ruleset draft | deny | allow draft/preview | allow draft/preview | deny | non-admin mutation rejected; draft validation |
| Publish/rollback scoring ruleset | deny | deny unless later approval flow grants it | allow | deny | admin-only publish/rollback; audit log written |
| Create/edit business-rule draft | deny | allow for assigned domains | allow | deny | non-admin mutation rejected; domain role checks |
| Publish/rollback business rules | deny | deny unless later approval flow grants it | allow | deny | publish writes actor/before/after/version/reason/trace_id |
| Run ruleset dry-run/preview | deny | allow on sampled historical evidence | allow | deny | preview does not change active version or reports |
| View/share selected highlights | owner-only review list | no access unless explicitly granted | operational access only with audit | future allow only via token/authorization | owner-only CRUD; share token TTL/revocation/access audit/desensitized fields |
| View adaptive difficulty output | own explanation if ever exposed | dry-run dashboard only | dry-run dashboard only | no direct training change | dry-run must not mutate real difficulty |

## Audit Matrix

| Event | Required audit fields | Status in plan | Verification expectation |
| --- | --- | --- | --- |
| scoring ruleset draft create/update | actor, ruleset id/version, before/after draft snapshot, trace_id, reason optional | covered by ADR follow-up | integration test creates draft and asserts audit row |
| scoring ruleset publish | actor, before active, after active, version, reason, trace_id, created_at | covered by ADR decision | publish test asserts full audit envelope |
| scoring ruleset rollback | actor, before active, rollback target, after active, reason, trace_id | covered by ADR follow-up | rollback returns previous published version |
| business-rule publish | actor, key/domain, before_version, after_version, reason, trace_id | covered by admin plan | publish writes `business_rule_config_audit_logs` |
| business-rule preview/dry-run | actor, key/ruleset, sample selector, output summary id, trace_id | covered as no-active-change | preview audit optional for observability; must not mutate active |
| share token access | actor/token id, requester, decision, timestamp, trace_id | deferred by non-goal | required before any external/coach sharing enablement |
| supervisor/coach denied access | requester, target learner/session, denial reason, trace_id | required by Phase 4 tests | overreach test asserts denied and logged |

## Privacy Matrix

| Data surface | Privacy requirement | Validation result |
| --- | --- | --- |
| Reports and trends | Store/display `ruleset_version`, `score_basis`, `evidence_completeness`; do not silently re-score historical reports | PASS in governance plan; implementation tests still required |
| Non-evaluable sessions | Return stable reason instead of fabricated score | PASS in ADR; implementation tests still required |
| Dry-run samples | Sampled output must be internal/admin only and must not rewrite reports or recommendations | PASS in ADR/admin plan; implementation tests still required |
| Highlight sharing | Use minimum payload, explicit TTL, revocation, access audit, and desensitized fields | PASS as deferred requirement; no sharing enabled |
| AI coach notifications | Template/frequency/trigger rules governed centrally; template missing means no send | PASS in admin plan; implementation tests still required |
| Supervisor/coach access | Future access must be explicitly authorized and audited | PASS in matrix; implementation tests still required |

## Test Matrix

| Area | Required coverage from test spec | Current validation status |
| --- | --- | --- |
| Config helper | valid int/choice, invalid env fallback, out-of-range fallback, duplicate helper removed | Planned; backend common tests attempted via `uv run pytest` |
| Business rule config | admin draft, non-admin denied, invalid publish denied, preview no active change, publish audit, rollback, resolver fallback | Covered by admin plan; implementation tests still pending |
| Scoring ruleset | report fields, non-evaluable reason, old report compatibility, dry-run diff | Covered by ADR; implementation tests still pending |
| Rate limiter | memory behavior, session-window gap documented, future Redis atomicity | Not changed by this lane |
| StepFun/realtime | payload snapshot, tool result, KB lock blocked, resume/error fallback, WS status, TTS chunk fixtures | Covered by decomposition plan; no StepFun code changed |
| Frontend combinations/report/practice | service-config render/fallback, owner-only CRUD, hook extraction snapshots, practice status/record/hotkey/mobile | Planned; web test execution blocked by missing dependencies |
| Growth safety | adaptive dry-run no real mutation, share token TTL/revocation/audit/desensitization, AI coach frequency/template, supervisor denied+audit | Guardrailed in this matrix; implementation deferred |

## Verification Commands Run

| Command | Result | Notes |
| --- | --- | --- |
| `git diff --check` | PASS | No whitespace errors in current diff. |
| Markdown structure validation (`python3` headings/content assertions) | PASS | Confirms required docs exist and include guardrail/audit markers. |
| `cd backend && uv run ruff check src tests --quiet` | PASS | Backend lint check succeeded. |
| `pnpm --dir web exec tsc --noEmit --pretty false` | FAIL / environment | Fails because `web/node_modules` is absent and there is no committed pnpm lockfile to safely install deterministically in this lane. Errors are missing modules such as `next`, `react`, `vitest`, `@types/node`. |
| `pnpm --dir web exec vitest run --reporter=dot` | FAIL / environment | `Command "vitest" not found` because `web/node_modules` is absent. |
| `cd backend && .venv-test/bin/python -m pytest tests/unit/common tests/integration -q --no-cov` | FAIL / environment | `.venv-test/bin/python` does not exist in this worktree. |
| `cd backend && uv run pytest tests/unit/common tests/integration -q --no-cov` | FAIL / environment | Collection stopped with 39 import errors from missing test/runtime dependencies including `jwt` and `rank_bm25` in the uv-created environment. |

## Release Gate Recommendation

Do not treat this roadmap as implementation-complete until the implementation lanes add and pass the required tests above. This lane is complete when the governance/security matrix is committed and available checks are reported with environment blockers separated from product/code failures.

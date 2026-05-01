# 2026-05-01 Remediation Team Plan — Lane 0 Matrix and Release Checklist

- Team: `execute-the-remediation-progra`
- Worker: `worker-6`
- Role: `executor`
- Source of truth: `.omx/specs/deep-interview-review-remediation-team-plan.md`
- Scope boundary: coordination artifacts and release checklist only; no product code changes
- Non-goals preserved: approval-gated external actions stay external; no UI redesign
- Backup boundary: do not touch `.omx/preteam-untracked-20260501T033414Z`

## Lane 0 obligations for worker-6

Lane 0 is the coordination lane. Worker-6 owns the following release-prep artifacts:

1. Maintain a single issue-to-lane matrix that maps every review finding exactly once.
2. Keep the blocker order visible: secrets → SSRF/upload/RAG secret → governance bypass → verification runner → contract/runtime gates → lower-governance items.
3. Keep external actions explicitly labeled as approval-gated:
   - real credential rotation
   - remote history cleanup / force-push / repository purge
   - production configuration changes
4. Preserve the no-UI-redesign boundary.
5. Make the release checklist evidence-driven: every lane must have owner, tests, and current status.
6. Produce the final synthesis template for the leader without changing product behavior.

## Issue-to-lane matrix

| Severity | Finding | Owner lane | Scope owner | Write scope | Required evidence / tests | Current status |
| --- | --- | --- | --- | --- | --- | --- |
| CRITICAL | Credential exposure in working tree and history | Lane 1 | Security backend/ops | `.env.example`, docs with sample credentials, secret-scan CI/config/scripts/tests | Secret-scan command, placeholder-only docs/env examples, release note listing required rotations and history cleanup | **approval-gated external remediation pending** |
| HIGH | SSRF / API-key exfiltration in admin model test requests | Lane 2 | Backend security | `backend/src/common/ai/schemas.py`, `backend/src/admin/api/model_configs.py`, centralized URL/policy helper/tests | Reject localhost/private/metadata targets, allowlisted public host success, redacted error body, no redirect leakage | pending |
| HIGH | PPT upload path traversal | Lane 3 | Backend file-safety | `backend/src/admin/api/admin.py`, shared storage/validator helper if needed, tests | Server-generated filenames, extension validation, resolved-path containment, traversal/absolute/nested-path failures | pending |
| HIGH | RAG cross-encoder API key stored in plaintext | Lane 4 | Backend knowledge/security | `backend/src/admin/api/rag_profiles.py`, `backend/src/common/knowledge/rag_profile_*`, encryption helper usage, tests/migration if needed | Plaintext never stored/returned, runtime decrypt only, legacy handling path tested | pending |
| HIGH | Sales-combination governance bypass at learner entry | Lane 5 | Frontend + backend business rules | `web/src/app/(dashboard)/training/sales/page.tsx`, `web/src/lib/api/client.ts`, resolver/tests; backend only if fallback is missing | Active published rules consumed, unavailable-combination fallback, publish/rollback visibility, personalized priority | pending |
| HIGH | Unsafe recommendation links | Lane 6 | Frontend security | new `web/src/lib/routing` / `web/src/lib/recommendations` utility, dashboard/report pages, tests | Absolute/protocol-relative/encoded external paths rejected, safe internal allowlist enforced, fallback to `/training` | pending |
| HIGH | Verification runner runtime errors | Lane 7 | Backend reliability | `backend/src/common/analytics/verification_runner.py`, tests | Import/runtime path fixed, constructor fields aligned, regression tests for missing-doc/docs-error/API-contract/README/deploy/exception paths | pending |
| HIGH | Scoring ruleset governance bypass in report generation | Lane 8 | Backend evaluation | `backend/src/evaluation/services/comprehensive_report.py`, `backend/src/presentation_coach/services/presentation_report_service.py`, scoring metadata/tests | Active/default ruleset applied, report metadata records id/version/source/score basis, legacy fallback observable | pending |
| MEDIUM | API envelope drift | Lane 9 | Frontend API | `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, client contract tests | Domain methods consume unwrapped payloads; double-unwrap callsites removed; contract fixtures pass | pending |
| MEDIUM | Objection-ledger hardcoded rules | Lane 10 | Backend business-rule/config | `backend/src/sales_bot/websocket/components/objection_ledger_helpers.py`, config seed/validator/admin API if available, tests | Central rule source, schema validation, default seed, missing/invalid config fallback, configured override | pending |
| MEDIUM | Production CORS dev origins | Lane 11 | Backend architecture/reliability | `backend/src/app_factory.py`, settings adapter/tests | Dev-only localhost append, production fail-closed when explicit origins missing, credential-safe startup | pending |
| MEDIUM | `main.py` app authority drift | Lane 11 | Backend architecture/reliability | `backend/src/main.py`, `backend/src/router_registry.py` | Single assembly authority, dead duplicate registration neutralized, route inventory test | pending |
| MEDIUM | Startup `create_all` in the wrong environment | Lane 11 | Backend architecture/reliability | `backend/src/common/db/session.py` and startup/tests | Dev/test-only bootstrap, production validates schema instead of silently creating tables | pending |
| MEDIUM | Runtime-status swallowed failures | Lane 11 | Backend architecture/reliability | `backend/src/support/api/runtime_status.py`, tests | Dependency failure becomes `503` or degraded payload with error/trace_id, never empty success | pending |
| MEDIUM | Disabled report link bug | Lane 12 | Frontend functional | dashboard/history pages, frontend config adapter/tests | Disabled state is not wrapped by active `Link`; enabled path still works | pending |
| MEDIUM | Hardcoded weekly growth goal | Lane 12 | Frontend functional | dashboard/history pages, frontend config adapter/tests | Centralized config adapter, integer validation, safe default, fallback logged | pending |
| LOW | Alembic merge / test artifacts not tracked | Lane 13 | Test/build/verifier | tests, migration files if still needed, evidence docs | Single head confirmed, merge migration tracked if required, evidence recorded | pending |
| LOW | WebSocket query-token compatibility mode | Lane 11 | Backend architecture/reliability | WebSocket auth files/tests | Production disabled by default; only dev/explicit config enables query-token compatibility | pending |

## Release checklist

### 1) Critical gate: secrets and history

- [ ] Replace real-looking secrets in committed docs/env examples with placeholders.
- [ ] Run and document the secret-scan command on tracked files.
- [ ] Record external remediation gates for:
  - real credential rotation
  - repository history cleanup / force-push
  - any production secret deletion
- [ ] Verify that no lane claims to perform those external actions in-code.

### 2) High-risk security gates

- [ ] SSRF / model-test endpoint rejects private, loopback, link-local, multicast, unspecified, and metadata targets.
- [ ] PPT uploads use server-generated names and stay inside the upload root.
- [ ] RAG cross-encoder keys are encrypted at rest and redacted in responses.
- [ ] Sales-combination governance is read from the active published rule source.
- [ ] Recommendation links normalize to safe internal routes only.
- [ ] Verification runner no longer fails deterministically at runtime.
- [ ] Scoring ruleset governance is visible in real report output and metadata.

### 3) Medium-risk runtime / contract gates

- [ ] API client callsites consume the unwrapped payload contract consistently.
- [ ] Objection-ledger rules are centrally configured, validated, and defaulted.
- [ ] Production CORS fails closed without explicit origins.
- [ ] App assembly authority is singular and test-covered.
- [ ] Production startup does not silently `create_all`.
- [ ] Runtime-status failure is observable as degraded / `503`.
- [ ] Disabled report links are inert.
- [ ] Weekly growth goal comes from a config adapter with validation.

### 4) Low-risk release hygiene

- [ ] Alembic graph artifacts are tracked or removed with rationale.
- [ ] WebSocket query-token compatibility is off in production unless explicitly enabled.

### 5) Final verification checklist

- [ ] `alembic heads` and `alembic current` show the expected graph state.
- [ ] Backend targeted tests for the changed domains pass.
- [ ] Backend lint/type checks for touched files pass or remaining failures are explicitly classified as pre-existing.
- [ ] Web typecheck and targeted vitest/eslint checks pass for changed frontend domains.
- [ ] Route inventory confirms canonical paths for the critical admin/business/scoring endpoints.
- [ ] Final code-review or security-review is recorded after fixes.

## Final synthesis template for the leader

Use this shape when the leader consolidates the release gate:

```md
## Outcome
- Release status: PASS / FAIL / CONDITIONAL

## Evidence summary
- Secrets gate:
- Security gates:
- Runtime / contract gates:
- Low-risk hygiene:

## External approval-gated actions still required
- 

## Remaining blockers
- 

## Stop condition reached
- 
```

## Notes

- This doc is coordination-only and does not modify runtime behavior.
- Matrix artifact: `docs/audit-remediation/20260501-review-remediation-issue-lane-matrix.md`.
- The matrix covers every supplied review finding exactly once.
- The file intentionally stays inside the allowed handoff/release-checklist scope.

## Verification anchor

- `git status --short` was clean in the worker-6 worktree when this handoff was finalized.
- `.omx/preteam-untracked-20260501T033414Z` was not read or modified.

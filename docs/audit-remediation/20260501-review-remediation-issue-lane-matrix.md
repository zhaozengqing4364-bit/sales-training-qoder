# Review Remediation Issue-to-Lane Matrix

Source of truth: `.omx/specs/deep-interview-review-remediation-team-plan.md` created `20260501T032714Z`.

Boundary decisions preserved:

- External/destructive actions are approval-gated: real credential rotation, remote history rewrite, repository purge, and production setting changes are release gates, not local worker actions.
- No product UI redesign: frontend work is limited to functional repair, safe fallbacks, contract alignment, disabled states, and layout-preserving behavior.
- Workers must not touch `.omx/preteam-untracked-20260501T033414Z`; it is a preteam untracked backup.

## Release-blocker order

1. Secrets and history exposure gates.
2. SSRF/upload/RAG secret security blockers.
3. User-facing governance bypasses and unsafe links.
4. Verification runner and API contract/runtime gates.
5. Lower-risk governance, migration, and management hardening.

## Matrix

| Severity | Finding | Lane | Owner role | Primary files/surfaces | Required tests/evidence | Status |
| --- | --- | ---: | --- | --- | --- | --- |
| CRITICAL | Credential exposure in working tree/history | 1 | security backend/ops | `.env.example`, docs samples, secret scan CI/scripts/tests | Secret scan over tracked env/docs; external rotation/history checklist | approval-gated external + local hygiene pending |
| HIGH | Admin model-config SSRF and API-key exfiltration | 2 | backend security | `backend/src/common/ai/schemas.py`, `backend/src/admin/api/model_configs.py`, URL/policy helper/tests | Unsafe/private/redirect/allowed-host/redaction tests | pending |
| HIGH | PPT upload path traversal | 3 | backend file-safety | `backend/src/admin/api/admin.py`, storage validator/tests | Traversal, absolute/nested path, wrong extension, valid ppt/pptx tests | pending |
| HIGH | RAG cross-encoder API key plaintext storage/response | 4 | backend knowledge/security | `backend/src/admin/api/rag_profiles.py`, `backend/src/common/knowledge/rag_profile_*`, encryption helper/tests | Raw DB encryption, response redaction, runtime decrypt, legacy handling tests | pending |
| HIGH | Sales-combination governance bypass at learning entry | 5 | frontend + backend business-rule | `web/src/app/(dashboard)/training/sales/page.tsx`, `web/src/lib/api/client.ts`, resolver/API tests | Active rule, fallback, missing entities, priority, publish/rollback tests | pending |
| HIGH | Unsafe recommendation `Link` targets | 6 | frontend security | `web/src/lib/routing` or `web/src/lib/recommendations`, dashboard/report pages/tests | Internal route normalization and unsafe fallback tests | pending |
| HIGH | Verification runner deterministic runtime errors | 7 | backend reliability | `backend/src/common/analytics/verification_runner.py`, `backend/tests/unit/test_verification_runner.py` | Missing-doc/docs-error/API-contract/README/deployment/exception paths include `duration_ms`; DB health uses real engine access | in progress by worker-2 |
| HIGH | Scoring ruleset governance bypass in real report paths | 8 | backend evaluation | `backend/src/evaluation/services/comprehensive_report.py`, `backend/src/presentation_coach/services/presentation_report_service.py`, scoring metadata/tests | Active/default/invalid/legacy fallback, metadata/version tests | pending |
| MEDIUM | Frontend API envelope drift/double unwrap | 9 | frontend API | `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, client contract tests | Backend envelope fixtures for RAG profiles/chunking presets and fixed callsites | pending |
| MEDIUM | Objection-ledger hardcoded rules | 10 | backend business-rule/config | `backend/src/sales_bot/websocket/components/objection_ledger_helpers.py`, config adapter/seed/tests | Default/missing/invalid/override tests | pending |
| MEDIUM | Production CORS dev origins | 11 | backend architecture/reliability | `backend/src/app_factory.py`, settings/tests | Dev/test append, prod fail-closed, explicit prod origins tests | pending |
| MEDIUM | `main.py` app authority drift / route inventory | 11 | backend architecture/reliability | `backend/src/main.py`, `backend/src/router_registry.py`, route inventory tests | Critical admin/business/scoring route inventory evidence | pending |
| MEDIUM | Startup `create_all` masks migration gaps | 11 | backend architecture/reliability | `backend/src/common/db/session.py`, startup tests/docs | Prod create_all blocked/validated; dev/test bootstrap preserved | pending |
| MEDIUM | Runtime status swallows failures into healthy unknowns | 11 | backend architecture/reliability | `backend/src/support/api/runtime_status.py`, tests | Healthy and dependency failure -> degraded/503 with trace/error | pending |
| LOW | WebSocket query-token compatibility enabled in prod | 11 | backend architecture/reliability | WebSocket auth settings/boundary/tests | Prod disabled by default; explicit flag/dev enabled tests | pending |
| MEDIUM | Hardcoded dashboard growth goal | 12 | frontend functional | dashboard page/config adapter/tests | Default/missing/invalid/configured goal tests | pending |
| MEDIUM | Disabled history report action remains clickable through parent `Link` | 12 | frontend functional | history page/tests | Disabled action not wrapped/clickable; enabled action still navigates | pending |
| LOW | Alembic merge/test artifacts not tracked or graph unverified | 13 | test/build/verifier | Alembic versions/tests, evidence docs | `alembic heads`, `alembic current`, migration graph test evidence | pending |

## External release gates

| Gate | Required owner/action | Local team action |
| --- | --- | --- |
| Real credential rotation | Authorized operator rotates exposed OpenRouter, StepFun, model encryption, Alibaba OSS, and any newly discovered secrets | Keep placeholders only; document owner/status; do not rotate real keys locally |
| Remote git history cleanup | Authorized maintainer performs repository purge/history rewrite and force-push if approved | Document as approval-gated; do not rewrite remote history locally |
| Production configuration changes | Ops/admin updates production CORS, WebSocket compatibility, provider policies, DNS/network toggles if needed | Implement fail-closed/read adapters/tests; do not change live settings |

## Verification consolidation checklist

- [ ] Secret scan passes on committed files.
- [ ] Backend targeted tests pass for changed domains.
- [ ] Frontend typecheck and targeted Vitest pass for changed domains.
- [ ] Alembic reports a single head or remaining heads are owned with rationale.
- [ ] Route inventory covers critical admin/business/scoring paths.
- [ ] Remaining red checks are labeled pre-existing vs introduced.

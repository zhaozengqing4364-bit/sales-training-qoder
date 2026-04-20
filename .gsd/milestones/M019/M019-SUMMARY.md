---
id: M019
title: "Authority seams 与 release gate 收口"
status: complete
completed_at: 2026-04-13T09:48:58.253Z
key_decisions:
  - D210 — Keep Alembic as schema-evolution authority and keep startup/bootstrap/repair boundaries explicit.
  - D211 — Restrict startup compatibility repairs to development/test; route production-like legacy drift through explicit repair or Alembic.
  - D212 — Introduce `common.services.practice_service` as the first route-facing practice seam bundle.
  - D213 — Keep `practice_service` as a compatibility bundle over `practice_session_service` and `practice_report_service`.
  - D214 — Preserve `SessionEvidenceService` as the canonical completed-session read model.
  - D215 — Keep interrupt transcript cleanup inside `usePracticeWebSocket()` rather than page-level hacks.
  - D216 — Preserve outward `api` / `usePracticeWebSocket()` contracts while extracting inward domain and transport helpers.
  - D217 — Use `backend/requirements.txt` as backend workflow install authority in GitHub Actions.
  - D218 — Reuse the assembled release-truth workflow + docs/route proof bundle as the default downstream release authority.
key_files:
  - backend/src/common/db/session.py
  - backend/src/common/db/legacy_schema_repair.py
  - backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py
  - backend/scripts/repair_legacy_schema.py
  - backend/src/common/api/practice.py
  - backend/src/common/services/practice_service.py
  - backend/src/common/services/practice_session_service.py
  - backend/src/common/services/practice_report_service.py
  - web/src/lib/api/client.ts
  - web/src/lib/api/client-domains.ts
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/websocket/transport.ts
  - .github/workflows/release-truth-gate.yml
  - .github/workflows/nfr-performance-check.yml
  - backend/src/common/api/analytics.py
  - backend/src/common/monitoring/metrics.py
  - backend/src/main.py
  - docs/api-contract/sessions.md
  - docs/api-contract/release-verification.md
  - docs/api-contract/support-runtime.md
lessons_learned:
  - In this repository, milestone close-out must compare code changes against `origin/001-ai-practice-system`, not `main`, or the non-`.gsd` diff gate yields a false failure.
  - When a roadmap only encodes acceptance through slice-overview `After this` outcomes and omits separate Success Criteria / Horizontal Checklist sections, close-out should verify those outcomes directly and record the absence instead of inventing new criteria.
  - Authority-seam milestones are only trustworthy when backend, frontend, workflow, observability, and doc-contract proof are rerun as one assembled acceptance bundle rather than accepted slice by slice.
  - Workflow install commands and router-backed docs parity are authority-bearing release surfaces in this repo; if they drift from `backend/requirements.txt`, `web/package-lock.json`, or live routers, the release gate has drifted even if code tests still pass.
---

# M019: Authority seams 与 release gate 收口

**Closed M019 by turning startup schema repair, practice backend/frontend mega files, and scattered release checks into explicit authority seams backed by one fresh milestone-level verification bundle.**

## What Happened

M019 closed the remaining "authority by folklore" seams across database startup, practice orchestration, frontend transport, and release verification.

S01 moved database truth off implicit startup repair and onto explicit Alembic / repair / bootstrap lanes. `backend/src/common/db/session.py::STARTUP_DB_AUTHORITY`, `backend/src/common/db/legacy_schema_repair.py`, `backend/scripts/repair_legacy_schema.py`, and Alembic revision `20260413_1040_029_explicit_legacy_startup_repairs.py` now make the ownership line executable, and non-development startup fails fast on legacy drift instead of silently mutating schema.

S02 extracted practice backend orchestration out of `backend/src/common/api/practice.py` into a route-facing compatibility bundle plus focused application seams: `practice_session_service.py` for create/lifecycle/runtime-descriptor flow, `practice_report_service.py` for report/audio-audit/audio-segment flow, while `SessionEvidenceService` remains the canonical completed-session read model for replay/history/admin.

S03 repeated the same move on the frontend. `web/src/lib/api/client.ts` stays the sole outward `api` façade and cross-cutting auth/error/trace seam, while `web/src/lib/api/client-domains.ts` now owns extracted runtime-facing domain builders. `usePracticeWebSocket()` remains the outward practice transport/orchestration contract, while `web/src/hooks/websocket/transport.ts` owns URL/queue/backoff/close-reason helpers and interrupt pre-cleanup remains transport-owned.

S04 assembled those seams into one reusable release truth line. `.github/workflows/release-truth-gate.yml` plus `.github/workflows/nfr-performance-check.yml` now align on `web/package-lock.json` and `backend/requirements.txt` install authority; `/metrics` and `/api/v1/analytics/error|performance|custom` are mounted on the live backend path; and `docs/api-contract/sessions.md`, `release-verification.md`, and `support-runtime.md` are rechecked against live router modules while legacy `api-spec.md`, checked-in `openapi.yaml`, and admin-home demo stats remain explicit negative inventory.

Fresh milestone close-out reran the assembled proof instead of trusting slice-local success claims in isolation: S01 startup/bootstrap authority proof passed 4/4; the S02 practice evidence/lifecycle bundle passed 50/50; the combined S03+S04 web seam/release bundle passed 100/100; the S04 backend auth/observability bundle passed 19/19; workflow/install-authority grep proof stayed green; and router-backed `docs/api-contract` parity proof still matched live practice/release-verification/support-runtime modules. Functionally, the milestone now delivers the promised outcome: database evolution no longer hides in startup, practice orchestration no longer lives inside one backend mega file, frontend request/transport logic no longer depends on two mega files as the only source of truth, and release readiness now has a named reusable gate rather than scattered assumptions.

## Decision Re-evaluation

| Decision | Re-evaluation | Verdict | Next milestone action |
| --- | --- | --- | --- |
| D210 — keep Alembic as schema-evolution authority and keep startup/bootstrap/repair split explicit | Fresh S01 authority tests plus workflow/runbook/doc alignment still support this boundary. | Still valid | Revisit only if a future milestone removes the remaining startup `create_all()` bootstrap path. |
| D211 — restrict startup compatibility repairs to development/test and force production-like legacy drift through explicit repair/migration | Fresh 4/4 S01 verification confirms fail-fast non-development startup still holds. | Still valid | Preserve until every remaining legacy compatibility path is fully migrated away. |
| D212 — introduce `practice_service` as the first route-facing seam bundle | The extracted backend services remained route-compatible and the 50-test practice bundle stayed green. | Still valid | Keep the compatibility bundle while later slices narrow internal helpers further. |
| D213 — keep `practice_service` as a compatibility bundle over `practice_session_service` + `practice_report_service` | Fresh backend practice verification shows the compatibility layer still provides the safest route-facing import point. | Still valid | Maintain until downstream callers no longer need the bundle. |
| D214 — preserve `SessionEvidenceService` as the completed-session truth line | Practice/report/replay/history/admin parity stayed green under the fresh 50-test bundle. | Still valid | Continue routing completed-session truth through `SessionEvidenceService`. |
| D215 — keep interrupt transcript cleanup inside `usePracticeWebSocket()` | Fresh websocket/report/replay practice web tests stayed green, so transport-owned cleanup is still the right seam. | Still valid | Preserve unless the outward websocket contract itself changes. |
| D216 — keep outward `api` / `usePracticeWebSocket()` stable while extracting inward domain and transport helpers | Fresh 100-test web bundle confirms the outward contract is still stable while the inward split remains useful. | Still valid | Continue extracting inward helpers without teaching pages to bypass the façade/hook. |
| D217 — use `backend/requirements.txt` as backend workflow install authority | Fresh workflow grep proof confirms both release and NFR workflows still align to the requirements-backed install path. | Still valid | Keep workflow install commands aligned with local/bootstrap reality. |
| D218 — reuse the assembled release-truth workflow + docs/route proof bundle as the default downstream release authority | Fresh workflow, docs, web, and backend observability proof confirms the assembled bundle is now the correct reusable default. | Still valid | Revisit only when a stronger contract source (for example machine-checked generated OpenAPI or a new observability truth surface) is explicitly promoted. |

## Success Criteria Results

The milestone roadmap only exposes acceptance through the slice-overview `After this` outcomes and does not include separate `Success Criteria` or `Horizontal Checklist` sections. Close-out therefore verified those four shipped outcomes directly.

- [x] **数据库演进、bootstrap、兼容补齐的 authority map 落到真实迁移/脚本/测试入口，非开发环境不再靠隐式 schema 修补。**
  - Evidence: S01 shipped `STARTUP_DB_AUTHORITY`, shared legacy repair helpers, the explicit repair script, and Alembic revision `20260413_1040_029_explicit_legacy_startup_repairs.py`.
  - Fresh proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -x -q` passed **4/4**.

- [x] **`practice.py` 不再独自承载会话创建、生命周期、报告、音频审计、runtime descriptor 编排。**
  - Evidence: S02 extracted `backend/src/common/services/practice_service.py`, `practice_session_service.py`, and `practice_report_service.py`, while preserving `SessionEvidenceService` as the canonical completed-session read model.
  - Fresh proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q` passed **50/50**.

- [x] **`client.ts` 按 domain 拆包、`use-practice-websocket.ts` 保留 transport/orchestration outward contract，前端大文件不再是唯一事实源。**
  - Evidence: S03 preserved outward `api` / `usePracticeWebSocket()` while extracting `web/src/lib/api/client-domains.ts` and `web/src/hooks/websocket/transport.ts`.
  - Fresh proof: the combined web verification bundle `npm --prefix web test -- --run "src/lib/api/client.auth.test.ts" "src/lib/api/client-domains.test.ts" "src/lib/api/client-governance.test.ts" "src/hooks/websocket/transport.test.ts" "src/hooks/use-practice-websocket.test.ts" "src/app/(dashboard)/page.test.tsx" "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/components/error-reporting.test.tsx"` passed **100/100**.

- [x] **GitHub Actions、metrics、前端错误上报和 docs/spec contract 形成真实、可检查的 release truth line。**
  - Evidence: S04 aligned `.github/workflows/release-truth-gate.yml` and `.github/workflows/nfr-performance-check.yml` to `package-lock` / `requirements.txt`, kept `/metrics` plus `/api/v1/analytics/*` mounted on the live app, and promoted router-backed `docs/api-contract/*` proof while keeping legacy specs/admin-home demo stats as explicit drift inventory.
  - Fresh proof: workflow/install-authority grep stayed green and rejected `pip install -e .[test]`; router-backed `docs/api-contract` proof still matched live practice/release-verification/support-runtime routers; `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q` passed **19/19**; the combined web bundle above also kept frontend error reporting green.

- Horizontal Checklist: **none present** in `M019-ROADMAP.md`; there were no additional checklist rows to verify.

## Definition of Done Results

- [x] **All slices complete.** `gsd_milestone_status(milestoneId="M019")` reported S01/S02/S03/S04 all `complete`, with **12/12** tasks done across the milestone.
- [x] **All slice summaries exist.** `find .gsd/milestones/M019 -maxdepth 4 \( -name 'M019-ROADMAP.md' -o -name 'S*-SUMMARY.md' -o -name 'T*-SUMMARY.md' \) | sort` confirmed the milestone roadmap, all four slice summaries, and all twelve task summaries are present on disk.
- [x] **Cross-slice integration points work correctly.**
  - S01's database authority split remained coherent under fresh 4/4 startup/bootstrap proof and is the same authority line referenced by runbook/workflow/doc surfaces.
  - S02's backend extraction and S03's frontend seam split still assemble into the current learner/report/replay contracts: the fresh backend practice bundle passed **50/50** and the fresh frontend bundle passed **100/100** across login/dashboard/practice/report/replay/websocket/API seams.
  - S03's frontend error-reporting seam and S04's backend analytics/metrics seam still assemble into one release-truth line: the fresh web bundle kept `ErrorBoundary` reporting green and the fresh backend observability bundle passed **19/19**.
  - Workflow/install-authority and router-backed docs parity grep proofs stayed green, so the release gate still checks named repo-root surfaces instead of relying on scattered file folklore.
- [x] **Code-change gate passed.** This repository does not use `main` as the live integration branch, so close-out used the repository-equivalent diff against `origin/001-ai-practice-system`; that non-`.gsd` diff returned many real code/document changes, so M019 did not collapse into planning-only output.

## Requirement Outcomes

No requirement status transitions occurred in M019.

- Fresh repository check: `rg -n "M019" .gsd/REQUIREMENTS.md` returned **no M019 requirement mappings**.
- Slice evidence: S01, S02, S03, and S04 summaries all explicitly reported **no requirements advanced, validated, invalidated, or re-scoped**.
- Close-out verdict: no `gsd_requirement_update` calls were needed because the milestone delivered structural authority seams and release-gate closure without changing requirement status in the canonical requirements registry.

## Deviations

None beyond the already-recorded slice-local adaptations: S04 primarily aligned and proved pre-existing live observability/workflow surfaces instead of inventing a second release model, and milestone close-out used the repository's real integration branch (`origin/001-ai-practice-system`) because `main` is not present here.

## Follow-ups

- Reuse the M019 assembled release bundle by default in M020-M022 instead of inventing a second release authority path.
- If a future milestone narrows or removes startup `create_all()` / compatibility bootstrap further, do it from the explicit S01 authority map rather than reopening implicit startup repair.
- Continue extracting remaining inline façade domains from `web/src/lib/api/client.ts` only while preserving the outward `api` contract.
- Replace the current router-backed `docs/api-contract` proof with machine-checked generated OpenAPI only by promoting a new single authority bundle, not by running two competing contract truths in parallel.
- Truthify or explicitly replace the admin-home demo metrics surface before any manager/admin dashboard is promoted into release authority.

---
id: S04
parent: M019
milestone: M019
provides:
  - A reusable repo-root release gate that checks workflow install authority, web/backend focused proof, and doc/spec drift together.
  - A truthful observability baseline covering mounted `/metrics` plus frontend analytics/error beacon acceptance on live backend routes.
  - A downstream rule that keeps `docs/api-contract` as the current contract authority while leaving legacy specs and admin-home demo stats in explicit drift inventory.
  - A shared verification bundle that M020-M022 can reuse without rediscovering which release surfaces are actually live.
requires:
  []
affects:
  - M020
  - M021
  - M022
key_files:
  - .github/workflows/release-truth-gate.yml
  - .github/workflows/nfr-performance-check.yml
  - web/src/components/ErrorBoundary.tsx
  - backend/src/common/api/analytics.py
  - backend/src/common/monitoring/metrics.py
  - backend/src/main.py
  - docs/api-contract/sessions.md
  - docs/api-contract/release-verification.md
  - docs/api-contract/support-runtime.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D217 — use backend/requirements.txt as the backend dependency install authority in GitHub Actions via per-job virtualenvs.
  - D218 — reuse the assembled release-truth workflow bundle plus router-backed doc/spec drift proof as the default release authority for M020-M022 until a new surface is explicitly promoted.
patterns_established:
  - Assemble one release gate from multiple truthful repo-root surfaces instead of trusting a single workflow file.
  - Treat CI dependency-install commands as authority-bearing behavior and review them like code-contract drift.
  - Use router-backed doc-contract inventory proof until generated OpenAPI becomes the actual checked authority.
  - Keep explicit negative inventory for legacy specs and demo-only dashboard stats so they cannot silently re-enter release authority.
observability_surfaces:
  - `/metrics` export mounted in `backend/src/main.py` via `get_metrics()` and `MetricsMiddleware`.
  - `/api/v1/analytics/error`, `/api/v1/analytics/performance`, and `/api/v1/analytics/custom` backend sinks in `backend/src/common/api/analytics.py`.
  - Focused verification in `backend/tests/integration/test_observability_surfaces.py` and `src/components/error-reporting.test.tsx`.
  - Architecture/plan writeback in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` and `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` for downstream release-gate reuse.
drill_down_paths:
  - .gsd/milestones/M019/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M019/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M019/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T09:12:31.225Z
blocker_discovered: false
---

# S04: Release gate / metrics / doc-contract truth line 收口

**Closed S04 by turning CI, observability, and docs/spec checks into one reusable assembled release gate backed by requirements-authority installs, live `/metrics` and `/api/v1/analytics/*` sinks, and explicit drift inventory for legacy specs plus admin-home demo stats.**

## What Happened

# S04: Release gate / metrics / doc-contract truth line 收口

**Turned workflow checks, frontend error reporting, backend metrics export, and docs/spec drift proof into one explicit release-truth bundle instead of scattered file-level assumptions.**

## What Happened

## Delivered
- Kept `.github/workflows/release-truth-gate.yml` as the assembled repo-root release authority and aligned `.github/workflows/nfr-performance-check.yml` to the same backend install truth line: `backend/requirements.txt` via per-job virtualenvs, not editable installs from undefined `pyproject` extras.
- Confirmed the frontend error-reporting seam is now live end to end: `web/src/components/ErrorBoundary.tsx` posts to `/api/v1/analytics/error`, `web/src/lib/performance.ts` posts performance/custom beacons, and `backend/src/common/api/analytics.py` accepts those payloads on mounted backend routes.
- Confirmed backend observability is on the live authority line: `backend/src/common/monitoring/metrics.py` remains the shared metrics sink, `MetricsMiddleware` is mounted in `backend/src/main.py`, and `/metrics` is exported on the running FastAPI app.
- Promoted `docs/api-contract/*` to the current doc-contract truth surface only through explicit repo-root drift proof against live router modules, while keeping `api-spec.md` and `specs/001-ai-practice-system/contracts/openapi.yaml` as negative inventory / drift artifacts instead of pretending they are current authority.
- Wrote the downstream reuse rule into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` and `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`: M020-M022 should reuse the same assembled release bundle unless they deliberately promote a new authority surface.
- Carried the admin-home truthfulness gap forward explicitly: `web/src/app/admin/page.tsx` still mixes live top-card calls with hardcoded dashboard numbers, so it is an M022 truth-surface input, not part of the release gate.

## What This Slice Actually Changed
- Release validation is no longer “whichever workflow happens to be green.” The release authority is now the combination of:
  1. `.github/workflows/release-truth-gate.yml`
  2. `.github/workflows/nfr-performance-check.yml`
  3. live backend observability routes (`/metrics`, `/api/v1/analytics/error|performance|custom`)
  4. repo-root `docs/api-contract` vs live-router drift proof
  5. explicit negative inventory proof for legacy specs and admin-home demo stats
- `backend/requirements.txt` is now the durable backend install authority for both release and NFR CI paths.
- `docs/api-contract/sessions.md`, `docs/api-contract/release-verification.md`, and `docs/api-contract/support-runtime.md` are the currently trusted contract surfaces because they are rechecked against live router modules.
- `api-spec.md` and `specs/001-ai-practice-system/contracts/openapi.yaml` stay in the repository as useful drift detectors, but not as release authority.

## Patterns Established
- Assemble one release gate from multiple truthful surfaces instead of treating a single workflow file as the whole truth.
- Treat workflow dependency installs as authority-bearing behavior; CI drift counts as release-truth drift.
- Use router-backed grep proof for doc contracts when generated OpenAPI is not yet the source of truth.
- Keep explicit negative inventory for legacy or demo-only surfaces so they cannot silently re-enter authority status.

## Downstream Guidance
- M020-M022 should start from the existing repo-root release bundle before inventing any new verification path.
- If future work changes frontend analytics/error beacons, update the backend sink routes, observability tests, workflow bundle, and architecture writeback together.
- If future work promotes generated OpenAPI or another contract source into authority, it must replace the whole doc/spec proof bundle, not sit beside it as a competing truth line.
- Do not treat `backend/src/main.py` top-level route comments or `web/src/app/admin/page.tsx` dashboard cards as release authority without fresh repo-root proof.

## Operational Readiness
- **Health signal:** fresh repo-root verification is green for the web login + error-reporting gate, the backend auth + observability gate, the workflow/install-authority greps, and the `docs/api-contract` vs live-router drift proof.
- **Failure signal:** release-truth regressions will usually show up as one of four symptoms: a workflow falls back to the wrong install authority, `/metrics` or `/api/v1/analytics/*` stops being mounted or accepted, `docs/api-contract` stops matching live practice/release-verification/support-runtime routes, or legacy/admin-home surfaces start being treated as authority without proof.
- **Recovery procedure:** restore the matching workflow install path, re-mount or rewire the missing backend sink, update the router-backed doc-contract inventory, then rerun the S04 repo-root bundle (`npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"`, `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q`, and the three repo-root `rg` proofs recorded in the architecture scan/plan).
- **Monitoring gaps:** current proof stops at beacon acceptance + Prometheus export. There is still no durable Sentry aggregation, alert routing, or trustworthy admin dashboard observability surface; admin-home demo stats remain intentionally out of the release gate.

## Verification

Fresh slice-close verification passed all planned repo-root gates:
- `rg -n "analytics/error|metrics|openapi|api-contract|pip install -e|requirements.txt|package-lock" .github/workflows web/src/components/ErrorBoundary.tsx backend/src/common/monitoring/metrics.py api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml docs/api-contract` matched the current workflow/install/metrics/spec surfaces.
- `rg -n "npm --prefix web|backend/venv/bin/python -m pytest|requirements.txt|package-lock|metrics|analytics/error" .github/workflows` plus a negative grep for `pip install -e .[test]` reconfirmed both workflows are aligned to the repo’s current dependency authority.
- `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"` passed 8/8 tests.
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q` passed 19/19 tests.
- `rg -n "release gate|metrics|error reporting|doc contract|repo-root" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` kept the downstream reuse rule grep-discoverable.
- `rg -n "/practice/sessions|/admin/release-verification|/support/runtime" docs/api-contract backend/src/common/api/practice.py backend/src/admin/api/release_verification.py backend/src/support/api/runtime_status.py` proved the current doc-contract authority still matches live route modules.

Fresh LSP diagnostics on `web/src/components/ErrorBoundary.tsx`, `backend/src/common/api/analytics.py`, `backend/src/common/monitoring/metrics.py`, and `backend/src/main.py` all returned no diagnostics. The backend pytest gate still emitted the already-known local Python 3.14 coverage noise (`Module src was never imported` / `No data was collected`) plus existing dependency deprecation warnings, but the gate exited 0 and all focused auth/observability tests passed.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor local adaptation only: the live release-truth workflow, backend metrics export, and analytics sink routes were already present in the workspace before close-out, so S04 focused on removing remaining workflow-authority drift, proving the live surfaces end to end, and locking the downstream reuse rule rather than inventing a second release model.

## Known Limitations

`docs/api-contract` is still enforced through inventory-style repo-root proof, not machine-generated OpenAPI parity. `api-spec.md` and the checked-in `openapi.yaml` still drift and are intentionally left as negative inventory. `web/src/app/admin/page.tsx` still mixes live top-card metrics with hardcoded numbers (`2,543`, `84`, `42%`, `68%`, `75%`, `450 GB`) and static alert/log copy, so the admin home remains untrustworthy as an observability surface.

## Follow-ups

M019 milestone validation should now treat the S04 bundle as the close-out release authority. M020-M022 should reuse the same repo-root release-truth commands by default. M022/S03 should truthify or explicitly replace the admin-home fake metrics surface before any manager/admin dashboard is promoted into release authority. A future contract slice can replace the current router-backed docs proof with machine-checked generated OpenAPI, but only by replacing the full authority bundle.

## Files Created/Modified

- `.github/workflows/release-truth-gate.yml` — remains the assembled repo-root release authority for web/backend/doc/spec verification.
- `.github/workflows/nfr-performance-check.yml` — now uses `backend/requirements.txt`-backed virtualenv installs instead of editable-install drift.
- `web/src/components/ErrorBoundary.tsx` — keeps the frontend route-error beacon on `/api/v1/analytics/error`.
- `backend/src/common/api/analytics.py` — provides the live backend sinks for frontend error/performance/custom analytics beacons.
- `backend/src/common/monitoring/metrics.py` — remains the shared Prometheus/request/frontend-analytics metrics sink.
- `backend/src/main.py` — mounts `MetricsMiddleware`, `/metrics`, and the analytics/support/release-verification routers on the live app authority line.
- `docs/api-contract/sessions.md` — remains the current practice-session contract authority surface.
- `docs/api-contract/release-verification.md` — remains the current admin release-verification contract authority surface.
- `docs/api-contract/support-runtime.md` — remains the current support runtime contract authority surface.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — records the assembled release gate, negative inventory surfaces, and downstream reuse rule.
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` — tells downstream milestones to reuse the S04 bundle by default.
- `.gsd/KNOWLEDGE.md` — records the workflow/install-authority and doc-contract drift gotchas.
- `.gsd/DECISIONS.md` — records D217 and D218 for workflow install authority and the default downstream release bundle.

## Verification

Fresh slice-close verification passed from repo root: workflow/install-authority grep proofs stayed green; `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"` passed 8/8; `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q` passed 19/19; the architecture-scan/plan release-gate grep remained present; the router-backed `docs/api-contract` drift proof still matched live practice/release-verification/support-runtime modules; and fresh LSP diagnostics on the touched TS/Python authority files returned no diagnostics.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor local adaptation only: the live release workflow and observability routes already existed before close-out, so the slice focused on removing remaining workflow-authority drift, proving the live surfaces, and freezing the downstream reuse rule rather than rebuilding those surfaces from scratch.

## Known Limitations

`docs/api-contract` still relies on inventory-style router-backed proof rather than machine-generated OpenAPI parity. `api-spec.md` and `specs/001-ai-practice-system/contracts/openapi.yaml` are still drift artifacts. `web/src/app/admin/page.tsx` still contains mixed live and hardcoded dashboard numbers, so it remains excluded from release authority.

## Follow-ups

Use the S04 repo-root release bundle as the milestone-close validation authority. Carry the admin-home demo-stat truthfulness gap into M022/S03. Replace the current docs/spec inventory proof with machine-checked generated OpenAPI only if the full bundle is promoted together.

## Files Created/Modified

- `.github/workflows/release-truth-gate.yml` — Assembled repo-root release workflow for web/backend/doc/spec verification.
- `.github/workflows/nfr-performance-check.yml` — Aligned the NFR companion workflow to `backend/requirements.txt`-backed virtualenv installs.
- `web/src/components/ErrorBoundary.tsx` — Keeps frontend route errors posting to the backend analytics/error sink.
- `backend/src/common/api/analytics.py` — Accepts frontend error/performance/custom analytics beacons on live backend routes.
- `backend/src/common/monitoring/metrics.py` — Provides Prometheus/request/frontend-analytics metrics collection helpers.
- `backend/src/main.py` — Mounts `MetricsMiddleware`, `/metrics`, and the analytics/support/release-verification routers.
- `docs/api-contract/sessions.md` — Documents the current practice-session contract authority surface.
- `docs/api-contract/release-verification.md` — Documents the current admin release-verification contract authority surface.
- `docs/api-contract/support-runtime.md` — Documents the current support-runtime contract authority surface.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Records the assembled release gate, negative inventory surfaces, and downstream reuse rule.
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` — Carries the S04 release bundle forward as the default verification contract for later milestones.
- `.gsd/KNOWLEDGE.md` — Captures workflow/install-authority and doc-contract drift gotchas for future agents.
- `.gsd/DECISIONS.md` — Records D217 and D218 for workflow authority and downstream release-bundle reuse.

# S04: Release gate / metrics / doc-contract truth line 收口 — UAT

**Milestone:** M019
**Written:** 2026-04-13T09:12:31.225Z

# S04 UAT — Release gate / metrics / doc-contract truth line 收口

## Preconditions
1. Repository is at the M019/S04 close-out state.
2. Run every command from repo root: `/Users/zhaozengqing/github/销售训练qoder`.
3. Frontend dependencies are installed under `web/node_modules` and backend dependencies are installed in `backend/venv`.
4. Do not substitute older workflow files, `api-spec.md`, or checked-in `openapi.yaml` for the live release gate during this UAT.

## Test Case 1 — Workflow authority matches the current repo install truth
**Goal:** confirm both release workflows use the same dependency authority that the repository actually ships.

1. Run:
   - `rg -n "npm --prefix web|backend/venv/bin/python -m pytest|requirements.txt|package-lock|metrics|analytics/error" .github/workflows`
2. Run:
   - `! rg -n "pip install -e \.\[test\]" .github/workflows/nfr-performance-check.yml`
3. Open `.github/workflows/release-truth-gate.yml` and `.github/workflows/nfr-performance-check.yml`.

**Expected outcomes**
- `release-truth-gate.yml` references `web/package-lock.json` and `backend/requirements.txt` as install authority inputs.
- `nfr-performance-check.yml` also installs backend dependencies from `backend/requirements.txt` via a job-local virtualenv.
- No remaining editable-install command (`pip install -e .[test]`) appears in the NFR workflow.

## Test Case 2 — Frontend error reporting and backend observability sinks are truly connected
**Goal:** confirm the frontend error boundary and backend observability routes still form one live truth line.

1. Run:
   - `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"`
2. Run:
   - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q`
3. Inspect the relevant code paths if needed:
   - `web/src/components/ErrorBoundary.tsx`
   - `backend/src/common/api/analytics.py`
   - `backend/src/main.py`

**Expected outcomes**
- The web suite passes and proves `ErrorBoundary` still posts to `/api/v1/analytics/error`.
- The backend suite passes and proves `/metrics` and `/api/v1/analytics/error|performance|custom` are mounted and accept requests.
- No verification step depends on a mock-only or dead backend route.

## Test Case 3 — `docs/api-contract` still matches live practice/support/release-verification routes
**Goal:** confirm the current contract authority is tied to live router modules, not memory.

1. Run:
   - `rg -n "/api/v1/practice/sessions|/api/v1/admin/release-verification|/api/v1/support/runtime" docs/api-contract`
2. Run:
   - `rg -n "/practice/sessions|/admin/release-verification|/support/runtime" docs/api-contract backend/src/common/api/practice.py backend/src/admin/api/release_verification.py backend/src/support/api/runtime_status.py`
3. Review `docs/api-contract/sessions.md`, `docs/api-contract/release-verification.md`, and `docs/api-contract/support-runtime.md` only if the grep proof fails.

**Expected outcomes**
- The doc-contract grep succeeds.
- The live router grep succeeds and matches the same practice, release-verification, and support-runtime families described in `docs/api-contract`.
- The current contract authority remains the docs + live-router inventory proof, not the legacy spec files.

## Test Case 4 — Legacy specs and admin-home demo stats remain explicit negative inventory
**Goal:** ensure drift surfaces stay visible instead of quietly re-entering release authority.

1. Run:
   - `rg -n "/auth/wechat|POST /api/v1/sessions" api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml`
2. Run:
   - `rg -n "api.internal.health|api.analyticsOpen.getDashboard|2,543|84|42%|68%|75%|450 GB" web/src/app/admin/page.tsx`
3. Run:
   - `rg -n "release gate|metrics|error reporting|doc contract|repo-root" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md`

**Expected outcomes**
- The legacy spec grep shows old surfaces such as `/auth/wechat` or `POST /api/v1/sessions`, proving those files are still drift inventory.
- The admin page grep shows the known mixed truth surface (live top cards plus hardcoded numbers), proving it is still excluded from release authority.
- The architecture scan and plan grep show the downstream reuse rule so future milestones know to start from this assembled bundle.

## Edge Cases
- If the web tests pass but the backend observability suite fails, treat it as a broken backend sink or `/metrics` mount, not as proof that the frontend beacon is healthy.
- If `docs/api-contract` grep passes but live-router grep fails, treat it as contract drift; do not close the slice on document-only success.
- If legacy spec files stop matching the negative-inventory grep, review whether they were intentionally promoted into authority. If not, the drift proof itself has rotted and must be restored before release closure.
- If admin-home hardcoded numbers disappear, verify they were actually replaced with trustworthy live data before promoting the page into any release or observability gate.

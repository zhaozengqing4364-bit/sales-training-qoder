---
id: T02
parent: S04
milestone: M019
key_files:
  - .github/workflows/nfr-performance-check.yml
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Recorded D217: GitHub Actions should use `backend/requirements.txt` as the backend install authority via per-job virtualenvs instead of `pip install -e .[test]`.
duration: 
verification_result: passed
completed_at: 2026-04-13T08:46:55.053Z
blocker_discovered: false
---

# T02: Aligned the release/NFR workflow authority line to backend requirements installs and reverified the live metrics and frontend error-reporting gates.

**Aligned the release/NFR workflow authority line to backend requirements installs and reverified the live metrics and frontend error-reporting gates.**

## What Happened

I executed T02 against local repo reality rather than the older inventory snapshot. The current workspace already had the new `release-truth-gate.yml`, a mounted `/metrics` export in `backend/src/main.py`, backend analytics sinks in `backend/src/common/api/analytics.py`, and frontend beacon posting in `web/src/components/ErrorBoundary.tsx`, so I did not duplicate or replace those live seams. The remaining truth-line drift was the older `.github/workflows/nfr-performance-check.yml`, which still installed backend dependencies via `pip install -e .[test]` even though `backend/requirements.txt` is the repo’s install authority and `backend/pyproject.toml` does not define a `test` extra. I rewrote that workflow to use cached Python setup keyed by `backend/requirements.txt`/`backend/pyproject.toml`, create a per-job virtualenv, install from `requirements.txt`, and run migrations/tests/report generation through that venv. After that, I revalidated the focused web login + error-reporting tests and the backend auth + observability tests, and I updated `.gsd/KNOWLEDGE.md` so future agents do not assume the release truth is connected just because the newest workflow file looks correct while an older workflow still drifts.

## Verification

I first ran the task-plan repo-root gate and confirmed the existing release-truth workflow, focused web login test, and focused backend auth test all passed. After tightening `.github/workflows/nfr-performance-check.yml`, I reran the workflow authority grep to prove both workflows now point at `web/package-lock.json` / `backend/requirements.txt` and that the old editable-install path is gone from the NFR workflow. I then ran `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"`, which passed 8/8 tests and proved the frontend error boundary still posts to `/api/v1/analytics/error`. Finally, I ran `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q`, which passed 19/19 tests and reconfirmed the login surface plus `/metrics` and `/api/v1/analytics/*` observability sinks. Local backend pytest still emits coverage warnings under the existing Python 3.14 venv, but the test outcomes were green and CI remains pinned to Python 3.11 in the workflow.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "npm --prefix web|backend/venv/bin/python -m pytest|requirements.txt|package-lock|metrics|analytics/error" .github/workflows && ! rg -n "pip install -e \\.\\[test\\]" .github/workflows/nfr-performance-check.yml && rg -n "venv/bin/pip install -r requirements.txt|venv/bin/python -m pytest|cache-dependency-path" .github/workflows/nfr-performance-check.yml` | 0 | ✅ pass | 6500ms |
| 2 | `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/components/error-reporting.test.tsx"` | 0 | ✅ pass | 6500ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_observability_surfaces.py -x -q` | 0 | ✅ pass | 6500ms |

## Deviations

Minor local adaptation: the release-truth gate workflow and the live backend/frontend observability seams were already present in the workspace before T02 execution, so I focused this task on removing the remaining drift in the legacy NFR workflow and on revalidating the already-wired surfaces instead of recreating those routes/components.

## Known Issues

Local repo-root backend pytest under `backend/venv` (Python 3.14.3) still emits coverage warnings (`Module src was never imported` / `No data was collected`) even though the focused auth and observability tests pass. The workflow itself is pinned to Python 3.11, so this remains a local environment hygiene issue rather than a T02 release-gate blocker.

## Files Created/Modified

- `.github/workflows/nfr-performance-check.yml`
- `.gsd/KNOWLEDGE.md`

---
id: T02
parent: S01
milestone: M005
provides: []
requires: []
affects: []
key_files: ["web/src/app/admin/analytics/page.tsx", "web/src/app/admin/analytics/page.test.tsx", "web/src/lib/api/types.ts", "web/src/lib/api/client.ts"]
key_decisions: ["Kept the current admin analytics route and charts, but replaced generic wording with projection/evidence semantics instead of building a second dashboard.", "Normalized admin analytics payloads in the web client so evaluability, issue-family, and leaderboard projection metadata arrive with stable defaults before rendering."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan page regression `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'` and both focused render tests passed. Reran the failing repo-root backend gate exactly as reported by auto-mode with `venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py`; all 27 backend tests passed, confirming the projection-backed admin analytics/user API contract remained green while clearing the gate failure."
completed_at: 2026-03-26T06:10:47.478Z
blocker_discovered: false
---

# T02: Reframed the existing admin analytics page around projection-backed evaluability, issue families, and next-goal evidence language.

> Reframed the existing admin analytics page around projection-backed evaluability, issue families, and next-goal evidence language.

## What Happened
---
id: T02
parent: S01
milestone: M005
key_files:
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/analytics/page.test.tsx
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
key_decisions:
  - Kept the current admin analytics route and charts, but replaced generic wording with projection/evidence semantics instead of building a second dashboard.
  - Normalized admin analytics payloads in the web client so evaluability, issue-family, and leaderboard projection metadata arrive with stable defaults before rendering.
duration: ""
verification_result: passed
completed_at: 2026-03-26T06:10:47.480Z
blocker_discovered: false
---

# T02: Reframed the existing admin analytics page around projection-backed evaluability, issue families, and next-goal evidence language.

**Reframed the existing admin analytics page around projection-backed evaluability, issue families, and next-goal evidence language.**

## What Happened

Updated the current /admin/analytics page so it uses the same evidence semantics as learner and supervisor surfaces. The page now explains the score basis explicitly, separates evaluable and not-evaluable sessions, surfaces repeated issue families, highlights the dominant evidence-insufficient reason, and shows repeated next-goal language plus leaderboard issue/goal context without creating a second dashboard. I also extended the web-side admin analytics types and normalized admin analytics client payloads so overview, trends, agents, and leaderboard responses carry the projection-backed fields with stable defaults before rendering. Finally, I repaired the local repo-root verification path by restoring Homebrew python@3.11 and routing venv/bin/python to the healthy backend venv because the auto gate invokes that literal path in this workspace.

## Verification

Ran the task-plan page regression `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'` and both focused render tests passed. Reran the failing repo-root backend gate exactly as reported by auto-mode with `venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py`; all 27 backend tests passed, confirming the projection-backed admin analytics/user API contract remained green while clearing the gate failure.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/admin/analytics/page.test.tsx'` | 0 | ✅ pass | 727ms |
| 2 | `venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py` | 0 | ✅ pass | 4040ms |


## Deviations

Also repaired the local repo-root `venv/bin/python` execution path after the auto gate exposed a broken root Python 3.13 environment in this workspace. This was a verification-environment repair, not a product-behavior change.

## Known Issues

No known shipped UI issue remains from this task. The repo-root `venv/bin/python3.13` environment itself is still not trustworthy if invoked directly; use the repo-root `venv/bin/python` wrapper or the backend venv path for backend verification in this workspace.

## Files Created/Modified

- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/analytics/page.test.tsx`
- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`


## Deviations
Also repaired the local repo-root `venv/bin/python` execution path after the auto gate exposed a broken root Python 3.13 environment in this workspace. This was a verification-environment repair, not a product-behavior change.

## Known Issues
No known shipped UI issue remains from this task. The repo-root `venv/bin/python3.13` environment itself is still not trustworthy if invoked directly; use the repo-root `venv/bin/python` wrapper or the backend venv path for backend verification in this workspace.

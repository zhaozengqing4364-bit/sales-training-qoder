---
id: T01
parent: S02
milestone: M013
provides: []
requires: []
affects: []
key_files: ["docs/plans/2026-04-08-system-audit-remediation-plan.md", ".gsd/milestones/M013/slices/S02/tasks/T01-SUMMARY.md"]
key_decisions: ["Reused the smallest existing focused web/backend suites per surface instead of inventing new umbrella regression commands."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Confirmed that every documented test target referenced by the new matrix exists at the repo-root paths used in the plan, including the hook-based .test.ts suites used for lifecycle/websocket/profile-state coverage. Ran the task-plan verification command to prove the remediation plan now contains repo-root web and backend focused commands."
completed_at: 2026-04-09T16:57:45.768Z
blocker_discovered: false
---

# T01: Added a repo-root focused verification matrix to the audit remediation plan so later repair slices can reuse real web/backend commands by surface.

> Added a repo-root focused verification matrix to the audit remediation plan so later repair slices can reuse real web/backend commands by surface.

## What Happened
---
id: T01
parent: S02
milestone: M013
key_files:
  - docs/plans/2026-04-08-system-audit-remediation-plan.md
  - .gsd/milestones/M013/slices/S02/tasks/T01-SUMMARY.md
key_decisions:
  - Reused the smallest existing focused web/backend suites per surface instead of inventing new umbrella regression commands.
duration: ""
verification_result: passed
completed_at: 2026-04-09T16:57:45.769Z
blocker_discovered: false
---

# T01: Added a repo-root focused verification matrix to the audit remediation plan so later repair slices can reuse real web/backend commands by surface.

**Added a repo-root focused verification matrix to the audit remediation plan so later repair slices can reuse real web/backend commands by surface.**

## What Happened

Reviewed the slice/task contract plus the current remediation plan, inspected the existing focused web and backend test inventory, and sampled the relevant suites by declared subject to confirm the surfaces were real. Updated docs/plans/2026-04-08-system-audit-remediation-plan.md with a new inventory section that maps auth, dashboard, history, profile, practice, lifecycle, websocket, and admin to repo-root runnable commands, then added reuse guidance so downstream repair slices can pick the smallest matching command instead of inventing broader umbrella suites.

## Verification

Confirmed that every documented test target referenced by the new matrix exists at the repo-root paths used in the plan, including the hook-based .test.ts suites used for lifecycle/websocket/profile-state coverage. Ran the task-plan verification command to prove the remediation plan now contains repo-root web and backend focused commands.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 - <<'PY' ... Path(...).exists() ... PY` | 0 | ✅ pass | 40ms |
| 2 | `rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" docs/plans/2026-04-08-system-audit-remediation-plan.md` | 0 | ✅ pass | 36ms |


## Deviations

Minor local adaptation only: beyond the planned web/src/**/*.test.tsx inputs, I also inventoried existing web/src/**/*.test.ts hook suites where they are the live focused seams for lifecycle, websocket, and profile-state verification.

## Known Issues

There are still no dedicated backend-focused suites that map only to the dashboard or profile surfaces; those rows remain web-led today, while backend auth/history/practice/lifecycle/admin suites cover the server-side seams most likely to pair with them in later repair slices.

## Files Created/Modified

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/milestones/M013/slices/S02/tasks/T01-SUMMARY.md`


## Deviations
Minor local adaptation only: beyond the planned web/src/**/*.test.tsx inputs, I also inventoried existing web/src/**/*.test.ts hook suites where they are the live focused seams for lifecycle, websocket, and profile-state verification.

## Known Issues
There are still no dedicated backend-focused suites that map only to the dashboard or profile surfaces; those rows remain web-led today, while backend auth/history/practice/lifecycle/admin suites cover the server-side seams most likely to pair with them in later repair slices.

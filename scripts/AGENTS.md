# scripts/ — Repo-Level Operations

## Overview

Root scripts operate across backend, frontend, local infra, smoke gates, secrets, and recovery drills.

## Where to Look

| Need | Location | Notes |
|------|----------|-------|
| Script catalog | `README.md` | Update when adding or changing a public script entry. |
| Local dev stack | `dev-up.sh`, `dev-stop.sh` | Own ports 3444/3445 and optional local infra cleanup. |
| Smoke stack | `dev-smoke-up.sh`, `dev-smoke-stop.sh` | Used by Playwright global setup/teardown. |
| Full gate | `critical-quality-gate.sh` | Canonical local/CI quality sequence. |
| Frontend test proxy | `run-vitest-root.mjs` | Root `npm test` delegates into `web/`. |
| Secrets / dependency checks | `secret-scan.sh`, `check_secret_hygiene.py`, `dependency-governance.sh` | Never weaken checks to pass a feature task. |
| Recovery drills | `recovery-drill-*.py`, `recovery_drill_*.py` | Keep paired CLI names intentional if both exist. |

## Conventions

- Shell scripts must be runnable from repo root unless the script documents otherwise.
- Prefer env vars for ports and credentials; never bake secrets into scripts.
- Destructive cleanup needs an explicit env switch or narrowly documented target.
- Scripts that start services should have a matching stop/teardown path.
- If a script becomes a required workflow, update `README.md` and parent docs.

## Anti-Patterns

- Do not add a second quality gate when `critical-quality-gate.sh` can be extended.
- Do not silently kill broad port ranges or user-owned services.
- Do not hide failing subprocesses with `|| true` unless the failure is intentionally non-blocking and documented.

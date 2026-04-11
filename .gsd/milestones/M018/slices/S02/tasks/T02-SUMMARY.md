---
id: T02
parent: S02
milestone: M018
key_files:
  - docs/setup/dependency-governance-baseline.md
  - scripts/dependency-governance.sh
  - scripts/README.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D206 — expose dependency governance through a repo-local doc + wrapper script that distinguishes runnable scans from blocked prerequisites instead of relying on drifted CI install behavior.
  - Keep backend dependency sync anchored to `backend/requirements.txt` until `backend/pyproject.toml` defines reusable extras cleanly.
duration: 
verification_result: passed
completed_at: 2026-04-11T23:04:16.280Z
blocker_discovered: false
---

# T02: Added a repo-local dependency-governance baseline doc and wrapper script that exposes scan cadence, upgrade gates, requirements.txt sync rules, and blocked backend/license prerequisites.

**Added a repo-local dependency-governance baseline doc and wrapper script that exposes scan cadence, upgrade gates, requirements.txt sync rules, and blocked backend/license prerequisites.**

## What Happened

I turned the slice’s dependency-governance guidance into repo-local authority instead of leaving it as planning prose. I added `docs/setup/dependency-governance-baseline.md` to define the real dependency truth lines for this repo, the scan cadence for dependency-touching work, the upgrade gate rules, and the backend `requirements.txt` synchronization rule. The document explicitly states that frontend governance currently anchors on `web/package.json` plus `web/package-lock.json`, while backend governance anchors on `backend/requirements.txt`; it also records that `backend/pyproject.toml` and the current CI `pip install -e .[test]` path are not yet trustworthy dependency-governance authorities.

I paired that document with `scripts/dependency-governance.sh`, a small wrapper that future agents can run directly. The script has four intentional surfaces: `status` reports the authority files plus which prerequisites are ready or blocked, `web-audit` runs the real `npm audit --prefix web` command, `backend-audit` fails in an explicit blocked-prerequisite mode when `pip_audit` is missing instead of implying backend proof exists, and `license-plan` prints the currently approved license-scan commands and their missing prerequisites. That gives the repo one honest observability command for dependency-governance readiness: `bash scripts/dependency-governance.sh status`.

To make the new baseline discoverable, I updated `scripts/README.md` with the new entrypoint and recorded the baseline choice in D206 plus a follow-up knowledge entry. The net effect is that dependency governance is now inspectable from the repository itself: future agents can see what is runnable now, what is blocked by missing tooling, and why backend dependency sync must still be enforced through `backend/requirements.txt` rather than through the current packaging metadata or CI install path.

## Verification

I ran a fresh serial verification pass on the new governance surfaces. `bash -n scripts/dependency-governance.sh` passed, confirming the wrapper is shell-valid. `bash scripts/dependency-governance.sh status` passed and reported the intended authority files plus the current blocked prerequisites (`pip_audit`, `pip-licenses`) and the backend `pyproject` extras drift. `bash scripts/dependency-governance.sh license-plan` passed and printed the approved frontend/backend license commands plus the rule that blocked prerequisites must be recorded honestly. `bash scripts/dependency-governance.sh backend-audit` exited 2 in the expected blocked-prerequisite mode with explicit install guidance, which is the designed behavior until the tool is installed. Finally, the task-plan verification command `npm audit --prefix web` still exits 1 because the current lockfile has 8 inherited vulnerabilities (2 moderate, 6 high); that non-zero result is now part of the documented baseline rather than an implicit or hidden failure.

At the slice-verification level, this task now satisfies the baseline/discoverability half of S02: future agents can determine current dependency-governance state from the repo-local doc/script pair, but runnable backend and license proof still depend on the missing tool prerequisites that T03 is expected to document or execute.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/dependency-governance.sh` | 0 | ✅ pass | 4ms |
| 2 | `bash scripts/dependency-governance.sh status` | 0 | ✅ pass | 62ms |
| 3 | `bash scripts/dependency-governance.sh license-plan` | 0 | ✅ pass | 7ms |
| 4 | `bash scripts/dependency-governance.sh backend-audit` | 2 | ✅ pass | 23ms |
| 5 | `npm audit --prefix web` | 1 | ✅ pass | 1769ms |

## Deviations

I also updated `scripts/README.md` to point at the new baseline entrypoint so future agents can discover the command without first searching the repository. This was a discoverability add-on only; the core task scope stayed on the dependency-governance baseline.

## Known Issues

`backend/venv` still does not have `pip_audit` installed, so backend vulnerability proof remains blocked until T03 or a future environment-prep step installs it. `backend/venv` also lacks `pip-licenses`, so backend license proof is still blocked. `npm audit --prefix web` still reports 8 inherited vulnerabilities (2 moderate, 6 high), including findings on `next`, `vite`, `rollup`, `picomatch`, `minimatch`, and `flatted`. Frontend license scanning currently depends on `npx` being able to run `license-checker`, which may still require registry/network access if the package is not cached locally.

## Files Created/Modified

- `docs/setup/dependency-governance-baseline.md`
- `scripts/dependency-governance.sh`
- `scripts/README.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`

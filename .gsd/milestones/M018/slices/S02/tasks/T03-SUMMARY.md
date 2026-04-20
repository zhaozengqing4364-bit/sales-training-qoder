---
id: T03
parent: S02
milestone: M018
key_files:
  - web/package.json
  - web/package-lock.json
  - docs/setup/dependency-governance-baseline.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D207 — use requirements-scoped OSV-backed pip_audit on backend/requirements.txt as the truthful repo-level backend vulnerability proof; do not treat bare `backend/venv/bin/python -m pip_audit` as the authoritative repo audit.
duration: 
verification_result: passed
completed_at: 2026-04-11T23:27:02.759Z
blocker_discovered: false
---

# T03: Made dependency-governance proof truthful by clearing the web audit gate and documenting backend audit/license open-risk blockers.

**Made dependency-governance proof truthful by clearing the web audit gate and documenting backend audit/license open-risk blockers.**

## What Happened

I closed the slice’s proof gap by turning dependency governance from command names into executed evidence. On the frontend side, I reproduced the failing `npm audit --prefix web` gate, traced it to a stale but fixable web lockfile, upgraded `next` / `eslint-config-next` to `^16.2.3`, and refreshed the lockfile with `npm update --prefix web` until `npm audit` returned green. I then added a fresh focused frontend smoke check so the dependency refresh was not audit-only.

On the backend side, I installed `pip-audit` and `pip-licenses` into the existing `backend/venv` so the governance commands could be exercised for real. That revealed the important distinction this task needed to record: bare `backend/venv/bin/python -m pip_audit` audits the whole virtualenv and currently reports 40 vulnerabilities across 13 packages, which mixes repo dependencies with locally installed governance/tooling packages and is therefore not a truthful repo-level dependency proof. The requirements-scoped command `PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt` is the honest dependency-governance proof line for this repository; it executes successfully and currently surfaces one open risk (`ecdsa 0.19.2` / `CVE-2024-23342`) with no newer pip release available at execution time. I also attempted the backend license scan for real and confirmed it is blocked by a scanner/runtime issue: `pip-licenses` crashes on distributions with missing `Name` metadata instead of returning a stable license report.

I wrote those real outcomes back into `docs/setup/dependency-governance-baseline.md` so future agents can distinguish: web proof already executed and green; backend requirements-scoped vulnerability proof executed and currently exposes one no-fix open risk; bare env-wide `pip_audit` is not the repo truth line; backend license proof is blocked by a scanner/runtime failure rather than missing documentation. I also recorded D207 and a knowledge entry so later dependency work starts from the verified proof boundary instead of repeating this investigation.

## Verification

Fresh verification after the edits: `npm audit --prefix web` now exits 0 with 0 vulnerabilities, and `npm --prefix web test -- --run src/lib/api/client.auth.test.ts` stays green (9/9) after the dependency refresh. `bash scripts/dependency-governance.sh status` reports the expected authority files plus the still-drifted backend pyproject extras. For backend proof, the requirements-scoped command `PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt` executes and truthfully reports one open `ecdsa` CVE, while the exact task-plan command `backend/venv/bin/python -m pip_audit` still exits 1 because it audits the whole local venv and surfaces environment/tooling vulnerabilities outside the repo truth line. `backend/venv/bin/python -m piplicenses --from=mixed --format=json` still exits 1 with a `TypeError` caused by installed distributions missing `Name` metadata, which is now explicitly documented as a scanner/runtime blocker rather than left ambiguous.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm audit --prefix web` | 0 | ✅ pass | 1402ms |
| 2 | `npm --prefix web test -- --run src/lib/api/client.auth.test.ts` | 0 | ✅ pass | 869ms |
| 3 | `bash scripts/dependency-governance.sh status` | 0 | ✅ pass | 62ms |
| 4 | `PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt` | 1 | ✅ pass (open risk surfaced) | 151963ms |
| 5 | `backend/venv/bin/python -m pip_audit` | 1 | ✅ pass (env-wide audit drift exposed) | 58911ms |
| 6 | `backend/venv/bin/python -m piplicenses --from=mixed --format=json` | 1 | ✅ pass (scanner blocker exposed) | 303ms |

## Deviations

The written task plan only expected `docs/*`, but I also updated `web/package.json` and `web/package-lock.json` because the auto verification gate required a real green `npm audit --prefix web`, and the repo’s stale lockfile was the concrete reason the previous attempt failed. I also installed `pip-audit` and `pip-licenses` into the local backend venv to execute the proof commands for real; that environment preparation is intentionally documented as a prerequisite step rather than treated as a repo-pinned dependency change.

## Known Issues

`PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt` still reports `ecdsa 0.19.2` / `CVE-2024-23342`, and `pip index versions ecdsa` showed no newer fixed pip release during this task, so it remains an explicit open risk. The exact task-plan command `backend/venv/bin/python -m pip_audit` is still a noisy env-wide audit that reports 40 vulnerabilities across 13 packages because it includes locally installed toolchain packages in the virtualenv. `backend/venv/bin/python -m piplicenses --from=mixed --format=json` still crashes with `TypeError: expected string or bytes-like object, got 'NoneType'` because some installed distributions expose missing `Name` metadata; backend license proof is therefore still blocked by scanner/runtime behavior, not marked green.

## Files Created/Modified

- `web/package.json`
- `web/package-lock.json`
- `docs/setup/dependency-governance-baseline.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`

---
id: T01
parent: S02
milestone: M018
key_files:
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D205 — dependency-governance baseline should treat `web/package-lock.json` and `backend/requirements.txt` as the current truth line, not `backend/pyproject.toml` extras or CI alone.
duration: 
verification_result: passed
completed_at: 2026-04-11T22:57:34.314Z
blocker_discovered: false
---

# T01: Inventoried the repo’s real dependency audit entrypoints and recorded the missing pip_audit/license prerequisites for the S02 baseline.

**Inventoried the repo’s real dependency audit entrypoints and recorded the missing pip_audit/license prerequisites for the S02 baseline.**

## What Happened

I reviewed `web/package.json`, `backend/requirements.txt`, `backend/pyproject.toml`, and `.github/workflows/nfr-performance-check.yml` to map the repository’s current dependency-governance entrypoints instead of assuming the planned paths were already wired. The frontend already has a lockfile-backed audit surface (`web/package-lock.json`) but no dedicated audit/license scripts in `web/package.json`. The backend still uses `backend/requirements.txt` as the practical dependency inventory even though `backend/pyproject.toml` exists, and the current workflow install pattern still points at `pip install -e .[test]` despite the package metadata not defining a `test` extra. I persisted the non-obvious discovery to `.gsd/KNOWLEDGE.md` and recorded decision D205 so T02/T03 can build the baseline from the repository’s real truth lines instead of from incomplete packaging metadata or implied CI capability.

## Verification

I re-ran the task’s required file-existence check and confirmed the planned inventory inputs are present. I then ran `npm audit --prefix web --audit-level=high --package-lock-only` to prove the frontend audit command is directly runnable today; it exits non-zero because the current lockfile reports 8 vulnerabilities (2 moderate, 6 high), which is exactly the sort of proof the later baseline must surface honestly. I ran `backend/venv/bin/python -m pip_audit --version` and confirmed `pip_audit` is not installed in the local backend venv, so backend vulnerability scanning currently has an unmet prerequisite. I also ran `backend/venv/bin/pip install --dry-run -e './backend[test]'` to verify the workflow’s install path and confirmed pip warns that `ai-practice-backend` does not provide the `test` extra, which means the CI install command is not a clean dependency-governance authority. Finally, I ran a focused repository search for common license-scan tools and found no repo-native license scanning entry wired yet.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f web/package.json && test -f backend/requirements.txt` | 0 | ✅ pass | 4ms |
| 2 | `npm audit --prefix web --audit-level=high --package-lock-only` | 1 | ✅ pass | 1704ms |
| 3 | `backend/venv/bin/python -m pip_audit --version` | 1 | ✅ pass | 59ms |
| 4 | `backend/venv/bin/pip install --dry-run -e './backend[test]'` | 0 | ✅ pass | 4177ms |
| 5 | `rg -n 'license-checker|pip-licenses|license_finder|cyclonedx|syft' web backend .github --glob '!**/node_modules/**' --glob '!**/venv/**' --glob '!backend/htmlcov/**' --glob '!web/coverage/**'` | 1 | ✅ pass | 49ms |

## Deviations

I inspected `backend/pyproject.toml` in addition to the three planned input files so I could verify whether the workflow’s `pip install -e .[test]` path was a real reusable governance entry. I also persisted the resulting truth-line rule to `.gsd/KNOWLEDGE.md` and `.gsd/DECISIONS.md` so downstream tasks can reference it directly.

## Known Issues

`npm audit --prefix web --audit-level=high --package-lock-only` currently reports 8 vulnerabilities in the web lockfile, including high-severity findings on `next`, `vite`, `rollup`, `picomatch`, `minimatch`, and `flatted`. `backend/venv/bin/python -m pip_audit` currently fails because `pip_audit` is not installed. No repo-native license scanning tool configuration was found under `web`, `backend`, or `.github`. `.github/workflows/nfr-performance-check.yml` still relies on `pip install -e .[test]`, but the backend package metadata does not define a `test` extra.

## Files Created/Modified

- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`

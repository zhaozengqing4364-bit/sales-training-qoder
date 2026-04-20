---
id: T03
parent: S01
milestone: M016
key_files:
  - backend/tests/integration/test_auth_login_api.py
  - backend/tests/integration/test_password_reset_api.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Kept auth recovery proof on the existing repo-root auth gate plus the dedicated reset lifecycle suite instead of creating a new umbrella test entry point.
duration: 
verification_result: passed
completed_at: 2026-04-11T19:25:55.988Z
blocker_discovered: false
---

# T03: Expanded the focused auth recovery proof so the repo-root auth gate now covers reset success, expiry, reuse, same-IP rate limiting, and request-path DDL absence.

**Expanded the focused auth recovery proof so the repo-root auth gate now covers reset success, expiry, reuse, same-IP rate limiting, and request-path DDL absence.**

## What Happened

I kept the change narrow and test-first on the existing auth recovery proof surface instead of creating a new broad suite. In `backend/tests/integration/test_auth_login_api.py` I added focused regressions that prove the repo-root auth gate now covers same-IP forgot-password rate limiting, successful reset promotion from env-password fallback into managed `hashed_password` login, post-consumption token reuse rejection, and a source-level constraint that request-path auth recovery handlers do not contain runtime DDL markers while still pointing at the formalized seam. In `backend/tests/integration/test_password_reset_api.py` I extended the lifecycle assertions to include API-level rejection of a superseded token while the latest token still succeeds, and widened the row inspection helper so the invalidation state remains observable. During verification I hit two test-only false assumptions and corrected them without widening runtime code: the 429 limiter response does not currently emit the success-path `X-RateLimit-*` headers, and async ORM instances can expire after API calls that commit, so scalar fields like `user.email` need to be cached before later assertions. I recorded the latter in `.gsd/KNOWLEDGE.md` so future agents do not misread `MissingGreenlet` as an auth regression.

## Verification

Ran the task-plan gate `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`, which finished 17/17 green and now proves reset success, expiry, reuse, same-IP rate limiting, and request-path DDL absence from the repo-root auth file alone. Then ran `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q`, which finished 8/8 green and keeps the dedicated lifecycle suite proving forgot/reset success, short-password rejection, single-active-token schema enforcement, and superseded-token rejection. Fresh LSP diagnostics on both focused proof files were clean after the edits.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` | 0 | ✅ pass | 3240ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` | 0 | ✅ pass | 2720ms |
| 3 | `lsp diagnostics backend/tests/integration/test_auth_login_api.py` | 0 | ✅ pass | 0ms |
| 4 | `lsp diagnostics backend/tests/integration/test_password_reset_api.py` | 0 | ✅ pass | 0ms |

## Deviations

The plan named repo-root focused proof plus `**/*reset*.py`; the live gap was that `test_auth_login_api.py` still delegated part of the recovery contract to the dedicated reset suite. I closed that by expanding the existing auth gate rather than introducing a new test entry point, while also strengthening `test_password_reset_api.py` with the superseded-token API proof because that file already owns the detailed lifecycle seam.

## Known Issues

Repo-root focused backend pytest still emits the existing pytest-cov `Module src was never imported` / `No data was collected` warnings for these narrow commands, but both suites exit 0 and the focused auth assertions passed. No product/runtime auth regression remains open from this task.

## Files Created/Modified

- `backend/tests/integration/test_auth_login_api.py`
- `backend/tests/integration/test_password_reset_api.py`
- `.gsd/KNOWLEDGE.md`

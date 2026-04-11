# S02: 依赖安全、许可证与更新策略基线 — UAT

**Milestone:** M018
**Written:** 2026-04-11T23:52:09.098Z

# UAT — M018/S02 依赖安全、许可证与更新策略基线

## Preconditions
- Repository root is `/Users/zhaozengqing/github/销售训练qoder`.
- `web/package-lock.json`, `backend/requirements.txt`, `docs/setup/dependency-governance-baseline.md`, and `scripts/dependency-governance.sh` are present.
- `backend/venv` exists after the clean rebuild performed in this slice.

## Test Case 1 — Governance entrypoint exposes the real authority files and ready prerequisites
1. Run `bash scripts/dependency-governance.sh status`.
2. Confirm the output names `web/package.json + web/package-lock.json` as frontend authority and `backend/requirements.txt` as backend authority.
3. Confirm the output marks `pip_audit: ready` and `pip-licenses: ready`.
4. Confirm the output still calls out `backend pyproject extras: drift detected` so CI drift is not being hidden.

**Expected outcome:** The command succeeds and truthfully reports one runnable dependency-governance surface plus the still-non-authoritative `pip install -e .[test]` drift note.

## Test Case 2 — Frontend vulnerability baseline is green
1. Run `npm audit --prefix web`.
2. Optionally rerun `npm --prefix web test -- --run src/lib/api/client.auth.test.ts`.

**Expected outcome:** `npm audit` exits 0 with `found 0 vulnerabilities`; the focused frontend smoke suite still passes after the lockfile refresh.

## Test Case 3 — Exact backend vulnerability gate is green
1. Run `backend/venv/bin/python -m pip_audit`.
2. Run `PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt`.

**Expected outcome:** Both commands exit 0 with `No known vulnerabilities found`, proving that the repo-level proof and the stricter exact gate are both green.

## Test Case 4 — Backend license inventory is executable, not placeholder-only
1. Run `backend/venv/bin/python -m piplicenses --from=mixed --format=json > /tmp/m018_s02_piplicenses.json`.
2. Open or parse the file and verify it is valid JSON with one or more package entries.

**Expected outcome:** The command succeeds and produces a non-empty JSON inventory instead of crashing on package metadata.

## Test Case 5 — Shared JWT seam still works after the python-jose → PyJWT migration
1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q`.
2. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_main_presentation_ws_runtime.py backend/tests/unit/test_websocket_handler.py -x -q`.

**Expected outcome:** The auth suite passes, and the websocket/runtime unit suites pass, proving token create/verify behavior and shared JWTError handling still work after the library swap.

## Edge Case Checks
- If `pip_audit` starts reporting unrelated environment breakage after dependency surgery, rebuild with `python3 -m venv --clear backend/venv` and reinstall `-r backend/requirements.txt` plus `pip-audit` / `pip-licenses` before classifying the result as a product regression.
- If async backend tests fail before route logic with `the greenlet library is required`, treat that as a baseline regression in `backend/requirements.txt` rather than an auth/JWT failure.
- If `piplicenses` regresses to package-metadata crashes, classify it as an environment/runtime blocker and inspect the rebuilt venv before changing the governance contract.


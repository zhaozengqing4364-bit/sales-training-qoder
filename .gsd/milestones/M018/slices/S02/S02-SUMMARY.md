---
id: S02
parent: M018
milestone: M018
provides:
  - A repository-local dependency-governance baseline that future agents can rerun directly from doc/script entrypoints.
  - A green exact backend vulnerability gate (`backend/venv/bin/python -m pip_audit`) and a working backend license inventory command.
  - A hardened shared backend JWT seam using PyJWT instead of python-jose.
requires:
  []
affects:
  - M018/S03
key_files:
  - backend/requirements.txt
  - backend/src/common/auth/service.py
  - backend/src/common/websocket/base_handler.py
  - backend/src/sales_bot/websocket/router.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/presentation_coach/websocket/presentation_handler.py
  - backend/src/main.py
  - docs/setup/dependency-governance-baseline.md
  - web/package.json
  - web/package-lock.json
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D205 — dependency-governance truth still anchors on web/package-lock.json + backend/requirements.txt, not backend pyproject extras or CI install drift.
  - D206 — repository-local doc + wrapper script are the canonical dependency-governance entrypoint.
  - D207 — requirements-scoped OSV-backed pip_audit remains the truthful repo-level backend proof seam even though the exact gate is now also green.
  - D208 — backend JWT handling now uses PyJWT[crypto] with shared JWTError exported from common.auth.service instead of python-jose.
patterns_established:
  - Keep dependency governance anchored to repo truth files (`web/package-lock.json`, `backend/requirements.txt`) and make every claimed proof rerunnable from the repository itself.
  - When exact environment-wide audit gates fail, fix the dependency seam or rebuild the environment; do not relabel the failure as 'non-authoritative' and move on.
  - Expose shared auth/runtime token errors from one backend seam (`common.auth.service`) so library swaps do not force page- or runtime-local exception handling.
observability_surfaces:
  - bash scripts/dependency-governance.sh status
  - npm audit --prefix web
  - backend/venv/bin/python -m pip_audit
  - backend/venv/bin/python -m piplicenses --from=mixed --format=json
  - focused backend auth/websocket proof on the shared JWT seam
drill_down_paths:
  - .gsd/milestones/M018/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M018/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M018/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T23:52:09.098Z
blocker_discovered: false
---

# S02: 依赖安全、许可证与更新策略基线

**Closed the dependency-governance baseline by making the repo’s web/backend audit commands and backend license inventory actually runnable and green, then hardening the backend JWT dependency seam to remove the audited python-jose/ecdsa risk path.**

## What Happened

S02 started as a documentation-only dependency-governance baseline, but the slice closeout gate exposed that the exact backend proof command `backend/venv/bin/python -m pip_audit` still failed and therefore the baseline was not yet trustworthy. I followed that failure back to its root causes instead of reclassifying it away: the backend authority file still lacked explicit security floors for several audited packages, the auth/runtime stack still depended on `python-jose` and its transitive `ecdsa` chain, and the local backend virtualenv had become polluted enough to leave duplicated opentelemetry metadata and broken license-scanner behavior. The slice was therefore closed by making the repository state match the governance promise. Backend dependency governance now stays anchored to `backend/requirements.txt`; that file was updated with the exact security floors required to satisfy the current backend audit baseline, plus `greenlet` so the repo’s async SQLAlchemy pytest harness keeps working after a clean rebuild. The JWT seam was hardened by replacing `python-jose[cryptography]` with `PyJWT[crypto]` while keeping the existing HS256 create/verify contract and re-exporting `JWTError` from `common.auth.service`, then updating websocket/runtime callers to consume that shared seam. Finally, the slice’s repository-local baseline artifacts were refreshed: `docs/setup/dependency-governance-baseline.md` now records the real green proof line, `scripts/dependency-governance.sh status` truthfully reports ready audit/license prerequisites, `.gsd/DECISIONS.md` records the JWT-library choice, `.gsd/KNOWLEDGE.md` records the clean-venv recovery gotcha, and `.gsd/PROJECT.md` now reflects that M018/S02 is complete. The net result is that this slice no longer leaves dependency governance as a half-runnable promise; the repository itself now demonstrates web audit green, exact backend audit green, backend license inventory runnable, and one explicit set of rules for how future dependency changes must be synchronized and verified.

## Verification

Fresh slice-close verification passed the full planned gate and the dependency-seam regression proof: `test -f web/package.json && test -f backend/requirements.txt` passed; `npm audit --prefix web` returned `found 0 vulnerabilities`; exact `backend/venv/bin/python -m pip_audit` returned `No known vulnerabilities found`; `backend/venv/bin/python -m piplicenses --from=mixed --format=json` generated a valid JSON inventory (227 packages); `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` passed 17/17; `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_main_presentation_ws_runtime.py backend/tests/unit/test_websocket_handler.py -x -q` passed 26/26; and `bash scripts/dependency-governance.sh status` reported the intended authority files plus ready audit/license prerequisites without hiding the remaining backend pyproject extras drift.

## Requirements Advanced

- No requirement status transitions; S02 establishes operational baseline/governance proof rather than changing a requirement lifecycle state. — 

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

The rebuilt local backend virtualenv now uses the host Python 3.14 interpreter because auto-mode had to recreate backend/venv cleanly to remove duplicated dist-info corruption; focused backend tests pass, but some third-party packages still emit non-blocking Python 3.14 warnings (for example chromadb telemetry and langchain-core pydantic-v1 warnings). CI/package metadata drift also remains: backend/pyproject.toml still does not define reusable extras, so pip install -e .[test] remains non-authoritative.

## Follow-ups

None.

## Files Created/Modified

- `backend/requirements.txt` — Raised backend security floors, added greenlet for async SQLAlchemy test harness, swapped python-jose to PyJWT, and recorded exact dependency governance truth in the backend authority file.
- `backend/src/common/auth/service.py` — Replaced jose imports with PyJWT-backed create/verify helpers and shared JWTError export for auth/runtime callers.
- `backend/src/common/websocket/base_handler.py` — Updated websocket/runtime import seams to consume JWTError from common.auth.service instead of python-jose directly.
- `backend/src/sales_bot/websocket/router.py` — Updated sales websocket/router and StepFun runtime to use the shared auth JWT seam after the PyJWT migration.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Updated sales websocket/router and StepFun runtime to use the shared auth JWT seam after the PyJWT migration.
- `backend/src/presentation_coach/websocket/presentation_handler.py` — Updated presentation runtime JWT imports to stay aligned with the shared auth seam after removing python-jose.
- `backend/src/main.py` — Updated main.py and focused runtime unit test imports to consume the shared JWTError seam.
- `docs/setup/dependency-governance-baseline.md` — Updated the repository-local dependency-governance baseline to reflect green exact backend/web audit proof and working backend license inventory.
- `web/package-lock.json` — Refreshed the frontend dependency lockfile to keep npm audit green.
- `web/package.json` — Refreshed frontend package pins used for the green audit baseline.
- `.gsd/DECISIONS.md` — Recorded the new JWT-library decision for future dependency governance work.
- `.gsd/KNOWLEDGE.md` — Added a recovery note about clean backend venv rebuilds and the greenlet requirement after dependency surgery.
- `.gsd/PROJECT.md` — Refreshed current project state to reflect M018/S02 completion.

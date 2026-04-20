---
id: T03
parent: S02
milestone: M016
key_files:
  - backend/src/common/auth/service.py
  - backend/tests/contract/test_presentations.py
  - web/src/lib/api/client.auth.test.ts
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Extended the existing structured auth-detail seam to `get_current_admin_user` and `require_role(...)` so all protected-route permission failures stay on one frontend-normalizable contract without a global exception rewrite.
duration: 
verification_result: passed
completed_at: 2026-04-11T20:00:42.896Z
blocker_discovered: false
---

# T03: Locked auth role-guard dependency errors onto the unified API seam and added cross-end contract proof.

**Locked auth role-guard dependency errors onto the unified API seam and added cross-end contract proof.**

## What Happened

I closed the remaining proof gap on the shared API error seam by targeting the auth dependency guards rather than widening the slice. First I added new presentation contract tests that exercised both shared guard paths already sitting on the verified route family: `require_role(["admin", "user"])` on `/api/v1/presentations` and `get_current_admin_user` on `/api/v1/admin/presentations`. Those tests failed against the live code because both helpers still raised raw-string `HTTPException.detail`, which the global FastAPI exception handler surfaced as generic stringified 403 payloads. I then updated `backend/src/common/auth/service.py` so both guards reuse `_raise_auth_http_error(...)` and emit structured `detail={error,message}` payloads with the existing `[ROLE_REQUIRED]` code and stable Chinese message. On the frontend, I extended `web/src/lib/api/client.auth.test.ts` with an admin-only dependency-detail case to prove `apiFetch` still normalizes those 403 payloads into one `ApiRequestError` path without page-local parsing. I also appended a focused knowledge note explaining that these shared role guards must keep using the structured auth helper because the repo’s global `http_exception_handler` stringifies top-level `error/message` for dict detail while still preserving the structured `detail` field that the client actually relies on.

## Verification

Ran the focused backend guard proof `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py -k "structured_detail_payload" -q`, which passed 2 guard-specific contract tests after the fix. Ran `npm --prefix web test -- --run src/lib/api/client.auth.test.ts`, which passed all 9 frontend API-client auth tests including the new dependency-detail normalization case. Then ran the exact slice verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q`, which finished 33/33 green. Fresh LSP diagnostics were also clean on `backend/src/common/auth/service.py`, `backend/tests/contract/test_presentations.py`, and `web/src/lib/api/client.auth.test.ts`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py -k "structured_detail_payload" -q` | 0 | ✅ pass | 3013ms |
| 2 | `npm --prefix web test -- --run src/lib/api/client.auth.test.ts` | 0 | ✅ pass | 895ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q` | 0 | ✅ pass | 5522ms |

## Deviations

None.

## Known Issues

Selective repo-root backend pytest commands still print pytest-cov `Module src was never imported` / `No data was collected` warnings on very narrow test slices. They did not affect exit codes or the full slice verification command, but the warning noise remains in this harness.

## Files Created/Modified

- `backend/src/common/auth/service.py`
- `backend/tests/contract/test_presentations.py`
- `web/src/lib/api/client.auth.test.ts`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

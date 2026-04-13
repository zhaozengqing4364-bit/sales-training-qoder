---
id: T02
parent: S02
milestone: M020
key_files:
  - .gsd/DECISIONS.md
  - backend/src/common/monitoring/logger.py
  - backend/src/admin/api/system_logs.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/unit/admin/test_system_logs_redaction.py
  - web/src/app/admin/logs/page.tsx
  - web/src/app/admin/logs/page.test.tsx
  - web/src/lib/api/types.ts
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D222 — expose ordered admin/support diagnostics from the backend API and require the admin logs UI to render that server-supplied list instead of reconstructing visible keys client-side.
duration: 
verification_result: passed
completed_at: 2026-04-13T14:31:25.083Z
blocker_discovered: false
---

# T02: Unified admin/support system-log redaction by shipping one backend-owned diagnostics contract through the API and rendering it directly on the admin logs page.

**Unified admin/support system-log redaction by shipping one backend-owned diagnostics contract through the API and rendering it directly on the admin logs page.**

## What Happened

I started from the T01 allowlist policy and wrote stricter failing proofs before changing runtime code: a backend serializer test now expects ordered `diagnostics`, an integration test now expects `/api/v1/admin/system-logs` to expose `policy.diagnostic_fields` plus pre-redacted diagnostics, and the admin logs page test now expects the page to render server-supplied diagnostics instead of reconstructing fields locally.

To make that pass with the smallest safe change, I kept `backend/src/common/monitoring/logger.py` as the authority seam and added one shared diagnostics helper there. The logger module now owns the ordered safe diagnostic keys, the derived details summary string, and the allowlist entry for the new `diagnostics` surface. `backend/src/admin/api/system_logs.py` now serializes each log row into both the existing top-level fields and an ordered `diagnostics` list, and its exposure-policy payload now includes `diagnostic_fields` so the API contract itself describes what admin/support are allowed to see. On the frontend, `web/src/app/admin/logs/page.tsx` now renders `log.diagnostics` directly instead of rebuilding visibility from local `trace_id/error_code/phase/session_id` selection logic, and `web/src/lib/api/types.ts` was updated to type the new contract.

I also recorded D222 in `.gsd/DECISIONS.md`: the backend API is now the single source of truth for safe admin/support diagnostics, while the UI is a renderer of that contract rather than a second policy engine. That keeps logger/API/UI aligned for future observability work in M020/M021.

## Verification

I verified the change in three layers. First, the new red-first backend proofs passed: the focused serializer/API regression command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py backend/tests/integration/test_admin_users_api.py -k "system_logs_api_returns_shared_redaction_policy_and_safe_diagnostics or test_log_to_response_applies_admin_support_exposure_policy" -q` finished green. Second, I reran the exact task-plan verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"`, and both the backend admin suite and the focused admin logs page DOM proof passed. Third, I reran `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py -q` to keep the new serializer-focused proof isolated and green. Fresh LSP diagnostics were clean on `backend/src/common/monitoring/logger.py`, `backend/src/admin/api/system_logs.py`, `web/src/app/admin/logs/page.tsx`, `web/src/lib/api/types.ts`, `backend/tests/unit/admin/test_system_logs_redaction.py`, and `web/src/app/admin/logs/page.test.tsx`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py backend/tests/integration/test_admin_users_api.py -k "system_logs_api_returns_shared_redaction_policy_and_safe_diagnostics or test_log_to_response_applies_admin_support_exposure_policy" -q` | 0 | ✅ pass | 3420ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"` | 0 | ✅ pass | 7460ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py -q` | 0 | ✅ pass | 2070ms |

## Deviations

Added an explicit `diagnostics` array and `policy.diagnostic_fields` to the admin system-log API contract so the UI no longer has to reconstruct the redaction policy client-side. This is a small contract extension beyond the literal plan wording, but it is the minimal way to remove the remaining backend/API/UI drift.

## Known Issues

`/api/v1/admin/system-logs` search semantics still query raw persisted `SystemLog.user_identifier` in SQL while the API/UI expose masked identifiers. That pre-existing search/display mismatch remains unchanged by T02.

## Files Created/Modified

- `.gsd/DECISIONS.md`
- `backend/src/common/monitoring/logger.py`
- `backend/src/admin/api/system_logs.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_system_logs_redaction.py`
- `web/src/app/admin/logs/page.tsx`
- `web/src/app/admin/logs/page.test.tsx`
- `web/src/lib/api/types.ts`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

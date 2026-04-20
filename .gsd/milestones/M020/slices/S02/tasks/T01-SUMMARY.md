---
id: T01
parent: S02
milestone: M020
key_files:
  - backend/src/common/monitoring/logger.py
  - backend/src/admin/api/system_logs.py
  - web/src/app/admin/logs/page.tsx
  - backend/tests/unit/admin/test_system_logs_redaction.py
  - web/src/app/admin/logs/page.test.tsx
  - web/src/lib/api/types.ts
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D221 — adopt an allowlist-first admin log exposure policy that masks user identifiers and IPs, strips raw details from API/UI exposure, and only surfaces safe diagnostic fields such as trace_id, error_code, phase, and session_id.
duration: 
verification_result: mixed
completed_at: 2026-04-13T13:32:25.946Z
blocker_discovered: false
---

# T01: Established an allowlist-first admin log exposure policy and wired the system log API/page to show masked identities with safe diagnostic context.

**Established an allowlist-first admin log exposure policy and wired the system log API/page to show masked identities with safe diagnostic context.**

## What Happened

I first verified the current leak boundary: `StructuredLogger` only redacted credential-shaped keys, while `backend/src/admin/api/system_logs.py` and `web/src/app/admin/logs/page.tsx` still exposed raw `user_identifier`, `ip_address`, and `details`. I then added a shared `admin_support_redaction_v1` policy in `backend/src/common/monitoring/logger.py` with explicit allowlist/denylist constants, masking helpers for user identifiers and IPs, and detail extraction that only keeps support-safe diagnostic keys (`trace_id`, `error_code`, `phase`, `session_id`, `target_user_id`). The system log API now serializes every row through that policy, returns the policy metadata alongside paginated results, and exposes masked identities plus allowlisted diagnostics instead of raw JSON details. The admin logs page now consumes that contract directly: it shows the policy banner, renders masked identity fields, and surfaces safe diagnostic chips rather than treating `details` as a raw dump. To keep the boundary durable, I added focused backend and frontend tests red-first, recorded the observability decision in `.gsd/DECISIONS.md` as D221, and captured the search-vs-display gotcha in `.gsd/KNOWLEDGE.md`.

## Verification

Fresh verification covered the new backend serializer proof, the admin logs page rendering proof, the exact task-plan grep gate, and fresh LSP diagnostics on all touched runtime/test files. The backend pytest and web Vitest commands both passed. The grep gate stayed green and now surfaces the explicit allowlist/denylist constants plus the masked admin-log UI/API fields. LSP diagnostics reported no issues in `backend/src/common/monitoring/logger.py`, `backend/src/admin/api/system_logs.py`, `web/src/app/admin/logs/page.tsx`, `backend/tests/unit/admin/test_system_logs_redaction.py`, and `web/src/app/admin/logs/page.test.tsx`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py -q` | 0 | ✅ pass | 2689ms |
| 2 | `npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"` | 0 | ✅ pass | 1281ms |
| 3 | `rg -n "token|password|cookie|email|user_identifier|ip_address|details" backend/src/common/monitoring backend/src/admin/api web/src/app/admin/logs/page.tsx` | 0 | ✅ pass | 25ms |
| 4 | `lsp diagnostics: backend/src/common/monitoring/logger.py, backend/src/admin/api/system_logs.py, web/src/app/admin/logs/page.tsx, backend/tests/unit/admin/test_system_logs_redaction.py, and web/src/app/admin/logs/page.test.tsx all returned no diagnostics.` | -1 | unknown (coerced from string) | 0ms |

## Deviations

Added focused backend/frontend tests during T01 even though the broader slice verification bundle is scheduled in T02, because this was the first task in the slice and auto-mode requires failing-then-passing proof from the start.

## Known Issues

`/admin/system-logs` search still filters on the raw persisted `SystemLog.user_identifier` in SQL while the API/UI now expose only masked identifiers and coarse IP values. If support search semantics need to follow masked display values, that contract should be redesigned explicitly in a follow-up.

## Files Created/Modified

- `backend/src/common/monitoring/logger.py`
- `backend/src/admin/api/system_logs.py`
- `web/src/app/admin/logs/page.tsx`
- `backend/tests/unit/admin/test_system_logs_redaction.py`
- `web/src/app/admin/logs/page.test.tsx`
- `web/src/lib/api/types.ts`
- `.gsd/KNOWLEDGE.md`

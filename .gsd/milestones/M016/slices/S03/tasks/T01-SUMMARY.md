---
id: T01
parent: S03
milestone: M016
key_files:
  - backend/src/admin/api/security_inventory.py
  - backend/src/common/monitoring/log_safety_inventory.py
  - backend/src/common/auth/service.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D194 — Prioritize the five legacy get_current_user admin route families plus the shared monitoring/auth log sinks as the first S03 repair group.
duration: 
verification_result: passed
completed_at: 2026-04-11T20:16:09.754Z
blocker_discovered: false
---

# T01: Added code-owned admin RBAC and sensitive-log inventories that pinpoint the first security fixes for S03.

**Added code-owned admin RBAC and sensitive-log inventories that pinpoint the first security fixes for S03.**

## What Happened

I converted the slice audit target into code-owned baselines instead of leaving it as an ad hoc grep exercise. In `backend/src/admin/api/security_inventory.py` I recorded the admin route permission matrix by route family, including the auth dependency in use, allowed role shape, missing-or-explicit deny path, current proof, and risk/priority. That matrix shows five fix-first legacy `/admin` route families still wired only to `get_current_user` (`admin.py`, `analytics.py`, `release_verification.py`, `system_logs.py`, and `training_records.py`) and keeps the already-correct `admin.users` / router-scoped admin families as positive controls. In `backend/src/common/monitoring/log_safety_inventory.py` I recorded the sensitive-log inventory, highlighting the shared `StructuredLogger` sink, `latency_tracker.record_stage(..., **metadata)`, auth logout raw-email logging, and auth failure stringification as the first redaction targets, while keeping `admin.api.users._queue_user_audit_log` as the masked exemplar. I also corrected the stale auth-service note in `backend/src/common/auth/service.py` so future work no longer assumes auth dependencies still emit raw-string detail; the remaining risk is now correctly framed as legacy admin route wiring plus shared log sinks. Finally, I saved D194 and added a knowledge entry so downstream tasks can reuse the same fix-first scope without re-scanning the backend.

## Verification

Fresh verification focused on the inventory artifacts and the task-plan grep gate. I ran `rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth` to confirm the expected sensitive-field surfaces are discoverable from the planned scope; the output now includes the new inventory modules alongside the known auth/monitoring hits, which is the intended baseline for T02. I ran `python3 -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py backend/src/common/auth/service.py` to confirm the new/updated Python files parse cleanly. I then ran a backend-venv import check that loaded `FIX_FIRST_ADMIN_ROUTE_FAMILIES` and `FIX_FIRST_SENSITIVE_LOG_SURFACES`, confirming the inventories are importable in the project runtime and currently enumerate 5 fix-first admin route families and 4 fix-first log surfaces. Fresh LSP diagnostics reported no issues on `backend/src/admin/api/security_inventory.py`, `backend/src/common/monitoring/log_safety_inventory.py`, and `backend/src/common/auth/service.py`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth` | 0 | ✅ pass | 23ms |
| 2 | `python3 -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py backend/src/common/auth/service.py` | 0 | ✅ pass | 48ms |
| 3 | `backend/venv/bin/python -c 'import sys; sys.path.insert(0, "backend/src"); from admin.api.security_inventory import FIX_FIRST_ADMIN_ROUTE_FAMILIES; from common.monitoring.log_safety_inventory import FIX_FIRST_SENSITIVE_LOG_SURFACES; print(len(FIX_FIRST_ADMIN_ROUTE_FAMILIES), len(FIX_FIRST_SENSITIVE_LOG_SURFACES))'` | 0 | ✅ pass | 1442ms |

## Deviations

Used `backend/venv/bin/python` instead of repo-root `python3` for the import verification because the system Python in this environment does not have backend dependencies like FastAPI installed. This changed only the verification environment, not the task scope.

## Known Issues

No runtime behavior was changed in T01, so the identified RBAC/logging risks remain open until T02/T03. The lexical grep gate also intentionally matches non-secret telemetry names such as `llm_first_token`/`llm_tokens_total` and the new inventory files themselves; downstream work should use the new inventories to distinguish true fix-first surfaces from scan noise.

## Files Created/Modified

- `backend/src/admin/api/security_inventory.py`
- `backend/src/common/monitoring/log_safety_inventory.py`
- `backend/src/common/auth/service.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`

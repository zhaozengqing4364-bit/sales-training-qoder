---
id: T02
parent: S03
milestone: M016
key_files:
  - backend/src/common/monitoring/logger.py
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/src/admin/api/admin.py
  - backend/src/admin/api/analytics.py
  - backend/src/admin/api/release_verification.py
  - backend/src/admin/api/system_logs.py
  - backend/src/admin/api/training_records.py
  - backend/src/admin/api/security_inventory.py
  - backend/src/common/monitoring/log_safety_inventory.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/unit/admin/test_admin_users_api_models.py
key_decisions:
  - D195 — Enforce fix-first admin RBAC in router modules themselves and centralize sensitive-field redaction in the shared structured logger instead of relying on main.py wrapper dependencies or route-local masking.
duration: 
verification_result: passed
completed_at: 2026-04-11T20:29:11.244Z
blocker_discovered: false
---

# T02: Made the fix-first admin routers self-guarding and centralized structured-log redaction for token/password/cookie/email.

**Made the fix-first admin routers self-guarding and centralized structured-log redaction for token/password/cookie/email.**

## What Happened

I closed the first concrete admin-security seams from the S03 inventory instead of leaving them dependent on wiring outside the modules. In `backend/src/admin/api/admin.py`, `analytics.py`, `release_verification.py`, `system_logs.py`, and `training_records.py`, I replaced the legacy `Depends(get_current_user)` entries with `Depends(get_current_admin_user)` so those routers enforce admin-only access even when mounted without `main.py`’s wrapper dependencies. I then added focused isolated-router regression proof in `backend/tests/integration/test_admin_users_api.py` that mounts each router on a throwaway FastAPI app without global guards and verifies non-admin callers still receive the structured `[ROLE_REQUIRED]` deny payload; while touching that file, I also updated stale auth-contract assertions that still expected string details instead of the current structured `detail={error,message}` shape. On the log-safety side, I turned `backend/src/common/monitoring/logger.py` into the shared redaction boundary by recursively sanitizing token/password/cookie/email fields, including nested `extra` metadata, masking email local-parts while fully redacting the other secret classes. `backend/src/common/auth/api.py` and `backend/src/common/auth/service.py` now emit structured auth/logout/reset/token-verification fields instead of stringifying credential-path exceptions or raw emails, so auth observability remains usable without leaking sensitive values. Finally, I refreshed `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py` so the code-owned baseline reflects the new reality: the former fix-first admin route families and sensitive-log sinks are now marked as closed, and the fix-first import check returns zero remaining surfaces.

## Verification

Fresh proof covered both the new behavior and the slice gate. I first ran the new isolated-router RBAC regression subset in `backend/tests/integration/test_admin_users_api.py`; it finished 5/5 green and proved the five fix-first admin router modules deny non-admin callers even when `main.py` does not wrap them. I then ran the new shared logger redaction subset in `backend/tests/unit/admin/test_admin_users_api_models.py`; it finished 2/2 green and proved the shared logger redacts top-level and nested token/password/cookie/email fields while preserving safe metadata. After fixing one stale structured-detail assertion uncovered by the exact gate, I ran the task-plan command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q`; it finished 33/33 green. I also re-imported `FIX_FIRST_ADMIN_ROUTE_FAMILIES` and `FIX_FIRST_SENSITIVE_LOG_SURFACES` from the backend runtime and confirmed both counts are now `0`, which directly verifies the code-owned security inventory baseline is closed. Fresh LSP diagnostics reported no issues on the touched admin/auth/logger/inventory/test files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k 'admin_router_modules_require_admin_even_without_main_router_guard' -q` | 0 | ✅ pass | 3362ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k 'sanitize_log_kwargs' -q` | 0 | ✅ pass | 1781ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q` | 0 | ✅ pass | 4106ms |
| 4 | `backend/venv/bin/python - <<'INNER'
import sys
sys.path.insert(0, 'backend/src')
from admin.api.security_inventory import FIX_FIRST_ADMIN_ROUTE_FAMILIES
from common.monitoring.log_safety_inventory import FIX_FIRST_SENSITIVE_LOG_SURFACES
print({'fix_first_admin_route_families': len(FIX_FIRST_ADMIN_ROUTE_FAMILIES), 'fix_first_sensitive_log_surfaces': len(FIX_FIRST_SENSITIVE_LOG_SURFACES)})
INNER` | 0 | ✅ pass | 959ms |

## Deviations

Local reality differed slightly from the T01 inventory snapshot: `main.py` was already wrapping most of the legacy admin routers in `dependencies=[Depends(get_current_admin_user)]`, so the live app often looked safe even though the router modules themselves still declared only `get_current_user`. Rather than widen scope into a routing refactor, I tightened the module-level dependencies and added isolated-router proof so the boundary is explicit and reuse-safe. I also found that `release_verification_router` is imported in `main.py` but not currently mounted; I still hardened its module-level dependency and covered it with the same isolated-router proof instead of changing product exposure in this task.

## Known Issues

The repo-root pytest commands in this harness still emit the pre-existing pytest-cov warning `Failed to generate report: No data to report.` even when the tests pass; the security gate stays trustworthy because the command exits 0 and all targeted assertions are green. Also, `release_verification_router` remains unmounted in `backend/src/main.py`, so its new admin guard is currently proven through the isolated-router regression test rather than an app-mounted runtime path.

## Files Created/Modified

- `backend/src/common/monitoring/logger.py`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/admin/api/admin.py`
- `backend/src/admin/api/analytics.py`
- `backend/src/admin/api/release_verification.py`
- `backend/src/admin/api/system_logs.py`
- `backend/src/admin/api/training_records.py`
- `backend/src/admin/api/security_inventory.py`
- `backend/src/common/monitoring/log_safety_inventory.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_admin_users_api_models.py`

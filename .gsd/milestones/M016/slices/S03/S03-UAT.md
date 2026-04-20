# S03: RBAC、敏感日志与 admin 安全面 audit — UAT

**Milestone:** M016
**Written:** 2026-04-11T20:40:03.985Z

# S03 UAT — admin RBAC baseline and sensitive-log redaction

## Preconditions
- Repository state includes the S03 changes.
- Python dependencies are installed in `backend/venv`.
- Run commands from repo root: `/Users/zhaozengqing/github/销售训练qoder`.

## Test Case 1 — Repaired legacy admin routers deny non-admin callers even without `main.py` wrapper guards
1. Run:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_security_baseline_inventory_is_closed_and_scoped or admin_router_modules_require_admin_even_without_main_router_guard" -q
   ```
2. Confirm the selected tests pass.
3. Inspect the test names in the output and verify they cover the repaired legacy route families (`admin.py`, `analytics.py`, `release_verification.py`, `system_logs.py`, `training_records.py`) plus the inventory-scope baseline assertion.

**Expected outcome**
- Pytest exits `0`.
- The selected tests pass, proving non-admin callers still receive the structured `403 [ROLE_REQUIRED]` denial even when the routers are mounted on an isolated FastAPI app without `main.py`-level guards.
- The inventory-scope assertion confirms the fix-first admin list is closed and the remaining watch surfaces are intentionally tracked.

## Test Case 2 — Shared logger redacts sensitive fields before sink emission
1. Run:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "structured_logger_masks_sensitive_fields_before_sink_emission or sensitive_log_security_baseline_inventory_is_closed_and_scoped" -q
   ```
2. Confirm the selected tests pass.
3. Verify the test scope covers both sink-level emission proof and inventory-scope proof.

**Expected outcome**
- Pytest exits `0`.
- The sink-level test proves `StructuredLogger` masks/redacts `token`, `password`, `cookie`, and `email` fields — including nested metadata — before the underlying logger sees them.
- The inventory-scope assertion confirms the fix-first sensitive-log list is closed and the remaining watch surfaces are intentionally tracked.

## Test Case 3 — Full slice regression gate stays green
1. Run the exact slice-plan verification command:
   ```bash
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
   ```
2. Wait for completion.

**Expected outcome**
- Pytest exits `0`.
- All tests in the focused integration + unit bundle pass (`36 passed` on the current branch).
- The only acceptable noise is the known repo-root `pytest-cov` warning `Failed to generate report: No data to report.`; no assertion failures or collection errors are allowed.

## Test Case 4 — Code-owned inventories expose the current baseline explicitly
1. Run:
   ```bash
   backend/venv/bin/python - <<'PY'
   import sys
   sys.path.insert(0, 'backend/src')
   from admin.api.security_inventory import (
       FIX_FIRST_ADMIN_ROUTE_FAMILIES,
       ADMIN_PERMISSION_POSITIVE_CONTROL,
       ADMIN_ROUTE_PERMISSION_MATRIX,
   )
   from common.monitoring.log_safety_inventory import (
       FIX_FIRST_SENSITIVE_LOG_SURFACES,
       SENSITIVE_LOG_POSITIVE_CONTROL,
       SENSITIVE_LOG_SURFACES,
   )
   print({
       'fix_first_admin_route_families': len(FIX_FIRST_ADMIN_ROUTE_FAMILIES),
       'watch_routes': sorted(entry.route_family for entry in ADMIN_ROUTE_PERMISSION_MATRIX if entry.priority == 'watch'),
       'positive_control': ADMIN_PERMISSION_POSITIVE_CONTROL,
       'fix_first_sensitive_log_surfaces': len(FIX_FIRST_SENSITIVE_LOG_SURFACES),
       'watch_logs': sorted(surface.surface for surface in SENSITIVE_LOG_SURFACES if surface.priority == 'watch'),
       'log_positive_control': SENSITIVE_LOG_POSITIVE_CONTROL,
   })
   PY
   ```
2. Review the printed structure.

**Expected outcome**
- `fix_first_admin_route_families` is `0`.
- `fix_first_sensitive_log_surfaces` is `0`.
- The watch lists remain explicit and readable for future audits.
- `admin.api.users` remains the admin positive-control seam and `admin.api.users._queue_user_audit_log` remains the masked logging positive control.

## Edge Cases To Confirm
- `release_verification_router` is currently validated through isolated-router proof rather than app-mounted runtime proof; this is acceptable for S03 because the router is hardened at module level and not currently mounted in `backend/src/main.py`.
- Not every inventory entry with `priority="watch"` should map to the same runtime deny-path test. Some watch entries are repaired router families; others are already-correct admin positive controls that stay tracked for future follow-up.
- The lexical grep gate from the slice plan intentionally matches inventory files and non-secret telemetry names; use the code-owned inventories, not grep output alone, to decide whether a real security regression exists.

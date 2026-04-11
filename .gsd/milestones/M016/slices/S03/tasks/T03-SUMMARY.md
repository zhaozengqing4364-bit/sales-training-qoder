---
id: T03
parent: S03
milestone: M016
key_files:
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/unit/admin/test_admin_users_api_models.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep the admin baseline proof split between the explicit isolated-router subset and `ADMIN_PERMISSION_POSITIVE_CONTROL` instead of assuming every inventory `watch` entry should map to the same runtime test.
duration: 
verification_result: passed
completed_at: 2026-04-11T20:36:04.178Z
blocker_discovered: false
---

# T03: Added focused admin-security baseline proof for isolated-router RBAC, sink-level log redaction, and inventory scope.

**Added focused admin-security baseline proof for isolated-router RBAC, sink-level log redaction, and inventory scope.**

## What Happened

I deepened the existing S03 proof instead of widening the repair surface. In `backend/tests/integration/test_admin_users_api.py`, I tied the isolated-router deny checks to a named `ADMIN_SECURITY_BASELINE_WATCH_ROUTE_PROOFS` subset and added an inventory-scope assertion that locks the current admin baseline shape: the fix-first route-family list is now empty, the five repaired legacy router families stay on the explicit isolated proof path, `admin.api.users` remains the baseline positive control, and the remaining already-correct admin families are tracked separately through `ADMIN_PERMISSION_POSITIVE_CONTROL` instead of being conflated with the repaired router subset. In `backend/tests/unit/admin/test_admin_users_api_models.py`, I added sink-boundary proof for `StructuredLogger.info(...)` so the task no longer relies only on helper-level sanitizer tests; the new assertion proves trace_id preservation plus masking/redaction of email/token/cookie fields before the shared logger emits anything. I also added a sensitive-log inventory-scope assertion so the current covered-vs-watch list is encoded in tests and future edits have to update the inventory deliberately. Finally, I wrote one knowledge entry documenting the non-obvious inventory split: `priority="watch"` mixes the isolated-router proof subset with already-correct positive controls, so future agents should separate those two cases instead of assuming the whole bucket maps to one runtime test.

## Verification

I ran the new focused admin-RBAC/inventory subset with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_security_baseline_inventory_is_closed_and_scoped or admin_router_modules_require_admin_even_without_main_router_guard" -q`; it finished 6 selected tests green and proved the repaired router subset still rejects non-admin callers even when mounted without `main.py` wrapper guards while the inventory shape stays explicit. I ran the new sink-redaction/inventory subset with `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "structured_logger_masks_sensitive_fields_before_sink_emission or sensitive_log_security_baseline_inventory_is_closed_and_scoped" -q`; it finished 2 selected tests green and proved the shared logger masks/redacts sensitive fields at the actual sink boundary while the current log-surface baseline remains closed. I then ran the exact task-plan gate `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q`; it finished 36/36 green. Fresh LSP diagnostics for `backend/tests/integration/test_admin_users_api.py` and `backend/tests/unit/admin/test_admin_users_api_models.py` reported no diagnostics. The repo-root pytest-cov `No data to report` warning still appears on these commands, but the gate remains trustworthy because exit codes were 0 and all targeted assertions passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_security_baseline_inventory_is_closed_and_scoped or admin_router_modules_require_admin_even_without_main_router_guard" -q` | 0 | ✅ pass | 3375ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "structured_logger_masks_sensitive_fields_before_sink_emission or sensitive_log_security_baseline_inventory_is_closed_and_scoped" -q` | 0 | ✅ pass | 2133ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q` | 0 | ✅ pass | 4555ms |

## Deviations

I adapted the planned baseline-scope proof to local reality after the first failing assertion showed that `security_inventory.py` intentionally uses `priority="watch"` for two different groups: the five repaired legacy router families covered by the isolated-router regression tests, and several already-correct admin positive controls that are only being tracked for later follow-up. I preserved the task scope by splitting those groups in the proof instead of trying to widen runtime coverage or rewrite the inventory model.

## Known Issues

The repo-root pytest commands in this harness still emit the pre-existing pytest-cov warning `Failed to generate report: No data to report.` even when the focused subsets and exact task gate pass. Also, this task intentionally keeps the runtime-focused router proof scoped to the repaired five-family subset plus the `admin.api.users` positive control; other already-correct admin families remain inventory-tracked follow-up surfaces rather than new runtime coverage in this task.

## Files Created/Modified

- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/unit/admin/test_admin_users_api_models.py`
- `.gsd/KNOWLEDGE.md`

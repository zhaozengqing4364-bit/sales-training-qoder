---
id: S03
parent: M016
milestone: M016
provides:
  - A reusable admin RBAC matrix that future agents can inspect before widening security work.
  - A shared logger redaction seam for token/password/cookie/email across auth and monitoring paths.
  - Focused regression proof that distinguishes repaired watch-list route families from already-correct positive controls.
requires:
  - slice: M016/S01
    provides: Formalized password-reset/auth recovery seam and auth dependency contract that S03 reuses for structured admin deny paths.
  - slice: M016/S02
    provides: Structured API/auth error contract so S03 RBAC denials continue to surface stable `detail={error,message}` payloads.
affects:
  - M016 milestone validation/close-out
  - Future admin security audit slices
  - Backend auth and monitoring observability seams
key_files:
  - backend/src/admin/api/security_inventory.py
  - backend/src/common/monitoring/log_safety_inventory.py
  - backend/src/common/monitoring/logger.py
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/tests/integration/test_admin_users_api.py
  - backend/tests/unit/admin/test_admin_users_api_models.py
key_decisions:
  - D194 — Prioritize the five legacy get_current_user admin route families plus the shared monitoring/auth log sinks as the first S03 repair group.
  - D195 — Enforce fix-first admin RBAC in router modules themselves and centralize sensitive-field redaction in the shared structured logger instead of relying on main.py wrapper dependencies or route-local masking.
  - D196 — Split admin security baseline proof between the repaired isolated-router watch subset and already-correct positive controls instead of forcing every watch entry into the same runtime test.
patterns_established:
  - Use code-owned inventory modules to bound security work before changing runtime code.
  - Put admin-only RBAC on router modules themselves so reuse outside `main.py` cannot silently weaken access control.
  - Redact token/password/cookie/email at the shared structured-logger sink and keep auth paths emitting structured fields instead of stringified exceptions.
observability_surfaces:
  - `backend/src/admin/api/security_inventory.py` — admin route permission matrix, watch list, and positive-control seam.
  - `backend/src/common/monitoring/log_safety_inventory.py` — sensitive-log sink inventory, watch list, and masked positive control.
  - Focused backend proof in `backend/tests/integration/test_admin_users_api.py` and `backend/tests/unit/admin/test_admin_users_api_models.py` for isolated-router denial, sink-level redaction, and inventory-scope closure.
drill_down_paths:
  - .gsd/milestones/M016/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M016/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M016/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T20:40:03.985Z
blocker_discovered: false
---

# S03: RBAC、敏感日志与 admin 安全面 audit

**Closed the first high-risk admin security baseline by making legacy admin routers self-guarding, centralizing structured-log redaction for token/password/cookie/email, and locking the resulting scope with code-owned inventories plus focused proof.**

## What Happened

## What this slice delivered

S03 turned the last M016 security-hardening goal into an explicit backend baseline instead of a one-off audit.

1. **Code-owned scope instead of ad hoc scanning.** `backend/src/admin/api/security_inventory.py` now records the admin route permission matrix, and `backend/src/common/monitoring/log_safety_inventory.py` records the sensitive-log sink inventory. That baseline kept the slice focused on the first real risk cluster: the five legacy `/admin` router families that still depended on generic authentication semantics plus the shared monitoring/auth log sinks that could leak token/password/cookie/email fields.
2. **Module-level RBAC hardening on the fix-first admin surfaces.** `backend/src/admin/api/admin.py`, `analytics.py`, `release_verification.py`, `system_logs.py`, and `training_records.py` now declare `Depends(get_current_admin_user)` in the router modules themselves. This removes the old dependency on `main.py` wrapper wiring and makes the permission boundary explicit even if those routers are mounted elsewhere later.
3. **Shared sink-level sensitive-field redaction.** `backend/src/common/monitoring/logger.py` is now the central redaction seam for token/password/cookie/email fields, including nested structured metadata. `backend/src/common/auth/api.py` and `backend/src/common/auth/service.py` were aligned to emit structured auth/error fields instead of stringified credential-path exceptions or raw email output, so the auth and monitoring paths stay observable without leaking sensitive values.
4. **Focused proof and explicit boundary mapping.** `backend/tests/integration/test_admin_users_api.py` now proves the repaired router families reject non-admin callers even when mounted on an isolated FastAPI app without `main.py` guards. `backend/tests/unit/admin/test_admin_users_api_models.py` now proves `StructuredLogger` redacts sensitive fields at the actual sink boundary. The inventory scope is also asserted in tests so the fix-first lists stay closed and future changes must update the inventories deliberately.

## Why this matters downstream

This slice gives future agents one stable answer to two common security questions:
- **“Is this an admin-boundary regression or just router mounting noise?”** Check the permission matrix plus the isolated-router proof subset.
- **“Is this a call-site logging leak or a shared sink issue?”** Check the log-safety inventory plus the `StructuredLogger` sink proof before editing individual callers.

That keeps later security work from expanding into a blind backend-wide audit and preserves the M016 rule that auth/API/admin hardening should stay on the highest-risk seams.

## Operational Readiness (Q8)

- **Health signal:** the slice gate passes end-to-end; the code-owned inventories report zero remaining `fix-first` admin route families and zero remaining `fix-first` sensitive-log sinks; focused tests prove isolated-router RBAC denial and sink-level redaction.
- **Failure signal:** if a legacy admin router falls back to `get_current_user`, the isolated-router deny tests fail; if token/password/cookie/email values bypass the shared logger sanitizer, the sink-redaction tests fail; if someone reclassifies or widens the baseline silently, the inventory-scope assertions fail.
- **Recovery procedure:** inspect `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py` first, restore module-level `get_current_admin_user` on the affected router or restore shared logger sanitization/structured auth logging, then rerun the exact slice gate plus the inventory import check.
- **Monitoring gaps:** S03 intentionally does not widen runtime proof to every watch-only admin family; some already-correct admin routes stay tracked as positive controls rather than new deny-path tests. `release_verification_router` is hardened at module level but is still proven through isolated-router coverage because it is not currently mounted in `backend/src/main.py`.


## Verification

- Ran the slice-plan gate exactly as written: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q` → **36 passed**.
- Ran a fresh inventory import/inspection check from the backend runtime to confirm the fix-first lists are closed: `fix_first_admin_route_families=0`, `fix_first_sensitive_log_surfaces=0`, with the remaining route/log surfaces explicitly tracked in the watch lists and positive-control constants.
- Ran fresh LSP diagnostics on `backend/tests/integration/test_admin_users_api.py`, `backend/tests/unit/admin/test_admin_users_api_models.py`, `backend/src/admin/api/security_inventory.py`, `backend/src/common/monitoring/log_safety_inventory.py`, `backend/src/common/monitoring/logger.py`, and `backend/src/common/auth/api.py` → no diagnostics.
- Non-blocking note: the repo-root pytest command still emits the known `pytest-cov` "No data to report" warning, but the gate exited 0 and all targeted assertions passed.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- No new requirement IDs were surfaced; S03 hardened the existing M016 security baseline on admin RBAC and sensitive logging without changing the current requirement set.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

S03 intentionally covers only the first high-risk admin/logging seam, not every admin route family or every possible structured-log caller. Some already-correct admin routes remain watch-listed rather than newly runtime-tested, and `release_verification_router` is still validated through isolated-router proof because it is not mounted in `backend/src/main.py`.

## Follow-ups

Use the watch lists in `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py` as the next-entry inventory if future slices widen admin security coverage. Keep new admin router work on module-level `get_current_admin_user` dependencies and keep new sensitive-field protection at the shared logger boundary rather than adding route-local masking.

## Files Created/Modified

- `backend/src/admin/api/security_inventory.py` — Added the code-owned admin permission matrix, watch-list boundary, and positive-control constants for S03.
- `backend/src/common/monitoring/log_safety_inventory.py` — Added the code-owned sensitive-log sink inventory, watch-list boundary, and logging positive control for S03.
- `backend/src/common/monitoring/logger.py` — Centralized recursive token/password/cookie/email redaction in the shared structured logger.
- `backend/src/common/auth/api.py` — Replaced raw-email/stringified auth failure logging with structured fields that flow through the shared sanitizer.
- `backend/src/common/auth/service.py` — Aligned auth verification logging and stale notes with the new structured, redacted logging contract.
- `backend/tests/integration/test_admin_users_api.py` — Added isolated-router RBAC deny-path proof and inventory-scope assertions for the admin security baseline.
- `backend/tests/unit/admin/test_admin_users_api_models.py` — Added sink-level structured logger redaction proof and sensitive-log inventory-scope assertions.

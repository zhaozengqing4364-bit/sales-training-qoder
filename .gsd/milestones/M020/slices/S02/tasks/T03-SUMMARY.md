---
id: T03
parent: S02
milestone: M020
key_files:
  - backend/src/admin/api/security_inventory.py
  - backend/src/common/monitoring/log_safety_inventory.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D223 — future admin/support quality-event surfaces must reuse the backend-owned allowlist diagnostics contract and keep raw provider/request/config details backend-only.
duration: 
verification_result: passed
completed_at: 2026-04-13T15:15:15.397Z
blocker_discovered: false
---

# T03: Codified the admin/support log redaction boundary into code-owned inventories and the architecture scan, including the M021 quality-event constraint.

**Codified the admin/support log redaction boundary into code-owned inventories and the architecture scan, including the M021 quality-event constraint.**

## What Happened

I turned the shipped logger/API/UI redaction contract from T01-T02 into durable inventory language instead of leaving it implicit in runtime code. In `backend/src/admin/api/security_inventory.py` I added explicit admin/support visibility constants for the safe diagnostics allowlist (`trace_id`, `error_code`, `phase`, `session_id`, `target_user_id`), the backend-only detail classes (raw `details`, precise identifiers, provider/request/response payloads, prompt text, secrets, stack traces), and a support-facing guidance string that says admin/support must treat backend-supplied diagnostics as the only safe error-details surface. In `backend/src/common/monitoring/log_safety_inventory.py` I mirrored the same boundary as a shared observability rule, named the three surfaces that must stay aligned (`StructuredLogger`, `system_logs` API, and the admin logs page), and added the downstream M021 rule that future quality/cost/failure events must inherit this redaction boundary instead of inventing a second support payload. I then updated `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with a new M020/S02 section that explains the authority seam, the allowlist vs backend-only split, the support inspection rule, and the fact that M021/S04 quality events may surface degraded/failure diagnostics but must not surface raw provider/request/config secrets. I also recorded D223 in `.gsd/DECISIONS.md` and synced `.codex/loop/state.json` plus `.codex/loop/log.md` so the next turn sees this task as the latest completed continuity point.

## Verification

I reran the exact task-plan verification gate `rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, and it passed with the new allowlist/redaction/support wording visible in both code-owned inventories and the architecture scan. I also ran `backend/venv/bin/python -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py` to prove the updated inventory modules are syntactically valid Python. Fresh LSP diagnostics for `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py` returned no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` | 0 | ✅ pass | 25ms |
| 2 | `backend/venv/bin/python -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py` | 0 | ✅ pass | 60ms |

## Deviations

Added a small py_compile + LSP sanity check beyond the plan’s grep-only gate so the new code-owned inventories are not only grep-discoverable but also syntactically valid and diagnostics-clean.

## Known Issues

`/api/v1/admin/system-logs` access is still admin-only. This task codifies the redaction/exposure contract that any future support-facing observability surface must reuse; it does not introduce a separate support-role route.

## Files Created/Modified

- `backend/src/admin/api/security_inventory.py`
- `backend/src/common/monitoring/log_safety_inventory.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

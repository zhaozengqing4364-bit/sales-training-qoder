---
id: S02
parent: M020
milestone: M020
provides:
  - A single backend-owned admin/support log redaction contract shared by the logger, system-log API, and admin logs UI.
  - Focused backend/frontend proof that safe diagnostics remain visible while raw details and precise identifiers stay out of admin/support surfaces.
  - Inventory and architecture guidance that future M020/M021 observability work must reuse instead of inventing a second support payload.
requires:
  []
affects:
  - S03
  - S04
key_files:
  - backend/src/common/monitoring/logger.py
  - backend/src/admin/api/system_logs.py
  - web/src/app/admin/logs/page.tsx
  - web/src/lib/api/types.ts
  - backend/src/admin/api/security_inventory.py
  - backend/src/common/monitoring/log_safety_inventory.py
  - backend/tests/unit/admin/test_system_logs_redaction.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/app/admin/logs/page.test.tsx
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
key_decisions:
  - D221 — adopt an allowlist-first admin log exposure policy that masks identifiers, strips raw details from API/UI exposure, and keeps only safe diagnostics visible.
  - D222 — expose ordered backend-owned `diagnostics` plus `policy.diagnostic_fields` from the API, and require the admin logs UI to render that contract directly.
  - D223 — require future admin/support quality-event surfaces to reuse the same diagnostics contract and keep raw provider/request/config details backend-only.
patterns_established:
  - Keep sensitive-log visibility in one backend-owned seam (`backend/src/common/monitoring/logger.py`) and let downstream API/UI layers render, not reinterpret, the policy.
  - Use allowlist-first admin/support diagnostics: preserve `trace_id`/`error_code`/`phase`/`session_id`/`target_user_id` for triage while treating raw identifiers, payloads, prompts, and secrets as backend-only.
  - Write the redaction boundary into code-owned inventory artifacts and architecture scan guidance so future observability work inherits the same safe exposure rules.
observability_surfaces:
  - `GET /api/v1/admin/system-logs` policy metadata (`version`, `allowed_detail_keys`, `diagnostic_fields`).
  - Per-log ordered `diagnostics[]` contract and safe `details` summary in the admin system-log API.
  - `/admin/logs` masked identity display plus backend-supplied diagnostics rendering.
  - Code-owned redaction inventories in `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py`.
drill_down_paths:
  - .gsd/milestones/M020/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M020/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M020/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T15:28:06.552Z
blocker_discovered: false
---

# S02: Sensitive log 与 admin observability redaction 收口

**Unified logger, admin system-log API, and admin logs UI behind one allowlist-first redaction policy so support/admin keep traceable diagnostics without exposing raw details, precise identifiers, or secret-adjacent payloads.**

## What Happened

# S02: Sensitive log 与 admin observability redaction 收口

**Unified logger, admin system-log API, and admin logs UI behind one backend-owned allowlist-first redaction policy so support/admin keep usable diagnostics without seeing raw `details`, precise identifiers, or secret-adjacent payloads.**

## What Happened

S02 started by inventorying the real leakage boundary instead of assuming the logger was already sufficient. T01 proved that `StructuredLogger` only masked credential-shaped keys while `backend/src/admin/api/system_logs.py` and `web/src/app/admin/logs/page.tsx` could still expose raw `user_identifier`, `ip_address`, and `details`. The slice then established `admin_support_redaction_v1` in `backend/src/common/monitoring/logger.py` as the shared authority seam: it now owns the allowlist/denylist constants, masking helpers for identifiers and IPs, safe-detail extraction, and the ordered diagnostics contract (`trace_id`, `error_code`, `phase`, `session_id`, `target_user_id`).

T02 carried that same contract through the shipped API/UI surfaces instead of letting each layer reinterpret policy. `backend/src/admin/api/system_logs.py` now serializes log rows into masked top-level fields plus a pre-redacted ordered `diagnostics` list and returns `policy.version`, `policy.allowed_detail_keys`, and `policy.diagnostic_fields` so the backend response itself describes what admin/support may see. `web/src/app/admin/logs/page.tsx` no longer reconstructs visible keys locally; it renders the backend-supplied diagnostics list, the policy banner, masked identities, and the safe details summary string. This means logger → API → UI now share one policy rather than three drifting heuristics.

T03 converted that runtime contract into durable downstream guidance. `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py` now codify the same allowlist/back-end-only boundary, and `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` records the rule that future admin/support observability work — especially M021 quality/cost/failure events — must reuse the same diagnostics contract rather than inventing a second support payload. D221, D222, and D223 capture the key decisions: allowlist-first masking, backend-owned ordered diagnostics, and a single reusable redaction boundary for future support surfaces.

This slice establishes three reusable patterns for the rest of M020/M021. First, sensitive observability fields are governed by one backend-owned policy seam, not page-local filtering. Second, admin/support visibility is allowlist-first: safe diagnostics stay visible, but raw provider/request/config/prompt/secret context remains backend-only. Third, inventory and architecture artifacts now explicitly constrain downstream work, so future slices can extend observability without reopening this leakage boundary.

## Operational Readiness

- **Health signal:** `GET /api/v1/admin/system-logs` returns `policy.version=admin_support_redaction_v1`, exposes `policy.diagnostic_fields`, and each row contains masked `user_identifier` / coarse `ip_address` plus ordered safe `diagnostics`; the admin logs page renders those diagnostics and never needs to guess which fields are safe.
- **Failure signal:** raw `details`, exact identifiers/IPs, or secret-adjacent fields appearing in `/api/v1/admin/system-logs` or `/admin/logs` indicate policy drift; the focused backend serializer/API tests and frontend page test are the first-line regression signal for that class of failure.
- **Recovery procedure:** revert to the shared logger allowlist/denylist constants in `backend/src/common/monitoring/logger.py`, confirm `system_logs.py` still serializes only backend-owned diagnostics, rerun `backend/tests/unit/admin/test_system_logs_redaction.py`, `backend/tests/integration/test_admin_users_api.py`, `backend/tests/unit/admin/test_admin_users_api_models.py`, and `web/src/app/admin/logs/page.test.tsx`, then inspect backend-controlled logs for any raw-detail need instead of widening the admin/support payload.
- **Monitoring gaps:** `/api/v1/admin/system-logs` remains admin-only, not a separate support-role surface; search semantics still query raw persisted `SystemLog.user_identifier` while the UI displays masked identifiers; and there is not yet a live production detector beyond focused tests/inventory review if a new admin/support surface bypasses the shared diagnostics contract.


## Verification

Fresh slice-close verification reran every slice-plan gate and passed. Required task-plan runtime gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"` ✅ pass (37 backend tests + 1 frontend test). Required inventory/documentation gate 1: `rg -n "token|password|cookie|email|user_identifier|ip_address|details" backend/src/common/monitoring backend/src/admin/api web/src/app/admin/logs/page.tsx` ✅ pass. Required inventory/documentation gate 2: `rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` ✅ pass. Additional focused observability proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py -q` ✅ pass. Fresh LSP diagnostics were clean on `backend/src/common/monitoring/logger.py`, `backend/src/admin/api/system_logs.py`, `backend/src/admin/api/security_inventory.py`, `backend/src/common/monitoring/log_safety_inventory.py`, `web/src/app/admin/logs/page.tsx`, `web/src/lib/api/types.ts`, `backend/tests/unit/admin/test_system_logs_redaction.py`, and `web/src/app/admin/logs/page.test.tsx`. Only pre-existing pytest-cov no-data warnings and upstream Python 3.14 dependency deprecation warnings remained.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

`/api/v1/admin/system-logs` search still filters by raw persisted `SystemLog.user_identifier` while the API/UI display only masked identifiers. The route is still admin-only rather than a dedicated support-role surface, and runtime drift detection still relies primarily on focused tests plus the codified inventory.

## Follow-ups

M020/S03 should treat this logger/API/UI diagnostics contract as fixed while it hardens reconnect/session-state authority. M020/S04 and later M021 observability work should reuse the same allowlist-first diagnostics seam for recovery/quality/failure events instead of inventing a second support payload.

## Files Created/Modified

- `backend/src/common/monitoring/logger.py` — Added the backend-owned allowlist/denylist policy, masking helpers, and ordered diagnostics extraction for admin/support log views.
- `backend/src/admin/api/system_logs.py` — Serialized log rows through the shared redaction policy and exposed policy metadata plus ordered `diagnostics` in the API contract.
- `web/src/app/admin/logs/page.tsx` — Rendered the backend-supplied diagnostics contract directly and showed masked identifiers plus safe detail summaries.
- `web/src/lib/api/types.ts` — Typed the new admin system-log diagnostics and policy metadata contract.
- `backend/src/admin/api/security_inventory.py` — Codified the admin/support allowlist vs backend-only detail boundary for future observability work.
- `backend/src/common/monitoring/log_safety_inventory.py` — Recorded the shared logger/API/UI redaction rule and downstream M021 reuse constraint.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Documented the shipped redaction authority seam and the rule that future quality-event surfaces must reuse it.

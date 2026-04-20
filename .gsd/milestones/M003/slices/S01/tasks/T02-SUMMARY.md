---
id: T02
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: [".gsd/milestones/M003/M003-ROADMAP.md", ".gsd/milestones/M003/slices/S01/S01-PLAN.md", ".gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md", ".gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md", ".gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md", ".gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Treat `build_session_runtime_diagnostics(...).status` as the only current learner/admin-visible knowledge-status contract; keep KB-lock `blocked_*` states and retrieval detail like `hit_keyword_fallback` in diagnostic fields instead of promoting them to report status.", "Use escaped literal Next.js paths in M003 S01 `test -f` verifier commands, and refresh the generated `T##-VERIFY.json` artifact when a failed gate already captured the old broken command form."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the slice-level file-existence verifier with escaped literal Next.js paths and confirmed all current admin/runtime/report/replay authority files exist. Ran the T02 status grep across runtime diagnostics, the KB-lock guard, the internal searcher, and the M003 roadmap/slice/task docs to confirm the locked vocabulary is present in code and planning artifacts. Ran the slice out-of-scope / blocker grep to confirm the current-route and inventory/spike boundaries remain explicit. Ran an extra ownership grep for `hit_keyword_fallback`, `last_status`, `kb_lock_status`, and `kb_lock_last_status` to prove the new doc wording matches the real runtime-detail fields."
completed_at: 2026-03-25T01:51:45.861Z
blocker_discovered: false
---

# T02: Locked M003’s live knowledge-status contract to the current report/runtime vocabulary and retired the stale T01 verifier failure.

> Locked M003’s live knowledge-status contract to the current report/runtime vocabulary and retired the stale T01 verifier failure.

## What Happened
---
id: T02
parent: S01
milestone: M003
key_files:
  - .gsd/milestones/M003/M003-ROADMAP.md
  - .gsd/milestones/M003/slices/S01/S01-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Treat `build_session_runtime_diagnostics(...).status` as the only current learner/admin-visible knowledge-status contract; keep KB-lock `blocked_*` states and retrieval detail like `hit_keyword_fallback` in diagnostic fields instead of promoting them to report status.
  - Use escaped literal Next.js paths in M003 S01 `test -f` verifier commands, and refresh the generated `T##-VERIFY.json` artifact when a failed gate already captured the old broken command form.
duration: ""
verification_result: passed
completed_at: 2026-03-25T01:51:45.862Z
blocker_discovered: false
---

# T02: Locked M003’s live knowledge-status contract to the current report/runtime vocabulary and retired the stale T01 verifier failure.

**Locked M003’s live knowledge-status contract to the current report/runtime vocabulary and retired the stale T01 verifier failure.**

## What Happened

Read `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/common/knowledge/kb_lock_guard.py`, `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/src/common/api/practice.py`, and `web/src/app/(user)/practice/[sessionId]/report/page.tsx` to pin the real ownership line before touching the docs. The confirmed learner/admin contract is `build_session_runtime_diagnostics(...).status`, which surfaces exactly `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, and `hit` on knowledge-check/report inspection. KB-lock `blocked_no_kb` / `blocked_not_ready` / `blocked_search_failed` / `blocked_empty` stay on `kb_lock_status` / `kb_lock_last_status`, and lower-level retrieval detail like `hit_keyword_fallback` stays on `runtime_metrics.knowledge_retrieval.last_status` rather than expanding the current report status vocabulary.

With that confirmed, I rewrote `.gsd/milestones/M003/M003-ROADMAP.md`, `.gsd/milestones/M003/slices/S01/S01-PLAN.md`, and `.gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` so S01 now explicitly documents the seven learner/admin-visible statuses, the runtime-only blocked diagnostics, and the fact that richer unsupported / evidence-pending / evidence-backed claim truth remains downstream M003 work instead of a current S01 product contract.

The verification gate failure turned out to be a stale artifact problem, not a code mismatch: `.gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json` still contained the pre-fix bare `web/src/app/(user)...` commands, and `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` still had an unescaped future verifier. I hardened the M003 S01 file-existence commands to use escaped literal Next.js paths, refreshed `T01-VERIFY.json` with fresh passing results, and appended the VERIFY-artifact gotcha to `.gsd/KNOWLEDGE.md` so later auto-mode turns do not keep replaying an already-fixed shell failure.

## Verification

Ran the slice-level file-existence verifier with escaped literal Next.js paths and confirmed all current admin/runtime/report/replay authority files exist. Ran the T02 status grep across runtime diagnostics, the KB-lock guard, the internal searcher, and the M003 roadmap/slice/task docs to confirm the locked vocabulary is present in code and planning artifacts. Ran the slice out-of-scope / blocker grep to confirm the current-route and inventory/spike boundaries remain explicit. Ran an extra ownership grep for `hit_keyword_fallback`, `last_status`, `kb_lock_status`, and `kb_lock_last_status` to prove the new doc wording matches the real runtime-detail fields.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/knowledge/kb_lock_guard.py && test -f backend/src/common/conversation/runtime_diagnostics.py && test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx` | 0 | ✅ pass | 4ms |
| 2 | `rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` | 0 | ✅ pass | 19ms |
| 3 | `rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` | 0 | ✅ pass | 8ms |
| 4 | `rg -n "hit_keyword_fallback|last_status|kb_lock_status|kb_lock_last_status" backend/src/common/conversation/runtime_diagnostics.py backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` | 0 | ✅ pass | 6ms |


## Deviations

Extended the planned doc rewrite to refresh the stale `.gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json` artifact and to harden the T01/T03 file-existence verifier commands with escaped literal Next.js paths so auto-mode would stop replaying a false failure.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M003/M003-ROADMAP.md`
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json`
- `.gsd/KNOWLEDGE.md`


## Deviations
Extended the planned doc rewrite to refresh the stale `.gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json` artifact and to harden the T01/T03 file-existence verifier commands with escaped literal Next.js paths so auto-mode would stop replaying a false failure.

## Known Issues
None.

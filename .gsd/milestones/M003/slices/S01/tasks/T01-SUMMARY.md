---
id: T01
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: [".gsd/milestones/M003/M003-ROADMAP.md", ".gsd/milestones/M003/slices/S01/S01-PLAN.md", ".gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Treat `POST /api/v1/practice/sessions` plus `web/src/app/(user)/practice/[sessionId]/page.tsx` as the canonical M003 business entry seam between admin configuration and learner-visible runtime/read surfaces.", "Keep planning verification commands shell-runnable by quoting literal Next.js file paths that contain `[]` or `()`."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-level verification commands from `T01-PLAN.md` and the slice-level verification commands from `S01-PLAN.md`. All five final checks exited 0: the confirmed backend/frontend entrypoint files exist, the roadmap/slice/task docs now mention the real business chain (`POST /api/v1/practice/sessions` plus the learner practice/report/replay paths), the live knowledge status vocabulary remains aligned with current code, and the out-of-scope / inventory-spike boundary language is present in the milestone docs."
completed_at: 2026-03-25T01:37:18.630Z
blocker_discovered: false
---

# T01: Locked M003 on the real admin→session→practice entry chain and made the doc verifiers runnable.

> Locked M003 on the real admin→session→practice entry chain and made the doc verifiers runnable.

## What Happened
---
id: T01
parent: S01
milestone: M003
key_files:
  - .gsd/milestones/M003/M003-ROADMAP.md
  - .gsd/milestones/M003/slices/S01/S01-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Treat `POST /api/v1/practice/sessions` plus `web/src/app/(user)/practice/[sessionId]/page.tsx` as the canonical M003 business entry seam between admin configuration and learner-visible runtime/read surfaces.
  - Keep planning verification commands shell-runnable by quoting literal Next.js file paths that contain `[]` or `()`.
duration: ""
verification_result: passed
completed_at: 2026-03-25T01:37:18.632Z
blocker_discovered: false
---

# T01: Locked M003 on the real admin→session→practice entry chain and made the doc verifiers runnable.

**Locked M003 on the real admin→session→practice entry chain and made the doc verifiers runnable.**

## What Happened

Confirmed the current business chain in runnable code before changing any planning artifacts. On the admin side, `web/src/app/admin/personas/[id]/page.tsx` loads and saves `persona_policy`, knowledge-base bindings, and tool-policy flags, while `web/src/app/admin/knowledge/[id]/page.tsx` remains the live detail/search surface for KB readiness and diagnostics. On the backend, `POST /api/v1/practice/sessions` in `backend/src/common/api/practice.py` validates the agent/persona pair, calls `VoiceRuntimePolicyService.resolve_effective_policy(...)`, freezes the result into `PracticeSession.voice_policy_snapshot`, and carries that runtime context into the learner flow. `backend/src/agent/services/persona_policy.py` is the persona-policy normalization authority, `backend/src/sales_bot/services/voice_runtime_policy.py` merges persona/agent/profile/KB policy and builds realtime tools, and `backend/src/sales_bot/services/voice_instruction_compiler.py` turns the resolved policy into the stable instruction contract. On the learner side, `web/src/app/(user)/practice/[sessionId]/page.tsx` is the runtime entrypoint, while the report page reads `knowledge-check` and the replay page reads the shared read-side evidence surface. With that seam confirmed, I rewrote `M003-ROADMAP.md`, `S01-PLAN.md`, and `T01-PLAN.md` so they explicitly point at `POST /api/v1/practice/sessions`, `web/src/app/(user)/practice/[sessionId]/page.tsx`, and the current report/replay read surfaces instead of vague “product route” wording. During verification I found a real doc bug: unquoted Next.js literal paths such as `(user)` and `[sessionId]` made the shell examples unrunnable, so I quoted those paths in the runnable plan commands and recorded the gotcha in `.gsd/KNOWLEDGE.md`.

## Verification

Ran the task-level verification commands from `T01-PLAN.md` and the slice-level verification commands from `S01-PLAN.md`. All five final checks exited 0: the confirmed backend/frontend entrypoint files exist, the roadmap/slice/task docs now mention the real business chain (`POST /api/v1/practice/sessions` plus the learner practice/report/replay paths), the live knowledge status vocabulary remains aligned with current code, and the out-of-scope / inventory-spike boundary language is present in the milestone docs.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -lc "test -f 'backend/src/agent/services/persona_policy.py' && test -f 'backend/src/sales_bot/services/voice_runtime_policy.py' && test -f 'backend/src/sales_bot/services/voice_instruction_compiler.py' && test -f 'backend/src/common/api/practice.py' && test -f 'web/src/app/admin/personas/[id]/page.tsx' && test -f 'web/src/app/admin/knowledge/[id]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/report/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/replay/page.tsx'"` | 0 | ✅ pass | 10ms |
| 2 | `rg -n "persona_policy.py|voice_runtime_policy.py|voice_instruction_compiler.py|practice.py|POST /api/v1/practice/sessions|web/src/app/admin/personas/\[id\]/page.tsx|web/src/app/admin/knowledge/\[id\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx|Silence|Conda|\.env|lockfile|inventory/spike" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md` | 0 | ✅ pass | 20ms |
| 3 | `bash -lc "test -f 'backend/src/agent/services/persona_policy.py' && test -f 'backend/src/sales_bot/services/voice_runtime_policy.py' && test -f 'backend/src/sales_bot/services/voice_instruction_compiler.py' && test -f 'backend/src/common/knowledge/kb_lock_guard.py' && test -f 'backend/src/common/conversation/runtime_diagnostics.py' && test -f 'backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py' && test -f 'backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py' && test -f 'backend/src/common/api/practice.py' && test -f 'backend/src/common/conversation/session_evidence.py' && test -f 'web/src/app/admin/personas/[id]/page.tsx' && test -f 'web/src/app/admin/knowledge/[id]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/report/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/replay/page.tsx'"` | 0 | ✅ pass | 10ms |
| 4 | `rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` | 0 | ✅ pass | 10ms |
| 5 | `rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` | 0 | ✅ pass | 5ms |


## Deviations

Extended the planned doc edits to quote literal Next.js route-segment file paths inside verification commands because the unquoted planner version was syntactically invalid in `bash`. No scope change.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M003/M003-ROADMAP.md`
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Extended the planned doc edits to quote literal Next.js route-segment file paths inside verification commands because the unquoted planner version was syntactically invalid in `bash`. No scope change.

## Known Issues
None.

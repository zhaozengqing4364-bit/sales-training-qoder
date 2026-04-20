---
id: T03
parent: S01
milestone: M003
provides: []
requires: []
affects: []
key_files: [".gsd/milestones/M003/M003-ROADMAP.md", ".gsd/milestones/M003/slices/S01/S01-PLAN.md", ".gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Keep session creation, knowledge-check, and report proof on `backend/src/common/api/practice.py`, but bind replay proof to `backend/src/common/conversation/api.py` + `backend/src/common/conversation/replay.py` over `SessionEvidenceService`.", "Limit downstream M003 acceptance to one current-route proof set: focused backend proof, focused web proof, and later live UAT on the same admin -> session -> practice -> knowledge-check/report/replay chain; missing entrypoints force inventory/spike."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-level verifier for the proof-surface file set, then ran the task-level doc grep for focused backend / focused web / live UAT / replay-route wording. After that I ran the full slice verification set: the expanded file-existence check now includes `backend/src/common/conversation/api.py` and `backend/src/common/conversation/replay.py`, the live knowledge-status vocabulary grep still passes, the out-of-scope / inventory-spike grep still passes, and the new proof-boundary grep confirms the roadmap, slice plan, and T03 plan all mention the current report and replay routes plus `SessionEvidenceService`. All final verification commands exited 0."
completed_at: 2026-03-25T02:01:44.790Z
blocker_discovered: false
---

# T03: Bound M003 proof to the live report/knowledge-check/replay routes and locked the inventory/spike blocker.

> Bound M003 proof to the live report/knowledge-check/replay routes and locked the inventory/spike blocker.

## What Happened
---
id: T03
parent: S01
milestone: M003
key_files:
  - .gsd/milestones/M003/M003-ROADMAP.md
  - .gsd/milestones/M003/slices/S01/S01-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep session creation, knowledge-check, and report proof on `backend/src/common/api/practice.py`, but bind replay proof to `backend/src/common/conversation/api.py` + `backend/src/common/conversation/replay.py` over `SessionEvidenceService`.
  - Limit downstream M003 acceptance to one current-route proof set: focused backend proof, focused web proof, and later live UAT on the same admin -> session -> practice -> knowledge-check/report/replay chain; missing entrypoints force inventory/spike.
duration: ""
verification_result: passed
completed_at: 2026-03-25T02:01:44.792Z
blocker_discovered: false
---

# T03: Bound M003 proof to the live report/knowledge-check/replay routes and locked the inventory/spike blocker.

**Bound M003 proof to the live report/knowledge-check/replay routes and locked the inventory/spike blocker.**

## What Happened

I verified the current proof surfaces against real runnable code before tightening the docs. The admin proof surfaces remain `web/src/app/admin/personas/[id]/page.tsx` and `web/src/app/admin/knowledge/[id]/page.tsx`. The learner runtime proof surface remains `web/src/app/(user)/practice/[sessionId]/page.tsx`. On the backend, `POST /api/v1/practice/sessions`, `GET /api/v1/practice/sessions/{id}/report`, and `GET /api/v1/practice/sessions/{id}/knowledge-check` are still owned by `backend/src/common/api/practice.py`, while replay is actually served by `GET /api/v1/sessions/{id}/replay` in `backend/src/common/conversation/api.py`, with `backend/src/common/conversation/replay.py` reading from `SessionEvidenceService`. That ownership split was the only real local mismatch between the planner snapshot and the live code.

With that confirmed, I rewrote the M003 roadmap acceptance boundary, the S01 slice plan, and the T03 task contract so later work is pinned to one accepted proof set on current routes only. The docs now name explicit focused backend proof, focused web proof, and later live UAT boundaries; they call out the exact report and replay routes instead of generic “inspection surfaces”; and they keep the blocker rule explicit that any missing/non-runnable entrypoint stops execution and becomes inventory/spike. I also recorded the ownership split as decision D049 and appended a knowledge note so later M003 tasks do not incorrectly aim replay verification at `practice.py`.

## Verification

Ran the task-level verifier for the proof-surface file set, then ran the task-level doc grep for focused backend / focused web / live UAT / replay-route wording. After that I ran the full slice verification set: the expanded file-existence check now includes `backend/src/common/conversation/api.py` and `backend/src/common/conversation/replay.py`, the live knowledge-status vocabulary grep still passes, the out-of-scope / inventory-spike grep still passes, and the new proof-boundary grep confirms the roadmap, slice plan, and T03 plan all mention the current report and replay routes plus `SessionEvidenceService`. All final verification commands exited 0.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/api.py && test -f backend/src/common/conversation/replay.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx` | 0 | ✅ pass | 3ms |
| 2 | `rg -n "focused backend|focused web|live UAT|/api/v1/practice/sessions/\{id\}/report|/api/v1/sessions/\{id\}/replay|common/conversation/api.py|common/conversation/replay.py|SessionEvidenceService|inventory/spike|blocking rule|current routes" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` | 0 | ✅ pass | 14ms |
| 3 | `test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/knowledge/kb_lock_guard.py && test -f backend/src/common/conversation/runtime_diagnostics.py && test -f backend/src/common/conversation/api.py && test -f backend/src/common/conversation/replay.py && test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx` | 0 | ✅ pass | 3ms |
| 4 | `rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` | 0 | ✅ pass | 15ms |
| 5 | `rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` | 0 | ✅ pass | 13ms |
| 6 | `rg -n "focused backend|focused web|live UAT|/api/v1/practice/sessions/\{id\}/report|/api/v1/sessions/\{id\}/replay|common/conversation/api.py|common/conversation/replay.py|SessionEvidenceService" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` | 0 | ✅ pass | 15ms |


## Deviations

Minor local adaptation: the live replay proof surface is not owned by `backend/src/common/api/practice.py`, so I extended the docs and verifiers to include `backend/src/common/conversation/api.py` and `backend/src/common/conversation/replay.py` instead of pretending replay lives under the practice API.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M003/M003-ROADMAP.md`
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Minor local adaptation: the live replay proof surface is not owned by `backend/src/common/api/practice.py`, so I extended the docs and verifiers to include `backend/src/common/conversation/api.py` and `backend/src/common/conversation/replay.py` instead of pretending replay lives under the practice API.

## Known Issues
None.

---
estimated_steps: 4
estimated_files: 4
skills_used:
  - safe-grow
---

# T02: Define the live knowledge status vocabulary and ownership line

**Slice:** S01 — 真实入口 inventory 与 current knowledge 真值线
**Milestone:** M003

## Description

Define the current live knowledge status vocabulary on the actual business chain rather than inventing a future contract. Map each status to the code that owns it and the route where the user can inspect it: learner/admin-visible statuses from `runtime_diagnostics` and report knowledge-check, plus runtime-only KB-lock block states. Treat `build_session_runtime_diagnostics(...).status` as the current learner/admin contract; lower-level retrieval detail such as `hit_keyword_fallback` may survive in `runtime_metrics.knowledge_retrieval.last_status`, but it is not a current report status. Reserve richer truth such as unsupported / evidence-pending / evidence-backed for later slices instead of pretending those states already exist on the current product surface.

## Steps

1. Inspect the current runtime retrieval helpers and KB-lock guard to capture the exact status names already emitted in code.
2. Inspect `build_session_runtime_diagnostics(...)` and the current report knowledge panel to capture the exact learner/admin-visible status vocabulary.
3. Rewrite the roadmap and slice/task plan so the current live contract uses only confirmed status names and ownership boundaries.
4. Explicitly mark richer claim-truth semantics as downstream M003 work rather than part of S01's locked contract.

## Must-Haves

- [ ] The S01 docs use the current learner/admin-visible status vocabulary: `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, and `miss`/`hit` on `knowledge-check.status`.
- [ ] Runtime-only diagnostics such as `blocked_no_kb`, `blocked_not_ready`, `blocked_search_failed`, and `blocked_empty` are documented as diagnostics, not mislabeled as current user-visible report states.
- [ ] Retrieval-detail states such as `hit_keyword_fallback` are documented as internal/runtime detail (`runtime_metrics.knowledge_retrieval.last_status`), not as extra learner/admin-visible report statuses.

## Verification

- `rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md`

## Inputs

- `backend/src/common/conversation/runtime_diagnostics.py` — current learner/admin-visible knowledge-check vocabulary
- `backend/src/common/knowledge/kb_lock_guard.py` — current KB-lock block vocabulary and grounding gate behavior
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — current retrieval helper payload builders
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — current retrieval result/error status emission
- `backend/src/common/api/practice.py` — current `/practice/sessions/{id}/knowledge-check` inspection route
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — current learner knowledge panel consumer
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — slice contract being rewritten around the live vocabulary

## Expected Output

- `.gsd/milestones/M003/M003-ROADMAP.md` — success criteria and boundary map aligned to current live statuses
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — slice verification and observability sections aligned to current status ownership
- `.gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` — task contract that names only real live statuses and clearly defers richer truth states

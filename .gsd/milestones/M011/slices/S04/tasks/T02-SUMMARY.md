---
id: T02
parent: S04
milestone: M011
provides: []
requires: []
affects: []
key_files: ["backend/src/common/api/knowledge_debug.py", "backend/src/main.py", "backend/tests/integration/test_knowledge_debug_api.py", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M011/slices/S04/tasks/T02-SUMMARY.md"]
key_decisions: ["Read the debug API directly from persisted KnowledgeAnswerRun and KnowledgeAnswerRunStep rows instead of reconstructing traces from runtime-local StepFun state.", "Keep the new inspection surface read-only and restricted to admin/support roles via the existing require_role dependency seam."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the task-plan verification command fresh from repo root and confirmed the new focused integration suite passed 5/5 against list/detail/steps, RBAC, and not-found behaviors. Then ran a follow-up py_compile check on the new router and focused test module, which also passed. Fresh LSP diagnostics reported no issues on backend/src/common/api/knowledge_debug.py and backend/src/main.py."
completed_at: 2026-03-31T05:58:24.676Z
blocker_discovered: false
---

# T02: Added a read-only knowledge debug API that lists persisted answer runs, returns single-run audit details, and exposes ordered step breakdowns for admin/support inspection.

> Added a read-only knowledge debug API that lists persisted answer runs, returns single-run audit details, and exposes ordered step breakdowns for admin/support inspection.

## What Happened
---
id: T02
parent: S04
milestone: M011
key_files:
  - backend/src/common/api/knowledge_debug.py
  - backend/src/main.py
  - backend/tests/integration/test_knowledge_debug_api.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M011/slices/S04/tasks/T02-SUMMARY.md
key_decisions:
  - Read the debug API directly from persisted KnowledgeAnswerRun and KnowledgeAnswerRunStep rows instead of reconstructing traces from runtime-local StepFun state.
  - Keep the new inspection surface read-only and restricted to admin/support roles via the existing require_role dependency seam.
duration: ""
verification_result: passed
completed_at: 2026-03-31T05:58:24.676Z
blocker_discovered: false
---

# T02: Added a read-only knowledge debug API that lists persisted answer runs, returns single-run audit details, and exposes ordered step breakdowns for admin/support inspection.

**Added a read-only knowledge debug API that lists persisted answer runs, returns single-run audit details, and exposes ordered step breakdowns for admin/support inspection.**

## What Happened

Executed T02 in TDD order. After reading the task plan plus the existing audit repository, audit schemas, DB models, and FastAPI router-registration pattern, I defined the smallest truthful debug surface: list recent runs, fetch one run, and fetch that run’s ordered steps. I wrote the integration test first to lock the intended contract on the real app seam, including latest-first ordering, normalized detail payloads, ordered step breakdowns, admin/support-only access, and a structured not-found response. The first red run exposed a local test-fixture issue rather than a product issue: the new module needed to import agent.models so Base.metadata.create_all() could resolve PracticeSession foreign keys in the in-memory async DB. After fixing that test setup issue, the suite failed for the expected reason: the knowledge debug routes did not exist yet. I then implemented backend/src/common/api/knowledge_debug.py as a read-only router backed directly by persisted KnowledgeAnswerRun and KnowledgeAnswerRunStep rows, normalized JSON payload fields defensively, and returned the backend’s standard success/error envelope shape. Finally, I registered the new router in backend/src/main.py behind require_role(["admin", "support"]) so the inspection surface stays narrow and operationally useful. Fresh focused verification passed, py_compile passed, and LSP diagnostics reported no issues in the new router or main.py registration changes.

## Verification

Ran the task-plan verification command fresh from repo root and confirmed the new focused integration suite passed 5/5 against list/detail/steps, RBAC, and not-found behaviors. Then ran a follow-up py_compile check on the new router and focused test module, which also passed. Fresh LSP diagnostics reported no issues on backend/src/common/api/knowledge_debug.py and backend/src/main.py.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q` | 0 | ✅ pass | 3757ms |
| 2 | `backend/venv/bin/python -m py_compile backend/src/common/api/knowledge_debug.py backend/tests/integration/test_knowledge_debug_api.py` | 0 | ✅ pass | 33ms |


## Deviations

The task plan did not mention a local async test-fixture requirement: the new integration test module needed to import agent.models so Base.metadata.create_all() could resolve PracticeSession foreign keys. This was a local test-environment correction only; the shipped API scope and behavior still match the plan.

## Known Issues

Focused repo-root backend pytest still emits the pre-existing pytest-cov warning about src not being imported / no coverage data collected for this narrow invocation, but the task verification command itself passed and no task-specific failures remain.

## Files Created/Modified

- `backend/src/common/api/knowledge_debug.py`
- `backend/src/main.py`
- `backend/tests/integration/test_knowledge_debug_api.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M011/slices/S04/tasks/T02-SUMMARY.md`


## Deviations
The task plan did not mention a local async test-fixture requirement: the new integration test module needed to import agent.models so Base.metadata.create_all() could resolve PracticeSession foreign keys. This was a local test-environment correction only; the shipped API scope and behavior still match the plan.

## Known Issues
Focused repo-root backend pytest still emits the pre-existing pytest-cov warning about src not being imported / no coverage data collected for this narrow invocation, but the task verification command itself passed and no task-specific failures remain.

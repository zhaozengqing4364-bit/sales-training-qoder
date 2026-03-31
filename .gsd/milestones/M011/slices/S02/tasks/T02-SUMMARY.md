---
id: T02
parent: S02
milestone: M011
provides: []
requires: []
affects: []
key_files: ["backend/src/common/knowledge_engine/intent_classifier.py", "backend/src/common/knowledge_engine/retrieval_planner.py", "backend/tests/unit/common/test_knowledge_intent_classifier.py", "backend/tests/unit/common/test_knowledge_retrieval_planner.py", "backend/src/common/knowledge_engine/__init__.py", ".gsd/milestones/M011/slices/S02/tasks/T02-SUMMARY.md"]
key_decisions: ["Keep intent classification and retrieval planning on project-owned DTOs, with `entity_keyword_contains` encoded as a classifier-side rule type instead of adding new control-plane columns before Haystack wiring.", "Preserve the existing product-overview rewritten-query behavior by letting the planner emit deterministic progressive query steps from the selected profile rather than reaching back into legacy websocket helpers."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Followed TDD by writing the focused classifier and planner tests first, confirming the initial pytest run failed with `ModuleNotFoundError` for the missing modules, then implementing the minimal DTO-backed behavior and rerunning the same focused pytest command to green. Fresh LSP diagnostics on the new modules, package exports, and focused tests all reported no issues."
completed_at: 2026-03-31T03:50:56.013Z
blocker_discovered: false
---

# T02: Added DB-backed intent classification and progressive retrieval planning for normalized knowledge queries.

> Added DB-backed intent classification and progressive retrieval planning for normalized knowledge queries.

## What Happened
---
id: T02
parent: S02
milestone: M011
key_files:
  - backend/src/common/knowledge_engine/intent_classifier.py
  - backend/src/common/knowledge_engine/retrieval_planner.py
  - backend/tests/unit/common/test_knowledge_intent_classifier.py
  - backend/tests/unit/common/test_knowledge_retrieval_planner.py
  - backend/src/common/knowledge_engine/__init__.py
  - .gsd/milestones/M011/slices/S02/tasks/T02-SUMMARY.md
key_decisions:
  - Keep intent classification and retrieval planning on project-owned DTOs, with `entity_keyword_contains` encoded as a classifier-side rule type instead of adding new control-plane columns before Haystack wiring.
  - Preserve the existing product-overview rewritten-query behavior by letting the planner emit deterministic progressive query steps from the selected profile rather than reaching back into legacy websocket helpers.
duration: ""
verification_result: mixed
completed_at: 2026-03-31T03:50:56.014Z
blocker_discovered: false
---

# T02: Added DB-backed intent classification and progressive retrieval planning for normalized knowledge queries.

**Added DB-backed intent classification and progressive retrieval planning for normalized knowledge queries.**

## What Happened

Implemented a project-owned knowledge intent classifier plus retrieval planner on top of the DB-normalized config snapshot and T01 entity-resolution seam. The classifier now supports deterministic `regex`, `keyword_contains`, and `entity_keyword_contains` rules, returns the chosen profile and trace metadata, and falls back to the first available profile when no explicit rule matches. The planner consumes that classification and emits progressive retrieval steps with audit metadata, preserving the existing product-overview rewritten-query behavior while keeping legacy websocket helper state out of the new engine seam. Focused tests were written first, confirmed red because the modules were missing, then turned green after the minimal implementation landed; package exports and LSP diagnostics were also updated and verified.

## Verification

Followed TDD by writing the focused classifier and planner tests first, confirming the initial pytest run failed with `ModuleNotFoundError` for the missing modules, then implementing the minimal DTO-backed behavior and rerunning the same focused pytest command to green. Fresh LSP diagnostics on the new modules, package exports, and focused tests all reported no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q` | 2 | ❌ fail | 350ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q` | 0 | ✅ pass | 90ms |
| 3 | `LSP diagnostics on backend/src/common/knowledge_engine/intent_classifier.py, backend/src/common/knowledge_engine/retrieval_planner.py, backend/src/common/knowledge_engine/__init__.py, backend/tests/unit/common/test_knowledge_intent_classifier.py, backend/tests/unit/common/test_knowledge_retrieval_planner.py` | 0 | ✅ pass | 0ms |


## Deviations

None.

## Known Issues

Focused pytest still emits the pre-existing pytest-cov warnings (`Module src was never imported` / `No data was collected`) from the current backend coverage configuration, but the targeted classifier/planner suite passed all assertions and LSP found no code issues.

## Files Created/Modified

- `backend/src/common/knowledge_engine/intent_classifier.py`
- `backend/src/common/knowledge_engine/retrieval_planner.py`
- `backend/tests/unit/common/test_knowledge_intent_classifier.py`
- `backend/tests/unit/common/test_knowledge_retrieval_planner.py`
- `backend/src/common/knowledge_engine/__init__.py`
- `.gsd/milestones/M011/slices/S02/tasks/T02-SUMMARY.md`


## Deviations
None.

## Known Issues
Focused pytest still emits the pre-existing pytest-cov warnings (`Module src was never imported` / `No data was collected`) from the current backend coverage configuration, but the targeted classifier/planner suite passed all assertions and LSP found no code issues.

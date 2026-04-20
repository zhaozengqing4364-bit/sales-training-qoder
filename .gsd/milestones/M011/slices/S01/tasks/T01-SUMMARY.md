---
id: T01
parent: S01
milestone: M011
provides: []
requires: []
affects: []
key_files: ["backend/src/common/knowledge_engine/__init__.py", "backend/src/common/knowledge_engine/engine.py", "backend/src/common/knowledge_engine/schemas.py", "backend/tests/unit/common/test_knowledge_answer_engine.py", "backend/pyproject.toml", "backend/requirements.txt", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Use a project-owned KnowledgeAnswerEngine seam instead of exposing Haystack types directly to callers.", "Make Haystack a soft-imported pipeline factory dependency so engine construction stays safe before runtime installation is guaranteed.", "Stabilize observability fields on the placeholder result contract from the first slice rather than adding them later ad hoc."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Focused backend seam verification passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q` completed successfully with 2/2 tests green. LSP diagnostics on the new engine, schema, and test files reported no issues."
completed_at: 2026-03-31T02:39:06.226Z
blocker_discovered: false
---

# T01: Added the initial KnowledgeAnswerEngine seam, project-owned request/result schemas, and Haystack dependency entrypoints behind a constructable placeholder engine.

> Added the initial KnowledgeAnswerEngine seam, project-owned request/result schemas, and Haystack dependency entrypoints behind a constructable placeholder engine.

## What Happened
---
id: T01
parent: S01
milestone: M011
key_files:
  - backend/src/common/knowledge_engine/__init__.py
  - backend/src/common/knowledge_engine/engine.py
  - backend/src/common/knowledge_engine/schemas.py
  - backend/tests/unit/common/test_knowledge_answer_engine.py
  - backend/pyproject.toml
  - backend/requirements.txt
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Use a project-owned KnowledgeAnswerEngine seam instead of exposing Haystack types directly to callers.
  - Make Haystack a soft-imported pipeline factory dependency so engine construction stays safe before runtime installation is guaranteed.
  - Stabilize observability fields on the placeholder result contract from the first slice rather than adding them later ad hoc.
duration: ""
verification_result: passed
completed_at: 2026-03-31T02:39:06.229Z
blocker_discovered: false
---

# T01: Added the initial KnowledgeAnswerEngine seam, project-owned request/result schemas, and Haystack dependency entrypoints behind a constructable placeholder engine.

**Added the initial KnowledgeAnswerEngine seam, project-owned request/result schemas, and Haystack dependency entrypoints behind a constructable placeholder engine.**

## What Happened

Started from a failing seam test, confirmed the package did not exist, then implemented the smallest constructable `common.knowledge_engine` boundary. Added project-owned request/result/audit schemas with stable observability fields (`audit_run_id`, `retrieval_summary`, `unsupported_claims`), a minimal `KnowledgeAnswerEngine` that can be instantiated before retrieval logic lands, and a soft-imported Haystack pipeline factory seam so future slices can wire execution without leaking framework types into callers. Updated both `backend/pyproject.toml` and `backend/requirements.txt` because local repository installs still flow through the requirements file even when task plans cite pyproject metadata.

## Verification

Focused backend seam verification passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q` completed successfully with 2/2 tests green. LSP diagnostics on the new engine, schema, and test files reported no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q` | 0 | ✅ pass | 611ms |
| 2 | `lsp diagnostics backend/src/common/knowledge_engine/engine.py` | 0 | ✅ pass | 0ms |
| 3 | `lsp diagnostics backend/src/common/knowledge_engine/schemas.py` | 0 | ✅ pass | 0ms |
| 4 | `lsp diagnostics backend/tests/unit/common/test_knowledge_answer_engine.py` | 0 | ✅ pass | 0ms |


## Deviations

Minor local adaptation only: updated `backend/requirements.txt` in addition to `backend/pyproject.toml` because the repository’s actual backend install path still consumes the requirements file.

## Known Issues

Focused pytest emits pre-existing coverage warnings because repo-level pytest config forces coverage even for this small seam test. No functional failures remain in the new seam.

## Files Created/Modified

- `backend/src/common/knowledge_engine/__init__.py`
- `backend/src/common/knowledge_engine/engine.py`
- `backend/src/common/knowledge_engine/schemas.py`
- `backend/tests/unit/common/test_knowledge_answer_engine.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `.gsd/KNOWLEDGE.md`


## Deviations
Minor local adaptation only: updated `backend/requirements.txt` in addition to `backend/pyproject.toml` because the repository’s actual backend install path still consumes the requirements file.

## Known Issues
Focused pytest emits pre-existing coverage warnings because repo-level pytest config forces coverage even for this small seam test. No functional failures remain in the new seam.

---
id: S01
parent: M011
milestone: M011
provides:
  - A constructable `common.knowledge_engine` package with project-owned request/result/audit contracts and a soft-imported Haystack dependency seam.
  - Versioned Alembic schema history for knowledge config versions, query/ranking/answerability profiles, entity aliases, and answer run/step audit tables.
  - A DB-backed `KnowledgeAnswerConfigRepository` that reads the latest enabled active config version and returns normalized DTO snapshots for downstream execution code.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - backend/src/common/knowledge_engine/__init__.py
  - backend/src/common/knowledge_engine/engine.py
  - backend/src/common/knowledge_engine/schemas.py
  - backend/src/common/knowledge_engine/config_repo.py
  - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
  - backend/tests/unit/common/test_knowledge_answer_engine.py
  - backend/tests/unit/common/test_knowledge_answer_control_plane_models.py
  - backend/tests/unit/common/test_knowledge_answer_config_repo.py
  - backend/pyproject.toml
  - backend/requirements.txt
key_decisions:
  - Use a project-owned KnowledgeAnswerEngine with project-owned request/result schemas and a soft-imported Haystack pipeline factory seam so callers never depend on Haystack types directly.
  - Treat the missing Alembic revision as the real T02 gap because the ORM models already existed, and protect ORM/schema-history alignment with a focused migration-presence regression.
  - Expose a repository-owned normalized active-config snapshot carrying config_version_id, config_version_name, and profile_source instead of returning SQLAlchemy ORM rows.
patterns_established:
  - Keep external execution frameworks and database control-plane storage behind project-owned engine/repository contracts; callers should not depend on Haystack types or SQLAlchemy rows directly.
  - When models already exist but schema history is missing, close the real gap by adding the Alembic revision and a migration-presence regression instead of inventing duplicate model churn.
  - Normalize control-plane JSON/list columns at the repository boundary into plain DTO fields so runtime logic consumes stable engine-safe shapes with debug-friendly config metadata.
observability_surfaces:
  - Focused backend seam gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q`
  - Focused backend control-plane gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q`
  - Focused backend repository gate: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q`
  - Static diagnostics gate: LSP reported no diagnostics on the engine, schemas, repository, migration, and focused test files.
drill_down_paths:
  - .gsd/milestones/M011/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M011/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M011/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T03:30:47.339Z
blocker_discovered: false
---

# S01: 引擎 seam 与数据库控制面骨架

**S01 established the project-owned KnowledgeAnswerEngine seam, versioned DB control plane, and normalized active-config repository that downstream slices can wire directly into Haystack execution.**

## What Happened

S01 closed the foundation work for the new database-driven knowledge answering path. T01 introduced `common.knowledge_engine` as a project-owned seam with stable request/result/audit contracts and a constructable `KnowledgeAnswerEngine` whose Haystack dependency is soft-imported behind a factory boundary, so downstream code can instantiate the engine without leaking framework types into runtime/report/replay contracts. T02 then reconciled schema history with the actual backend state: instead of fabricating more ORM work, it added the missing Alembic revision for config versions, query profiles, intent rules, entity aliases, ranking profiles, answerability profiles, and answer run/step audit tables, and added focused regression coverage that fails if migration history drifts again. T03 completed the database control plane by implementing `KnowledgeAnswerConfigRepository`, which selects the latest enabled active config version and returns engine-safe dataclass snapshots for query profiles, intent rules, aliases, ranking profiles, and answerability profiles. Across the slice, raw ORM rows and JSON/list columns are normalized at the repository boundary while `config_version_id`, `config_version_name`, and `profile_source` stay available for future runtime diagnostics and debug APIs. The slice therefore delivers the exact S01 handoff needed by downstream work: S02 can now build query understanding, planner output, and Haystack retrieval execution on top of a stable engine seam and a normalized active-config snapshot, rather than starting from handlers or leaking database shapes into execution code.

## Verification

Fresh slice-close verification reran all slice-plan gates from repo root and all passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q` (2/2 green), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q` (10/10 green), and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q` (2/2 green). LSP diagnostics also reported no issues on `backend/src/common/knowledge_engine/__init__.py`, `backend/src/common/knowledge_engine/engine.py`, `backend/src/common/knowledge_engine/schemas.py`, `backend/src/common/knowledge_engine/config_repo.py`, `backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py`, and the three focused test files.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 discovered that the knowledge-answer ORM models already existed locally, so the slice closed the real gap by adding the missing Alembic revision and migration-presence regression instead of inventing duplicate model churn. Otherwise the slice stayed within plan.

## Known Limitations

This slice only establishes the seam and control plane. KnowledgeAnswerEngine.answer() is still a placeholder, no Haystack retrieval/planner/reranking execution is wired yet, and slice verification locks migration presence/model behavior rather than running a full live Alembic upgrade against a persistent environment.

## Follow-ups

S02 should wire query understanding, planner output, and Haystack retrieval execution onto this seam, and should keep using the repository snapshot rather than reading ORM rows or raw JSON control-plane columns directly inside runtime handlers.

## Files Created/Modified

- `backend/src/common/knowledge_engine/engine.py` — Introduced the constructable project-owned KnowledgeAnswerEngine seam with a soft-imported Haystack pipeline factory and placeholder answer contract.
- `backend/src/common/knowledge_engine/schemas.py` — Added project-owned request/result/citation/audit schemas with stable observability fields for future runtime and debug surfaces.
- `backend/src/common/knowledge_engine/config_repo.py` — Implemented the DB-backed active-config repository that returns normalized engine-safe DTO snapshots instead of ORM rows.
- `backend/src/common/knowledge_engine/__init__.py` — Exported the engine, repository, snapshot DTOs, and schemas from one package seam for downstream slices.
- `backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py` — Added the missing Alembic revision for knowledge config versions, query/ranking/answerability profiles, entity aliases, and answer run/step audit tables.
- `backend/tests/unit/common/test_knowledge_answer_engine.py` — Locked the constructable engine seam and placeholder observability contract with focused regression coverage.
- `backend/tests/unit/common/test_knowledge_answer_control_plane_models.py` — Locked ORM persistence plus migration-file presence/down_revision coverage for the control-plane schema.
- `backend/tests/unit/common/test_knowledge_answer_config_repo.py` — Verified active-version selection, disabled-row filtering, JSON/list normalization, and ORM-leak prevention in the repository boundary.
- `backend/pyproject.toml` — Registered the Haystack dependency entrypoint for the new knowledge-answer seam.
- `backend/requirements.txt` — Kept the repository’s actual backend install path aligned with the new knowledge-answer dependency.
- `.gsd/PROJECT.md` — Updated project state to record that M011/S01 has established the engine seam, control-plane schema history, and active-config repository.
- `.gsd/DECISIONS.md` — Recorded the slice-level migration-alignment decision for the control-plane schema close-out.

# S01: 引擎 seam 与数据库控制面骨架 — UAT

**Milestone:** M011
**Written:** 2026-03-31T03:30:47.340Z

# S01: 引擎 seam 与数据库控制面骨架 — UAT

**Milestone:** M011
**UAT mode:** focused backend seam/control-plane verification

## Why this UAT mode is sufficient

This slice delivers backend foundation only: a constructable engine seam, schema history for the knowledge-answer control plane, and an active-config repository. It does not yet ship learner-visible runtime behavior, so acceptance depends on focused backend verification of contracts, migration coverage, and repository normalization rather than browser flows.

## Preconditions

- Backend dependencies are installed in `backend/venv`.
- Run commands from the repository root.
- The branch contains the S01 engine, migration, and repository changes.

## Smoke Test

Run all three focused slice gates:

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q`

**Expected:** all 14 focused backend tests pass, proving the seam is constructable, the control-plane schema history exists, and the active-config repository returns normalized DTO snapshots.

## Test Cases

### 1. Engine seam can be instantiated before retrieval logic exists

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q`.
2. Confirm the constructability test passes.
3. **Expected:** `KnowledgeAnswerEngine()` can be instantiated with default dependencies even when no runtime retrieval pipeline is wired yet.

### 2. Placeholder answer contract exposes the stable observability fields downstream slices need

1. In the same engine suite, inspect the placeholder-answer assertions.
2. **Expected:** `answer()` returns a `KnowledgeAnswerResult` whose `final_text` and `blocked_text` are `None`, `answerability == "unanswered"`, `source_status == "not_run"`, and whose observability fields (`citations`, `rewritten_queries`, `unsupported_claims`, `audit_run_id`, `retrieval_summary`) are present with stable empty defaults.

### 3. The knowledge-answer control plane has real Alembic schema history, not only ORM rows

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q`.
2. Inspect the migration-presence assertions.
3. **Expected:** the suite proves an Alembic revision file named `*_knowledge_answer_control_plane.py` exists, declares all expected control-plane/audit tables, and revises `20260328_1000_022`.

### 4. The minimal control-plane ORM rows persist the fields downstream slices rely on

1. In the same control-plane suite, inspect the persistence tests for config versions, query profiles, intent rules, entity aliases, ranking profiles, answerability profiles, answer runs, and answer run steps.
2. **Expected:** all minimal rows persist and round-trip the planned fields, including profile keys, rewrite strategy, thresholds, JSON-backed weight/slot fields, query text, answerability, and per-step payload/status data.

### 5. The active-config repository returns `None` when no enabled active config version exists

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q`.
2. Inspect the no-active-config regression test.
3. **Expected:** when only draft or disabled active versions exist, `KnowledgeAnswerConfigRepository.get_active_config()` returns `None` instead of leaking partial rows or choosing an invalid version.

### 6. The repository returns a normalized engine-safe snapshot for the latest enabled active config version

1. In the same repository suite, inspect the seeded active-config snapshot test.
2. **Expected:** the snapshot contains `config_version_id`, `config_version_name`, and `profile_source`; includes only enabled rows from the latest enabled active version; orders intent rules by priority; normalizes JSON/list columns into plain dict/list DTO fields; and does not leak SQLAlchemy state such as `_sa_instance_state`.

## Edge Cases

### A. Haystack is not required to instantiate the seam yet

- **Expected:** the constructability test remains green because the Haystack dependency is isolated behind a soft-imported factory seam.

### B. Disabled rows do not leak into runtime configuration

- **Expected:** disabled query profiles, intent rules, and aliases seeded in the repository test are excluded from the returned snapshot.

### C. Raw JSON control-plane columns do not leak into engine consumers

- **Expected:** `doc_type_weights_json`, `section_weights_json`, `required_slots_json`, and `optional_slots_json` are exposed as normalized plain DTO fields, not as ORM rows or unvalidated raw shapes.

## Failure Signals

- `KnowledgeAnswerEngine()` cannot be instantiated without extra runtime setup.
- The placeholder result contract drops or renames the stable observability fields.
- The Alembic revision is missing, points to the wrong `down_revision`, or no longer declares the expected control-plane/audit tables.
- The repository picks a draft/disabled version instead of the latest enabled active one.
- Disabled rows appear in the returned snapshot.
- The returned snapshot leaks ORM state or raw JSON/list column shapes into downstream callers.

## Requirements Proved By This UAT

None are newly validated at slice close-out. This UAT proves the technical foundation required for M011/S02-S04, not a learner-facing product requirement transition.

## Not Proved By This UAT

- Query understanding, planner output, retrieval execution, reranking, or answerability decisions.
- Runtime/report/replay integration of the new engine.
- A full live Alembic upgrade run against a persistent environment.

## Notes For The Next Slice

Treat `common.knowledge_engine` and `KnowledgeAnswerConfigRepository` as the only accepted entry seams for new execution work. If S02 needs new knobs, add them to the repository snapshot DTOs rather than reaching directly into SQLAlchemy models or raw JSON columns from runtime handlers.

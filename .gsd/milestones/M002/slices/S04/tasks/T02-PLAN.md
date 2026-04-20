---
estimated_steps: 5
estimated_files: 7
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - verification-before-completion
---

# T02: Override stale sales conclusions in session evidence projection

**Slice:** S04 — 训练中建议与报告结论一致性
**Milestone:** M002

## Description

Move S04’s alignment logic into the read-side seam that every completed sales consumer already shares. `SessionEvidenceService.build_projection(...)` is the lowest-blast-radius place to stop reusing stale `effectiveness_snapshot.main_issue` / `next_goal` values for sales sessions. This task should make projection prefer the latest persisted stage + score evidence from T01’s helper, emit minimal diagnostics about whether alignment was applied, and prove replay/report/history all receive the same conclusion even when the stored snapshot is outdated.

## Steps

1. Add failing backend tests in `backend/tests/unit/test_session_evidence_service.py`, `backend/tests/unit/test_replay_service.py`, and `backend/tests/unit/test_history_service_evidence_projection.py` that build completed sales sessions with stale `effectiveness_snapshot` values and assert projection-backed consumers now return the aligned `main_issue` / `next_goal` instead.
2. Update `backend/src/common/conversation/session_evidence.py` so completed sales sessions derive an aligned read-side conclusion from the latest persisted `sales_stage` + normalized `score_snapshot` evidence and override stale snapshot values only in projection output; keep non-sales and insufficient-evidence fallback paths unchanged.
3. Extend `practice_session_evidence_projection_built` logging with concise alignment diagnostics (for example whether sales alignment was applied and why fallback happened), then update `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_practice_evidence_flow.py`, and `backend/tests/integration/test_sales_value_training_flow.py` to prove report/replay share the aligned result under the stable public contract.
4. Run the backend pytest commands sequentially, not in parallel, because this repository still has a `pytest-cov` combine race on parallel runs.
5. Confirm the failure-path assertions still surface `evaluable`, `not_evaluable_reason`, and `evidence_completeness` clearly when there is not enough persisted evidence to align a sales conclusion.

## Must-Haves

- [ ] Projection overrides stale sales `main_issue` / `next_goal` read-side values without mutating public key names or requiring a DB migration.
- [ ] Replay/report/history tests prove the same aligned conclusion flows through every projection-backed consumer.
- [ ] Alignment diagnostics stay minimal and safe: enough to inspect override vs fallback, without logging transcript text or secrets.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`

## Observability Impact

- Signals added/changed: `practice_session_evidence_projection_built` should expose whether sales alignment applied, plus the concise fallback reason when projection keeps the old evaluator path.
- How a future agent inspects this: run the focused unit/contract/integration pytest commands and inspect projection log fields plus returned `main_issue` / `next_goal` payloads from report/replay APIs.
- Failure state exposed: stale snapshot reuse, missing persisted sales evidence, or replay/report divergence fail named tests and surface whether the projection override path was skipped or fell back.

## Inputs

- `backend/src/common/effectiveness/evaluator.py` — shared report-alignment helper from T01.
- `backend/src/common/conversation/session_evidence.py` — current projection seam reused by report/replay/history/admin.
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py` — focused helper proof from T01.
- `backend/tests/unit/test_session_evidence_service.py` — current projection unit coverage.
- `backend/tests/unit/test_replay_service.py` — replay contract coverage.
- `backend/tests/unit/test_history_service_evidence_projection.py` — history projection coverage.
- `backend/tests/contract/test_practice_evidence_contract.py` — public contract assertions.

## Expected Output

- `backend/src/common/conversation/session_evidence.py` — projection-side override for completed sales sessions plus alignment diagnostics.
- `backend/tests/unit/test_session_evidence_service.py` — stale-snapshot and insufficient-evidence coverage.
- `backend/tests/unit/test_replay_service.py` — replay alignment regressions.
- `backend/tests/unit/test_history_service_evidence_projection.py` — history alignment regressions.
- `backend/tests/contract/test_practice_evidence_contract.py` — stable contract assertions for aligned sales conclusions.
- `backend/tests/integration/test_practice_evidence_flow.py` — shared replay/report flow proof.
- `backend/tests/integration/test_sales_value_training_flow.py` — sales-specific end-to-end evidence proof.

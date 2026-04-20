---
estimated_steps: 4
estimated_files: 6
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - verification-before-completion
---

# T01: Align backend realtime contracts across StepFun and classic mode

**Slice:** S01 — 实时评分与训练页销售语义对齐
**Milestone:** M002

## Description

Close the only confirmed backend semantic drift in S01: StepFun realtime already emits the five sales dimensions, but classic mode still derives action-card pass flags from generic communication / structure heuristics. This task should lock the StepFun payload contract with focused tests, then move classic mode onto the same shared sales effectiveness helper without changing the existing three-rollup report boundary.

## Steps

1. Extend `backend/tests/unit/test_stepfun_realtime_handler.py` to assert a real `_run_realtime_feedback(...)` cycle emits canonical `score_update` / `action_card` payloads with `overall_score`, five sales `dimension_scores`, `stage_name`, and sales-specific next-turn wording.
2. Refactor `backend/src/sales_bot/websocket/components/capability_processor.py` so legacy/classic mode derives action-card pass flags from the shared sales effectiveness helper instead of `沟通技巧` / `销售流程` fallback math, then add focused coverage in `backend/tests/unit/test_capability_processor.py`.
3. Re-run the scorer / effectiveness / handler suites plus `backend/tests/contract/test_practice_evidence_contract.py` to prove runtime semantics changed without altering the report-side three-rollup evidence contract.
4. If helper extraction is needed, keep the canonical websocket fields unchanged (`overall_score`, `dimension_scores`, `suggestions`, `stage_name`) and avoid any read-side rollup changes while closing the backend drift.

## Must-Haves

- [ ] StepFun-focused tests assert the emitted websocket payload, not just the scorer internals.
- [ ] Classic mode action-card semantics reuse the shared sales effectiveness line instead of generic communication/structure heuristics.
- [ ] The existing report/practice evidence contract remains three-rollup on the read side.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py`

## Observability Impact

- Signals added/changed: backend websocket contract assertions for `score_update` / `action_card`, plus classic-mode action-card derivation now flowing through the shared sales effectiveness helper.
- How a future agent inspects this: run the focused backend pytest commands and inspect `_latest_score_snapshot` / `_latest_action_card` expectations in `backend/tests/unit/test_stepfun_realtime_handler.py`.
- Failure state exposed: generic-dimension regressions or classic-mode drift now fail as focused handler/processor tests instead of surfacing later as vague practice-page mismatches.

## Inputs

- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic-mode realtime feedback path that still uses generic action-card heuristics.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun sales contract authority for emitted score/stage/action payloads.
- `backend/tests/unit/test_capability_processor.py` — current legacy-path focused coverage.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — current StepFun handler coverage.
- `backend/tests/unit/test_effectiveness_sales_baseline.py` — shared sales rollup/action-card expectations.
- `backend/tests/contract/test_practice_evidence_contract.py` — downstream report/evidence contract guardrail.

## Expected Output

- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic-mode action-card logic aligned to the shared sales effectiveness helper.
- `backend/tests/unit/test_capability_processor.py` — focused legacy-path sales contract assertions.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — emitted StepFun websocket payload assertions for the sales contract.

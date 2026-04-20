---
id: T01
parent: S01
milestone: M002
provides:
  - StepFun realtime payload assertions plus classic-mode sales action-card alignment on one helper path
key_files:
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/tests/unit/test_capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - .gsd/milestones/M002/slices/S01/S01-PLAN.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D033: Use build_sales_effectiveness_metrics(...) + evaluate_pass_flags(...) as the classic sales realtime action-card authority.
patterns_established:
  - Classic sales realtime feedback must derive action-card pass flags from shared sales effectiveness metrics instead of generic communication/structure heuristics.
observability_surfaces:
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_capability_processor.py
  - websocket score_update/action_card payload assertions
  - persisted StepFun handler snapshots via _latest_score_snapshot / _latest_action_card expectations
duration: 40m
verification_result: passed
completed_at: 2026-03-24T19:07:08+0800
blocker_discovered: false
---

# T01: Align backend realtime contracts across StepFun and classic mode

**Aligned classic sales action-card semantics to the shared sales effectiveness helper and locked the StepFun realtime payload contract with focused backend tests.**

## What Happened

I started with the required pre-flight fix: `.gsd/milestones/M002/slices/S01/S01-PLAN.md` was missing a diagnostic verification step, so I added a focused handler/processor pytest command before touching runtime code.

Then I extended `backend/tests/unit/test_stepfun_realtime_handler.py` with a real `_run_realtime_feedback(...)` contract test. It now asserts the emitted `score_update` and `action_card` payloads carry canonical StepFun sales fields: `overall_score`, five sales `dimension_scores`, `suggestions`, `stage_name`, and the expected sales-specific `next_turn_rule`. That test also locks the handler’s `_latest_score_snapshot` and `_latest_action_card` state surfaces.

For the classic path, I wrote a red test in `backend/tests/unit/test_capability_processor.py` that reproduced the confirmed drift: a sales-shaped low-evidence score still produced the generic default action-card guidance. I then changed `backend/src/sales_bot/websocket/components/capability_processor.py` to prefer canonical `dimension_scores` when present, fall back to the legacy `dimensions` list when needed, and derive action-card pass flags through `build_sales_effectiveness_metrics(...)` plus `evaluate_pass_flags(...)` instead of reconstructing generic communication/structure heuristics.

That keeps StepFun and classic sales runtime modes on the same sales helper line while leaving the report-side three-rollup read contract untouched. I also recorded the pattern in `D033` and added a knowledge note about pytest-cov races when backend suites are run in parallel.

## Verification

I ran the task-level backend suite, the read-side contract guardrail, the new slice-level diagnostic check, and the slice web command. All four passed fresh after I reran the main backend unit suite sequentially; an earlier parallel pytest launch hit a coverage-file race, which I treated as a harness issue rather than product evidence.

The report/practice evidence contract stayed green, so the runtime semantic change did not alter the existing three-rollup read boundary.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py` | 0 | ✅ pass | 2.84s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'` | 0 | ✅ pass | 3.23s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 3.33s |
| 4 | `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'` | 0 | ✅ pass | 983ms |

## Diagnostics

To inspect this task later, rerun:
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -k run_realtime_feedback_emits_canonical_sales_score_and_action_card`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_capability_processor.py -k realtime_scoring_action_card_uses_sales_effectiveness_semantics`

The StepFun handler test is the main runtime contract surface for `_latest_score_snapshot`, `_latest_action_card`, and emitted websocket payloads. The capability-processor test is the focused failure surface for classic-mode sales drift.

## Deviations

I added the missing diagnostic verification command to `S01-PLAN.md` during pre-flight because auto-mode flagged the slice plan as lacking an inspectable failure-path check.

I also reran the main backend unit suite sequentially after an initial parallel pytest attempt triggered a `pytest-cov` `.coverage.*` combine race. The product code was unchanged between runs; the sequential rerun is the verification evidence above.

## Known Issues

None.

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/capability_processor.py` — switched classic realtime action-card pass-flag derivation to the shared sales effectiveness helper and canonical `dimension_scores` handling.
- `backend/tests/unit/test_capability_processor.py` — added a regression test proving classic-mode action cards follow sales evidence semantics instead of generic fallback math.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — added a focused `_run_realtime_feedback(...)` payload test for canonical `score_update` / `action_card` sales contracts.
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — added the required slice-level diagnostic verification step and marked T01 complete.
- `.gsd/DECISIONS.md` — recorded D033 for the shared classic realtime action-card helper choice.
- `.gsd/KNOWLEDGE.md` — recorded the backend pytest parallel-coverage gotcha for future auto-mode runs.

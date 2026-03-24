---
id: T01
parent: S03
milestone: M002
provides:
  - stage-aware sales coaching-focus contract in common.effectiveness
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/effectiveness/schemas.py
  - backend/src/common/effectiveness/__init__.py
  - backend/tests/unit/test_effectiveness_sales_coaching_focus.py
key_decisions:
  - D039 — gate shared coaching-focus action cards on rich stage/score context while preserving the legacy fallback for unwired callers
patterns_established:
  - resolve_sales_coaching_focus is the shared backend seam for canonical sales issue/replacement/next_turn_rule triples
  - build_action_card switches to the shared helper only when rich sales stage/score context is present
observability_surfaces:
  - backend/tests/unit/test_effectiveness_sales_coaching_focus.py
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
duration: 1h22m
verification_result: passed
completed_at: 2026-03-24T21:37:02+0800
blocker_discovered: false
---

# T01: Define stage-aware coaching focus in `common.effectiveness`

**Added a shared stage-aware sales coaching-focus resolver and rewired action cards to use it when rich context is available.**

## What Happened

I treated the pre-existing `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` file as the TDD red step, confirmed the initial import failure for `resolve_sales_coaching_focus`, then added the shared helper in `backend/src/common/effectiveness/evaluator.py` and exported it from `common.effectiveness`.

The helper now normalizes stage and score context, selects the canonical coaching focus from weakest/declining sales dimensions with stage-aware priority, and returns the pinned `issue` / `replacement` / `next_turn_rule` triple used by the new focused tests. I also added explicit typed literals in `backend/src/common/effectiveness/schemas.py` for the stage/focus/dimension vocabulary.

To keep T01 isolated, `build_action_card(...)` only switches to the shared resolver when rich `stage_context` or `score_context` is actually supplied. Existing fuzzy/suggestion + pass-flags-only behavior stays intact for current callers until S03/T02-T03 rewire classic and StepFun to pass the richer context.

## Verification

I ran the focused T01 suite, the verbose selector, the weakest-dimension selector, and the slice-level backend verification commands. All passed fresh after the implementation landed. One intermediate attempt to run two pytest-cov selectors in parallel hit a transient local `.coverage` race; I reran the exact selector sequentially and the planned verification passed without further code changes.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py` | 0 | ✅ pass | 6.64s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv` | 0 | ✅ pass | 6.17s |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv` | 0 | ✅ pass | 5.88s |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py` | 0 | ✅ pass | 6.46s |
| 5 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv` | 0 | ✅ pass | 5.73s |

## Diagnostics

Use `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` as the canonical inspection surface for the shared helper. The runtime-facing continuity surfaces that now indirectly depend on this seam remain `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_capability_processor.py`, and `backend/tests/unit/test_stepfun_realtime_handler.py`.

## Deviations

No product-scope deviation. I only adapted verification execution by rerunning one selector sequentially after a transient local pytest-cov `.coverage` race caused by parallel execution.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/effectiveness/evaluator.py` — added `resolve_sales_coaching_focus`, stage/score normalization helpers, and rich-context `build_action_card(...)` wiring.
- `backend/src/common/effectiveness/schemas.py` — added typed literals for stage/focus/dimension vocabulary used by the shared coaching-focus seam.
- `backend/src/common/effectiveness/__init__.py` — re-exported `resolve_sales_coaching_focus`.
- `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` — pinned the shared stage-aware coaching-focus contract and weakest-dimension behavior.
- `.gsd/DECISIONS.md` — recorded D039 for the rich-context gate/legacy fallback boundary.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — marked T01 done.

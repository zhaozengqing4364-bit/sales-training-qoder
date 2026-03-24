---
estimated_steps: 4
estimated_files: 4
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - code-refactoring
  - verification-before-completion
---

# T01: Define stage-aware coaching focus in `common.effectiveness`

**Slice:** S03 — 阶段推进教练与下一轮规则闭环
**Milestone:** M002

## Description

Create the single backend rule S03 depends on before touching runtime wiring. Today `build_action_card(...)` picks `next_turn_rule` from pass flags alone, while report-side helpers and stage guidance reason differently about the next move. This task should lock a shared, stage-aware coaching-focus contract in `common.effectiveness`, then make `build_action_card(...)` derive its three user-visible fields from that contract without changing the public `action_card` shape.

## Steps

1. Add a new focused unit file at `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` covering at least three cases: discovery + evidence gap, objection + objection-handling gap, and closing + next-step gap, including one case where the weakest or declining dimension changes the expected next-turn rule.
2. Introduce a typed shared coaching-focus helper in `backend/src/common/effectiveness/evaluator.py` and `backend/src/common/effectiveness/schemas.py` that accepts normalized stage context, score context, and existing pass flags, then returns canonical `issue`, `replacement`, and `next_turn_rule` semantics for the next turn.
3. Rewire `build_action_card(...)` to consume that helper while keeping the existing `ActionCard` field names stable and avoiding any replay/report/database schema changes.
4. Export the helper from `backend/src/common/effectiveness/__init__.py`, run the focused unit command, and keep the contract pinned by assertions rather than comments or undocumented heuristics.

## Must-Haves

- [ ] One shared helper decides next-turn coaching from stage context plus score context instead of only from pass flags.
- [ ] `build_action_card(...)` keeps the existing websocket field names: `issue`, `replacement`, and `next_turn_rule`.
- [ ] No replay/report schema, database model, or frontend payload changes are introduced in this task.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv`

## Observability Impact

- Signals changed: `common.effectiveness` now exposes one shared coaching-focus decision surface for sales turns, and `build_action_card(...)` becomes a thin projection of that helper instead of a pass-flags-only rule.
- Inspection surfaces: `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` should pin the canonical `issue` / `replacement` / `next_turn_rule` triples directly, and downstream runtimes will inspect the same helper through existing action-card assertions.
- Failure visibility: stage-insensitive prompts or weak-dimension drift should fail focused assertions with the expected coaching text diff, especially the `weakest_dimension_changes_next_turn_rule` diagnostic selector added above.
- Redaction constraints: use synthetic stage names, synthetic score deltas, and synthetic sales utterances only.

## Inputs

- `backend/src/common/effectiveness/evaluator.py` — current shared sales effectiveness logic, including `build_action_card(...)`, `resolve_main_issue(...)`, and `resolve_next_goal(...)`.
- `backend/src/common/effectiveness/schemas.py` — current typed dicts for `ActionCard` and related effect surfaces.
- `backend/src/common/effectiveness/__init__.py` — current shared-effectiveness exports.

## Expected Output

- `backend/src/common/effectiveness/evaluator.py` — shared stage-aware coaching-focus helper plus updated `build_action_card(...)` wiring.
- `backend/src/common/effectiveness/schemas.py` — typed schema for the new shared coaching-focus contract if needed.
- `backend/src/common/effectiveness/__init__.py` — re-export of the shared helper.
- `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` — focused assertions pinning the new coaching-focus behavior.

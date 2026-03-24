---
estimated_steps: 4
estimated_files: 4
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - verification-before-completion
---

# T01: Add a shared sales report-alignment helper in `common.effectiveness`

**Slice:** S04 — 训练中建议与报告结论一致性
**Milestone:** M002

## Description

Create the smallest shared backend seam that lets S04 compare realtime coaching and report conclusions without reopening persistence or websocket contracts. S03 already made `resolve_sales_coaching_focus(...)` the authoritative realtime next-turn rule; this task should add a companion read-side helper that turns persisted sales stage + normalized score evidence into the existing `main_issue` / `next_goal` report shape so later tasks can override stale session projections from one place.

## Steps

1. Add a new focused backend unit file at `backend/tests/unit/test_effectiveness_sales_report_alignment.py` covering at least three persisted-evidence cases: discovery + evidence gap, objection + objection-handling gap, and closing + next-step gap, plus one insufficient-evidence fallback case.
2. Implement a shared helper in `backend/src/common/effectiveness/evaluator.py` that accepts the latest persisted `sales_stage` and normalized `score_snapshot.dimension_scores`, reuses S03-compatible focus logic where evidence is sufficient, and returns report-compatible `main_issue` / `next_goal` payloads.
3. Add any minimal typed schema/export support in `backend/src/common/effectiveness/schemas.py` and `backend/src/common/effectiveness/__init__.py`, but do not introduce new public API keys, websocket fields, or database schema.
4. Run the focused unit suite and keep the new helper honest with assertions on exact `issue_type` / `goal_type` outputs instead of comments or implicit behavior.

## Must-Haves

- [ ] The helper derives report-compatible `main_issue` / `next_goal` from persisted sales stage + score evidence using the same decision family as S03 coaching focus.
- [ ] Existing public field names remain unchanged: no new report keys, no websocket changes, no persistence migration.
- [ ] When persisted evidence is insufficient, the helper cleanly falls back to the current evaluator semantics instead of inventing partial heuristics.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -vv`

## Inputs

- `backend/src/common/effectiveness/evaluator.py` — current sales `main_issue` / `next_goal` resolver and S03 `resolve_sales_coaching_focus(...)` seam.
- `backend/src/common/effectiveness/schemas.py` — current typed dicts for effectiveness/read-side contracts.
- `backend/src/common/effectiveness/__init__.py` — current shared-effectiveness exports.

## Expected Output

- `backend/src/common/effectiveness/evaluator.py` — new shared sales report-alignment helper.
- `backend/src/common/effectiveness/schemas.py` — any minimal typing needed for the helper contract.
- `backend/src/common/effectiveness/__init__.py` — exported helper.
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py` — focused proof that persisted evidence maps to the expected `main_issue` / `next_goal` pairs.

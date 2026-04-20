---
id: T01
parent: S01
milestone: M022
key_files:
  - backend/src/common/effectiveness/methodology.py
  - backend/src/common/effectiveness/__init__.py
  - backend/tests/unit/test_sales_methodology_contract.py
  - docs/api-contract/effectiveness.md
  - docs/api-contract/README.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep methodology-aware rubric semantics additive to the existing canonical kernel and compatibility readers instead of replacing the shipped score schema.
  - Treat qualification as part of the first-round `opening + discovery` contract until `sales_stage` gains a real standalone qualification stage.
duration: 
verification_result: passed
completed_at: 2026-04-14T05:14:19.631Z
blocker_discovered: false
---

# T01: Added an additive methodology-aware sales rubric contract that crosswalks canonical kernel dimensions to realtime, report, history, and admin evidence surfaces.

**Added an additive methodology-aware sales rubric contract that crosswalks canonical kernel dimensions to realtime, report, history, and admin evidence surfaces.**

## What Happened

I implemented a new code-owned contract in `backend/src/common/effectiveness/methodology.py` so M022 no longer has to infer sales methodology semantics from scattered dimension aliases and issue-family heuristics. The contract defines five first-round rubrics — `discovery_qualification`, `value_story`, `evidence_proof`, `objection_reframe`, and `next_step_commitment` — and ties each one to shipped canonical dimension ids, `sales_stage` coverage, `main_issue` / `next_goal` mappings, evidence paths, and compatibility rules. I exported the new contract through `common.effectiveness`, added a fail-first focused unit test to lock the crosswalk, wrote the authority line back into `docs/api-contract/effectiveness.md` plus `docs/api-contract/README.md`, updated the M022 architecture scan handoff, recorded the additive-schema decision in GSD, and captured the non-obvious qualification-stage boundary in `.gsd/KNOWLEDGE.md`. The only local adaptation from the planner snapshot is that qualification is explicitly merged into `opening + discovery`, because the current shipped `sales_stage` runtime still has no standalone `qualification` stage.

## Verification

Ran the fail-first focused backend proof and watched it pass after the new contract landed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_sales_methodology_contract.py -q` finished 2/2 green. Ran the exact task-plan grep gate: `rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract`, which now exposes the new methodology authority through both code and docs. Also checked LSP diagnostics on `backend/src/common/effectiveness/methodology.py`, `backend/src/common/effectiveness/__init__.py`, and `backend/tests/unit/test_sales_methodology_contract.py`; all were clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_sales_methodology_contract.py -q` | 0 | ✅ pass | 1518ms |
| 2 | `rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract` | 0 | ✅ pass | 36ms |

## Deviations

Merged qualification into the `opening` / `discovery` methodology contract instead of inventing a new runtime stage, because the current shipped `sales_stage` capability does not yet expose a standalone `qualification` state. This preserves truthful alignment with local reality while still defining the first-round rubric contract.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/effectiveness/methodology.py`
- `backend/src/common/effectiveness/__init__.py`
- `backend/tests/unit/test_sales_methodology_contract.py`
- `docs/api-contract/effectiveness.md`
- `docs/api-contract/README.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`

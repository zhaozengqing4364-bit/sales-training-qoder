---
id: S03
parent: M002
milestone: M002
provides:
  - One shared backend coaching-focus rule that converts sales stage + weakest/declining realtime dimensions into a single `action_card.issue` / `replacement` / `next_turn_rule` direction across classic + StepFun without changing the public websocket contract.
requires:
  - slice: S01
    provides: The canonical five-dimension sales realtime `score_update` / `stage_update` / `action_card` contract.
  - slice: S02
    provides: The shared realtime-feedback arbiter, duplicate suppression, and one-primary-action pacing boundary.
affects:
  - S04
  - S05
  - S06
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/effectiveness/schemas.py
  - backend/src/common/effectiveness/__init__.py
  - backend/src/sales_bot/websocket/realtime_feedback_arbiter.py
  - backend/src/sales_bot/websocket/components/capability_processor.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_effectiveness_sales_coaching_focus.py
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
key_decisions:
  - D038
  - D039
patterns_established:
  - `common.effectiveness.resolve_sales_coaching_focus(...)` is now the canonical seam for turning sales stage + score context into one next-turn coaching triple.
  - `build_action_card(...)` should use the shared coaching-focus resolver only when rich stage/score context is present; the old pass-flags fallback remains only for unwired callers.
  - Both runtimes may preserve richer backend-only context for arbitration than they expose publicly: classic forwards raw `stage_data` / `score_payload`, while StepFun keeps `_latest_stage_data` plus raw `dimensions[*].delta/trend` for the arbiter but still emits the stable `score_update` / `_latest_score_snapshot` snapshot shape.
observability_surfaces:
  - backend/tests/unit/test_effectiveness_sales_coaching_focus.py
  - backend/tests/unit/test_realtime_feedback_arbiter.py
  - backend/tests/unit/test_capability_processor.py
  - backend/tests/unit/test_stepfun_realtime_handler.py::test_analyze_and_emit_sales_stage_retains_latest_rich_stage_data_for_followup_feedback
  - backend/tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable
  - backend diagnostic fields `_latest_stage_data` and `_latest_score_snapshot`
drill_down_paths:
  - .gsd/milestones/M002/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T03-SUMMARY.md
verification_result: passed
completed_at: 2026-03-24T22:19:01+08:00
---

# S03: 阶段推进教练与下一轮规则闭环

**Realtime sales coaching now uses one shared backend rule to decide the next-turn action from stage context plus weakest/declining dimensions, and classic + StepFun now converge on the same `action_card` direction without changing the public practice-page contract.**

## What Happened

S03 closed the third M002 gap: stage updates, realtime scores, and action cards are no longer three parallel hints that happen to coexist. The slice first added `resolve_sales_coaching_focus(...)` inside `common.effectiveness` and gave it a typed vocabulary for sales stages, focus types, and dimensions. That helper now decides one canonical `issue` / `replacement` / `next_turn_rule` triple from the current stage plus weakest or declining sales dimensions. `build_action_card(...)` switches to that rule only when rich `stage_context` or `score_context` is actually available, so legacy pass-flags-only callers do not regress while newer runtime paths opt into the smarter behavior.

Classic runtime was then rewired to actually use that seam. `CapabilityProcessor` already had the raw stage and score payloads, but the last hop into `RealtimeFeedbackArbiter` previously let action cards drift back toward suggestion/pass-flags text. S03 now forwards `stage_data` and `score_payload` through the arbiter and into `build_action_card(...)`, so classic action cards can change when the stage changes or when a declining dimension matters more than the static weakest score. The slice kept S02’s pacing guarantees intact: duplicate same-turn action cards are still suppressed, and fuzzy/stage/score payloads remain available as context even when score guidance becomes the one primary coaching action.

StepFun then closed the parity gap. The handler now preserves rich stage-analysis output in `_latest_stage_data`, keeps raw scoring details for the arbiter (including `dimensions[*].delta` and `trend`), and feeds that richer context into the same shared arbiter used on classic. At the same time, it deliberately keeps the outward `score_update` and `_latest_score_snapshot` shape stable for existing consumers. That means StepFun gained smarter next-turn coaching without forcing a frontend planner rewrite or a persistence schema migration.

The closer turn reran every slice-plan verification command fresh and treated the test surfaces as the observability proof. The focused coaching-focus tests, arbiter context-preservation selector, and StepFun verbose suite all passed. Together they prove discovery/evidence, objection/handling, and closing/next-step cases now move through one shared next-turn rule seam, and that both runtimes carry equivalent backend context into that decision.

## Verification

Fresh slice-level verification passed:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv`

Fresh observability / diagnostic confirmation also passed:

- `test_effectiveness_sales_coaching_focus.py` still proves stage-aware discovery, objection, and closing cases plus the weakest-dimension change in `next_turn_rule`.
- `test_preserve_context_without_primary_action` still proves the arbiter can retain `stage_context` and `score_context` even when it emits no primary action card.
- StepFun verbose coverage still proves `_latest_stage_data` retention and the split between rich arbiter context and stable public `score_update` / `_latest_score_snapshot` snapshots.

## Requirements Advanced

- R009 — S03 advanced the realtime-coaching requirement from “one paced primary action” to “one shared next-turn coaching rule”: stage context, weakest/declining sales dimensions, and action-card text now converge through one backend resolver reused by classic + StepFun.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

No product-scope deviation was introduced. The only execution adjustment was operational: backend pytest suites were run sequentially, not in parallel, to avoid the repo’s known `pytest-cov` coverage combine race.

## Known Limitations

- S03 proves next-turn rule convergence inside realtime coaching only. It does not yet prove that the surviving live `action_card` direction matches report `main_issue` / `next_goal`; that remains S04.
- S03 does not add degraded/resume visibility for coach failures. A missing coach surface can still be ambiguous between “no issue detected” and “coach chain degraded”; that remains S05.
- No live browser/runtime UAT was required for this slice. The proof is artifact-driven through focused backend diagnostics and parity tests.
- Replay/report persistence schemas were intentionally left unchanged. The richer stage/score context remains backend-only for now.

## Follow-ups

- S04 should align report/replay `main_issue` / `next_goal` with the same coaching-focus seam instead of inventing a second read-side mapping rule.
- S05 should reuse the new classic/StepFun context boundary when exposing explicit coach degraded / resumed status.
- S06 should treat the focused S03 tests as the authoritative preflight before any live end-to-end UAT, because breaking the shared coaching-focus seam would invalidate both runtime modes at once.

## Files Created/Modified

- `backend/src/common/effectiveness/evaluator.py` — added `resolve_sales_coaching_focus(...)`, normalized stage/score extraction, and rich-context `build_action_card(...)` wiring.
- `backend/src/common/effectiveness/schemas.py` — added typed sales stage/focus/dimension vocabulary for the shared coaching-focus seam.
- `backend/src/common/effectiveness/__init__.py` — re-exported `resolve_sales_coaching_focus`.
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — passed rich stage/score context through the shared action-card build path while preserving S02 dedupe semantics.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — forwarded classic raw stage and score payloads into the arbiter so classic action cards become stage-aware and declining-dimension-aware.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — retained `_latest_stage_data`, forwarded raw score deltas/trends to the arbiter, and kept outward score snapshots stable.
- `backend/tests/unit/test_effectiveness_sales_coaching_focus.py` — pinned the new shared discovery / objection / closing coaching triples and weakest-dimension action-card changes.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — pinned stage-aware score action-card changes, declining-dimension overrides, duplicate suppression, and context preservation.
- `backend/tests/unit/test_capability_processor.py` — proved classic runtime now emits the shared sales coaching text from raw stage/score inputs.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — proved StepFun parity, `_latest_stage_data` retention, and stable public snapshot shapes alongside richer arbiter context.
- `.gsd/REQUIREMENTS.md` — advanced R009 with S03’s shared next-turn coaching proof.
- `.gsd/milestones/M002/M002-ROADMAP.md` — marked S03 complete.
- `.gsd/milestones/M002/slices/S03/S03-SUMMARY.md` — recorded the slice outcome, verification, and downstream guidance.
- `.gsd/milestones/M002/slices/S03/S03-UAT.md` — captured the tailored artifact-driven UAT for this slice.
- `.gsd/PROJECT.md` — refreshed current-state continuity to include shipped M002/S03 behavior.

## Forward Intelligence

### What the next slice should know
- There is now one authoritative backend seam for “下一轮最该怎么推进”: `resolve_sales_coaching_focus(...)`. S04 should derive report/replay language from that seam or from rules explicitly compatible with it, not by reconstructing stage/score logic elsewhere.

### What’s fragile
- The rich-context rule only activates when callers keep passing `stage_context` / `score_context` all the way into `build_action_card(...)`. If a future refactor trims those payloads before the arbiter, action cards silently fall back to the old pass-flags-only behavior.
- StepFun parity depends on a deliberate split: public `score_update` stays slim and stable, while the arbiter gets richer backend-only context. Collapsing those two concerns into one payload will either break consumers or weaken coaching quality.

### Authoritative diagnostics
- Start with `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`, `backend/tests/unit/test_realtime_feedback_arbiter.py`, and `backend/tests/unit/test_stepfun_realtime_handler.py::test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable`. Those tests pin the exact seam S04-S06 now depend on.

### What assumptions changed
- We started S03 with an implicit assumption that shared pacing from S02 was enough to make live coaching coherent. That was false: one paced action card can still be contextually wrong if stage guidance and score deltas are stripped before the decision. S03 corrected that by making context preservation, not just pacing, part of the authoritative backend rule boundary.

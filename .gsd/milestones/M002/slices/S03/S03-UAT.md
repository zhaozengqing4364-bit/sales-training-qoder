# S03: 阶段推进教练与下一轮规则闭环 — UAT

**Milestone:** M002  
**Written:** 2026-03-24T22:19:01+08:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 proves backend rule convergence, not live model UX. The slice is complete when one shared sales coaching-focus rule changes `action_card` text from stage + score context, classic and StepFun both feed equivalent rich context into that rule, and StepFun keeps its public `score_update` / `_latest_score_snapshot` contract stable while doing so.

## Preconditions

- Run from repo root `/Users/zhaozengqing/github/销售训练qoder`.
- Backend dependencies are installed in `backend/venv`.
- Run backend pytest suites sequentially, not in parallel, because this repo’s `pytest-cov` combine step can false-fail when backend runs overlap.
- No local frontend or backend dev server is required for this UAT.

## Smoke Test

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv
   ```
2. **Expected:** all four focused coaching-focus tests pass, showing that discovery/evidence, objection/handling, closing/next-step, and weakest-dimension action-card switching are pinned by explicit assertions.

## Test Cases

### 1. Shared coaching-focus rule changes next-turn guidance by stage and weakest dimension

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv
   ```
2. Confirm these cases pass:
   - `test_resolve_sales_coaching_focus_for_discovery_evidence_gap`
   - `test_resolve_sales_coaching_focus_for_objection_handling_gap`
   - `test_resolve_sales_coaching_focus_for_closing_next_step_gap`
   - `test_build_action_card_weakest_dimension_changes_next_turn_rule`
3. Re-run the most specific selector:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv
   ```
4. **Expected:**
   - discovery stage with weak `证据使用` yields the evidence-focused action card
   - objection stage yields the objection-handling action card
   - closing stage yields the next-step-locking action card
   - changing the weakest discovery dimension from `证据使用` to `客户收益连接` changes `next_turn_rule` accordingly

### 2. Classic runtime now feeds raw stage + score context into the shared arbiter without losing pacing behavior

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py
   ```
2. Run the focused context-preservation selector:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv
   ```
3. **Expected:**
   - `test_stage_context_can_change_score_primary_action_card` passes, proving identical score context can still produce different action cards when stage changes
   - `test_declining_dimension_can_change_score_primary_action_card` passes, proving a declining dimension can override a merely low static score
   - `test_realtime_scoring_action_card_uses_sales_effectiveness_semantics` and `test_realtime_scoring_action_card_uses_declining_dimension_from_raw_score_payload` pass, proving classic `CapabilityProcessor` forwards raw context into the shared rule
   - `test_preserve_context_without_primary_action` passes, proving stage/score context is still retained even when there is no primary action card to emit
   - same-turn duplicate suppression remains green rather than regressing under the richer context path

### 3. StepFun matches classic next-turn direction while keeping public score snapshots stable

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv
   ```
2. Confirm these focused behaviors pass inside the verbose output:
   - `test_analyze_and_emit_sales_stage_retains_latest_rich_stage_data_for_followup_feedback`
   - `test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable`
   - `test_run_realtime_feedback_uses_declining_dimension_to_match_classic_action_card`
3. **Expected:**
   - `_latest_stage_data` preserves `guidance` / `key_actions` / `progress` for follow-up arbitration
   - arbiter receives raw `dimensions[*].delta` / `trend` data and full stage context
   - emitted `score_update` continues to contain only the stable public snapshot fields (`overall_score`, `dimension_scores`, `suggestions`, `stage_name`, etc.) and does **not** expose raw `dimensions`
   - StepFun emits the same objection-handling action-card direction classic would emit for the same stage/score input

### 4. Full slice gate stays green after classic + StepFun convergence

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py
   ```
2. **Expected:**
   - all tests pass in one fresh slice-level run
   - no classic/StepFun expectation drift remains after both runtimes start using the shared coaching-focus rule
   - no public payload migration is required for the passing suite

## Edge Cases

### Stage context exists but there is no primary action card

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv
   ```
2. **Expected:** the arbiter returns `primary_source is None` and `action_card is None`, but still preserves `stage_context` and `score_context` for downstream inspection.

### A declining dimension should beat a merely low-but-stable dimension when they imply different actions

1. Re-run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k declining_dimension_can_change_score_primary_action_card -vv
   ```
2. **Expected:** the objection-stage action card flips from evidence-focused text to objection-handling text once `异议处理` is marked as declining.

### StepFun richer arbitration must not leak extra fields into the public score snapshot

1. Re-run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -k score_update_stays_stable -vv
   ```
2. **Expected:** the test proves `dimensions` remains absent from outbound `score_update`, even though the arbiter consumed raw `dimensions[*].delta/trend` internally.

## Failure Signals

- `build_action_card(...)` starts emitting the same generic next-turn rule regardless of stage or weakest/declining dimension.
- Classic tests pass only when stage/score context is missing, indicating the arbiter handoff regressed to suggestion/pass-flags-only behavior.
- StepFun action-card expectations drift from classic after a handler change, even though the stage/score inputs are equivalent.
- `_latest_stage_data` stops retaining rich stage guidance, causing follow-up StepFun coaching to lose stage-specific context.
- Outbound `score_update` starts exposing raw `dimensions` or other arbiter-only fields, signaling an unintended public contract change.
- Backend verification is run in parallel and ends with coverage combine errors despite otherwise passing tests.

## Requirements Proved By This UAT

- R009 — proves the “next-turn rule convergence” portion of realtime coaching: stage context, weakest/declining dimensions, and action-card wording now resolve through one shared backend seam across classic + StepFun.

## Not Proven By This UAT

- Whether report / replay `main_issue` and `next_goal` align with the same coaching-focus seam for the same session (S04).
- Whether coach degraded / resumed states are explicitly visible and diagnosable in the runtime/UI (S05).
- Live human-perceived usefulness in a real sales rehearsal; this slice intentionally stops at backend integration proof.

## Notes for Tester

- Treat `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`, `backend/tests/unit/test_realtime_feedback_arbiter.py`, and the focused StepFun handler tests as the authoritative diagnostics for S03. They pin the rule boundary downstream slices depend on.
- If classic action cards look generic again, inspect whether `stage_context` / `score_context` still reach `RealtimeFeedbackArbiter.decide(...)` and `build_action_card(...)` before assuming the shared helper regressed.
- If StepFun parity breaks, check whether `_latest_stage_data` or raw `score_context_for_arbiter` was flattened into the stable public snapshot shape. The slice depends on those remaining separate.

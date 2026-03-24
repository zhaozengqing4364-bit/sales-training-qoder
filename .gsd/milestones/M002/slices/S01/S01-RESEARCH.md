# M002/S01 — Research

**Date:** 2026-03-24

## Requirement Focus

S01 directly owns **R009** and supports **R003 / R005**.

For this slice, "done" is not "the labels look more sales-like". The slice only really lands if the live training page uses the same sales vocabulary and action logic that the backend already persists and the canonical report already trusts. The critical question is therefore: **which runtime path is the authority for the learner-facing realtime panel, and where does drift still remain?**

## Summary

This is **targeted closure work**, not greenfield feature work.

The default StepFun sales path already contains most of the S01 architecture:

- `backend/src/agent/capabilities/realtime_scoring.py` already emits the five sales dimensions `价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` already turns that into the live websocket `score_update` payload with canonical `overall_score`, `dimension_scores`, `suggestions`, and `stage_name`.
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` already canonicalizes persisted `score_snapshot` to the stable `overall_score` shape.
- `backend/src/common/effectiveness/evaluator.py` already maps the five live dimensions into the three report rollups and already generates sales-specific `main_issue`, `next_goal`, and `action_card` logic.
- `web/src/hooks/websocket/message-handlers.ts` and `web/src/components/practice/ScorePanel.tsx` already accept and render the sales vocabulary, and the focused tests already assert that behavior.

So the main S01 risk is **not missing sales scoring logic**. The main risks are at the seams:

1. **Legacy voice mode is still reachable.** The agent launch page defaults to `stepfun_realtime`, but still exposes a legacy toggle. When the session resolves to legacy mode, the runtime goes through `enhanced_handler.py` + `capability_processor.py`, and that code still derives `action_card` pass-flag logic from old `communication / structure` assumptions instead of the sales rollup helper used by StepFun.
2. **Frontend compatibility fallbacks are intentionally broad.** `ScorePanel.tsx` still preserves legacy/unknown dimensions, and `message-handlers.ts` still maps generic `evaluation_feedback` into the same `scores` state. That is useful for compatibility, but it means S01 needs contract-focused tests or old vocabulary can drift back in without obvious breakage.
3. **The report contract is already intentionally different.** The canonical report page compresses five live dimensions into three rollups (`logic / accuracy / completeness` → `价值表达 / 证据与收益 / 异议推进`). S01 should not try to make practice-page/live payloads and report payloads identical by expanding the report contract.

Per the repo-local `safe-grow` skill, the smallest correct move is: **prove and harden the StepFun sales live contract first, then make an explicit scope decision about legacy mode instead of silently assuming it away.**

## Recommendation

### Approach comparison

**A. StepFun live-contract closure only** — **Recommended**

Treat `voice_mode=stepfun_realtime` as the S01 authority path and close the remaining gaps there:

- add missing backend tests around emitted realtime websocket payloads;
- keep the five-dimension live contract;
- keep the three-rollup report contract unchanged;
- tighten only copy/consumer gaps that still drift on the StepFun path;
- record legacy mode as an explicit follow-up risk if not fixed in this slice.

Why this is the best fit:

- It follows `safe-grow`: one issue, smallest direct change, no broad refactor.
- Most of the S01 behavior already exists on StepFun, so this path mainly needs proof and seam-hardening.
- It avoids reopening S02/S03/S06/S07 reader contracts that already trust the three-rollup report line.

**B. Cross-mode parity (StepFun + legacy enhanced handler)**

In addition to A, update `backend/src/sales_bot/websocket/components/capability_processor.py` so legacy mode computes `action_card` input from `build_sales_effectiveness_metrics(...)` rather than the old `communication / structure` fallback. This is the more product-complete choice **if** legacy voice mode is still considered supported for M002.

Tradeoff: correct if legacy stays exposed, but materially larger because the old enhanced runtime has a different persistence/report authority line.

**C. Frontend-only relabeling**

Not recommended. The StepFun backend already sends sales-shaped data. A frontend-only pass would mostly hide the remaining runtime-path drift and make the slice look done without actually proving it.

## Implementation Landscape

### What already exists and should be preserved

- `backend/src/agent/capabilities/realtime_scoring.py`
  - The live sales rubric already exists here.
  - Emits exactly five dimensions with stable names and weighted overall scoring.
  - Also generates the single short feedback string that becomes the live suggestion/action-card input.

- `backend/src/agent/capabilities/sales_stage.py`
  - Owns stage ids, labels, key actions, guidance text, and progress calculation.
  - If S01 needs stage copy changes, this is the seam. The detection model is still keyword-based, but the user-visible labels are already sales-oriented.

- `backend/src/agent/capabilities/fuzzy_detection.py`
  - Independent of the sales rubric, but still part of the live right-panel contract and action-card precedence.
  - S01 should not redesign its pacing; that belongs to S02.

- `backend/src/common/effectiveness/evaluator.py`
  - Critical authority seam.
  - Already contains:
    - alias normalization for the five sales dimensions;
    - rollup mapping into `logic_score / accuracy_score / completeness_score`;
    - sales-specific `pass_flags` interpretation;
    - sales-specific `main_issue`, `next_goal`, and `build_action_card(...)`.
  - This is why S01 should not invent a second action-card or report scorer.

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
  - Canonicalizes persisted score snapshots to `overall_score` + `dimension_scores`.
  - Good compatibility boundary. If any runtime path still emits `overall`, this helper already absorbs it.

- `backend/src/common/api/practice.py`
  - Important read/write boundary.
  - `_apply_sales_realtime_score_snapshot_to_session(...)` already maps the five live dimensions into the report rollups.
  - `_sync_sales_realtime_terminal_evidence(...)` only does this automatically for `voice_mode="stepfun_realtime"`.
  - That means the report alignment line is already explicit — and also why legacy mode is the main scope question.

- `web/src/hooks/websocket/types.ts`
  - The stable frontend live contract already exists:
    - `ScoreUpdate { overall_score, dimension_scores, suggestions, stage_name, turn_count }`
    - `SalesStage`
    - `ActionCard`
  - This file does not need redesign unless the transport shape changes.

- `web/src/components/practice/ScorePanel.tsx`
  - Already sales-first in display order/icons.
  - Still deliberately keeps legacy and unknown dimension fallback support.
  - That fallback is useful; do not remove it just to make the code look cleaner.

- `web/src/components/practice/RightPanelContent.tsx`
  - The live practice page already composes the current stage, fuzzy detections, action card, and score panel.
  - Leave pacing/composition changes for S02. S01 should only change this file if the semantics/copy are wrong.

### Files that define the active StepFun truth line

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - This is the most important S01 file.
  - Natural seams inside it:
    - `_analyze_and_emit_sales_stage(...)`
    - `_run_realtime_feedback(...)`
    - `_send_score_update(...)`
    - `_send_action_card(...)`
    - `_create_state_snapshot(...)` / `_restore_session_state(...)`
  - On the StepFun path, this file already keeps stage → score snapshot → action card on one line.
  - Missing piece: focused tests do not currently prove the emitted `score_update` and `action_card` payload contents directly.

- `backend/tests/unit/test_realtime_scoring.py`
  - Good focused coverage for the five-dimension scorer itself.
  - Already proves value / benefit / evidence / objection / next-step language is rewarded.

- `backend/tests/unit/test_sales_stage.py`
  - Good focused coverage for stage ids, labels, progress, and transitions.

- `backend/tests/unit/test_effectiveness_sales_baseline.py`
  - Good focused coverage for rollup mapping and sales-specific `main_issue` / `next_goal` logic.

### Files that expose the remaining drift / scope risk

- `backend/src/sales_bot/websocket/router.py`
  - Both runtime paths are still reachable.
  - If persisted session `voice_mode == "stepfun_realtime"`, router uses `StepFunRealtimeHandler`.
  - Otherwise it falls back to `EnhancedSalesHandler`.

- `backend/src/sales_bot/websocket/enhanced_handler.py`
  - Legacy runtime entry.
  - Still instantiated for sales sessions when voice mode is not StepFun.

- `backend/src/sales_bot/websocket/components/capability_processor.py`
  - This is the one backend file that still obviously carries old assumptions.
  - It sends `score_update` using the capability result directly, so the live dimension vocabulary may already be sales-shaped.
  - But its `pass_flags_for_card` logic still derives from `communication_score` / `structure_score` fallback, which no longer matches the sales-specific StepFun/evaluator path.
  - If legacy mode is in-scope, this is the first backend parity seam.

- `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
  - Launch page defaults `voiceMode` to `stepfun_realtime`, but still exposes a legacy toggle.
  - This is the concrete proof that legacy mode is not merely dead code.

### Frontend test coverage status

- `web/src/components/practice/ScorePanel.test.tsx`
  - Already asserts the five sales dimensions render correctly.
  - Also explicitly preserves unknown/legacy fallback behavior.

- `web/src/hooks/websocket/message-handlers.test.ts`
  - Already asserts `score_update` keeps sales vocabulary unchanged in state.
  - Also asserts the generic `evaluation_feedback` fallback path still works.

- Missing / fragile point in `web/src/hooks/websocket/message-handlers.ts`
  - The `score_update` idempotence guard only compares `overall_score` and `turn_count`.
  - If the same turn later sends different `dimension_scores`, `stage_name`, or `suggestions` with the same overall score, the update is dropped.
  - That is not a confirmed S01 bug today, but it is a real consumer fragility if the backend ever sends richer same-turn refreshes.

## Natural Seams

1. **StepFun payload proof seam**
   - First prove what the live StepFun handler actually emits before changing UI copy.
   - Best file to extend first: `backend/tests/unit/test_stepfun_realtime_handler.py`.
   - This is the highest-leverage task because it will tell the planner whether S01 needs code changes or mostly just stronger guardrails.

2. **Legacy parity seam**
   - If the slice must cover both voice modes, `backend/src/sales_bot/websocket/components/capability_processor.py` is the first backend fix point.
   - Do not spread the same logic into multiple handlers; reuse the sales rollup helper already used by StepFun.

3. **Frontend consumer seam**
   - `web/src/hooks/websocket/message-handlers.ts` + `web/src/components/practice/ScorePanel.tsx` are the only live sales consumer surfaces that matter for S01.
   - `RightPanelContent.tsx` is composition, not scoring logic.

4. **Report boundary seam**
   - `backend/src/common/api/practice.py` already intentionally compresses live five-dimension snapshots into three report rollups.
   - Preserve that boundary unless the user explicitly wants a report contract change.

## What to Prove First

Start with **backend StepFun handler contract tests**, not UI relabeling.

Why:

- the capability unit tests already prove the scorer itself;
- the report integration test already proves the read-side rollups;
- what is still under-proved is the live websocket payload path that sits between them.

The planner should assume the first executable task is:

- extend `backend/tests/unit/test_stepfun_realtime_handler.py` to assert that a real `_run_realtime_feedback(...)` cycle emits:
  - `score_update` with the five sales dimensions and canonical keys;
  - `stage_name` matching the emitted stage;
  - `action_card` phrased from sales semantics rather than generic communication-flow logic.

If that test passes with only small adjustments, S01 remains a tight slice. If it fails on the legacy path too, the planner can then decide whether to expand scope or explicitly constrain the slice to StepFun.

## Verification Strategy

### Backend focused verification

Use the existing sales baseline suites first:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_sales_stage.py tests/unit/test_fuzzy_detection.py tests/unit/test_effectiveness_sales_baseline.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py`

If legacy parity is in scope, add/extend focused coverage for:

- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/sales_bot/websocket/enhanced_handler.py`

### Existing downstream safety nets

Keep the existing report/read-side line green:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_sales_value_training_flow.py tests/contract/test_practice_evidence_contract.py`

This is enough to prove S01 did not accidentally break the already-established sales report semantics.

### Frontend focused verification

- `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts'`

If the planner changes the message dedupe behavior or right-panel copy, also run:

- `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'`

### Runtime/UAT recommendation

A full browser wave is not strictly necessary for the scout phase, but if the executor needs live proof, the smallest meaningful runtime check is:

1. create a fresh sales session in `stepfun_realtime` mode;
2. drive one turn that mentions customer benefit + ROI + evidence + next step;
3. confirm the right panel shows the five sales dimensions and a sales-specific action card;
4. confirm `/api/v1/practice/sessions/{id}/report` still reads as the three rollups, not a duplicated five-dimension report.

## Common Pitfalls

- **Trying to make report and realtime payloads identical**
  - The live contract is five dimensions.
  - The canonical report contract is three rollups.
  - S01 should align semantics, not collapse these two shapes into one.

- **Deleting fallback support from the frontend**
  - `ScorePanel` and `message-handlers` intentionally preserve legacy/unknown dimensions and `evaluation_feedback`.
  - Removing that support would create unnecessary regression risk outside the StepFun sales path.

- **Touching pacing/layout in S01**
  - `RightPanelContent.tsx` already shows multiple simultaneous surfaces.
  - That noise problem belongs to S02. S01 should stay on semantic alignment.

- **Assuming legacy mode is dead because StepFun is default**
  - It is not dead; it is still user-selectable on the agent launch page.
  - The planner must either include it or explicitly scope it out.

- **Reimplementing sales action-card logic in another place**
  - `common/effectiveness/evaluator.py` already owns sales rollup/action-card semantics.
  - Reuse it; do not create a second version in a handler or component.

## Open Risks

- **Legacy-mode support ambiguity**
  - If the product still treats legacy voice mode as supported, S01 is larger than a StepFun-only hardening pass.
  - If the product treats StepFun as the only meaningful M002 path, the slice should say that explicitly and leave legacy parity for later.

- **Consumer-side stale-update risk**
  - `message-handlers.ts` only dedupes `score_update` on `overall_score` + `turn_count`.
  - That is acceptable for one-shot per-turn updates, but brittle if future work sends richer same-turn refreshes.

- **Reconnect snapshot is persisted but not fully rehydrated into UI state**
  - StepFun persists `latest_score_snapshot` and `latest_action_card`, but the current `reconnected` frontend handler only restores status/ai-state.
  - This is more of an S05 concern than an S01 blocker, but the planner should know the reconnect contract is not fully surfaced to the right panel yet.

## Skills Discovered

Installed and directly relevant:

| Technology | Skill | Status |
|---|---|---|
| React / Next.js | `react-best-practices`, `vercel-react-best-practices` | installed |
| Full-stack React + Python integration | `fullstack-dev` | installed |

Non-installed but potentially useful if the user wants extra domain guidance later:

| Technology | Skill | Install |
|---|---|---|
| FastAPI | `wshobson/agents@fastapi-templates` | `npx skills add wshobson/agents@fastapi-templates` |
| React WebSocket | `claude-dev-suite/claude-dev-suite@react-websocket` | `npx skills add claude-dev-suite/claude-dev-suite@react-websocket` |

For this slice, the installed skills are already sufficient; the non-installed options are optional only.

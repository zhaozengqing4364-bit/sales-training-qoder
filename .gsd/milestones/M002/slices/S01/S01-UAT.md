# S01: 实时评分与训练页销售语义对齐 — UAT

**Milestone:** M002
**Written:** 2026-03-24T19:25:11+08:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01’s proof target is contract alignment, not live runtime quality. This slice succeeds when both sales runtime paths emit the same coaching vocabulary, the practice-page consumer preserves richer same-turn sales updates, and the existing report-side three-rollup contract stays unchanged.

## Preconditions

- Run from the repo root `/Users/zhaozengqing/github/销售训练qoder`.
- Backend dependencies are installed in `backend/venv`.
- Web dependencies are installed in `web/node_modules`.
- Run backend pytest suites sequentially, not in parallel, because this repo’s default `pytest-cov` setup can race on `.coverage.*` combine files.
- No local server is required for this UAT; all checks are command-driven.

## Smoke Test

1. Run:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx'
   ```
2. **Expected:** both suites pass, proving the practice-page consumer is still sales-first and that same-turn score updates are not discarded.

## Test Cases

### 1. Backend realtime contracts stay sales-shaped across StepFun and classic mode

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py
   ```
2. Inspect the passing cases in the output, especially:
   - `test_run_realtime_feedback_emits_canonical_sales_score_and_action_card`
   - `test_realtime_scoring_action_card_uses_sales_effectiveness_semantics`
3. **Expected:**
   - StepFun feedback emits five sales `dimension_scores`, `stage_name`, `suggestions`, and a sales `next_turn_rule`
   - classic-mode action cards use the shared sales effectiveness helper instead of generic communication/structure heuristics
   - all tests pass without changing report-side semantics

### 2. Focused diagnostic surfaces still catch stage/action drift

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'
   ```
2. **Expected:**
   - four focused tests pass
   - unchanged stage updates are suppressed until the stage actually changes
   - the canonical StepFun action-card payload remains sales-shaped
   - the classic runtime path stays aligned to the same action-card semantics

### 3. Report-side three-rollup evidence contract stays unchanged

1. Run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py
   ```
2. **Expected:**
   - report/replay contract tests pass
   - `GET /report` and replay still share the same evidence fields
   - access-control / completion-gate behavior is unchanged
   - no S01 change leaks websocket sales terminology into the canonical report contract

### 4. Practice-page consumers preserve richer same-turn sales updates and one shared rubric

1. Run:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'
   ```
2. **Expected:**
   - all four suites pass
   - `message-handlers` proves same-turn score refreshes with updated stage/suggestions/dimensions are not deduped away
   - `ScorePanel` shows the five sales dimensions first
   - unknown/fallback dimensions are still rendered instead of dropped
   - launch-page tests prove both voice modes describe the same sales scoring rubric
   - runtime lock tests stay green, proving the voice-mode affordance change did not break training-page mode boundaries

### 5. Websocket hook surface still carries the richer score-update contract end-to-end

1. Run:
   ```bash
   cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'
   ```
2. **Expected:**
   - the hook suite passes
   - the richer score-update payload still flows through the practice websocket layer without being collapsed back to overall-score-only semantics

## Edge Cases

### Same-turn refinement with unchanged overall score

1. Re-run:
   ```bash
   cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts'
   ```
2. **Expected:** a `score_update` that keeps the same `overall_score` and `turn_count` but changes `stage_name`, `suggestions`, or `dimension_scores` is still treated as a meaningful update.

### Unknown dimensions must remain visible

1. Re-run:
   ```bash
   cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx'
   ```
2. **Expected:** the panel keeps the five canonical sales dimensions first, but any unknown/fallback dimension still renders rather than disappearing.

### Stage duplicates must not spam when the stage has not changed

1. Re-run:
   ```bash
   cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_capability_processor.py -k 'stage_update'
   ```
2. **Expected:** no duplicate stage event is emitted for an unchanged stage, but a real stage change still emits a fresh update.

## Failure Signals

- Backend tests reintroduce `沟通技巧` / `销售流程`-style generic action-card logic on the classic runtime path.
- StepFun payload assertions stop seeing five sales dimensions, sales `suggestions`, or `next_turn_rule`.
- Frontend tests fail because `score_update` dedupe falls back to `overall_score + turn_count` and same-turn refinements disappear.
- `ScorePanel` drops unknown dimensions instead of rendering them.
- Launch-page tests start implying that classic and StepFun modes use different scoring vocabularies.
- Practice evidence contract tests fail because S01 changes accidentally altered the existing report-side three-rollup read contract.

## Requirements Proved By This UAT

- R009 — proves the contract-alignment portion of the realtime-coaching requirement: the training page now has one authoritative sales rubric across both runtime paths and preserves same-turn coaching refinements.

## Not Proven By This UAT

- Whether coach prompts are paced well enough or reduced to one primary action per turn (S02).
- Whether realtime coaching and post-session `main_issue` / `next_goal` remain aligned for the same session (S04).
- Whether coach degraded / reconnect states are explicit and diagnosable in the product UI/runtime (S05).
- Human-experience quality in a live sales conversation; this slice intentionally stops at contract proof.

## Notes for Tester

- Treat the focused backend tests and the websocket hook/panel tests as the authoritative diagnostics for this slice. They pin the exact contract downstream M002 slices depend on.
- If a backend pytest run reports a coverage-combine `FileNotFoundError` after tests appear to pass, rerun sequentially before concluding there is a product regression.
- If a future change needs to expand coaching semantics, extend the existing sales payload boundary (`dimension_scores`, `stage_name`, `suggestions`, `next_turn_rule`) instead of introducing a second parallel realtime vocabulary.

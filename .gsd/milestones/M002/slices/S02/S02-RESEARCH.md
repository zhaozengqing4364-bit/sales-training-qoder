# M002/S02 — Research

**Date:** 2026-03-24

## Summary

S02 owns the next real delivery step for **R009**: the product already speaks one sales-first realtime contract after S01, but it still does not control *how many* coach surfaces compete in the same turn. The low-level pieces exist in isolation: `sales_stage` already suppresses duplicate stage events, `fuzzy_detection` already has per-category cooldown, and the frontend now keeps same-turn `score_update` refinements instead of dropping them. What is still missing is a cross-channel policy that decides which signal is the primary action for this turn, which signals should stay informational only, and when old coaching state should be cleared instead of lingering.

The main drift is no longer in scoring math; it is in orchestration. Both realtime backends still emit their coach signals independently, and the practice-page right panel renders `actionCard`, `fuzzyDetections`, `salesStage`, and `ScorePanel` suggestions together. Worse, the frontend never clears stale `actionCard` / `fuzzyDetections` on a new user turn unless another payload overwrites them, so an old instruction can survive into later turns. That is exactly the failure mode the roadmap describes as “刷屏 / 打架”.

The smallest safe path is a **shared backend arbitration helper** reused by `CapabilityProcessor` and `StepFunRealtimeHandler`, plus a **light frontend state/render pass** that clears ephemeral coach hints on a new final transcript and suppresses duplicate textual coaching when a primary `action_card` already exists. That keeps S01’s websocket contract intact, avoids inventing new score vocabularies, and leaves S04 free to align `main_issue` / `next_goal` on top of the same `suggestions` / `next_turn_rule` line instead of another rewrite.

## Recommendation

Use a **backend-first arbitration policy with lightweight frontend precedence rules**.

Recommended approach:

1. Keep `fuzzy_detection`, `sales_stage`, and `realtime_scoring` focused on producing raw signals.
2. Add one small shared policy helper for sales realtime feedback arbitration.
3. Reuse that helper from both runtime surfaces:
   - `backend/src/sales_bot/websocket/components/capability_processor.py`
   - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
4. On the frontend, treat `actionCard` as the highest-priority coaching surface, while `ScorePanel` stays the numeric/status surface.
5. Clear ephemeral coach hints (`actionCard`, `fuzzyDetections`) when a new final transcript arrives, so old turn-specific advice does not bleed into the next turn.

Why this approach:

- A frontend-only fix is too weak. The client does not currently receive enough consistent turn metadata across all coach events to infer priority reliably, especially on the classic path.
- A capability-local fix is the wrong seam. The product problem is cross-channel competition after signals are generated, not the individual signal generators.
- A shared arbiter matches the project’s safe-grow rule of “smallest direct change”: one policy seam, existing contracts preserved, both runtime paths kept aligned.
- Per the `react-best-practices` skill, UI priority should be derived from existing state during render / message reduction, not added as another effect-heavy state machine.

## Implementation Landscape

### Key Files

- `backend/src/sales_bot/websocket/components/capability_processor.py` — Classic voice path. `run_and_send_feedback()` currently sends `fuzzy_detection`, `stage_update`, `score_update`, then always builds/sends `action_card` afterward (`run_and_send_feedback` at line 43; senders at lines 185/203/221/239). This is the best classic-path seam for post-capability arbitration.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun path. `_run_realtime_feedback()` emits fuzzy/score/action independently (`_run_realtime_feedback` at line 1908; senders at 1853/1866/1892) and `_analyze_and_emit_sales_stage()` already dedupes unchanged stage events (`_analyze_and_emit_sales_stage` at 3861). `_create_state_snapshot()` / `_restore_session_state()` only persist `last_emitted_stage`, `latest_score_snapshot`, and `latest_action_card` today (lines 499 and 526).
- `backend/src/common/effectiveness/evaluator.py` — `build_action_card()` is pure and shared by both runtime surfaces (line 424). It already enforces “one card”, but it chooses the **first** fuzzy detection, not necessarily the highest-priority one.
- `backend/src/agent/capabilities/fuzzy_detection.py` — Existing per-category cooldown lives here (`cooldown_seconds` config at line 105, execute path at line 204). Reuse it; do not replace it with a second low-level throttle.
- `backend/src/agent/capabilities/realtime_scoring.py` — Generates sales dimension scores and a single feedback string (`execute` at line 193, `_generate_feedback` at 367). This feedback is currently duplicated into both `score_update.suggestions` and `action_card.replacement` downstream.
- `backend/src/agent/capabilities/runner.py` — `run_all()` executes capabilities in parallel on shared `AgentContext` (line 144). That means cross-channel pacing logic should not be hidden inside individual capability `execute()` methods where ordering assumptions can race.
- `backend/src/presentation_coach/services/feedback_service.py` — Existing reference pattern for explicit cooldown / priority policy (`PresentationFeedbackRuleConfig`, `feedback_cooldown_seconds`, and policy-driven interruption decisions).
- `backend/src/presentation_coach/services/semantic_point_tracker.py` — Existing reusable `FeedbackDeduplicator` pattern (`class FeedbackDeduplicator` at line 336, `should_send()` at 347).
- `web/src/hooks/websocket/message-handlers.ts` — Current client reducer. It dedupes only `stage_update` and `score_update` (`isSameSalesStage` at line 65, `isSameScoreUpdate` at line 103, handlers at 550/559/573/587). It never clears stale `actionCard` or `fuzzyDetections` on a new user turn. The transcript handlers at lines 247 and 260 are the lowest-blast-radius place to reset ephemeral coaching state.
- `web/src/components/practice/RightPanelContent.tsx` — Current rendering seam. It shows `本轮唯一动作`, `实时提示`, `当前阶段`, and `ScorePanel` together (action card at line 93, fuzzy panel at 116, stage panel at 164). This is where visible cross-channel competition happens.
- `web/src/components/practice/ScorePanel.tsx` — Keeps score visibility and stage badge, but also renders free-text suggestions (component starts at line 153). If `actionCard` is present, these suggestions are usually duplicate coaching rather than new information.
- `backend/src/sales_bot/websocket/enhanced_handler.py` and `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Both runtime surfaces already emit final ASR transcript events (`asr_transcript` senders at enhanced handler line 915 and StepFun line 4053), so frontend clearing on final transcript can work across both voice modes without new transport.
- `backend/tests/unit/test_capability_processor.py` — Existing classic-path stage/action-card focused tests (`test_stage_update_emits_once_for_unchanged_stage`, `test_realtime_scoring_action_card_uses_sales_effectiveness_semantics`). Extend here for arbitration behavior.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — Existing StepFun focused tests (`test_run_realtime_feedback_emits_canonical_sales_score_and_action_card` at line 1474, stage-dedupe tests around 1268). Extend here for StepFun arbitration behavior.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — Extend only if S02 decides any pacing state must survive reconnect (`test_create_state_snapshot_captures_minimal_runtime_recovery_fields...` at line 51).
- `web/src/hooks/websocket/message-handlers.test.ts` — Existing client-state tests already lock same-turn score refreshes, full-payload idempotence, and reconnect behavior (lines 383, 422, 479, 614). Extend here for ephemeral reset rules.
- `web/src/components/practice/RightPanelContent.test.tsx` — Does not exist yet; worth adding because there is currently no focused test for combined right-panel precedence.

### Build Order

1. **Prove the backend arbitration rules first.**
   - Add focused failing tests around repeated same-turn coaching, repeated cross-turn coaching within cooldown, and severity/priority selection for the single primary action.
   - If any pacing state must survive reconnect, pin that behavior in `test_stepfun_realtime_persistence.py` before implementation.

2. **Implement one shared arbitration helper and wire both runtime paths to it.**
   - Keep `build_action_card()` pure.
   - Put timing / dedupe / primary-action selection in a shared helper near the websocket feedback surfaces, not inside the scoring or fuzzy capabilities.
   - Reuse the same helper from `CapabilityProcessor` and `StepFunRealtimeHandler` so S01’s classic/StepFun alignment stays intact.

3. **Then adjust frontend state clearing and render precedence.**
   - Clear ephemeral turn-bound hints on final transcript.
   - Keep scores/stage visible, but suppress duplicate text coaching when `actionCard` is present.
   - Add a focused `RightPanelContent` test instead of spreading this across page-level tests.

4. **Only after that, consider reconnect persistence for pacing state.**
   - Do not persist more StepFun runtime state unless the tests prove it matters. Safe-grow here means persisting only the minimum state that prevents feedback bursts after reconnect.

### Verification Approach

Run backend pytest sequentially, not in parallel.

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown`
- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx' 'src/hooks/use-practice-websocket.test.ts'`

Observable behaviors worth pinning:

- Repeated unchanged stage still emits once.
- Same primary issue does not keep re-issuing a fresh action card every turn unless it meaningfully changes or cooldown expires.
- Multiple fuzzy categories in one turn resolve to the intended highest-priority action, not whichever pattern happened to be appended first.
- On a new final transcript, stale `actionCard` / `fuzzyDetections` disappear before the next turn’s coaching lands.
- When `actionCard` exists, the right panel does not simultaneously show a second competing instruction copied from `ScorePanel.suggestions`.
- If reconnect persistence is changed, StepFun restore does not cause a feedback burst or wipe required pacing history unexpectedly.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Session-scoped feedback cooldown history | `backend/src/presentation_coach/services/semantic_point_tracker.py` → `FeedbackDeduplicator` | The project already has a simple, test-covered cooldown helper. Reusing or adapting that pattern is safer than introducing two separate ad hoc timestamp maps in classic + StepFun paths. |
| Explicit priority / threshold policy | `backend/src/presentation_coach/services/feedback_service.py` → `PresentationFeedbackRuleConfig` + `_determine_interruption(...)` | S02 needs a small policy seam with readable thresholds and priority order, not scattered booleans across handlers. The presentation coach already solved this shape. |

## Constraints

- `CapabilityRunner.run_all()` executes capabilities in parallel on a shared `AgentContext`. Any cross-channel pacing or priority state that depends on ordering should live **after** result collection in `CapabilityProcessor`, not inside capability `execute()` methods.
- `FuzzyDetectionCapability` already enforces per-category cooldown. S02 should layer higher-level coach arbitration on top of that instead of breaking the capability’s local behavior.
- `build_action_card()` is used by both runtime paths. Preserve its shared contract (`issue`, `replacement`, `next_turn_rule`) because S04 will need that stable line for report alignment.
- StepFun reconnect persistence currently stores only `last_emitted_stage`, `latest_score_snapshot`, and `latest_action_card`. Any pacing state that matters across reconnect must be added deliberately and tested; otherwise leave it ephemeral.
- Keep backend and web verification commands separate. This repo’s auto-mode closer can mis-handle chained backend/web commands, and backend pytest runs should stay sequential to avoid coverage combine races.

## Common Pitfalls

- **Treating raw fuzzy detection order as business priority** — `build_action_card()` currently takes `detections[0]`, while `FuzzyDetectionCapability` appends detections in pattern order, not guaranteed severity order. Sort/normalize before card selection if S02 wants a real “single highest-priority action”.
- **Trying to solve turn scoping only in the frontend** — Only `score_update` reliably carries richer turn-level data on the StepFun path, and the classic path still emits more minimal payloads. Frontend-only arbitration will become heuristic and fragile unless the backend first chooses what to emit.
- **Leaving stale hints in client state** — `actionCard` and `fuzzyDetections` are set-latest fields today; without an explicit reset on new final transcript, old advice survives into later turns.
- **Hiding the wrong surface** — The useful distinction is “numeric/status context” vs “text coaching direction”. Keep the score panel and stage context available, but avoid rendering two separate textual instructions for the same turn.
- **Persisting too much reconnect state** — S02 only needs the minimum pacing state that prevents replay bursts. Do not turn reconnect snapshots into a full policy cache unless tests prove it is necessary.

## Open Risks

- Product/UI choice is still needed on whether `当前阶段` guidance text remains always visible when a primary action card exists, or whether stage becomes a quieter context-only surface. The code seam is clear; the precedence rule is the only unresolved product call.
- If typed-text user turns must behave identically to ASR turns in the future, confirm that every user-turn entry path still produces a transcript-equivalent reset moment. Voice paths already do.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js | `react-best-practices` | available |
| Browser-based UAT | `agent-browser` | available |
| Frontend UI precedence / polish | `frontend-design`, `best-practices` | available |
| FastAPI backend patterns | `wshobson/agents@fastapi-templates` | discoverable via `npx skills add wshobson/agents@fastapi-templates` |
| FastAPI backend patterns | `mindrally/skills@fastapi-python` | discoverable via `npx skills add mindrally/skills@fastapi-python` |
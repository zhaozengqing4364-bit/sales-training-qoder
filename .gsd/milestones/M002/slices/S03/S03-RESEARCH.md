# S03: 阶段推进教练与下一轮规则闭环 — Research

**Date:** 2026-03-24

## Summary

R009 remains the active requirement for this slice. S03 should deepen that requirement by making stage guidance, score movement, and the single primary action card point to the same next-turn move. The codebase already has the right pacing seam in `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`, but the semantics are still split: `SalesStageCapability` owns stage guidance, `RealtimeScoringCapability` owns per-dimension `trend` / `delta`, `build_action_card(...)` only uses pass flags plus one suggestion/fuzzy input, and report-side `next_goal` is generated separately from the same metrics family. The user can still receive a valid stage panel, a valid score panel, and a valid action card that were not produced from one shared rule.

Classic and StepFun runtimes are also asymmetric in exactly the places S03 cares about. `backend/src/sales_bot/websocket/components/capability_processor.py` passes raw `score_payload` and full `stage_data` into the arbiter, but `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` downgrades `score_context` to a stripped `score_snapshot` and `stage_context` to `{ current_stage, stage_name }`. So any stage-aware or delta-aware action-card logic implemented naively in one path will reopen the S01/S02 runtime drift.

Recommended path: keep the frontend as a renderer and add one shared backend coaching-focus resolver in `backend/src/common/effectiveness/evaluator.py` that consumes normalized sales scores, optional score deltas/trends, and stage context, then returns the canonical next-turn focus used by the arbiter. This follows the loaded `fullstack-dev` skill rule to keep business logic in shared service/domain code instead of handlers or UI, and the loaded `systematic-debugging` skill rule to fix the split source rather than papering over it in the panel. Use that seam first for realtime `action_card`; preserve report/replay contracts for now, but shape the helper so S04 can reuse it for `main_issue` / `next_goal` alignment without renaming any fields.

## Recommendation

Per the loaded `brainstorming` skill, there are two viable approaches here:

1. **Recommended — shared coaching-focus helper + richer arbiter inputs**
   - Add one backend resolver that decides the next-turn focus from stage context + weakest/declining sales dimension + existing pass flags.
   - Make both runtime paths feed the same normalized stage/score context into `RealtimeFeedbackArbiter`.
   - Keep the frontend largely unchanged unless the action-card payload needs optional metadata.
   - Why: lowest blast radius, preserves S02’s one-arbiter architecture, and sets up S04 without creating another rules engine.

2. **Rejected for now — frontend-side composition of stage + score + next-step rule**
   - Extend the websocket payload/UI and let the practice page infer the next move.
   - Why not: this duplicates coaching logic in the client, violates the current arbiter boundary, and makes classic/StepFun/replay/report drift more likely.

If replayable structured coach snapshots become a hard requirement inside S03, the cheap version is to keep persisting `ai_feedback` text plus `score_snapshot.stage_name` and `sales_stage`. Avoid a DB/model migration unless the slice explicitly needs per-turn structured `action_card` replay; current persistence only supports `score_snapshot` and `ai_feedback`, while StepFun reconnect state can already carry richer `latest_action_card` without schema work.

## Implementation Landscape

### Key Files

- `backend/src/common/effectiveness/evaluator.py` — best shared seam for S03. Today `_sales_main_issue(...)`, `_sales_next_goal(...)`, and `build_action_card(...)` each reason differently about the “next move”. `build_action_card(...)` ignores stage context and score deltas entirely; it only uses one suggestion/fuzzy detection plus pass flags. Add the canonical stage-aware coaching-focus resolver here, then have `build_action_card(...)` call it.
- `backend/src/common/effectiveness/schemas.py` — update only if the shared helper or `ActionCard` type needs optional metadata such as focus dimension or stage anchor. Keep existing `issue` / `replacement` / `next_turn_rule` fields stable.
- `backend/src/common/effectiveness/__init__.py` — re-export any new shared helper used by both realtime runtimes.
- `backend/src/agent/capabilities/realtime_scoring.py` — source of the only existing per-dimension `trend` / `delta` data (`dimensions[*]`). S03 should reuse this instead of inventing a second delta heuristic.
- `backend/src/agent/capabilities/sales_stage.py` — source of `stage_name`, `key_actions`, `guidance`, `progress`, `stage_changed`, and `previous_stage`. Reuse these as the authoritative stage context.
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — keep ownership of priority/dedupe/pacing, but stop making next-turn semantics from too little information. This file should consume the new shared helper, not grow a second planner.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic runtime reference path. It already passes full `stage_data` and raw `score_payload` into the arbiter.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun currently drops important context before arbitration: `stage_context_for_arbiter` only carries `{ current_stage, stage_name }`, and `score_context_for_arbiter` is reduced to `overall_score` / `dimension_scores` / `suggestions` / `stage_name`. Bring it to parity with the classic path before expecting stable S03 behavior.
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — existing score-snapshot normalizer. Use this if S03 needs to carry extra score-context fields safely; otherwise keep persistence minimal.
- `backend/src/common/conversation/session_evidence.py` — read-side constraint. Projection/replay currently only understand `sales_stage`, `score_snapshot`, and `ai_feedback` for per-turn coaching semantics.
- `backend/src/common/conversation/replay.py` and `backend/src/common/conversation/schemas.py` — only touch if S03 decides to persist richer per-turn coach data.
- `backend/src/common/api/practice.py` — report and replay already depend on normalized session evidence. Re-verify here if persisted coach semantics or report-adjacent outputs change.
- `web/src/components/practice/RightPanelContent.tsx` — likely minimal or no structural change. S02 already established `action_card` as the sole primary textual coach surface.
- `web/src/components/practice/ScorePanel.tsx` — only relevant if S03 wants new UI-visible score context beyond the existing bars and stage label.
- `web/src/hooks/websocket/types.ts` and `web/src/hooks/websocket/message-handlers.ts` — only touch if the `action_card` or `score_update` payload expands. Do not move planner logic here.
- `backend/tests/unit/test_effectiveness_sales_baseline.py` — best place to pin the new shared coaching-focus mapping without websocket plumbing.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — primary backend diagnostic for the S02 seam; expand it first for stage-aware / delta-aware next-turn selection.
- `backend/tests/unit/test_capability_processor.py` — locks classic runtime parity.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — locks StepFun parity; should explicitly prove the same stage/score inputs yield the same action-card output as classic mode.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — needed if `_latest_action_card` or persisted runtime score context changes.
- `backend/tests/contract/test_practice_evidence_contract.py` and `backend/tests/integration/test_practice_evidence_flow.py` — only required if S03 changes persisted per-turn analysis or replay/report-facing data.
- `web/src/components/practice/RightPanelContent.test.tsx`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — targeted frontend verification if payload or copy changes.

### Build Order

1. **Define the shared coaching-focus rule in `common.effectiveness` first.** This is the highest-risk seam because today `build_action_card(...)`, `_sales_next_goal(...)`, and stage guidance are parallel systems. Lock the mapping with focused unit tests before touching runtime handlers.
2. **Normalize arbiter inputs across classic and StepFun.** Classic already passes richer `stage_data` / `score_payload`; StepFun currently strips them. Make both runtimes feed the same normalized stage + score context into `RealtimeFeedbackArbiter` before changing output expectations.
3. **Rewire the arbiter to use the shared resolver while preserving S02 pacing behavior.** Priority, duplicate suppression, and reconnect-safe state should stay in `RealtimeFeedbackArbiter`; only the semantic “what should the one action be?” decision should move to the new shared helper.
4. **Touch frontend only if payload shape or rendered copy must change.** The safest S03 path is that the right panel remains structurally the same and simply receives a smarter `action_card`.
5. **Only extend persistence/replay if the slice explicitly needs replayable structured coach data.** Current message storage can already replay `ai_feedback` text plus `score_snapshot` and `sales_stage`; a schema change is wider and should be justified explicitly.

### Verification Approach

Per the loaded `test` skill, stay with the repo’s existing focused pytest/vitest patterns instead of inventing new suite entrypoints.

- Backend focused unit gate:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`
- If persisted message analysis or replay/report contract changes:
  - `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
- Frontend targeted gate only if payload/UI changes:
  - `cd web && npm test -- --run 'src/components/practice/RightPanelContent.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts'`
- If report-facing copy or contract moves early:
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

Manual proof target for the planner: the same stage + the same weak/declining dimension should produce the same primary action on classic and StepFun; changing stage context or the weakest dimension should change the rule text, not just the replacement sentence.

## Constraints

- Preserve the active R009 scope and the existing report-side three-rollup contract. S03 is about realtime rule closure, not renaming report `main_issue` / `next_goal` fields.
- Keep `action_card` as the only primary textual coach surface. Do not reintroduce parallel client-side text planners through `fuzzyDetections` or `ScorePanel` suggestions.
- `ConversationMessage.sales_stage` is DB-constrained to five IDs: `opening | discovery | presentation | objection | closing`. Do not persist sub-stage labels there.
- Replay/report projections only persist `sales_stage`, `score_snapshot`, and `ai_feedback`; there is no structured per-turn action-card column today.
- StepFun reconnect state already persists `latest_action_card` and `feedback_pacing_state`, so richer runtime-only action-card fields are cheap; richer replay fields are not.
- Backend pytest suites should run sequentially in this repo; parallel pytest jobs can collide during coverage combine.

## Common Pitfalls

- **Fixing only `build_action_card(...)` is not enough** — StepFun currently strips out `key_actions`, `guidance`, `progress`, and score `dimensions[*].trend/delta` before arbitration. If that normalization gap remains, classic and StepFun will diverge again.
- **Fixing only the frontend is the wrong layer** — `RightPanelContent` already obeys S02 by treating `action_card` as the sole primary coach surface. Adding more client-side rule composition would violate the shared arbiter pattern.
- **Persisting structured coach data is wider than it looks** — the DB model, storage service, Pydantic schemas, replay service, API types, and UI all assume `ai_feedback` is a string. If S03 only needs better live coaching, stay schema-compatible.
- **Vitest targeted commands can false-green if a file path is wrong** — inspect the reported `Test Files` list, not just exit code.

## Open Risks

- If S03 truly needs UI-visible score delta, the public `ScoreUpdate` websocket contract will need expansion; right now deltas exist inside capability outputs but are not exposed to frontend state.
- If the new shared coaching-focus helper also changes report-side `next_goal` semantics now, the slice boundary starts overlapping S04. The planner should decide whether to keep report outputs unchanged in S03 or accept early convergence intentionally.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next realtime UI | `react-best-practices`, `fullstack-dev`, `agent-browser`, `test` | installed |
| FastAPI backend | `wshobson/agents@fastapi-templates` | available via `npx skills add wshobson/agents@fastapi-templates` |
| SQLAlchemy / Alembic | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available via `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` |
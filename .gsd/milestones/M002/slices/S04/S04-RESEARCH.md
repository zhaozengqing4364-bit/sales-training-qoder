# M002/S04 — Research

## Summary

R009 is still the active requirement, and this slice directly supports the still-open “training-time guidance vs report conclusion” part of R005. S03 already established one authoritative realtime coaching seam in `backend/src/common/effectiveness/evaluator.py`: `resolve_sales_coaching_focus(...)` drives the stage-aware `action_card` direction used by both classic and StepFun runtimes. The drift is now on the read side. Report/replay/history consumers still get `main_issue` / `next_goal` from `evaluate_effectiveness_snapshot(...)` / `ensure_effectiveness_snapshot(...)`, which are driven by session rollups or an already-persisted snapshot, not by the same stage-aware coaching-focus rule that powers realtime action cards.

The smallest safe S04 path is therefore **read-side alignment, not a persistence migration**. `backend/src/common/conversation/session_evidence.py` is already the single projection seam for report, replay, and history/admin surfaces. It has the latest persisted `sales_stage`, normalized `score_snapshot`, and per-turn `ai_feedback`. That makes it the best place to derive one stable “coach-aligned” conclusion for the completed session and then feed the existing `main_issue`, `next_goal`, and `stage_summary` fields everywhere else. This matches `safe-grow`’s single-item / minimum-blast-radius rule, and it keeps the frontend as a renderer rather than inventing client-side heuristics (`react-best-practices` / `fullstack-dev`: keep derivation on the server, keep clients thin).

## Recommendation

Use a **shared backend alignment helper** under `common.effectiveness` that converts the latest persisted sales evidence into report/replay conclusions via the same rule family as realtime coaching. The helper should consume:
- latest persisted `sales_stage`
- latest normalized `score_snapshot.dimension_scores`
- existing pass-flags / rollup metrics when needed as fallback

and should internally reuse `resolve_sales_coaching_focus(...)` wherever rich enough context exists. The output should stay compatible with the current read contract: `main_issue`, `next_goal`, and optionally an additive derived `realtime_coach_snapshot` only if replay/report need a more explicit comparison surface. Do **not** rename existing keys or reopen the S01/S03 websocket contract.

Prefer a **projection-only override first**:
1. derive aligned conclusions inside `SessionEvidenceService.build_projection(...)`
2. feed those aligned fields into report/replay/history/admin consumers
3. add the smallest frontend changes needed to make replay visibly show the same conclusion the report shows

This avoids a DB migration and avoids depending on transient StepFun runtime memory. It also respects `verification-before-completion`: alignment must be proved by fresh backend contract/integration tests plus focused report/replay UI assertions, not by prose claims.

## Implementation Landscape

### Key Files

- `backend/src/common/effectiveness/evaluator.py` — Current authoritative realtime coaching seam. Relevant functions:
  - `resolve_sales_coaching_focus(...)`
  - `_sales_main_issue(...)`
  - `_sales_next_goal(...)`
  - `evaluate_effectiveness_snapshot(...)`
  - `build_action_card(...)`
  
  Today, `build_action_card(...)` can use stage-aware context, but `_sales_main_issue(...)` / `_sales_next_goal(...)` still derive report conclusions from rollup metrics only. This is the core semantic split S04 needs to close.

- `backend/src/common/effectiveness/schemas.py` — Typed shapes for sales coaching focus, action cards, stage context, and score context. Best place to add any typed additive “derived coach snapshot” shape if S04 needs one.

- `backend/src/common/conversation/session_evidence.py` — The key S04 seam. `build_projection(...)` normalizes messages and currently sets:
  - `stage_summary` from persisted message `sales_stage`
  - scores from session fields or latest message `score_snapshot`
  - `main_issue` / `next_goal` from `ensure_effectiveness_snapshot(...)`
  
  This file already fan-outs to report/replay/history consumers, so aligning here gives the widest payoff with the smallest blast radius.

- `backend/src/common/conversation/replay.py` — `get_replay_data(...)` simply exposes the projection. Likely only needs test updates unless S04 adds an explicit derived coach-snapshot field.

- `backend/src/common/api/practice.py` — `/practice/sessions/{id}/report` already consumes `SessionEvidenceService.get_projection(...)`. The report endpoint itself is not the main design seam; it will inherit alignment once projection output changes. Relevant drift-related helpers:
  - `_apply_sales_realtime_score_snapshot_to_session(...)`
  - `_sync_sales_realtime_terminal_evidence(...)`
  - local `_ensure_effectiveness_snapshot(...)`
  
  These write session rollups from realtime score snapshots, but they still do not carry the S03 stage-aware coaching rule through to read-side `main_issue` / `next_goal`.

- `backend/src/common/analytics/history_service.py` — Consumes `projection.main_issue` / `projection.next_goal` and groups repeated blockers/goals for supervisor/admin surfaces. Any S04 vocabulary changes here will immediately affect trend buckets, admin labels, and tests.

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — Already centralizes realtime pacing and primary-action selection. Useful as behavioral reference, but not the first place to change for S04 if the goal is report/replay alignment.

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Important constraint surface:
  - persists `sales_stage`, `score_snapshot`, and `ai_feedback` per message
  - does **not** persist a structured `action_card`
  - keeps richer raw `dimensions[*].delta/trend` only in runtime memory for arbitration
  
  This means S04 can safely derive a stable read-side conclusion from persisted stage + score, but it cannot perfectly reconstruct every transient decline-driven action-card nuance unless new persistence is added.

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — Confirms current persistence boundary. Persisted analysis payload includes `sales_stage`, normalized `score_snapshot`, `ai_feedback`, and `fuzzy_words`; there is no persisted structured `action_card` JSON yet.

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Sales report page already renders:
  - `main_issue`
  - `next_goal`
  - `stage_summary`
  
  Main job here is verification, not heavy redesign, unless S04 adds an explicit aligned snapshot block.

- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Replay page currently renders:
  - `stage_summary`
  - per-message content / `ai_feedback`
  
  but it does **not** render `main_issue` / `next_goal`. This is the main UI gap if S04 wants replay to visibly confirm the same conclusion as the report.

- `web/src/lib/session-evidence.ts` — Shared label helpers. Currently missing several newer sales issue/goal types (for example `value_translation_gap`, `evidence_gap`, `objection_handling_gap`, `next_step_gap`, `value_to_benefit_translation`, `evidence_backing`, `objection_reframe`, `next_step_commitment`). Admin and any new replay/report badges will need this updated.

- `web/src/lib/api/types.ts` — `SessionEvidenceContract`, `PracticeSessionReport`, `ReplayData`, and `ReplayMessage` types. Update only if S04 introduces an additive derived coach-snapshot field or needs replay message score typings widened.

### Build Order

1. **Prove the backend rule seam first**
   - Add a shared alignment helper in `backend/src/common/effectiveness/evaluator.py` (or a nearby shared file) that derives report/replay `main_issue` / `next_goal` from persisted stage + score evidence using the S03 coaching-focus rule where possible.
   - Keep existing field names stable.
   - Decide explicitly whether S04 is “stable latest-stage/latest-score alignment” or “full transient parity.” The current persistence layer supports the former immediately.

2. **Wire projection before touching endpoints/UI**
   - Update `backend/src/common/conversation/session_evidence.py::build_projection(...)` so completed sales sessions emit aligned `main_issue` / `next_goal` from the new helper instead of trusting a stale persisted snapshot blindly.
   - Best low-risk option: override projection fields for sales sessions when persisted message evidence exists, without requiring a session DB write.

3. **Carry the aligned output through shared consumers**
   - Re-run/adjust `backend/src/common/conversation/replay.py` and `backend/src/common/analytics/history_service.py` expectations.
   - This gives report, replay, and admin/supervisor read surfaces the same aligned conclusion through one seam.

4. **Make replay visibly reviewable**
   - Add a compact “coach conclusion” / “本场销售主问题 + 下一轮目标” block to `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` using the already-present API fields.
   - Keep the client read-only; do not re-derive conclusions in React.

5. **Patch shared labels/types only where alignment exposes new vocabulary**
   - Update `web/src/lib/session-evidence.ts` label maps.
   - Update `web/src/lib/api/types.ts` only if S04 adds optional payload.

### Verification Approach

Run backend suites **sequentially**, not in parallel, to avoid the repo’s known coverage-combine race.

Backend contract / projection / replay alignment:
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`

Frontend read-side verification:
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`

Verification goals:
- report and replay return the **same** `main_issue` / `next_goal`
- the chosen `main_issue` / `next_goal` are compatible with the S03 coaching-focus rule for the latest persisted stage + score evidence
- replay visibly surfaces the same conclusion as report
- history/admin repeated-bucket logic still groups the new/updated issue and goal types correctly

## Constraints

- `backend/src/common/conversation/session_evidence.py::ensure_effectiveness_snapshot(...)` short-circuits when an existing snapshot already has `pass_flags`, `overall_result`, `main_issue`, `next_goal`, `evaluable`, and `not_evaluable_reason`. If S04 only changes `evaluate_effectiveness_snapshot(...)`, old completed sessions can stay semantically stale. Projection override or version-gating is required.

- Persisted per-message evidence currently includes `sales_stage`, normalized `score_snapshot`, `ai_feedback`, and `fuzzy_words`, but **not** a structured `action_card` or raw `dimensions[*].delta/trend`. Any S04 plan that promises exact reconstruction of transient action-card changes must first add persistence for richer realtime context.

- `HistoryService` and `/admin/users/{id}` consume `main_issue` / `next_goal` buckets. Renaming issue/goal types without updating `web/src/lib/session-evidence.ts` and focused tests will create admin drift.

- Keep the current public report contract stable: `SessionReport` / `ReplayData` already expose `main_issue`, `next_goal`, `stage_summary`, `evaluable`, `not_evaluable_reason`, and `evidence_completeness`. Additive fields are acceptable if truly needed; renames are not.

## Common Pitfalls

- **Backend-only alignment with no replay UI change** — `replay/page.tsx` currently does not render `main_issue` / `next_goal`, so users still cannot visually confirm report/replay consistency even if the API is fixed.

- **Touching websocket/public score contracts unnecessarily** — S01 and S03 already stabilized `score_update`, `_latest_score_snapshot`, and `action_card` semantics. S04 should consume those semantics, not redesign them.

- **Blindly trusting persisted `effectiveness_snapshot`** — many tests intentionally show that projections reuse existing snapshots when present. Without a projection override or stale-version check, the drift path remains.

- **Forgetting admin label maps** — new issue/goal types can pass backend tests yet silently lose badges in `web/src/app/admin/users/[id]/page.tsx` because `web/src/lib/session-evidence.ts` lacks the current vocabulary.

- **Assuming Vitest path filters prove coverage** — per repo knowledge, inspect the “Test Files” list in output; a mistyped path can still return 0.

## Open Risks

- If product requires replay/report to mirror the exact same-turn action card chosen from a declining-dimension signal, the current persisted evidence is insufficient because raw score deltas/trends are not stored per message. The smallest S04 slice should explicitly accept “stable latest-stage/latest-score alignment” unless the slice is allowed to add richer persistence.

- Existing completed sessions with already-persisted `effectiveness_snapshot` may need a stale-version or projection-override strategy; otherwise newly aligned logic only applies to freshly completed sessions.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js | `react-best-practices` | installed |
| FastAPI | `wshobson/agents@fastapi-templates` | available |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available |

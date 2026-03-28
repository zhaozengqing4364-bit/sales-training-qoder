# S02 Research — 同 session 结论同源收口

## Summary

S02 is not mainly a report/replay problem. Report and replay already share the same completed-session authority: `backend/src/common/conversation/session_evidence.py` builds the canonical projection, `backend/src/common/api/practice.py` returns it on `/practice/sessions/{id}/report`, and `backend/src/common/conversation/replay.py` reuses it and only decorates it with replay anchors / learning evidence.

The unfinished seam is **live runtime -> completed projection continuity on the same session**.

Today the codebase already has one canonical family map in `backend/src/common/effectiveness/evaluator.py`:
- live coaching text comes from `resolve_sales_coaching_focus(...)` + `build_action_card(...)`
- completed `main_issue` / `next_goal` comes from `resolve_sales_report_alignment(...)`
- objection-ledger override is enforced in `SessionEvidenceService._build_objection_ledger_alignment(...)`

So the safest S02 path is to keep using that shared evaluator seam and close the runtime continuity gap, rather than inventing new UI-side mappings or a new milestone-only API.

## Requirement Focus

- **R009 (active, owner M007/S01)** — S02 supports R009 by proving that the learner can trust the coaching direction during active practice because the same session later resolves to coherent report/replay conclusions instead of drifting to a different issue/goal family.

## Skills Discovered

- Existing installed skill used: **react-best-practices**
  - Relevant rule: `rerender-derived-state-no-effect` — if the learner route needs a stable same-session conclusion cue, derive it directly from runtime authority during render/shared helpers, not via a second page-local copied state.
- Existing installed skill used: **fastapi-python**
  - Relevant rule: keep FastAPI routes thin and move truth assembly into shared helpers / Pydantic-friendly service seams rather than duplicating dict-shaping inside routes.
- No new external skill was needed. The core technologies for this slice (React/Next learner pages, FastAPI backend, websocket runtime) are already covered by installed skills.

## Implementation Landscape

### 1. Canonical family mapping already exists in one backend seam

**File:** `backend/src/common/effectiveness/evaluator.py`

This file already defines the authoritative family map:
- `SALES_COACHING_FOCUS_TEMPLATES`
- `SALES_REPORT_MAIN_ISSUES_BY_FOCUS`
- `SALES_REPORT_NEXT_GOALS_BY_FOCUS`
- `resolve_sales_report_alignment(...)`
- `resolve_sales_coaching_focus(...)`
- `build_action_card(...)`

Existing focus families:
- `value_translation_gap`
- `evidence_gap`
- `objection_handling_gap`
- `next_step_gap`

Planner implication:
- do **not** create a new frontend-only mapping from score/action-card text to report issue/goal
- do **not** fork a second backend mapping just for `/knowledge-check`
- extend/reuse this evaluator seam if S02 needs a live-family payload

### 2. Completed-session truth is already unified

**Files:**
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`

`SessionEvidenceService.build_projection(...)` is the completed-session authority.

Important behavior:
- projection starts from persisted `session.effectiveness_snapshot`
- then `_resolve_sales_projection_alignment(...)` may override stale `main_issue` / `next_goal` / `claim_truth`
- precedence is:
  1. latest open objection ledger
  2. latest usable message `score_snapshot`
  3. fallback snapshot

`/practice/sessions/{id}/report` uses that projection directly.

`/sessions/{id}/replay` also uses that projection directly, then adds:
- `replay_anchor`
- `learning_evidence.issue_family`
- deep-link metadata

Planner implication:
- report/replay parity is already structurally centralized
- if S02 changes completed-session family semantics, change `SessionEvidenceService` / evaluator first, not page-level formatting
- replay-only work should preserve the existing rule that `replay_anchor` is decoration; tests already strip it before comparing report vs replay payloads

### 3. Lifecycle gate is asymmetric by design

**Files:**
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/replay.py`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`
- `backend/tests/contract/test_practice_evidence_contract.py`

Current behavior:
- report route does **not** require completed session
- replay/highlights do require `SessionStatus.COMPLETED`
- learner page redirects to `/practice/{id}/report` as soon as status becomes `scoring` or `completed`

There is already contract coverage that replay/highlights stay blocked before finalization and unlock on the **same session** after background finalization:
- `test_sales_background_finalization_unlocks_same_session_replay_and_highlights`

Planner implication:
- do not treat temporary missing replay during `scoring` as a regression
- same-session live proof should account for the expected sequence:
  `practice` -> `report while scoring/completed` -> `replay after completion`
- if S02 adds browser/UAT proof, it should explicitly wait for completion before demanding replay

### 4. The live-runtime continuity gap is real

**Files:**
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/enhanced_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`

#### StepFun path

StepFun already computes live alignment-adjacent truth:
- `_run_realtime_feedback(...)` builds `live_claim_truth` with `resolve_sales_report_alignment(...)`
- `_latest_claim_truth` is persisted in runtime state
- `score_update` includes `claim_truth`
- `get_runtime_diagnostics()` returns `claim_truth` + `coach_health`

#### Classic path

Classic does **not** have parity yet:
- `EnhancedHandler.get_runtime_diagnostics()` returns `claim_truth: None`
- `capability_processor._send_score_update(...)` forwards raw score payload only
- no live `resolve_sales_report_alignment(...)` call exists on the classic path

Planner implication:
- S02 is not fully closed if only StepFun can surface live claim-truth/family continuity
- the likely backend task seam is to give classic the same shared live-alignment authority, preferably by reusing evaluator helpers instead of duplicating StepFun logic line-for-line

### 5. The learner route does not currently render canonical same-session conclusion family

**Files:**
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/components/practice/ScorePanel.tsx`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/hooks/websocket/types.ts`

Current live learner surfaces:
- coach health notice
- current stage
- score panel (`overall_score`, `dimension_scores`, `suggestions`, `stage_name`)
- action card
- fuzzy hints

Important constraint from reducer/tests:
- final transcript clears `actionCard` and `fuzzyDetections`
- `scores` and `salesStage` survive
- this is deliberate and already guarded in `web/src/hooks/websocket/message-handlers.test.ts`

So the durable surviving live direction at end-of-turn is currently **score/stage/suggestions**, not action-card text.

Additional gap:
- backend StepFun `score_update` includes `claim_truth`
- frontend `ScoreUpdate` type in `web/src/hooks/websocket/types.ts` does **not** include `claim_truth`
- `web/src/hooks/websocket/message-handlers.ts` stores `score_update` as `scores` and effectively drops any extra `claim_truth` field from the typed contract

Planner implication:
- if S02 needs learner-visible same-session continuity on the active route, the smallest change is likely a shared runtime summary derived from existing websocket/runtime authority
- do not rely on action-card text alone, because it is intentionally transient
- if extending live UI, prefer a shared helper / existing runtime state path over page-local duplicated interpretation (per `react-best-practices` derived-state rule)

### 6. `/knowledge-check` is the existing comparison surface, not a new API candidate

**Files:**
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`

`/practice/sessions/{id}/knowledge-check` already merges:
- live runtime diagnostics (`live_claim_truth`, `live_coach_health`) when a handler is active
- projection `effectiveness_snapshot.claim_truth` when the session is completed
- session snapshot fallback

This is already the sanctioned inspection surface from S01.

Planner implication:
- if S02 needs a backend-visible “same-session conclusion family” payload, add it here / in `runtime_diagnostics.py` using shared evaluator output
- do not add a second debug endpoint
- keep the route thin; put shaping/precedence in shared helper code (matches `fastapi-python` guidance)

### 7. Cross-session retry focus is not the same problem

**Files:**
- `backend/src/common/api/practice.py`
- `backend/src/training_runtime/service.py`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`

`focus_intent` is already solid, but it is for the **next session**:
- report builds `retry_entry.focus_intent`
- session creation persists it into `voice_policy_snapshot.focus_intent`
- runtime descriptor exposes it
- learner page shows the carry-forward banner only for retry sessions

Planner implication:
- do not misuse `focus_intent` as proof of same-session closure
- S02 should prove coherence on the current session first, then keep retry flow unchanged

## Recommendation

Treat S02 as a **two-seam closure** problem:

1. **Backend/runtime seam first**
   - unify StepFun and classic around one live same-session alignment authority
   - likely place: evaluator + runtime diagnostics, not route code
   - preferred output: a live family/claim-truth summary that can be compared against completed projection on the same session

2. **Frontend learner seam second (only if needed for visible proof)**
   - decide whether the current learner page already gives enough same-session continuity via surviving score suggestions/stage
   - if not, extend the websocket/runtime state contract to carry/render the stable live family summary
   - keep derivation shared and render-time, not copied into effect-managed local state

3. **Then prove report/replay closure on the same session, not by cross-session stitching**
   - report page should remain the canonical first stop after session end
   - replay should remain gated on completion and then show the same family plus anchors

## Natural Task Seams

### Seam A — backend live-alignment authority

Primary files:
- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/enhanced_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/common/api/practice.py`

Goal:
- make live same-session family/claim-truth available from the current runtime path on both runtimes

### Seam B — learner route continuity surface

Primary files:
- `web/src/hooks/websocket/types.ts`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/components/practice/ScorePanel.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/lib/session-evidence.ts`

Goal:
- only if necessary, render the stable live direction that survives turn completion and can be recognized again on report/replay

### Seam C — parity + UAT proof

Primary files:
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- likely new/expanded classic runtime unit coverage
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/hooks/websocket/message-handlers.test.ts`
- `web/src/components/practice/RightPanelContent.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

Goal:
- lock same-session family continuity without weakening existing report/replay parity contracts

## Don’t Hand-Roll

- Don’t create a frontend-only mapping from live score/stage text to `main_issue` / `next_goal` families.
- Don’t fix report/replay parity by changing both pages independently; they already share the backend projection.
- Don’t add a new milestone-specific diagnostics endpoint; extend `/knowledge-check` / `runtime_diagnostics.py` if extra comparison data is needed.
- Don’t use `focus_intent` as evidence for current-session closure; it is a retry-session carry-forward contract.

## Verification Entrypoints

### Backend focused checks

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_practice_evidence_flow.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py`
- if classic parity is added, add a focused classic runtime unit file instead of relying on StepFun tests alone

### Frontend focused checks

- `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/components/practice/RightPanelContent.test.tsx' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`

### Localhost proof constraints

- Use the same loopback host for frontend and backend (`localhost` with `localhost`, or `127.0.0.1` with `127.0.0.1`) so auth cookies survive the route family.
- Frontend local dev route for this repo is `:3445`; do not trust an unrelated app already running on `:3000`.
- Expect `/practice/{id}/report` to be available before `/practice/{id}/replay` if the session is still `scoring`.
- If running real StepFun websocket proof and it loops on `1006` with a backend `python-socks` error, that is an environment dependency issue, not same-session family drift.

## Suggested planner order

1. Read/lock the backend authority seam first (`evaluator.py`, runtime diagnostics, StepFun/classic handlers).
2. Decide whether learner-visible runtime continuity requires a frontend contract extension or whether existing score/stage/suggestion surfaces are enough once backend parity exists.
3. Only after that, add/adjust report/replay/browser proof so the same session can be followed honestly through the existing route family.

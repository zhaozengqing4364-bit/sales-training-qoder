---
id: S03
parent: M003
milestone: M003
provides:
  - A reconnect-safe unresolved-objection ledger on the existing sales runtime chain.
  - Ledger-backed report/replay `main_issue` / `next_goal` alignment that keeps the blocking proof gap visible after session completion.
  - A learner-panel pattern that suppresses stale turn hints but preserves the lingering proof prompt users still need to answer.
requires:
  - slice: S01
    provides: The locked live admin Persona/knowledge -> practice -> knowledge-check/report/replay entry chain and accepted learner/admin-visible proof surfaces for M003.
  - slice: S02
    provides: The frozen session-level `customer_pressure` contract that survives reconnect and can be combined with multi-turn objection tracking.
affects:
  - S04
  - S05
key_files:
  - backend/src/sales_bot/websocket/components/objection_ledger_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/conversation/session_evidence.py
  - web/src/hooks/use-practice-websocket.ts
  - web/src/components/practice/RightPanelContent.tsx
key_decisions:
  - Persist the unresolved-objection ledger on the existing runtime/evidence chain (`ConversationMessage.transcript_metadata["objection_ledger"]` plus StepFun `runtime_state["objection_ledger"]`) instead of adding a new store.
  - Keep only one active objection family at a time, with explicit `closure_state` transitions (`open`, `evidence_provided`, `gap_acknowledged`) so later read-side logic can tell whether the gap still owns the conversation.
  - Use ledger-derived synthetic objection stage/score context to keep the shared feedback arbiter focused on the same business gap, while leaving the public/persisted `score_update` snapshot on the stable contract.
  - Prefer the latest open objection ledger over generic sales score-stage alignment when projecting completed-session `main_issue` / `next_goal`, so report/replay keep explaining the blocker that actually stayed unresolved.
patterns_established:
  - Use `transcript_metadata` as the pass-through carrier for new per-turn structured facts that must survive replay/report without reopening public websocket contracts.
  - Keep one unresolved objection ledger with explicit closure semantics, then let runtime and read-side consumers share that same dict instead of each re-inferring the gap from raw text.
  - When outward score contracts must stay stable, inject richer ledger-derived context into the arbiter seam instead of mutating the published `score_update` payload.
  - Resolve completed-session sales conclusions in this order: latest open objection ledger -> latest alignable score/stage evidence -> existing effectiveness snapshot fallback.
observability_surfaces:
  - `ConversationMessage.transcript_metadata["objection_ledger"]` on persisted turn evidence
  - StepFun reconnect snapshot `runtime_state["objection_ledger"]` plus `feedback_pacing_state`
  - Projection-backed sales `main_issue` / `next_goal` on report and replay when the latest ledger is still open
  - Learner right-panel proof prompt rendered from `scores.suggestions[0]` as “当前仍卡住的证明”
drill_down_paths:
  - .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T06:06:42.543Z
blocker_discovered: false
---

# S03: 多轮异议 ledger 与持续施压

**Persisted one unresolved objection ledger across runtime, reconnect, and read-side projections so proof / price / competitor gaps keep driving the same customer pressure until they are closed.**

## What Happened

T01 introduced the minimum unresolved-objection ledger on the existing conversation chain: `objection_family`, `promised_proof`, `next_expected_evidence`, and `closure_state`. The runtime context manager now carries that dict in-memory, the conversation storage layer normalizes it, and message persistence merges it into `ConversationMessage.transcript_metadata` so the fact survives beyond a single websocket turn.

T02 threaded the same ledger through both realtime runtime paths without inventing a second memory system. Classic `CapabilityProcessor` and StepFun `_run_realtime_feedback(...)` now resolve one objection family per turn, keep an open ledger through topic drift, and feed ledger-derived objection context into the shared feedback arbiter so the customer keeps pressing the same proof/price/competitor/implementation gap. On the StepFun path, reconnect snapshots persist the normalized ledger alongside minimal pacing state and restore it later without replaying stale `action_card` UI state.

T03 carried that fact line onto learner/read-side surfaces. `SessionEvidenceService` now prefers the latest open transcript-metadata ledger when projecting completed-session sales `main_issue` / `next_goal`, so report/replay keep naming the unresolved blocker instead of falling back to a generic late-stage score alignment. On the practice page, the websocket wrapper clears stale action-card/fuzzy hints on reconnect or new final transcripts, while the right panel keeps the unresolved proof prompt visible as “当前仍卡住的证明” when an action card is present. The result is one continuous seam from runtime pressure -> reconnect snapshot -> persisted evidence -> report/replay explanation.

## Verification

Fresh slice gates passed exactly as planned. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py` passed with 62 tests. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py` passed with 68 tests. `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'` passed with 2 test files / 13 tests. The backend evidence checks covered ledger persistence, open-ledger reuse across topic drift, closure-state release, reconnect snapshot restore, and stale-action-card suppression. The web checks covered reconnect/final-transcript clearing plus right-panel priority rules and lingering proof-prompt visibility.

## Requirements Advanced

- R010 — Proved that the current runtime/evidence chain now carries one unresolved objection family plus promised proof and next expected evidence across turns, reconnect, and completed-session report/replay projections, so Persona/knowledge-driven pressure no longer disappears as soon as the topic drifts.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

The ledger intentionally tracks only one unresolved objection family at a time. It proves persistence, reconnect safety, and read-side carry-forward, but it does not yet distinguish whether a later response is unsupported, merely promised, or evidence-backed on the canonical report/replay contract; that remains S04 work.

## Follow-ups

S04 needs to extend this same fact line so report/replay/runtime can distinguish unsupported claims, promised-but-not-delivered evidence, and evidence-backed responses without inventing a second evaluator. S05 still needs one live objection-heavy admin -> practice -> report/replay proof run on the current routes.

## Files Created/Modified

- `backend/src/sales_bot/services/context_manager.py` — Defined the minimal in-memory objection ledger contract and exposed it in conversation summaries.
- `backend/src/common/conversation/storage.py` — Normalized objection ledger payloads and merged them into `ConversationMessage.transcript_metadata` on save/update.
- `backend/src/sales_bot/websocket/components/objection_ledger_helpers.py` — Added the runtime helper that detects objection families, opens/closes one ledger, and derives override context for the feedback arbiter.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — Wired classic sales runtime feedback through the objection ledger so topic drift keeps pressure on one open gap.
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — Whitelisted objection ledger facts through StepFun message normalization and duplicate-message patching.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Persisted/restored the ledger in reconnect snapshots, fed ledger-aware context into realtime feedback, and avoided replaying stale action cards after restore.
- `backend/src/common/conversation/session_evidence.py` — Made completed-session projection prefer the latest open objection ledger for sales `main_issue` / `next_goal` before generic score-stage alignment.
- `backend/tests/unit/test_context_manager.py` — Covered ledger creation, closure updates, and transcript-metadata persistence at the storage seam.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — Covered open-ledger reuse across topic drift, gap acknowledgement closure, and reconnect snapshot rehydration on the StepFun path.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — Covered reconnect-safe restore behavior so the ledger survives while stale action-card replay stays suppressed.
- `backend/tests/unit/test_session_evidence_service.py` — Covered read-side preference for the latest open objection ledger when projecting completed-session sales conclusions.
- `web/src/hooks/use-practice-websocket.ts` — Cleared transient coaching hints on reconnect/reset while preserving score-context proof prompts that carry the unresolved objection forward on the learner side.
- `web/src/hooks/use-practice-websocket.test.ts` — Covered reconnect/final-transcript behavior so stale action-card hints disappear without losing the lingering proof prompt in scores.
- `web/src/components/practice/RightPanelContent.tsx` — Rendered `action_card` as the only primary coaching surface and exposed the surviving proof prompt as “当前仍卡住的证明”.
- `web/src/components/practice/RightPanelContent.test.tsx` — Covered learner-side priority rules between action card, fuzzy hints, stage context, and the persistent proof prompt.

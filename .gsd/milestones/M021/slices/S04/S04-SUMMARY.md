---
id: S04
parent: M021
milestone: M021
provides:
  - A single inspectable runtime-event truth line for AI quality/cost/failure/mode across backend, support, and learner proof surfaces.
  - Explicit knowledge-answer `live|compat` path provenance that downstream slices can read without reverse-engineering rollout flags.
  - A stable read-side contract for validating degraded/failure semantics without pretending default scores or fallback copy are successful outcomes.
requires:
  []
affects:
  - M021 milestone validation and close-out
  - M022 downstream planning on top of explicit quality/cost/evidence surfaces
key_files:
  - backend/src/common/knowledge_engine/runtime_events.py
  - backend/src/common/knowledge_engine/compat.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/ai/llm_service.py
  - backend/src/support/services/runtime_status_service.py
  - backend/src/support/api/runtime_status.py
  - docs/api-contract/support-runtime.md
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
key_decisions:
  - D239 — adopt one allowlist-first runtime_events schema and normalize knowledge-answer path truth to explicit path_mode=live|compat with rollout_mode retained only as supporting detail.
  - D240 — keep S04 read-side proof on the existing support/runtime faults contract plus report/replay data-contract-source and explicit failure copy instead of inventing a second support payload or UI-only status layer.
patterns_established:
  - Allowlist-first runtime event schema shared across knowledge-check, websocket diagnostics, support/runtime faults, and LLM bookkeeping.
  - Separate provenance (`category=mode`, `status=live|compat`) from quality (`severity=degraded|failure`) so compat does not masquerade as success or failure.
  - Use existing learner/source surfaces (`data-contract-source`, explicit failure copy) to prove compat/degraded states instead of adding page-local status plumbing.
observability_surfaces:
  - `/api/v1/practice/sessions/{id}/knowledge-check` runtime diagnostics / runtime_events
  - StepFun websocket runtime diagnostics from `stepfun_realtime_handler.py`
  - `/api/v1/support/runtime/faults.items[].diagnostics.runtime_events[]`
  - `LLMService` runtime event recording for generation/report/evaluation cost/failure paths
drill_down_paths:
  - .gsd/milestones/M021/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M021/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M021/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T04:47:44.676Z
blocker_discovered: false
---

# S04: AI quality/cost/failure events 与 knowledge path 收口

**Unified allowlist-safe AI runtime events now expose quality/cost/failure/mode truth across knowledge-check, websocket diagnostics, support/runtime faults, and learner proof surfaces, while knowledge-answer rollout is normalized to explicit live/compat path mode instead of hidden fallback semantics.**

## What Happened

## Outcome
S04 completed the final assembly goal for M021: AI runtime/control-plane failures, degradations, cost signals, and knowledge-answer path provenance are now visible on one explicit runtime-event line instead of being hidden behind default scores, fallback copy, or scattered flags.

## What this slice actually delivered
1. **One shared runtime-event schema across the shipped authority seams.**
   - Added the allowlist-first `runtime_events` shape (`event_id / category / severity / status / source / summary / details / metrics / occurred_at`) in `backend/src/common/knowledge_engine/runtime_events.py`.
   - Reused that shape in the existing live seams instead of inventing a second observability payload: knowledge-answer compat diagnostics, `build_session_runtime_diagnostics()` / knowledge-check, StepFun websocket runtime diagnostics, support/runtime fault diagnostics, and `LLMService` quality/cost/failure bookkeeping.
   - The event taxonomy is intentionally narrow: `category = quality|cost|failure|mode`, `severity = info|ok|degraded|failure`.

2. **Knowledge-answer dual-run/shadow behavior is now readable as explicit path truth.**
   - `common.knowledge_engine.compat` remains the rollout authority seam, but the learner/support-facing truth is now normalized to `path_mode=live|compat`.
   - `rollout_mode` is retained only as supporting detail for diagnostics and audit, rather than being the primary thing readers must reverse-engineer.
   - `stepfun_internal_knowledge_searcher` now attaches the same normalized diagnostics across enabled, legacy, and degraded returns, so knowledge-check/report/support readers do not need to infer provenance from incidental payload differences.

3. **Default score / fallback copy / hidden LLM failures are no longer the only outward signal.**
   - S04 cataloged the legacy hiding spots first (`LLM_RUNTIME_EVENT_INVENTORY`, `STEPFUN_RUNTIME_EVENT_INVENTORY`), then promoted the important ones into runtime events: parse-default 60-point evaluations, generation/report fallback paths, provider/config failures, session-cost tracking, budget warnings, kb-lock / claim-truth / knowledge quality degradation.
   - This means downstream agents can inspect explicit degraded/failure/cost events instead of reverse-engineering whether a mediocre score or generic Chinese filler text came from a real model result.

4. **Read-side proof stayed on the existing contracts instead of creating new UI-only plumbing.**
   - Support/runtime documentation now explains how to read `runtime_events[]`, especially the key distinction that `category=mode` answers provenance (`live|compat`) while `severity=degraded|failure` answers result quality.
   - Learner report and replay tests now lock the existing proof surfaces: `data-contract-source="compatibility_reader"` for compat score reads, plus explicit retrieval failure copy such as `search_failed` rather than low-quality-success phrasing.
   - This read-side choice is now recorded in decision **D240**, complementing **D239**’s schema/path-mode decision.

## Patterns established
- **Allowlist-first eventization before UI expansion:** make backend runtime state explicit on one safe event line first, then let docs/support/frontend consume that same line.
- **Separate provenance from quality:** `path_mode`/`category=mode` says where the answer came from; `severity` says whether that answer is healthy, degraded, or failed.
- **Prefer explicit compat/failure proof over synthetic success:** report/replay/support should read the explicit contract surface, not reinterpret fallback copy, default scores, or missing kernel data as normal success.

## Downstream impact
- Future M021 validation and M022 planning can inspect real `runtime_events` for cost, degradation, failure, and knowledge-path provenance instead of guessing from scattered flags or optional enhancement failures.
- Compatibility-reader retirement now has a clearer stopping condition: when report/replay/support no longer need explicit compat proof from current surfaces, the remaining compat mirrors can be retired without losing explainability.
- Support/operators now have one durable inspection surface for AI runtime anomalies that stays inside the existing allowlist-safe diagnostics contract.

## Requirements impact
No requirement status changed in this slice, so `.gsd/REQUIREMENTS.md` did not need a status transition. This slice **advanced**:
- **R022** by making knowledge-answer / retrieval failure and path facts explicit on runtime diagnostics instead of hiding them behind generic fallback outcomes.
- **R023** by keeping knowledge-check, support/runtime diagnostics, and learner report/replay proof aligned to the same knowledge-path / degradation truth line.

## Operational Readiness (Q8)
- **Health signal:** `/api/v1/practice/sessions/{id}/knowledge-check`, websocket runtime diagnostics, and `/api/v1/support/runtime/faults` now all expose `runtime_events[]`; healthy runs should show a coherent knowledge path-mode event plus non-failure quality/cost signals with no secret-bearing keys.
- **Failure signal:** `knowledge_answer_quality` with `severity=failure|degraded`, `claim_truth_status` degraded/failure states, kb-lock events, `llm_report_generation_failed`, parse-default evaluation events, and cost warning events now surface explicitly instead of being implied by filler copy or low scores.
- **Recovery procedure:** inspect `runtime_events[]` first, follow the surfaced `summary/details/metrics` on the existing knowledge-check/support-runtime surfaces, and fix the underlying seam (knowledge config, prompt contract, provider/config, kb-lock readiness, report generation) rather than patching UI copy. For support-runtime tests, prefer KB-free fixtures or seed KB tables explicitly when the goal is to prove runtime-event rendering rather than asset-governance joins.
- **Monitoring gaps:** LLM cost events are now explicit but still session-local/in-memory rather than aggregated into a long-term cost analytics surface; learner UI still proves compat/failure mainly through existing source/failure copy rather than a dedicated operator dashboard; some in-memory support fault fixtures still require KB-table care to avoid schema-drift false negatives.


## Verification

Fresh slice-close verification reran every verification command declared in the S04 plan and all passed. Commands and outcomes: (1) `rg -n "default|fallback|NO_STAGE_RESULTS|cost|report_generation_failed|knowledge_answer|degraded|claim_truth" backend/src/common backend/src/sales_bot backend/src/evaluation` passed and still exposes the hidden/default/fallback surfaces S04 set out to make explicit; (2) `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/integration/test_knowledge_flow.py backend/tests/integration/test_websocket_status_contract.py -x -q` passed with 27/27 tests green, proving knowledge-check parity, websocket runtime diagnostics, and support/read-side runtime-event coverage; (3) `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" && rg -n "quality|cost|failure|degraded|compat" docs/api-contract/support-runtime.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` passed with 39/39 web tests green plus the intended read-side/documentation grep hits. Additional fresh verification: Python LSP diagnostics returned clean results for `backend/src/common/knowledge_engine/runtime_events.py`, `backend/src/common/ai/llm_service.py`, and `backend/src/support/api/runtime_status.py`.

## Requirements Advanced

- R022 — Added explicit runtime-event surfaces for knowledge-answer / retrieval failure, degradation, and path provenance so auditable retrieval facts are no longer inferred only from fallback outcomes.
- R023 — Aligned knowledge-check/support runtime diagnostics with learner report/replay compat/failure proof so the same knowledge-path truth line is readable across diagnostics and user-facing read surfaces.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

LLM cost/runtime events are explicit but still not aggregated into a durable long-term cost analytics surface. Support/runtime in-memory fixtures can still require KB-table care to avoid asset-governance lookup failures when the actual proof target is runtime-event rendering. Learner proof relies on existing source/failure surfaces rather than a new dedicated operator UI.

## Follow-ups

1. Validate and close M021 at milestone level using the now-shipped runtime-event, compiled-prompt, and canonical-evaluation seams together. 2. Decide when compatibility-reader mirrors can be retired once all consumers no longer depend on explicit compat fallback. 3. If cost observability becomes a product requirement, promote the current session-local LLM cost events into a durable aggregate surface without breaking the allowlist-safe diagnostics boundary.

## Files Created/Modified

- `backend/src/common/knowledge_engine/runtime_events.py` — Introduced the shared allowlist-first runtime-event schema and helpers for knowledge-answer and claim-truth eventization.
- `backend/src/common/knowledge_engine/compat.py` — Normalized knowledge-answer diagnostics to explicit live/compat path-mode semantics and attached runtime events on the compat authority seam.
- `backend/src/common/conversation/runtime_diagnostics.py` — Merged persisted/live knowledge diagnostics, claim-truth, and kb-lock signals into a single runtime-events inspection surface.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — Carried the unified knowledge diagnostics and runtime events through live, legacy, and degraded knowledge-search outcomes.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Surfaced the unified runtime-event line on live websocket diagnostics and preserved the code-owned runtime inventory/proof seam.
- `backend/src/common/ai/llm_service.py` — Recorded explicit quality/cost/failure runtime events for evaluation fallback, generation/report errors, and budget tracking instead of relying only on fallback copy or totals.
- `backend/src/support/services/runtime_status_service.py` — Threaded runtime events into support/runtime fault diagnostics.
- `backend/src/support/api/runtime_status.py` — Documented/modelled the support/runtime payload shape that now includes runtime events.
- `docs/api-contract/support-runtime.md` — Explained how to read runtime-events, especially the distinction between mode provenance and degraded/failure semantics.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Locked learner report proof for compatibility-reader source and explicit retrieval failure semantics.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Locked learner replay proof for compatibility-reader source and completion-gated failure semantics.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Wrote back the S04 inventory baseline and the final read-side/runtime-event interpretation rules for downstream slices.

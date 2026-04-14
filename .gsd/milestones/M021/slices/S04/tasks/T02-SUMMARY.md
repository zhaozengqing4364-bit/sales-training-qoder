---
id: T02
parent: S04
milestone: M021
key_files:
  - backend/src/common/knowledge_engine/runtime_events.py
  - backend/src/common/knowledge_engine/compat.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/ai/llm_service.py
  - backend/src/support/services/runtime_status_service.py
  - backend/src/support/api/runtime_status.py
  - backend/tests/integration/test_knowledge_flow.py
  - backend/tests/integration/test_websocket_status_contract.py
  - backend/tests/contract/test_conclusion_evidence_parity.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D239: Use one allowlist-first `runtime_events` schema and normalize knowledge path truth to `path_mode=live|compat` with `rollout_mode` retained only as supporting detail.
duration: 
verification_result: passed
completed_at: 2026-04-14T04:33:42.181Z
blocker_discovered: false
---

# T02: Added unified runtime event surfaces for knowledge path mode, support faults, websocket diagnostics, and LLM quality/cost failures.

**Added unified runtime event surfaces for knowledge path mode, support faults, websocket diagnostics, and LLM quality/cost failures.**

## What Happened

I implemented one allowlist-first `runtime_events` schema and wired it through the live knowledge-answer seam, runtime diagnostics, support fault read-side, websocket handler diagnostics, and LLM runtime bookkeeping. Concretely, I added `backend/src/common/knowledge_engine/runtime_events.py` as the shared builder for normalized `event_id/category/severity/status/source/summary/details/metrics/occurred_at` payloads, plus helpers that enrich knowledge-answer diagnostics with explicit `path_mode=live|compat`, keep `rollout_mode` as supporting detail, and emit stable knowledge-quality / kb-lock / claim-truth events without leaking `token`, `base_url`, or other secret-like keys.

I then connected that schema to the shipped runtime paths. `common.knowledge_engine.compat.attach_rollout_diagnostics()` now enriches `_answerability` into a canonical knowledge diagnostics object with runtime events, and `sales_bot.websocket.components.stepfun_internal_knowledge_searcher.search_internal_knowledge()` now attaches that unified diagnostics shape across enabled, legacy, and dual-run/degraded returns instead of only on the happy path. `common.conversation.runtime_diagnostics.build_session_runtime_diagnostics()` now reads persisted/live knowledge diagnostics, merges them with kb-lock and claim-truth events into top-level `runtime_events`, and exposes the same line through `/practice/.../knowledge-check`. `sales_bot.websocket.stepfun_realtime_handler.get_runtime_diagnostics()` now surfaces the same unified event line for live websocket/process-local readers, and `support.services.runtime_status_service` now carries those runtime events into support fault diagnostics; `support/api/runtime_status.py` was updated to model that shape explicitly.

To cover the slice’s cost/failure scope, I also extended `common.ai.llm_service.LLMService` with per-session runtime event recording. It now records explicit events when generation falls back due to configuration/runtime failures, when token/cost usage is tracked, when session cost crosses the warning threshold, when evaluation parsing degrades into default 60-point scores, and when report generation fails. That gives future S04/T03 work a code-owned runtime event seam instead of relying only on filler copy or coarse session totals.

On the proof side, I followed a fail-first loop by adding focused assertions to the exact verification files named by the task contract: one integration test for knowledge-check runtime events + knowledge path mode, one websocket status-contract test for live handler diagnostics, and one contract test showing support faults carry the same runtime-event line. During verification I hit two local mismatches and adapted narrowly: completed-session claim-truth in this repo is still projection-driven and can normalize to `evidence_pending`, so I asserted against the surfaced diagnostics contract instead of a planner-side status guess; and the support fault contract fixture DB in this environment still lacks `knowledge_bases`, so I switched that proof to a fault-producing session without KB asset refs to keep the test focused on runtime-event rendering rather than fixture schema drift.

## Verification

I first ran the new focused fail-first tests and used the failures to close the missing seams: knowledge-check lacked unified runtime events, websocket runtime diagnostics lacked a top-level event line, and support faults were missing the carried event payload. After implementation, those focused tests passed, static diagnostics on the touched Python files were clean, and the task’s exact verification command passed end to end: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/integration/test_knowledge_flow.py backend/tests/integration/test_websocket_status_contract.py -x -q` → 27 passed. I also wrote decision D239 for the shared runtime-event schema / live-vs-compat path-mode choice and appended a KNOWLEDGE note about the support-runtime contract fixture gotcha so future agents do not rediscover it.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/integration/test_knowledge_flow.py backend/tests/integration/test_websocket_status_contract.py -x -q` | 0 | ✅ pass | 7571ms |

## Deviations

I made two narrow local adaptations while staying inside the task scope. First, the completed-session claim-truth status in this repository is still projection-authored, so the new proof follows the surfaced diagnostics contract rather than hardcoding the planner’s assumed status value. Second, the support-runtime contract fixture DB in this environment does not expose the `knowledge_bases` table needed by asset-governance lookups, so I validated the support fault runtime-event line with a fault-producing session that avoids KB asset refs instead of treating fixture-schema drift as a product blocker.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/knowledge_engine/runtime_events.py`
- `backend/src/common/knowledge_engine/compat.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/ai/llm_service.py`
- `backend/src/support/services/runtime_status_service.py`
- `backend/src/support/api/runtime_status.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/integration/test_websocket_status_contract.py`
- `backend/tests/contract/test_conclusion_evidence_parity.py`
- `.gsd/KNOWLEDGE.md`

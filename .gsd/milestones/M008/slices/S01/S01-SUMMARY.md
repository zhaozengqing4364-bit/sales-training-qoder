---
id: S01
parent: M008
milestone: M008
provides:
  - Provider-neutral retrieval ledger entries persisted in voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts
  - Backward-compatible flat knowledge metrics (last_status, last_query, last_result_count, etc.) preserved alongside the ledger
  - Read-side fallback in build_session_runtime_diagnostics that enriches diagnostics from the ledger when flat fields are stale
requires:
  []
affects:
  - S02
key_files:
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - backend/src/sales_bot/websocket/components/stepfun_helpers.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/tests/unit/test_stepfun_knowledge_helpers.py
  - backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
  - backend/tests/unit/test_stepfun_runtime_metrics_helpers.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - Reused the existing knowledge runtime-metrics seam as the only persistence channel for retrieval ledger entries (D118).
  - Rejected malformed persisted recent_attempts payloads at snapshot-merge time so invalid ledger state does not half-write PracticeSession.voice_policy_snapshot.
  - Prefer the latest valid runtime_metrics.knowledge_retrieval.recent_attempts entry only as a fallback for missing or stale flat last_* fields (D119).
  - Keep the read-side fix inside build_session_runtime_diagnostics instead of adding a new audit route or changing report/replay payloads.
  - Normalize away optional agent_persona_override_config:null in contract assertions so snapshot-ref tests keep checking the real immutability invariant.
patterns_established:
  - Provider-neutral retrieval ledger: every internal knowledge search outcome is normalized to one bounded ledger_event before persistence, independent of the underlying search provider.
  - Copy-on-write snapshot merges: runtime-metrics writes deep-copy the knowledge_retrieval subtree before mutation, so the original snapshot object is never modified in place.
  - Read-side ledger fallback: diagnostics prefer flat last_* fields first, then fall back to the latest valid recent_attempts entry only when those fields are missing or stale.
observability_surfaces:
  - voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts — persisted bounded ledger visible on current session snapshot/detail routes
drill_down_paths:
  - milestones/M008/slices/S01/tasks/T01-SUMMARY.md
  - milestones/M008/slices/S01/tasks/T02-SUMMARY.md
  - milestones/M008/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T16:45:01.291Z
blocker_discovered: false
---

# S01: 会话检索账本落库

**Provider-neutral retrieval ledger events are now persisted in session voice_policy_snapshot and readable on current session routes, with backward-compatible flat metrics and copy-on-write snapshot semantics.**

## What Happened

S01 delivered the first layer of auditable retrieval truth for knowledge-backed sales sessions. The work spanned three tasks:

**T01 (absorbed into T02):** The original T01 executor left no implementation, so T02 pulled the helper/searcher normalization work into its own unit. The search-helper layer now builds one bounded provider-neutral `ledger_event` for every internal retrieval outcome — missing query, no KB bound, KB not ready, miss, hit, and failure. Each event carries normalized query text, status, result count, retrieval mode, error summary, and bounded transformed result summaries. 28 focused helper/searcher tests prove normalization, trimming, and truthful event creation.

**T02:** Wired the normalized ledger events through the existing `apply_knowledge_runtime_metric(...)` and `StepFunRealtimeHandler._record_knowledge_runtime_metric(...)` persistence path. The `merge_runtime_metrics_snapshot(...)` helper deep-copies knowledge metrics into a new snapshot object (copy-on-write), rejects malformed persisted `recent_attempts` payloads at merge time, and keeps existing flat counters readable. 69 runtime-metrics and handler tests prove copy-on-write persistence, bounded ledger retention, and the preexisting warning-only failure surface when persistence raises after in-memory updates.

**T03:** Closed the read-side gap. `build_session_runtime_diagnostics(...)` now falls back to the latest valid `knowledge_retrieval.recent_attempts` entry when flat `last_*` fields are missing or stale, scanning backwards and skipping malformed entries. Integration and contract suites prove the ledger is visible on current session/detail surfaces while `voice_policy_snapshot_ref` stays frozen across detail/report/replay reads. 24 tests green across unit, integration, and contract levels.

Total verification: 121 tests across three focused packs, all passing. No new routes, tables, or report payload changes — S01 proof stays on current session snapshot/detail surfaces as planned.

## Verification

All three task-level verification packs pass:
1. T01/T02 helper+searcher pack: 28 tests green — normalization, trimming, hit/miss/failure event creation
2. T02 runtime-metrics+handler pack: 69 tests green — copy-on-write persistence, bounded ledger, warning-only failure surface
3. T03 read-side pack: 24 tests green — ledger-backed diagnostics fallback, route-level integration, contract-level frozen-ref proof

No new routes, tables, or report payload changes introduced. Existing flat metrics remain backward-compatible.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 absorbed the unfinished T01 helper/searcher normalization work because T02 had no ledger_event payload to persist without it. The deviation stayed inside the same slice boundary and did not widen into T03 route-reader work.

## Known Limitations

Focused pytest still emits existing pytest-cov warnings about `Module src was never imported` / `No data was collected`; the targeted packs themselves pass. The ledger is only readable through current session diagnostics and detail routes — report/replay knowledge-check alignment is S02 scope.

## Follow-ups

S02 should now extend the retrieval ledger read side to knowledge-check and report routes, proving they return consistent retrieval facts against the same persisted snapshot. S03 should then surface the ledger on the report page UI.

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — Added provider-neutral ledger_event normalization for hit/miss/failure/kb-not-ready/no-kb/missing-query paths
- `backend/src/sales_bot/websocket/components/stepfun_helpers.py` — Extended helper utilities to carry richer retrieval event payloads
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — Searcher now builds bounded ledger events from transformed search results for all outcome paths
- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` — Runtime-metrics merge now deep-copies knowledge_retrieval subtree and rejects malformed recent_attempts at merge time
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Handler passes normalized ledger_event through existing _record_knowledge_runtime_metric path with warning-only failure surface
- `backend/src/common/conversation/runtime_diagnostics.py` — Added bounded fallback that scans recent_attempts backwards to fill missing/stale flat last_* fields
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — Tests for helper-level normalization of query, rerank params, and KB binding
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` — Tests for searcher-level ledger event creation across all outcome paths
- `backend/tests/unit/test_stepfun_runtime_metrics_helpers.py` — Tests for copy-on-write persistence, bounded ledger retention, and malformed rejection
- `backend/tests/unit/test_stepfun_realtime_handler.py` — Tests for handler-level persistence with warning-only failure surface
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — Tests for read-side ledger fallback when flat fields are missing or stale
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — Integration tests proving ledger visible on current session/detail surfaces with frozen ref
- `backend/tests/contract/test_practice_evidence_contract.py` — Contract tests proving voice_policy_snapshot_ref immutability across runtime-metrics churn

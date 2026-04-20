---
estimated_steps: 3
estimated_files: 5
skills_used:
  - safe-grow
  - fastapi-python
  - test-driven-development
  - verification-before-completion
---

# T03: Keep current session routes readable with ledger-backed snapshots

**Slice:** S01 — 会话检索账本落库
**Milestone:** M008

## Description

Lock the read side on current session routes so ledger-backed snapshots stay truthful and backward-compatible before S02 starts sharing this truth with report. The executor should load `safe-grow`, `fastapi-python`, `test-driven-development`, and `verification-before-completion` before coding. Stay on existing detail/knowledge-check/report/replay route family; do not introduce a new audit surface.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `build_session_runtime_diagnostics(...)` | keep current knowledge-check summary behavior and fail the new regression if ledger-backed snapshots cannot be read | do not add new polling or runtime dependencies to read the ledger | fall back to the latest valid ledger entry or current flat fields instead of throwing |
| current practice session/detail routes | preserve existing access-control and snapshot-ref behavior | keep current single-read behavior; do not add background fetches | reject runtime-metrics drift that changes `voice_policy_snapshot_ref` |

## Load Profile

- **Shared resources**: one session fetch and current diagnostics normalization on existing routes.
- **Per-operation cost**: one read plus lightweight fallback logic from flat fields to the latest bounded ledger entry.
- **10x breakpoint**: repeated JSON normalization on every read if fallback logic becomes expensive or duplicates work.

## Negative Tests

- **Malformed inputs**: partial or missing flat `last_*` fields should still allow ledger-backed snapshots to read truthfully when a valid latest event exists.
- **Error paths**: completed-session hit/miss/failure snapshots still classify correctly on `knowledge-check` and current detail routes.
- **Boundary conditions**: `voice_policy_snapshot_ref` remains unchanged while runtime metrics churn, and owner/admin access on current session routes does not regress.

## Steps

1. Teach `backend/src/common/conversation/runtime_diagnostics.py` and only the minimal API glue it needs to tolerate the richer `knowledge_retrieval` payload while preserving today's counter/status summary contract.
2. Extend snapshot and contract tests so a completed knowledge-backed session proves the bounded ledger is visible on current session/detail surfaces and `voice_policy_snapshot_ref` still ignores runtime-metric churn across detail/report/replay reads.
3. Re-run the focused route tests sequentially and stop if the implementation starts adding report semantics or new routes that belong to S02 rather than S01.

## Must-Haves

- [ ] No new audit route or report payload redesign in S01.
- [ ] Existing `knowledge-check` status summaries stay compatible with ledger-backed snapshots.
- [ ] Current session routes remain the proof surface for persisted snapshot truth.

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_practice_evidence_contract.py`
- Inspect the route assertions to confirm detail/knowledge-check reads stay truthful while `voice_policy_snapshot_ref` remains frozen.

## Observability Impact

- Signals added/changed: current session detail / knowledge-check readers can inspect the persisted ledger without losing legacy counter-based status summaries.
- How a future agent inspects this: compare `GET /api/v1/practice/sessions/{id}` and `GET /api/v1/practice/sessions/{id}/knowledge-check` for the same completed session, or rerun the focused integration/contract pack.
- Failure state exposed: whether richer runtime metrics can still be read consistently on existing session routes or whether snapshot/ref drift reappears.

## Inputs

- `backend/src/common/conversation/runtime_diagnostics.py` — current `knowledge-check` diagnostics builder.
- `backend/src/common/api/practice.py` — existing session/detail/knowledge-check route family.
- `backend/src/common/db/voice_policy_snapshot.py` — current frozen snapshot-ref builder.
- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` — T02 persistence seam for ledger-backed snapshots.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — T01/T02 ledger event source.
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — current snapshot/read-route integration proof.
- `backend/tests/contract/test_practice_evidence_contract.py` — current route-family contract proof.

## Expected Output

- `backend/src/common/conversation/runtime_diagnostics.py` — ledger-aware backward-compatible diagnostics reader.
- `backend/src/common/api/practice.py` — minimal route glue, only if needed to keep current session surfaces truthful.
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — new focused unit coverage for ledger-backed reader fallback.
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — integration proof that the mutated snapshot is readable on current session routes.
- `backend/tests/contract/test_practice_evidence_contract.py` — contract proof that `voice_policy_snapshot_ref` stays frozen while runtime metrics churn.

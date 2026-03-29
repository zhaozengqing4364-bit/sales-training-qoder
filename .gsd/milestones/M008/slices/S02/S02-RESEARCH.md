# M008/S02: knowledge-check 与 report 共用检索真相 — Research

**Date:** 2026-03-28

## Summary

**Requirement targeting:** S02 primarily owns **R023** (knowledge-check/report retrieval truth parity), consumes **R022** from S01 as its persistence base, and advances the M010-foundation parts of **R027/R028** by making report explanations point back to persisted retrieval facts instead of abstract status alone.

S01 already delivered the durable source of truth this slice needs: a bounded provider-neutral ledger at `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`. The missing piece is read-side reuse.

What exists today:
- `build_session_runtime_diagnostics(...)` in `backend/src/common/conversation/runtime_diagnostics.py` already reads persisted retrieval metrics for `/knowledge-check`, but it only exposes flat counters + `last_*` fields + `recent_queries`.
- `SessionEvidenceService.build_projection(...)` in `backend/src/common/conversation/session_evidence.py` is still the report authority seam, but it does **not** read `voice_policy_snapshot.runtime_metrics` at all.
- `GET /api/v1/practice/sessions/{id}/knowledge-check` in `backend/src/common/api/practice.py` already fetches a completed-session projection for sales sessions, but only passes `projection_effectiveness_snapshot` into diagnostics for `main_issue` / `next_goal` / `claim_truth` fallback. Retrieval truth is not reused there yet.

Important current gap: `_normalize_knowledge_retrieval_attempt(...)` in `runtime_diagnostics.py` strips ledger entries down to `status/query/result_count/retrieval_mode/error_summary/attempted_at`. It drops `knowledge_base_ids` and `result_summaries`, so neither knowledge-check nor report can currently answer “命中了什么”.

Good news for blast radius: `SessionReport.effectiveness_snapshot` is still typed as `dict[str, Any] | None` in `backend/src/common/db/schemas.py`, and the web client treats it as opaque `Record<string, unknown>`. So S02 can stay backend-only and add nested retrieval facts without forcing frontend work or top-level schema churn.

## Recommendation

Use the existing completed-session projection seam instead of patching routes separately.

1. **Build one pure retrieval-truth read model from the persisted snapshot ledger** (`recent_attempts` + flat metrics + KB binding), not from live handler state.
2. **Attach that read model once inside `SessionEvidenceService.build_projection(...)`** as a new nested field such as `effectiveness_snapshot.retrieval_facts`.
3. **Let `build_session_runtime_diagnostics(...)` prefer the projected `retrieval_facts` for completed sales sessions** when `projection_effectiveness_snapshot` is available, while keeping the existing flat `status/summary/last_*` compatibility fields intact.
4. **Keep `claim_truth` separate from retrieval truth.** `claim_truth` answers whether a sales claim was sufficiently supported; retrieval truth answers whether retrieval happened, what it returned, and why it missed/failed. They should align, not merge.

This follows the loaded skill guidance:
- **FastAPI skill:** keep routes thin and modular; put normalization in one reusable function instead of duplicating dict reshaping in `/report` and `/knowledge-check`.
- **Pydantic skill:** keep response/use-case model changes scoped to the consumer boundary. Since report already exposes `effectiveness_snapshot` as an open dict, S02 does not need premature top-level response-model expansion; stronger typing can wait for S03 UI consumption.

## Implementation Landscape

### Key Files

- `backend/src/common/conversation/runtime_diagnostics.py`
  - Current knowledge-check authority seam.
  - Already knows how to read persisted `knowledge_retrieval` metrics and how to accept `projection_effectiveness_snapshot` from the route.
  - Today it only derives flat last-attempt truth, not structured retrieval facts.

- `backend/src/common/conversation/session_evidence.py`
  - Current report/replay/history/admin evidence authority seam.
  - `build_projection(...)` overlays `claim_truth`, `main_issue`, and `next_goal` onto `projection_snapshot`, but does not read `voice_policy_snapshot.runtime_metrics`.
  - This is the right place to attach retrieval truth for report parity, as a **projection-only** augmentation.

- `backend/src/common/api/practice.py`
  - `GET /practice/sessions/{session_id}/report` returns `projection.effectiveness_snapshot` directly for sales sessions.
  - `GET /practice/sessions/{session_id}/knowledge-check` already resolves a completed sales projection and passes `projection_effectiveness_snapshot` into `build_session_runtime_diagnostics(...)`.
  - That existing hook is the cheapest parity seam; no route family redesign needed.

- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
  - Defines the persisted ledger shape and caps:
    - `MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES = 10`
    - `MAX_KNOWLEDGE_RETRIEVAL_RESULT_SUMMARIES = 3`
    - `MAX_KNOWLEDGE_RETRIEVAL_SNIPPET_CHARS = 240`
  - `build_knowledge_retrieval_ledger_event(...)` already preserves `knowledge_base_ids` and bounded `result_summaries`.
  - S02 should **read** this shape, not invent a second one.

- `backend/src/common/db/schemas.py`
  - `SessionReport.effectiveness_snapshot` is still `dict[str, Any] | None`, so nested `retrieval_facts` can be added without widening the top-level report contract.

- `web/src/lib/api/types.ts`
  - `PracticeSessionReport.effectiveness_snapshot?: Record<string, unknown> | null`
  - No S02 change required unless the UI starts consuming `retrieval_facts`; that is S03 scope.

### Natural Seams / Task Shape

#### 1. Shared retrieval-truth read model
Best seam: a new pure helper (likely under `backend/src/common/conversation/`) or a carefully extracted shared function, used by both projection and diagnostics.

It should read from persisted snapshot data only and normalize:
- KB binding (`knowledge_base_ids`, count)
- top-level retrieval status/summary
- latest attempt
- bounded recent attempts
- structured miss/failure explanation
- preserved `knowledge_base_ids` and `result_summaries` from the ledger

Avoid putting this logic directly into the route. Route glue already exists.

#### 2. Report projection wiring
In `SessionEvidenceService.build_projection(...)`:
- read retrieval truth from `session.voice_policy_snapshot`
- attach it into `projection_snapshot` as something like `retrieval_facts`
- keep this **projection-only**

Do **not** write it back into `session.effectiveness_snapshot` during reads. Current projection logic already overlays aligned claim-truth/issue/goal into a temporary `projection_snapshot` without mutating the persisted row; retrieval truth should follow the same pattern.

#### 3. Knowledge-check parity reuse
In `build_session_runtime_diagnostics(...)`:
- keep the current top-level `status`, `summary`, `last_*`, `recent_queries`, `kb_lock_*` fields for backward compatibility
- when `projection_effectiveness_snapshot` already contains `retrieval_facts`, prefer that shared payload for the new structured field returned by `/knowledge-check`
- keep the current live-session path unchanged; S02 acceptance is about the **same completed session** across `/knowledge-check` and `/report`

#### 4. Tests / proof
S02 can be proven without browser work and without touching frontend rendering.

### What To Build Or Prove First

1. **Shared normalization first**
   - If projection and diagnostics each normalize the ledger differently, parity will drift again immediately.
   - This is the highest-risk seam.

2. **Projection attachment second**
   - Once report has `effectiveness_snapshot.retrieval_facts`, the report side becomes authoritative.

3. **Knowledge-check reuse third**
   - The route already passes `projection_effectiveness_snapshot`; this is mostly read-side wiring once the projection field exists.

4. **Contract/integration proof last**
   - Verify the same session returns the same retrieval truth through both routes.

## Verification Approach

Prefer focused backend packs, run sequentially.

### Primary packs
- `backend/tests/unit/test_session_evidence_service.py`
  - Add assertions that completed-session projections now carry `effectiveness_snapshot["retrieval_facts"]` derived from `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`.
  - Also assert the persisted `session.effectiveness_snapshot` is not rewritten with the derived retrieval field.

- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`
  - Extend current ledger-aware diagnostics tests so knowledge-check exposes the new structured retrieval facts.
  - Add a completed-session case where diagnostics reuse `projection_effectiveness_snapshot["retrieval_facts"]` rather than recomputing a divergent shape.

- `backend/tests/contract/test_practice_evidence_contract.py`
  - Add a same-session contract proving:
    - `/api/v1/practice/sessions/{id}/knowledge-check`
    - `/api/v1/practice/sessions/{id}/report`
    return consistent retrieval facts for the same completed session.
  - Keep the existing claim-truth assertions separate so retrieval truth and claim-truth do not get conflated.

- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
  - Best integration base for S02 because it already exercises persisted `recent_attempts` and knowledge-check behavior from the current route family.
  - Extend with a completed-session `/report` call and assert parity of the new structured retrieval field.

### Suggested focused command
From repo root, one safe sequential pass is:

```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml \
  backend/tests/unit/test_session_evidence_service.py \
  backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py \
  backend/tests/contract/test_practice_evidence_contract.py \
  backend/tests/integration/test_voice_runtime_session_snapshot.py
```

### Verification note
Avoid making `backend/tests/integration/test_knowledge_flow.py` the primary S02 gate. Project knowledge already notes that this suite is more cwd/env sensitive because of the `dev-login` fixture path; it can still be a supplemental check, but it is not the cleanest parity proof surface for this slice.

## Constraints

- **No second truth source.** Report retrieval truth must still come from `SessionEvidenceService`, and knowledge-check must reuse that output for completed sessions instead of inventing a new route-local read model.
- **No live-handler dependency for completed sessions.** Completed-session retrieval truth must come from persisted `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`.
- **Do not call `build_session_runtime_diagnostics(...)` from `build_projection(...)`.** That would reverse the authority boundary and re-entangle route formatting with the report read model.
- **Keep the ledger provider-neutral and bounded.** Reuse S01’s persisted shape instead of exposing raw search provider payloads.
- **Do not widen frontend/API surface unnecessarily in S02.** Nested `effectiveness_snapshot.retrieval_facts` is enough for this slice; report page rendering belongs in S03.

## Common Pitfalls

- **Normalizing the same ledger twice in different ways.** `knowledge-check` and `report` will drift again if each endpoint decides status/summary/latest-attempt independently.
- **Dropping `result_summaries` and `knowledge_base_ids` again.** The current diagnostics helper does this today; S02 must not keep using the truncated attempt shape as the report truth source.
- **Persisting derived retrieval facts into `session.effectiveness_snapshot` on read.** Projection overlays in `session_evidence.py` are currently read-time only; keep that property.
- **Conflating retrieval truth with claim truth.** A session can retrieve and still have `claim_truth = weak_evidence`; that distinction is part of the milestone intent.
- **Over-scoping into UI work.** The backend contract can be completed without touching `web/src/app/(user)/practice/[sessionId]/report/page.tsx` yet.

## Open Risks

- **Shared projection fan-out:** if `retrieval_facts` is added inside `projection.effectiveness_snapshot`, replay/history/admin consumers that pass through the same snapshot will also inherit it. Current tests mostly assert subkeys rather than exact snapshot equality, so blast radius looks low, but the planner should treat this as intentional shared-surface expansion.
- **Status vocabulary mismatch:** persisted ledger events can contain richer raw attempt statuses (for example `hit_keyword_fallback`) while current public knowledge-check status is coarser (`hit`). Decide explicitly whether `retrieval_facts.latest_attempt.status` keeps the raw event status while the top-level `knowledgeCheck.status` remains collapsed.
- **No response-model guard on knowledge-check:** `/knowledge-check` currently returns a raw dict, so contract discipline for the new retrieval field will rely on tests rather than a Pydantic response model until a later tightening pass.

## Skills Discovered

| Technology | Skill | Status |
|---|---|---|
| FastAPI route/service seams | `fastapi-python` | loaded in this unit |
| Pydantic response modeling / nested payload discipline | `pydantic` | loaded in this unit |
| SQLAlchemy ORM | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | installed via `npx skills add ...`; becomes available in subsequent units |

# M008 S01 Session Retrieval Ledger Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make one sales training session answer, truthfully and audibly, whether knowledge retrieval happened, what it retrieved, whether it influenced the session, and how that evidence appears in `knowledge-check` and the canonical report.

**Architecture:** Extend the existing frozen `voice_policy_snapshot` + `runtime_metrics.knowledge_retrieval` seam into a durable session-level retrieval ledger instead of adding a new debug route family. Keep the authority on current APIs: `/api/v1/practice/sessions/{id}/knowledge-check`, `/api/v1/practice/sessions/{id}/report`, and the existing session evidence projection. Persist the retrieval facts once, read them back consistently everywhere, and prove the chain with focused backend tests plus one shipped-route smoke.

**Tech Stack:** FastAPI, SQLAlchemy Async, existing `PracticeSession.voice_policy_snapshot` / runtime metrics, `SessionEvidenceService`, Next.js report page, existing `api.practice.getKnowledgeCheck(...)` client.

---

## Implementation rules

- Do **not** create a second audit/debug route. Use the current route family.
- Do **not** invent a new report truth source outside `SessionEvidenceService`.
- Do **not** store giant raw retrieval payloads if a normalized, auditable summary will do.
- Prefer session-level persisted retrieval facts with stable keys over transient runtime-only logs.
- TDD the contract first.

---

### Task 1: Lock the retrieval-ledger contract in backend tests first

**Files:**
- Modify: `backend/tests/integration/test_knowledge_flow.py`
- Modify: `backend/tests/contract/test_practice_evidence_contract.py`
- Check while coding: `backend/src/common/conversation/runtime_diagnostics.py`
- Check while coding: `backend/src/common/api/practice.py`

**Step 1: Write the failing integration test for a session-level retrieval ledger**

Add an integration case in `backend/tests/integration/test_knowledge_flow.py` that:
- creates a sales session with a ready knowledge base
- injects `runtime_metrics.knowledge_retrieval` containing a normalized retrieval ledger summary
- calls `/api/v1/practice/sessions/{id}/knowledge-check`
- asserts the response includes durable retrieval facts beyond status only

Target shape to lock in the test:
- retrieval happened / not happened
- query or query summary
- hit count
- top hit summaries / titles
- retrieval mode
- last status
- last error when present

**Step 2: Run the new test and verify it fails**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k retrieval_ledger -v
```

Expected: FAIL because current response shape is too thin.

**Step 3: Write the failing contract test for report evidence linkage**

In `backend/tests/contract/test_practice_evidence_contract.py`, add a case that proves a completed session report can expose retrieval-audit facts in a stable contract field, for example under `evidence_completeness`, `effectiveness_snapshot`, or a new `retrieval_audit` object on the report payload.

The test should lock:
- report does not just say `weak_evidence`
- report also exposes the retrieval fact line that explains whether knowledge support was hit / missed / unavailable

**Step 4: Run the contract test and verify it fails**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -k retrieval -v
```

Expected: FAIL because report contract does not yet expose the retrieval audit line.

**Step 5: Commit checkpoint**

Do **not** commit in this planning session, but during execution the checkpoint is:
```bash
git add backend/tests/integration/test_knowledge_flow.py backend/tests/contract/test_practice_evidence_contract.py
git commit -m "test: lock retrieval ledger contract"
```

---

### Task 2: Persist and normalize one session-level retrieval ledger on the existing runtime seam

**Files:**
- Modify: `backend/src/common/conversation/runtime_diagnostics.py`
- Modify: `backend/src/common/api/practice.py`
- Modify: `backend/src/common/conversation/schemas.py` (if response schema needs extension)
- Modify: `backend/src/common/db/schemas.py` (if typed response model needs extension)
- Check while coding: `backend/src/sales_bot/services/voice_runtime_policy.py`
- Check while coding: `backend/src/sales_bot/services/voice_instruction_compiler.py`

**Step 1: Implement one normalized retrieval-ledger builder**

Add a helper on the runtime diagnostics path that reads `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` and emits a **small, stable, auditable** object such as:
- `retrieval_attempted`
- `query_summary`
- `hit_count`
- `top_hits[]` with title/snippet/source type
- `last_status`
- `last_retrieval_mode`
- `last_error`
- `used_in_reasoning` (only if truly derivable from existing facts)

Do not dump opaque provider payloads into the API.

**Step 2: Extend `/knowledge-check` to return the new retrieval audit block**

Modify `backend/src/common/api/practice.py` so `/api/v1/practice/sessions/{id}/knowledge-check` returns the normalized retrieval ledger on the existing response.

**Step 3: Run the Task 1 tests and make them pass**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k retrieval_ledger -v
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -k retrieval -v
```

Expected: PASS.

**Step 4: Add one negative-path test**

Add a case proving malformed or partial `knowledge_retrieval` metrics fail soft:
- response still returns 200
- status remains truthful
- retrieval audit block is `null` or degraded, not garbage

**Step 5: Commit checkpoint**

```bash
git add backend/src/common/conversation/runtime_diagnostics.py backend/src/common/api/practice.py backend/src/common/conversation/schemas.py backend/src/common/db/schemas.py backend/tests/integration/test_knowledge_flow.py backend/tests/contract/test_practice_evidence_contract.py
git commit -m "feat: expose normalized retrieval ledger on knowledge-check"
```

---

### Task 3: Carry retrieval audit into the canonical report evidence line

**Files:**
- Modify: `backend/src/common/conversation/session_evidence.py`
- Modify: `backend/src/common/api/practice.py`
- Modify: `backend/tests/contract/test_practice_evidence_contract.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/session-evidence.ts`
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

**Step 1: Add retrieval audit to the session evidence projection**

Extend `SessionEvidenceProjection` so completed-session report consumers can read one canonical retrieval audit object from the same evidence line.

Keep this projection-level, not report-page-local.

**Step 2: Surface the field on the report API**

Modify the report builder in `backend/src/common/api/practice.py` so the canonical report payload includes retrieval audit facts.

Recommended user-facing semantics:
- no knowledge base
- retrieval not triggered
- retrieval failed
- retrieval miss
- retrieval hit but weak support
- retrieval hit with usable support

**Step 3: Update the frontend types and report helper**

Extend `web/src/lib/api/types.ts` and `web/src/lib/session-evidence.ts` so the report page can render the retrieval evidence note from typed data instead of local heuristics.

**Step 4: Add a focused report-page test**

In `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, add a case that proves the report shows:
- the retrieval evidence block when present
- a degraded/neutral message when retrieval facts are missing
- no contradiction between claim-truth wording and retrieval audit wording

**Step 5: Run focused backend + web tests**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py -k 'retrieval or report' -v
npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx'
```

Expected: PASS.

**Step 6: Commit checkpoint**

```bash
git add backend/src/common/conversation/session_evidence.py backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py web/src/lib/api/types.ts web/src/lib/session-evidence.ts web/src/app/(user)/practice/[sessionId]/report/page.tsx web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
git commit -m "feat: carry retrieval audit into canonical report"
```

---

### Task 4: Prove the shipped route family on one session

**Files:**
- Modify: `.artifacts/` (new proof artifact during execution)
- Optional helper updates: `scripts/` or existing smoke helpers only if needed
- Modify: `.gsd/KNOWLEDGE.md` if a new recurring verification trap is discovered

**Step 1: Prepare one clean knowledge-backed session proof**

Use the existing real route family:
- create session
- verify `knowledge-check`
- inspect report

Do **not** use a special debug route.

**Step 2: Run one real proof**

The proof must answer:
- Did the session have a frozen KB binding?
- Did retrieval happen?
- What was hit or missed?
- Did the canonical report expose the same retrieval audit line?

**Step 3: Save a compact artifact**

Write an artifact under `.artifacts/` that records:
- session id
- knowledge base ids
- knowledge-check retrieval audit block
- report retrieval audit block
- whether the two are consistent

**Step 4: Run the focused verification pack**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py -k 'retrieval or knowledge_check or report'
npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx'
```

Expected: PASS.

**Step 5: Commit checkpoint**

```bash
git add .artifacts/... backend/tests/integration/test_knowledge_flow.py backend/tests/contract/test_practice_evidence_contract.py web/src/app/(user)/practice/[sessionId]/report/page.test.tsx .gsd/KNOWLEDGE.md
git commit -m "test: prove retrieval audit on shipped session routes"
```

---

## Out of scope for this slice

Do **not** include these in M008/S01:
- full audio audit chain
- new audit dashboard page
- PPT realtime interruption
- supervisor assignment workflow
- external integrations

---

## Final validation bar

This slice is only done when one real session can answer, on current routes:

1. which KBs were bound
2. whether retrieval happened
3. what retrieval found or failed to find
4. whether that retrieval fact is visible in `knowledge-check`
5. whether the canonical report exposes the same retrieval truth line

---

Plan complete and saved to `docs/plans/2026-03-28-m008-s01-session-retrieval-ledger-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?

# M003 S06 Scoring Replay Unlock Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the current sales end-session response contract (`status="scoring"`) but finalize the same session to `completed` once canonical replay/report evidence is ready, so `/api/v1/sessions/{id}/replay` and `/api/v1/sessions/{id}/highlights` unlock on the accepted M003 same-session proof chain.

**Architecture:** Preserve the existing lifecycle split: sales REST end still transitions immediately to `scoring`, while a background finalization step promotes the session to `completed`. Do **not** make replay/highlights depend on optional comprehensive-report success. Instead, use the projection-backed evidence line (`SessionEvidenceService`) as the authority for “replay-ready”, keep `report_status` as a separate enhancement signal, and lock the behavior with focused backend tests before re-running the accepted proof chain.

**Tech Stack:** FastAPI, SQLAlchemy Async, pytest, `SessionLifecycleService`, `ReportGenerationTrigger`, `SessionEvidenceService`, replay/highlights APIs.

---

### Task 1: Lock the intended scoring → completed behavior in tests

**Files:**
- Modify: `backend/tests/unit/test_report_generation_trigger.py`
- Modify: `backend/tests/integration/test_session_lifecycle_api.py`
- Modify: `backend/tests/integration/test_replay_api.py`
- Modify: `backend/tests/contract/test_practice_evidence_contract.py`

**Step 1: Write the failing unit test for sales finalization after background completion**

```python
@pytest.mark.asyncio
async def test_trigger_on_session_end_success_promotes_sales_session_to_completed(...):
    mock_session.status = "scoring"
    mock_session.report_status = "processing"

    mock_report_service.generate_report.return_value = Result.ok(MagicMock(overall_score=85.5))

    await report_trigger.trigger_on_session_end(session_id, "sales")

    assert mock_session.report_status == "completed"
    assert mock_session.status == "completed"
```

**Step 2: Run the focused unit test and verify it fails**

Run: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_report_generation_trigger.py -k promotes_sales_session_to_completed -v`
Expected: FAIL because `ReportGenerationTrigger` updates `report_status` today but does not change `PracticeSession.status`.

**Step 3: Write the failing lifecycle/integration test for the two-stage contract**

```python
@pytest.mark.asyncio
async def test_sales_end_response_stays_scoring_but_background_finalization_can_complete_session(...):
    # 1) POST lifecycle end still returns scoring immediately
    # 2) invoke the report/finalization seam
    # 3) persisted session becomes completed
```

**Step 4: Run the focused lifecycle test and verify it fails**

Run: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py -k background_finalization_can_complete_session -v`
Expected: FAIL because the persisted session remains `scoring`.

**Step 5: Write the failing replay/highlights unlock tests**

```python
@pytest.mark.asyncio
async def test_sales_session_replay_unlocks_after_background_finalization(...):
    session.status = "scoring"
    # seed enough conversation/report evidence for projection
    # run finalization seam
    # replay/highlights should return 200
```

```python
@pytest.mark.asyncio
async def test_replay_completion_gate_still_blocks_true_in_progress_sessions(...):
    session.status = SessionStatus.IN_PROGRESS.value
    response = await async_client.get(f"/api/v1/sessions/{session.session_id}/replay", ...)
    assert response.status_code == 400
    assert response.json()["error"] == "[SESSION_NOT_COMPLETED]"
```

**Step 6: Run the replay/contract tests and verify the new unlock test fails while the in-progress gate still passes**

Run: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py -k 'finalization or completion_gate' -v`
Expected: the new finalized-sales unlock test FAILS; the true in-progress gate test still PASSes.

**Step 7: Commit checkpoint**

```bash
git add backend/tests/unit/test_report_generation_trigger.py backend/tests/integration/test_session_lifecycle_api.py backend/tests/integration/test_replay_api.py backend/tests/contract/test_practice_evidence_contract.py
git commit -m "test: lock sales scoring finalization and replay unlock"
```

### Task 2: Implement a projection-backed sales finalization seam

**Files:**
- Modify: `backend/src/evaluation/services/report_generation_trigger.py`
- Modify: `backend/src/common/db/session_lifecycle.py`
- Maybe modify: `backend/src/common/api/practice.py`
- Reference: `backend/src/common/conversation/session_evidence.py`

**Step 1: Add a dedicated helper that decides when a sales session can leave `scoring`**

```python
async def _finalize_session_status_if_ready(
    self,
    session: PracticeSession,
    *,
    scenario_type: str,
) -> None:
    if scenario_type != "sales":
        return
    if session.status != SessionStatus.SCORING.value:
        return

    projection_result = await SessionEvidenceService(self.db).get_projection(
        session_id=session.session_id,
        require_completed=False,
    )
    if projection_result.is_success:
        session.status = SessionStatus.COMPLETED.value
```
```

Use the projection-backed evidence line as the authority. The important rule is:
- **sales immediate end response remains `scoring`**
- **background finalization promotes to `completed` once replay/report evidence is actually readable**
- **optional enhanced-report failure must not keep replay/highlights locked forever if canonical evidence is already available**

**Step 2: Call the helper from the background report/finalization path**

Implement it inside `ReportGenerationTrigger.trigger_on_session_end(...)` so completion is decided after the asynchronous end-session work runs, not inside the immediate REST end response.

**Step 3: Keep `report_status` independent from `session.status`**

Do not collapse these into one field. Preserve:
- `report_status="completed"|"failed"|...` for comprehensive-report generation tracking
- `session.status="completed"` for replay/highlights unlock once canonical evidence is ready

That means a sales session may legitimately end up as:
- `session.status="completed"`
- `report_status="failed"`

…as long as the projection-backed canonical evidence line is readable and replay/highlights can load truthful same-session content.

**Step 4: If needed, add one small lifecycle helper rather than changing the terminal contract**

If `SessionLifecycleService` needs a reusable status promotion helper, keep it narrow:

```python
async def promote_scoring_session_to_completed(self, session: PracticeSession) -> None:
    session.status = "completed"
    await self.db.flush()
```

Do **not** change `terminal_status_for_scenario("sales")` to return `completed`; that would break the shipped immediate end-session contract and the existing scoring intermediate state.

**Step 5: Run the focused implementation tests**

Run: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_report_generation_trigger.py tests/integration/test_session_lifecycle_api.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py -v`
Expected: PASS.

**Step 6: Commit checkpoint**

```bash
git add backend/src/evaluation/services/report_generation_trigger.py backend/src/common/db/session_lifecycle.py backend/src/common/api/practice.py backend/tests/unit/test_report_generation_trigger.py backend/tests/integration/test_session_lifecycle_api.py backend/tests/integration/test_replay_api.py backend/tests/contract/test_practice_evidence_contract.py
git commit -m "fix: finalize sales sessions when replay evidence is ready"
```

### Task 3: Re-prove the accepted M003 chain on the current authority surfaces

**Files:**
- Verify: `backend/tests/integration/test_knowledge_flow.py`
- Verify: `backend/tests/contract/test_practice_evidence_contract.py`
- Verify: `backend/tests/integration/test_replay_api.py`
- Verify live surfaces: `GET /api/v1/practice/sessions/{id}/knowledge-check`, `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, `GET /api/v1/sessions/{id}/highlights`
- Update after proof: `.gsd/milestones/M003/slices/S06/...` artifacts (in the execution session, not in this planning-only step)

**Step 1: Run the focused same-chain backend proof**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_stepfun_realtime_handler.py \
  tests/unit/test_stepfun_knowledge_helpers.py \
  tests/integration/test_knowledge_flow.py \
  tests/integration/test_replay_api.py \
  tests/contract/test_practice_evidence_contract.py
```
Expected: PASS, with replay/highlights tests green for finalized sales sessions and the true in-progress completion gate still intact.

**Step 2: Verify the session-status boundary explicitly**

Use one assertion or debug read that proves the intended sequence:
- immediate end response: `status == "scoring"`
- background finalization: persisted `PracticeSession.status == "completed"`
- replay/highlights: 200 on the same session

**Step 3: Re-run the real same-session proof**

Use the same M003 accepted chain:
- admin Persona / knowledge change
- `POST /api/v1/practice/sessions`
- `/practice/{sessionId}` runtime
- `/practice/{sessionId}/knowledge-check`
- `/practice/{sessionId}/report`
- `/practice/{sessionId}/replay`
- sibling `/api/v1/sessions/{id}/highlights`

Expected:
- no longer stuck at `[SESSION_NOT_COMPLETED]`
- replay page shows truthful same-session evidence, not `统一训练证据不可用`
- highlights endpoint returns same-session items

**Step 4: Update milestone artifacts only after proof is fresh**

Update the S06 plan/summary/UAT and M003 validation/summary only after the focused backend proof and same-session route proof both pass.

**Step 5: Commit checkpoint**

```bash
git add .
git commit -m "test: prove scoring finalization unlocks replay and highlights"
```

## Notes / Non-goals

- Do **not** relax replay/highlights to allow generic `scoring` sessions through; keep the gate strict for true in-progress/non-finalized sessions.
- Do **not** make completion depend on optional enhanced-report success if canonical evidence is already readable.
- Do **not** broaden this into a generic session-status refactor. The smallest credible slice is the sales post-end finalization seam only.

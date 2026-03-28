# M002 Remediation S07/S08 Close-out Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the two missing M002 remediation slices — S07 degraded/resumed coach observability and S08 end-to-end coaching closure proof — then re-run milestone validation and close out M002 if validation passes.

**Architecture:** Do not reopen or reinterpret S01-S04. Treat their shipped semantics as the fixed baseline: sales-first realtime scoring, one primary action direction per turn, stage-aware coaching focus, and completed-session report/replay alignment are already delivered. The remediation work only fills the two gaps called out by `M002-VALIDATION.md`: (1) make coach degraded / resumed state explicit on the current learner/runtime surfaces when realtime coaching partially fails, and (2) prove one real same-session sales path that stays coherent from live coaching through final report/replay review.

**Tech Stack:** FastAPI, SQLAlchemy Async, StepFun/classic sales websocket handlers, runtime diagnostics, React/Next.js learner practice page, Vitest, pytest, browser proof on localhost.

---

## Scope Guardrails

- **Do not** change the sales rubric, pacing semantics, or report-alignment logic delivered in S01-S04 unless fresh evidence proves regression.
- **Do not** add new product surfaces, debug consoles, or milestone-only APIs.
- **Do not** broaden this into M003/M004 work.
- **Do** keep the accepted learner surfaces on the current route family:
  - `/practice/[sessionId]`
  - `/practice/[sessionId]/report`
  - `/practice/[sessionId]/replay`
  - existing runtime/report/replay APIs
- **Do** make the degraded/resumed coach state visible on the same product path the learner already uses.

## Root-Cause Context to Preserve

From the existing `M002-VALIDATION.md`, the milestone is blocked for exactly two reasons:

1. **S07 missing:** there is no delivered proof that capability failure, upstream jitter, silence, or reconnect can degrade only the coach surface while keeping training usable and visibly marked as degraded/resumed.
2. **S08 missing:** there is no delivered live same-session UAT proving one real sales path stays coherent from realtime coaching through final report/replay review.

That means the remediation plan is:
- implement/verify explicit coach degraded-resumed observability on current runtime surfaces,
- capture one live end-to-end same-session proof on current learner surfaces,
- then rerun milestone validation and close out if the verdict flips to pass.

---

### Task 1: S07 — make coach degraded/resumed state explicit on current runtime surfaces

**Files:**
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/sales_bot/websocket/components/capability_processor.py`
- Modify: `backend/src/common/conversation/runtime_diagnostics.py`
- Modify: `backend/src/common/api/practice.py`
- Modify: `web/src/hooks/use-practice-websocket.ts`
- Modify: `web/src/hooks/websocket/message-handlers.ts`
- Modify: `web/src/components/practice/RightPanelContent.tsx`
- Test: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_capability_processor.py`
- Test: `web/src/hooks/websocket/message-handlers.test.ts`
- Test: `web/src/hooks/use-practice-websocket.test.ts`
- Test: `web/src/components/practice/RightPanelContent.test.tsx`

**Step 1: Write the failing backend tests for degraded/resumed coach state**

Add focused tests that prove:
- capability failure sets an explicit degraded runtime signal,
- reconnect or successful next evaluation clears that degraded state and emits resumed/healthy state,
- training session status remains usable (`in_progress`) while coach state is degraded.

Suggested test names:
- `test_run_realtime_feedback_marks_coach_degraded_when_capability_pipeline_fails`
- `test_run_realtime_feedback_clears_coach_degraded_state_after_successful_resume`
- `test_capability_processor_failure_does_not_change_training_session_status`

**Step 2: Run backend tests to verify they fail**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_stepfun_realtime_handler.py \
  tests/unit/test_capability_processor.py \
  -k 'degraded or resumed or capability_pipeline_fails' -v
```
Expected: FAIL because current runtime path does not yet expose an explicit degraded/resumed coach contract.

**Step 3: Write the failing frontend tests for learner-visible degraded/resumed state**

Add focused tests that prove:
- websocket/runtime messages surface a visible `coach degraded / data unavailable` state on the current learner panel,
- the degraded state clears on resumed/healthy messages,
- the learner still sees the session as ongoing instead of terminal/broken.

Suggested test names:
- `it("shows coach degraded state without breaking the active practice session")`
- `it("clears degraded coach state when coaching resumes")`

**Step 4: Run frontend tests to verify they fail**

Run:
```bash
cd web && pnpm dlx npm@11.6.1 test -- --run \
  'src/hooks/websocket/message-handlers.test.ts' \
  'src/hooks/use-practice-websocket.test.ts' \
  'src/components/practice/RightPanelContent.test.tsx'
```
Expected: FAIL because the learner UI does not yet render an explicit degraded/resumed coaching state.

**Step 5: Implement the minimal degraded/resumed runtime contract**

Implement a narrow contract on existing seams only:
- backend runtime keeps one explicit coach status state (`healthy`, `degraded`, `resumed` or equivalent stable vocabulary),
- runtime diagnostics / current practice session API can expose that state,
- websocket handling preserves training usability while updating the coach state,
- frontend renders one explicit degraded/resumed status on the current right panel without adding a second coach surface.

Keep the implementation minimal:
- no new pages,
- no second debug API,
- no changes to S01-S04 scoring semantics.

**Step 6: Run focused backend + frontend tests to verify they pass**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_stepfun_realtime_handler.py \
  tests/unit/test_capability_processor.py \
  -k 'degraded or resumed or capability_pipeline_fails' -v
```

Run:
```bash
cd web && pnpm dlx npm@11.6.1 test -- --run \
  'src/hooks/websocket/message-handlers.test.ts' \
  'src/hooks/use-practice-websocket.test.ts' \
  'src/components/practice/RightPanelContent.test.tsx'
```
Expected: PASS.

**Step 7: Record the S07 slice artifacts**

After verification passes, add:
- `S07-PLAN.md` via GSD if missing
- `S07-SUMMARY.md`
- `S07-UAT.md`

The UAT only needs to prove the degraded/resumed state on the current learner/runtime chain, not full milestone closure.

---

### Task 2: S08 — prove one real same-session sales coaching closure path

**Files:**
- Reuse current learner/runtime/product routes
- Likely modify only if proof exposes a real bug:
  - `backend/src/common/api/practice.py`
  - `backend/src/common/conversation/replay.py`
  - `backend/src/common/conversation/session_evidence.py`
  - `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- Test: existing focused suites plus new live UAT artifact
- Create/Update: `.gsd/milestones/M002/slices/S08/S08-UAT.md`
- Create/Update: `.gsd/milestones/M002/slices/S08/S08-SUMMARY.md`

**Step 1: Define the exact closure proof before touching code**

The same session must prove all of these on current product surfaces:
- learner sees sales-first realtime coaching during practice,
- each turn has one primary action direction,
- if coach degrades, learner can tell it degraded and later resumed,
- the same session’s final report/replay stays on the same issue/goal family,
- degraded path remains diagnosable.

Write this as the S08 UAT checklist before implementation changes.

**Step 2: Run the current focused backend suites as a baseline**

Run:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml \
  tests/unit/test_realtime_scoring.py \
  tests/unit/test_stepfun_realtime_handler.py \
  tests/unit/test_capability_processor.py \
  tests/unit/test_realtime_feedback_arbiter.py \
  tests/unit/test_effectiveness_sales_coaching_focus.py \
  tests/unit/test_effectiveness_sales_report_alignment.py \
  tests/unit/test_session_evidence_service.py \
  tests/contract/test_practice_evidence_contract.py \
  tests/integration/test_practice_evidence_flow.py
```
Expected: PASS. If not, stop and investigate before any live UAT.

**Step 3: Run the current focused frontend suites as a baseline**

Run:
```bash
cd web && pnpm dlx npm@11.6.1 test -- --run \
  'src/hooks/websocket/message-handlers.test.ts' \
  'src/hooks/use-practice-websocket.test.ts' \
  'src/components/practice/ScorePanel.test.tsx' \
  'src/components/practice/RightPanelContent.test.tsx' \
  'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' \
  'src/app/admin/users/[id]/page.test.tsx'
```
Expected: PASS.

**Step 4: Run one real same-session localhost coaching proof**

Use the current learner route family on localhost only:
1. Start backend and web locally on matching hostnames.
2. Dev-login.
3. Create one fresh sales session on the live API.
4. Open `/practice/{sessionId}`.
5. Drive a real or controlled same-session coaching path through the current runtime.
6. Capture:
   - realtime coaching state,
   - any degraded/resumed coach state,
   - final report,
   - final replay,
   - same-session issue/goal consistency.

This proof is invalid if it stitches together evidence from different sessions.

**Step 5: If the live proof exposes a real gap, fix only that gap**

Use root-cause-first debugging. Acceptable fixes are only those needed to make the same-session closure proof truthful on the current route family.

Do **not** reopen S01-S04 semantics unless the live proof shows an actual regression there.

**Step 6: Re-run the full focused backend + frontend verification after any fix**

Re-run the Task 2 baseline commands fresh.

**Step 7: Record the S08 slice artifacts**

Write:
- `S08-SUMMARY.md`
- `S08-UAT.md`

The UAT must reference the exact session/proof path used for milestone closure.

---

### Task 3: Re-run M002 validation and close out only if the verdict flips to pass

**Files:**
- Verify: `.gsd/milestones/M002/M002-ROADMAP.md`
- Verify/Create: `.gsd/milestones/M002/M002-VALIDATION.md`
- Verify/Create: `.gsd/milestones/M002/M002-SUMMARY.md`

**Step 1: Confirm roadmap is fully green before validation**

Check that S07 and S08 are now complete in both GSD state and rendered roadmap.

Run:
```bash
rg -n "S07|S08" .gsd/milestones/M002/M002-ROADMAP.md
```
Expected: both slices present and marked complete.

**Step 2: Run milestone validation**

Use the fresh proof only. Validation should explicitly audit:
- criterion 3 (same-session live coaching → final conclusion coherence),
- criterion 4 (degraded/resumed coach visibility),
- slice delivery for S07 and S08.

**Step 3: If validation is not `pass`, stop**

Do not attempt close-out. Document what still blocks it.

**Step 4: If validation is `pass`, execute milestone close-out**

Use `gsd_complete_milestone` only after validation passes.

Required close-out content should include:
- what S07 added,
- what S08 proved live,
- why R009 can now move to validated (if the evidence supports it),
- what still remains as follow-up after M002.

**Step 5: Re-verify the final state**

Run:
```bash
ls .gsd/milestones/M002/M002-VALIDATION.md .gsd/milestones/M002/M002-SUMMARY.md
rg -n "S07|S08" .gsd/milestones/M002/M002-ROADMAP.md
```
Expected: validation and summary exist, and roadmap is fully green.

---

## Distance to true M002 close-out

If no hidden blocker appears, M002 is exactly **three execution stages** away from true close-out:

1. **Finish S07**
   - implement + verify degraded/resumed coach observability on current runtime surfaces
2. **Finish S08**
   - capture one real same-session coaching closure proof on current learner/report/replay routes
3. **Re-run validation and close out**
   - validation must flip from `needs-remediation` to `pass`
   - then milestone completion can be executed legitimately

In practical terms, the minimum required deliverables are:
- `S07-PLAN.md`, `S07-SUMMARY.md`, `S07-UAT.md`
- `S08-PLAN.md`, `S08-SUMMARY.md`, `S08-UAT.md`
- fresh `M002-VALIDATION.md` with `pass`
- final milestone close-out summary

---

Plan complete and saved to `docs/plans/2026-03-27-m002-remediation-s07-s08-closeout.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
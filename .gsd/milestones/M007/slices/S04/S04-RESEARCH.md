# S04 Research — 最终集成验证与封板

## Summary

S04 is now a targeted closure slice, not a new feature slice. R009’s semantic seams are already aligned across live coaching, `/practice/{sessionId}/report`, `/practice/{sessionId}/replay`, and `/knowledge-check`. The remaining product blocker is mechanical: the StepFun post-end path still leaves some real sales sessions stuck in `status="scoring"`, which keeps replay locked even though the canonical report is already readable on the same session.

The strongest root-cause candidate is in the background report trigger path, not in report/replay semantics. `backend/src/evaluation/services/report_generation_trigger.py` creates its own async DB session via `get_db_session()` and updates `PracticeSession.report_status` / `PracticeSession.status`, but `trigger_on_session_end()` only flushes those updates and never commits them. Meanwhile `backend/src/evaluation/services/comprehensive_report.py` commits the optional comprehensive report row inside `_store_report()`. That combination matches the S02 live artifact exactly: canonical `/practice/{id}/report` remains readable from projection/report storage, while `PracticeSession.status` can stay `scoring` and `/sessions/{id}/replay` remains correctly blocked by the completed-session gate.

Per the loaded skills: keep this YAGNI-tight (`brainstorming`), do not declare closure without fresh full evidence (`verification-before-completion`), and run the localhost proof on the shipped route family with a browser workflow that explicitly navigates, inspects, interacts, and re-checks state (`agent-browser`).

## Active Requirement Focus

- **R009 (owner: M007/S04)** — retire the last closure/proof blocker by making the same-session StepFun terminal flow reach truthful completion on the existing learner/runtime/report/replay route family, then validate and close the milestone through normal GSD render paths.

## Skills Discovered

Installed or already available skills directly relevant to this slice:

- **Already available:** `agent-browser`, `websocket-engineer`, `fastapi-python`, `verification-before-completion`
- **Discovered via `npx skills find`:** SQLAlchemy ORM skills exist; installed `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` for later units. It is not available in this session prompt yet, but subsequent units should see it.
- **WebSockets:** a dedicated websocket skill already exists locally (`websocket-engineer`), so no extra install was needed there.

## Recommendation

Plan S04 in this order:

1. **Fix the backend background-finalization persistence bug first.** Do not touch replay gating. Replay is behaving correctly; sales sessions need to actually leave `scoring`.
2. **Add a regression that exercises the real fire-and-forget DB-session path.** Current unit/integration coverage mostly passes an already-open DB session to `ReportGenerationTrigger` and then commits externally, which can hide the missing-commit bug.
3. **Re-run the same-session route-family regression pack.** Confirm report is still readable during `scoring`, replay still blocks before completion, and replay unlocks only after the session truly becomes `completed`.
4. **Run one fresh localhost proof on `localhost:3445` ↔ `localhost:3444`.** Use the existing learner/report/replay family only; no mocks, no alternate debug surfaces, no cross-session stitching.
5. **Only then do GSD close-out operations.** Use generator-backed milestone validation/completion; do not hand-edit `.gsd/STATE.md` or `.gsd/state-manifest.json`.

## Implementation Landscape

### 1) Lifecycle / completion seam

Relevant files:

- `backend/src/common/db/session_lifecycle.py:96` — `terminal_status_for_scenario()` makes sales session end transition to `scoring`, not `completed`.
- `backend/src/common/db/session_lifecycle.py:240` + `:257` — `trigger_report_generation_if_needed()` / `_trigger_report_generation()` fire the background report job after lifecycle commit.
- `backend/src/common/api/practice.py:397` — `_sync_sales_realtime_terminal_evidence()` copies StepFun runtime/message score snapshots onto `PracticeSession` before cleanup.
- `backend/src/common/api/practice.py:464` — `_prepare_terminal_lifecycle_result()` persists sales-side terminal evidence before the async report trigger starts.
- `backend/src/common/api/practice.py:563` — `_run_lifecycle_action()` commits the lifecycle transition, triggers report generation, syncs the live handler, broadcasts terminal events, then closes the websocket connection.

Implication for S04: do **not** weaken replay’s completion gate. The intended design is still: end → immediate `scoring` → background finalization → `completed` once canonical evidence is readable.

### 2) Report vs replay authority seam

Relevant files:

- `backend/src/common/api/practice.py:1382` — `/api/v1/practice/sessions/{id}/report` is projection-backed and does **not** require completed status.
- `backend/src/common/api/practice.py:1508` — `/knowledge-check` can still read live handler diagnostics while a live handler exists.
- `backend/src/common/conversation/session_evidence.py` — `SessionEvidenceService.get_projection(... require_completed=False)` is the canonical report/read-model seam.
- `backend/src/common/conversation/replay.py:95` — replay explicitly requires `SessionStatus.COMPLETED`.

This means the current split is expected **until** background finalization commits. S04 should make the session reach `completed`, not make replay looser.

### 3) Root-cause candidate: background trigger never commits its own session-level updates

Relevant files:

- `backend/src/evaluation/services/report_generation_trigger.py:39` — `get_db_session()` yields a bare `AsyncSession`; there is no implicit commit on exit.
- `backend/src/evaluation/services/report_generation_trigger.py:92` — `trigger_on_session_end()` updates `report_status` / finalizes sales status, but never commits after those updates.
- `backend/src/evaluation/services/report_generation_trigger.py:165` — `_finalize_session_status_if_ready()` only flushes `session.status = completed`.
- `backend/src/evaluation/services/report_generation_trigger.py:281` — `_update_report_status()` only flushes report-status changes.
- `backend/src/evaluation/services/comprehensive_report.py:603` — `_store_report()` *does* commit the report row.
- `backend/src/common/db/session.py` — the project’s DB policy is explicit commit only; session close does not auto-commit.

This is the most important S04 finding. It explains why:

- `report_generation_failed [NO_STAGE_RESULTS]` appears,
- projection-backed `/practice/{id}/report` can still work,
- but `PracticeSession.status` / `report_status` may roll back when the background session closes,
- leaving replay blocked with `[SESSION_NOT_COMPLETED]`.

The planner should treat this as the first code seam to repair and test.

### 4) Secondary divergence: classic handler still has its own end-session path

Relevant files:

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:2874` — StepFun `_handle_session_end()` now just closes after terminal notifications/capability cleanup; lifecycle/report triggering happens earlier in `_apply_lifecycle_action()`.
- `backend/src/sales_bot/websocket/enhanced_handler.py:411` — classic `_handle_session_end()` still directly builds a comprehensive report inside the handler.

This is a real divergence, but it is **not** the current live blocker. Do not widen S04 into a handler-architecture cleanup unless focused tests show the classic path has regressed.

### 5) GSD artifact / generator seam

Relevant files/surfaces:

- `.gsd/milestones/M007/slices/S04/S04-PLAN.md` — exists but has no tasks yet.
- `.gsd/STATE.md` — now mostly aligned (`Active Milestone: M007`, `Active Slice: S04`, phase planning).
- `.gsd/state-manifest.json` — still materially stale: `M001`/`M002` are still marked `active` with blank titles, despite current milestone truth living in M007.

Implication: S04 must finish with normal GSD tool flows (`gsd_validate_milestone`, `gsd_complete_milestone`, slice completion), then re-read rendered state surfaces. Do not patch generated files manually.

## Natural Seams for Tasking

### Task seam A — backend finalization fix + regression

Touch first:

- `backend/src/evaluation/services/report_generation_trigger.py`
- `backend/tests/unit/test_report_generation_trigger.py`
- one real-session persistence regression under `backend/tests/integration/` or `backend/tests/contract/`

Goal:

- make background finalization persist `session.status` / `report_status` on its own DB session,
- prove it with a regression that fails on the live `db=None`/own-session path, not just the injected-session path.

### Task seam B — route-family contract proof

Mostly verification, maybe no code changes if seam A is correct.

Primary files:

- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `backend/tests/integration/test_session_lifecycle_api.py`
- `backend/tests/integration/test_replay_api.py`
- optionally `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- optionally `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- optionally `web/src/app/(dashboard)/history/page.test.tsx` if report-status semantics become visible there

Goal:

- report remains readable during `scoring`,
- replay stays blocked pre-completion,
- replay unlocks post-completion on the same session,
- no frontend workaround is introduced.

### Task seam C — live localhost proof + evidence capture

No new product code unless live proof reveals a missing UI/route contract.

Surfaces:

- `/practice/{sessionId}`
- `/practice/{sessionId}/report`
- `/practice/{sessionId}/replay`
- `/api/v1/practice/sessions/{id}`
- `/api/v1/practice/sessions/{id}/report-status`
- `/api/v1/practice/sessions/{id}/knowledge-check`
- backend logs around `report_generation_triggered`, `sales_session_finalized`, `report_generation_failed`, `no_scoring_context_available`

Goal:

- produce one fresh same-session proof artifact for M007 close-out.

### Task seam D — milestone validation / close-out / rendered-state reconciliation

No manual file edits to generated surfaces.

Use GSD tools only after fresh proof passes:

- `gsd_complete_slice`
- `gsd_validate_milestone`
- `gsd_complete_milestone`
- likely `gsd_requirement_update` for `R009` → validated, with proof notes

Goal:

- generate M007 validation/summary artifacts,
- confirm `.gsd/STATE.md` and `.gsd/state-manifest.json` stop contradicting milestone truth.

## Verification Plan

Per `verification-before-completion`, S04 should not claim closure from partial evidence. The minimum credible pack is:

### Backend focused regressions

Run sequentially, not in parallel.

```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_report_generation_trigger.py
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k "report_generation or scoring"
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "same_session or knowledge_check or replay"
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_practice_evidence_flow.py
```

If the fire-and-forget regression lands in another file, add that exact file explicitly rather than relying on a broad suite.

### Frontend route-family regressions

Only rerun the surfaces that encode report/replay behavior unless backend changes force more.

```bash
npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
```

If report-status visibility changes on history/support surfaces, add the relevant focused test there rather than broad frontend packs.

### Localhost proof

Use same-host frontend/backend (`localhost` ↔ `localhost`) exactly as S02 documented.

Suggested repo-root-safe server commands:

```bash
PYTHONPATH=backend/src backend/venv/bin/uvicorn main:app --app-dir backend/src --port 3444
pnpm --dir web dev
```

Proof expectations:

1. Active learner route shows the stable same-session cue (`当前同 session 结论`, `主问题`, `下一轮目标`).
2. Ending the session still returns immediate `status: "scoring"`.
3. Background finalization then moves `/api/v1/practice/sessions/{id}` to `status: "completed"`.
4. `/practice/{id}/report` remains readable on that same session.
5. `/practice/{id}/replay` unlocks on that same session.
6. If `report_generation_failed [NO_STAGE_RESULTS]` still appears, explicitly decide whether that is now optional-noise (acceptable) or still a blocker before any close-out claim.

Use browser evidence, not prose-only assertions. The `agent-browser` workflow rule applies: navigate → inspect → act → re-inspect.

### GSD rendered-state read-back

After slice completion + milestone validation/completion:

- re-read `.gsd/STATE.md`
- re-read `.gsd/state-manifest.json`

At minimum, expect M007 metadata to be truthful and no longer queued/stale. If generated state still contradicts milestone truth, S04 is not honestly closed.

## Risks / Watchpoints

- **Do not “fix” replay by weakening `ReplayService._check_session_completed()`.** That would hide the lifecycle bug instead of retiring it.
- **Do not add a second debug/status API.** Existing proof surfaces are enough; the milestone explicitly forbids milestone-only surfaces.
- **Do not trust `NO_STAGE_RESULTS` alone as the blocker.** The blocker is the persisted session lifecycle state. `NO_STAGE_RESULTS` may remain optional enhancement noise if completion and replay unlock still succeed.
- **Do not parallelize backend pytest jobs.** Coverage combine races are already documented in project knowledge.
- **Do not use mixed `localhost` / `127.0.0.1` hosts in the browser proof.** Host-only auth cookies will produce false 401s.
- **Do not hand-edit generated GSD files.** S03 already established that canonical docs and generated surfaces must be reconciled through the DB/render path.

## Bottom Line for the Planner

The smallest honest S04 is:

- fix the background report-trigger commit boundary,
- add one regression that proves the live fire-and-forget path persists completion,
- rerun the existing same-session report/replay contract pack,
- capture one fresh localhost proof on the shipped route family,
- then close the slice and milestone through GSD tools and re-read generated state.

No new learner surface, no replay-gate relaxation, no manual `.gsd` edits.
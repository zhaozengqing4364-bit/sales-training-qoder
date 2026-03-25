---
id: T03
parent: S05
milestone: M003
key_files:
  - .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Treat projection-backed canonical report degradation as shippable only when the learner still gets a truthful same-session evidence surface with explicit fallback copy.
  - Treat same-session replay/highlights blocked behind `status="scoring"` as the remaining release blocker for M003 final acceptance, even though the replay page surfaces that failure explicitly.
  - Use measured browser timeline milestones from the same-session proof as the current latency guardrail until this business chain exposes a durable server-side latency metric.
duration: ""
verification_result: passed
completed_at: 2026-03-25T09:44:29.285Z
blocker_discovered: false
---

# T03: Documented M003 release guardrails and marked replay-blocked scoring sessions as the remaining acceptance blocker.

**Documented M003 release guardrails and marked replay-blocked scoring sessions as the remaining acceptance blocker.**

## What Happened

I rewrote `.gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md` from the stub plan into the actual M003 stability and acceptance guardrail document. To keep it tied to the real product line instead of a synthetic checklist, I first re-read the M003 roadmap, the S05 live UAT artifact, and the current owning code in `backend/src/common/api/practice.py` and `web/src/app/(user)/practice/[sessionId]/report/page.tsx`. That let me anchor the written guardrails to the shipped report/replay behavior: projection-backed canonical report reads from the shared evidence path, optional enhanced insights/highlights already have explicit fallback copy in the report page, and replay/highlights still hard-gate on completed-session status.

Using the same-session proof from `S05-UAT.md`, I turned the task artifact into a release-facing contract with three parts: measured latency bands from the recorded browser timeline, the degraded states that remain shippable when the canonical evidence line survives, and the failures that block M003 acceptance. The latency section stays honest about the current instrumentation boundary — browser-level timings exist in the evidence pack, but there is no durable server-side latency metric on this proof path yet — so the guardrail is written against user-visible milestones on the same chain. The degraded-state section explicitly keeps runtime transcription fallback and enhanced-report/highlights unavailability inside the shippable line when the learner still gets a truthful same-session report. The blocking section draws the hard line on the live issue from T02: if the same proof session stays `scoring` and replay/highlights remain blocked with `[SESSION_NOT_COMPLETED]` after `report_generation_failed [NO_STAGE_RESULTS]`, M003 is not complete.

I also recorded that acceptance line as decision `D060` in `.gsd/DECISIONS.md` so downstream slice closure and milestone wrap-up reuse the same report-versus-replay boundary instead of reinterpreting the UAT. Finally, I updated `.codex/loop/state.json` and `.codex/loop/log.md` so the safe-grow continuity layer points at T03 as done and carries forward the replay-blocker rule for the next unit.

## Verification

Ran a fresh slice-close verification set after writing the guardrail. First, I reran the exact S05 objection-heavy backend regression suite from T01 and it passed with all 90 tests green. Second, I rechecked the live UAT proof pack from T02: `S05-UAT.md` is still non-empty and the trace, timeline, report debug bundle, and replay debug bundle referenced by the artifact still exist on disk. Third, I ran the task’s own verification gate and confirmed the rewritten `T03-PLAN.md` now contains the required latency, degraded/fallback, and blocking language. I also re-read the updated loop state/log after rewriting them to confirm the continuity layer now points at `M003-S05-T03`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 7920ms |
| 2 | `/usr/bin/time -p sh -c 'test -s .gsd/milestones/M003/slices/S05/S05-UAT.md && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/m003-s05-t02.trace.zip && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/s05-timeline.json && test -d .artifacts/browser/2026-03-25T08-32-14-317Z-s05-report && test -d .artifacts/browser/2026-03-25T08-31-00-679Z-s05-replay'` | 0 | ✅ pass | 10ms |
| 3 | `rg -n "latency|degraded|fallback|block" .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md` | 0 | ✅ pass | 10ms |


## Deviations

None.

## Known Issues

The same live objection-heavy proof session from T02 still shows the remaining M003 acceptance problem: after end-of-session, the session can remain `status="scoring"`, `/api/v1/sessions/{id}/replay` and `/api/v1/sessions/{id}/highlights` stay blocked with `[SESSION_NOT_COMPLETED]`, and backend logs attribute that state to `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available`. The new guardrail documents this as release-blocking rather than treating it as an acceptable degradation.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

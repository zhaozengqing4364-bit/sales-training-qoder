---
id: T02
parent: S05
milestone: M003
key_files:
  - .gsd/milestones/M003/slices/S05/S05-UAT.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Kept the live proof on the real practice-page recorder path by delaying synthetic microphone playback after `getUserMedia` instead of swapping to the websocket text shortcut.
  - Preserved the first same-session transcription-miss fallback in the evidence pack instead of discarding it, because it is part of the current runtime stability boundary.
  - Treated the `report readable / replay blocked while scoring` outcome as a real degraded-state finding to document for T03 rather than forcing the session into an artificial green replay path.
duration: ""
verification_result: passed
completed_at: 2026-03-25T08:42:56.824Z
blocker_discovered: false
---

# T02: Captured a live objection-heavy S05 evidence pack with canonical report proof and replay degradation evidence.

**Captured a live objection-heavy S05 evidence pack with canonical report proof and replay degradation evidence.**

## What Happened

I used the live localhost product chain to capture one honest objection-heavy same-session proof instead of writing code. First I brought up the repo’s local backend/frontend stack, confirmed the KB-backed sales path on the admin knowledge page, and updated the existing `石犀专家` persona into an explicit objection-heavy pressure contract while keeping its knowledge-base lock intact. Creating a fresh StepFun sales session showed that the runtime snapshot froze the expected `customer_pressure_source: explicit`, KB binding, and strict no-network tool policy.

On the real `/practice/{sessionId}` page I drove the page’s own recorder + websocket path with synthetic `getUserMedia` speech clips so the browser stayed on the shipped runtime surface. The first recording attempt produced a genuine degraded runtime signal — the page surfaced `当前会话已开启知识库强制模式，但本轮语音转写尚未完成...` and backend logged `timeout_proceeded_without_transcription_completion`. I kept that on the same session, delayed playback after `getUserMedia`, and the later turns transcribed successfully. The live page then showed the expected objection-heavy behavior: the persona kept forcing ROI proof, the score panel and action card updated in real time, the stage stayed on `异议处理`, and the current proof gap remained visible as `补上案例、数据或ROI证据，让价值主张更可信。`

Ending the same session redirected into the canonical report page. That page carried the same-session evidence correctly: overall score 70.37, `claim_truth.status=weak_evidence`, KB hit status with 3/3 retrieval hits, explicit `customer_pressure_source: explicit` in the voice snapshot reference, and the right sales main issue / next goal. Optional layers degraded honestly instead of hiding the usable report: the page showed both `综合洞察暂不可用，当前页面仅展示统一训练证据。` and `高光片段暂不可用，基础评估结果不受影响。`.

I also checked the replay side of the same session. Replay did not go green: the session stayed `scoring`, `/sessions/{id}/replay` and `/sessions/{id}/highlights` returned `[SESSION_NOT_COMPLETED]`, and the browser replay page surfaced `统一训练证据不可用` with the same status message. Backend logs showed why: after end-of-session, the canonical projection/report still built, but enhanced report generation failed with `[NO_STAGE_RESULTS]` and `no_scoring_context_available`, so replay remained blocked. I wrote all of that into `S05-UAT.md`, saved the two reusable runtime gotchas to `.gsd/KNOWLEDGE.md`, and updated the safe-grow state/log so T03 can write guardrails against the real observed acceptance boundary rather than an assumed all-green replay path.

## Verification

Verified the task output directly with fresh filesystem checks: `S05-UAT.md` exists and is non-empty, and the browser trace/timeline/debug bundles referenced inside it exist on disk. Before cleanup, I also exercised the live localhost browser flow end to end: admin knowledge search hit 5 fragments from the bound KB, the real practice page showed runtime action-card/score-panel updates on the same session, the report page passed explicit browser assertions for `训练评估报告`, `证据偏弱`, `知识库命中检测`, `已命中`, `customer_pressure_source:explicit`, and the optional-highlights degraded copy, and the replay page passed explicit assertions for `统一训练证据不可用` plus `[SESSION_NOT_COMPLETED] ... Current status: scoring`. Direct API reads for the same session confirmed `overall_score=70.37`, `claim_truth.status=weak_evidence`, `knowledge-check.status=hit`, `attempt_count=3`, `hit_query_count=3`, and backend logs confirmed the replay blockage root cause as `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `/usr/bin/time -p sh -c 'test -s .gsd/milestones/M003/slices/S05/S05-UAT.md && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/m003-s05-t02.trace.zip && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/s05-timeline.json && test -d .artifacts/browser/2026-03-25T08-32-14-317Z-s05-report && test -d .artifacts/browser/2026-03-25T08-31-00-679Z-s05-replay'` | 0 | ✅ pass | 10ms |
| 2 | `/usr/bin/time -p sh -c "rg -q 'ef48ed80-0bfa-4a47-82c7-228ac3d468d2' .gsd/milestones/M003/slices/S05/S05-UAT.md && rg -q 'SESSION_NOT_COMPLETED' .gsd/milestones/M003/slices/S05/S05-UAT.md && rg -q 'customer_pressure_source == \"explicit\"' .gsd/milestones/M003/slices/S05/S05-UAT.md"` | 0 | ✅ pass | 30ms |


## Deviations

Used a synthetic `getUserMedia` audio stream on the real `/practice/{sessionId}` page because browser automation cannot speak into a physical microphone; this kept the live recorder + websocket path intact without falling back to the websocket `type:"text"` shortcut. Also verified the persona-pressure save through the live admin backend response because the page save button did not visibly redirect after submission.

## Known Issues

The live session `ef48ed80-0bfa-4a47-82c7-228ac3d468d2` remained `status="scoring"` after end. Canonical `/practice/{id}/report` and `/practice/{id}/knowledge-check` still built successfully from persisted evidence, but `/sessions/{id}/replay` and `/sessions/{id}/highlights` remained blocked with `[SESSION_NOT_COMPLETED]`. Backend log tied that state to `report_generation_failed [NO_STAGE_RESULTS]` plus `no_scoring_context_available`.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S05/S05-UAT.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

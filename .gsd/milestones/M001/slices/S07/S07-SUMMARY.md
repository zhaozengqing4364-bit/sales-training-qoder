---
id: S07
parent: M001
milestone: M001
provides:
  - Canonical PPT post-session review on the shared `/practice/{sessionId}/report` entrypoint, backed by page-aware presentation evidence, degraded diagnostics, and presentation-preserving retry continuity.
requires:
  - slice: S02
    provides: Unified SessionEvidence/shared-report baseline so presentation postmortems could land on the same canonical single-session contract instead of a second truth surface.
  - slice: S04
    provides: Live standard-PPT identity/version pipeline so presentation review reads the latest governed deck and keeps retry bound to the same `presentation_id`.
affects:
  - S08
key_files:
  - backend/src/presentation_coach/services/presentation_report_service.py
  - backend/src/presentation_coach/websocket/presentation_handler.py
  - backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/db/schemas.py
  - backend/src/common/api/practice.py
  - backend/tests/contract/test_presentation_report_contract.py
  - backend/tests/integration/test_presentation_report_flow.py
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
key_decisions:
  - D028
  - D029
patterns_established:
  - Keep `PresentationReportService.build_presentation_review(...)` as the single PPT review authority, then map that payload into `SessionEvidenceService`, `/practice/sessions/{id}/report`, and the shared report page instead of recomputing PPT heuristics at each read surface.
  - Presentation degraded history must stay presentation-shaped: expose `scenario_type="presentation"`, `presentation_review`, and explicit degraded completeness/coverage reasons rather than falling back to sales `main_issue` / `next_goal` semantics.
  - Local S07 runtime/browser proof is most reliable when frontend/backend share the same loopback host and the websocket uses real audio chunks plus `page_change`; the StepFun `type:"text"` shortcut can finish a session but does not prove page-number persistence.
observability_surfaces:
  - `practice_session_evidence_projection_built`
  - `practice_session_report_built`
  - `GET /api/v1/practice/sessions/{id}/report`
  - `backend/tests/contract/test_presentation_report_contract.py`
  - `backend/tests/integration/test_presentation_report_flow.py`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Live presentation sessions `8531c7f6-50da-4934-9fd4-63784c791edf` (fresh complete) and `ec5b7b03-a83a-4ee6-bc33-d768ccfec610` (historical degraded)
drill_down_paths:
  - .gsd/milestones/M001/slices/S07/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S07/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S07/tasks/T03-SUMMARY.md
duration: 4h
verification_result: passed
completed_at: 2026-03-24T12:06:53+08:00
---

# S07: PPT 对练会后统一复盘可用化

**Shared `/practice/{sessionId}/report` now serves canonical PPT postmortems from page-aware evidence, and a fresh local page-turn session proved that the same report page can show complete PPT review content without leaking sales-only UI or semantics.**

## What Happened

S07 closed the remaining PPT postmortem split between the dedicated presentation evaluator and the shared report entrypoint. On the backend, `PresentationReportService` became the single builder for normalized PPT review facts: six dimension scores, page summaries, required-talking-point coverage, issue counts, strengths, improvements, recommendations, and degraded diagnostics. Legacy presentation persistence was also tightened so `transcript_metadata.page_number` travels through the existing message-analysis update path instead of depending on a second write lane.

With that review payload available, `SessionEvidenceService` and `GET /api/v1/practice/sessions/{id}/report` were extended into a scenario-aware contract. Presentation sessions now return `scenario_type="presentation"` and a canonical `presentation_review` block on the same `/practice/sessions/{id}/report` route already used by learners and supervisors. The write-up stayed intentionally presentation-shaped even when history is incomplete: older sessions with missing page evidence still expose `presentation_review`, `evidence_completeness.page_metadata_complete=false`, `presentation_review.coverage_status="degraded"`, and non-empty degraded reasons instead of drifting back to sales `main_issue`, `next_goal`, `pass_flags`, or stage-summary language.

On the web side, the shared `/practice/{sessionId}/report` page now branches on `report.scenario_type`. For presentation sessions it renders the PPT-specific header, dimension cards, page summaries, coverage/issue diagnostics, recommendation lists, and degraded copy; it also skips the sales-only knowledge-check request and hides sales-only cards such as `销售推进结果`, `销售推进基线`, and `知识库命中检测`. Retry continuity remains on the same material line by carrying `presentation_id` back into the next `/practice/{newSessionId}` URL.

The closer turn re-proved the slice with fresh evidence rather than trusting task summaries. All slice-level automated commands passed again. Then a live local session was created on the real presentation runtime (`8531c7f6-50da-4934-9fd4-63784c791edf`) using the published presentation agent/persona pair plus the ready S07 verification deck (`750be5ad-41b6-4752-b772-b4fce6cb9c16`). The session was driven through the actual StepFun presentation websocket with control-start, real synthesized audio chunks for page 1, a live `page_change` to page 2, real synthesized audio chunks for page 2, and control-end. That produced a complete `presentation_review` with `page_metadata_complete=true`, two page summaries, `required_talking_points.status="complete"`, and presentation-preserving retry metadata. Finally, the shared browser report page rendered that exact session with PPT headings, page summaries, coverage diagnostics, the `按目标再练一轮` CTA, and no sales-only UI; the retry CTA also moved the browser to a new `/practice/{id}?scenario_type=presentation&...&presentation_id=750be5ad-41b6-4752-b772-b4fce6cb9c16` URL, preserving material continuity.

## Verification

Fresh slice-level verification passed:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_presentation_report_flow.py -k degraded`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

Fresh operational / diagnostics proof passed:

- Live API check on a fresh runtime session `8531c7f6-50da-4934-9fd4-63784c791edf` returned `scenario_type="presentation"`, `overall_score=80.5`, `page_metadata_complete=true`, `page_summaries_count=2`, `required_talking_points.status="complete"`, and `retry_entry.presentation_id="750be5ad-41b6-4752-b772-b4fce6cb9c16"`.
- Live API check on historical degraded session `ec5b7b03-a83a-4ee6-bc33-d768ccfec610` returned `scenario_type="presentation"`, `page_summaries_status="degraded"`, `required_status="degraded"`, non-empty `degraded_reasons=["missing_page_metadata"]`, and `main_issue=null` / `next_goal=null`.
- Browser verification on `http://localhost:3445/practice/8531c7f6-50da-4934-9fd4-63784c791edf/report` passed explicit assertions for `PPT 复盘报告`, `PPT 表达能力总览`, `逐页总结`, `要点覆盖与表达诊断`, `按目标再练一轮`, both page-summary bodies, `2 / 3 已覆盖`, and `页级证据完整`; targeted browser searches also confirmed `销售推进结果`, `销售推进基线`, and `知识库命中检测` were absent.
- Browser retry continuity was rechecked indirectly but live: after clicking `按目标再练一轮`, the session moved onto a new presentation practice URL (`/practice/69718633-7db3-437d-ad84-a4e224c74b44?...&presentation_id=750be5ad-41b6-4752-b772-b4fce6cb9c16`).

## Requirements Advanced

- R011 — S07 extended the unified evidence line into the presentation scenario as well, so the canonical `/practice/{sessionId}/report` route now carries PPT review facts and degraded completeness instead of leaving presentation evidence on a separate truth surface.

## Requirements Validated

- R008 — Fresh backend suites, live happy/degraded report API checks, a fresh audio-driven page-turn runtime session, and browser verification together proved that a learner can now finish a PPT practice and receive a usable post-session review grounded in real page/material evidence from the shared report entrypoint.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The live runtime proof used synthesized speech chunks over the real presentation websocket instead of a manual browser-microphone run. That was a verification-method deviation, not a product-scope change: it still exercised the actual audio/transcription path, `page_change` handling, evidence persistence, report generation, and shared report rendering while avoiding an agent-harness limitation around speaking into the browser.

## Known Limitations

- The StepFun presentation websocket `type:"text"` shortcut can still finish a session but does not prove page-number persistence; it lands in a degraded `missing_page_metadata` report. The product’s real audio path is now proven, but this shortcut remains a misleading local verification path.
- Optional enhanced layers (`/evaluation/sessions/{id}/report`, `/sessions/{id}/highlights`) still sit on top of the canonical contract. They rendered cleanly in the happy-path browser session here, but S08 still needs milestone-level observability closure for those optional layers and other local-runtime failure modes.
- Release-level proof across the full milestone remains open. S07 proves PPT postmortem usability, not final launch readiness.

## Follow-ups

- S08 should reuse the live S07 verification recipe — same host alignment, fresh presentation session creation, websocket audio/page-turn flow, happy/degraded report checks, and browser assertions — as part of milestone-level release UAT.
- Convert the synthesized-audio websocket probe used here into a reusable verification asset so future agents can reproduce a complete PPT runtime session without rediscovering the host/cookie and `type:"text"` pitfalls.

## Files Created/Modified

- `backend/src/presentation_coach/services/presentation_report_service.py` — now owns the normalized `presentation_review` payload and explicit degraded diagnostics for page-aware PPT postmortems.
- `backend/src/presentation_coach/websocket/presentation_handler.py` — forwards legacy `current_page` into `transcript_metadata.page_number` on the existing message-analysis persistence path.
- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` — remains the live StepFun runtime used for fresh S07 audio/page-turn verification.
- `backend/src/common/conversation/session_evidence.py` — injects `presentation_review` into the shared scenario-aware evidence projection and surfaces presentation completeness diagnostics.
- `backend/src/common/db/schemas.py` — extends the canonical session report contract with `scenario_type` and `presentation_review`.
- `backend/src/common/api/practice.py` — makes `/practice/sessions/{id}/report` the authoritative presentation-aware report route.
- `backend/tests/contract/test_presentation_report_contract.py` — locks happy-path and degraded presentation contract behavior on the shared report route.
- `backend/tests/integration/test_presentation_report_flow.py` — proves the shared report route reuses `PresentationReportService` and keeps degraded presentation payloads presentation-shaped.
- `web/src/lib/api/types.ts` — carries the scenario-aware presentation contract used by the shared report page.
- `web/src/lib/session-evidence.ts` — formats presentation degraded reasons and issue labels for the report UI.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — renders the PPT branch, skips knowledge-check for presentation sessions, and keeps presentation retry continuity.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — covers PPT rendering, degraded presentation copy, and retry continuity without reintroducing sales-only blocks.
- `.gsd/REQUIREMENTS.md` — marked R008 validated and recorded S07’s reinforcement of R011.
- `.gsd/KNOWLEDGE.md` — recorded the localhost/127 cookie pitfall and the misleading StepFun `type:"text"` shortcut for S07 runtime proof.
- `.gsd/PROJECT.md` — refreshed current state to include shipped PPT postmortem capability and the new remaining S08 risk.
- `.gsd/milestones/M001/M001-ROADMAP.md` — marked S07 complete.
- `.gsd/milestones/M001/slices/S07/S07-SUMMARY.md` — recorded slice-level outcome, verification, and forward guidance.
- `.gsd/milestones/M001/slices/S07/S07-UAT.md` — captured the tailored S07 UAT flow.

## Forward Intelligence

### What the next slice should know
- The canonical PPT postmortem path is now `/api/v1/practice/sessions/{id}/report` + `/practice/{sessionId}/report`. If S08 adds more diagnostics or release checks, extend this single route/page pair instead of reviving `/evaluation/.../report` as a second authority.

### What's fragile
- Local runtime/browser proof is fragile if frontend and backend mix `localhost` with `127.0.0.1`, or if the verifier uses the websocket `type:"text"` shortcut instead of real audio. Both failure modes look like product regressions even when the shipped report contract is correct.

### Authoritative diagnostics
- Start with `GET /api/v1/practice/sessions/{id}/report`, then `practice_session_evidence_projection_built` / `practice_session_report_built`, then the focused contract/integration tests. Those surfaces come from the same shared report/evidence path the product now uses for both happy and degraded presentation sessions.

### What assumptions changed
- We started S07 with the implicit assumption that any completed presentation session on the live websocket path would be enough to prove page-aware review. That turned out to be false: the StepFun `type:"text"` shortcut can complete a session while still dropping page metadata, so only the real audio/transcription path actually proves the slice goal.

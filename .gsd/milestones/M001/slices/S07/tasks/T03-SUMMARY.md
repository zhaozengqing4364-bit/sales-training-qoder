---
id: T03
parent: S07
milestone: M001
provides:
  - Scenario-aware shared report page rendering for presentation sessions, including canonical PPT review cards, degraded copy, and retry continuity on the same presentation.
key_files:
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/lib/session-evidence.ts
  - .gsd/milestones/M001/slices/S07/S07-PLAN.md
key_decisions:
  - The shared report page now gates sales-only sections and knowledge-check loading strictly on `report.scenario_type`, so presentation sessions never infer UI state from missing sales fields.
patterns_established:
  - Presentation report UI reads `report.presentation_review` as the canonical baseline, renders page summaries / coverage / issue diagnostics directly, and keeps retry CTA on the presentation baseline card instead of waiting for a sales-style `next_goal`.
observability_surfaces:
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - browser network logs on `/practice/{sessionId}/report` should show no `/knowledge-check` request for presentation sessions
  - `GET /api/v1/practice/sessions/{id}/report`
duration: 2h
verification_result: partial
completed_at: 2026-03-24T11:38:46+08:00
blocker_discovered: false
---

# T03: 让共享 report page 按 scenario_type 渲染 PPT 会后复盘

**Scenario-aware shared report pages now render canonical PPT postmortems, skip presentation knowledge-check noise, and keep retry tied to the same presentation.**

## What Happened

I started with the red phase in `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`. The new assertions lock the two presentation paths the task plan asked for: a happy-path presentation report that shows six PPT dimensions, per-page summaries, coverage / forbidden / missing diagnostics, no sales-only sections, no knowledge-check request, and retry continuity via `presentation_id`; plus a degraded historical path that still stays presentation-shaped and shows presentation-specific degraded copy instead of falling back to sales UI.

Then I changed `web/src/app/(user)/practice/[sessionId]/report/page.tsx` with the smallest scenario-aware branch that makes those tests pass. The page now waits for the unified report before loading optional layers, skips `getKnowledgeCheck(sessionId)` entirely when `report.scenario_type === "presentation"`, and logs that skip explicitly. Presentation sessions now render their own baseline cards: a PPT-specific hero copy, six-dimension score cards sourced from `report.presentation_review.dimension_scores`, a `逐页总结` section driven by `page_summaries`, and a `要点覆盖与表达诊断` section driven by `required_talking_points` plus `issue_counts`. Sales-only sections (`销售推进结果` / `下一轮销售目标` / `销售推进基线` / `知识库命中检测`) are now explicitly gated off for presentation sessions instead of leaking through because fields happen to be null.

I added small presentation helpers in `web/src/lib/session-evidence.ts` so the degraded copy and issue labels come from one place. That powers the page-level degraded path: when page metadata is missing, the UI shows `当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。` and a `逐页总结暂不可用` state, while still preserving the retry CTA on the presentation baseline card. I also made the enhanced-report fallback copy scenario-aware, so presentation users now see that the page is still showing the canonical PPT review even if enhanced insights are unavailable.

## Verification

The focused web regression suite passed fresh after the report-page and helper edits. I also validated the live shared report API against locally seeded completed presentation sessions: one clean happy-path session and one degraded historical session with missing page metadata. Both return `scenario_type="presentation"`, canonical `presentation_review`, no top-level sales `main_issue` / `next_goal`, and retry continuity via the same `presentation_id`.

I partially attempted the browser/UAT proof on a fresh local backend (`:3444`) and a fresh local web dev server (`:3445`). The pre-existing process on `:3000` was serving stale unrelated assets, so I deliberately avoided using it. The remaining gap is browser auth: a browser-side `dev-login` fetch succeeded, but the report-page navigation on `:3445` still hit `401 Not authenticated`, so I could not complete the visual happy/degraded report-page walkthrough before the timeout. That is a local-runtime auth/session issue, not a plan-invalidating blocker for the T03 code path.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 0.81s |
| 2 | `TOKEN=$(curl -s -X POST http://127.0.0.1:3444/api/v1/auth/dev-login | jq -r '.data.access_token'); for SESSION in 8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b ec5b7b03-a83a-4ee6-bc33-d768ccfec610; do curl -s http://127.0.0.1:3444/api/v1/practice/sessions/$SESSION/report -H "Authorization: Bearer $TOKEN" | jq -c '{success,error,scenario_type:.data.scenario_type,overall_score:.data.overall_score,page_summaries:(.data.presentation_review.page_summaries|length),required_status:.data.presentation_review.required_talking_points.status,degraded_reasons:.data.presentation_review.diagnostics.degraded_reasons,main_issue:.data.main_issue,next_goal:.data.next_goal,retry_entry:.data.retry_entry}'; done` | 0 | ✅ pass | n/a |
| 3 | `Browser UAT — fresh web dev server on http://127.0.0.1:3445 plus browser-side POST http://127.0.0.1:3444/api/v1/auth/dev-login, then navigate to /practice/8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b/report` | n/a | ❌ fail | n/a |

## Diagnostics

- Inspect `web/src/app/(user)/practice/[sessionId]/report/page.tsx` for the `scenario_type === "presentation"` branch and the `Knowledge-check skipped for presentation scenario` debug log.
- Inspect `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` for the happy-path presentation branch, degraded copy branch, no-knowledge-check assertion, and retry `presentation_id` continuity proof.
- Inspect `web/src/lib/session-evidence.ts` for the presentation degraded-copy and issue-label helpers.
- API sanity checks from this run:
  - Happy-path seeded session: `8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b`
  - Degraded seeded session: `ec5b7b03-a83a-4ee6-bc33-d768ccfec610`
  - Shared presentation seed deck: `750be5ad-41b6-4752-b772-b4fce6cb9c16`
- For live browser follow-up, use the fresh dev server on `http://127.0.0.1:3445`, not the stale process on `:3000`.

## Deviations

- The pre-flight plan fix added an explicit diagnostics/failure-path verification line to `S07-PLAN.md` instead of leaving degraded-path proof implicit.
- For runtime validation I seeded two clean completed presentation sessions directly into the live local DB because the pre-existing local presentation sessions returned `[SESSION_EVIDENCE_FAILED]` and were not usable as report-page UAT fixtures.
- I used a fresh local web dev server on `:3445` for UAT because the existing process on `:3000` served stale unrelated assets and 404’d its `_next/static/*` bundle.

## Known Issues

- Browser-side auth on the fresh `:3445` web server is still incomplete for this task: a browser `dev-login` POST succeeds, but subsequent report-page navigation still fetches `/api/v1/practice/sessions/{id}/report` as unauthenticated and returns `401 Not authenticated`.
- Pre-existing local historical presentation sessions `ec1ebcaf-5071-4b13-96ce-78e25113419b` and `3358d497-824b-4f43-bb84-2036f75d21b4` return `[SESSION_EVIDENCE_FAILED]` on the shared report route. I did not debug that further in this task because the seeded happy/degraded sessions were enough to verify the new presentation contract path.

## Files Created/Modified

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — added the `scenario_type` presentation branch, skipped presentation knowledge-check requests, rendered PPT review/page-summary/diagnostic sections, and kept retry on the presentation baseline card.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — added happy-path presentation assertions, degraded presentation assertions, no-knowledge-check coverage, and retry `presentation_id` continuity checks.
- `web/src/lib/session-evidence.ts` — added presentation degraded-copy and issue-label helpers used by the shared report page.
- `.gsd/milestones/M001/slices/S07/S07-PLAN.md` — added the explicit diagnostics/failure-path verification step and will be updated with the completed T03 checkbox.
- `.gsd/milestones/M001/slices/S07/tasks/T03-SUMMARY.md` — recorded this task’s implementation, verification evidence, and the remaining browser-auth UAT gap.

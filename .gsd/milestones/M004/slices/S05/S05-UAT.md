# S05: sales + PPT 学习闭环终验 — UAT

**Milestone:** M004
**Written:** 2026-03-26T05:08:00Z

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: T02 captured the live sales `history -> report -> replay -> retry` loop on the shipped learner routes. T03 adds the live PPT half on the same shared `/practice/{sessionId}/report` + `/practice/{sessionId}/replay` family, plus a real degraded PPT proof when page metadata is missing. Together they prove the current user-facing review loop for both scenario types without inventing a parallel acceptance harness.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- Frontend and backend must use the same loopback host (`localhost` with `localhost`). Using `127.0.0.1` for the page while the web client still points at `localhost:3444` breaks the client-side auth fetches and lands the browser on `/login`.
- Browser session is authenticated through `POST /api/v1/auth/dev-login`.
- Current history data still contains the completed sales session `6aff04f9-a09e-4956-8abc-07251c597a8f` (`语言的魅力` / `挑剔型客户`).
- Current history data still contains the completed PPT session `8531c7f6-50da-4934-9fd4-63784c791edf` (`S07 presentation report seed dd32398d`) with complete page evidence.
- Current history and report data still contain the degraded PPT session `c6f66bdc-26ca-487a-8f58-5dd7f61934f4` with `missing_page_metadata` degradation.
- Evidence packs from these runs exist under `.artifacts/m004-s05-t02/` and `.artifacts/m004-s05-t03/`.

## Smoke Test

1. Open `http://localhost:3445/history` after dev-login.
2. For the completed sales session `6aff04f9-a09e-4956-8abc-07251c597a8f`, open report, jump to replay, and launch a focused retry.
3. For the completed PPT session `8531c7f6-50da-4934-9fd4-63784c791edf`, open report, return to the same history row, open replay, review page 2 evidence, and launch a PPT retry.
4. Open degraded PPT session `c6f66bdc-26ca-487a-8f58-5dd7f61934f4` on both report and replay.
5. **Expected:** both scenario types stay on the shared learner route family, each retry stays scoped to the original training configuration, and degraded PPT routes explain missing page evidence in plain language instead of falling back to sales copy or blank states.

## Test Cases

### 1. History route keeps the usable completed sales loop visible even with newer non-completed sessions above it

1. Open `http://localhost:3445/history` in an authenticated browser session.
2. Locate the completed sales session `6aff04f9-a09e-4956-8abc-07251c597a8f` in the current list.
3. Compare it with the newer `scoring` sales rows that appear above it.
4. **Expected:** the completed row still exposes `回放` and `报告` links on the shared `/practice/{sessionId}/...` route family, while newer non-completed rows remain understandable as `进行中` / `综合洞察待生成` instead of hiding the usable finished review path.

### 2. Report route shows the canonical sales conclusion and the focused retry affordance

1. Open `http://localhost:3445/practice/6aff04f9-a09e-4956-8abc-07251c597a8f/report` from the history row.
2. Review the visible conclusion cards and retry actions.
3. Cross-check the same session with `GET /api/v1/practice/sessions/6aff04f9-a09e-4956-8abc-07251c597a8f/report`.
4. **Expected:** the page renders `训练评估报告`, exposes the sales evidence verdict `证据待补齐`, shows the main issue `产品价值已经说到客户收益，但 ROI 证据还不够硬。`, and offers both `定位问题片段` and `按目标再练一轮`. The API should agree on `overall_score=74.67`, `main_issue.issue_type=roi_evidence_gap`, and a non-null `retry_entry.focus_intent`.

### 3. Replay deep-link explains the missing-highlight fallback instead of dropping the learner on an ambiguous replay state

1. On the report page, click `定位问题片段`.
2. Wait for the browser to land on the replay URL generated from the report anchor.
3. Inspect the replay banner and the anchored conversation turn.
4. Cross-check the same session with `GET /api/v1/sessions/6aff04f9-a09e-4956-8abc-07251c597a8f/replay` and `GET /api/v1/sessions/6aff04f9-a09e-4956-8abc-07251c597a8f/highlights`.
5. **Expected:** the replay URL includes `focus=main_issue`, `anchor_status=degraded`, `anchor_reason=no_matching_highlight`, `turn=3`, and the stage marker timestamp. The page must render `已定位到主问题片段` plus `未找到精确高光，已定位到“促成成交”阶段附近的第 3 轮。`, keep the referenced user turn `如果价格更高，你怎么说服我继续推进？` visible, and remain usable even though `highlights` is empty.

### 4. Focused retry launches on the current practice route family with the preserved sales focus intent

1. From replay, click `按目标再练一轮`.
2. Wait for the new practice route to open.
3. Inspect the browser URL and the create-session response.
4. **Expected:** the browser lands on a new route in the same family, `http://localhost:3445/practice/{newSessionId}?scenario_type=sales&agent_id=dee4a877-2f19-47f4-a326-954f2ab554d5&persona_id=5ff0c27e-ea3d-4f4a-9cfe-eae1946feff2`, and the create-session payload preserves the original report focus intent from source session `6aff04f9-a09e-4956-8abc-07251c597a8f`.

### 5. History keeps the completed PPT row on the same shared replay/report route family

1. Open `http://localhost:3445/history` in the authenticated browser session.
2. Locate the completed PPT session `8531c7f6-50da-4934-9fd4-63784c791edf`.
3. Inspect the row actions.
4. **Expected:** the completed PPT row exposes both `回放` and `报告` links on `/practice/8531c7f6-50da-4934-9fd4-63784c791edf/replay` and `/practice/8531c7f6-50da-4934-9fd4-63784c791edf/report`, even while newer in-progress PPT rows remain above it.

### 6. Report route shows the canonical PPT review baseline and the page-level issue cluster

1. Open `http://localhost:3445/practice/8531c7f6-50da-4934-9fd4-63784c791edf/report`.
2. Review the PPT baseline cards, page summaries, and retry affordance.
3. Cross-check the same session with `GET /api/v1/practice/sessions/8531c7f6-50da-4934-9fd4-63784c791edf/report`.
4. **Expected:** the page renders `PPT 复盘报告`, `页级证据完整`, `PPT 表达能力总览`, and `页级问题簇总览`; page 2 shows `第 2 页仍缺少 1 个必讲点，需要补齐再进入下一页。` with evidence `未覆盖：ROI结果`; and the page offers `按目标再练一轮`. The API should agree on `overall_score=80.5`, `presentation_review.coverage_status=complete`, `diagnostics.total_pages=2`, `diagnostics.page_issue_cluster_count=1`, and `retry_entry.presentation_id=750be5ad-41b6-4752-b772-b4fce6cb9c16`.

### 7. Replay route lets the learner inspect page evidence and relaunch the same PPT configuration

1. From the same completed history row, open `http://localhost:3445/practice/8531c7f6-50da-4934-9fd4-63784c791edf/replay`.
2. On replay, switch to page 2.
3. Inspect the page 2 summary and issue cluster, then click `定位到第 2 轮`.
4. Click `按目标再练一轮`.
5. Cross-check the same session with `GET /api/v1/sessions/8531c7f6-50da-4934-9fd4-63784c791edf/replay`.
6. **Expected:** replay renders `PPT 回放` and `PPT 页级问题定位`; page 2 shows `第 2 页有讲解记录，建议补充更明确的关键点表达。`, `仍待补充：ROI结果`, and `第 2 页仍缺少 1 个必讲点，需要补齐再进入下一页。`; jumping to turn 2 keeps the source user turn `第二页补充模拟结果和客户案例，说明上线后转化率提升和交付周期缩短。` visible; and retry opens a new route in the same family, `http://localhost:3445/practice/{newSessionId}?scenario_type=presentation&agent_id=7199854c-3921-4d9f-9833-fe99ca209c59&persona_id=4c99d4d0-965b-439b-b746-33d2e1c55073&presentation_id=750be5ad-41b6-4752-b772-b4fce6cb9c16`.

### 8. Missing page metadata stays understandable on both PPT report and PPT replay

1. Open `http://localhost:3445/practice/c6f66bdc-26ca-487a-8f58-5dd7f61934f4/report`.
2. Review the PPT report baseline and empty page-summary area.
3. Open `http://localhost:3445/practice/c6f66bdc-26ca-487a-8f58-5dd7f61934f4/replay`.
4. Inspect the replay fallback copy.
5. Cross-check the same session with `GET /api/v1/practice/sessions/c6f66bdc-26ca-487a-8f58-5dd7f61934f4/report` and `GET /api/v1/sessions/c6f66bdc-26ca-487a-8f58-5dd7f61934f4/replay`.
6. **Expected:** report renders `页级证据降级` and `逐页总结暂不可用`, replay renders `当前页暂无逐页摘要`, and both routes explain the degradation with `当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。` instead of falling back to sales wording or a blank page.

## Edge Cases

### PPT report currently proves review + retry, while replay remains a sibling learner route

1. Open the completed PPT report `http://localhost:3445/practice/8531c7f6-50da-4934-9fd4-63784c791edf/report`.
2. Inspect the visible actions.
3. Compare with the same row on `/history`.
4. **Expected:** current PPT report keeps `按目标再练一轮`, but does not expose a sales-style `定位问题片段` CTA. Replay remains reachable through the sibling `/practice/{sessionId}/replay` route already exposed on the shared history row. Treat that as the current shipped contract, not as a browser-test failure.

### Newer in-progress PPT rows do not block review of older completed PPT evidence

1. Open `/history` and observe the newer in-progress PPT rows above the completed seed session.
2. Then open the older completed row `8531c7f6-50da-4934-9fd4-63784c791edf`.
3. **Expected:** the presence of unfinished PPT sessions does not remove or corrupt the completed row’s report/replay/retry path.

## Failure Signals

- `/history` redirects back to `/login` even after dev-login on the same loopback host.
- The completed PPT row loses either the `报告` or `回放` route.
- The PPT report route falls back to sales headings or loses the page-2 issue-cluster evidence for session `8531c7f6-50da-4934-9fd4-63784c791edf`.
- PPT replay stops showing the page 2 summary / issue cluster / turn-jump evidence on the shared route.
- PPT retry stops preserving `scenario_type=presentation` or drops the original `presentation_id` from the new practice URL.
- The degraded PPT session stops explaining `missing_page_metadata` in plain language and instead shows a blank state, generic error, or sales-oriented copy.

## Requirements Proved By This UAT

- none — this revision closes the slice’s route proof, but requirement IDs are tracked at slice completion rather than in task-level UAT.

## Not Proven By This UAT

- A fresh microphone-driven same-session PPT capture; this task proves the current learner review loop on completed sessions and shared review routes.
- A direct PPT report-to-replay CTA; the shipped UI currently exposes replay from the shared history row while the PPT report route exposes retry only.
- Thumbnail-generation fidelity under missing `python-pptx` / `Pillow`; this route proof only confirms that persisted PPT evidence and retry remain usable on the shipped learner routes.

## Notes for Tester

- Browser evidence from the sales run lives in:
  - `.artifacts/m004-s05-t02/history.png`
  - `.artifacts/m004-s05-t02/report.png`
  - `.artifacts/m004-s05-t02/replay.png`
  - `.artifacts/m004-s05-t02/retry.png`
  - `.artifacts/m004-s05-t02/summary.json`
- The replay URL captured in the sales run was:
  - `http://localhost:3445/practice/6aff04f9-a09e-4956-8abc-07251c597a8f/replay?focus=main_issue&message_id=a5c1094d-d365-4da9-9210-f8e9671d1252&turn=3&anchor_status=degraded&anchor_reason=no_matching_highlight&marker_type=stage_change&marker_timestamp_ms=3900`
- The focused sales retry launched as new session `d4083a3f-2ec9-4154-93c0-242a0ce1f010` during the proof run documented in T02.
- Browser evidence from the PPT run lives in:
  - `.artifacts/m004-s05-t03/history.png`
  - `.artifacts/m004-s05-t03/report.png`
  - `.artifacts/m004-s05-t03/replay.png`
  - `.artifacts/m004-s05-t03/retry.png`
  - `.artifacts/m004-s05-t03/degraded-report.png`
  - `.artifacts/m004-s05-t03/degraded-replay.png`
  - `.artifacts/m004-s05-t03/summary.json`
- The PPT report proof used completed session `8531c7f6-50da-4934-9fd4-63784c791edf`; the degraded proof used `c6f66bdc-26ca-487a-8f58-5dd7f61934f4`.
- The PPT retry launched as new session `7da690a1-d52b-427a-8966-f7fe501158f9` during this proof run.
- This run also confirmed `reportHasReplayCta=false` for the current PPT report UI: replay remains a sibling history entrypoint, while retry stays available directly on report and replay.

# S05: sales + PPT 学习闭环终验 — UAT

**Milestone:** M004
**Written:** 2026-03-26T04:46:00Z

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: T02 only needs the current sales review loop on shipped user routes, so this revision proves the real `history -> report -> replay -> retry` chain in a browser and cross-checks the same session on the live APIs. PPT proof is still pending in T03.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- Frontend and backend must use the same loopback host (`localhost` with `localhost`). Using `127.0.0.1` for the page while the web client still points at `localhost:3444` breaks the client-side auth fetches and lands the browser on `/login`.
- Browser session is authenticated through `POST /api/v1/auth/dev-login`.
- Current history data still contains the completed sales session `6aff04f9-a09e-4956-8abc-07251c597a8f` (`语言的魅力` / `挑剔型客户`).
- Evidence pack from this run exists under `.artifacts/m004-s05-t02/`.

## Smoke Test

1. Open `http://localhost:3445/history` after dev-login.
2. Open the completed sales session `6aff04f9-a09e-4956-8abc-07251c597a8f` from the current history list.
3. From the report page, click `定位问题片段` to enter replay.
4. From replay, click `按目标再练一轮`.
5. **Expected:** the user stays on the current review route family the whole way, sees a truthful sales conclusion, gets an explicit degraded replay-anchor explanation when no exact highlight exists, and lands on a new retry practice route carrying the original focus intent.

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

## Edge Cases

### Missing exact highlight still produces a readable replay anchor

1. Use the report-generated `main_issue` replay link for session `6aff04f9-a09e-4956-8abc-07251c597a8f`.
2. Inspect the replay request and banner text.
3. **Expected:** when `replay.main_issue.replay_anchor.status=degraded` and `degraded_reason=no_matching_highlight`, replay falls back to the stage-change marker (`促成成交`) and explains that fallback in plain language rather than showing a blank state or a generic error.

### Newer scoring rows do not block review of older completed sales evidence

1. Open `/history` and observe the newest sales rows (`ef48ed80-0bfa-4a47-82c7-228ac3d468d2`, `9f8710f1-c77e-4e73-bcbe-eac9561efbe0`).
2. Then open the older completed row `6aff04f9-a09e-4956-8abc-07251c597a8f`.
3. **Expected:** the presence of unfinished sessions does not remove or corrupt the completed row’s report/replay/retry path.

## Failure Signals

- `/history` redirects back to `/login` even after dev-login on the same loopback host.
- The completed sales row loses either the `报告` or `回放` route.
- The report page stops showing the canonical sales issue/goal line for session `6aff04f9-a09e-4956-8abc-07251c597a8f`.
- `定位问题片段` stops producing a replay URL with an explicit degraded anchor explanation when no exact highlight exists.
- Replay falls into a blank/ambiguous state instead of showing the stage-fallback banner.
- `按目标再练一轮` no longer creates a new sales practice route with the source session’s focus intent.

## Requirements Proved By This UAT

- none — this revision proves the sales half of S05 only; slice-level requirement closure still depends on the PPT proof in T03.

## Not Proven By This UAT

- The PPT report/replay/retry route family; that remains for T03.
- A fresh microphone-driven same-session sales runtime capture; this task proves the current learner review loop on `history -> report -> replay -> retry` using a real completed session.
- Any guarantee that the newest `scoring` sales rows will finalize into completed replay/highlight data without further runtime work.

## Notes for Tester

- Browser evidence from this run lives in:
  - `.artifacts/m004-s05-t02/history.png`
  - `.artifacts/m004-s05-t02/report.png`
  - `.artifacts/m004-s05-t02/replay.png`
  - `.artifacts/m004-s05-t02/retry.png`
  - `.artifacts/m004-s05-t02/summary.json`
- The replay URL captured in this run was:
  - `http://localhost:3445/practice/6aff04f9-a09e-4956-8abc-07251c597a8f/replay?focus=main_issue&message_id=a5c1094d-d365-4da9-9210-f8e9671d1252&turn=3&anchor_status=degraded&anchor_reason=no_matching_highlight&marker_type=stage_change&marker_timestamp_ms=3900`
- The focused retry launched as new session `d4083a3f-2ec9-4154-93c0-242a0ce1f010` during this proof run.

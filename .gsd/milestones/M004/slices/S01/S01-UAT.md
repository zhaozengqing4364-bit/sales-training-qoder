# S01: 当前 report/replay/highlight 入口的学习证据 contract — UAT

**Milestone:** M004
**Written:** 2026-03-25T16:15:19.810Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice only changes the completed-session read-side contract and the existing replay/report/history/highlight renderers. Focused backend and web tests exercise the real authority line and the required degraded states without depending on a fresh live runtime session.

## Preconditions

- Backend dependencies are installed and backend focused tests can run under `backend/venv`.
- Web dependencies are installed and Vitest can run under `web/`.
- Run commands from the repo root, but keep the `cd backend` / `cd web` prefixes exactly as written.
- Use quoted Next.js literal paths when invoking the web tests.

## Smoke Test

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py`.
2. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'`.
3. **Expected:** The backend exposes nested `learning_evidence` on the current replay/highlight APIs, and the existing replay/highlight surfaces render that richer evidence without adding a new page.

## Test Cases

### 1. Replay/highlight backend contract exposes explanation-rich evidence on the existing authority line

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py`.
2. Confirm the focused cases covering `learning_evidence` attachment and replay/highlight API serialization pass.
3. **Expected:** Replay/highlights responses include `learning_evidence.reason`, `issue_family`, `stage`, `nearby_context`, `suggested_response`, `linked_issue`, and `linked_goal`, while flat compatibility fields like `stage_name`, `context`, and `suggested_response` remain available to current consumers.

### 2. Replay page renders session-level conclusion and per-turn learning evidence without stitching a second truth line

1. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`.
2. Review the passing replay test fixture, which supplies canonical `getReplay` data plus a conflicting `/messages` payload.
3. **Expected:** The replay page renders the canonical main issue / next goal / claim-truth / evaluable state from `getReplay`, enriches highlights from the same contract, and does not fall back to a second stitched message source.

### 3. Highlight cards and detail modal explain why the turn matters and how to improve it

1. Run `cd web && npm test -- --run 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'`.
2. Confirm the focused highlight fixtures render issue-family labels, linked goal text, linked issue text, nearby context, and better-response copy.
3. **Expected:** The existing highlight card and modal surfaces show why the turn matters, which stage it belongs to, what issue family it belongs to, what the next goal is, and what a better response looks like.

### 4. Report and history keep the same learning vocabulary when optional enhancements degrade

1. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`.
2. Confirm the passing cases for not-evaluable sessions, failed analytics snapshots, and unavailable highlights / enhanced report data.
3. **Expected:** Report and history still surface shared issue/goal learning cues derived from the unified session evidence contract, and degraded states stay explicit instead of collapsing into generic pending/loading copy.

## Edge Cases

### Highlights API unavailable

1. Use the replay/report focused tests where `getHighlights` rejects.
2. **Expected:** Replay/report stay readable from canonical session evidence and show an inline availability hint instead of failing the whole page.

### No highlights returned

1. Run the `HighlightList` empty-state test.
2. **Expected:** The current highlight surface stays clean (`暂无高光片段`) and does not invent placeholder learning content.

### Session not evaluable

1. Run the report/history focused tests with `evaluable=false` and `not_evaluable_reason='INSUFFICIENT_TURN_DATA'`.
2. **Expected:** Current entrypoints explain that evidence is insufficient and keep the rest of the completed-session projection readable instead of collapsing to a generic pending state.

## Failure Signals

- Backend replay/highlights tests fail because `learning_evidence` or flat compatibility fields disappear from the serialized response.
- Replay page starts preferring stitched `/messages` data over canonical `getReplay`.
- Highlight card/modal lose issue/stage/goal/context/suggested-response copy.
- Report/history vocabulary drifts away from replay/highlight wording or hides degradation behind generic loading/pending text.
- Service code builds the new payload but clients cannot see it because `backend/src/common/conversation/schemas.py` trimmed the fields.

## Requirements Proved By This UAT

- R011 — The current replay/highlight/report/history entrypoints now preserve and render one explanation-rich session-evidence contract for learning review without adding a new learning page or second evaluator.

## Not Proven By This UAT

- Report → replay deep links to the exact anchor turn/page.
- Retry/bootstrap flows driven from `issue_family` or `linked_goal`.
- PPT page-level learning evidence.
- Live runtime same-session proof; this UAT only proves the completed-session read-side contract and its degraded states.

## Notes for Tester

- Quote Next.js literal paths exactly when running the Vitest commands.
- The richer replay/highlight contract still sits behind the existing completed-session replay gate; this slice does not bypass `SESSION_NOT_COMPLETED` behavior.
- Stage / issue / goal labels can appear both in the session-level conclusion card and in per-turn learning cards; that duplication is intentional, not a regression.

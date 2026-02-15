# task-4-audit-009-014.md

RUN_ID: 20260213T134317Z

## AUDIT-009
- verdict: FAIL
- passes: false
- confidence: medium
- command: `grep -n "controlLifecycle" "web/src/app/(user)/practice/[sessionId]/page.tsx"; python3 test_websocket.py; python3 test_websocket_detailed.py`
- code_refs: web/src/app/(user)/practice/[sessionId]/page.tsx, backend/src/common/api/practice.py, .agent/evidence/20260213T134317Z/task-8-ws-smoke.log, .agent/evidence/20260213T134317Z/task-8-ws-detailed.log, .agent/evidence/20260213T134317Z/task-9-contract-drift.md
- db_refs: practice_sessions, conversation_messages, interruption_events
- expected: Session lifecycle actions and WS validation should reject invalid session and maintain stable flow.
- actual: WS smoke logs invalid-session rejection failure; detailed WS script terminates with AttributeError after SESSION_NOT_STARTED sequence. Task-9 drift check flags session top-level runtime profile naming drift risk and getSession typing drift.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path
- unblock_condition: Ensure invalid session rejection and repair `test_websocket_detailed.py` script stability; rerun smoke+detailed WS suites.

## AUDIT-010
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getReplay" "web/src/app/(user)/practice/[sessionId]/replay/page.tsx"; grep -n "/replay" "backend/src/common/conversation/api.py"`
- code_refs: web/src/app/(user)/practice/[sessionId]/replay/page.tsx, backend/src/common/conversation/api.py, backend/src/common/conversation/replay.py
- db_refs: conversation_messages, practice_sessions
- expected: Replay controls map to replay/messages/highlights APIs with persisted conversation records.
- actual: Replay page calls replay/messages/highlights APIs and backend conversation API exposes corresponding routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-011
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getReport" "web/src/app/(user)/practice/[sessionId]/report/page.tsx"; grep -n "/practice/sessions/{session_id}/report" "backend/src/common/api/practice.py"`
- code_refs: web/src/app/(user)/practice/[sessionId]/report/page.tsx, backend/src/common/api/practice.py, .agent/evidence/20260213T134317Z/task-9-contract-drift.md
- db_refs: staged_evaluation_results, comprehensive_reports
- expected: Report page buttons map to report/knowledge/highlight/comprehensive report APIs.
- actual: Report page triggers report and comprehensive report APIs; backend exposes report and comprehensive-report routes. Task-9 drift check confirms report snapshot field compatibility while documenting top-level session naming drift.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-012
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getMyHistory" "web/src/app/(dashboard)/history/page.tsx"; grep -n "/practice/history" "backend/src/common/api/practice.py"`
- code_refs: web/src/app/(dashboard)/history/page.tsx, backend/src/common/api/practice.py, backend/src/common/api/dashboard.py
- db_refs: practice_sessions, scenarios
- expected: History list/statistics/trends remain aligned with session status/report status payload fields.
- actual: History page uses matching APIs and status fields; backend history response includes session/report status fields.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-013
- verdict: PASS
- passes: true
- confidence: high
- command: `grep -n "getPublicLeaderboard" "web/src/app/(dashboard)/leaderboard/page.tsx"; pytest tests/contract/test_analytics.py`
- code_refs: web/src/app/(dashboard)/leaderboard/page.tsx, backend/src/common/api/analytics.py, backend/tests/contract/test_analytics.py, .agent/evidence/20260213T134317Z/task-9-contract-drift.md
- db_refs: leaderboard_entries, users
- expected: Leaderboard filters map to API parameters and contract remains stable.
- actual: Leaderboard page forwards scenario/time filters; contract tests include leaderboard and my-rank routes. Task-9 drift check confirms leaderboard contract compatibility (rank/average_score/best_score).
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-014
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "updateProfile" "web/src/app/(dashboard)/profile/page.tsx"; grep -n "/auth/logout" "backend/src/common/auth/api.py"`
- code_refs: web/src/app/(dashboard)/profile/page.tsx, backend/src/common/api/users.py, backend/src/common/auth/api.py
- db_refs: users
- expected: Profile save/logout flow is wired end-to-end with user record updates and auth endpoint.
- actual: Profile page calls getMe/updateProfile/logout and backend exposes logout endpoint and user APIs.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path


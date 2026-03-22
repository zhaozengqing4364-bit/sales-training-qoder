# task-9-contract-drift.md

RUN_ID: 20260213T134317Z

| Drift Item | Status | Risk | Contract Refs | Code/Payload Refs | Evidence |
|---|---|---|---|---|---|
| Request `runtime_profile_id` to DB persistence mapping | PASS | low | `docs/api-contract/sessions.md` | `backend/src/common/db/schemas.py`, `backend/src/common/api/practice.py`, `backend/src/common/db/models.py` | request field exists, backend resolves/persists to `practice_sessions.voice_runtime_profile_id` |
| Session top-level field naming (`runtime_profile_id` vs `voice_runtime_profile_id`) | FAIL | medium-high | `docs/api-contract/sessions.md` | `backend/src/common/db/schemas.py`, `backend/src/common/api/practice.py`, `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts` | contract includes `voice_runtime_profile_id` while API serializes normalized `runtime_profile_id` and client bridges both |
| Voice policy snapshot reference field consistency (`runtime_profile_id`) | PASS | low | `docs/api-contract/replay.md`, `docs/api-contract/sessions.md` | `backend/src/common/db/voice_policy_snapshot.py`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` | snapshot field is consistently consumed as `runtime_profile_id` |
| `getSession` frontend typing compatibility | FAIL | medium | `docs/api-contract/sessions.md` | `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/page.tsx` | `getSession` caller relies on cast due shape mismatch against strongly-typed session runtime data |
| Leaderboard field compatibility (`rank`, `average_score`, `best_score`) | PASS | low | `docs/api-contract/analytics.md` | `backend/src/common/api/analytics.py`, `backend/src/common/analytics/leaderboard_service.py`, `web/src/lib/api/types.ts`, `backend/tests/contract/test_analytics.py` | contract and runtime fields align in current API + FE use |
| `/practice/history` item schema completeness in contract | BLOCKED | medium | `docs/api-contract/sessions.md` | `backend/src/common/api/practice.py`, `web/src/lib/api/client.ts` | contract lists endpoint but does not fully define item schema; full drift closure needs schema expansion |

## Roll-up
- PASS: 3
- FAIL: 2
- BLOCKED: 1

## Unblock Conditions
1. Canonicalize top-level session runtime profile naming across docs, backend serializer, and frontend types.
2. Split `getSession` client typing from history list `SessionItem` type.
3. Add explicit `/practice/history` response item schema in `docs/api-contract/sessions.md`.

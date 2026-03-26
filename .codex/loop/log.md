# Safe Grow Log

Append one entry per iteration:

- time
- mode
- item id
- files changed
- summary
- verification commands
- verification results
- success signal status
- rollback note

- time: 2026-03-23T02:10:18+08:00
  mode: stabilize
  item id: M001-S01-T02
  files changed:
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S01/S01-PLAN.md
    - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
  summary: Hooked Sales StepFun back into snapshot recovery, restored turn/session runtime continuity on reconnect, and deleted dirty snapshots on timeout/terminal exits.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py
    - cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"
    - cd web && npx vitest --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts
  verification results: passed; exact npm test slice command still fails before execution because the package script duplicates --run
  success signal status: reconnected payloads now restore minimal runtime state and reconnect flow reaches end with session_status=scoring while snapshots are cleared
  rollback note: revert StepFun handler snapshot integration if future work changes reconnect protocol; keep D010 boundary unless replacing it with a broader tested contract

- time: 2026-03-25T15:03:33+0800
  mode: stabilize
  item id: M003-S04-T03
  files changed:
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Learner report and replay now render the canonical claim-truth line from the completed-session evidence snapshot, with shared labels/explanations for unsupported, weak, pending, and verified sales claims.
  verification commands:
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
    - cd web && npx tsc --noEmit
  verification results: focused report/replay Vitest passed; repo-wide web typecheck still reports the pre-existing admin knowledge page error `api.reprocessKnowledgeDocument` missing in `src/app/admin/knowledge/[id]/page.tsx`, and no new type errors remained in the S04 files after the claim-truth parser fix
  success signal status: report and replay now expose the same canonical claim-truth vocabulary already used by realtime diagnostics without leaking kb-lock chain-failure copy into completed-session coaching surfaces
  rollback note: if a future contract version promotes claim-truth to a top-level field, keep report/replay on the completed-session projection line and migrate the shared frontend helper rather than reintroducing knowledge-check as the primary read surface

- time: 2026-03-23T02:35:20+08:00
  mode: stabilize
  item id: M001-S01-T03
  files changed:
    - web/package.json
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/message-handlers.test.ts
    - .gsd/DECISIONS.md
    - .gsd/completed-units.json
    - .gsd/milestones/M001/slices/S01/S01-PLAN.md
    - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
  summary: Practice page lifecycle now follows server status/reconnected/session_ended, end failures stay visible on the training page with retry/reconnect affordances, and report navigation waits for confirmed terminal status.
  verification commands:
    - cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"
    - cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts
    - browser verification: legacy sales session + backend-down failure injection confirmed end stays on /practice with retry UI; fresh legacy session confirmed end routes to /report after terminal transition
  verification results: passed
  success signal status: training-page end failures are no longer masked by report redirects, and lifecycle UI state is driven by server events instead of optimistic local writes
  rollback note: revert the T03 frontend lifecycle changes together if future work redefines websocket lifecycle contracts; keep D011 unless a new server-authoritative contract replaces it

- time: 2026-03-23T04:32:58+08:00
  mode: stabilize
  item id: M001-S02-T01
  files changed:
    - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
    - backend/src/sales_bot/websocket/components/message_persistence.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/src/common/api/practice.py
    - backend/tests/unit/test_stepfun_message_helpers.py
    - backend/tests/unit/test_stepfun_realtime_persistence.py
    - backend/tests/unit/test_sales_message_persistence.py
    - .gsd/DECISIONS.md
    - .gsd/completed-units.json
    - .gsd/milestones/M001/slices/S02/S02-PLAN.md
    - .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Stabilized StepFun sales evidence writes around canonical overall_score payloads, synced terminal session scores from runtime/message evidence, and turned zero-turn or thin-evidence endings into explicit not-evaluable facts instead of summary-failure terminal semantics.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_message_helpers.py -k patch_existing_message_analysis_returns_true_on_success -vv
    - cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py
    - cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
    - cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'
  verification results: focused T01 backend pytest passed; downstream slice verification commands for T02/T03/T04 currently fail because the referenced test files do not exist yet
  success signal status: StepFun sales sessions now persist canonical turn/session evidence and explicitly expose INSUFFICIENT_TURN_DATA instead of collapsing thin-evidence terminal paths into [SUMMARY_GENERATION_FAILED]
  rollback note: revert the T01 StepFun evidence normalization and terminal insufficiency handling together if a future slice replaces the persistence contract; keep D013 unless a broader evidence projection contract supersedes it

- time: 2026-03-23T04:54:55+08:00
  mode: stabilize
  item id: M001-S02-T02
  files changed:
    - backend/src/common/conversation/session_evidence.py
    - backend/src/common/conversation/replay.py
    - backend/src/common/api/practice.py
    - backend/src/common/conversation/schemas.py
    - backend/src/common/db/schemas.py
    - backend/tests/unit/test_session_evidence_service.py
    - backend/tests/unit/test_replay_service.py
    - backend/tests/contract/test_practice_evidence_contract.py
    - backend/tests/integration/test_practice_evidence_flow.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S02/S02-PLAN.md
    - .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a shared SessionEvidenceService that projects one normalized session evidence view, then switched quick report and replay to read that same projection with aligned overall/evaluable/stage facts and completeness diagnostics.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py
    - cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
    - cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'
  verification results: T01 backend regression suite passed; T02 focused backend suite passed; T03 backend verification still fails because the referenced history projection tests do not exist yet; T04 web verification still fails because the referenced page tests do not exist yet
  success signal status: report and replay now return the same overall score, stage summary, main issue / next goal, evaluable flag, not_evaluable_reason, and completeness diagnostics for the same completed session
  rollback note: revert SessionEvidenceService and the report/replay schema wiring together if downstream slices replace the reader contract; keep D014 unless a versioned projection contract supersedes it

- time: 2026-03-23T08:25:48+08:00
  mode: stabilize
  item id: M001-S02-T03
  files changed:
    - backend/src/common/analytics/history_service.py
    - backend/src/common/api/users.py
    - backend/src/common/api/analytics.py
    - backend/tests/unit/test_history_service_evidence_projection.py
    - backend/tests/unit/common/test_analytics_api_normalization.py
    - backend/tests/integration/test_history_evidence_flow.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S02/S02-PLAN.md
    - .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Reworked history/statistics/trends to batch-project completed sessions through the shared session evidence reader, aligned alias filtering and evaluability metadata, and removed dependence on ComprehensiveReport plus the old weighted overall formula.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py
    - cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
    - cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'
  verification results: all backend slice verification commands passed; the web slice command still fails with `No test files found` because T04's page tests do not exist yet
  success signal status: users/me/history, analytics/practice/history, practice/history/statistics, and practice/history/trends now return projection-backed overall/evaluable semantics that match report/replay for the same completed sessions
  rollback note: revert the HistoryService/API wiring together if a later slice replaces the history aggregation contract; keep D015 unless a new explicit non-evaluable trend contract supersedes it

- time: 2026-03-23T09:34:11+08:00
  mode: stabilize
  item id: M001-S02-T04
  files changed:
    - web/src/lib/api/types.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(dashboard)/history/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - web/src/app/(dashboard)/history/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S02/S02-PLAN.md
    - .gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finalized the web consumer closure so report/replay/history all trust the unified evidence contract, keep comprehensive report/highlights optional, and expose explicit degraded states instead of stitching conflicting scores.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py
    - cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
    - cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'
    - browser verification: dev-login -> /history asserted heading plus explicit `统一训练证据加载失败` / `重试` UI while local backend returned a schema-drift 500 for missing `conversation_messages.transcript_metadata`
  verification results: all slice verification commands passed; browser verification confirmed the page-level unified-evidence failure surface stays explicit instead of collapsing to a blank/generic state
  success signal status: web report/replay/history consumers now share one baseline fact source and preserve clear degraded states when enhanced content or analytics snapshots are missing
  rollback note: revert the T04 web consumer changes together if a later contract version replaces the unified evidence fields; keep D016 unless a new single-source frontend contract supersedes it

- time: 2026-03-23T09:45:31+08:00
  mode: stabilize
  item id: M001-S02
  files changed:
    - .gsd/milestones/M001/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M001/slices/S02/S02-UAT.md
    - .gsd/milestones/M001/M001-ROADMAP.md
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .gsd/STATE.md
    - .gsd/completed-units.json
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Completed slice S02 by verifying the crash-written task artifacts, writing the slice summary/UAT, marking the roadmap done, and recording that unified session evidence now underpins report/replay/history/trends for downstream slices.
  verification commands:
    - reused previously passed slice verification set recorded during T04 before the crash:
      - cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py
      - cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
      - cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py
      - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'
  verification results: no rerun during crash recovery per resume instructions; the previously completed slice verification set already passed, and the recorded browser diagnostics already proved the unified-evidence failure surface on /history stays explicit under local DB schema drift
  success signal status: S02 is now marked complete in roadmap/state artifacts and the project requirement notes explicitly capture that report/replay/history/trends share one evidence baseline for downstream work
- time: 2026-03-23T15:18:00+08:00
  mode: stabilize
  item id: M001-S03
  files changed:
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - .gsd/milestones/M001/slices/S03/S03-SUMMARY.md
    - .gsd/milestones/M001/slices/S03/S03-UAT.md
    - .gsd/milestones/M001/M001-ROADMAP.md
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed S03 by removing the regressed dead export affordance, writing the slice summary/UAT, validating learner report readability plus supervisor preview contracts against one evidence line, and marking the roadmap slice complete.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_admin_users_api.py
    - npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'
    - cd backend && venv/bin/alembic upgrade head
    - live runtime UAT: /practice/1398bea9-c25a-454f-ad1c-f645edcb3350/report, /practice/eda38292-9b64-4a8a-a271-c8f237477e9c/report, /api/v1/admin/users/0a0af6d4-d7cb-4ec8-be9f-f44288b10be2/sessions, /api/v1/admin/interventions/lists
  verification results: passed; fresh backend/frontend slice verification succeeded, report-page runtime UAT proved evaluable + not-evaluable first-screen behavior, and admin preview APIs matched the canonical report session ids after upgrading the local DB to Alembic head.
  success signal status: S03 is complete and R005/R006 are now validated; single-session learner/supervisor reads stay on one unified evidence line.
  rollback note: if future work changes single-session reporting again, preserve the explicit no-export-button assertion and keep admin previews sourced from SessionEvidenceService instead of reviving legacy weighting.


- time: 2026-03-23T18:16:22+08:00
  mode: stabilize
  item id: M001-S04-T02
  files changed:
    - backend/src/presentation_coach/api/presentations.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_flow.py
    - web/src/lib/api/client.ts
    - web/src/app/admin/presentations/[id]/page.tsx
    - web/src/app/admin/presentations/[id]/page.test.tsx
    - web/src/app/(dashboard)/agents/[agentId]/page.tsx
    - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
    - web/src/app/admin/presentations/page.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M001/slices/S04/S04-PLAN.md
    - .gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
  summary: Added in-place standard PPT replacement on the live presentations API, blocked swaps while active sessions reference the deck, rebuilt page-level coaching metadata for the next session, and surfaced version/status on both admin and learner entry pages.
  verification commands:
    - cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py
    - cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py
    - cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx' 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'
    - local runtime UAT attempt: cd backend && PYTHONPATH=src venv/bin/uvicorn main:app --host 127.0.0.1 --port 3444
  verification results: all automated S04 slice verification commands passed; local browser/runtime UAT remained blocked because backend startup exits with `redis package is required for SessionStateService` before port 3444 is ready
  success signal status: admin can replace a standard PPT without changing presentation_id, learner entry shows current version/status, and new presentation sessions read rebuilt page content + rules from the latest version
  rollback note: if future work revives a dedicated admin presentation API, keep /presentations as the source of truth until the admin surface is schema-aligned and fully verified end-to-end

- time: 2026-03-23T18:51:08+08:00
  mode: stabilize
  item id: M001-S04-T02
  files changed:
    - backend/src/presentation_coach/api/presentations.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_flow.py
    - web/src/lib/api/client.ts
    - web/src/app/admin/presentations/[id]/page.tsx
    - web/src/app/admin/presentations/[id]/page.test.tsx
    - web/src/app/(dashboard)/agents/[agentId]/page.tsx
    - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
    - .gsd/milestones/M001/slices/S04/S04-PLAN.md
    - .gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Recovered the missing T02 task artifact, re-verified the in-place standard PPT replacement feature, proved the live active-session blocker in the browser, and confirmed the user launch flow still carries the stable presentation_id with version/status visibility.
  verification commands:
    - cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py
    - cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py
    - cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx' 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'
    - browser UAT: /admin/presentations/20706b4b-bb22-484a-8f2f-8ecacc43bb3b upload + replace blocker verification
    - browser UAT: /agents/7199854c-3921-4d9f-9833-fe99ca209c59 version/status selector + new session launch carrying presentation_id=20706b4b-bb22-484a-8f2f-8ecacc43bb3b
  verification results: passed; automated S04 suites are green, live browser verified the blocker and stable-ID user launch, and the only unresolved destructive live-swap path is intentionally deferred because the ready deck is still referenced by unrelated in-progress sessions while backend integration tests already cover successful replace semantics
  success signal status: admin sees version/status + replace blocker on the live detail page, and user entry shows the current deck version/status while launching the next presentation practice with the same stable presentation_id
  rollback note: if later work needs a full browser success-swap UAT, first free or clone a ready presentation deck not referenced by active sessions before rerunning the replace flow

- time: 2026-03-23T19:07:30+08:00
  mode: stabilize
  item id: M001-S04
  files changed:
    - .gsd/milestones/M001/slices/S04/S04-SUMMARY.md
    - .gsd/milestones/M001/slices/S04/S04-UAT.md
    - .gsd/milestones/M001/M001-ROADMAP.md
    - .gsd/milestones/M001/slices/S04/S04-PLAN.md
    - .gsd/milestones/M001/slices/S04/tasks/T01-VERIFY.json
    - .gsd/milestones/M001/slices/S04/tasks/T02-VERIFY.json
    - .gsd/REQUIREMENTS.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .gsd/STATE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed S04 by writing the missing slice summary/UAT, validating R004 as shipped, fixing the stale task-level verifier artifacts that had been split into invalid bare commands, and re-proving the knowledge/PPT material-effectiveness surfaces with fresh automated plus local runtime checks.
  verification commands:
    - cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py
    - cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py
    - cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx' 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'
    - browser/runtime: POST /api/v1/auth/dev-login -> /admin/knowledge/7295703d-d400-4289-baef-62598051ffe7 search diagnostics -> POST /api/v1/practice/sessions for sales session 662543a2-07d0-4d8c-a1f0-1feffc05c23b -> GET /api/v1/practice/sessions/662543a2-07d0-4d8c-a1f0-1feffc05c23b/knowledge-check -> lifecycle start/end cleanup
    - browser/runtime: /admin/presentations/20706b4b-bb22-484a-8f2f-8ecacc43bb3b replace attempt with backend/data/ppts/5d63f1d6-1bf5-41b9-81ff-8a8827679225.pptx -> expect 409 blocker, then /agents/7199854c-3921-4d9f-9833-fe99ca209c59 version/status visibility
  verification results: passed; all three slice-level automated commands are green, local admin knowledge diagnostics and fresh sales-session snapshot/knowledge-check surfaces are live, admin presentation replace correctly blocks with 409 while user entry shows the current deck version/status, and the only intentionally skipped browser path is a destructive success-swap on a deck still occupied by unrelated in-progress sessions
  success signal status: S04 is complete and R004 is now validated; admins can self-serve product materials and standard PPT updates while new sessions consume the frozen latest-material bindings through the live runtime contracts
  rollback note: if later work changes S04 verification again, keep task-level backend/web checks as separate commands and preserve the live `/api/v1/presentations` + `voice_policy_snapshot/knowledge-check` authority lines unless a fully re-verified contract replaces them

- time: 2026-03-23T20:06:53+08:00
  mode: stabilize
  item id: M001-S05-T01
  files changed:
    - backend/src/agent/capabilities/realtime_scoring.py
    - backend/src/common/effectiveness/evaluator.py
    - backend/src/common/effectiveness/__init__.py
    - backend/src/common/api/practice.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/tests/unit/test_realtime_scoring.py
    - backend/tests/unit/test_effectiveness_sales_baseline.py
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - backend/tests/contract/test_practice_evidence_contract.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M001/slices/S05/S05-PLAN.md
    - .gsd/milestones/M001/slices/S05/tasks/T01-SUMMARY.md
    - .codex/loop/state.json
  summary: Replaced the generic StepFun sales scorer with a five-dimension value/benefit/evidence/objection/next-step rubric, mapped runtime snapshots into three sales rollups, and kept the unified report/replay contract stable while switching main_issue/next_goal to sales semantics.
  verification commands:
    - cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py
    - cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py -k 'value or objection or report'
    - cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py
    - cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - cd backend && PYTHONPATH=src venv/bin/python - <<'PY' ...
  verification results: task-level focused backend suites passed; direct observability check proved new dimension_scores, sales rollups, sales issue/goal, and persisted/not_evaluable logs; slice-level backend verification still fails because tests/integration/test_sales_value_training_flow.py is not present yet; slice-level web command exits 0 but ScorePanel.test.tsx is still absent and belongs to T03.
  success signal status: write-layer sales sessions now persist value-expression/evidence/objection facts that report/replay can read without changing field names or read-side scoring.
- time: 2026-03-23T22:45:07+08:00
  mode: stabilize
  item id: M001-S05-T03
  files changed:
    - backend/tests/integration/test_sales_value_training_flow.py
    - web/src/components/practice/ScorePanel.tsx
    - web/src/components/practice/ScorePanel.test.tsx
    - web/src/hooks/websocket/message-handlers.test.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - .gsd/milestones/M001/slices/S05/tasks/T03-PLAN.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M001/slices/S05/S05-PLAN.md
    - .gsd/milestones/M001/slices/S05/tasks/T03-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Aligned ScorePanel/report consumers to sales semantics, added focused web regressions plus a report API integration proof, and verified the live report page shows sales rollups/main_issue/next_goal/knowledge-hit diagnostics from the unified contract.
  verification commands:
    - cd backend && pytest tests/integration/test_sales_value_training_flow.py
    - cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py
    - cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - browser_assert /practice/6aff04f9-a09e-4956-8abc-07251c597a8f/report
    - browser runtime spot-check /practice/0661f672-a39a-404e-b4b5-93e396c77fe0
  verification results: task-level backend/web and full automated S05 slice suites all passed; browser report verification passed against a seeded completed sales session in the real app; live practice runtime reached Realtime in_progress with an enabled recording control, but the four-dialogue microphone UAT remains open due time budget.
  success signal status: live report/ScorePanel consumers now present value-expression, evidence-benefit, and objection-progression semantics without changing the underlying unified report contract.
  rollback note: revert the T03 consumer/test changes together if later work redefines S05 sales vocabulary, and keep the `.gsd/KNOWLEDGE.md` python-socks runtime note unless local StepFun proxy handling is solved another way.

- time: 2026-03-24T09:08:24+08:00
  mode: stabilize
  item id: M001-S06-T02
  files changed:
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M001/slices/S06/S06-PLAN.md
    - .gsd/milestones/M001/slices/S06/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Verified that the admin user-detail page already consumes the projection-backed supervisor progress contract, proved the live success state on a seeded learner, and confirmed inline progress empty/error states through the real refresh path without regressing the surrounding shell or report drill-ins.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k 'progress or stats'
    - cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'
    - cd backend && venv/bin/alembic upgrade head
    - browser runtime: /admin/users/89e31f06-6393-42b6-877e-5a007803136a success + injected progress empty/error refresh assertions
  verification results: passed; the full S06 backend slice checks, focused web regression, idempotent migration step, and live browser verification all passed fresh. No migration/blocker mismatch surfaced after upgrading to head.
  success signal status: the supervisor continuous-change page is now verified end-to-end on the same projection-backed fact line as admin stats/progress/sessions, with explicit inline empty/error UX proven in the real app shell.
  rollback note: no production rollback needed from this turn because execution only completed verification/state artifacts; if future browser UAT needs progress-only degraded states again, reuse the window.fetch override path instead of cross-origin route mocks.

- time: 2026-03-24T09:21:47+08:00
  mode: stabilize
  item id: M001-S06
  files changed:
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M001/M001-ROADMAP.md
    - .gsd/milestones/M001/slices/S06/S06-SUMMARY.md
    - .gsd/milestones/M001/slices/S06/S06-UAT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed S06 by rerunning the full slice verification set, re-proving the live admin supervisor progress view against local success/empty/error states, validating R007, reinforcing R011, and writing the slice summary/UAT plus roadmap/project continuity updates.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_history_service_evidence_projection.py tests/integration/test_admin_users_api.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py -k 'progress or stats'
    - cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx'
    - cd backend && /usr/bin/time -p venv/bin/alembic upgrade head
    - browser runtime: POST /api/v1/auth/dev-login -> /admin/users/89e31f06-6393-42b6-877e-5a007803136a success state assertions + direct /progress and /stats checks + injected progress empty/error refresh assertions
  verification results: passed; fresh backend/web slice verification succeeded, Alembic was at head, direct browser-side /progress and /stats reads matched the rendered cards, and the live admin page kept report drill-ins while proving success, empty, and error progress branches.
  success signal status: S06 is complete and the supervisor continuous-change view is now a verified projection-backed part of the M001 training loop rather than a generic chart detached from the canonical report facts.
  rollback note: no product rollback introduced in this closer turn; if future work needs to revisit S06, keep R007 validated unless /progress, /stats, and completed-session previews drift off the shared HistoryService projection line.

- time: 2026-03-24T10:09:23+08:00
  mode: stabilize
  item id: M001-S07-T01
  files changed:
    - backend/src/presentation_coach/services/presentation_report_service.py
    - backend/src/presentation_coach/websocket/presentation_handler.py
    - backend/tests/unit/evaluation/test_comprehensive_report_service.py
    - backend/tests/unit/test_presentation_handler_persistence.py
    - backend/tests/unit/test_presentation_stepfun_realtime_handler.py
    - .gsd/milestones/M001/slices/S07/S07-PLAN.md
    - .gsd/milestones/M001/slices/S07/tasks/T01-SUMMARY.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a normalized PresentationReportService review builder with explicit degraded page-metadata diagnostics, routed the enhanced presentation report through that builder, and made the legacy PPT websocket persist current_page via transcript_metadata on the existing message-analysis update path.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_handler_persistence.py -k page_number
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
  verification results: backend T01 unit suites and the explicit degraded-path check passed fresh; the slice-level contract/integration command failed because T02's report contract tests are not in the tree yet; the existing report page test still passes.
  success signal status: both presentation runtimes now write the same page-number evidence fact line, and one reusable presentation review payload is available for the shared report contract with explicit degraded fallback reasons instead of sales-semantic silence.
  rollback note: if S07 contract wiring changes in T02+, keep PresentationReportService as the single PPT review authority and preserve legacy transcript_metadata.page_number persistence unless a fully re-verified storage contract replaces it.

- time: 2026-03-24T11:02:36+08:00
  mode: stabilize
  item id: M001-S07-T02
  files changed:
    - backend/src/common/conversation/session_evidence.py
    - backend/src/common/db/schemas.py
    - backend/src/common/api/practice.py
    - backend/tests/contract/test_presentation_report_contract.py
    - backend/tests/integration/test_presentation_report_flow.py
    - web/src/lib/api/types.ts
    - .gsd/milestones/M001/slices/S07/S07-PLAN.md
    - .gsd/milestones/M001/slices/S07/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Verified and carried forward the scenario-aware presentation shared-report baseline so /practice/sessions/{id}/report now returns canonical presentation_review facts, explicit degraded page-evidence diagnostics, and retry presentation_id continuity instead of sales fallback fields.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_presentation_report_flow.py -k degraded
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
  verification results: passed; the new presentation contract/integration suites are green, the degraded-path unit and integration proofs are green, and the existing report page test still passes. Real runtime/browser UAT remains for final slice closure.
  success signal status: shared report consumers can now inspect scenario_type=presentation plus presentation_review/evidence_completeness instead of reading PPT sessions through sales main_issue/next_goal semantics.
  rollback note: if later work needs to revisit S07 contract wiring, preserve the shared report route's scenario-aware presentation payload and keep degraded state inside presentation_review/evidence_completeness rather than reviving sales fallback fields.
- time: 2026-03-24T11:38:46+08:00
  mode: stabilize
  item id: M001-S07-T03
  files changed:
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/lib/session-evidence.ts
    - .gsd/milestones/M001/slices/S07/S07-PLAN.md
    - .gsd/milestones/M001/slices/S07/tasks/T03-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Shared report pages now branch on scenario_type=presentation, render canonical PPT review/page-summary/coverage diagnostics, skip knowledge-check noise for presentation sessions, and keep retry continuity on the same presentation_id.
  verification commands:
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - TOKEN=$(curl -s -X POST http://127.0.0.1:3444/api/v1/auth/dev-login | jq -r '.data.access_token'); for SESSION in 8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b ec5b7b03-a83a-4ee6-bc33-d768ccfec610; do curl -s http://127.0.0.1:3444/api/v1/practice/sessions/$SESSION/report -H "Authorization: Bearer $TOKEN" | jq -c '{success,error,scenario_type:.data.scenario_type,overall_score:.data.overall_score,page_summaries:(.data.presentation_review.page_summaries|length),required_status:.data.presentation_review.required_talking_points.status,degraded_reasons:.data.presentation_review.diagnostics.degraded_reasons,main_issue:.data.main_issue,next_goal:.data.next_goal,retry_entry:.data.retry_entry}'; done
    - browser UAT attempt on http://127.0.0.1:3445/practice/8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b/report after browser-side POST http://127.0.0.1:3444/api/v1/auth/dev-login
  verification results: focused web regression passed; seeded happy/degraded presentation report API checks passed; live browser page UAT on the fresh :3445 web server remained blocked by local auth cookie/session persistence and returned 401 on the report fetch
  success signal status: presentation sessions now render PPT-specific postmortems in the shared report page and no longer trigger sales-only knowledge-check/report cards
  rollback note: if follow-up work revisits S07 runtime proof, reuse the seeded presentation sessions 8ed2f3d9-9591-4c74-b9cb-1827eabf3b4b and ec5b7b03-a83a-4ee6-bc33-d768ccfec610 on :3445 rather than the broken historical local sessions that currently return [SESSION_EVIDENCE_FAILED]

- time: 2026-03-24T12:06:53+08:00
  mode: stabilize
  item id: M001-S07
  files changed:
    - .gsd/REQUIREMENTS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M001/M001-ROADMAP.md
    - .gsd/milestones/M001/slices/S07/S07-SUMMARY.md
    - .gsd/milestones/M001/slices/S07/S07-UAT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed S07 by re-running the full presentation slice verification set, proving a fresh audio-driven page-turn presentation session on the real websocket path, verifying happy/degraded canonical report behavior plus the shared PPT report page, validating R008, and writing the slice summary/UAT with updated project knowledge.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_presentation_report_flow.py -k degraded
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - live runtime: create presentation session -> websocket audio chunks + page_change -> GET /api/v1/practice/sessions/8531c7f6-50da-4934-9fd4-63784c791edf/report
    - browser/runtime: localhost dev-login -> /practice/8531c7f6-50da-4934-9fd4-63784c791edf/report -> assert PPT branch + absent sales-only text + retry continuity
    - diagnostics: GET /api/v1/practice/sessions/ec5b7b03-a83a-4ee6-bc33-d768ccfec610/report
  verification results: passed; fresh automated backend/web slice suites are green, the live websocket/audio proof produced complete page-aware presentation evidence on the canonical report route, the degraded historical session stayed presentation-shaped with explicit missing-page diagnostics, and the browser report page showed PPT review content without sales-only sections.
  success signal status: S07 is complete and the shared learner report entrypoint now serves usable PPT postmortems from real page/material evidence instead of sales fallback semantics or optional enhanced-report dependence.
  rollback note: if later work revisits S07 verification, keep localhost/localhost host alignment and use real audio chunks for page-metadata proof; the StepFun text shortcut can complete a session but is not trustworthy evidence for page-number persistence.


- time: 2026-03-24T16:52:43+08:00
  mode: stabilize
  item id: M001-S08-T01
  files changed:
    - backend/src/common/conversation/runtime_diagnostics.py
    - backend/src/support/services/runtime_status_service.py
    - backend/src/support/services/__init__.py
    - backend/src/support/api/runtime_status.py
    - backend/src/common/api/practice.py
    - backend/tests/unit/test_support_runtime_service.py
    - backend/tests/contract/test_support_runtime.py
    - backend/tests/integration/test_support_runtime_api.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S08/S08-PLAN.md
    - .gsd/milestones/M001/slices/S08/tasks/T01-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Replaced the old SystemLog-based support/runtime reader with an evidence-backed release-health service, extracted shared runtime diagnostics from practice knowledge-check, and classified typed blocking/warning anomalies for scoring, projection, knowledge, and presentation degraded states.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses
  verification results: passed; the new support-runtime task suite is green and the extracted helper preserved the canonical knowledge-check status semantics.
  success signal status: /api/v1/support/runtime/overview and /api/v1/support/runtime/faults now expose typed release-health counters plus blocking/warning anomaly items from unified session evidence instead of coarse completion/log counts.
  rollback note: if later work revisits this reader, keep SystemLog as supplemental warning-only input and preserve the shared runtime diagnostics helper as the single source for knowledge-check/support-runtime status semantics.

- time: 2026-03-24T17:44:00+08:00
  mode: stabilize
  item id: M001-S08-T02
  files changed:
    - web/src/app/(dashboard)/support/runtime/page.tsx
    - web/src/app/(dashboard)/support/runtime/page.test.tsx
    - web/src/lib/api/types.ts
    - web/src/lib/api/client.ts
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M001/slices/S08/S08-PLAN.md
    - .gsd/milestones/M001/slices/S08/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Rebuilt /support/runtime into a typed blocking/warning release-health panel, added focused page coverage, kept overview/fault failures local, and proved the live plus degraded UI states in the browser.
  verification commands:
    - cd web && npm test -- --run 'src/app/(dashboard)/support/runtime/page.test.tsx'
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts'
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - browser/runtime: localhost dev-login -> /support/runtime live blocking/warning assertions + window.fetch override for empty/error refresh assertions
  verification results: support runtime focused suite passed, the slice lifecycle/websocket web suite passed, and browser UAT proved live blocking/warning plus local empty/error states. The broader report/admin/support web slice command is still red because report/page.test.tsx already fails alone on missing enhanced-report degraded copy.
  success signal status: support/admin can now see backend-typed release health, scoring separation, blocking/warning counts, and session-scoped anomaly diagnostics directly on /support/runtime instead of coarse completion/log cards.
  rollback note: if follow-up work revisits browser UAT for support/runtime, avoid cross-origin route mocks for localhost support-runtime endpoints and keep using an in-page window.fetch override plus the page's own 刷新 action.

- time: 2026-03-24T17:58:35+08:00
  mode: stabilize
  item id: M001-S08-T03
  files changed:
    - .gsd/milestones/M001/slices/S08/tasks/T03-PLAN.md
    - .gsd/milestones/M001/slices/S08/S08-UAT.md
    - .gsd/milestones/M001/slices/S08/tasks/T03-SUMMARY.md
    - .gsd/milestones/M001/slices/S08/S08-PLAN.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added the missing observability section to the T03 plan, wrote the S08 release-wave UAT artifact, ran the full automated slice gate, recorded the carried-forward report-page web failure plus current support-runtime blocking/warning evidence, and left exact resume notes for the unfinished localhost browser waves.
  verification commands:
    - cd backend && venv/bin/alembic upgrade head
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'
  verification results: backend verification passed fresh; the full web command still fails on the carried-forward sales report degraded-copy expectation in report/page.test.tsx; localhost backend/web were healthy, a fresh realtime sales session was created, and support/runtime currently reports a blocking release state with typed stuck_scoring / kb_lock_blocked_* / projection_failed anomalies plus warning-only upstream_unstable / presentation_degraded_missing_page_metadata.
  success signal status: S08-UAT is now a usable release-close artifact with actual gate output and precise resume instructions, but the browser-wave proof and final release verdict remain unfinished.
  rollback note: no product rollback was needed; next context should restart localhost servers and resume the browser waves from S08-UAT instead of redoing the automated gate.

- time: 2026-03-24T19:07:08+0800
  mode: stabilize
  item id: M002-S01-T01
  files changed:
    - backend/src/sales_bot/websocket/components/capability_processor.py
    - backend/tests/unit/test_capability_processor.py
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - .gsd/milestones/M002/slices/S01/S01-PLAN.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Aligned classic realtime action-card semantics to the shared sales effectiveness helper, added focused StepFun payload assertions for canonical sales score_update/action_card fields, and preserved the existing three-rollup evidence contract.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'
  verification results: passed; backend unit, diagnostic, contract, and slice web commands are green. An earlier parallel pytest attempt hit a pytest-cov .coverage.* combine race, so the main backend suite was rerun sequentially and passed fresh.
  success signal status: classic and StepFun sales runtime paths now agree on action-card semantics, and the canonical StepFun payload/read-side contract guardrails stay green.
  rollback note: if later work changes realtime action-card behavior again, keep CapabilityProcessor and StepFun handler tests aligned to the same build_sales_effectiveness_metrics/evaluate_pass_flags line rather than reviving generic communication/structure heuristics.

- time: 2026-03-24T19:18:31+0800
  mode: stabilize
  item id: M002-S01-T02
  files changed:
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/message-handlers.test.ts
    - web/src/components/practice/ScorePanel.tsx
    - web/src/components/practice/ScorePanel.test.tsx
    - web/src/app/(dashboard)/agents/[agentId]/page.tsx
    - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M002/slices/S01/S01-PLAN.md
    - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Hardened the practice-page sales websocket consumer to keep same-turn score refreshes, kept ScorePanel explicitly sales-first while preserving fallback dimensions, and aligned launch-page voice-mode copy to one shared sales rubric.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'
    - cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'
  verification results: passed; all slice-level backend/web commands and the extra websocket-hook task suite are green, so the frontend consumer fix kept the realtime/report contract boundary intact.
  success signal status: same-turn sales guidance now reaches the practice page without being deduped away, fallback dimensions remain visible, and mode selection no longer suggests a different classic-mode scoring rubric.
  rollback note: if later frontend work touches realtime scoring again, keep isSameScoreUpdate aligned with the focused Vitest contract and preserve the explicit fallback-dimension rendering instead of reintroducing overall-score-only dedupe.

- time: 2026-03-24T19:25:11+08:00
  mode: stabilize
  item id: M002-S01
  files changed:
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M002/M002-ROADMAP.md
    - .gsd/milestones/M002/slices/S01/S01-SUMMARY.md
    - .gsd/milestones/M002/slices/S01/S01-UAT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed S01 by rerunning the full slice verification set, updating R009 to capture the shipped contract-alignment proof, writing the slice summary/UAT artifacts, marking the roadmap slice complete, and refreshing project state for downstream roadmap reassessment.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py -k 'action_card or stage_update'
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'
    - cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'
  verification results: passed; all slice-level backend/web commands and the extra websocket-hook diagnostic suite passed fresh. The sales realtime contract is now aligned across StepFun and classic mode, same-turn practice-page score refreshes survive dedupe, and the existing report-side three-rollup evidence contract remains unchanged.
  success signal status: the training page now shows one shared sales rubric across both voice modes, and same-turn stage/suggestion/dimension refinements reach ScorePanel instead of being silently dropped.
  rollback note: no new product rollback was introduced in the closer turn; if downstream slices touch realtime coaching again, keep the shared sales-effectiveness helper on the backend and full-payload score_update idempotence on the frontend aligned as one contract.

- time: 2026-03-24T19:58:10+08:00
  mode: stabilize
  item id: M002-S02-T01
  files changed:
    - .gsd/milestones/M002/slices/S02/S02-PLAN.md
    - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
    - .gsd/DECISIONS.md
    - backend/src/sales_bot/websocket/realtime_feedback_arbiter.py
    - backend/src/sales_bot/websocket/components/capability_processor.py
    - backend/tests/unit/test_realtime_feedback_arbiter.py
    - backend/tests/unit/test_capability_processor.py
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a shared realtime-feedback arbiter for classic sales coaching, kept fuzzy/stage/score payloads as context, preferred score guidance over low-severity filler detections for the primary action card, and suppressed duplicate action cards when the same signature repeats within the same turn.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'
  verification results: task-level backend arbiter/classic processor suites passed; fuzzy cooldown and the added arbiter diagnostic command passed; slice-level web verification passed; the broader slice backend command still fails on test_sync_sales_realtime_terminal_evidence_uses_latest_message_score_snapshot outside the classic-path seam.
  success signal status: classic mode now emits one primary action card per turn with score-over-filler priority while preserving low-level context signals for downstream UI and StepFun reuse.
  rollback note: if T02 revisits arbitration, keep the shared turn+signature pacing state as the only action-card dedupe source and preserve FuzzyDetectionCapability's own cooldown rather than adding a second low-level throttle.

- time: 2026-03-24T20:14:49+08:00
  mode: stabilize
  item id: M002-S02-T02
  files changed:
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - backend/tests/unit/test_stepfun_realtime_persistence.py
    - .gsd/milestones/M002/slices/S02/S02-PLAN.md
    - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Routed StepFun realtime coaching through the shared arbiter, persisted only minimal reconnect-safe pacing state, restored replay suppression after reconnect, and refreshed the stale legacy terminal-evidence expectation to the current sales-rollup fallback.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'
  verification results: passed; all backend T02/slice commands are green and the existing web slice command still exits 0, but Vitest only matched the three existing files because RightPanelContent.test.tsx is still missing and remains T03 work.
  success signal status: StepFun now stays on the same single-action pacing line as classic mode and reconnect restore no longer replays stale action cards for the same turn.
  rollback note: if later slices revisit reconnect persistence, keep StepFun snapshot state limited to feedback_pacing_state plus read-side score/action diagnostics unless a broader, fully re-verified recovery contract replaces it.

- time: 2026-03-24T20:31:00+08:00
  mode: stabilize
  item id: M002-S02-T03
  files changed:
    - .gsd/milestones/M002/slices/S02/S02-PLAN.md
    - .gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/message-handlers.test.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/components/practice/RightPanelContent.tsx
    - web/src/components/practice/RightPanelContent.test.tsx
    - web/src/components/practice/ScorePanel.tsx
    - web/src/components/practice/ScorePanel.test.tsx
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Cleared stale turn-bound hints on final transcripts, made action_card the only primary text coach surface in the sales practice panel, and suppressed duplicate score suggestions without hiding stage or dimension context.
  verification commands:
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv
    - browser smoke: localhost dev-login -> create sales session -> /practice/adf0d98f-99dd-4127-8904-2ff8cbe8862e assert shell + score placeholder
  verification results: passed for the focused web gate, the broad S02 backend suite, the arbiter diagnostic filter, the StepFun replay diagnostic filter, and the live localhost practice-page smoke path. The remaining fuzzy cooldown slice command was not rerun in this unit after the context-budget warning; last known result was green from T02.
  success signal status: the practice page now clears stale hint state when a new user turn closes and no longer renders competing fuzzy/score suggestion text beside an active action card.
  rollback note: if slice closeout needs a fully fresh all-checks gate, rerun the fuzzy cooldown command before marking S02 complete; otherwise keep the new ScorePanel suppression prop local to RightPanelContent rather than mutating score payloads upstream.

- time: 2026-03-24T20:38:55+08:00
  mode: stabilize
  item id: M002-S02
  files changed:
    - .gsd/milestones/M002/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M002/slices/S02/S02-UAT.md
    - .gsd/milestones/M002/M002-ROADMAP.md
    - .gsd/REQUIREMENTS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M002/S02 after rerunning the full slice gate, recording the slice summary/UAT, marking the roadmap done, and updating requirement/project/knowledge continuity to reflect that realtime coaching now enforces one primary action per turn with reconnect-safe replay suppression and transcript-driven stale-hint clearing.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown
    - cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'
  verification results: passed; all slice-level backend and web commands were rerun fresh, including the previously deferred fuzzy cooldown regression, and the web gate reported Test Files (4) so the targeted RightPanelContent coverage actually executed.
  success signal status: S02 is now closed with one shared realtime-feedback pacing line across classic + StepFun, no same-turn action-card replay burst after restore, and no stale turn-bound action/fuzzy hints leaking into the next practice turn.
  rollback note: if downstream slices touch coach pacing again, preserve the backend arbiter + minimal feedback_pacing_state + frontend transcript-reset trio together; splitting those seams will recreate either replay bursts or cross-turn stale hints.

- time: 2026-03-24T21:37:02+0800
  mode: stabilize
  item id: M002-S03-T01
  files changed:
    - backend/src/common/effectiveness/evaluator.py
    - backend/src/common/effectiveness/schemas.py
    - backend/src/common/effectiveness/__init__.py
    - backend/tests/unit/test_effectiveness_sales_coaching_focus.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M002/slices/S03/S03-PLAN.md
    - .gsd/milestones/M002/slices/S03/tasks/T01-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a shared stage-aware sales coaching-focus resolver in common.effectiveness, rewired build_action_card to use it when rich stage/score context is present, and kept the legacy fallback path stable for current callers until T02/T03 wire the richer runtime context through.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv
  verification results: passed; all focused T01 checks and the full S03 backend unit gate exited 0. One intermediate parallel pytest-cov attempt hit a local .coverage race, and the affected selector passed when rerun sequentially.
  success signal status: common.effectiveness now exposes one canonical sales coaching-focus seam, and action cards can switch issue/replacement/next-turn guidance when stage or weakest dimension changes without changing the public websocket contract.
  rollback note: if later S03 work rewires action-card generation again, preserve the rich-context gate on build_action_card until every caller actually passes stage/score context through the shared resolver.

- time: 2026-03-24T21:51:30+0800
  mode: stabilize
  item id: M002-S03-T02
  files changed:
    - backend/src/sales_bot/websocket/realtime_feedback_arbiter.py
    - backend/tests/unit/test_realtime_feedback_arbiter.py
    - backend/tests/unit/test_capability_processor.py
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M002/slices/S03/S03-PLAN.md
    - .gsd/milestones/M002/slices/S03/tasks/T02-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Routed classic realtime action-card arbitration through the shared sales coaching-focus rule, proved stage-aware and declining-dimension classic outputs under focused arbiter/processor tests, and preserved same-turn duplicate suppression plus contextual fuzzy/stage/score messages without changing websocket payload shapes.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv
  verification results: the two T02 classic commands passed fresh; the carried-forward coaching-focus focused suites and new arbiter diagnostic selector also passed; the broad S03 backend suite and StepFun verbose suite now fail only on T03-owned StepFun action-card expectation drift in tests/unit/test_stepfun_realtime_handler.py after classic arbitration started emitting shared rich-context coaching-focus text.
  success signal status: classic runtime now changes action_card issue/replacement/next_turn_rule when stage or weakest/declining dimension changes while keeping fuzzy_detection, stage_update, score_update, and same-turn duplicate suppression intact.
  rollback note: if T03 revisits this seam, keep the arbiter rich-context handoff and only adapt StepFun context parity/assertions on top; reverting classic back to suggestion-only action cards would reopen the slice gap.

- time: 2026-03-24T22:09:36+08:00
  mode: stabilize
  item id: M002-S03-T03
  files changed:
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M002/slices/S03/S03-PLAN.md
    - .gsd/milestones/M002/slices/S03/tasks/T03-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: StepFun now retains rich stage analysis output and raw score deltas for arbitration, matches classic sales action-card direction on equivalent inputs, and keeps the public score_update/_latest_score_snapshot contract unchanged.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv
  verification results: passed; all task-level and slice-level S03 verification commands exited 0 after the StepFun handoff fix.
  success signal status: classic and StepFun now stay on the same shared coaching-focus action-card direction while StepFun still emits the existing stable score snapshot for consumers.
  rollback note: if later work revisits this seam, preserve the split between stable public score snapshots and richer arbiter-only context instead of changing the score_update shape.

- time: 2026-03-24T22:19:01+08:00
  mode: stabilize
  item id: M002-S03
  files changed:
    - .gsd/milestones/M002/slices/S03/S03-SUMMARY.md
    - .gsd/milestones/M002/slices/S03/S03-UAT.md
    - .gsd/milestones/M002/M002-ROADMAP.md
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M002/S03 by rerunning the full slice verification set, confirming the coaching-focus diagnostic surfaces, writing the slice summary/UAT, marking the roadmap done, and recording that classic + StepFun now share one stage-aware next-turn coaching rule while keeping the public score snapshot contract stable.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv
  verification results: passed; all five slice-plan commands exited 0 fresh, the shared coaching-focus and arbiter context-preservation diagnostics are green, and StepFun verbose coverage still proves rich-stage/raw-score arbitration parity without changing public score_update payload shape.
  success signal status: S03 is complete and R009 is further advanced; realtime stage, weakest/declining dimension changes, and action-card wording now converge on one backend rule across classic + StepFun.
  rollback note: if downstream slices touch coach/report alignment or degraded-state visibility, keep resolve_sales_coaching_focus plus the classic/StepFun rich-context handoff boundary intact; falling back to pass-flags-only action cards or flattening StepFun arbiter context into the public snapshot will reopen S03 drift.

- time: 2026-03-24T23:03:44+08:00
  mode: stabilize
  item id: M002-S04-T01
  files changed:
    - .gsd/milestones/M002/slices/S04/S04-PLAN.md
    - .gsd/milestones/M002/slices/S04/tasks/T01-PLAN.md
    - .gsd/milestones/M002/slices/S04/tasks/T01-SUMMARY.md
    - backend/src/common/effectiveness/evaluator.py
    - backend/src/common/effectiveness/schemas.py
    - backend/src/common/effectiveness/__init__.py
    - backend/tests/unit/test_effectiveness_sales_report_alignment.py
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a shared persisted-evidence sales report-alignment helper, covered discovery/objection/closing plus insufficient-evidence fallback with focused unit tests, and recorded the internal diagnostic seam needed for later projection logging without changing public report keys.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
  verification results: task-level helper verification passed, the new insufficient-evidence failure-path check passed, and the backend contract/integration set already passes; slice-level verification is partial because replay unit mocks still fall into presentation review, the focused T02 session-evidence selector currently matches no tests, and the report page web suite still expects older degraded-copy text.
  success signal status: common.effectiveness now has one stage-aware read-side sales alignment seam with explicit fallback diagnostics, giving T02 a single place to override stale completed-session conclusions.
  rollback note: if T02+ changes this seam, keep the helper internal-diagnostic fields and shared issue/goal vocabulary map together; reverting to separate read-side heuristics would reopen coach/report drift.

- time: 2026-03-25T07:41:30+08:00
  mode: stabilize
  item id: M002-S04-T02
  files changed:
    - backend/src/common/conversation/session_evidence.py
    - backend/tests/unit/test_replay_service.py
    - backend/tests/integration/test_sales_value_training_flow.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M002/slices/S04/tasks/T02-SUMMARY.md
    - .gsd/milestones/M002/slices/S04/S04-PLAN.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Projection-backed completed sales readers now override stale main_issue/next_goal from the latest alignable persisted stage+dimension evidence, log concise alignment diagnostics, and keep replay/history/report on one sales-first conclusion baseline.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'insufficient_sales_evidence' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
  verification results: passed; all six slice verification commands exited 0 fresh. The backend packs now prove stale-snapshot override, insufficient-evidence fallback, replay/history/report alignment, and the web focused command still passes after the read-side change.
  success signal status: completed sales projection now walks backward to the latest alignable persisted sales evidence instead of letting newer partial snapshots disable alignment, so report/replay/history/admin can share one conclusion family while the projection log exposes why override did or did not apply.
  rollback note: if T03+ revisits sales read-side alignment, preserve the projection-only override boundary plus the minimal log fields; falling back to newest-raw-snapshot selection or omitting `sales_alignment_*` diagnostics will silently reopen stale report/replay drift.

- time: 2026-03-25T07:55:00+08:00
  mode: stabilize
  item id: M002-S04
  files changed:
    - backend/src/common/effectiveness/evaluator.py
    - backend/src/common/effectiveness/schemas.py
    - backend/src/common/effectiveness/__init__.py
    - backend/src/common/conversation/session_evidence.py
    - backend/tests/unit/test_effectiveness_sales_report_alignment.py
    - backend/tests/unit/test_session_evidence_service.py
    - backend/tests/unit/test_replay_service.py
    - backend/tests/unit/test_history_service_evidence_projection.py
    - backend/tests/contract/test_practice_evidence_contract.py
    - backend/tests/integration/test_practice_evidence_flow.py
    - backend/tests/integration/test_sales_value_training_flow.py
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/admin/users/[id]/page.test.tsx
    - .gsd/REQUIREMENTS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M002/slices/S04/tasks/T03-SUMMARY.md
    - .gsd/milestones/M002/slices/S04/S04-SUMMARY.md
    - .gsd/milestones/M002/slices/S04/S04-UAT.md
    - .gsd/milestones/M002/M002-ROADMAP.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed S04 by finishing the missing replay/admin web carry-forward, re-running the full slice verification set, updating requirement/project/knowledge continuity, and recording that completed sales sessions now share one aligned coach conclusion across report/replay/history/admin.
  verification commands:
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'insufficient_sales_evidence' -vv
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py
    - cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'
  verification results: passed; all six slice-level verification commands exited 0 on the final run. The web gate first exposed a real missing T03 carry-forward plus an async test-timing issue, and the final rerun proved replay/report/admin now stay green on the aligned sales conclusion family.
  success signal status: completed sales sessions now override stale read-side conclusions from the latest alignable persisted sales evidence, replay visibly surfaces the same aligned coach conclusion as report, admin badges remain readable for the new vocabulary, and R009 is further advanced without changing public report/websocket keys.
  rollback note: if later slices revisit S04, preserve the projection-only override boundary, the centralized `session-evidence` vocabulary map, and the replay page’s direct API rendering; reintroducing client heuristics or choosing the newest partial snapshot will silently reopen conclusion drift.

- time: 2026-03-25T09:37:53+08:00
  mode: stabilize
  item id: M003-S01-T01
  files changed:
    - .gsd/milestones/M003/M003-ROADMAP.md
    - .gsd/milestones/M003/slices/S01/S01-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M003/slices/S01/tasks/T01-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md

  summary: Locked the M003 roadmap/S01/T01 artifacts to the real admin→session→practice chain, fixed unrunnable verification commands for literal Next.js paths, and recorded the shell-quoting gotcha in project knowledge.
  verification commands:
    - bash -lc "test -f 'backend/src/agent/services/persona_policy.py' && test -f 'backend/src/sales_bot/services/voice_runtime_policy.py' && test -f 'backend/src/sales_bot/services/voice_instruction_compiler.py' && test -f 'backend/src/common/api/practice.py' && test -f 'web/src/app/admin/personas/[id]/page.tsx' && test -f 'web/src/app/admin/knowledge/[id]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/report/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/replay/page.tsx'"
    - rg -n \"persona_policy.py|voice_runtime_policy.py|voice_instruction_compiler.py|practice.py|POST /api/v1/practice/sessions|web/src/app/admin/personas/\[id\]/page.tsx|web/src/app/admin/knowledge/\[id\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx|Silence|Conda|\\.env|lockfile|inventory/spike\" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md
    - bash -lc "test -f 'backend/src/agent/services/persona_policy.py' && test -f 'backend/src/sales_bot/services/voice_runtime_policy.py' && test -f 'backend/src/sales_bot/services/voice_instruction_compiler.py' && test -f 'backend/src/common/knowledge/kb_lock_guard.py' && test -f 'backend/src/common/conversation/runtime_diagnostics.py' && test -f 'backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py' && test -f 'backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py' && test -f 'backend/src/common/api/practice.py' && test -f 'backend/src/common/conversation/session_evidence.py' && test -f 'web/src/app/admin/personas/[id]/page.tsx' && test -f 'web/src/app/admin/knowledge/[id]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/report/page.tsx' && test -f 'web/src/app/(user)/practice/[sessionId]/replay/page.tsx'"
    - rg -n \"no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty\" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
    - rg -n \"Silence|Conda|\\.env|lockfile|inventory/spike|current admin|current product route\" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md

  verification results: passed; all five final verification commands exited 0 after quoting literal Next.js route paths in the doc commands. No blocker or scope change remained.
  success signal status: M003 planning is now pinned to the confirmed admin Persona/knowledge → POST /api/v1/practice/sessions → learner practice/report/replay chain, and the verification examples no longer false-fail on literal Next.js paths.
  rollback note: If later planning rewrites M003/S01 again, keep POST /api/v1/practice/sessions plus web/src/app/(user)/practice/[sessionId]/page.tsx as the canonical seam and keep quoted route-path verification commands.

- time: 2026-03-25T09:48:35+08:00
  mode: stabilize
  item id: M003-S01-T02
  files changed:
    - .gsd/milestones/M003/M003-ROADMAP.md
    - .gsd/milestones/M003/slices/S01/S01-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T02-SUMMARY.md
    - .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Locked the live knowledge status ownership line to the real runtime/report contract, documented blocked and retrieval-detail states as diagnostics only, hardened the remaining M003 verifier commands with escaped Next.js literal paths, and replaced the stale T01 verify artifact that kept replaying the old false failure.
  verification commands:
    - test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/knowledge/kb_lock_guard.py && test -f backend/src/common/conversation/runtime_diagnostics.py && test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx
    - rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
    - rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - rg -n "hit_keyword_fallback|last_status|kb_lock_status|kb_lock_last_status" backend/src/common/conversation/runtime_diagnostics.py backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
  verification results: passed; the slice-level path/status/scope checks all exited 0, the ownership grep confirmed `hit_keyword_fallback` stays in runtime detail rather than learner/admin status, and the refreshed T01-VERIFY artifact now records the fixed literal-path checks as passing.
  success signal status: M003 S01 now explicitly separates learner/admin-visible knowledge statuses from runtime-only KB-lock and retrieval-detail diagnostics, and auto-mode no longer replays the old `app/(user)` shell failure from stale verification state.
  rollback note: If later planning rewrites M003/S01 again, keep `build_session_runtime_diagnostics(...).status` as the seven-status learner/admin contract, keep `blocked_*` plus `hit_keyword_fallback` in diagnostics only, and refresh any stale VERIFY artifact when verification syntax changes.

- time: 2026-03-25T10:02:13+08:00
  mode: stabilize
  item id: M003-S01-T03
  files changed:
    - .gsd/milestones/M003/M003-ROADMAP.md
    - .gsd/milestones/M003/slices/S01/S01-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - .gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Bound the M003 proof boundary to the live report/knowledge-check/replay routes, documented the real replay ownership split, and locked the inventory/spike blocker so later slices cannot verify against guessed backend seams.
  verification commands:
    - test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/api.py && test -f backend/src/common/conversation/replay.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx
    - rg -n "focused backend|focused web|live UAT|/api/v1/practice/sessions/\{id\}/report|/api/v1/sessions/\{id\}/replay|common/conversation/api.py|common/conversation/replay.py|SessionEvidenceService|inventory/spike|blocking rule|current routes" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/knowledge/kb_lock_guard.py && test -f backend/src/common/conversation/runtime_diagnostics.py && test -f backend/src/common/conversation/api.py && test -f backend/src/common/conversation/replay.py && test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx
    - rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
    - rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - rg -n "focused backend|focused web|live UAT|/api/v1/practice/sessions/\{id\}/report|/api/v1/sessions/\{id\}/replay|common/conversation/api.py|common/conversation/replay.py|SessionEvidenceService" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
  verification results: passed; both T03 task checks and the full S01 slice verification set exited 0 after the docs were updated to name the current replay route/modules explicitly.
  success signal status: M003 S01 now forces later proof onto the live admin -> session -> practice -> knowledge-check/report/replay chain, and replay is documented against its real conversation-api ownership instead of an assumed practice.py seam.
  rollback note: If later M003 planning changes the proof boundary again, keep replay anchored to `/api/v1/sessions/{id}/replay` plus `ReplayService`/`SessionEvidenceService`, and keep the inventory/spike blocker explicit whenever a required route cannot be found.

- time: 2026-03-25T10:13:00+08:00
  mode: stabilize
  item id: M003-S01
  files changed:
    - .gsd/milestones/M003/slices/S01/tasks/T03-VERIFY.json
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M003/slices/S01/S01-SUMMARY.md
    - .gsd/milestones/M003/slices/S01/S01-UAT.md
    - .gsd/milestones/M003/M003-ROADMAP.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M003/S01 by refreshing the stale T03 VERIFY artifact that still replayed bare Next.js shell paths, rerunning the full slice gate plus observability grep, updating R010/project continuity, and recording the slice summary/UAT on the locked real-entry-chain proof boundary.
  verification commands:
    - test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/knowledge/kb_lock_guard.py && test -f backend/src/common/conversation/runtime_diagnostics.py && test -f backend/src/common/conversation/api.py && test -f backend/src/common/conversation/replay.py && test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx
    - rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
    - rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - rg -n "focused backend|focused web|live UAT|/api/v1/practice/sessions/\{id\}/report|/api/v1/sessions/\{id\}/replay|common/conversation/api.py|common/conversation/replay.py|SessionEvidenceService" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
    - rg -n "knowledge-check\.status|knowledge-check\.summary|runtime_metrics\.knowledge_retrieval|kb_lock_status|kb_lock_last_status|last_query|recent_queries|voice_policy_snapshot_ref" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/api/practice.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md
  verification results: passed; the full slice gate and the observability-surface grep all exited 0, and the refreshed T03-VERIFY artifact removed the stale shell syntax failure from bare `app/(user)` commands.
  success signal status: M003/S01 is now complete with one real admin->practice proof boundary, one locked seven-status knowledge contract, and verifier artifacts that match the hardened shell-safe command form.
  rollback note: If a later M003 gate trips on literal Next.js paths again, inspect the relevant `T##-VERIFY.json` before changing slice docs; keep replay bound to the conversation API/replay service seam and keep environment/tooling work out of M003 unless the milestone is explicitly re-scoped.

- time: 2026-03-25T10:24:42+08:00
  mode: stabilize
  item id: M003-S02-T01
  files changed:
    - backend/src/agent/services/persona_policy.py
    - backend/src/agent/services/persona_service.py
    - backend/tests/unit/test_persona_policy.py
    - backend/tests/integration/test_persona_api.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md
    - .gsd/milestones/M003/slices/S02/S02-PLAN.md
  summary: Normalized Persona policy into a nested customer-pressure contract, preserved flat sales-focus fields as compatibility projections, and added audit/test coverage that distinguishes raw legacy rows from canonical persisted policy.
  verification commands:
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py
    - lsp diagnostics: backend/src/agent/services/persona_policy.py, backend/src/agent/services/persona_service.py, backend/tests/unit/test_persona_policy.py, backend/tests/integration/test_persona_api.py
  verification results: passed; focused backend pytest finished green with 18 passing tests, and all touched backend files were clean in LSP diagnostics.
  success signal status: Persona admin/runtime work now has one snapshot-ready customer-pressure shape and one explicit audit signal for rows still stored in legacy flat form.
  rollback note: if follow-up work revisits Persona pressure storage, keep the nested customer_pressure model canonical and continue using pressure_model_legacy_only only for raw rows that truly lack the nested snapshot.

- time: 2026-03-25T11:07:30+08:00
  mode: stabilize
  item id: M003-S02
  files changed:
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M003/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M003/slices/S02/S02-UAT.md
    - .gsd/milestones/M003/M003-ROADMAP.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M003/S02 by rerunning the full planned slice gate, adding an extra snapshot-persistence sanity pass, updating R010 and project continuity, and recording the slice summary/UAT around the frozen Persona pressure contract.
  verification commands:
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py
    - cd web && /usr/bin/time -p npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_voice_runtime_session_snapshot.py
  verification results: passed; the planned backend persona-policy/admin API gate passed with 18 tests, the planned backend runtime-snapshot gate passed with 12 tests, the planned web Persona detail gate matched the intended file and passed with 2 tests, and the extra snapshot-persistence sanity file passed with 8 tests proving the frozen baseline survives later detail/report/replay reads and runtime-metrics appends.
  success signal status: M003/S02 is now closed with one structured customer_pressure contract on the current admin Persona surfaces and one auditable per-session frozen pressure model in PracticeSession.voice_policy_snapshot.
  rollback note: if downstream work revisits Persona realism, keep the nested customer_pressure model, the source.customer_pressure_source snapshot tag, and the current policy-health audit together; splitting those seams would bring back prompt-only drift.


- time: 2026-03-25T11:28:04+08:00
  mode: stabilize
  item id: M003-S03-T01
  files changed:
    - backend/src/common/conversation/storage.py
    - backend/src/sales_bot/services/context_manager.py
    - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/tests/unit/test_context_manager.py
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - backend/tests/unit/test_stepfun_message_helpers.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md
    - .gsd/milestones/M003/slices/S03/S03-PLAN.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added the normalized unresolved-objection ledger seam to current runtime state, persisted it via existing conversation transcript metadata, and extended StepFun reconnect snapshots plus focused unit tests without introducing a second store.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_context_manager.py tests/unit/test_stepfun_realtime_handler.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_message_helpers.py
  verification results: passed; the planned T01 backend gate finished green with 60 tests, and the extra StepFun helper suite finished green with 5 tests confirming the new whitelist/patch path.
  success signal status: unresolved objection family, promised proof, next expected evidence, and closure state now share one normalized shape across ContextManager, ConversationMessage transcript metadata, duplicate-message patching, and StepFun reconnect snapshots.
  rollback note: if later S03 tasks revisit persistence, keep the transcript_metadata-objection_ledger seam plus the StepFun runtime_state mirror together; adding new analysis keys without whitelisting both helper and storage layers will silently drop the fact.

- time: 2026-03-25T12:05:16+08:00
  mode: stabilize
  item id: M003-S03-T02
  files changed:
    - backend/src/sales_bot/websocket/components/objection_ledger_helpers.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/src/sales_bot/websocket/components/capability_processor.py
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - backend/tests/unit/test_stepfun_realtime_persistence.py
    - backend/tests/unit/test_capability_processor.py
    - .gsd/DECISIONS.md
  summary: Wired one unresolved-objection ledger through the classic and StepFun coaching paths, kept open objection pressure alive across topic drift, and shrank StepFun reconnect state down to ledger + pacing semantics so stale action cards are not replayed.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_capability_processor.py
  verification results: passed
  success signal status: unresolved objection families now survive into later turns and reconnect recovery without re-emitting the previous action-card payload on the same turn
  rollback note: if a later slice changes objection-pressure semantics, preserve the reconnect rule that action-card UI state is transient while objection_ledger + feedback_pacing_state remain the durable runtime facts

- time: 2026-03-25T12:17:45+08:00
  mode: stabilize
  item id: M003-S03-T03
  files changed:
    - backend/src/common/conversation/session_evidence.py
    - backend/tests/unit/test_session_evidence_service.py
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/components/practice/RightPanelContent.tsx
    - web/src/components/practice/RightPanelContent.test.tsx
    - .gsd/DECISIONS.md
  summary: Surfaced unresolved objection proof gaps on the shared session-evidence projection, kept the existing report/replay contract stable by overriding main_issue/next_goal from the latest open ledger, and made the practice panel keep the proof prompt while reconnect drops stale turn hints.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'latest_open_objection_ledger or preserves_insufficient_sales_evidence_fallback'
    - cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/RightPanelContent.test.tsx'
  verification results: passed
  success signal status: unresolved objection families now stay visible to learners and read-side consumers without replaying stale reconnect coaching cards
  rollback note: if later work changes objection carry-forward again, preserve the rule that transcript_metadata objection_ledger overrides generic read-side sales alignment while reconnect cleanup clears only transient action-card/fuzzy state and keeps the score proof prompt.

- time: 2026-03-25T07:31:39+08:00
  mode: stabilize
  item id: M003-S04-T01
  files changed:
    - backend/src/common/effectiveness/evaluator.py
    - backend/src/common/conversation/session_evidence.py
    - backend/tests/unit/test_effectiveness_sales_report_alignment.py
    - backend/tests/unit/test_session_evidence_service.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Defined the canonical claim-truth contract on the current evaluator/session-evidence line, classifying unsupported, weak, pending, and verified evidence without renaming the existing main_issue / next_goal report keys.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py
  verification results: passed
  success signal status: completed sales projections now expose `effectiveness_snapshot.claim_truth` and preserve objection-ledger closure semantics so open gaps stay pending while acknowledged or supported claims no longer masquerade as the same evidence state
  rollback note: if later S04 work needs to change the truth taxonomy, keep the nested `effectiveness_snapshot.claim_truth` seam and preserve the rule that only open ledgers override main_issue / next_goal while closed ledgers still inform truth-status classification.

- time: 2026-03-25T15:15:42+0800
  mode: stabilize
  item id: M003-S04
  files changed:
    - .gsd/milestones/M003/slices/S04/S04-SUMMARY.md
    - .gsd/milestones/M003/slices/S04/S04-UAT.md
    - .gsd/milestones/M003/M003-ROADMAP.md
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
  summary: Closed S04 by rerunning the full slice verification set, recording the canonical claim-truth contract across evaluator/runtime/report/replay surfaces, updating project and requirement continuity, and writing the slice summary/UAT for downstream roadmap reassessment.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
  verification results: passed; fresh slice-close backend and web gates are green, and the runtime diagnostics contract still keeps claim-truth states distinct from kb-lock chain failures.
  success signal status: S04 is complete and the same sales session can now carry unsupported/weak/pending/verified claim truth from runtime diagnostics onto the canonical report/replay surfaces without inventing a second evaluator.
  rollback note: if later work revisits claim-truth surfacing, keep `effectiveness_snapshot.claim_truth` as the shared authority line and preserve the boundary that kb-lock `blocked_*`/chain-failure states stay diagnostic-only unless a fully re-verified contract explicitly replaces it.

- time: 2026-03-25T15:28:42+0800
  mode: stabilize
  item id: M003-S05-T01
  files changed:
    - backend/tests/unit/test_stepfun_realtime_handler.py
    - backend/tests/unit/test_stepfun_knowledge_helpers.py
    - backend/tests/integration/test_knowledge_flow.py
    - backend/tests/contract/test_practice_evidence_contract.py
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Extended the objection-heavy regression net on the current runtime routes so ROI, price, competitor, and implementation-risk cases now freeze distinct pressure contracts, widen knowledge retrieval coverage, and prove pending versus verified claim-truth behavior on the shared report/replay line.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py
  verification results: passed; the exact T01 backend gate is 90/90 green and now includes explicit competitor, implementation-risk, verified-evidence, and search-failed assertions alongside the existing ROI/price paths.
  success signal status: objection-heavy realism is now pinned to the live StepFun/runtime/report contracts instead of a narrower ROI-only proof set.
  rollback note: if later S05 work rewrites objection-taxonomy semantics, keep these tests on the current `/practice` + shared evidence routes and preserve the existing status names (`weak_evidence`, `evidence_pending`, `evidence_verified`) unless the runtime contract is re-verified end-to-end.

- time: 2026-03-25T16:35:57+0800
  mode: stabilize
  item id: M003-S05-T02
  files changed:
    - .gsd/milestones/M003/slices/S05/S05-UAT.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Captured one real objection-heavy same-session evidence pack on the live localhost product chain, proving explicit customer-pressure freeze-in, live objection coaching on the practice page, canonical report/knowledge-hit facts for the same session, and the current replay blockage when post-end scoring stalls.
  verification commands:
    - browser/runtime proof: localhost dev-login -> /admin/knowledge/c6dad7ec-4673-4e00-acc1-0de190a88198 search diagnostic -> /practice/ef48ed80-0bfa-4a47-82c7-228ac3d468d2 -> /practice/ef48ed80-0bfa-4a47-82c7-228ac3d468d2/report -> /practice/ef48ed80-0bfa-4a47-82c7-228ac3d468d2/replay
    - /usr/bin/time -p sh -c 'test -s .gsd/milestones/M003/slices/S05/S05-UAT.md && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/m003-s05-t02.trace.zip && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/s05-timeline.json && test -d .artifacts/browser/2026-03-25T08-32-14-317Z-s05-report && test -d .artifacts/browser/2026-03-25T08-31-00-679Z-s05-replay'
  verification results: passed for the task gate and artifact capture; the UAT file plus browser artifacts exist on disk, the same session reached a healthy canonical report with `weak_evidence` and `knowledge-check=hit`, and replay remained explicitly blocked with `[SESSION_NOT_COMPLETED]` because the live session stayed `scoring` after backend `report_generation_failed [NO_STAGE_RESULTS]`.
  success signal status: M003 now has one honest same-session objection-heavy proof pack that shows both the working evidence line (practice -> report -> knowledge-check) and the current degraded boundary (replay/highlights blocked while scoring).
  rollback note: no product code changed in this turn; if future S05 runtime proof work reuses synthetic microphone automation, keep the delayed post-getUserMedia playback rule and continue treating report-readable / replay-blocked scoring sessions as a real degradation to document, not as a fake green replay pass.

- time: 2026-03-25T16:56:00+0800
  mode: stabilize
  item id: M003-S05-T03
  files changed:
    - .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the final M003 stability guardrail on the real admin -> practice -> report/replay chain, including measured latency bands from the same-session browser proof, the degraded states that remain shippable when canonical evidence survives, and the replay-blocked-while-scoring condition that still blocks final release acceptance.
  verification commands:
    - cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py
    - /usr/bin/time -p sh -c 'test -s .gsd/milestones/M003/slices/S05/S05-UAT.md && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/m003-s05-t02.trace.zip && test -f .artifacts/browser/2026-03-25T07-48-56-629Z-session/s05-timeline.json && test -d .artifacts/browser/2026-03-25T08-32-14-317Z-s05-report && test -d .artifacts/browser/2026-03-25T08-31-00-679Z-s05-replay'
    - rg -n "latency|degraded|fallback|block" .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
  verification results: passed; the exact objection-heavy backend regression suite is green, the live UAT trace/timeline/debug bundles are still present, and the T03 artifact now explicitly records which fallback states remain shippable versus which same-session replay failures block M003 acceptance.
  success signal status: M003 now has one written release guardrail grounded in the real localhost objection-heavy proof instead of an assumed all-green replay path.
  rollback note: if future work fixes the scoring -> completed replay path, keep the same business-chain acceptance rule and only relax the replay blocker after the live admin -> practice -> report/replay proof is re-run on the same routes.


- time: 2026-03-26T00:07:01+0800
  mode: stabilize
  item id: M004-S01-T03
  files changed:
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(dashboard)/history/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(dashboard)/history/page.test.tsx
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Carried the unified learning vocabulary through the current report and history entrypoints, so issue/goal cues stay aligned with replay/highlights and degraded enhanced-data states remain explicit without adding a new learning route.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/components/highlights/HighlightList.test.tsx' 'src/components/highlights/HighlightDetailModal.test.tsx'
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
  verification results: passed; the backend replay contract is still green, replay/highlight UI drift detectors stayed green, and the report/history/replay page suite now locks the issue/goal labels plus degraded-state copy on the existing user routes.
  success signal status: completed-session learners now see the same evidence-gap / next-goal vocabulary across report, history, replay, and highlights even when highlights or analytics overlays degrade.
  rollback note: if a future slice changes learning-cue wording, keep report/history sourced from the shared session-evidence helper and only expand beyond the current routes after the same drift-detector set is updated together.

- time: 2026-03-26T00:52:43+0800
  mode: stabilize
  item id: M004-S02-T02
  files changed:
    - web/src/lib/api/types.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Report conclusions on the current report page now expose replay deep-link CTAs based on the replay anchor contract, keep degraded anchor copy visible, and let highlight cards jump into the existing replay route by turn without adding a second learning page.
  verification commands:
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
  verification results: focused report-page Vitest passed; local browser verification on the repo web server proved the route exists but stopped short of a fully authenticated live report→replay proof because login/runtime setup did not finish within this task's time budget.
  success signal status: the current report page can now hand off the surfaced issue, next goal, and key evidence into the current replay route instead of forcing manual transcript search.
  rollback note: if T03 changes the landing semantics, keep the query-param handoff tied to replay anchors/turns from the existing replay contract rather than introducing a separate report-only resolver.

- time: 2026-03-26T01:14:18+08:00
  mode: stabilize
  item id: M004-S02-T03
  files changed:
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/milestones/M004/slices/S02/tasks/T03-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Replay now honors report deep links, auto-focuses the requested turn, and keeps degraded anchor fallback visible.
  verification commands:
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
  verification results: focused replay/report Vitest passed; a frontend-only browser stub attempt on localhost reproduced the repo's known cross-origin route-mock/CORS noise against :3444, so browser proof was not counted as product verification
  success signal status: report deep links now land inside the current replay route on the requested turn or an explicit degraded fallback state instead of forcing manual transcript search
  rollback note: if a later slice changes the report→replay handoff, keep the replay-side banner plus highlighted-turn behavior on the existing route unless a new tested landing contract replaces D066

- time: 2026-03-26T01:23:00+08:00
  mode: stabilize
  item id: M004-S02
  files changed:
    - .gsd/milestones/M004/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M004/slices/S02/S02-UAT.md
    - .gsd/milestones/M004/M004-ROADMAP.md
    - .gsd/REQUIREMENTS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M004/S02 by rerunning the full slice verification set, updating R011/project continuity, and atomically rendering the slice summary/UAT plus roadmap status for the report→replay anchor flow.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
  verification results: passed fresh; backend replay service/API suite passed 48 tests, the focused report-page Vitest passed 8 tests, and the combined replay+report run passed 12 tests while explicitly exercising both files and the resolved/degraded/missing-anchor landing behaviors.
  success signal status: the current report page can now open the existing replay route at the relevant issue/goal/highlight turn, and replay keeps explicit degraded or missing-anchor guidance instead of silently failing when markers drift.
  rollback note: if a later slice revisits this loop, keep report→replay navigation on the existing replay authority line and preserve the visible degraded-state banners unless a new tested landing contract supersedes D064-D066.

- time: 2026-03-26T01:41:45+0800
  mode: stabilize
  item id: M004-S03-T01
  files changed:
    - backend/src/common/api/practice.py
    - backend/src/common/db/schemas.py
    - backend/tests/contract/test_practice_evidence_contract.py
    - backend/tests/integration/test_practice_evidence_flow.py
    - backend/tests/integration/test_sales_value_training_flow.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Extended the existing sales retry-entry contract with a structured focus_intent derived from main_issue/next_goal and persisted the same payload into new-session voice_policy_snapshot on POST /practice/sessions.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_sales_value_training_flow.py tests/integration/test_voice_runtime_session_snapshot.py tests/contract/test_sessions.py
  verification results: passed fresh; the task suite covered report focus-intent contract plus create-session persistence, and the adjacent session/report contract suite stayed green after aligning the existing sales retry_entry expectation.
  success signal status: sales reports now hand T02/T03 one structured retry focus payload, and newly created practice sessions freeze that focus on the existing voice_policy_snapshot seam for later runtime display.
  rollback note: if later slices revise retry semantics, keep the focus payload on retry_entry + voice_policy_snapshot instead of inventing a second retry store unless a fully re-verified contract replaces D067.

- time: 2026-03-26T08:38:30+0800
  mode: stabilize
  item id: M004-S03-T03
  files changed:
    - backend/src/training_runtime/models.py
    - backend/src/training_runtime/service.py
    - backend/tests/unit/test_training_runtime_service.py
    - web/src/lib/api/types.ts
    - web/src/app/(user)/practice/[sessionId]/runtime-lock.ts
    - web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/(user)/practice/[sessionId]/page.test.tsx
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Exposed retry focus on the typed runtime descriptor, threaded it through the practice runtime-lock hook, and rendered a targeted-retry focus callout on the live practice page.
  verification commands:
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_training_runtime_service.py
    - cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts' 'src/hooks/use-practice-websocket.test.ts'
    - cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'
  verification results: passed fresh; backend runtime-descriptor coverage is green, the T01 backend contract/integration suite stayed green, the exact T02 report/replay CTA suite passed after rerunning the correctly quoted test paths, and both the practice-page focus suite and the exact T03 websocket hook command passed.
  success signal status: a learner who starts a focused retry now lands on `/practice/{sessionId}` with an explicit targeted-retry banner showing the carried-forward main issue and next goal instead of a generic blank entry state.
  rollback note: if later work revisits this entry chain, keep the learner page reading retry focus from `runtime_descriptor.focus_intent` rather than adding raw snapshot parsing or a second metadata fetch unless a broader tested runtime contract replaces D068.

- time: 2026-03-26T10:48:51+0800
  mode: stabilize
  item id: M004-S04-T02
  files changed:
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/lib/session-evidence.ts
    - web/src/lib/api/types.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Extended the shared PPT report branch to surface page-level issue-cluster cards with concrete evidence, added a focused regression for the richer page evidence UI, and kept the route on the existing presentation authority line.
  verification commands:
    - cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
    - cd web && pnpm dlx npm@11.6.1 run dev
  verification results: the focused report-page suite passed 10/10 through the temporary npm runner after repairing web node_modules with `cd web && pnpm dlx npm@11.6.1 ci`; attempted live browser proof was blocked by the pre-existing local Next install drift `Cannot find module '../server/config'` before :3445 became ready, so browser verification was not counted as product-failure evidence.
  success signal status: learners can now see which PPT page triggered which issue cluster and why it should be reworked directly on the current report route instead of inferring problems from summary text alone.
  rollback note: if T03 changes how page evidence is carried into replay, keep the report-side issue-cluster rendering sourced from `presentation_review.page_summaries[*].issue_clusters` and its diagnostics overview rather than inventing a second PPT learning payload.

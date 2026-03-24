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

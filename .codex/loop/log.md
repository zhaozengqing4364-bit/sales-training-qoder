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

- time: 2026-03-31T11:52:40+08:00
  mode: grow
  item id: M011-S02-T02
  files changed:
    - backend/src/common/knowledge_engine/intent_classifier.py
    - backend/src/common/knowledge_engine/retrieval_planner.py
    - backend/src/common/knowledge_engine/__init__.py
    - backend/tests/unit/common/test_knowledge_intent_classifier.py
    - backend/tests/unit/common/test_knowledge_retrieval_planner.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a project-owned intent classifier plus progressive retrieval planner that consume DB-normalized config and entity-resolution output, support regex/keyword/entity+keyword rules, and emit auditable rewritten query steps for downstream Haystack execution.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q
  verification results: passed; focused backend pytest finished 4/4 green after confirming the initial red state was missing classifier/planner modules, and fresh LSP diagnostics reported no issues on the new modules, exports, or focused tests.
  success signal status: normalized entity-aware queries can now be classified into DB-backed profiles and turned into deterministic progressive retrieval plans that preserve existing product-overview rewrite behavior while exposing trace/audit metadata.
  rollback note: if later control-plane work changes rule syntax or rewrite expansion vocabulary, keep the classifier/planner seam on project-owned DTOs and update the focused rule/plan tests in lockstep rather than bypassing the new modules from the Haystack adapter.

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

- time: 2026-03-30T15:49:00+08:00
  mode: grow
  item id: M010-S03-T01
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added shared frontend conclusion-evidence types and helper-owned provenance/degradation formatters, then wired the learner report page to render canonical report-driven conclusion provenance plus four-layer degradation without parsing raw contract fragments in the page.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx"
  verification results: passed; focused report-page Vitest finished 21/21 green, including happy-path sales provenance/degradation, malformed payload omission, rejected supplemental knowledge-check, and presentation-null suppression.
  success signal status: the learner report now exposes a visible helper-driven authority seam for conclusion provenance and degradation distinct from optional knowledge-check diagnostics.
  rollback note: if T02 replay parity reopens this path, keep token-to-copy mapping and malformed-fragment filtering in session-evidence.ts rather than duplicating page-local parsing.

- time: 2026-03-30T16:09:30+0800
  mode: grow
  item id: M010-S03
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M010/S03 after fresh slice-level verification confirmed learner report and replay both render helper-owned conclusion provenance and four-layer degradation from canonical payload fields, while replay keeps report snapshots retry-metadata-only.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
  verification results: passed; focused report+replay Vitest finished 33/33 green, covering shared provenance/degradation vocabulary, malformed helper inputs, supplemental knowledge-check failure isolation, stale report-snapshot non-authority, replay completion-gate behavior, retry CTA behavior, highlight/deep-link anchors, and presentation-null suppression.
  success signal status: learner-facing report and replay now show the same explanation of why each conclusion is believed and which evidence layers are degraded, without page-local truth derivation.
  rollback note: if future work changes conclusion provenance/degradation fields, keep report and replay on the shared session-evidence helper seam and preserve replay payload authority over any cached report snapshot.

- time: 2026-03-31T11:06:08+08:00
  mode: grow
  item id: M011-S01-T02
  files changed:
    - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
    - backend/tests/unit/common/test_knowledge_answer_control_plane_models.py
    - .gsd/KNOWLEDGE.md
  summary: Added the missing Alembic control-plane revision for knowledge config and answer-run audit tables, and extended the focused backend model test to fail when the migration file is absent or stops declaring the expected schema.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
  verification results: passed; focused backend pytest finished 10/10 green, and the new migration-presence assertions verified the revision exists, points to 20260328_1000_022, and names all expected control-plane/audit tables.
  success signal status: knowledge answer control-plane schema history now contains the versioned config plus answer run/step audit tables needed for future DB-backed config reads and execution-trace persistence.
  rollback note: if a future migration reshapes these tables, update the focused regression test in lockstep so ORM definitions and Alembic history cannot drift again.

- time: 2026-03-31T11:31:56+0800
  mode: grow
  item id: M011-S01
  files changed:
    - backend/src/common/knowledge_engine/__init__.py
    - backend/src/common/knowledge_engine/engine.py
    - backend/src/common/knowledge_engine/schemas.py
    - backend/src/common/knowledge_engine/config_repo.py
    - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
    - .gsd/DECISIONS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
  summary: Closed M011/S01 after fresh slice-level verification confirmed the constructable KnowledgeAnswerEngine seam, control-plane Alembic schema history, and DB-backed normalized active-config repository are all in place for downstream Haystack execution work.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q
  verification results: passed; focused backend slice-close gate finished 14/14 tests green and LSP diagnostics reported no issues on the engine, schemas, repository, migration, and focused test files
  success signal status: downstream slices can now instantiate a project-owned knowledge-answer engine and read one latest enabled active query/ranking/answerability configuration snapshot from the database without leaking Haystack types, ORM rows, or raw JSON control-plane shapes
  rollback note: if S02/S03 reshape the control-plane schema or repository snapshot, keep the project-owned engine/repository seam intact and update migration-presence plus repository-normalization regressions in lockstep rather than bypassing them in runtime handlers

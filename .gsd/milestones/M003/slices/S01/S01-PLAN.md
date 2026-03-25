# S01: 真实入口 inventory 与 current knowledge 真值线

**Goal:** Inventory and lock the real business entry chain, current knowledge status vocabulary, and accepted inspection surfaces before any richer Persona or retrieval work continues.
**Demo:** An admin can change Persona / knowledge on the current admin pages, create a sales session through `POST /api/v1/practice/sessions`, land on `web/src/app/(user)/practice/[sessionId]/page.tsx`, and then inspect on the current knowledge-check / report surfaces whether retrieval was `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, or `hit`.

## Must-Haves

- The plan names only confirmed business-code routes and authority modules that already exist in the repo today.
- The current knowledge vocabulary uses live contract terms from runtime diagnostics and current learner surfaces: `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, and `hit`.
- The slice records the blocker rule explicitly: if a required entrypoint is missing or non-runnable, stop and do inventory/spike instead of pretending the surface exists.
- Silence / Conda / `.env` / lockfile work stays out of scope for this slice unless the milestone goal is explicitly re-scoped to environment migration.

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/knowledge/kb_lock_guard.py && test -f backend/src/common/conversation/runtime_diagnostics.py && test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx`
- `rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md`
- `rg -n "Silence|Conda|\.env|lockfile|inventory/spike|current admin|current product route" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`

## Observability / Diagnostics

- Runtime signals: `knowledge-check.status`, `knowledge-check.summary`, `runtime_metrics.knowledge_retrieval.*`, `kb_lock_status`, `kb_lock_last_status`, `last_query`, `recent_queries`, and `voice_policy_snapshot_ref`.
- Status ownership: `knowledge-check.status` and the report knowledge panel stay on the current seven-status learner/admin vocabulary (`no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, `hit`); KB-lock `blocked_no_kb` / `blocked_not_ready` / `blocked_search_failed` / `blocked_empty` remain on `kb_lock_status` / `kb_lock_last_status`, and retrieval-detail statuses such as `hit_keyword_fallback` remain on `runtime_metrics.knowledge_retrieval.last_status`.
- Inspection surfaces: `GET /api/v1/practice/sessions/{id}/knowledge-check`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, and admin Persona / knowledge detail pages.
- Failure visibility: `search_failed`, `kb_not_ready`, `no_knowledge_base`, `disabled`, `not_triggered`, `miss`, plus KB-lock `blocked_no_kb` / `blocked_not_ready` / `blocked_search_failed` / `blocked_empty` remain inspectable instead of collapsing into one generic miss.
- Redaction constraints: keep secret prompt content, credentials, and raw KB document bodies out of planning artifacts; refer only to current routes, modules, and existing diagnostics.

## Integration Closure

- Upstream surfaces consumed: `web/src/app/admin/personas/[id]/page.tsx`, `web/src/app/admin/knowledge/[id]/page.tsx`, `backend/src/common/api/practice.py`, `backend/src/agent/services/persona_policy.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/common/knowledge/kb_lock_guard.py`, `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/src/common/conversation/session_evidence.py`, `web/src/app/(user)/practice/[sessionId]/page.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, and `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`.
- New wiring introduced in this slice: none — S01 only locks the business-chain contract and accepted proof surfaces.
- What remains before the milestone is truly usable end-to-end: S02-S05 still need to implement snapshot-backed Persona pressure, multi-turn objection persistence, claim-truth semantics, and live objection-heavy UAT on the current routes.

## Tasks

- [x] **T01: Lock the current admin → runtime → learner entry chain** `est:45m`
  - Why: M003 cannot claim realism work until the existing value path from admin Persona / knowledge configuration to learner-visible runtime surfaces is explicit and verified.
  - Files: `.gsd/milestones/M003/M003-ROADMAP.md`, `.gsd/milestones/M003/slices/S01/S01-PLAN.md`, `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`
  - Do: Confirm the current admin detail pages, backend authority modules, `POST /api/v1/practice/sessions` create-session route, and learner practice / report / replay routes that already move user value. Rewrite the roadmap and slice/task plans so they reference only those confirmed paths and explicitly exclude tooling-only scope.
  - Verify: `test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/api/practice.py && test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx && rg -n "persona_policy.py|voice_runtime_policy.py|voice_instruction_compiler.py|practice.py|POST /api/v1/practice/sessions|web/src/app/admin/personas/\[id\]/page.tsx|web/src/app/admin/knowledge/\[id\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx|Silence|Conda|\.env|lockfile|inventory/spike" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`
  - Done when: the M003 docs name one confirmed business chain from current admin pages to current learner practice / report / replay surfaces and explicitly reject environment/tooling-only milestone scope.

- [x] **T02: Define the live knowledge status vocabulary and ownership line** `est:60m`
  - Why: The current plan still mixes real runtime signals with invented state names, which would make downstream M003 slices drift away from the actual product contract.
  - Files: `.gsd/milestones/M003/M003-ROADMAP.md`, `.gsd/milestones/M003/slices/S01/S01-PLAN.md`, `.gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md`
  - Do: Map the current live knowledge statuses to their owning code and inspection surfaces: `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, `hit` on learner/admin-visible diagnostics, plus KB-lock block states on runtime diagnostics. Reserve richer evidence truth like unsupported / evidence-pending / evidence-backed for later slices instead of pretending it already exists.
  - Verify: `rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" backend/src/common/conversation/runtime_diagnostics.py backend/src/common/knowledge/kb_lock_guard.py backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md`
  - Done when: every status named in the M003 docs is present in current code or clearly deferred to a later slice, and no invented live status remains in S01 planning.

- [ ] **T03: Bind proof and blocker rules to current routes only** `est:45m`
  - Why: Later M003 execution needs one accepted proof surface set; otherwise the milestone will drift into placeholder APIs, hidden prompts, or non-runnable tooling artifacts.
  - Files: `.gsd/milestones/M003/M003-ROADMAP.md`, `.gsd/milestones/M003/slices/S01/S01-PLAN.md`, `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`
  - Do: Define the accepted proof classes and inspection surfaces for the rest of M003 using only current product routes: admin Persona detail, admin knowledge detail, practice page, knowledge-check, report, and replay. Record the rule that missing or non-production entrypoints force inventory/spike before any implementation work starts.
  - Verify: `test -f web/src/app/admin/personas/\[id\]/page.tsx && test -f web/src/app/admin/knowledge/\[id\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx && test -f backend/src/common/api/practice.py && rg -n "knowledge-check|report|replay|inventory/spike|focused backend|focused web|live UAT" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`
  - Done when: the rest of M003 has one explicit proof surface set on current routes and one blocker rule that prevents execution on guessed code paths.

## Files Likely Touched

- `.gsd/milestones/M003/M003-ROADMAP.md`
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md`
- `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`

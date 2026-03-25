---
id: M003
provides:
  - Frozen `customer_pressure` session snapshots on the current admin Persona/knowledge -> session create -> practice runtime chain.
  - Persisted unresolved objection ledgers plus one shared `effectiveness_snapshot.claim_truth` contract across runtime diagnostics, knowledge-check, report, and replay read paths.
  - One live admin Persona/knowledge -> practice -> knowledge-check -> report proof on current routes, with explicit evidence that replay/highlights are still blocked by `status="scoring"` / `[SESSION_NOT_COMPLETED]` on the same chain.
key_decisions:
  - Keep the accepted M003 entry chain on the current admin Persona/knowledge detail routes, `POST /api/v1/practice/sessions`, learner practice runtime, knowledge-check/report, and replay via `backend/src/common/conversation/api.py` + `backend/src/common/conversation/replay.py`.
  - Freeze Persona pressure as nested `customer_pressure` in `PracticeSession.voice_policy_snapshot` and inspect `source.customer_pressure_source` instead of inferring behavior from compiled prompt prose.
  - Keep unsupported/weak/pending/verified evidence semantics on `effectiveness_snapshot.claim_truth`, distinct from KB-lock blocked/detail statuses.
patterns_established:
  - Persist multi-turn sales-realism facts on existing pass-through seams (`voice_policy_snapshot`, `transcript_metadata`, runtime snapshots) instead of inventing parallel storage.
  - Keep the public learner/admin vocabulary small and stable while richer blocked/detail states stay in diagnostics.
  - Milestone close-out must compare the roadmap’s planned slices against actual slice directories and summary/UAT files before any completion claim.
observability_surfaces:
  - GET /api/v1/practice/sessions/{id}/knowledge-check
  - GET /api/v1/practice/sessions/{id}/report
  - GET /api/v1/sessions/{id}/replay
  - PracticeSession.voice_policy_snapshot.customer_pressure / source.customer_pressure_source
  - ConversationMessage.transcript_metadata.objection_ledger
  - effectiveness_snapshot.claim_truth
  - runtime_metrics.knowledge_retrieval.*, kb_lock_status, kb_lock_last_status
requirement_outcomes: []
duration: 2026-03-25 close-out audit
verification_result: failed
completed_at: 2026-03-25T18:13:17+08:00
---

# M003: 知识与角色真实性

**Built the S01-S05 knowledge/persona realism chain through canonical report on current routes, but the milestone failed close-out because S06 is missing and the accepted replay/highlights proof is still blocked behind `status="scoring"`.**

## What Happened

M003 started by locking the work to the real business chain instead of designing against imagined seams. S01 fixed the authority line on the current admin Persona detail page, admin knowledge detail page, `POST /api/v1/practice/sessions`, learner practice runtime, knowledge-check, canonical report, and replay via the conversation API. It also froze the public learner/admin knowledge vocabulary at the seven live statuses (`no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, `hit`) and kept richer blocked/detail states in diagnostics.

S02 and S03 then made Persona and objection pressure durable instead of prompt-shaped. Persona pressure now normalizes into one canonical nested `customer_pressure` contract, current admin Persona surfaces can edit and audit it, and session creation freezes that contract into `PracticeSession.voice_policy_snapshot` with `source.customer_pressure_source`. On top of that frozen session truth, unresolved objection ledgers now persist on `ConversationMessage.transcript_metadata["objection_ledger"]` and reconnect-safe runtime snapshots, so price / competitor / proof gaps survive topic drift and flow back into report/replay `main_issue` and `next_goal`.

S04 aligned the read side around one claim-truth contract instead of introducing a second evaluator. Runtime diagnostics, `/api/v1/practice/sessions/{id}/knowledge-check`, canonical `/api/v1/practice/sessions/{id}/report`, and `/api/v1/sessions/{id}/replay` now share `effectiveness_snapshot.claim_truth` semantics (`unsupported_claim`, `weak_evidence`, `evidence_pending`, `evidence_verified`) while KB-lock blocked states remain diagnostic-only. S05 then proved the live admin Persona/knowledge -> practice -> knowledge-check -> report chain on current routes: objection-heavy coaching showed up in runtime, the frozen session exposed `customer_pressure_source="explicit"`, `knowledge-check.status` reached `hit`, and the canonical report stayed readable even when optional enhanced insights/highlights degraded.

The close-out failed at the final milestone boundary, not at the code-exists check. The working branch contains real implementation code, and the implemented S01-S05 surfaces verify cleanly on focused backend/web suites. But the milestone still lacks S06 entirely: `.gsd/milestones/M003/slices/S06/` has no plan, summary, or UAT artifact, and the accepted same-session replay/highlights proof is still blocked by `status="scoring"`, `report_generation_failed [NO_STAGE_RESULTS]`, `no_scoring_context_available`, and `[SESSION_NOT_COMPLETED]` on the replay/highlights endpoints. Separately, the roadmap’s strict “business-code directories only” wording was not met literally, because the implemented claim-truth and client-contract work also required shared seams such as `backend/src/common/effectiveness/*` and `web/src/lib/api/*`.

## Cross-Slice Verification

- **Implementation-backed branch, not planning-only:** `git diff --stat "$(git merge-base HEAD 001-ai-practice-system)" HEAD -- ':!.gsd/'` returned non-`.gsd/` code changes across **105 files** with **20630 insertions** and **2253 deletions**. This proves the working branch contains real implementation, not only milestone artifacts.
- **Definition-of-done artifact check failed:** `for s in S01 S02 S03 S04 S05 S06; do ...; done` confirmed `S01`-`S05` each have `PLAN/SUMMARY/UAT`, while `S06-PLAN.md`, `S06-SUMMARY.md`, and `S06-UAT.md` are all missing. The milestone cannot pass close-out while a planned slice has no execution artifacts.
- **Focused backend verification for the implemented contract passed:** `venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py tests/integration/test_voice_runtime_session_snapshot.py tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py tests/unit/test_persona_policy.py tests/unit/test_stepfun_realtime_persistence.py -q` completed with **39 passed**. This covers frozen Persona pressure snapshots, knowledge-check runtime statuses, report/replay claim-truth alignment, objection-ledger read-side projection, and reconnect-safe minimal StepFun persistence.
- **Focused web verification for the implemented surfaces passed:** `cd web && npm test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/admin/knowledge/[id]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"` completed with **5 files passed / 23 tests passed**. This rechecked the current admin Persona/knowledge surfaces, learner report/replay rendering, and reconnect UI behavior.
- **Criterion 1 — admin Persona/knowledge config freezes into session/runtime on the current chain:** **Met.** S01-S02 evidence plus the passing backend/web suites confirm that current admin surfaces feed `POST /api/v1/practice/sessions`, freeze `voice_policy_snapshot.customer_pressure`, and continue through current practice/report/replay seams.
- **Criterion 2 — learner/admin surfaces distinguish the live seven-status knowledge vocabulary:** **Not fully met.** The passing backend suites verify the seven-status knowledge-check contract and keep KB-lock `blocked_*` states in diagnostics, and the canonical report remains readable on the same proof chain. But the accepted replay surface is still blocked on the same live proof session by `status="scoring"` / `[SESSION_NOT_COMPLETED]`, so this criterion is not retired across all accepted read surfaces.
- **Criterion 3 — Persona pressure stays stable across turns and reconnect:** **Met for the delivered S01-S05 scope.** The passing backend current-contract suite includes reconnect-safe snapshot tests, and the passing web websocket suite verifies reconnect behavior while preserving the objection-proof prompt line.
- **Criterion 4 — slices stay only inside the roadmap’s listed business-code directories:** **Not met as written.** The implemented milestone needed shared contract seams outside the literal allowlist, notably `backend/src/common/effectiveness/*` for claim-truth alignment and `web/src/lib/api/*` for admin/practice contract plumbing.
- **Definition of done:** **Failed.** The roadmap still has an unfinished planned slice in practice, all slice summaries do not exist (`S06` missing), and the key cross-slice acceptance point — same-session `scoring -> completed` so replay/highlights load canonical evidence instead of `[SESSION_NOT_COMPLETED]` — is still open.
- **Additional verification note:** running `venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py tests/integration/test_sales_realtime_reconnect_flow.py tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py tests/unit/test_persona_policy.py -q` produced **21 passed / 1 failed** because `tests/integration/test_sales_realtime_reconnect_flow.py` still expects persisted `latest_action_card` in the reconnect snapshot. The current contract intentionally keeps only minimal `feedback_pacing_state`, so that test is stale proof, not the milestone’s primary blocker.

## Requirement Changes

- None. **R010 remains active** — S01-S05 materially advanced it, but the milestone did not validate the full requirement because the accepted same-session replay/highlights surface is still blocked and S06 has not been executed.

## Forward Intelligence

### What the next milestone should know
- Finish the missing S06 on the same accepted proof chain before reopening any new realism work. The next meaningful proof is not “report still renders”; it is one objection-heavy session moving from `scoring` to `completed` so replay/highlights read the same evidence line the report already can.

### What's fragile
- The report/replay split is real: canonical `/practice/{sessionId}/report` can stay readable from persisted evidence while `/sessions/{id}/replay` and `/sessions/{id}/highlights` still fail the completed-session gate. That can look like a frontend routing issue if you do not check session status, report-generation logs, and replay endpoint payloads together.

### Authoritative diagnostics
- Start with `GET /api/v1/practice/sessions/{id}/knowledge-check`, `GET /api/v1/practice/sessions/{id}/report`, `GET /api/v1/sessions/{id}/replay`, `PracticeSession.status`, and backend logs carrying `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available`. Those signals tell you whether you have a real replay-completion blocker, a knowledge/runtime issue, or only optional enhancement noise.

### What assumptions changed
- “All slices are done” was false. The close-out step has to verify roadmap slice IDs against actual slice directories and summary/UAT files.
- “Keep the milestone inside a narrow set of business-code directories” was too tight for the real implementation. Shared seams such as `common/effectiveness` and `web/src/lib/api` are part of the current product contract and need to be named explicitly if future milestones want a literal directory boundary.

## Files Created/Modified

- `.gsd/milestones/M003/M003-SUMMARY.md` — wrote the milestone close-out record with fresh verification evidence, unmet criteria, and the remaining blocker line.
- `.gsd/PROJECT.md` — updated current project state to record the failed M003 close-out audit, the missing S06 artifacts, and the remaining replay/highlights gate.
- `.gsd/KNOWLEDGE.md` — appended reusable close-out lessons about slice/artifact parity, shared contract seams, and the stale reconnect snapshot test expectation.

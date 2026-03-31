---
id: S03
parent: M011
milestone: M011
provides:
  - A slot-coverage answerability seam that returns sufficient/partial/insufficient/blocked verdicts with audit-ready coverage metadata.
  - A deterministic evidence-driven answer assembler that emits learner-safe blocked copy, numbered grounded final text, normalized citations, and unsupported claims.
  - A persisted answer-run audit seam (`KnowledgeAnswerRun` + ordered `KnowledgeAnswerRunStep`) for later inspection and debugging.
  - Compatibility readers that carry audit_run_id, answerability, rewritten_queries, and citations into existing realtime payloads, runtime diagnostics, and replay metadata.
requires:
  - slice: S02
    provides: The retrieval-truth seam (`entity_resolution`, `intent`, `retrieval_plan`, `execution_trace`, reranked rows) that S03 now classifies, assembles, audits, and mirrors into compatibility payloads.
affects:
  - S04
key_files:
  - backend/src/common/knowledge_engine/answerability.py
  - backend/src/common/knowledge_engine/assembler.py
  - backend/src/common/knowledge_engine/audit_repo.py
  - backend/src/common/knowledge_engine/engine.py
  - backend/src/common/knowledge_engine/compat.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/conversation/replay.py
  - backend/tests/unit/common/test_knowledge_answer_audit_repo.py
  - backend/tests/unit/common/test_knowledge_answer_engine.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - backend/tests/unit/test_replay_service.py
key_decisions:
  - D149: evaluate slot coverage from row-level or metadata slot arrays and fall back to count-based verdicts when no answerability profile exists.
  - D150: treat snippet-backed rows as supported claims and downgrade content-only rows into `unsupported_claims`, with fixed learner-safe blocked copy for blocked answerability.
  - D151: expose audit_run_id, citations, and answerability through a dedicated compatibility mapper on existing realtime/runtime/replay seams instead of leaking raw engine DTOs.
  - D152: persist ordered `KnowledgeAnswerRunStep` payloads per answer run so future debug/report tooling can inspect real execution without reconstructing handler-local state.
patterns_established:
  - Keep answerability, answer assembly, audit persistence, and compatibility mapping on project-owned seams rather than rebuilding them in handlers or route readers.
  - Preserve slot annotations (`slot_hits` / `coverage_slots`) and quoteable snippets all the way through the row pipeline; dropping either silently weakens answerability or learner-safe assembly.
  - Treat the persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` pair as the future inspection authority seam for debug/eval/report work.
  - Use a compatibility mapper to project engine truth onto existing runtime/replay payloads so downstream surfaces stay stable while the engine internals evolve.
observability_surfaces:
  - Persisted `knowledge_answer_runs` / `knowledge_answer_run_steps` rows via `KnowledgeAnswerAuditRepository`.
  - Realtime `knowledge_answer_diagnostics` on emitted StepFun `tts_audio` payloads.
  - Runtime diagnostics / knowledge-check `knowledge_answer_diagnostics` via `build_session_runtime_diagnostics(...)`.
  - Replay `messages[*].transcript_metadata.knowledge_answer_diagnostics`.
  - Focused backend verification gates for answerability, assembler, audit repo, engine orchestration, StepFun handler compatibility, runtime diagnostics compatibility, and replay preservation.
drill_down_paths:
  - .gsd/milestones/M011/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M011/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M011/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-31T05:37:18.036Z
blocker_discovered: false
---

# S03: Coverage answerability、answer assembly 与 compatibility seam

**S03 closed the first grounded-answer compatibility seam: coverage-based answerability, deterministic evidence assembly, persisted answer-run audits, and compat payloads now line up across StepFun runtime, runtime diagnostics, and replay metadata.**

## What Happened

S03 turned the M011/S02 retrieval-truth seam into a grounded answering seam with durable auditability. T01 introduced a project-owned `KnowledgeAnswerabilityEvaluator` that reads required/optional slot coverage from `slot_hits` / `coverage_slots` on evidence rows (or their metadata), preserves blocked retrieval semantics, and degrades to hit-count verdicts when no answerability profile exists yet. T02 then added a deterministic `KnowledgeAnswerAssembler` that only turns snippet-backed evidence into learner-facing `final_text` and normalized `citations`, emits a fixed learner-safe `blocked_text` when answerability is blocked, and keeps non-snippet rows in `unsupported_claims` instead of letting ungrounded assertions leak into the answer body. T03 completed the persistence and compatibility seam: `KnowledgeAnswerAuditRepository` now writes one `KnowledgeAnswerRun` plus ordered `KnowledgeAnswerRunStep` rows per answer, `KnowledgeAnswerEngine` orchestrates config → resolve → classify → plan → retrieve → rank → answerability → assemble → audit, and `common.knowledge_engine.compat` maps the engine contract back onto the existing payload seams so runtime consumers can see `audit_run_id`, `answerability`, `rewritten_queries`, and `citations` without importing raw engine DTOs.

Fresh slice-close verification proved the shipped compatibility behavior on the current surfaces. The engine/audit tests proved a real answer run can normalize `请介绍一下世袭科技` to the canonical entity, assemble one grounded answer, and persist a durable audit row with ordered step payloads. The StepFun handler tests proved strict KB mode blocks unsupported grounded answers with learner-safe copy, partial mode retains only supported sentences, and emitted `tts_audio` payloads now carry `knowledge_answer_diagnostics` including `answerability`, `audit_run_id`, `rewritten_queries`, and `citations`. The runtime diagnostics tests proved the current `knowledge-check`/runtime diagnostics seam exposes the same live `knowledge_answer_diagnostics` bundle. The replay tests proved assistant-message `transcript_metadata.knowledge_answer_diagnostics` survives through replay payload generation, so downstream readers can trace a replayed answer back to the same audit truth line. In practice, after one grounded knowledge answer, the system can now preserve the same answerability/citation/audit identity across engine output, realtime payloads, runtime diagnostics, and replay metadata.

This slice also established two important downstream patterns. First, answerability, answer assembly, audit persistence, and compat mapping stay project-owned even when retrieval execution underneath may evolve; future slices should extend these seams instead of rebuilding answerability or learner copy in handlers. Second, the persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows are now the intended inspection seam for S04. The current async StepFun helper preserves the same compatibility contract on shipped runtime surfaces, but the repo should not assume every current runtime path already delegates through one direct synchronous `KnowledgeAnswerEngine.answer(...)` call. S04 should therefore build debug/report/eval inspection on the persisted audit seam and existing compat payloads rather than reconstructing execution from handler-local state or overstating direct canonical report consumption that is not yet proven at slice close-out.

## Verification

Fresh slice-close verification reran every S03 plan gate serially from repo root and all passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answerability.py -q` (5/5), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_assembler.py -q` (3/3), and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py -q` (134/134). Fresh LSP diagnostics on `backend/src/common/knowledge_engine/engine.py`, `compat.py`, `audit_repo.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/src/common/api/practice.py`, `backend/src/common/conversation/runtime_diagnostics.py`, and `backend/src/common/conversation/replay.py` all reported no diagnostics.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice plan language implied a broader report/replay/runtime-diagnostics compatibility closure than the verified code currently proves. At slice close-out, the compatibility proof is strongest on StepFun realtime payloads, runtime diagnostics/knowledge-check, and replay transcript metadata; canonical completed-session report payloads are not yet a first-class reader of the knowledge-answer audit seam and remain an explicit S04 follow-up.

## Known Limitations

The strongest close-out proof today is on engine output, StepFun realtime payloads, runtime diagnostics/knowledge-check, and replay transcript metadata. Canonical completed-session report payloads are not yet a first-class reader of the knowledge-answer audit seam, there is no dedicated recent-run debug API yet, and the async StepFun helper still preserves the compatibility contract through its existing orchestration path rather than a fully unified direct engine invocation path.

## Follow-ups

S04 should expose a recent-run/debug inspection surface on top of persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows, and it should decide deliberately whether canonical completed-session report payloads need to mirror knowledge-answer audit fields instead of assuming that report compatibility is already closed by S03.

## Files Created/Modified

- `backend/src/common/knowledge_engine/answerability.py` — Added the coverage-based answerability evaluator that reads required/optional slot coverage and preserves blocked compatibility semantics.
- `backend/src/common/knowledge_engine/assembler.py` — Added deterministic learner-safe answer assembly with numbered final text, citations, blocked copy, and unsupported-claim handling.
- `backend/src/common/knowledge_engine/audit_repo.py` — Added durable persistence for one answer run plus ordered audit step rows.
- `backend/src/common/knowledge_engine/engine.py` — Added the project-owned orchestration seam that runs config → resolve → classify → plan → retrieve → rank → answerability → assemble → audit.
- `backend/src/common/knowledge_engine/compat.py` — Added the compatibility mapper that exposes engine output on existing runtime/replay payload seams.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — Preserved the shipped StepFun search payload contract while carrying answerability diagnostics alongside retrieval truth.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — Propagated knowledge-answer diagnostics into response guardrails, blocked-copy behavior, and emitted realtime payloads.
- `backend/src/common/conversation/runtime_diagnostics.py` — Threaded live knowledge-answer diagnostics into the runtime diagnostics read model.
- `backend/src/common/conversation/replay.py` — Kept knowledge-answer diagnostics available on replay message transcript metadata.
- `backend/src/common/api/practice.py` — Passed live knowledge-answer diagnostics into the knowledge-check/runtime diagnostics path.

---
id: M011
title: "M011"
status: complete
completed_at: 2026-03-31T07:00:18.420Z
key_decisions:
  - D143 project-owned KnowledgeAnswerEngine seam with soft-imported Haystack factory
  - D144 repository-owned normalized active-config snapshot DTOs instead of ORM row leakage
  - D145 close control-plane schema-history drift with a real Alembic revision plus migration-presence regression
  - D146 deterministic alias/canonical entity resolution with explicit traces before fuzzy NLP
  - D147 project-owned intent-classifier and retrieval-planner DTO seam
  - D148 integrate the engine through the existing StepFun search seam with safe legacy fallback
  - D149 slot-coverage answerability with count fallback when no profile exists
  - D150 snippet-backed supported-claim assembly with unsupported claims downgraded out of learner-facing final text
  - D151 compatibility mapper for runtime/replay consumers instead of raw engine DTO leakage
  - D152 persisted KnowledgeAnswerRun / KnowledgeAnswerRunStep as the inspection authority seam
  - D153 fixture-driven real-engine evaluation harness
  - D154 read-only debug API backed directly by persisted run/step audit rows
  - D155 compat-seam rollout control with legacy / enabled / dual-run modes and session-backed shadow audits
key_files:
  - backend/src/common/knowledge_engine/engine.py
  - backend/src/common/knowledge_engine/config_repo.py
  - backend/src/common/knowledge_engine/entity_resolver.py
  - backend/src/common/knowledge_engine/intent_classifier.py
  - backend/src/common/knowledge_engine/retrieval_planner.py
  - backend/src/common/knowledge_engine/haystack_adapter.py
  - backend/src/common/knowledge_engine/reranker.py
  - backend/src/common/knowledge_engine/answerability.py
  - backend/src/common/knowledge_engine/assembler.py
  - backend/src/common/knowledge_engine/audit_repo.py
  - backend/src/common/knowledge_engine/compat.py
  - backend/src/common/knowledge_engine/evaluation.py
  - backend/src/common/api/knowledge_debug.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/conversation/replay.py
  - backend/scripts/seed_knowledge_answer_config.py
  - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
  - backend/tests/evaluation/test_knowledge_answer_engine_eval.py
  - backend/tests/integration/test_knowledge_debug_api.py
  - backend/tests/unit/common/test_knowledge_answer_feature_flag.py
lessons_learned:
  - For knowledge-answer work, build on project-owned seams and compat readers rather than leaking Haystack types or ORM rows into runtime/report/replay consumers.
  - Persisted `KnowledgeAnswerRun` and ordered `KnowledgeAnswerRunStep` rows are the inspection authority seam; debug and rollout tooling should read them directly instead of reconstructing handler-local execution stories.
  - Milestone close-out proof for this subsystem needs all three late-slice tiers together: deterministic eval coverage, read-only debug inspection, and compat/rollout verification across backend and web consumers.
  - In this repo, repo-root backend pytest commands still share the top-level `.coverage` SQLite file, so milestone-close backend gates must be rerun serially unless coverage output is isolated.
  - Safe rollout is best enforced at one compat seam with explicit legacy / enabled / dual-run modes and session-backed shadow audits, rather than scattering feature-flag branches across runtime helpers.
---

# M011: M011

**M011 closed the knowledge-answering overhaul by shipping a database-driven, auditable, debuggable Haystack-backed engine seam with grounded answerability, recent-run inspection, deterministic evaluation, and safe rollout controls on the existing StepFun runtime path.**

## What Happened

M011 turned the repository’s patch-style knowledge Q&A behavior into a project-owned backend subsystem with durable control-plane, execution, audit, debug, and rollout seams. S01 established the constructable `KnowledgeAnswerEngine` seam, the Alembic-backed control-plane schema history, and the normalized active-config repository so runtime code could consume one stable config snapshot instead of ORM rows or raw JSON. S02 then used that seam to deliver deterministic entity resolution, DB-backed intent classification, progressive retrieval planning, config-driven retrieval execution, and explainable business reranking on the existing StepFun internal knowledge search entrypoint while preserving the legacy fallback path when no active config exists. S03 converted retrieval truth into grounded answer truth by adding slot-coverage answerability, deterministic snippet-backed answer assembly, persisted `KnowledgeAnswerRun` / ordered `KnowledgeAnswerRunStep` audit rows, and compatibility projections that carry `audit_run_id`, `answerability`, `rewritten_queries`, and `citations` into realtime payloads, runtime diagnostics, and replay metadata. S04 completed the operational closure with a fixture-driven eval harness, a read-only `/api/v1/knowledge-debug` inspection API, idempotent starter-config seeding, and explicit legacy / enabled / dual-run compat rollout modes that keep shadow-vs-live behavior inspectable without breaking learner-visible contracts.

## Verification Summary

Milestone-level verification was rerun fresh during close-out instead of relying only on slice-close notes. Code-change verification used the repo’s actual integration branch (`origin/001-ai-practice-system`) via `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` and confirmed substantial non-`.gsd` implementation changes, including the new `backend/src/common/knowledge_engine/*` seam, runtime integration, debug API, seed script, tests, and compat/rollout wiring. Fresh milestone-close verification also reran the S04 proof stack serially to avoid the known repo-root pytest-cov `.coverage` SQLite race: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q` passed 6/6, `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q` passed 5/5, the focused backend compatibility/rollout suite passed 197/197, and `npm --prefix web test -- --run src/hooks/websocket/message-handlers.test.ts src/components/ui/chat-bubble.test.tsx "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` passed 68/68.

## Decision Re-evaluation

| Decision | Re-evaluation | Evidence | Next-milestone action |
|---|---|---|---|
| D143 project-owned engine seam over direct Haystack types | Still valid | S01-S04 all built on the seam without leaking Haystack types into runtime/replay/debug consumers. | Keep. |
| D144 normalized config snapshot DTOs instead of ORM rows | Still valid | S02-S04 consumed config metadata (`config_version_id`, `config_version_name`, `profile_source`) through repository-owned DTOs and debug/rollout surfaces stayed explainable. | Keep. |
| D145 close missing schema-history gap with Alembic revision + regression | Still valid | Migration-presence proof remained part of the backend verification stack and no contradictory schema drift surfaced during later slices. | Keep. |
| D146 deterministic entity resolution before fuzzy NLP | Still valid for this milestone | Product-introduction-class retrieval behavior, traces, and evals passed without needing fuzzier matching. | Revisit only if future retrieval evidence shows deterministic aliases are insufficient. |
| D147 project-owned intent/planner DTO seam | Still valid | S02-S04 preserved auditable planner output and compat rollout without reconnecting to legacy helper-local heuristics. | Keep. |
| D148 integrate through existing StepFun search seam with safe legacy fallback | Still valid | Runtime behavior stayed inspectable and safe when config is missing; later rollout work reused the same seam. | Keep. |
| D149 slot-coverage answerability with count fallback | Still valid | S03 grounded answerability and S04 evals passed while tolerating mixed row metadata shapes. | Keep, but revisit if stricter slot semantics are needed. |
| D150 snippet-backed supported claims / unsupported-claims downgrade | Still valid | Learner-safe assembly, citations, and blocked copy stayed deterministic and auditable through verification. | Keep. |
| D151 compat mapper for runtime/replay consumers | Still valid | Realtime/runtime/replay consumers received audit/citation/answerability truth without taking raw engine DTO dependencies. | Keep. |
| D152 persisted run/step audit as inspection authority | Still valid | `/api/v1/knowledge-debug` and rollout/debug work in S04 relied directly on persisted runs/steps successfully. | Keep. |
| D153 fixture-driven real-engine eval harness | Still valid | Fresh close-out eval rerun passed 6/6 and provided deterministic regression proof for intro/pricing/comparison/coaching/blocked cases. | Keep. |
| D154 read-only debug API backed by persisted audit rows | Still valid | Fresh debug API integration verification passed 5/5 and delivered recent-run list/detail/steps inspection. | Keep. |
| D155 compat-seam rollout with legacy/enabled/dual-run modes | Still valid | Fresh focused backend suite passed 197/197 and rollout diagnostics/shadow-audit behavior remained inspectable without destabilizing learner-visible payloads. | Keep. |

## Cross-slice Outcome

The milestone’s promised assembled outcome is now real end to end. One query can flow from DB-backed config selection to deterministic entity resolution, intent/planner output, executed retrieval traces, explainable reranked evidence, answerability, learner-safe answer assembly, persisted run/step audit rows, compat diagnostics on realtime/runtime/replay surfaces, recent-run debug inspection, and deterministic regression coverage. That closes the original M011 vision: the knowledge-answering path is no longer a handler-local patch chain but a database-driven, configurable, auditable, debuggable subsystem with an explicit rollout seam.

## Success Criteria Results

- ✅ **S01 foundation seam and DB control plane** — Met. S01 delivered the constructable `KnowledgeAnswerEngine` seam, the Alembic control-plane schema history, and the normalized `KnowledgeAnswerConfigRepository`. Fresh supporting evidence remains in the slice-close tests: engine seam 2/2, control-plane models/migration presence 10/10, repository snapshot behavior 2/2.
- ✅ **S02 query understanding, planner, and retrieval execution** — Met. S02 delivered deterministic entity resolution, DB-backed intent classification, progressive retrieval planning, executed-step tracing, and explainable reranked results on the StepFun internal knowledge search path. Slice-close verification proved this with entity resolver 3/3, intent/planner 4/4, and adapter/reranker/runtime integration 16/16.
- ✅ **S03 answerability, answer assembly, and compatibility seam** — Met. S03 delivered slot-coverage answerability verdicts, deterministic citation-backed assembly, persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` audit rows, and compat payloads carrying the same audit truth into realtime payloads, runtime diagnostics, and replay metadata. Freshly reviewed slice evidence plus slice-close verification passed answerability 5/5, assembler 3/3, and engine/audit/runtime/replay compatibility 134/134.
- ✅ **S04 evaluation, debug API, and rollout** — Met. Fresh milestone-close verification reran the planned S04 proof stack and all passed: eval harness 6/6, debug API integration 5/5, focused backend compatibility/rollout suite 197/197, and web compatibility suite 68/68. This directly proves recent-run inspection and product-introduction-class regression coverage now exist on the shipped subsystem.
- ✅ **Milestone vision** — Met. The shipped system is now database-driven, configurable, auditable, and debuggable, with Haystack as the execution substrate behind project-owned seams and learner/runtime contracts preserved via compat mapping and rollout gating.

## Definition of Done Results

- ✅ **All slices complete** — Verified. The roadmap shows S01-S04 all marked done, and `find .gsd/milestones/M011/slices -maxdepth 2 -name '*-SUMMARY.md' | sort` confirmed `S01-SUMMARY.md` through `S04-SUMMARY.md` all exist.
- ✅ **All slice summaries exist** — Verified. All four slice summaries are present on disk, together with their PLAN/UAT/task artifacts under `.gsd/milestones/M011/slices/`.
- ✅ **Cross-slice integration works** — Verified from delivered artifacts and fresh proof. S01’s engine/config seam is consumed by S02 retrieval execution; S02’s retrieval-truth seam is consumed by S03 answerability/audit/compat; S03’s persisted audit seam is consumed by S04 debug/eval/rollout surfaces. Fresh S04 milestone-close reruns (6/6, 5/5, 197/197, 68/68) confirmed the assembled late-slice integration still works.
- ✅ **Real code landed outside planning artifacts** — Verified. `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` reported substantial non-`.gsd` code changes, including backend engine/runtime/debug/compat/seed/test files.
- ✅ **Horizontal checklist** — No separate horizontal checklist was rendered in the current M011 roadmap, so there were no additional horizontal items to retire.

## Requirement Outcomes

No requirement status transitions occurred during M011. The execution context, slice summaries, and milestone verification all agree on **Requirements Advanced: None**, **Requirements Validated: None**, and **Requirements Invalidated or Re-scoped: None**. M011 therefore closes as a capability-foundation milestone whose evidence proves the new knowledge-answer subsystem, but does not change requirement states in `.gsd/REQUIREMENTS.md`.

## Deviations

The main close-out deviation was verification-process-only rather than product-scope: the repo does not have a `main` ref, so code-change verification had to use the equivalent integration branch `origin/001-ai-practice-system`, and backend proof had to be rerun serially because repo-root pytest-cov still shares a `.coverage` SQLite file. Product scope otherwise matched the milestone plan.

## Follow-ups

No milestone-blocking follow-up remains inside M011. Future milestones can extend retrieval quality, richer answerability semantics, or broader learner/report surfacing, but they should build on the shipped authority seams (`KnowledgeAnswerRun` / `KnowledgeAnswerRunStep`, `/api/v1/knowledge-debug`, and `common.knowledge_engine.compat`) instead of reintroducing handler-local truth lines.

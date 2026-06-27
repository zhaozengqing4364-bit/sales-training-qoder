---
slug: realtime-it-leader-roleplay-v1
status: drafting
intent: clear
pending-action: write .omo/plans/realtime-it-leader-roleplay-v1.md
approach: Reuse the existing sales_bot StepFun realtime policy/compiler/knowledge/scoring surfaces, add the smallest v1 sample assets and runtime hooks needed to freeze roleplay contract, maintain a lightweight state card, constrain knowledge visibility, and produce offline evidence-based scoring reports.
---

# Draft: realtime-it-leader-roleplay-v1

## Components (topology ledger)
<!-- Lock the SHAPE before depth. One row per top-level component that can succeed or fail independently. -->
<!-- id | outcome (one line) | status: active|deferred | evidence path -->
- C1 | V1 sample assets exist for roleplay_contract, state_card, knowledge visibility, scoring rubric, and regression transcript structure | active | .trellis/tasks/06-23-15-v1/prd.md; docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md
- C2 | Existing VoiceRuntimePolicyService / VoiceInstructionCompiler freeze and render the v1 roleplay contract without creating a parallel realtime path | active | CodeGraph exploration: VoiceRuntimePolicyService, VoiceInstructionCompiler, StepFunRealtimeHandler
- C3 | Realtime session state card is persisted/updated outside the hot audio path and injected as a short stage anchor | active | backend/src/sales_bot/AGENTS.md; docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md
- C4 | Knowledge tool usage respects customer-visible vs scoring-only knowledge boundaries | active | CONTEXT.md KnowledgeConfigVersion/RagProfile and Visible/Hidden Information Scope; backend/src/common/knowledge/internal_searcher.py
- C5 | Offline scoring produces learner/admin report with rubric, evidence, consistency checks, and low-confidence review flag | active | .trellis/tasks/06-23-15-v1/prd.md
- C6 | Regression and QA evidence prove the v1 sample does not drift, leak hidden information, or produce unsupported scoring | active | .omo/plans/realtime-it-leader-roleplay-v1.md

## Open assumptions (announced defaults)
<!-- Record any default you adopt instead of asking, so the user can veto it at the gate. -->
<!-- assumption | adopted default | rationale | reversible? -->
- Start with backend/sample assets and service seams before UI | Use existing admin/practice UI later; first make runtime/scoring artifacts testable | User explicitly wanted technically feasible v1 and current system already has broad UI surfaces | yes
- No new DB migration in first implementation wave unless existing snapshot fields cannot safely store the v1 structures | Prefer existing voice_policy_snapshot / runtime_state / curriculum_snapshot style storage | Minimizes risk in a dirty worktree and matches Ponytail constraints | yes
- Scoring is offline and test-driven using fixture transcripts | Do not call live LLM in unit tests; use structured fakes and prompt/schema tests | Backend rules forbid unit tests hitting real LLM/TTS APIs | yes
- Knowledge visibility is enforced at assembly/tool-policy boundaries first | Do not build a new knowledge permission system for v1 | Existing Roleplay Contract visible/hidden scope and tool policy concepts are enough for the sample | yes
- Manual QA for first executable slice can be CLI/data-shaped | Use tests plus a script/pytest artifact validating compiled prompt/report JSON, not browser UI | v1 deliverable is runtime behavior and report structure, not new UI | yes

## Findings (cited - path:lines)
- `.trellis/tasks/06-23-15-v1/prd.md` defines the v1 fixed scenario, roleplay contract, state card, knowledge split, offline scoring, dual report view, and out-of-scope boundaries.
- `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md` records the approved product/architecture design and acceptance expectations.
- `CONTEXT.md` already defines Roleplay Contract, Visible Information Scope, Hidden Information Scope, KnowledgeConfigVersion vs RagProfile, and configuration tracks. Plan must reuse these terms.
- `backend/src/sales_bot/AGENTS.md` marks `websocket/` as the dominant complexity hotspot and points voice policy work to `services/voice_instruction_compiler.py` and `services/voice_runtime_policy.py`.
- CodeGraph found `VoiceRuntimePolicyService`, `VoiceInstructionCompiler`, `StepFunRealtimeHandler`, and `search_internal_knowledge` as existing authorities for policy compilation, realtime handling, and internal KB tool use.
- `.trellis/spec/backend/prompt-template-governance.md` says live StepFun voice instruction contracts are governed by sessions, voice-runtime, and personas, not prompt template CRUD.
- Backend quality rules forbid real LLM/TTS calls in unit tests and require mocks/fakes.
- Metis plan-risk review found plan-blocking gaps before implementation: entry track must be fixed to platform direct practice, `sales_trainer` realtime must stay untouched, 6-item scoring must be compatible with existing 5-dimension evaluation, 4 roleplay phases must not become a third sales stage model, permissions/failure/rollback/observability must be explicit, and the 9 regression sample structure must be defined.

## Decisions (with rationale)
- Reuse existing realtime authority instead of adding a new runtime. Rationale: sales_bot StepFun path is already the current sales voice practice runtime and the local AGENTS explicitly warns not to reintroduce legacy runtime paths.
- Treat `roleplay_contract` and `session_state_card` as runtime data contracts with schema tests before changing live WebSocket behavior. Rationale: v1 risk is drift/leakage, not UI.
- Keep scoring offline and evidence-based. Rationale: user explicitly questioned scoring reliability; rules plus LLM judge is more defensible than pure keyword scoring or realtime self-scoring.
- Add regression fixtures early. Rationale: the product success criterion is effect stability after prompt/model/knowledge changes.
- Platform entry decision: v1 implementation uses platform direct practice `/practice/[sessionId]` and existing StepFun voice runtime policy snapshots. It does not enable `sales_trainer` realtime placeholder and does not route through curriculum `PracticeTemplate` for v1.
- Scoring compatibility decision: keep the 6-item 100-point rubric as a versioned v1 report projection; do not remove or redefine existing 5 coaching dimensions unless a compatibility mapper is explicitly added.
- Phase model decision: opening/discovery/credibility/next_step are roleplay phases/views, not new `SalesStageCapability` stages.

## Scope IN
- V1 sample roleplay contract, state card, knowledge visibility, scoring rubric, and transcript fixture structures.
- Minimal backend service/compiler changes required to inject frozen roleplay contract and short state card anchors into StepFun realtime instructions.
- Knowledge policy separation for customer-visible and scorer-only content at assembly/tool-use boundaries.
- Offline scoring/report structure with learner/admin outputs, original evidence, and rule consistency checks.
- Focused unit/contract tests and one data/CLI-shaped manual QA artifact.
- Implementation-boundary documentation patch that resolves entry track, scoring compatibility, permissions, failure, rollback, observability, and regression sample acceptance before product code changes.

## Scope OUT (Must NOT have)
- New full UI or large admin configuration center.
- Multi-industry or multi-role free configuration.
- Long-term customer memory across multiple visits.
- Realtime coach interruption or realtime scoring.
- Model fine-tuning.
- New realtime WebSocket runtime or reintroduction of legacy sales handlers.
- Every-turn mandatory retrieval.

## Open questions
- None blocking. User approved v1 scope and start-work. Defaults above are reversible if later vetoed.

## Approval gate
status: approved-by-start-work
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->
pending-action: append decision-complete todos to .omo/plans/realtime-it-leader-roleplay-v1.md, then execute through delegated subagents.

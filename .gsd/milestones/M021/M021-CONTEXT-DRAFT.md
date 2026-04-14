# M021: AI control plane / prompt / evaluation kernel 统一

**Gathered:** 2026-04-14
**Status:** In progress

## Project Description

This milestone consolidates the project’s AI control plane around the paths that are actually online today. The current system mixes StepFun realtime runtime, compiled voice instruction snapshots, knowledge-answer rollout seams, PromptTemplateService governance, legacy evaluation/report services, and classic voice scoring. M021 starts by freezing a truthful live/compat/shadow inventory, then uses that inventory to unify prompt compilation, evaluation truth, and AI quality/failure surfaces without breaking shipped consumers prematurely.

## Why This Milestone

The repository already has multiple AI-looking seams, but they do not all have the same authority level. StepFun realtime, voice-policy snapshot compilation, classic scoring helpers, optional comprehensive reports, and knowledge-answer rollout code all coexist. Without an explicit inventory, downstream work will keep editing the wrong layer — for example treating PromptTemplateService or `/evaluation/*` as the live sales runtime authority when the real learner path runs through StepFun and `voice_policy_snapshot`.

## User-Visible Outcome

### When this milestone is complete, the user can:

- rely on one stable prompt/runtime contract across live practice, report, replay, and diagnostics instead of seeing prompt/score/report semantics drift by path
- inspect AI failures, degradations, and knowledge-answer rollout state through truthful support/admin surfaces instead of silent fallback behavior

### Entry point / environment

- Entry point: learner `/practice/{sessionId}` websocket/runtime flow, learner `/practice/{sessionId}/report`, admin prompt/knowledge-answer governance endpoints
- Environment: local dev and production-like backend + web runtime
- Live dependencies involved: database, Redis reconnect snapshot state, StepFun realtime upstream, knowledge retrieval, browser frontend

## Completion Class

- Contract complete means: every AI/runtime/prompt/score/report seam used by M021 slices is labeled live / compat / shadow / retire-candidate with real callers and consumers
- Integration complete means: prompt compilation, evaluation truth, and knowledge-answer diagnostics read from the same declared authority seams across runtime and read-side consumers
- Operational complete means: AI failures/degradations stay inspectable through existing diagnostics surfaces rather than being hidden by default text or default scores

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- learner sales and presentation sessions use one declared live AI runtime authority and no longer depend on undocumented prompt/evaluation side paths
- report, replay, history, and support/admin diagnostics can explain which AI path produced the visible output and whether it was live, compat, or degraded
- legacy evaluation and classic scoring consumers are either still explicitly supported as compatibility surfaces or are retired with replacement proof; they cannot remain ambiguous

## Architectural Decisions

### AI runtime authority starts from the StepFun/session-snapshot seam

**Decision:** Treat `sales_bot/websocket/stepfun_realtime_handler.py` plus `voice_runtime_policy.py` and `voice_instruction_compiler.py` as the live AI runtime authority for StepFun-backed sessions.

**Rationale:** That seam owns the shipped realtime audio session, compiled instruction contract, tool policy, knowledge retrieval, claim-truth/runtime diagnostics, and persisted message/evidence state. It is the only place where learner-visible live practice behavior is fully assembled.

**Alternatives Considered:**
- `PromptTemplateService` as the live prompt authority — rejected because it governs templates and some compat helpers but does not own the active StepFun instruction snapshot
- `evaluation/services/*` as the live scoring/report authority — rejected because canonical completed-session truth already sits on `/practice/sessions/{id}/report` + `SessionEvidenceService`

### Knowledge-answer rollout authority stays on the compat seam

**Decision:** Treat `common.knowledge_engine.compat` as the rollout authority seam, with `engine.py` shadow-by-default unless rollout flags explicitly promote it.

**Rationale:** The shipped runtime/debug callers both go through the compat layer, and learner-visible payload shape plus rollout diagnostics (`legacy` / `enabled` / `dual_run`) are controlled there.

**Alternatives Considered:**
- Directly treating `engine.py` as always-live — rejected because default repo behavior still resolves rollout mode to `legacy`
- Handler-local rollout branching — rejected because it would split learner-visible behavior from audit/debug behavior

### Legacy evaluation stays compatibility-only until a canonical kernel replaces it

**Decision:** Keep `evaluation/services/*`, `evaluation/api.py`, `/practice/*/comprehensive-report`, and classic scoring helpers classified as compatibility/enhancement surfaces until M021 explicitly retires or replaces them.

**Rationale:** They still have shipped callers (`legacy` voice mode, enhanced report generation, `report_status` surfaces), so they are not safe to label dead. But they are also not the canonical learner/admin truth line.

**Alternatives Considered:**
- Mark them retire-now — rejected because classic mode and enhanced-report consumers still exist
- Keep them unlabeled — rejected because the lack of a label is exactly what causes downstream mis-edits

## Error Handling Strategy

This milestone favors truthful labeling over optimistic abstraction. When a path is optional, degraded, rollout-gated, or compatibility-only, the context and architecture scan must say so explicitly. Downstream slices should preserve existing user-facing fallback behavior, but they must also preserve the diagnostic seam that explains which authority path ran, which one did not, and whether the visible output came from live runtime truth, a compat reader, or a shadow rollout.

## Risks and Unknowns

- Knowledge-answer rollout mode can differ by environment — the code default is legacy, but enabled/dual-run may be active elsewhere, so slices must keep the compat seam as the authority boundary
- Classic voice mode is still user-selectable — removing or ignoring its scoring/evaluation helpers too early would break a shipped compatibility path
- Optional comprehensive-report surfaces still drive `report_status` diagnostics — retiring them requires replacing those consumers, not just deleting the services

## Existing Codebase / Prior Art

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — live sales StepFun runtime authority
- `backend/src/sales_bot/services/voice_runtime_policy.py` — resolves effective runtime policy and tool/prompt contract
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — compiles the frozen instruction contract recorded in session snapshots
- `backend/src/common/knowledge_engine/compat.py` — rollout authority seam for legacy/enabled/dual-run knowledge-answer behavior
- `backend/src/common/knowledge_engine/engine.py` — grounded-answer engine invoked only through compat rollout control today
- `backend/src/prompt_templates/service.py` — live prompt governance surface and compat runtime helper, but not the StepFun prompt authority
- `backend/src/evaluation/services/*` — classic scoring plus optional comprehensive-report enhancement stack
- `backend/src/common/conversation/session_evidence.py` — canonical completed-session read model that downstream evaluation work must not bypass

## Relevant Requirements

- No new requirement IDs are recorded yet for M021 — this milestone context exists to stop authority drift before prompt/evaluation/kernel slices change the live contract

## Scope

### In Scope

- label the current AI/runtime/prompt/score/report seams by authority level with real entrypoints, callers, and consumers
- establish the downstream rule for which code paths M021 S02-S04 may treat as live versus compat/shadow
- persist that rule in long-lived GSD artifacts so later slices can cite it directly

### Out of Scope / Non-Goals

- removing legacy evaluation/classic scoring paths in this first slice
- changing user-visible runtime/report behavior beyond writing the inventory
- redesigning support/admin diagnostics outside the already-shipped authority seams

## Technical Constraints

- the learner-visible StepFun runtime must keep `voice_policy_snapshot` and compiled instruction/hash as the current prompt/runtime authority
- knowledge-answer rollout behavior must stay compatible with `legacy`, `enabled`, and `dual_run` modes exposed by `common.knowledge_engine.compat`
- optional comprehensive-report and classic scoring consumers cannot be deleted until their remaining callers are either migrated or explicitly retired in later slices

## Integration Points

- StepFun realtime websocket runtime — live learner-facing AI session behavior
- session snapshots / runtime diagnostics — carry compiled prompt contract, tool policy, and live knowledge diagnostics into read-side surfaces
- `SessionEvidenceService` — canonical completed-session truth line that later evaluation unification must continue to feed
- prompt governance endpoints — admin-side template control plane that remains separate from the live StepFun prompt authority
- knowledge-answer audit/debug surfaces — rollout/debug inspection for the same compat seam used by runtime

## Testing Requirements

This slice is inventory-first, so proof is artifact and grep based. Verification must show the documented authority map is grep-discoverable across the architecture scan and the source files named in the task plan. Later slices should add focused runtime/compat tests where they actually change behavior; this first slice only needs to prove that downstream planning and debugging can quote a truthful live/compat/shadow map without rediscovering it.

## Acceptance Criteria

- architecture scan contains a concrete M021/S01 table that labels the major AI paths as live / compat / shadow / retire-candidate and names their callers/consumers
- milestone context explains which seams later M021 slices must treat as live runtime authority versus compatibility or rollout surfaces
- the task-plan grep gate still exposes the expected AI-path source files after the write-back

## Open Questions

- When M021/S02 unifies prompt control, should `PromptTemplateService` remain admin-only governance or become an input to compiled live contracts through one explicit adapter?
- When M021/S03 replaces the canonical evaluation kernel, which current `report_status` consumers must continue reading optional comprehensive-report state versus migrating to projection-backed quality events?
- When M021/S04 promotes AI quality/cost/failure events, which subset should become learner-visible versus remaining support/admin-only diagnostics?
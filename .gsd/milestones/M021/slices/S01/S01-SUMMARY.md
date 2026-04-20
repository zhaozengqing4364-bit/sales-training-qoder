---
id: S01
parent: M021
milestone: M021
provides:
  - One authoritative live/compat/shadow inventory for AI/runtime/prompt/score/report seams.
  - A consumer-facing doc contract that answers which AI path is live without rereading the full architecture scan.
  - A keep/compat/retire migration matrix for M021/S02-S04, plus explicit legacy-consumer guardrails.
requires:
  - slice: M020’s auth/support/runtime/recovery authority seams remain the foundation for the later M021 slices, especially the support-runtime diagnostics boundary used by future quality-event work.
    provides: 
affects:
  - S02
  - S03
  - S04
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - docs/api-contract/sessions.md
  - docs/api-contract/prompt-templates.md
  - docs/api-contract/support-runtime.md
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - backend/tests/unit/common/test_knowledge_answer_feature_flag.py
  - backend/tests/unit/test_report_generation_trigger.py
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D230 — Use the S01 must-keep / compat / retire-candidate matrix as the execution authority for M021/S02-S04.
  - D231 — Treat the StepFun realtime handler plus compiled voice-policy/session-snapshot seam as the live AI runtime authority for M021 unification work.
  - D232 — Treat `docs/api-contract/sessions.md` and `docs/api-contract/prompt-templates.md` as the durable consumer-facing authority docs for the M021 split, while `support-runtime.md` remains a support/read-side explainer.
patterns_established:
  - Inventory live-vs-compat seams before attempting control-plane unification.
  - When authority changes, sync architecture scan + consumer-facing API contracts + focused proof files together.
  - Express downstream migration as a keep/compat/retire matrix instead of prose-only notes.
observability_surfaces:
  - `docs/api-contract/support-runtime.md` now explicitly documents that `/api/v1/support/runtime/*` is a release-health/read-side surface, not a live AI authority surface.
  - Focused authority proof now lives in `test_voice_runtime_session_snapshot.py`, `test_knowledge_answer_feature_flag.py`, and `test_report_generation_trigger.py`, giving later slices an explicit seam-level verification bundle.
drill_down_paths:
  - .gsd/milestones/M021/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M021/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M021/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T01:57:58.586Z
blocker_discovered: false
---

# S01: Live AI authority inventory

**Mapped the shipped AI/runtime/prompt/score/report seams into one live/compat/shadow/retire inventory, synced that map into proof/docs, and handed S02-S04 a keep/compat/retire execution matrix so later unification work stops targeting the wrong authority.**

## What Happened

## What this slice actually delivered

This slice did not change the live AI behavior itself; it changed the team’s shared understanding of **which code paths already own live behavior** so M021 can unify the right seams instead of fighting shadows.

### T01 — live/compat/shadow inventory
- Wrote a concrete M021/S01 authority inventory into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` section 7.3.1.
- Locked the current shipped truth as:
  - `sales_bot/websocket/router.py -> stepfun_realtime_handler.py` = **live learner runtime authority**
  - `voice_runtime_policy.py + voice_instruction_compiler.py` = **live compiled prompt/runtime contract authority**
  - `presentation_stepfun_realtime_handler.py` = **live adapter on the same StepFun runtime seam**
  - `stepfun_internal_knowledge_searcher.py + common.knowledge_engine.compat` = **live rollout seam** for knowledge-answer mode / diagnostics
  - `common.knowledge_engine.engine.py` = **shadow by default; live only when enabled**
  - `PromptTemplateService` = **live governance + compat runtime helper**, not live StepFun prompt authority
  - classic scoring + legacy evaluation/report stack = **compat runtime / compat enhancement / retire candidate**, not canonical truth
- Persisted the same milestone context as `M021-CONTEXT-DRAFT.md` because final `CONTEXT` remains depth-gated and auto-mode cannot clear the human verification step.

### T02 — proof and contract sync
- Added explicit authority wording to the focused proof files so tests now state which seam they protect:
  - `backend/tests/integration/test_voice_runtime_session_snapshot.py` locks the **live StepFun/session-snapshot** authority line.
  - `backend/tests/unit/common/test_knowledge_answer_feature_flag.py` locks the **compat-owned knowledge rollout seam** and its enabled/dual-run/shadow behavior.
  - `backend/tests/unit/test_report_generation_trigger.py` locks the **optional enhanced-report sidecar** as compatibility/enhancement rather than canonical report truth.
- Synced the same split into consumer-facing docs:
  - `docs/api-contract/sessions.md` now says live runtime/read-side consumers all anchor on the frozen session snapshot + canonical evidence line.
  - `docs/api-contract/prompt-templates.md` now says prompt templates are governance/control-plane surfaces with runtime-adjacent compat consumers, not live StepFun prompt authority.
  - `docs/api-contract/support-runtime.md` stays the support/read-side explainer and explicitly does **not** become a second live AI authority document.
- Recorded the documentation choice as decision **D232**.

### T03 — downstream execution matrix
- Converted the descriptive inventory into an execution-ready matrix in both the architecture scan and `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`.
- Classified the real seams into:
  - **must keep**: StepFun realtime runtime, compiled voice snapshot, knowledge compat rollout seam
  - **compat**: PromptTemplateService governance surface, classic scoring path
  - **retire candidate**: staged/comprehensive evaluation, report trigger, `/evaluation/*`, `common/ai/llm_service.py::evaluate/generate_report`
- Wrote the explicit no-brute-delete guardrail for the still-live consumers: classic `voice_mode == "legacy"`, `report_status` / comprehensive-report readers, manual `/evaluation/*` flows, PromptTemplateService admin/runtime helpers, and knowledge compat debug/audit readers.
- Recorded the downstream migration rule as **D230**, and the live AI authority choice as **D231**.

## Patterns this slice established
- **Inventory before unification**: downstream slices must first identify the live authority seam, then unify around it, instead of treating file names like `PromptTemplateService` or `comprehensive_report` as proof of authority.
- **Three-way sync for authority changes**: analysis inventory + consumer-facing contract docs + focused proof files must all move together. If one changes alone, later slices will reintroduce authority drift.
- **Keep/compat/retire matrix as handoff artifact**: later slices should consume the matrix directly rather than rediscovering live-vs-compat status from scratch.

## Operational Readiness

Even though S01 is mostly an inventory/documentation slice, it establishes runtime-operational guidance for every later M021 change.

- **Health signal**: the architecture scan, API-contract docs, and focused proof files all agree that StepFun + compiled snapshot is the live AI authority and that legacy evaluation/report surfaces remain compatibility readers.
- **Failure signal**: a later slice starts changing `PromptTemplateService`, `/evaluation/*`, or `common/ai/llm_service.py::evaluate/generate_report` as if they were the live runtime authority, or it deletes a compat path while its shipped consumers still exist.
- **Recovery procedure**: go back to architecture scan §7.3.1 + the T03 matrix, rerun the slice verification bundle, then restore doc/proof alignment before changing behavior again.
- **Monitoring gaps**: authority alignment is still proven by focused tests + grep-backed contract checks, not by a machine-checked generated contract or a runtime-owned authority registry. `M021-CONTEXT.md` is also still blocked on human depth verification, so downstream research should continue to use `M021-CONTEXT-DRAFT.md` until that gate is cleared.


## Verification

Fresh slice-close verification reran every slice-plan gate plus the focused proof bundle that anchors the new authority wording. `rg -n "PromptTemplateService|generate_report|evaluate\(|stepfun|knowledge_answer|voice_instruction|compiled" backend/src/sales_bot backend/src/evaluation backend/src/prompt_templates backend/src/common backend/src/presentation_coach` exited 0 and still shows the intended StepFun / prompt-template / evaluation / knowledge seams. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py::test_start_session_persists_voice_policy_snapshot backend/tests/integration/test_voice_runtime_session_snapshot.py::test_snapshot_baseline_is_immutable_and_report_replay_refer_same_baseline backend/tests/unit/common/test_knowledge_answer_feature_flag.py backend/tests/unit/test_report_generation_trigger.py -q` passed 15/15, with only non-blocking pytest-cov no-data warnings from the focused run. `rg -n "live|compat|shadow|retire|authority" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md docs/api-contract backend/tests` exited 0 and showed the expected authority wording across analysis, docs, and proof files. `rg -n "must keep|compat|retire candidate|consumer" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` exited 0 and confirmed the downstream matrix/consumer guardrails. LSP diagnostics on `backend/tests/integration/test_voice_runtime_session_snapshot.py`, `backend/tests/unit/common/test_knowledge_answer_feature_flag.py`, and `backend/tests/unit/test_report_generation_trigger.py` all returned `No diagnostics`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None from slice scope. The only carried limitation is that final `M021-CONTEXT.md` is still blocked by the milestone depth-verification gate, so this slice intentionally relied on `M021-CONTEXT-DRAFT.md` instead of bypassing the gate.

## Known Limitations

Final milestone `CONTEXT` promotion still requires human depth verification. The AI authority split is documented and tested, but it is not yet enforced by a machine-generated contract; later M021 slices still depend on the grep-backed proof and focused suites added here.

## Follow-ups

1. M021/S02 must unify compiled prompt control on the StepFun/session-snapshot seam without promoting PromptTemplateService back to live runtime authority. 2. M021/S03 must migrate `report_status` / comprehensive-report / `/evaluation/*` consumers back toward the canonical evidence/report line before retiring legacy evaluation surfaces. 3. M021/S04 must expose quality/cost/failure/mode events through the existing knowledge compat seam and the existing admin/support diagnostics contract, not through a second support payload.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Added section 7.3.1 live AI authority inventory, the downstream rules, and the keep/compat/retire matrix.
- `docs/api-contract/sessions.md` — Added the M021/S01 authority boundary block for the session snapshot, runtime mode, and canonical read-side consumers.
- `docs/api-contract/prompt-templates.md` — Added the M021/S01 prompt-governance versus live runtime authority split.
- `docs/api-contract/support-runtime.md` — Kept support/runtime positioned as release-health/read-side contract instead of a second AI control-plane spec.
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — Annotated the focused proof for the live StepFun/session-snapshot authority seam.
- `backend/tests/unit/common/test_knowledge_answer_feature_flag.py` — Annotated the compat-owned knowledge rollout seam and enabled/dual-run/shadow behavior.
- `backend/tests/unit/test_report_generation_trigger.py` — Annotated the enhanced-report path as compatibility/enhancement rather than canonical report truth.
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` — Added the M021 S02-S04 input matrix and legacy-consumer guardrails.
- `.gsd/KNOWLEDGE.md` — Appended M021/S01 authority-baseline and CONTEXT-DRAFT gotchas for future agents.
- `.gsd/PROJECT.md` — Refreshed project state to show M021/S01 completion and the current M021 follow-on focus.

---
id: T01
parent: S01
milestone: M021
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/milestones/M021/M021-CONTEXT-DRAFT.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Treat the StepFun/session-snapshot seam as the live AI runtime authority for M021 work instead of PromptTemplateService or `/evaluation/*`.
  - Treat `common.knowledge_engine.compat` as the rollout authority seam; `engine.py` remains shadow-by-default unless explicitly enabled.
  - Keep classic scoring and comprehensive-report services labeled as compatibility/enhancement surfaces until later M021 slices can retire or replace their shipped consumers.
duration: 
verification_result: passed
completed_at: 2026-04-14T01:37:46.977Z
blocker_discovered: false
---

# T01: Added the M021 live/compat/shadow AI authority inventory to the architecture scan and milestone context draft.

**Added the M021 live/compat/shadow AI authority inventory to the architecture scan and milestone context draft.**

## What Happened

I traced the shipped AI/runtime/prompt/score/report seams from the actual code paths instead of relying on file names. The inventory now distinguishes the live StepFun runtime authority (`sales_bot/websocket/stepfun_realtime_handler.py` plus `voice_runtime_policy.py` and `voice_instruction_compiler.py`), the live presentation StepFun adapter, the compat-owned knowledge-answer rollout seam (`common.knowledge_engine.compat` + `stepfun_internal_knowledge_searcher.py`), the shadow-by-default engine (`common.knowledge_engine.engine.py`), the live-but-governance-oriented PromptTemplateService surface, and the still-shipped compatibility evaluation stack (`realtime_scoring.py`, `ai_scoring.py`, `staged_evaluation.py`, `comprehensive_report.py`, `report_generation_trigger.py`, `evaluation/api.py`). I wrote that map into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` as a concrete M021/S01 subsection with callers, consumers, and labels, then prepared milestone context content and persisted it as `.gsd/milestones/M021/M021-CONTEXT-DRAFT.md` because the canonical CONTEXT artifact is depth-gated and auto-mode cannot perform the required human confirmation step. I also updated `.codex/loop/state.json` and `.codex/loop/log.md` so the next single-item iteration starts from the new AI authority map rather than the previous M020 recovery close-out state.

## Verification

Ran the exact task-plan grep gate across the intended backend source trees to confirm the relevant StepFun, prompt-template, evaluation, knowledge-answer, and voice-instruction seams are still the live code surfaces being inventoried. Then ran a focused artifact check to confirm the architecture scan now exposes the concrete M021/S01 labels (`live rollout seam`, `shadow by default; live only when enabled`, `compat enhancement / retire candidate`) and that the milestone context content was persisted to `.gsd/milestones/M021/M021-CONTEXT-DRAFT.md`. Both commands exited 0.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "PromptTemplateService|generate_report|evaluate\(|stepfun|knowledge_answer|voice_instruction|compiled" backend/src/sales_bot backend/src/evaluation backend/src/prompt_templates backend/src/common backend/src/presentation_coach` | 0 | ✅ pass | 150ms |
| 2 | `rg -n "M021/S01 live AI authority inventory|live rollout seam|compat enhancement / retire candidate|shadow by default; live only when enabled" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md && test -f .gsd/milestones/M021/M021-CONTEXT-DRAFT.md` | 0 | ✅ pass | 19ms |

## Deviations

The task plan expected `.gsd/milestones/M021/M021-CONTEXT.md`, but `gsd_summary_save` hard-blocked final `CONTEXT` creation because M021 lacks depth verification and auto-mode cannot call `ask_user_questions`. I persisted the same material as `M021-CONTEXT-DRAFT.md` instead of bypassing the gate.

## Known Issues

Final `M021-CONTEXT.md` is still blocked on human depth verification; downstream slices should use `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` section 7.3.1 plus `.gsd/milestones/M021/M021-CONTEXT-DRAFT.md` until that gate is cleared.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/milestones/M021/M021-CONTEXT-DRAFT.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`

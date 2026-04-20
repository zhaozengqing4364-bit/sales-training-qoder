---
id: S05
parent: M001
milestone: M001
provides:
  - Live sales training now scores, prompts, knowledge diagnostics, and reports against value articulation, customer benefit, evidence usage, objection handling, and next-step progression while preserving the unified evidence contract.
requires:
  - slice: S02
    provides: unified session evidence projection and canonical report/replay contract
  - slice: S04
    provides: persona-policy → voice-policy snapshot → knowledge-check materials authority line
affects:
  - S06
  - S08
key_files:
  - backend/src/agent/capabilities/realtime_scoring.py
  - backend/src/agent/services/persona_policy.py
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/api/practice.py
  - web/src/components/practice/ScorePanel.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - backend/tests/integration/test_sales_value_training_flow.py
key_decisions:
  - Preserve existing report/pass_flag keys, but remap their meaning to sales value-articulation, evidence-benefit, and objection-progression semantics via shared write-layer helpers (D024).
  - Normalize sales-focus persona extensions in persona_policy, compile them into the existing voice instruction contract, and widen objection retrieval through stepfun_knowledge_helpers instead of creating a second materials path (D025).
patterns_established:
  - Sales semantics belong in the active StepFun write path and persona/runtime contract, not in SessionEvidenceService or frontend read-side recomputation.
  - Price / competitor / ROI / proof prompts reuse the existing knowledge-helper retrieval path with widened entity-query tuning instead of a parallel KB contract.
  - Web consumers stay aligned with the canonical report contract by relabeling existing rollup fields rather than introducing new top-level score keys.
observability_surfaces:
  - score_update.dimension_scores / overall_score
  - practice_session_evidence_persisted
  - practice_session_evidence_not_evaluable
  - GET /api/v1/practice/sessions/{id}/knowledge-check
  - GET /api/v1/practice/sessions/{id}/report
  - web/src/components/practice/ScorePanel.tsx
  - PracticeSession.effectiveness_snapshot.main_issue / next_goal
  - ConversationMessage.score_snapshot.overall_score
  - PracticeSession.voice_policy_snapshot / voice_policy_snapshot_ref
drill_down_paths:
  - .gsd/milestones/M001/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S05/tasks/T03-SUMMARY.md
duration: 5h+
verification_result: passed
completed_at: 2026-03-23T23:10:00+08:00
---

# S05: 销售价值表达与异议处理基线

**Sales practice now evaluates and pressures against product value translation, customer benefit, evidence, and objection handling on the same evidence line that report, replay, and diagnostics already trust.**

## What Happened

S05 finished the semantic turn that M001 still needed after S02/S04: the system no longer had a generic communication scorer and a separate sales story in the UI. The active StepFun write path, persona/runtime contract, knowledge diagnostics, and report labels now describe the same sales baseline.

Task-wise, the slice closed in three layers:

1. **Write-layer sales rubric and effectiveness snapshot**
   - `RealtimeScoringCapability` switched to five sales dimensions: `价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`.
   - StepFun session flush, terminal fallback, and effectiveness snapshot generation now share `build_sales_rollup_scores(...)` and `build_sales_effectiveness_metrics(...)`.
   - Existing top-level contract keys stayed in place (`logic_score / accuracy_score / completeness_score`, `pass_flags.*`, `overall_result`, `main_issue`, `next_goal`, `evaluable`, `not_evaluable_reason`), but their meaning changed to sales semantics instead of old generic talk-skill semantics.

2. **Persona-policy and retrieval contract alignment**
   - `persona_policy` now standardizes sales-focus extensions such as value axes, objection axes, and expected customer questions.
   - `VoiceInstructionCompiler` compiles those fields into the same voice/runtime contract already frozen in `voice_policy_snapshot`.
   - Price / competitor / ROI / proof prompts stay on the existing `stepfun_knowledge_helpers` path, with widened entity-query tuning for objection-style retrieval rather than a second KB integration route.

3. **Live/report consumer alignment and slice proof**
   - `ScorePanel` now renders the new five sales dimensions and still handles unknown/legacy labels safely.
   - The report page relabels the preserved rollup fields as `价值表达 / 证据与收益 / 异议推进`, and the top report sections now surface a sales result, sales main issue, sales next goal, and relabeled pass flags.
   - A backend integration proof (`test_sales_value_training_flow.py`) now locks the report API to the sales-specific `main_issue`, `next_goal`, rollups, and snapshot references that the UI consumes.

As closer, I also updated one stale failure-path unit test (`test_apply_latest_scores_to_session_supports_legacy_overall_and_marks_zero_turn_not_evaluable`) so it matches the shipped S05 contract: legacy `overall`-only snapshots now normalize into the sales rollup instead of preserving the old 90/82/80 generic split.

## Verification

Slice-level verification was re-run from the plan and passed:

- `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py`
- `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

Operational/runtime proof was also exercised on a live local stack (`backend` on `:3444`, `web` on `:3445`) with a bound sales session:

- A real StepFun sales session was created from the web UI.
- Live turns covering value translation, price objection, competitor objection, and proof/case demand produced sales-specific `score_update` payloads and updated the live page with:
  - `实时评分`
  - five sales dimensions (`价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`)
  - action-card guidance in sales language
  - `knowledge-check` recent queries/status tied to those prompts.
- After session end, the canonical `/practice/{sessionId}/report` page showed:
  - sales-specific `main_issue`
  - sales-specific `next_goal`
  - relabeled pass flags (`价值翻译达标 / 异议承接达标 / 证据推进达标`)
  - rollups labeled `价值表达 / 证据与收益 / 异议推进`
  - `知识库命中检测` with hit-rate/recent-query evidence.

Failure-path verification also passed after refreshing the stale legacy-fallback expectation:

- zero-turn not-evaluable fallback remains explicit
- `knowledge-check` still distinguishes `hit / miss / kb_not_ready / search_failed`
- report/replay contract still agrees on canonical score/evaluable fields even when legacy score keys are involved.

## Requirements Advanced

- R011 — unified session evidence now carries sales-specific value/evidence/objection semantics instead of generic communication labels, so later slices can build trends and learning surfaces on the same evidence line.

## Requirements Validated

- R003 — validated by the passing backend/web slice suites plus live runtime proof showing value/price/competitor/proof prompts driving sales-specific score updates, knowledge diagnostics, and canonical report output.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The only deviation from the written slice plan during close-out was verification-side: one legacy-fallback unit test still expected the pre-S05 generic rollup mapping, so it was updated to assert the shipped S05 sales normalization (`overall`-based rollup when only legacy generic labels are present). No product logic changed in the closer pass.

## Known Limitations

- S06 still has to aggregate these new sales categories across sessions; this slice only proves the single-session baseline.
- S07 still needs to bring the same value/evidence/objection semantics into PPT post-session review where relevant.
- The report page still treats comprehensive-report and highlights as optional enhancement layers; those endpoints may be unavailable while the canonical unified report remains correct.
- Local StepFun runtime can still produce reconnect / upstream-noise logs during long manual sessions; the core evidence/report contract remained intact in this slice, but S08 should tighten the final observability story.

## Follow-ups

- S06 should aggregate `价值表达 / 证据与收益 / 异议推进` into supervisor trend views instead of inventing a second category system.
- S08 should explicitly classify optional enhancement failures (comprehensive report / highlights) so they do not make local health checks look like core report regressions.

## Files Created/Modified

- `backend/src/agent/capabilities/realtime_scoring.py` — replaced the generic scorer with the five-dimension sales rubric and preserved canonical + legacy-compatible payload shape.
- `backend/src/common/effectiveness/evaluator.py` — centralized sales rollup/effectiveness helpers that now drive session-level rollups and sales-specific `main_issue` / `next_goal`.
- `backend/src/agent/services/persona_policy.py` — normalized sales-focus persona extension fields.
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — compiled sales-focus persona policy into the single runtime instruction contract.
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — widened objection-style retrieval tuning for price/competitor/ROI/proof prompts.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — persisted the sales rollup/effectiveness snapshot and kept runtime diagnostics on the StepFun write path.
- `backend/src/common/api/practice.py` — kept report fallback/effectiveness sync aligned with the new sales semantics.
- `backend/tests/integration/test_sales_value_training_flow.py` — locked the canonical report API to the new sales rollups, `main_issue`, and `next_goal`.
- `web/src/components/practice/ScorePanel.tsx` — rendered the five sales dimensions in the live score panel.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — relabeled rollups/pass flags and surfaced sales-specific report sections.
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — updated the legacy-overall fallback assertion to the shipped sales-rollup contract.
- `.gsd/REQUIREMENTS.md` — marked R003 validated with S05 proof.
- `.gsd/KNOWLEDGE.md` — captured the legacy fallback and optional enhancement gotchas discovered during close-out.
- `.gsd/PROJECT.md` — refreshed current project state with S05 completion.
- `.gsd/milestones/M001/M001-ROADMAP.md` — marked S05 done.

## Forward Intelligence

### What the next slice should know
- The authoritative S05 semantics are now: live `score_update` → StepFun persisted evidence → canonical `/practice/{sessionId}/report` → relabeled web consumers. Do not recreate these meanings in S06/S08 read-side code.
- `logic_score / accuracy_score / completeness_score` still exist by design. Their meanings are now `价值表达 / 证据与收益 / 异议推进`, and downstream consumers should treat them that way.
- Knowledge-driven objection prompts are still proved through the S04 authority line: `persona_policy -> resolve_effective_policy -> voice_policy_snapshot -> knowledge-check`.

### What's fragile
- Optional report enhancements (`/evaluation/.../report`, highlights) are still noisy in local runtime — they can 404/400/500 while the canonical unified report is correct.
- Long local StepFun sessions can emit repeated upstream reconnect diagnostics (`1006`) even when the session evidence line still lands correctly; treat those as runtime-observability signals, not automatic S05 regressions.

### Authoritative diagnostics
- `GET /api/v1/practice/sessions/{id}/knowledge-check` — this is the most reliable proof that a session used the bound-materials path for hit/miss/kb_not_ready/search_failed status.
- `practice_session_evidence_persisted` / `practice_session_evidence_not_evaluable` — these logs tell you whether the write layer actually committed sales evidence or explicitly downgraded it.
- `GET /api/v1/practice/sessions/{id}/report` — this is the canonical read surface for `main_issue`, `next_goal`, evaluability, pass flags, and rollups.

### What assumptions changed
- The old assumption that legacy `overall + 专业度/沟通技巧/销售流程` snapshots should preserve their original rollup mapping is no longer true — under S05 they normalize into the sales rubric, usually falling back to the overall score when only old generic labels exist.
- The product no longer needs a separate “sales interpretation” layer in the report/UI — the runtime write path itself is now the sales interpretation layer.

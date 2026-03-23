# M001/S05 — Research

**Date:** 2026-03-23

## Summary

S05 owns active **R003** and should be treated as a targeted extension of the S02/S04 authority chain, not as a new scoring/report subsystem. The stable line already exists: `persona_policy` / `VoiceRuntimePolicyService.resolve_effective_policy(...)` → frozen `PracticeSession.voice_policy_snapshot.knowledge_base_ids` + KB lock diagnostics → StepFun runtime `score_snapshot` / `effectiveness_snapshot` writes → `SessionEvidenceService.build_projection(...)` → report/replay/history/admin. That means S05 can improve **what the system trains and judges** without re-solving fact drift.

What is missing today is not storage but business semantics. The live runtime still uses `RealtimeScoringCapability` keyword heuristics on generic dimensions (`专业度 / 沟通技巧 / 销售流程 / 异议处理 / 成交能力`), and `common/effectiveness/evaluator.py` still reduces outcomes to the communication-training trio `3分钟连续表达 / 5轮追问不跑题 / 四段结构完整`. Because `main_issue` / `next_goal` are generated from that generic snapshot, the report can still tell the learner to “连续表达更稳定” even when the real failure was “没有把产品价值翻译成客户收益” or “面对价格/竞品追问没有给出证据”。

Recommendation: keep the existing projection contract as authority (per D012-D016), and make S05 a vertical slice across three layers only: (1) tighten the StepFun role contract so customer personas consistently attack budget/risk/ROI/price/competitor/proof angles using the bound knowledge bases; (2) replace the active runtime scoring/effectiveness write path with a sales-value baseline that emits canonical turn/session facts about value expression, customer-benefit linkage, evidence usage, objection handling, and next-step advancement; (3) update only the consumer surfaces that already show those facts live (`ScorePanel`, optionally report labels) without creating a second report scorer. This matches `safe-grow`’s “one item, smallest direct change” rule and `verification-before-completion`’s “fresh evidence before claims”.

## Recommendation

Take the smallest contract-preserving path: **version the sales evaluation semantics at the write layer, not the read layer**.

Specifically:

1. **Use `persona_policy` extension keys + `VoiceInstructionCompiler` to express the sales focus.**
   `normalize_persona_policy()` preserves unknown keys, so S05 can add fields like `sales_focus`, `value_axes`, `objection_axes`, or `expected_customer_questions` without first doing a DB migration. `VoiceInstructionCompiler.compile_base_contract(...)` is already the live StepFun contract seam; it should be the only place that turns those fields into persona behavior instructions. Do not fork prompt assembly elsewhere.

2. **Make the active StepFun runtime emit sales-specific `score_snapshot` and `effectiveness_snapshot`.**
   The authority write path is `stepfun_realtime_handler.py`, not the legacy `evaluation.services.realtime_scoring` stack. Add the new sales-value rubric where `_realtime_scoring_capability.execute(...)` is consumed and where `_apply_latest_scores_to_session(...)` maps runtime dimensions into session-level scores. Keep `SessionEvidenceService` and `/practice/sessions/{id}/report` as pure readers.

3. **Keep compatibility where downstream slices depend on it.**
   `SessionEvidenceService`, report/replay/history/admin, and the S02 tests all assume top-level keys like `pass_flags`, `overall_result`, `main_issue`, `next_goal`, `evaluable`, and `not_evaluable_reason` exist. S05 should keep those keys present, but may change how `main_issue` / `next_goal` are derived when sales-specific metrics are available. Avoid breaking `SessionEvidenceProjection` or adding client-side recomputation.

4. **Only touch UI where the new semantics become invisible otherwise.**
   `ScorePanel.tsx` hardcodes old dimension names/icons, and `report/page.tsx` still labels the top 3 cards as `逻辑性 / 准确性 / 完整性`. If backend ships new dimension names, at minimum the live score panel needs a mapping update or a graceful dynamic fallback. Per `baseline-ui` and `fixing-accessibility`, keep this minimal and preserve current accessible/native structure.

## Implementation Landscape

### Key Files

- `backend/src/sales_bot/services/voice_instruction_compiler.py`
  - Live StepFun role-contract compiler.
  - `compile_base_contract(...)` already merges persona prompt + traits + execution directives.
  - Best seam to force “ask about budget / risk / ROI / price / competitor / proof” behavior from `persona_policy` extension data, while `compose_turn_instructions(...)` preserves the S04 knowledge-grounding append model.

- `backend/src/agent/services/persona_policy.py`
  - `normalize_persona_policy(...)` preserves non-core extension keys today.
  - This is the lowest-risk place to formalize any new `persona_policy` sub-structure before runtime consumption.
  - Important: it is flexible enough for seeded config, but admin schemas/UI do not yet validate richer fields.

- `backend/src/sales_bot/services/voice_runtime_policy.py`
  - The authority merger for runtime profile + agent overrides + persona policy + KB lock defaults.
  - `resolve_effective_policy(...)` freezes `knowledge_base_ids`, `tool_policy`, compiled instructions, and `instruction_contract_hash`.
  - S05 should reuse this chain instead of inventing another “materials source”.

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - Active sales runtime.
  - Critical seams:
    - `_refresh_sales_stage_runtime_config(...)` loads persona behavior config and `Persona.scoring_weights`.
    - `_ensure_feedback_context_initialized(...)` passes runtime config into `AgentContext`.
    - The scoring block around `_realtime_scoring_capability.execute(...)` builds live `score_snapshot`, emits `score_update`, and derives the current `action_card`.
    - `_apply_latest_scores_to_session(...)` converts the latest runtime snapshot into session-level `logic_score / accuracy_score / completeness_score` and `effectiveness_snapshot`.
  - Any S05 dimension or metric change must update both score creation **and** session mapping here.

- `backend/src/agent/capabilities/realtime_scoring.py`
  - Current live scorer for StepFun.
  - Today it is purely keyword-based and generic.
  - Natural place to replace with a deterministic sales rubric using stage, persona focus, KB state, and turn text.
  - Existing focused tests: `backend/tests/unit/test_realtime_scoring.py`.

- `backend/src/common/effectiveness/evaluator.py`
  - Current `rule_v1` evaluator that generates `pass_flags`, `overall_result`, `main_issue`, `next_goal`, and `action_card`.
  - Right now the logic is communication-training-centric (`3分钟连续表达 / 5轮追问 / 四段结构`), not value/objection-centric.
  - S05 should either add a sales-aware branch/version here or introduce a backward-compatible extension layer that still returns the same top-level contract keys.

- `backend/src/common/conversation/session_evidence.py`
  - Canonical projection read model for report / replay / history / trends.
  - `build_projection(...)` and `ensure_effectiveness_snapshot(...)` are the readers that expose `main_issue`, `next_goal`, `stage_summary`, `evaluable`, and completeness diagnostics.
  - Do **not** add a second scoring truth here; this file should continue to trust persisted session/message evidence.

- `backend/src/common/api/practice.py`
  - Report API and terminal evidence sync.
  - `_apply_sales_realtime_score_snapshot_to_session(...)` is the fallback mapper used when ending sessions or recovering evidence from latest message snapshots.
  - If S05 changes runtime dimension names, this fallback must change together with `stepfun_realtime_handler.py`.

- `backend/src/common/knowledge/kb_lock_guard.py`
  - Authoritative KB lock / coach-mode decision logic from S04.
  - `build_kb_coach_grounding_context(...)` already distinguishes `coach_missing_evidence` from hard block states.
  - S05 should reuse these statuses as evidence of missing proof/grounding instead of inventing new retrieval-failure semantics.

- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
  - Query classification and grounding-context shaping.
  - Already detects entity-focused product / price / parameter queries and widens snippet/top-k limits for them.
  - Useful seam if S05 wants price / competitor / version questions to count differently from generic chat.

- `backend/src/common/knowledge/service.py`
  - Search expansion + fallback rules for product/price/version/deployment queries.
  - Existing expansion map already includes `价格 / 产品 / 型号 / 参数 / 部署`.
  - This is the materials truth line S05 should score against when checking whether objections were answered with real product evidence.

- `backend/src/evaluation/services/realtime_scoring.py`
- `backend/src/evaluation/services/ai_scoring.py`
- `backend/src/common/db/session_lifecycle.py`
- `backend/src/evaluation/services/report_generation_trigger.py`
  - Legacy/secondary scoring path.
  - Still saves and reloads `voice_policy_snapshot.realtime_scores` for comprehensive-report generation.
  - Not the authority for S02/S03 report facts anymore, but dimension-vocabulary drift here can still confuse enhancement layers if left untouched.

- `web/src/components/practice/ScorePanel.tsx`
  - Live learner-facing score surface.
  - Hardcodes icon/color mappings for the old generic dimension names.
  - No dedicated test file exists yet; S05 likely needs one if live scoring vocabulary changes.

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - Already projection-backed for `main_issue`, `next_goal`, `evaluable`, and stage summary.
  - Still renders top cards from `logic_score / accuracy_score / completeness_score` via `buildDimensionScores(...)`.
  - Only touch if S05 needs the report’s visible labels to match the new sales baseline.

- `web/src/hooks/websocket/message-handlers.ts`
  - WebSocket score-update normalization path.
  - Already accepts `dimension_scores` as either array or object and normalizes to `Record<string, number>`.
  - Useful if S05 changes only the names, not the transport shape.

- `web/src/app/(dashboard)/training/sales/page.tsx`
  - The landing page already hardcodes “价值表达 / 异议处理 / 竞品比较型客户 / 价格敏感型客户” combinations.
  - This can be left alone for the first S05 pass unless the slice explicitly wants entry-point content to be data-driven.

### Build Order

1. **Define the sales-value evidence vocabulary on the active write path first.**
   - Decide the minimum sales rubric fields that must exist at turn/session level (for example: value expression quality, customer benefit linkage, evidence usage, objection handling quality, next-step push).
   - This is the highest-risk decision because every downstream surface should read these facts, not reinterpret text later.

2. **Implement runtime scoring + session mapping on the active StepFun path.**
   - Update `agent.capabilities.realtime_scoring` and the StepFun handler together so:
     - live `score_update` emits the new business-facing dimensions;
     - session-level `logic/accuracy/completeness` still map consistently for S02/S03 readers;
     - `effectiveness_snapshot.main_issue / next_goal` become sales-specific when enough evidence exists.
   - This unblocks the rest because report/replay/history/admin are already projection-backed.

3. **Tighten persona runtime instructions and objection pressure using the existing policy chain.**
   - Extend `persona_policy` / compiled instructions so customer turns reliably pressure value, ROI, proof, price, competitor, and implementation questions.
   - Reuse S04’s bound-KB and KB-lock semantics so the conversation is about the latest material, not hardcoded lore.

4. **Align minimal consumer surfaces.**
   - Update `ScorePanel.tsx` (and only if necessary, report labels) so the learner can actually see the new baseline.
   - Keep these changes presentation-only; no client-side scoring or fact assembly.

5. **Only then decide whether to align the legacy enhancement path.**
   - If `evaluation.services.realtime_scoring` / report trigger are still used for comprehensive-report enhancements, update them last or explicitly leave them optional/degraded.

### Verification Approach

**Backend contract + unit verification**
- `cd backend && pytest tests/unit/test_realtime_scoring.py`
  - Update/add cases proving the active runtime scorer detects value-expression / evidence / objection semantics instead of only generic keywords.
- `cd backend && pytest tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_runtime_metrics_helpers.py`
  - Keep S04 knowledge-grounding classification and metrics intact.
- Add/update focused tests around:
  - `backend/src/common/effectiveness/evaluator.py`
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `backend/src/common/api/practice.py`
  - `backend/src/common/conversation/session_evidence.py`
- Then rerun S02 safety nets:
  - `cd backend && pytest tests/unit/test_session_evidence_service.py tests/integration/test_practice_evidence_flow.py tests/unit/test_history_service_evidence_projection.py`

**Frontend verification**
- Add a focused test for `web/src/components/practice/ScorePanel.tsx` (new file likely needed).
- Re-run:
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/hooks/websocket/message-handlers.test.ts'`
- If report labels change, extend the report page test to assert the new copy.

**Runtime / observable verification**
- Create a fresh sales session with a bound knowledge base.
- Drive at least one turn each for:
  - price objection,
  - competitor comparison,
  - evidence/proof demand,
  - benefit/ROI discussion.
- Verify:
  - live `score_update` events show the new sales dimensions;
  - `GET /api/v1/practice/sessions/{id}/knowledge-check` exposes a KB hit / coach-missing-evidence status consistent with the turn;
  - `GET /api/v1/practice/sessions/{id}/report` returns `main_issue` / `next_goal` phrased around value expression / objection handling rather than generic flow defects.

## Constraints

- **Per `safe-grow`, keep this to one slice and the smallest direct change.**
  S05 should not turn into persona-admin authoring, scenario-catalog redesign, or report-page overhaul unless the active write path forces it.

- **Per D012-D016, `SessionEvidenceService` remains the only fact authority for report / replay / history / trends.**
  Do not let `voice_policy_snapshot.realtime_scores` or a new comprehensive-report scorer become a second truth line.

- **`normalize_persona_policy()` preserves extension keys, but admin schemas are stricter.**
  This supports seeded `persona_policy` extensions immediately, but not necessarily polished admin editing of new fields.

- **`CreatePersonaRequest.scoring_weights` / `PersonaResponse.scoring_weights` are typed as `dict[str, float]`, while the active StepFun runtime and runtime tests expect `list[{name, weight}]`.**
  If S05 depends on persona-configured scoring weights, this shape mismatch must be resolved or explicitly bypassed.

- **UI currently hardcodes old labels.**
  `ScorePanel.tsx` and `report/page.tsx` will not automatically become semantically correct if backend dimension names change.

## Common Pitfalls

- **Two scoring stacks drift apart**
  - Active StepFun runtime uses `agent.capabilities.realtime_scoring.RealtimeScoringCapability`.
  - Legacy enhancement/report path still uses `evaluation.services.realtime_scoring.RealtimeScoringService`.
  - Changing only one will reintroduce enhancement-layer drift.

- **Generic effectiveness snapshot keeps overwriting the intended business diagnosis**
  - `evaluate_effectiveness_snapshot()` and `ensure_effectiveness_snapshot()` will continue to produce “连续表达 / 跑题 / 四段结构” outputs unless S05 explicitly feeds or versions sales-specific metrics there.

- **Dimension rename without fallback mapping breaks session-level scores**
  - `stepfun_realtime_handler._apply_latest_scores_to_session()` and `common/api/practice._apply_sales_realtime_score_snapshot_to_session()` currently only know the old dimension names.
  - If new names are introduced, update both together.

- **Live UI silently falls back to generic visuals**
  - `ScorePanel.tsx` renders unknown dimensions, but they lose meaningful icon/color mapping and become visually generic.
  - This is easy to miss because the transport still works.

- **Treating the training landing page as runtime authority**
  - `web/src/app/(dashboard)/training/sales/page.tsx` is currently curated/hardcoded marketing content, not the runtime truth of persona/scenario behavior.
  - Do not anchor S05 verification on this page alone.

## Open Risks

- The cleanest S05 implementation likely wants a sales-specific rubric version in `common/effectiveness/evaluator.py`, but many existing S02/S03 tests and UI labels hardcode the current pass-flag semantics. The planner should decide early whether S05 is:
  - an additive sales rubric that keeps existing keys and UI mostly intact, or
  - a versioned contract change that updates report labels/tests in lockstep.

- If persona-configured scoring weights become part of the solution, the `dict` vs `list` mismatch in persona schemas/runtime may force either a compatibility adapter or a narrower “seeded runtime config only” first pass.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js | `react-best-practices`, `vercel-react-best-practices` | installed |
| FastAPI | `wshobson/agents@fastapi-templates` | available |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available |
| WebSocket realtime | `jeffallan/claude-skills@websocket-engineer` | available |
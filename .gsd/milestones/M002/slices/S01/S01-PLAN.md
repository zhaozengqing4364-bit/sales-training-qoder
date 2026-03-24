# S01: 实时评分与训练页销售语义对齐

**Goal:** 让销售训练页在用户可达的实时语音模式下都复用同一套销售 rubric，使练中评分、阶段标签与下一轮建议直接围绕价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步展开。
**Demo:** 启动 sales 实时训练后，`score_update` / `stage_update` / `action_card` 在 StepFun 与经典链路上都输出并渲染 sales-first 语义；右侧面板保持五个销售维度；训练后报告仍保持现有三 rollup 读形。
**Requirement focus:** R009（owned）；R003、R005（supported）

## Must-Haves

- `score_update` / `stage_update` / `action_card` 在当前支持的 sales 语音模式上共用同一套销售语义和 canonical 字段结构。
- 训练页 websocket consumer 与右侧面板以五个销售维度为第一显示语义，同时保留兼容 fallback，而不是回退成旧的泛化标签。
- S01 只对齐 runtime / transport 语义，不改变训练后报告继续使用的三 rollup evidence contract。

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py`
- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'`

## Observability / Diagnostics

- Runtime signals: websocket `score_update` / `stage_update` / `action_card` payload assertions, plus persisted handler snapshots via `_latest_score_snapshot` / `_latest_action_card`.
- Inspection surfaces: `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/unit/test_capability_processor.py`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/components/practice/ScorePanel.test.tsx`.
- Failure visibility: generic dimension keys, dropped same-turn score refreshes, or legacy-mode action-card drift fail focused tests instead of surfacing later as ambiguous practice-page regressions.
- Redaction constraints: use sanitized fixture utterances only; no secrets or customer-identifying data in websocket/test payloads.

## Integration Closure

- Upstream surfaces consumed: `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/agent/capabilities/sales_stage.py`, `backend/src/common/effectiveness/evaluator.py`, `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `web/src/hooks/websocket/message-handlers.ts`, `web/src/components/practice/ScorePanel.tsx`, `web/src/app/(dashboard)/agents/[agentId]/page.tsx`.
- New wiring introduced in this slice: legacy sales realtime feedback reuses the shared sales effectiveness/action-card helper, and the practice-page consumers treat sales score payloads as the stable contract regardless of voice-mode selection.
- What remains before the milestone is truly usable end-to-end: S02 still needs to reduce prompt noise and enforce single-turn primary guidance; S04 still needs report/realtime consistency proof; S05 still needs degraded/reconnect visibility.

## Tasks

- [ ] **T01: Align backend realtime contracts across StepFun and classic mode** `est:2h`
  - Why: StepFun already emits the sales-shaped contract, but classic mode still derives action-card pass flags from generic communication / structure heuristics, leaving a user-reachable drift path.
  - Files: `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/tests/unit/test_capability_processor.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/unit/test_effectiveness_sales_baseline.py`
  - Do: Extend StepFun handler tests to assert emitted `score_update` + `action_card` payloads keep the five sales dimensions and stage-linked suggestions; refactor classic-mode `CapabilityProcessor` to reuse the shared sales effectiveness/action-card helper instead of `沟通技巧/销售流程` fallback math; keep the report-side three-rollup contract unchanged while locking both runtime paths to the same practice-page semantics.
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_capability_processor.py && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py`
  - Done when: backend tests prove both runtime paths emit sales-specific score/action semantics and the existing practice evidence contract still reads as the same three rollups.
- [ ] **T02: Harden practice-page consumers and voice-mode affordances around the sales contract** `est:90m`
  - Why: S01 only lands when the user-facing training page preserves the aligned sales vocabulary and does not silently drop richer same-turn updates or imply that mode choice changes the scoring rubric.
  - Files: `web/src/hooks/websocket/message-handlers.ts`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/components/practice/ScorePanel.tsx`, `web/src/components/practice/ScorePanel.test.tsx`, `web/src/app/(dashboard)/agents/[agentId]/page.tsx`, `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts`
  - Do: Tighten `score_update` idempotence so same-turn changes in dimensions / stage / suggestions are not dropped; keep ScorePanel sales-first ordering while preserving explicit fallback rendering for unknown dimensions; update launch-page voice-mode copy/tests so the selectable modes no longer imply a different practice-page scoring vocabulary.
  - Verify: `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts'`
  - Done when: frontend state and UI hold the five sales dimensions as the primary contract, fallback dimensions remain visible instead of being discarded, and mode selection tests confirm the same sales semantics reach the practice page.

## Files Likely Touched

- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_capability_processor.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/hooks/websocket/message-handlers.test.ts`
- `web/src/components/practice/ScorePanel.tsx`
- `web/src/components/practice/ScorePanel.test.tsx`
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx`

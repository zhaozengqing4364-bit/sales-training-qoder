# S02: 提示节奏收口与单轮唯一动作卡

**Goal:** 让销售实时教练在多轮对话里少而准：每轮最多保留一个主要动作方向，重复的阶段/模糊词/评分提示被节流和去重，旧回合提示不会拖到下一轮继续干扰。
**Demo:** 在同一条 sales 训练链路里，classic 与 StepFun 两条 runtime 都通过同一套 pacing/priority 规则产出实时反馈；同一轮只保留一个主要 `action_card`，重复 `fuzzy_detection` / `stage_update` / `score_update` 不再刷屏；训练页在新 final transcript 到来时清掉上一轮的 turn-bound hints，只保留阶段与评分作为上下文。
**Requirement focus:** R009（advanced）

## Must-Haves

- classic 与 StepFun 两条 sales runtime 都在 capability 执行之后复用同一个 pacing / priority seam，对重复阶段、模糊词和评分建议做节流与去重，而不是各自独立推送。
- 同一轮最多暴露一个主要动作方向：`action_card` 成为唯一主教练面，阶段与分数只保留为上下文，不再同时堆叠第二条 competing textual coaching。
- 新用户 final transcript 到来时，上一轮的 `actionCard` / `fuzzyDetections` 必须及时清空；如果 StepFun 发生恢复，最多只保留避免 replay burst 所需的最小 pacing 状态。

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k 'suppress or preserve_context' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py -k 'suppress or replay' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown`
- `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'`

## Observability / Diagnostics

- Runtime signals: shared realtime-feedback arbiter decisions, emitted websocket payload counts/types, persisted StepFun pacing snapshot fields, and client-side transcript-driven hint resets.
- Inspection surfaces: `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_capability_processor.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_realtime_persistence.py`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/components/practice/RightPanelContent.test.tsx`.
- Failure visibility: duplicate action cards, stale hints surviving into later turns, or reconnect-triggered replay bursts fail focused assertions with explicit turn/cooldown expectations instead of surfacing later as vague browser regressions.
- Redaction constraints: use sanitized sales utterances and synthetic payloads only; no real customer text, tokens, or production session identifiers in tests.

## Integration Closure

- Upstream surfaces consumed: S01’s canonical sales websocket contract from `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, and the practice-page reducer/panel consumers in `web/src/hooks/websocket/message-handlers.ts`, `web/src/hooks/use-practice-websocket.ts`, `web/src/components/practice/RightPanelContent.tsx`, `web/src/components/practice/ScorePanel.tsx`.
- New wiring introduced in this slice: one shared realtime-feedback arbiter reused by classic + StepFun runtime paths, plus transcript-driven hint reset and action-card precedence in the training-page right panel.
- What remains before the milestone is truly usable end-to-end: S03 still needs stage / score delta / next-turn rules to converge into one coaching flow, and S05 still needs coach degraded / reconnect visibility beyond pacing safety.

## Tasks

- [x] **T01: Add a shared backend arbiter for single-turn coaching** `est:2h`
  - Why: S02’s main risk is cross-channel competition after fuzzy / stage / score signals are produced; the priority and cooldown rules need one backend seam before both runtime modes can stay aligned.
  - Files: `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`, `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_capability_processor.py`, `backend/tests/unit/test_fuzzy_detection.py`
  - Do: Add failing arbiter tests for issue priority, duplicate suppression, and same-turn cooldown behavior; implement a shared helper that normalizes fuzzy detections / score suggestions / stage context into one primary action direction without changing S01 field names; wire classic mode through that helper while keeping `FuzzyDetectionCapability`’s local cooldown behavior intact.
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown`
  - Done when: classic mode emits at most one primary action card per turn, repeated coaching with the same signature is suppressed by focused tests, and low-level fuzzy cooldown semantics still pass unchanged.
- [x] **T02: Wire StepFun feedback pacing and reconnect-safe arbiter state** `est:2h`
  - Why: StepFun still emits fuzzy/score/action independently and only persists stage / score / action snapshots, so it can drift from classic mode and replay stale coaching after recovery.
  - Files: `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_realtime_persistence.py`
  - Do: Extend StepFun tests to prove same-turn single-action behavior and reconnect replay safety; route `_run_realtime_feedback(...)` through the shared arbiter instead of independent fuzzy/score/action sends; persist only the minimal serialized pacing state needed to avoid replay bursts after restore while keeping `_latest_score_snapshot` / `_latest_action_card` as the existing read-side diagnostics.
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_persistence.py`
  - Done when: StepFun follows the same arbitration rules as classic mode, reconnect-safe state restores do not replay stale coach bursts, and the focused handler/persistence suites prove it.
- [x] **T03: Clear stale turn hints and enforce action-card precedence in the practice panel** `est:90m`
  - Why: Even with backend pacing, the client still carries old turn hints forward and renders multiple textual instructions side by side, which is the visible “刷屏 / 打架” failure users feel.
  - Files: `web/src/hooks/websocket/message-handlers.ts`, `web/src/hooks/websocket/message-handlers.test.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/components/practice/RightPanelContent.tsx`, `web/src/components/practice/RightPanelContent.test.tsx`, `web/src/components/practice/ScorePanel.tsx`, `web/src/components/practice/ScorePanel.test.tsx`
  - Do: Add reducer tests proving a new final transcript clears `actionCard` / `fuzzyDetections` before the next turn’s coaching arrives; update the right panel so `action_card` is the only primary textual coach surface while stage and score context stay visible; let `ScorePanel` suppress duplicate textual suggestions when an action card is already present and lock the precedence rules with focused component tests.
  - Verify: `cd web && npm test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx'`
  - Done when: the right panel drops stale turn-bound hints on new user turns, does not show competing textual coaching beside `action_card`, and still keeps stage/score context visible.

## Files Likely Touched

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_realtime_feedback_arbiter.py`
- `backend/tests/unit/test_capability_processor.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_realtime_persistence.py`
- `web/src/hooks/websocket/message-handlers.ts`
- `web/src/hooks/websocket/message-handlers.test.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/components/practice/RightPanelContent.tsx`
- `web/src/components/practice/RightPanelContent.test.tsx`
- `web/src/components/practice/ScorePanel.tsx`
- `web/src/components/practice/ScorePanel.test.tsx`

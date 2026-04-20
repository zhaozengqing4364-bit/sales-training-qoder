# S03: 阶段推进教练与下一轮规则闭环

**Goal:** 让 sales 训练中的 `stage_update`、`score_update` 和 `action_card` 由同一套 backend rule 推出“下一轮最该怎么推进”；改变阶段或最弱/下滑维度时，classic 与 StepFun 都会同步改变 `action_card` 文案，而不是继续靠 pass-flags-only 规则给出与上下文脱节的提示。
**Demo:** 对同一轮 sales 发言，classic 与 StepFun 在共享 stage context + realtime score deltas 后，会产出一致的 `action_card.issue` / `replacement` / `next_turn_rule`；训练页继续消费现有 `action_card` contract，不需要新的前端 planner，也不引入新的 replay / report 持久化 schema。
**Requirement focus:** R009（advanced）

## Must-Haves

- `common.effectiveness` 提供一套共享的 coaching-focus rule：从当前销售阶段、最弱/下滑销售维度和既有 pass flags 推出下一轮唯一动作，`build_action_card(...)` 不再只靠 `pass_flags` 选 `next_turn_rule`。
- `RealtimeFeedbackArbiter` 与两条 runtime 都把等价的 rich context 喂给共享规则：classic 保留完整 `stage_data` 与 raw `score_payload`，StepFun 也必须保留 `key_actions` / `guidance` / `progress` 与 `dimensions[*].trend/delta` 级别的信息，而不是只剩 `stage_name` / score snapshot。
- websocket `action_card` contract 继续保持 `issue` / `replacement` / `next_turn_rule` 三字段；S03 不新增前端 rule composition，不做 replay/report schema 迁移，只用 focused tests 证明更聪明的文案来自 backend 共享规则。

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py tests/unit/test_stepfun_realtime_handler.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py -k weakest_dimension_changes_next_turn_rule -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py -k preserve_context_without_primary_action -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -vv`

## Observability / Diagnostics

- Runtime signals: shared coaching-focus outputs in `common.effectiveness`, arbiter decisions that now depend on stage + score context, and the existing `_latest_action_card` / `_latest_score_snapshot` StepFun diagnostics.
- Inspection surfaces: `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`, `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_capability_processor.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`.
- Failure visibility: stage-insensitive action cards, weak-dimension drift, or classic/StepFun parity gaps fail focused assertions with explicit expected `issue` / `replacement` / `next_turn_rule` values instead of surfacing later as vague browser regressions.
- Redaction constraints: use synthetic sales utterances and synthetic score/stage payloads only; no real customer text, tokens, or production session identifiers in tests.

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/effectiveness/evaluator.py`, `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/agent/capabilities/sales_stage.py`, `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`, `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, and the unchanged practice-page `action_card` renderer in `web/src/components/practice/RightPanelContent.tsx`.
- New wiring introduced in this slice: one shared backend coaching-focus resolver reused by `build_action_card(...)` and the arbiter, plus a StepFun handoff that preserves rich stage/score context for arbitration without changing emitted `score_update` / `action_card` payload shapes.
- What remains before the milestone is truly usable end-to-end: S04 still needs report/replay `main_issue` / `next_goal` alignment on the same seam, and S05 still needs degraded / resume visibility for coach failures.

## Tasks

- [x] **T01: Define stage-aware coaching focus in `common.effectiveness`** `est:2h`
  - Why: The split source is in the shared effectiveness layer: `build_action_card(...)`, `resolve_main_issue(...)`, and `resolve_next_goal(...)` reason about the next move differently, so S03 needs one authoritative backend rule before runtime wiring can converge.
  - Files: `backend/src/common/effectiveness/evaluator.py`, `backend/src/common/effectiveness/schemas.py`, `backend/src/common/effectiveness/__init__.py`, `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`
  - Do: Add failing unit coverage for discovery/evidence, objection/handling, and closing/next-step cases where changing stage or the weakest/declining dimension changes the next-turn focus; introduce one shared typed coaching-focus helper in `common.effectiveness`; make `build_action_card(...)` derive `issue` / `replacement` / `next_turn_rule` from that helper while keeping the public action-card field names stable and avoiding any replay/report schema change.
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_coaching_focus.py`
  - Done when: `common.effectiveness` can compute a stage-aware coaching focus from score/stage context, and `build_action_card(...)` changes its text when stage or weakest dimension changes without renaming existing keys.
- [x] **T02: Route classic arbitration through the shared coaching-focus rule** `est:2h`
  - Why: The classic path already has the richest context surface, but the arbiter ignores it and still builds action cards from pass flags plus one suggestion, so this runtime is the safest place to prove the new rule actually drives live coaching.
  - Files: `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`, `backend/src/sales_bot/websocket/components/capability_processor.py`, `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_capability_processor.py`
  - Do: Extend arbiter and classic-path tests to assert that stage context plus weakest/declining dimension can change the primary action-card text while S02 duplicate suppression and context retention still hold; pass raw stage and score context from `CapabilityProcessor` into the arbiter; keep websocket payload shapes stable so the existing practice-page consumer remains a renderer, not a planner.
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py`
  - Done when: classic runtime emits stage-aware, dimension-aware `action_card` text under focused tests, and the arbiter still suppresses same-turn duplicates without dropping contextual `fuzzy_detection` / `stage_update` / `score_update` messages.
- [x] **T03: Normalize StepFun stage and score context to classic parity** `est:2h`
  - Why: StepFun currently strips rich stage guidance and score `trend/delta` data before arbitration, so even a correct shared rule would drift again across runtimes unless this handoff is closed.
  - Files: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`
  - Do: Add failing handler tests proving that equivalent stage + score inputs now produce the same primary action on StepFun as on classic; retain the latest rich `stage_data` from the StepFun stage-analysis path; feed raw scoring dimensions/trend/delta into the arbiter while keeping emitted `score_update` and persisted `_latest_score_snapshot` / `ai_feedback` shapes unchanged.
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py`
  - Done when: StepFun produces the same coaching direction as classic for matched stage/score inputs, and focused handler tests prove the richer context stays backend-only without forcing a frontend or persistence migration.

## Files Likely Touched

- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/effectiveness/schemas.py`
- `backend/src/common/effectiveness/__init__.py`
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`
- `backend/tests/unit/test_realtime_feedback_arbiter.py`
- `backend/tests/unit/test_capability_processor.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`

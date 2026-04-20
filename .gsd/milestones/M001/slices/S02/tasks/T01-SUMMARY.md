---
id: T01
parent: S02
milestone: M001
provides:
  - Stable StepFun sales evidence writes with canonical `overall_score` payloads and explicit not-evaluable terminal facts for insufficient-evidence sessions
key_files:
  - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
  - backend/src/sales_bot/websocket/components/message_persistence.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_stepfun_message_helpers.py
  - backend/tests/unit/test_stepfun_realtime_persistence.py
  - backend/tests/unit/test_sales_message_persistence.py
key_decisions:
  - D013: StepFun sales evidence writes now canonicalize `score_snapshot.overall_score` and persist `evaluable=false` / `INSUFFICIENT_TURN_DATA` as the thin-evidence terminal fact instead of surfacing summary failure semantics
patterns_established:
  - Turn-level save/patch/update paths accept legacy `score_snapshot.overall` as input compatibility but only persist the canonical `overall_score` shape plus supported evidence fields
  - Sales StepFun terminal close syncs runtime or persisted message evidence into `PracticeSession` before considering summary generation, and insufficient evidence is persisted as an explicit effectiveness snapshot/log pair
observability_surfaces:
  - structured logs `practice_session_evidence_persisted`
  - structured logs `practice_session_evidence_not_evaluable`
  - focused pytest coverage for helper normalization, duplicate analysis patching, terminal evidence sync, and summary bypass on insufficient evidence
  - slice verification command results recorded in this summary for downstream tasks
duration: 50m
verification_result: passed
completed_at: 2026-03-23T04:32:58+08:00
blocker_discovered: false
---

# T01: 稳定逐轮证据写入与无证据终态语义

**Stabilized StepFun sales evidence writes around canonical `overall_score` payloads and made zero-turn / thin-evidence terminal sessions persist explicit not-evaluable facts instead of collapsing into summary-failure semantics.**

## What Happened

这轮只收写入边界，没有提前做 T02/T03/T04 的消费面。

1. `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
   - 把 turn-level analysis payload 的规范化集中在 `normalize_score_snapshot()` / `_normalize_analysis_payload()`。
   - `score_snapshot` 现在统一产出 `overall_score`，但仍接受历史 `overall` 作为兼容输入。
   - `sales_stage`、`fuzzy_words`、`ai_feedback`、`transcript_metadata` 只在类型合法时进入 persistence payload。
   - duplicate patch 路径 `patch_existing_message_analysis()` 和新写入路径 `save_stepfun_message()` 都走同一规范化逻辑，并打 `practice_session_evidence_persisted` 日志。

2. `backend/src/sales_bot/websocket/components/message_persistence.py`
   - `MessagePersistence.update_analysis()` 也改走 helper 的规范化输出，避免老代码路径继续把 `overall`、脏 key 或错类型直接写进库里。

3. `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
   - reconnect snapshot 里的 `latest_score_snapshot` 统一走 `normalize_score_snapshot()`，避免 runtime 快照和消息落库使用不同键形。
   - `_apply_latest_scores_to_session()` 现在会把最新 realtime score snapshot 安全写回 session-level 分数，并在 `turn_count == 0` 或没有可用 score snapshot 时显式写出 `evaluable=false` / `INSUFFICIENT_TURN_DATA` 的 effectiveness snapshot。
   - terminal/session 级日志区分 `practice_session_evidence_persisted` 和 `practice_session_evidence_not_evaluable`，不再把“证据不足”埋进泛化失败里。

4. `backend/src/common/api/practice.py`
   - `_sync_sales_realtime_terminal_evidence()` 先尝试 runtime score snapshot，再尝试最新消息 analysis snapshot；两者都没有时，直接给 session 落一个 `INSUFFICIENT_TURN_DATA` 的不可评估事实。
   - `_prepare_terminal_lifecycle_result()` 在 sales completed path 上先看 session 是否已有可用 evidence；如果 terminal snapshot 已经明确 `evaluable=false`，就直接结束并保留事实，不再继续调用 summary。
   - 真正的 summary 失败仍保留为异常路径；“薄证据”不再伪装成 `[SUMMARY_GENERATION_FAILED]`。

5. 测试面
   - `backend/tests/unit/test_stepfun_message_helpers.py` 覆盖 helper 规范化、legacy `overall` 兼容、duplicate patch 成功路径。
   - `backend/tests/unit/test_sales_message_persistence.py` 覆盖旧 message persistence 入口的规范化写入。
   - `backend/tests/unit/test_stepfun_realtime_persistence.py` 覆盖 runtime snapshot 兼容、session-level score flush、零轮终态显式 not-evaluable、以及 terminal path 跳过 summary 的语义。

## Verification

Passed:
- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py -k patch_existing_message_analysis_returns_true_on_success -vv`
  - 复现上次失败点；当前单测已通过。
- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`
  - 18 tests passed.
  - 覆盖点包括：`overall -> overall_score` 兼容、duplicate patch、session-level score flush、`evaluable=false` / `INSUFFICIENT_TURN_DATA` 终态语义。

Slice-level verification status:
- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
  - failed with `file or directory not found: tests/unit/test_session_evidence_service.py`
  - 这是 T02 产物尚未创建，符合当前任务边界。
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`
  - failed with `file or directory not found: tests/unit/test_history_service_evidence_projection.py`
  - 这是 T03 产物尚未创建，符合当前任务边界。
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'`
  - failed with `No test files found`
  - 这是 T04 页面测试尚未创建，符合当前任务边界。

## Diagnostics

后续排查这个切面，先看这几个点：
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
  - `normalize_score_snapshot()`
  - `patch_existing_message_analysis()`
  - `save_stepfun_message()`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `_apply_latest_scores_to_session()`
- `backend/src/common/api/practice.py`
  - `_sync_sales_realtime_terminal_evidence()`
  - `_prepare_terminal_lifecycle_result()`
  - `_log_sales_terminal_evidence_state()`
- 结构化日志：
  - `practice_session_evidence_persisted`
  - `practice_session_evidence_not_evaluable`

如果后续 report / replay / history 仍然漂，先确认这里写出的 `overall_score` / `evaluable` / `not_evaluable_reason` 是否稳定，再排 T02 之后的 projection/consumer。

## Deviations

none

## Known Issues

- Slice 验证里的 T02 / T03 / T04 命令目前仍失败，因为这些任务对应的测试文件还没创建；这不是 T01 blocker，但意味着还不能宣称 S02 全 slice 已验证完成。

## Files Created/Modified

- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — 统一逐轮 evidence payload 规范化、legacy `overall` 兼容和 turn-level persistence logging。
- `backend/src/sales_bot/websocket/components/message_persistence.py` — 让旧消息 analysis 更新入口也走同一 canonical payload contract。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 统一 runtime score snapshot 规范化、session-level score flush 和 zero-turn not-evaluable terminal semantics。
- `backend/src/common/api/practice.py` — 让 sales terminal path 先同步 evidence，再把薄证据会话收口成显式 not-evaluable 事实而不是 summary failure。
- `backend/tests/unit/test_stepfun_message_helpers.py` — 锁定 helper normalization、duplicate patch 和 canonical `overall_score` contract。
- `backend/tests/unit/test_stepfun_realtime_persistence.py` — 锁定 session-level score flush、terminal evidence sync、summary bypass 与薄证据终态语义。
- `backend/tests/unit/test_sales_message_persistence.py` — 锁定 legacy message persistence 入口的 analysis payload normalization。
- `.gsd/DECISIONS.md` — 记录 D013，明确 T01 的 evidence write contract。
- `.gsd/milestones/M001/slices/S02/S02-PLAN.md` — 标记 T01 完成。
- `.gsd/STATE.md` — 将下一动作推进到 T02。
- `.codex/loop/state.json` — 记录当前单项循环已完成并更新下一动作。
- `.codex/loop/log.md` — 追加这轮 stabilize 迭代记录。
- `.gsd/completed-units.json` — 记录 `execute-task/M001/S02/T01` 已完成。

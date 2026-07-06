# StepFun Realtime 角色一致性旁路观测闭环验证计划

## 范围与成功标准

- 风险等级：P1。原因：涉及实时语音运行时、角色一致性守护、历史记录投影、管理端观测与 CI 门禁；不得触发真实 StepFun 付费调用。
- 核心证明：角色一致性观测必须“记录但不阻断”。观测 sink、LLM 辅助判定或管理端读取失败，只能生成可观测诊断或降级信号，不能中断 learner 实时对练主路径。
- 权限边界：learner 只能看到本人历史；admin/training lead/ops 按 `sales_trainer` capability 与对象级权限读取观测结果；权限不足 fail-closed。
- 状态边界：实时会话 `in_progress -> completed` 不因观测写入失败而失败；阻断型角色泄露只影响当前输出处理/重生成，不应破坏 session lifecycle。

## CodeGraph 定位结果

- StepFun handler 入口：`backend/src/sales_bot/websocket/stepfun_realtime_handler.py`，现有测试入口包括 `backend/tests/unit/test_stepfun_realtime_handler.py`、`backend/tests/unit/test_stepfun_realtime_upstream.py`、`backend/tests/unit/test_stepfun_payload_snapshots.py`。
- 上游输出/角色守护入口：`backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`，`_record_roleplay_compliance_decision()` 写入 `runtime_metrics.roleplay_compliance` 并捕获持久化异常。
- 运行时观测快照入口：`backend/src/sales_bot/websocket/components/stepfun_roleplay_runtime_helpers.py` 与 `stepfun_runtime_metrics_helpers.py`，负责同步 `it_leader_roleplay_v1` observability、state card、knowledge degradation。
- Training records / replay 入口：`backend/src/common/services/runtime_outcome_projection.py`、`backend/src/sales_trainer/services/training_record_service.py`；通用 admin records 在 `backend/src/admin/api/training_records.py` 明确排除 `external_binding.owner=sales_trainer` 的会话。
- 管理端展示入口：`web/src/app/admin/sales-trainer/training-records/`、`web/src/app/admin/sales-trainer/analytics/`、`web/tests/e2e/newcomer-training-closed-loop.spec.ts`。

## 测试矩阵

| 场景 | 后端最小断言 | 前端/管理端断言 | E2E/契约断言 | 当前状态 |
| --- | --- | --- | --- | --- |
| 实时不阻塞 | `_record_roleplay_compliance_decision()` 在 sink 抛错时仍返回，`runtime_metrics.roleplay_compliance` 已在内存更新 | learner 页面不出现阻塞弹窗；实时状态仍可继续 | mock StepFun/local provider 完成一轮，观测写入失败但 session 仍 completed | 已新增单测覆盖 sink 失败不阻断；E2E 待最终实现后补 |
| sink 失败 | 持久化异常只记录 warning，不抛出到 `_handle_upstream_response_*` | admin 详情页展示“观测延迟/缺失”而非空成功 | CI 中用 mock sink 注入 DB/queue failure | 已新增单测覆盖 |
| heuristic signals | 无 LLM 时 `check_roleplay_output()` 能识别隐藏信息泄露/阶段越界信号 | analytics/training-records 展示 signal source、violation code、manual review | 契约要求 `signal_source=heuristic` 或等价字段进入快照 | 已新增单测覆盖隐藏信息泄露；展示待补 |
| LLM disabled | 辅助 LLM 关闭时不得调用外部 LLM；使用 heuristic-only 诊断 | 管理端显示 `llm_status=disabled` 或等价降级原因 | 环境变量关闭 LLM，确认无真实 provider 调用 | 待实现字段后补断言 |
| LLM timeout | timeout 转为 recoverable/diagnostic，不阻断 WebSocket 主路径 | 管理端显示 timeout 诊断与最近一次观测时间 | mock LLM timeout，确认 session 可完成且计数递增 | 待实现字段后补断言 |
| 权限不足 | learner/非授权 admin 读取观测明细返回 403/404 或 redacted | 直链页 fail-closed，不请求 dashboard 数据 | Playwright 验证未授权账号无 analytics/training records 观测入口 | 待补 |
| 管理端展示 | API 返回 `roleplay_compliance_summary`、timeline、quality_flags 时页面渲染 violation/manual review | loading/empty/error/success 均可见；失败不吞成“暂无数据” | mock API fixtures 覆盖指标卡、列表、详情 | 待最终 DTO 稳定后补 |
| 历史回放 | replay/report 从 frozen `voice_policy_snapshot.runtime_metrics` 读取，不反推最新 active config | 详情页能显示历史会话冻结合同 hash 与观测 timeline | completed session replay 保留 `roleplay_contract_hash`、state card、runtime observability | 现有 helper/handler 测试已有部分覆盖；需补 sales-trainer 详情页断言 |

## 已补充测试

- `backend/tests/unit/test_roleplay_observability_contract.py`
  - `test_should_record_roleplay_observation_without_blocking_when_sink_fails`
  - `test_should_emit_heuristic_hidden_information_signal_without_llm`
- `backend/tests/unit/test_roleplay_observation_evaluator.py`
  - 覆盖 heuristic、LLM disabled、LLM timeout、LLM failure、LLM invalid JSON 与敏感信息脱敏。
- `backend/tests/unit/test_sales_trainer_roleplay_observation_service.py`
  - 覆盖 observation 幂等落库、heuristic/LLM 聚合、non_blocking 写入失败不污染主路径。
- `backend/tests/unit/test_sales_websocket_router.py`
  - 覆盖 sales websocket transcript capture sink 可把 assistant turn 写入 observation sidecar，sink 异常只 warning。
- `backend/tests/integration/test_sales_trainer_api.py`
  - 覆盖 admin realtime roleplay observation endpoint 的 records 权限与部门 scope guard。
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts`
  - 在 mock/local StepFun realtime 闭环中新增 admin observation sidecar 断言：learner realtime session completed 后，admin observation endpoint 可见且详情页展示“角色一致性观察”，不使用真实 StepFun key。

这些测试不依赖真实 StepFun、LLM、ASR/TTS 或外部网络；只验证当前角色守护/观测契约的最低行为。

## 待补断言

- 后端：若新增独立 role consistency observer/sink 模块，需补单元测试：
  - observer sink 成功、失败、超时。
  - heuristic-only、LLM disabled、LLM timeout、LLM invalid JSON。
  - `record_but_do_not_block=true` 类策略不可被配置误改为阻断主路径。
- 后端契约：若 API 新增观测字段，需在 `backend/tests/contract/` 增加 envelope、错误码、redaction、权限不足断言。
- 前端：`web/src/app/admin/sales-trainer/analytics/page.test.tsx` 与 `training-records/[recordType]/[recordId]/page.test.tsx` 需补观测卡、质量旗标、manual review、错误态断言。
- E2E：`web/tests/e2e/newcomer-training-closed-loop.spec.ts` 增加 mock provider 场景，禁止真实 StepFun 付费调用。

## 最终 Gate 命令清单

### 后端 focused

```bash
cd backend
pytest tests/unit/test_roleplay_observability_contract.py -q
pytest tests/unit/test_roleplay_observation_evaluator.py -q
pytest tests/unit/test_sales_trainer_roleplay_observation_service.py -q
pytest tests/unit/test_sales_websocket_router.py -q
pytest tests/integration/test_sales_trainer_api.py -q
pytest tests/unit/test_stepfun_realtime_upstream.py -q
pytest tests/unit/test_stepfun_realtime_handler.py -q
pytest tests/unit/test_stepfun_payload_snapshots.py -q
pytest tests/unit/test_sales_trainer_training_journey_service.py -q
pytest tests/unit/test_sales_trainer_phase2_projection.py -q
pytest tests/contract/test_sales_trainer_phase2_contract.py -q
```

### 后端质量门禁

```bash
cd backend
ruff check src tests/unit/test_roleplay_observability_contract.py
mypy src/sales_bot src/training_runtime src/sales_trainer src/common/services
```

### 前端 focused

```bash
cd web
npx vitest run src/app/admin/sales-trainer/analytics/page.test.tsx
npx vitest run src/app/admin/sales-trainer/training-records/page.test.tsx
npx vitest run 'src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx'
npx vitest run src/lib/sales-trainer/operational-diagnostics.test.ts
```

### 前端质量门禁

```bash
cd web
npm run lint
npx tsc --noEmit
npm test -- --run
```

### Playwright 关键路径

```bash
cd web
STEPFUN_REALTIME_E2E_MODE=mock npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --grep "realtime|training records|analytics"
```

### CI / Path Filter

- `.github/workflows/roleplay-contract-eval.yml` 已把 observation service、evaluator、sales websocket router、migration、`docs/api-contract/sales-trainer.md`、admin observation UI 与 newcomer closed-loop E2E 纳入 PR/push path filter。
- `scripts/critical-quality-gate.sh` 已把 observation contract/evaluator/service/router 后端测试加入必跑目标，并把 observation service/evaluator/router 加入 newcomer mypy focused gate。
- 真实 StepFun smoke 仍只通过 `CRITICAL_GATE_MODE=newcomer-real-provider` 或 `RUN_NEWCOMER_REAL_PROVIDER_GATE=1` 可选启用；普通 CI 必跑路径固定使用 local/mock provider。

## 当前阻塞

- 最终实现的独立 role consistency observer/sink DTO 尚未稳定；无法补精确 API/页面字段断言。
- 管理端 analytics 与 training records 的最终观测字段需与后端契约对齐后再补 Vitest 断言。
- E2E 必须使用 mock/local provider；没有专用 mock seed 时，不应跑真实 StepFun。

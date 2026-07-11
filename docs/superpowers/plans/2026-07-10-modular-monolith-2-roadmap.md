# 模块化单体 2.0 AI 原生实施路线图

日期：2026-07-10
设计：`docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
ADR：`docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`

## 计划单位

本路线图按 Gate 和独立变更包推进，不按人周推进。预计 27–39 个变更包；每包
1–3 个提交、一个明确 reviewer gate、一个可独立运行的验证集合。

## 执行状态

| Gate | 状态 | 当前证据 / 下一步 |
|------|------|-------------------|
| 0A | Completed（2026-07-10） | 5 个工作提交；聚焦回归 `53 passed`；OpenAPI parity 已进入主门禁 |
| 0B | Completed（2026-07-10） | 15 项逐项分类并清零；后端 unit + contract `2617 passed`；ForbiddenWord 事务/DTO 合同闭环 |
| 0C | Completed（2026-07-10） | 17 项失败按时区/fixture/旧语义清零；209 files / 1327 passed / 6 skipped；5:54.32 自然 exit 0 |
| 1A | Completed（2026-07-10） | 49 条边全部受 policy 治理；12 包 SCC 只许缩小；guard 已进入主门禁 |
| 1B | Completed（2026-07-11） | 唯一 release gate 从头自然 exit 0；backend 2665 passed；Vitest 209 files / 1329 passed；全部本地 Playwright、598 个 selected backend 测试和 82% changed coverage 通过 |
| 2 | Completed（2026-07-11） | Presentation Engine tracer bullet 默认启用、单 flag 可回滚；canonical gate backend 2903 passed、Vitest 1329 passed、全部本地 Playwright、598 个 selected backend 测试和 91.34% changed coverage 通过 |
| 3–6 | Not started | 按顺序实施 Provider/Grounding 中立化、领域所有权、Locality 和兼容层退役 |

Gate 0A 的实现和归档证据见其详细计划。此表表达的是迁移进度，不把已批准的目标
设计或已完成的单个基础设施 Gate 误写成模块化单体 2.0 整体完成。

## Gate 0：恢复测试和合同事实

### Gate 0A：平台合同真相

状态：**Completed（2026-07-10）**。聚焦回归 `53 passed, 1 warning`；Gate 0A 完成时
后端全量仍有 15 项 Gate 0B 失败，因此该 Gate 只声明平台合同真相技术闭环。上述失败
随后已由 Gate 0B 逐项分类并清零。

范围：

- FastAPI `_IncludedRouter` 路由测试兼容；
- OpenAPI 生成、同步和 parity；
- app factory WS surface；
- contributor 全局 registry 的测试隔离；
- realtime reconnect auth fixture；
- async transcript capture 时序测试。

详细计划：
`docs/superpowers/plans/2026-07-10-gate-0a-platform-contract-truth.md`。

### Gate 0B：新人训练后端回归真相

状态：**Completed（2026-07-10）**。基线 15 项最终分类为 11 项 fixture 漂移、
3 项断言语义漂移和 1 项生产缺陷；最终后端 unit + contract 为
`2617 passed, 1 skipped, 74 warnings`，相关 integration 为 `41 passed, 2 warnings`。

已闭环的失败簇：

- audio evaluation scenario 治理后，旧 fixture 缺 `scenario_key`/受控 config；
- learning topic/path/quiz 收口后，旧测试仍按旧发布和解锁语义构造数据；
- learner-only 与管理员读取权限断言和当前对象级权限口径不一致；
- projection/lineage 测试对新训练记录真源的预期漂移；
- secret scan 默认路径断言和当前证据目录不一致；
- PPT forbidden word contract 漂移。

ForbiddenWord 生产缺陷已通过公共 DTO、commit 前验证、数据库失败 rollback、两路权限
和 runtime OpenAPI schema 回归闭环。Sales Trainer fixture 已通过正式 path
save/publish 入口，不再绕过 canonical 发布校验。Secret scan 使用确定性临时证据目录。

详细计划：
`docs/superpowers/plans/2026-07-10-gate-0b-backend-regression-truth.md`。

验收：**通过**。没有新增 skip、xfail、永久隔离或无期限例外。

### Gate 0C：前端回归真相

状态：**Completed（2026-07-10）**。可观测基线为 209 files、17 failed、
1309 passed、6 skipped，366.45 秒；最终为 209 files 全绿、1327 passed、6 skipped，
352.93 秒 / 5:54.32 wall clock，自然 exit 0，`hanging-process` 未报告遗留句柄。

已闭环：

- dashboard 用 runner-local fake system time，并在 `afterEach` 恢复 real timers；
- business-skills Journey fixture 迁到 non-blocking `learning_topics`，公开 API mock 迁到
  topic-specific facade；
- 5 个旧 required module/active path/catalog/next-action 用例改为 Learning Topic 当前治理语义；
- 新增专题未发布 fail-closed 回归；未修改生产代码、runner 并行配置或既有 skip。

详细计划：
`docs/superpowers/plans/2026-07-10-gate-0c-frontend-regression-truth.md`。

验收：**通过**。全量 Vitest 绿色且远低于 45 分钟 release-truth job timeout，自然退出。

## Gate 1：建立架构和测试护栏

### Gate 1A：跨包依赖与 SCC guard

状态：**Completed（2026-07-10）**。当前 49 条跨包边均由 stable/temporary policy
解释；12 包历史 SCC 可缩小但不得扩大，临时例外具备 owner、退役条件和到期日。
Architecture guard 与 19 个单测已进入主门禁。

- 纯 Python AST 扫描跨包 import 和字面量 dynamic import；
- 目标允许边 + 临时 exception policy；
- 禁止新增边、扩大 SCC、过期或陈旧 exception；
- 在主门禁中运行。

详细计划：
`docs/superpowers/plans/2026-07-10-gate-1a-architecture-fitness.md`。

### Gate 1B：自动测试选择

状态：**Completed（2026-07-11）**。实现已接入唯一
`scripts/critical-quality-gate.sh`：unit+contract 与 Vitest 自动发现，慢速测试由 policy +
CodeGraph additive selector 决定；backend 覆盖率在 selected integration/E2E 后 append，随后执行
80% changed executable line 与关键 branch baseline。CI 使用完整 Git history、稳定 base/head/mode、
90 分钟 job 上限和 1200 秒 suite watchdog，并上传 selector/coverage artifacts。

聚焦证据：selector + coverage guard `48 passed`；`mypy src` 对 625 个源文件全绿；真实 DB
跨 session 解锁与 latest-attempt-wins `2 passed`；权限 pending 双击先红后绿；本 Gate 前端页面、
FSM、权限和兼容入口聚焦回归最终 `48 passed`。

完整门禁证据：backend unit+contract branch coverage `2665 passed, 1 skipped`；Vitest 209 files /
`1329 passed, 6 skipped`，430.31 秒自然退出；generic/smoke/newcomer/presentation/sales Playwright
分别为 3/9/11/2/1 passed（newcomer 仅 1 个真实收费 Provider 条件 skip）；selected backend
integration/E2E `598 passed, 21 skipped`；changed executable lines 41/50（82%），关键 branch
无缺失、无 floor 回退，最终输出 `Critical quality gate passed`。独立 Trellis check 修复 1 项跨
runner fixture fallback 后剩余阻塞 finding=0。

- backend unit + contract 和全量 Vitest 自动发现；
- integration/E2E 使用 changed paths + CodeGraph affected 选择；
- 保留 critical-quality-gate 的关键路径 E2E；
- 增加 changed-line coverage 和关键状态机 branch coverage。

前置：**已满足**。Gate 0B 后端与 Gate 0C 前端全量均已绿色，未引入永久排除列表。

## Gate 2：Realtime Session Engine tracer bullet

状态：**Completed（2026-07-11）**。Presentation 的 `stepfun_realtime` 路径默认由
`PresentationRealtimeEngineHandler` 组合 `RealtimeSessionEngine` 与命名 Legacy Adapter；
`PRESENTATION_REALTIME_ENGINE_ENABLED=false` 在构造前切回 Legacy，每个 session 只构造一个
handler。Engine 显式维护 versioned Connection/Turn/Grounding/Evidence state；snapshot 仅
additive 新增 `runtime_state.realtime_engine` 并兼容 pre-Gate 恢复。兼容 Adapter 保持现有
message/score/report/reconnect 单 writer，Presentation 不构造 Sales capability objects，Sales
默认仍启用自身能力。真实 Golden differential 已覆盖完整事件、持久化、snapshot、reconnect
epoch、grounding/evidence terminal state 和 mutation sensitivity。

完整门禁证据：backend unit+contract `2903 passed, 1 skipped`；Vitest 209 files /
`1329 passed, 6 skipped`；generic/smoke/newcomer/presentation/sales Playwright 分别为
`3/9/11/2/1 passed`（newcomer 仅 1 个既有真实收费 Provider 条件 skip）；selected backend
integration/E2E `598 passed, 21 skipped`；changed executable lines 802/878（91.34%），critical
branch 无 changed missing line、无 floor 回退，最终自然输出 `Critical quality gate passed`。

详细计划：
`docs/superpowers/plans/2026-07-11-gate-2-realtime-session-engine.md`。

Gate 2 没有完成 Provider/Grounding 中立化。兼容 Adapter 仍复用 `sales_bot` StepFun mixins，
所以 `presentation_coach -> sales_bot` 临时 policy edge 继续保留；退役条件由 Gate 3 完成。

已完成变更包：

1. Golden Conversation Contract inventory；
2. 显式 ConnectionState/TurnState/GroundingState/EvidenceState；
3. Engine shell + 旧 Handler Adapter；
4. Presentation Scenario Hooks；
5. Presentation 新旧路径 differential test；
6. 切换 Presentation，保留快速回滚；
7. 删除 Presentation “继承 Sales 后关闭能力”的路径。

验收：Presentation 外部行为完全兼容，且不再构造 Sales 能力。

## Gate 3：Provider 与 Grounding 深化

变更包建议：

1. `RealtimeProviderPort` 和 provider capability contract；
2. StepFun Adapter + event codec；
3. 本地 Fake Provider contract suite；
4. Grounding prepare/retrieve/decide/overlay/block 收入单一 Module；
5. 删除 Tool/Grounding 双缓存；
6. 统一 timeout、fallback、diagnostics 和 metrics。

验收：Fake Provider 不修改 Engine 即可运行；Grounding 只有一个状态和缓存权威。

## Gate 4：Roleplay、配置与评估所有权

变更包建议：

1. 中立 Roleplay DTO/hash/freeze baseline；
2. compiler/disclosure/turn-context strangler；
3. Situation Pack Adapter；
4. Configuration Governance Module；
5. admin delivery Adapter；
6. Evaluation Evidence/Scenario ports；
7. 删除 evaluation ↔ sales/presentation/curriculum 反向边。

验收：Roleplay hash 和历史报告不变；相关 SCC 被拆开。

## Gate 5：训练闭环与前端 Locality

变更包建议：

1. Training Journey 只消费报告/Evidence projection；
2. 报告 DTO mapper/ViewModel；
3. 报告 actions 和页面状态抽离；
4. API domain factory/types barrel 增量拆分；
5. `common/db/models.py` 物理拆分但保留统一 metadata；
6. repository/projection 替代跨域 ORM import。

验收：报告或训练闭环变化不再同时修改全局页面、全局 DTO 和全局 client。

## Gate 6：兼容层退役和收益复核

- 删除无生产消费者的 plugin 字符串入口和浅 Interface；
- 删除已被 Engine 取代的 Mixin 状态写入；
- 删除消失的临时依赖 exception；
- 重跑 CodeGraph impact、Git 共变和关键文件 fan-in；
- 更新 `docs/architecture.md` 为已实现事实；
- 每项 ADR 标记完成、保留或后续决策。

验收：架构收益由依赖图、affected tests、共变半径和关键路径验证时间证明。

## Gate 之间的硬依赖

```text
Gate 0A ─┐
Gate 0B ─┼─> Gate 1B ─> Gate 2 ─> Gate 3 ─> Gate 4 ─> Gate 5 ─> Gate 6
Gate 0C ─┘       ↑
Gate 1A ─────────┘
```

Gate 0A 与 Gate 1A 可以并行；Gate 1B 必须等待全量测试绿色。Gate 2 以后每个 Gate
都必须以前一 Gate 的行为合同和 architecture policy 为输入。

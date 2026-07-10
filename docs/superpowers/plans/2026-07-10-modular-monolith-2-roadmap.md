# 模块化单体 2.0 AI 原生实施路线图

日期：2026-07-10
设计：`docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`
ADR：`docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`

## 计划单位

本路线图按 Gate 和独立变更包推进，不按人周推进。预计 27–39 个变更包；每包
1–3 个提交、一个明确 reviewer gate、一个可独立运行的验证集合。

## Gate 0：恢复测试和合同事实

### Gate 0A：平台合同真相

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

当前已复现的失败簇：

- audio evaluation scenario 治理后，旧 fixture 缺 `scenario_key`/受控 config；
- learning topic/path/quiz 收口后，旧测试仍按旧发布和解锁语义构造数据；
- learner-only 与管理员读取权限断言和当前对象级权限口径不一致；
- projection/lineage 测试对新训练记录真源的预期漂移；
- secret scan 默认路径断言和当前证据目录不一致；
- PPT forbidden word contract 漂移。

此 Gate 必须先逐簇确定“生产 bug”还是“测试 fixture 漂移”，再编写独立计划；禁止
在未核对领域规则前批量修改断言。

验收：后端 unit + contract 全量绿色；任何隔离项有 owner、原因和到期日。

### Gate 0C：前端回归真相

当前已复现：

- dashboard greeting 测试依赖实际系统时钟，未冻结时间；
- business-skills 的 16 个失败都先落入“学习专题未发布”分支，说明测试共享 mock
  未覆盖新增 topic-governance API，而不是 16 个独立 UI bug；
- 全量 Vitest 运行超过 5 分钟，需建立 per-file duration 和 open-handle 诊断。

验收：全量 Vitest 绿色且能在规定 CI timeout 内自然退出。

## Gate 1：建立架构和测试护栏

### Gate 1A：跨包依赖与 SCC guard

- 纯 Python AST 扫描跨包 import 和字面量 dynamic import；
- 目标允许边 + 临时 exception policy；
- 禁止新增边、扩大 SCC、过期或陈旧 exception；
- 在主门禁中运行。

详细计划：
`docs/superpowers/plans/2026-07-10-gate-1a-architecture-fitness.md`。

### Gate 1B：自动测试选择

- backend unit + contract 和全量 Vitest 自动发现；
- integration/E2E 使用 changed paths + CodeGraph affected 选择；
- 保留 critical-quality-gate 的关键路径 E2E；
- 增加 changed-line coverage 和关键状态机 branch coverage。

前置：Gate 0B/0C 全绿，避免把现有失败引入永久排除列表。

## Gate 2：Realtime Session Engine tracer bullet

变更包建议：

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

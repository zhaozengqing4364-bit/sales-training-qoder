# Gate 6 收益复核

日期：2026-07-12 UTC

## 可比基线与结果

| 指标 | Gate 6 前 | Gate 6 后 | 结论 |
|---|---:|---:|---|
| 治理包数量 | 15 | 15 | 模块范围未偷换 |
| 跨包边 | 52 | 51 | 删除 `presentation_coach -> sales_bot`，未新增边 |
| 多包 SCC | 1 个、7 包 | 1 个、7 包 | 未扩大；Gate 6 不夸大为已拆散历史 SCC |
| `training_runtime/plugins.py` | 471 行 | 211 行 | 删除 260 行无消费者描述器与动态字符串入口 |
| `ScenarioPluginEntrypoint` | 存在 | 删除 | 生命周期/证据/评估/报告的浅字符串 API 退役 |
| `common.roleplay_contracts` | 35 行、1 个生产转发消费者 | 删除 | Curriculum 直接依赖 `roleplay` owner |
| Presentation 对 Sales import | 1 个源位置 | 0 | 具体适配只在应用根组合 |

最终图为 51 条边；唯一多包 SCC 仍是
`agent/common/curriculum_practice/evaluation/prompt_templates/sales_trainer/support`。
`common -> roleplay` 仍由 `common/business_rules/defaults.py:9` 产生，因此正确保留。

## 影响半径与测试证据

- 变更前 CodeGraph：`ScenarioRuntimeHandlerSelection` 影响 10 个 symbol，
  `dispatch_scenario_plugin` 影响 13 个，旧 Presentation concrete handler 影响 129 个，
  `common.roleplay_contracts` 影响 6 个。
- 实施后 `codegraph sync .`：2043 files、39422 nodes、115358 edges，索引为最新状态。
- 对核心运行时变更执行 `codegraph affected` 选出 227 个测试文件。共享 StepFun transport 的高 fan-out
  说明不能仅以 9 个 Gate 6 合同测试作为完成证据，必须保留 full backend 与 canonical gate。
- Gate 6 聚焦矩阵：161 passed，pytest 39.39 秒、端到端 shell 48.129 秒；覆盖 closed factory、
  Presentation root composition、Engine/rollback、Roleplay owner 与 practice evidence consumer。

## 保留面与删除检验

| 面 | 当前证据 | 决策 |
|---|---|---|
| `common.db.models` | 222 个后端生产源码 importer；274 行；统一 metadata/import-order 仍是身份权威 | retained |
| frontend `types.ts` | 262 个源码 importer；6936 行 | retained |
| frontend `client-domains.ts` | 519 行；领域客户端迁移仍在兼容期 | retained |
| Legacy Grounding adapter/cache | Grounding flag=false 时真实构造 | retained |
| Presentation Engine / Provider / Grounding flags | 三个 constructor-time rollback 仍受 2x2/2x2x2 测试保护 | retained |
| `common -> roleplay` defaults edge | 活跃 business-rule registry 源 | follow-up decision |

这些保留项不是 Gate 6 遗漏。缺少生产 rollout 遥测、外部 consumer inventory 或完整 deprecation window
时强删，会降低回滚能力或破坏 ORM/API identity。

## 共变解释

Gate 5 固定的历史基线为：报告与全局 types 同时改动 22 次，types 与全局 client 同时改动 55 次。
Gate 6 没有修改前端文件，因此没有继续增加这两组共变；但一次零前端改动的架构切片不能证明历史
共变率已经下降。下降结论必须等待后续领域功能的提交样本，当前只声明“未扩大”。

## 结论边界

Gate 6 的可证收益是：少一条真实跨域边、闭集工厂替代可执行字符串、删除两个无消费者浅表面、
把隐藏的 MRO 要求显式化，并保持 SCC、协议、写入权威和 rollback 不恶化。它没有完成历史七包 SCC、
模型 façade 或前端 façade 的后续迁移，也不把这些工作伪报为闭环。

## Final canonical evidence

唯一 clean-start canonical gate 于 2026-07-12 03:08:56–03:50:03 UTC 自然 exit 0：backend
`3322 passed, 1 skipped`、Vitest 213 files / `1345 passed, 6 skipped`、Playwright
generic/smoke/newcomer/presentation/sales 为 `3/9/11/2/1 passed`（一个既有真实收费 Provider 条件
skip）、selected backend `598 passed, 21 skipped`、changed executable lines 7326/8048（91.03%），
violations 为空，末行 `Critical quality gate passed`。

# 模块化单体 2.0 Gate 6：兼容层退役与收益复核

## Goal

完成模块化单体 2.0 最后一个 Gate：删除已证明无生产消费者的浅兼容入口，把动态字符串运行时选择
收敛为闭合集合，在应用根组合 Presentation/StepFun 兼容运行时并消除
`presentation_coach -> sales_bot` 静态依赖；对仍有真实消费者或尚未经过发布窗口的兼容层作明确保留
决策，以可执行依赖图、影响测试、共变半径和唯一 canonical gate 证明收益。

## What I already know

- Gate 0A–5 已闭环并归档，Gate 5 clean-start canonical gate 自然输出
  `Critical quality gate passed`。
- 用户已批准总体设计、ADR 与 Gate 路线图，并要求不中断执行、不派发子代理。
- 当前政策基线为 15 包、52 条边、一个七包 SCC；Presentation 到 Sales 只有一个静态 import 位置。
- 兼容删除必须基于消费者事实，不得为了“全部删除”破坏 rollback、模型 identity、Alembic 或前端 API
  兼容。

## Requirements

### Closed runtime selection

- `ScenarioRuntimeHandlerSelection` 只携带 scenario、mode、route 和非空闭集 `RuntimeHandlerFactoryKey`。
- Sales StepFun、Presentation legacy、Presentation StepFun rollback、Presentation Engine 四种工厂均由应用根
  显式映射；不得使用 `import_module`、模块路径或属性名字符串执行代码。
- 未知 factory key 必须在构造前 fail closed，不构造任意对象。
- 删除无生产消费者的 `ScenarioPluginEntrypoint` 及 session start/end/evidence/evaluation/report descriptor
  方法；插件只负责运行时选择与可观察 diagnostics。

### Presentation dependency retirement

- Presentation StepFun 文件不再 import `sales_bot`；Presentation 行为以 mixin/structural contract 表达。
- 顶层 composition root 组合 Presentation mixin 与 Sales shared transport base，提供 legacy rollback 与
  Engine adapter factory；Presentation domain 不依赖 composition root。
- 保持现有 2x2x2 rollout、Golden wire、snapshot restore、reconnect、grounding/evidence projection 和
  single-writer 行为不变。
- 删除确实被 Engine authority 替代且无调用的重复 state writer；仍参与 default/rollback 的 bridge 明确
  标记为 retained，不伪称已删除。

### Compatibility inventory

- Curriculum 和测试迁移到 `roleplay` owner 后删除 `common.roleplay_contracts` forwarding module。
- 只有实际消失的 temporary exception 才从 policy 删除；仍由 active business-rule registry 产生的
  `common -> roleplay` 必须保留并记录具体来源。
- `common.db.models`、全局前端 type/client façade、Legacy Grounding cache 和三项 rollout flag 按消费者、
  deprecation-window 与 rollback 证据逐项标记 `retired`、`retained` 或 `follow-up decision`。
- 不新增另一个全局 barrel、动态服务定位器或 architecture allowlist 绕过。

### Benefit proof and documentation

- 记录实施前后 edge/SCC、compatibility symbol/fan-in、CodeGraph affected tests、关键聚焦测试耗时、Git
  co-change 基线与 canonical gate 结果。
- 更新总体设计、ADR、roadmap、`docs/architecture.md` 和 Trellis specs 为已实现事实；所有保留项包含
  owner、reason、retire_when 与验证方式。
- Brooks architecture audit 和 Trellis check blocking finding 均为 0。

## Acceptance Criteria

- [x] 生产代码不存在 plugin runtime module/attribute executable strings 或动态 import handler path。
- [x] `ScenarioPluginEntrypoint` 及无消费者 lifecycle/evidence/report descriptor surface 删除，diagnostics
      和 scenario dispatch 保持可用。
- [x] `presentation_coach -> sales_bot` 实际边和对应 policy target 消失；依赖边不增加，SCC 不扩大。
- [x] Presentation default/rollback、Sales StepFun、wire/snapshot/persistence/reconnect/evaluation differential
      全绿，未知 factory key fail closed。
- [x] `common.roleplay_contracts` forwarding module 删除；`common -> roleplay` 的 remaining source 仅为明确
      retained 的 business-rule registry（若仍存在）。
- [x] Model/frontend/flag/Legacy cache 逐项 consumer proof 与 retain/retire 决策写入 ADR/spec，无过度删除。
- [x] CodeGraph impact、依赖图、fan-in、共变与关键路径验证时间形成 before/after 收益报告。
- [x] Ruff、full mypy、architecture guard、OpenAPI、后端 affected、Vitest/TypeScript/ESLint、相关 Playwright
      与 changed coverage 满足唯一 clean-start canonical gate。
- [x] Brooks audit 100/100 且 Critical/Warning/Suggestion=0；Trellis blocking finding=0。

## Definition of Done

- TDD Red → Green → Refactor 和任何计划偏离记录在 `implementation-notes.md`。
- 新的 closed factory/composition/retirement contract 写入 `.trellis/spec/` 并由 AST/behavior tests 保护。
- 详细实施计划 checkbox、authority docs、task JSONL、archive 和 journal 全部完成。
- 工作区最终只保留用户的 readiness 文档改动；不 push、不部署、不调用收费 Provider。

## Out of Scope

- 删除仍有 222 个生产 importer 的 `common.db.models` 或仍有 262 个源码 importer 的前端 type barrel。
- 在缺少发布遥测和 deprecation window 时删除 Provider/Grounding/Presentation rollback flag。
- 重写 StepFun 协议、拆微服务、改变数据库 schema、生产数据或用户界面。

## Research References

- `research/compatibility-retirement-inventory.md` — 当前消费者、依赖图、保留/退役分类与选定架构。

## Assumptions

- 已批准的 Gate 6 roadmap 和持续 Goal 授权等同于本 PRD 的需求确认；无需再次打断用户。
- 顶层 Python 模块是现有应用 composition root 范围，允许依赖多个 domain，但 domain 不得反向依赖它。

# ADR：新人基础训练领域与模块所有权

- 日期：2026-07-16
- 状态：Accepted（目标合同；切片 0 不代表目标模块已创建）

## 决策

新人基础训练采用模块化单体。`newcomer_training` 拥有路径、Cohort、Enrollment、通用 Attempt、Gate 与 Journey；`learning`、`audio_assessment`、`ai_coach` 分别拥有活动内部记录和结果；`competency_evidence` 只拥有不可变能力事实；`readiness` 拥有档案、复核、重练与申诉。平台能力由 `identity_access`、`ai_platform`、`task_runtime`、`storage`、`configuration_governance`、`observability` 与 `shared_kernel` 提供。

模块内部依赖方向固定为 `delivery -> application -> domain/ports`，Adapter 实现 Port，应用组合根装配具体 Adapter。业务模块不得跨域导入 ORM、Repository 或内部 Service；`shared_kernel` 不得反向依赖业务模块。跨域只传稳定身份、不可变快照引用、Command、Query 或版本化 Event。

## 原因与后果

现有 `sales_trainer` 同时承担路径、题库、音频、Coach 与 Readiness，是迁移来源而非目标边界。目标接口及唯一写权威见 [`../architecture/newcomer-foundation-contract.md`](../architecture/newcomer-foundation-contract.md)。


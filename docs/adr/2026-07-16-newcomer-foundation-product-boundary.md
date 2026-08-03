# ADR：新人销售基础训练首发边界

- 日期：2026-07-16
- 状态：Accepted（目标合同；切片 0 不代表功能已上线）

## 决策

首发产品只承诺新人完成学习、测验、录音讲解、结构化 AI Coach、异步客户场景录音、证据归档与人工复核，并以 `foundation_ready` 表示“基础训练达标”。该结论不表示真实客户场景胜任，也不预测销售业绩。

Realtime 客户语音对练不进入首发导航、`ActivityDefinition` 封闭联合、默认种子、权限矩阵或验收用例。未来如接入，必须通过新的 `PathRevision` 和更高等级结论 `customer_roleplay_ready`，不得改写既有 `foundation_ready` 语义。

## 原因与后果

当前运行代码仍包含 `realtime_roleplay` Handler、Renderer、种子和路径配置，这是待迁移的 Legacy 事实，不是本 ADR 的目标产品合同。后续切片必须先建立五类首发活动的新权威，再删除对应旧入口；切片 0 不修改业务代码、路由或数据库。


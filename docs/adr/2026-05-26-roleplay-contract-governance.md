# ADR 2026-05-26: Roleplay Contract 情景包治理与运行时权威

## Status

Accepted. Revised by v2 on 2026-05-27.

## Context

客户对练中，AI 曾在“首次拜访”场景里说出“上次拜访”“之前我们聊过”等与场景设置冲突的话。这类问题不能继续靠更长 prompt 修补，需要把关系史、可见信息、隐藏信息和违规策略变成可发布、可冻结、可检测的运行时合同。

仓库已有配置治理能力：`BusinessRuleConfig` 负责 draft/publish/rollback/audit，`ConfigBundle` 负责管理面统一入口；课程化域已有 `PracticeTemplate` 发布门禁和 `RuntimeSnapshotService` 冻结原则；Sales 实时链路已有 `VoiceInstructionCompiler` 和 `SalesStageCapability`。

## 2026-05-27 Revision Context

后续配置资产中心设计暴露了原决策第 3 条的过度收缩：`Situation Pack` 不只是一个普通业务规则值，它有可复用资产身份、独立引用关系、版本、状态、兼容模式、发布前校验、导入导出和影响面查询需求。若长期把多个情景包压在一个 `BusinessRuleConfig` JSON ruleset 中，`common.business_rules` 会持续承载 roleplay 领域细节，导致通用配置基础设施与客户对练领域知识耦合。

因此，本 ADR 修订原有“不得新增独立配置表”的绝对约束。新的约束是：`Situation Pack` 可以演进为一等领域资产，但发布、预览、回滚、审计和 Config Center 入口必须继续接入统一配置治理，禁止产生第二套孤立 admin 生命周期。

## Decision

1. 新增 `Roleplay Contract` 作为客户对练运行时角色权威。`Persona`、`RoleProfile`、`CaseItem`、`PracticeTemplate`、`ScoringRuleset` 和 Situation Pack 都只是编译输入。
2. `Roleplay Situation` 只管关系史、情景边界、可见/隐藏信息范围和违规策略；销售漏斗阶段仍由 `SalesStageCapability` 维护。禁止新增第三套 conversation state machine。
3. Situation Pack 的领域模型允许一等资产化。短期实现可以继续由 `BusinessRuleConfig` / `ConfigBundle` 承载，配置 key 为 `roleplay.situation_packs.ruleset`；长期可以迁移为独立 `SituationPack` 实体、Repository 和 Service。
4. 不允许为 Situation Pack 创建孤立 admin 生命周期。无论底层存储是 `BusinessRuleConfig` ruleset 还是独立实体，draft/validate/preview/publish/rollback/audit、Config Center 展示、操作 reason、trace_id 和权限边界都必须复用或适配统一配置治理。
5. 若 Situation Pack 独立实体化，`BusinessRuleConfig` 不再承载包内领域字段，只能作为迁移期 backing store 或 ConfigBundle 适配来源。Roleplay 领域校验、默认值、引用查询、兼容性和 hash 计算应收敛到 `curriculum_practice` / roleplay 领域模块。
6. 运行时和发布门禁读取 Situation Pack 必须经过 `SituationPackRepository` 或等价深模块接口。调用方不得依赖具体存储形态，也不得直接解析 ConfigBundle snapshot 或 ORM row。
7. 内置默认包只能作为安全兜底和迁移保护。缺失或非法配置可回退到内置默认以避免系统不可恢复；但新模板发布仍由 Roleplay Contract gate 阻断语义冲突。生产长期权威应逐步迁移到已发布配置/资产版本。
8. 课程闭环在创建会话时冻结 `curriculum_snapshot.roleplay_contract`；平台直练在 voice policy 中冻结 `roleplay_contract`。运行时不得读取 latest asset 重新拼语义。
9. `VoiceInstructionCompiler` 继续作为 prompt 编译承载；Roleplay Contract 只提供结构化合同和 visible payload，不新增并列 prompt compiler。
10. 热路径守门只做确定性检查。LLM judge 只属于离线 eval / 发布前回归，不进入 StepFun Realtime 同步链路。

## Consequences

### Positive

- 首访、复访、续约、价格谈判、投诉安抚等场景可以通过配置包治理，而不是散落在 runtime prompt。
- 发布、回滚、审计复用现有配置治理链路，满足长期可管理性。
- Situation Pack 可以按领域资产演进，避免 `common.business_rules` 长期理解 roleplay 细节。
- StepFun runtime 的角色上下文来自 frozen contract，避免后台配置变化影响已创建会话。
- hidden information 默认不可见成为代码底线，运营只能配置披露范围，不能绕过底线。

### Negative

- Situation Pack 若从 ruleset 迁移为独立实体，需要补迁移计划、双读/影子校验、ConfigBundle adapter、导入导出协议和引用版本冻结。
- 独立实体化不能减少发布治理复杂度，只是把领域内聚提高；治理适配仍必须实现。
- 历史会话保持 `legacy_unversioned` / `legacy_unstructured_roleplay`，不会迁移或重算。
- Streaming delta cancel、披露状态机、eval release gate 仍需后续切片补齐。

## Fixed Rules

- `SalesStageCapability` 是销售阶段 authority。
- `hidden_information` 默认不可见。
- blocking regenerate 最多一次。
- 历史 session 不迁移、不重算。
- Situation Pack 运行时消费必须经过 frozen Roleplay Contract，不读 latest entity/config。
- Situation Pack 可以独立建模，但不得拥有与 ConfigBundle/audit 平行的治理生命周期。

## Configurable Rules

- Situation Pack 的 relationship context defaults。
- initial / conditional / hidden information keys。
- forbidden claim patterns / topic codes / stage codes。
- conflict response strategy。
- runtime violation policy。
- PracticeTemplate 是否要求 Roleplay Contract。

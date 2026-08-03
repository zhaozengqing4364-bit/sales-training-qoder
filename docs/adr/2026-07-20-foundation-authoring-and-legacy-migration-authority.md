# ADR：Foundation 内容生产权威与 Legacy 迁移边界

- 状态：Accepted
- 日期：2026-07-20
- 风险等级：P1
- Supersedes：仅更正 `2026-07-17-foundation-admin-release-governance.md` 中“统一工作台已形成完整内容生产闭环”的实现状态，不改变其 ReleasePlan 单一发布权威
- 相关任务：`.trellis/tasks/07-19-newcomer-training-content-authoring-closure/`

## 背景

2026-07-18 的首发验收证明了 Foundation 运行时、标准 Seed、路径编排和发布链路可运行，但把“Seed 已创建资源”“路由存在”“路径可选择已有修订”误判成了“管理员可以生产全部真实训练内容”。当前 Legacy `sales_trainer` 仍保存用户真实 PPT、`石犀ppt讲解` 与 `demo讲解`；新学员入口只读取 Foundation，二者没有完成迁移。统一入口不能等同于只剩一个模糊工作台，也不能让 Legacy 恢复为第二写权威。

## 决策

### 1. 唯一写权威

| 资源/对象 | 唯一写权威 | Stable identity | 修订与发布 |
|---|---|---|---|
| 来源资料与多媒体内容 | `learning` 的 `SourceDocument` | `organization_id + stable_key`，API 使用 opaque `document_id` | `SourceDocumentRevision`；working/published 指针；ReleasePlan |
| 学习单元 | `learning` 的 `LearningUnit` | `organization_id + stable_key` / `unit_id` | `LearningUnitRevision`；ReleasePlan |
| 候选题、正式题目、测验 | `learning` | Candidate 使用独立 ID；Question/Quiz 使用组织内 stable key | Candidate 审核与 Question approval 分离；正式发布仍走 ReleasePlan |
| 录音材料、评分方案、异步场景 | `audio_assessment` | 分别为 `AudioMaterial`、`ScoringScheme`、`Scenario` 逻辑身份；不得只把 revision row 当作可编辑身份 | 继续由有类型 `AudioActivityResourceRevision` 保存修订；Authoring 必须提供明确 working/published 指针 |
| 结构化 AI 教练 | `ai_coach` 的 `CoachProfile` | `organization_id + stable_key` / opaque profile ID | `CoachProfileRevision`；ReleasePlan；Session 冻结 exact revision |
| 训练方案与执行信封 | `newcomer_training` | Path/Cohort/Enrollment/Attempt 各自稳定 ID | PathRevision + ReleasePlan；Enrollment/Attempt 冻结 |
| 跨资源正式生效、回滚和影响审计 | `configuration_governance` / `ReleasePlan` | `release_plan_id` | exact revision dependency closure；原子发布/回滚 |

不得新增通用“万能 JSON 资源表”，不得让管理聚合层直接写各领域 ORM，也不得恢复 Legacy `sales_trainer` 为新人训练写权威。Seed 与管理员 Authoring 是同一领域命令的不同调用者；Seed 存在不能作为 CRUD 完成证据。

### 2. 统一生命周期

所有可配置逻辑资源遵循：

```text
stable identity
  -> create/save working revision
  -> validate
  -> review/approve（内容风险需要时）
  -> ReleasePlan preview exact revision closure
  -> publish immutable revision
  -> supersede or archive logical resource
```

- 审核通过不等于发布：`approved` 只表示内容审核通过，绝不等于 `published`。
- 每个写命令校验 capability、organization/object scope、`Idempotency-Key` 和 `If-Match`；成功和高风险拒绝均审计。
- 已发布修订不可原地修改。Path、Enrollment、Attempt、Outcome、Evidence 引用的历史修订不可硬删。
- 快速新建只返回合法 working revision ref、当前状态、下一步动作和 capability；浏览器不得拼接内部 snapshot。
- ReleasePlan 失败不移动任何 published pointer；新发布不自动迁移既有 Enrollment。

### 3. Authoring capability

权限以动作 capability 为真值，不以菜单或角色字符串为真值。冻结的业务 capability 为：

- `view_content`、`edit_content`、`review_content`；
- `view_question_bank`、`edit_questions`、`review_questions`、`edit_quizzes`；
- `edit_audio_materials`、`edit_scoring_schemes`；
- `edit_coach_profiles`；
- `edit_async_scenarios`；
- `edit_paths`、`manage_cohorts`、`retry_assessments`、`regrade_results`、`review_readiness`；
- `publish_releases`、`rollback_releases`、`view_sensitive_audit`。

默认角色组映射如下；这是 capability 默认值，不替代对象级范围校验：

| 角色组 | 默认 capability |
|---|---|
| Content Editor | `view_content`、`edit_content`、`review_content`、`view_question_bank`、`edit_questions`、`review_questions`、`edit_quizzes` |
| Training Admin | `view_content`、`view_question_bank`、`edit_audio_materials`、`edit_scoring_schemes`、`edit_coach_profiles`、`edit_async_scenarios`、`edit_paths`、`manage_cohorts`、`publish_releases`、`rollback_releases` |
| Training Manager | `view_content`、`view_question_bank`、`manage_cohorts`、`retry_assessments`、`regrade_results`、`review_readiness` |
| Platform/System Admin | 本节全部业务 capability |

Prompt 正文、模型策略、Provider 配置与密钥继续由 `govern_ai` 及更高系统权限隔离。所有对象先限制 organization，再限制 Team/负责范围；跨组织对象按安全合同返回 404，无权限写返回 403。隐藏导航不能代替后端拒绝。

### 4. API 与错误语义

八类 Authoring 联合为：

```text
source_document | learning_unit | question | quiz |
audio_material | scoring_scheme | coach_profile | scenario
```

每类资源必须通过领域端口提供 list/search、create、get、save working revision、validate、compare、reference impact、archive，以及进入 ReleasePlan 的 exact revision ref。`prompt` 不是普通训练资源联合成员，由 AI 治理端口单独管理；Path 只能绑定其已发布 exact dependency。错误保持领域前缀，但统一语义：404 不存在或不可访问、409 状态/幂等/引用冲突、412 版本冲突、422 Schema/校验失败、429 限流、503 依赖能力不可用。

### 5. Legacy 迁移

- Legacy 只允许通过命名的只读 inventory/migration adapter 读取；不得双写、请求时自动修复或长期双读。
- `SalesTrainerMaterial`、active orchestration revision 和旧评分 Prompt 没有可靠 `organization_id`，inventory 必须标记为 `global_unscoped`；选择目标组织是 dry-run 前置条件。
- 迁移严格执行 `inspect -> dry-run -> resolve conflicts -> apply -> verify -> ReleasePlan preview/confirm -> cut over`。本 ADR 和 inventory 不提供 apply。
- 迁移键为 `source_system + organization_id + legacy_type + legacy_id + source_revision/hash`。同名同 hash 可复用；同名不同 hash、同 hash 多目标、缺文件/缺 hash、无法验证的 Prompt 必须进入人工处理。
- `石犀ppt讲解` 与 `demo讲解` 分别迁为独立 `audio_material + scoring_scheme + audio_assessment Activity`；PPT 先迁为 `SourceDocumentRevision(content_kind=slide_deck)`。不能把旧 Prompt 正文直接标记为已验证 AI 合同。
- 不迁移历史录音、旧评分结果、旧 Coach 会话、活跃 Enrollment 或缺 lineage Evidence。

字段级映射和冲突矩阵见 [`../architecture/newcomer-foundation-legacy-authoring-mapping.md`](../architecture/newcomer-foundation-legacy-authoring-mapping.md)。

## 结果

- “运行时可用”和“管理员 Authoring 完整”被明确分开；后续验收不得再用 Seed、路由或可绑定已有资源替代 CRUD/浏览器证据。
- 新管理端仍只有一个产品入口，但内部必须按训练方案、内容、题库、讲解评分、AI 教练、异步客户场景、学员评测和发布治理提供稳定工作区。
- 当前学员运行时、published revision、Enrollment、Attempt 和历史 Evidence 不因本决策改变。

## 回滚

本任务只改合同和只读报告，不修改业务数据或运行时路由。若合同有误，撤销本 ADR及其合同补充即可；不得以回滚文档为由恢复 Legacy 写入或删除历史修订。

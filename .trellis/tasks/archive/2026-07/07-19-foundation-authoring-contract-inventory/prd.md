# 新人训练内容配置权威契约与迁移清单

## Goal

先把“什么可以配置、由谁拥有、如何版本化、如何发布、旧数据如何映射”写成与真实代码和数据库一致的权威合同，纠正原首发验收中把“已有 Seed/已有路由/可绑定已有资源”误判成“管理员可完整配置”的结论，为后续九个子任务建立不可漂移的边界。

## Dependencies

- 无。
- 父任务：`../07-19-newcomer-training-content-authoring-closure/`。

## Deliverables

- 一份 Accepted ADR：Foundation 内容生产、资源修订与 Legacy 迁移边界。
- 更新 `newcomer-foundation-contract`、API contract、领域词表、管理端规范和原验收矩阵状态。
- 一份可重复执行的只读 inventory 工具及结构化报告，不修改任何数据。
- 一份 Legacy → Foundation 对象、字段、版本、权限和发布映射清单。
- 后续子任务可直接采用的资源类型、生命周期、capability 和错误语义。

## Requirements

### R1. 资源权威

明确并冻结以下唯一写权威：

- `learning`：`SourceDocument/Revision`、`LearningUnit/Revision`、`QuestionCandidate`、`Question/Revision`、`Quiz/Revision`；
- `audio_assessment`：`audio_material`、`scoring_scheme`、`scenario` 修订；
- `ai_coach`：`CoachProfileRevision`；
- `newcomer_training`：Path/Stage/Activity、Cohort、Enrollment、Attempt 通用信封；
- `configuration_governance`/`ReleasePlan`：跨资源正式生效、回滚和影响审计。

禁止新增通用“万能 JSON 资源表”绕过领域合同，也禁止恢复 Legacy `sales_trainer` 为新人训练写权威。

### R2. 生命周期合同

每类逻辑资源统一说明：

- stable identity；
- working revision；
- validate；
- review/approve（适用时）；
- ReleasePlan publish；
- immutable published revision；
- supersede/archive；
- 被 Path、Attempt、Evidence 引用时的历史保留规则；
- `If-Match`、幂等、组织范围和审计字段。

“审核通过”和“正式发布”必须是不同状态；Seed 创建与管理员 Authoring 必须是同一领域合同的不同调用者。

### R3. 管理 capability

冻结面向任务的 capability，而不是前端 role string：

- 查看/编辑/审核内容；
- 查看/编辑/审核题库与测验；
- 编辑录音材料与评分方案；
- 编辑 Coach Profile；
- 编辑异步场景；
- 编辑路径、管理班级、发布/回滚、查看审计；
- 高风险 Prompt/模型策略和密钥治理继续与普通内容编辑隔离。

每项 capability 明确角色默认映射、对象级范围和无权限响应；不能用隐藏菜单替代后端拒绝。

### R4. API 合同

为每类资源写出最小闭环端点或领域命令：list/search、create、get、save working revision、validate、compare、archive，以及进入 ReleasePlan 的 exact revision ref。快速新建返回可绑定的 working/published ref 和下一步状态，不允许前端拼接内部快照。

修正当前 `resource_type` 文档与实际资源 options 不一致的问题，明确 `scenario`、`scoring_scheme`、`coach_profile`、`audio_material` 的领域端口和发布闭包。

### R5. 只读 Inventory

工具必须按组织输出：

- Legacy 路径 active revision、活动、材料、材料版本、评分 Prompt 和引用；
- Foundation 路径、资源、published/working pointers 和 Seed 来源；
- 可自动映射项、缺失依赖、同名/同 hash 冲突、无法验证项；
- `石犀ppt讲解`、`demo讲解` 与 `石犀科技-企业介绍标准版（202606版）.pptx` 的明确映射候选；
- 建议迁移顺序和预计新增对象数。

inventory 不得打印密钥、完整 Prompt、个人敏感信息或受保护文件内容；默认只读，不能暗含 apply 开关。

### R6. 验收真值修正

原 acceptance matrix 中以下结论必须改为“运行时已具备、Authoring 未闭环”或重新打开：

- 所有缺失资源均可快速创建；
- 内容与题库工作台已经完整；
- 旧权威清理已经覆盖用户真实 PPT/Demo 数据；
- 管理团队可以在单一工作台完成全生命周期。

不得删除历史验收证据；使用补充说明和新任务链接保留审计链。

## Acceptance Criteria

- [ ] ADR、架构合同、API 合同、领域词表、前后端规范对资源联合和唯一写权威表述一致。
- [ ] 每个后续子任务的输入/输出对象、capability、生命周期和发布边界均无待猜测项。
- [ ] Inventory 在空库、Seed 库和当前开发库均可运行，输出稳定 JSON/Markdown 摘要且零写入。
- [ ] 当前库报告能定位两个旧讲解活动、对应 PPT、冲突项和 Foundation 目标缺口。
- [ ] 原验收误报被显式更正，不能再用路由/Seed 存在代替管理员 CRUD 证据。
- [ ] 不引入运行时双写、不改变学员路径、不迁移数据。

## Minimal Verification

- Inventory 纯函数和脱敏单元测试。
- 空库、重复数据、跨组织和当前 fixture 的针对性集成测试。
- API/ADR/索引链接及受控资源联合的契约检查。
- 仅对改动的 Python/Markdown 运行 Ruff/相关文档检查；不运行全量前后端测试。

## Out of Scope

- 不实现任何资源编辑页面。
- 不创建目标资源或修改 Legacy 数据。
- 不调整导航。
- 不执行切换、发布或 Enrollment 迁移。

## Risk And Rollback

- 风险等级：P1（权威合同和后续迁移输入）。
- Inventory 保证只读，无数据回滚需求；文档/合同错误通过撤销本任务变更恢复。
- 若发现现有 Accepted ADR 与真实代码冲突，记录新 ADR supersede 关系，不静默改写历史决策。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，达标后立即停止。


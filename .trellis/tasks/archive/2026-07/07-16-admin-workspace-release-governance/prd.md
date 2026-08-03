# 切片 6：统一管理工作台与发布治理

## Goal

为培训负责人、内容编辑、训练管理员和系统管理员建立统一的新人训练管理工作台，把路径编辑、内容与题目审核、Cohort/Enrollment 管理、任务异常、达标复核和发布治理组织成面向工作对象的操作流。

管理后台不能继续按数据库表或分散模块组织；用户必须在当前任务上下文内完成选择、快速新建、关联、预览、发布和失败恢复。

## Dependencies

- 切片 0：页面契约、权限、领域、API、状态和发布契约。
- 切片 1：后台任务、发布检查、AI 调用审计和队列。
- 切片 2：Path、内容、题目、Quiz、Cohort 和 Enrollment。
- 切片 3：Audio 队列、重试和重评。
- 切片 4：Coach Profile、Session 和人工帮助队列。
- 切片 5：Dossier、Review Queue 和 Retraining。

## Page Model

统一入口：`/admin/newcomer-training`

一级工作区按任务划分：

- 总览与待办；
- 路径与版本；
- 内容与题库；
- 学员与班级；
- 评测任务；
- 达标复核；
- 发布记录；
- 治理设置（仅相应 capability 可见）。

不得以九宫格大卡片作为主要导航，也不得把所有功能塞入同权重仪表盘。

## Requirements

### R1. Admin Capability Projection

- 后端返回集中 capability projection。
- 前端不复制 role string 分支。
- 至少区分：
  - 查看运营总览；
  - 编辑路径；
  - 编辑内容；
  - 审核题目；
  - 管理 Cohort/Enrollment；
  - 重试评测任务；
  - 重评/失效结果；
  - 执行达标复核；
  - 发布/回滚；
  - 管理 Prompt/模型策略；
  - 查看敏感审计。
- 无权限时后端拒绝，前端展示明确无权限状态和申请路径。

### R2. Operations Overview

- 首页突出当前需要处理的工作，而非装饰性统计。
- 聚合并去重：
  - 发布阻塞；
  - 待审核题目；
  - 失败/对账中的任务；
  - 待复核 Dossier；
  - 需要人工帮助的 Coach Session；
  - Enrollment 数据冲突；
  - 即将过期或长期等待项。
- 每项解释优先级、影响对象和下一步。
- 数字必须来自真实查询，禁止虚构“AI 洞察”或无行动意义图表。

### R3. Three-Pane Path Editor

- 基于现有 UI 设计和组件体系实现三栏编辑器：
  - 左：Stage/Activity 结构树；
  - 中：选中对象编辑表单；
  - 右：实时预览、校验和引用影响。
- 支持键盘选择、拖动/按钮排序、复制、归档和未保存离开提醒。
- 每个 Activity 根据类型渲染有类型配置表单。
- 表单覆盖 label、helper、字段错误、服务端错误、dirty、submitting 和重复提交防护。
- 不允许编辑器直接写原始 JSON 作为普通操作。

### R4. In-Flow Resource Binding

- 当 Activity 缺少 Lesson、Quiz、Scenario、Scorecard、CoachProfile 或 Prompt 时，在当前编辑器 Drawer/Popover/Inspector 中：
  - 搜索已有对象；
  - 预览版本和状态；
  - 选择并自动关联；
  - 快速新建最小草稿；
  - 后台同步到标准对象；
  - 稍后补充或指派他人；
  - 处理重复、权限和失败。
- 禁止强迫管理员离开路径编辑去另一个模块补资料再返回。

### R5. Validation And Preview

- 草稿保存与正式校验分离。
- 校验结果按阻塞、警告、建议分类，定位到具体 Stage/Activity/字段。
- 发布预览使用与学员运行时相同的编译器和 Activity Runtime。
- 可用真实已发布资源或受控 preview data，不向普通 UI 泄露 test/mock 字样。
- 未注册 Activity、未发布资源、断裂 Anchor、无能力映射、无权限引用和非法规则必须阻止发布。

### R6. Content Workspace

- 原始材料与整理后 LearningUnit 明确分栏/版本。
- 支持上传/选择 Source、解析状态、来源定位、编辑学习单元、修订比较、审核和发布。
- 解析或 AI 整理为持久化任务，显示部分成功和恢复路径。
- 管理员能看到哪些 Path/Question 正在引用当前修订。
- 删除已引用内容默认归档，并展示影响。

### R7. Question Review Workspace

- 以 QuestionGenerationBatch 和 Candidate 队列组织审核。
- 支持来源预览、重复提示、答案/rubric 校验、能力映射、批量批准/拒绝/退回。
- 批量操作先预览影响，逐项返回成功/失败。
- AI 生成内容明确标为草稿；不得用闪光/机器人装饰代替状态。
- 正式题目与 Candidate 状态、修订和发布边界清晰。

### R8. Cohort And Enrollment Workspace

- 支持创建 Cohort、绑定 PathRevision、分配学员、查看进度和冻结修订。
- 缺少用户/组织关联时在当前流程选择或快速创建最小对象，遵守权限、去重和审计。
- PathRevision 迁移提供 dry-run、影响预览、选择范围、并发保护和逐项结果。
- 禁止发布新版自动迁移活跃 Enrollment。
- 批量导入有模板、校验、预览、部分失败报告和幂等。

### R9. Assessment Operations

- 统一查看 Audio、短答、题目生成和 Coach 的持久化任务。
- 运营视图展示用户语言状态、业务对象、等待时长、失败分类和可执行动作。
- 技术详情放在受权限 Inspector/审计页。
- 重试、取消、恢复、重评、对账和失效操作按风险提供 preview/confirm/reason/audit。
- 不能用“重试全部”绕过对象范围和幂等检查。

### R10. Readiness Review Workspace

- 复用切片 5 的队列、Dossier、Snapshot 和决策命令。
- 主区域以学员档案和证据为工作对象，不以聊天或原始事件流为中心。
- Reviewer 可就地查看来源、音频、transcript、评分版本和补练历史。
- 发起补练时在当前页选择/创建/关联目标 Activity。
- 正式决策后结果持久化并有明确成功页/记录位置。

### R11. ReleasePlan

- 将路径、内容、题目、Quiz、Scorecard、CoachProfile、Prompt 和能力映射的发布组织为 `ReleasePlan`。
- ReleasePlan 保存目标修订集合、依赖图、创建者、状态、校验报告、影响预览和审计。
- 发布前检查：
  - 所有引用存在且已批准；
  - Contract Hash 与 Runtime 兼容；
  - 无循环引用；
  - 能力映射完整；
  - 权限与组织范围合法；
  - 必需 Provider/配置可用；
  - Enrollment 影响明确；
  - 迁移/回滚可执行。
- 发布操作在数据库内尽可能原子；外部检查在事务外完成。
- 任一步失败时旧发布版本继续有效，不出现半发布。

### R12. Rollback And Supersede

- 发布后不修改已发布 Revision。
- 回滚通过重新激活已知稳定 ReleasePlan 或发布新修订，不物理删除历史。
- 回滚前预览对新 Enrollment、活跃 Enrollment、任务和引用的影响。
- 已冻结 Enrollment 默认继续使用其原 Revision。
- 所有发布/回滚动作记录原因、操作者和结果。

### R13. Settings And Governance

- 业务阈值、活动策略、模型策略、Prompt、Provider 路由和 feature flag 有明确管理入口与权限。
- 设置有默认值、校验、修订、预览、发布、回滚和审计。
- 不把配置散落在页面、本地存储或深层业务代码。
- 敏感密钥不在普通后台显示或回传；只展示已配置状态和必要指纹。

### R14. States And Resilience

- 每个工作区覆盖 loading、empty、no result、error、permission denied、partial/stale、conflict、submitting、success、cancelled 和 retrying。
- 长任务可离开、后台继续、通知和回到结果位置。
- recoverable failure 保留用户输入。
- 批量操作不能把部分失败显示为全部成功。
- 重要结果不能只用 Toast。

### R15. Audit And Observability

- 每个高风险操作带 request/trace、actor、scope、before/after revision、reason 和 result。
- 管理员可按业务对象检索审计，而不是只查原始日志。
- 日志和导出脱敏。
- 总览指标可追到具体队列或对象，避免不可行动的总数。

## Acceptance Criteria

- [x] `/admin/newcomer-training` 成为统一管理入口。
- [x] 用户按工作任务而非数据库模块完成路径、内容、题目、班级和复核。
- [x] 三栏路径编辑器复用现有设计体系，主操作、校验和预览清晰。
- [x] 缺少关联资源时可在当前编辑流选择或快速新建，不强制跳页。
- [x] 发布前完整校验所有引用、能力映射、Runtime、配置和影响。
- [x] 发布失败时旧版本继续有效，不出现半发布。
- [x] 新 PathRevision 不自动迁移活跃 Enrollment。
- [x] Candidate 批量审核和 Enrollment 批量导入均有预览与逐项结果。
- [x] 高风险重试、重评、失效、发布和回滚均有权限、原因、确认和审计。
- [x] 所有重要异步状态可离开后恢复，并有持久化结果位置。
- [x] 普通管理界面不泄露 raw JSON、Prompt 原文、内部 task type 或敏感 Provider payload。
- [x] 键盘、焦点、窄屏、长文本、大数据量和无权限状态经过验证。

## Verification

- API 权限矩阵和对象级权限集成测试。
- ReleasePlan 原子性、并发发布、失败回滚和旧版本可用性测试。
- 批量操作部分失败、幂等和审计测试。
- 前端组件/页面测试：dirty、conflict、permission、partial、long task。
- 浏览器 E2E：从材料上传到路径发布；Cohort 创建到 Enrollment 分配；Dossier 复核到补练。
- 浏览器视觉检查：现有 UI tokens、桌面、窄屏、200% zoom、键盘。

## Definition Of Done

- 运营团队能在一个工作台完成首发训练全生命周期。
- 发布过程可预览、可验证、可审计、可回滚。
- 上下文内完成原则落实到资源绑定、学员分配、补练和异常处理。
- 管理权限以后端 capability 为权威。
- 旧分散写入口删除或只读封存。

## Out Of Scope

- 不重新设计全站视觉系统。
- 不建设通用低代码平台或任意工作流编辑器。
- 不实现 Realtime 运营控制台。
- 不向普通管理员开放任意 SQL、JSON 或 Provider 密钥编辑。

## Risk And Rollback

- 风险等级：P1。
- 最大风险是发布半成功和管理操作越权。
- ReleasePlan、Revision、capability、审计和 feature flag 是核心保护。
- 回滚以旧 ReleasePlan 继续有效为原则；不能依赖手工改表。

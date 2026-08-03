# 路径内资源快建、绑定、预览与发布校验

## Goal

补齐五类 Activity 的上下文内配置能力：管理员在路径编辑器里发现缺失资源时，可以搜索、预览、快速新建、自动绑定并继续当前工作；完整编辑仍可进入资源详情，但不能要求用户先离开路径、手工记住对象再回来。

## Dependencies

- 内容资产、题库测验、录音评分、AI Coach、异步场景的 Authoring API 和资源修订合同均已完成。
- 管理端 capability 合同已冻结。

## Binding Matrix

| Activity | 必需资源 | 路径内最小快建 |
|---|---|---|
| `lesson` | LearningUnitRevision | 标题、目标、最小内容/来源选择，创建 working unit 并绑定 |
| `quiz` | QuizRevision | 标题、选择已批准题、基本通过规则，创建 working quiz 并绑定 |
| `audio_assessment` | AudioMaterialRevision + ScoringSchemeRevision | 任务壳、材料/来源、基础评分维度，创建 working revisions 并绑定 |
| `ai_coach` | CoachProfileRevision | 从模板复制检查点、来源范围和掌握策略，创建 working profile 并绑定 |
| `assignment` | ScenarioRevision + ScoringSchemeRevision | 从三段模板创建场景、绑定评分方案并自动关联 |

快建对象可以不立即满足发布条件，但必须是合法 working revision；编辑器显示“待补充/待审核/待发布”并定位下一步。ReleasePlan 只能冻结已批准、通过校验的 exact revisions。

## Requirements

### R1. 资源能力由后端声明

- `/resources` options 返回资源类型、状态、版本、引用摘要、capability 和 `quick_create_supported`。
- 前端不再硬编码只有 LearningUnit/Quiz 可创建；字段→资源类型→快建表单使用封闭 registry。
- 后端声明支持但缺少 UI renderer 时 fail closed 并显示可行动错误，不能静默隐藏按钮。

### R2. Drawer 交互

- 打开时保留当前 Path/Stage/Activity/字段上下文。
- 支持搜索、类型/状态筛选、版本预览、已发布/working 区分和引用影响。
- 默认优先选择已有可复用资源；没有合适对象时切换最小快建。
- 快建成功后刷新候选、自动选中并绑定返回的 exact revision ref。
- 关闭/失败/重试后恢复焦点到触发字段；错误不清空输入或当前 Activity。

### R3. 保存与版本语义

- Path working revision 可以引用同组织、合法 working resource，以便协同准备；正式 validate/publish 要求目标资源进入同一 ReleasePlan 并满足审核状态。
- Path 表单保存使用 expected version 和幂等键；重复提交不创建重复资源或丢失绑定。
- 资源更换显示 old/new revision、对发布和未来 Enrollment 的影响。
- 已发布 PathRevision 不原地修改；新发布不自动迁移活跃 Enrollment。

### R4. 完整编辑与上下文返回

- 超出快建范围的字段可“继续完整编辑”，打开对象页或同级 Inspector。
- 返回路径时恢复原 Path/Activity/field，自动刷新对象并保持未保存 Path 草稿。
- 若完整编辑未发布，路径明确显示仍被阻塞；不能用旧 revision 假装成功绑定。

### R5. 统一预览

- 右侧学员预览使用各 Activity Runtime 的正式 preview contract，不复制展示逻辑。
- Lesson 显示真实内容块；Quiz 使用真实 runner 的受控预览；Audio 显示材料/评分重点；Coach 显示结构化卡；Assignment 显示三段场景。
- Preview 不写正式 Attempt、Outcome、Evidence 或 Enrollment 进度。
- 缺失、stale、跨组织、归档、未批准和 Runtime 不兼容问题定位到具体 Activity/字段。

### R6. 发布校验

- ReleasePlan 依赖图覆盖 Source、Unit、Question、Quiz、AudioMaterial、ScoringScheme、CoachProfile、Scenario、Prompt/Model 和能力映射 exact revisions。
- 所有阻塞在 confirm 前可见；preview token/impact hash/If-Match/幂等和审计保持一致。
- 任一依赖失败时旧 ReleasePlan 继续有效，无半发布。

## Required States

覆盖资源为空、搜索无结果、快建中/失败/重复、无权限、资源 stale/archived、Path 并发冲突、完整编辑往返、预览失败、发布阻塞/过期、partial validation 和成功。重要结果不能只用 Toast。

## Acceptance Criteria

- [ ] 五类 Activity 的每个必需资源字段都支持选择或路径内最小快建。
- [ ] 快建成功后自动绑定；失败保留资源表单、Path 草稿、当前 Activity 和焦点位置。
- [ ] 前端严格消费后端 quick-create capability，不再硬编码资源类型支持矩阵。
- [ ] working 绑定与正式发布状态清晰，未批准资源不会被误标为可发布。
- [ ] 五类预览与 Runtime 契约一致且不产生正式业务记录。
- [ ] 发布依赖图包含全部资源与 AI 合同，失败保持旧发布可用。
- [ ] 键盘、Drawer 焦点、窄屏、长名称、重复提交和离开提醒通过验证。

## Minimal Verification

- 后端：资源 options/quick create registry、权限、幂等、working 绑定和 ReleasePlan dependency tests。
- 前端：Drawer 六类资源表单、自动绑定、失败恢复、完整编辑往返、预览 renderer tests。
- 浏览器：从空 Path 为五类活动各快建/绑定一次，验证发布阻塞和完成后的发布预览。
- 这是跨模块核心接口修改，允许运行 Foundation 相关契约/集成套件，但不运行整个仓库全量测试。

## Out of Scope

- 不在 Drawer 复制所有高级资源编辑功能。
- 不建设拖拽低代码工作流或任意 Activity 类型。
- 不执行 Legacy 迁移或 Enrollment 迁移。
- 不改变实时对练边界。

## Risk And Rollback

- 风险等级：P1（跨资源发布闭包和 Path 核心接口）。
- 可关闭新快建 renderer，保留选择已有资源；工作草稿不影响 active ReleasePlan。
- 发布错误通过 ReleasePlan 回滚，冻结 Enrollment 不动。

## Likely Areas

- `foundation_admin_workspace.py`、`foundation_admin_api.py`、Release composition；
- `activity-resource-drawer.tsx`、`v2-path-editor.tsx`、资源 ViewModels/API domain；
- 五类领域 Authoring ports 和 Runtime preview adapters。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，本任务不扩展资源完整 CRUD。


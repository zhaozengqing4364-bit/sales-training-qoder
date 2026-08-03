# Foundation 题库、导入与测验编排闭环

## Goal

在 Foundation 权威中补齐题目从手工创建、文件导入、AI 候选生成、审核、版本化到组卷、预览和发布的完整流程，让内容编辑不再依赖旧 `/admin/test-bank`，路径中的 Quiz 始终绑定可追溯的正式题目修订。

## Dependencies

- `07-19-foundation-authoring-contract-inventory`。
- 多媒体内容资产任务提供稳定 SourceRevision/Anchor 合同后，导入和出题可引用 PPT/文档来源。

## Page Contract

当内容编辑准备新人训练测验时，帮助其从已发布资料手工建题、导入或生成候选题，完成来源/答案/能力审核，编排测验并以学员视角预览，最终得到可发布、可追溯的 Quiz 修订。

页面模型：题库 List–Detail、候选审核 Process–Approval、测验 Editor–Preview；URL 保存筛选、页码和当前对象。

## Requirements

### R1. 正式题型

支持并以封闭 Schema 验证：

- 单选；
- 多选；
- 判断；
- 排序；
- 匹配；
- 简答。

客观题由确定性规则判分；简答题冻结参考答案、Rubric 和受治理 AI 评分合同。新增排序/匹配时同步 Activity Runtime、DTO、ViewModel 和回放快照，不能只在编辑器中出现。

排序/匹配是对当前四题型联合的 additive 扩展；既有 QuestionRevision、QuizRevision 和 Attempt 快照不迁移、不改变判分，只有新修订可使用新 discriminator。

### R2. 手工建题

- 内容编辑可创建逻辑 Question 和首个 working revision。
- 必填来源锚点、能力点、难度、题干、答案、解释；红线题明确标识及二次审核。
- 表单按题型显示结构化字段，不默认暴露 JSON。
- 保存草稿与通过校验分离；published revision 不可原地修改。

### R3. 批量导入

- 提供 CSV/XLSX 模板、下载说明和示例行。
- 上传后先进入持久 ImportBatch 和 Candidate，不直接创建正式题。
- 文件解析和批量校验在 DurableTask 中执行，慢文件 IO/AI 调用不占用数据库长事务；批次状态和逐项结果通过短事务追加回写。
- 预览列映射、类型/答案解析、来源匹配、重复、能力映射与预计结果。
- confirm 使用 preview token/impact hash/幂等键；逐行返回成功、重复、错误和跳过原因。
- 失败不丢原文件与已解析结果；允许修正后只重试失败项。

### R4. AI 候选审核

- 保留现有 GenerationBatch/QuestionCandidate 治理，支持按来源、单元、能力、题型和数量创建任务。
- 只使用已发布 Source/Unit 与服务端严格编译的 Prompt/模型合同。
- 审核页显示来源片段、重复差异、答案/Rubric 校验、能力映射和 AI 不确定性。
- 批量批准/拒绝先预览后确认并真实表达 partial success。
- AI/导入候选审核通过只形成 Question working revision，正式生效仍走 ReleasePlan。

### R5. 分类与检索

- 使用能力点作为首要治理维度，同时支持受控业务主题、标签、题型、难度、来源、状态和风险筛选。
- 标签/主题避免自由字符串失控：有去重、规范化、归档和引用保护。
- 列表服务端分页、筛选、排序；无权限与无结果分别表达。

### R6. 测验编排

- 创建 Quiz working revision，选择 exact QuestionRevision，配置题目分值/顺序、抽题策略、及格线、红线 Gate、时间、尝试次数、反馈和选项随机。
- 校验重复题、分值、来源 stale、未批准题、跨组织引用、简答评分合同和抽题可满足性。
- 学员预览使用正式 Quiz Runner 与受控 preview attempt，不写正式成绩或 Evidence。
- 发布后 Attempt 冻结题目、答案、评分合同、来源和随机结果。

### R7. 编辑与归档

- 正式题修改创建新修订并显示差异与受影响 Quiz/Path。
- 归档逻辑对象不删除历史修订；正在被 published Quiz 或 Attempt 引用时保留可回放。
- Source 更新导致 working 题 stale；新发布前重新验证，但不得篡改旧 Attempt。

## Required States

覆盖首次无题、筛选无结果、导入处理中/部分失败、AI 任务失败、重复冲突、审核冲突、无权限、stale、组卷不足、预览失败、保存/发布成功和归档只读。任何 recoverable failure 保留手工表单或批次上下文。

## Acceptance Criteria

- [ ] 管理员在 Foundation 管理端完成手工建题、CSV/XLSX 导入、AI 候选审核，无需旧题库页面。
- [ ] 六类题型从编辑、Schema、确定性/AI 判分、Attempt 快照到回放一致。
- [ ] 导入和批量审核有 preview/confirm、逐项结果、幂等与审计，不把部分失败显示为成功。
- [ ] 每道正式题有 exact source anchor、能力映射、答案合同和修订血缘。
- [ ] Quiz Editor 可搜索选题、配置规则、正式校验并使用真实 Runner 预览。
- [ ] 未审核、stale、跨组织或合同无效题不能进入新发布。
- [ ] 旧已发布 Quiz 与 Attempt 保持可读、可评分、可回放。
- [ ] 普通 UI 不展示 Prompt 正文、raw JSON、内部枚举或数据库主键。

## Minimal Verification

- 后端：六题型 Schema/评分、导入解析、重复检测、候选状态机、Quiz 校验与冻结快照单元测试。
- 集成：权限/组织隔离、ImportBatch partial success、ReleasePlan 阻塞与幂等。
- 前端：手工表单、候选审核、列表筛选、Quiz Editor/Preview 组件和 ViewModel 测试。
- 浏览器：手工一题、导入一批含错误行、批准候选、组卷预览的关键路径。
- 不运行全量 E2E；只跑 newcomer question/quiz 相关测试。

## Out of Scope

- 不迁移旧 `question_items` 或旧试卷；后续迁移任务负责。
- 不建设通用考试平台、监考、排行榜或作弊检测。
- 不让 AI 直接发布题目或决定正式通过规则。

## Risk And Rollback

- 风险等级：P1（评分合同和正式测验）。
- 新题型和导入入口可按 capability/feature flag 关闭；旧 published Quiz 不变。
- ReleasePlan 失败保持旧发布有效；新 working/candidate 数据可保留后续修复。

## Likely Areas

- `backend/src/learning/`、`foundation_question_generation.py`、`foundation_admin_api.py`；
- `web/src/components/admin/newcomer-training/question-review-workspace.tsx` 及新增题库/测验编辑组件；
- Quiz Runner、Foundation API types/ViewModels、ReleasePlan validation。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，不修复无关旧题库问题。

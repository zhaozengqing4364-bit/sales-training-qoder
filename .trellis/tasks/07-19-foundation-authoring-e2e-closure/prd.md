# 新人训练配置到学员执行端到端验收

## Goal

用真实对象和可复现证据验证“管理员配置 → 发布 → 分配 → 新人完成学习/做题/录音/Coach/异步场景 → 管理员复核”的闭环，重新建立可信验收矩阵；只修复本系列任务直接造成的验收缺陷，不把最终验收任务变成无边界清理。

## Dependencies

- 本父任务其余九个子任务全部完成并通过各自质量门。

## Acceptance Scenarios

### S1. 从零配置正常路径

1. Content Editor 上传一份真实结构 PPT/PPTX 和 Demo 材料/链接；
2. 查看解析/预览，精编为 LearningUnit；
3. 手工创建题目、导入一批题、审核一批 AI 候选；
4. 编排并预览 Quiz；
5. Training Admin 创建 PPT/Demo 录音材料和评分方案；
6. 创建 Coach Profile 和三段异步客户场景；
7. 在 Path Editor 中绑定/快建资源，完成学员预览、校验和 ReleasePlan 发布；
8. 创建 Cohort/Enrollment；
9. 新人完成 Lesson、Quiz、两个讲解活动、Coach 和异步场景；
10. 管理员看到冻结来源、评分、能力证据和复核入口。

### S2. 失败与恢复

- 非法或损坏 PPT 被拒绝，表单保留；
- PPT 解析/预览部分失败后从失败阶段重试；
- 题库导入含重复和错误行，逐项结果正确；
- AI 出题/Coach Provider 失败保留输入并给出结果位置；
- 路径有 working/stale/跨组织资源时发布被阻止；
- preview 过期、If-Match 冲突和重复提交不造成重复写；
- 修复后重新校验/发布成功，旧发布在失败期间持续可用。

### S3. 权限与组织隔离

验证 Content Editor、Training Admin、Training Manager、Platform/System Admin 和无权限用户：导航、只读/编辑/审核/发布能力正确；直接 URL、API 和对象 ID 越权均被后端拒绝且不泄露对象存在性。

### S4. 迁移与回滚

- 对当前 Legacy 数据执行可复现 dry-run；
- 在授权开发环境迁移 `石犀ppt讲解`、`demo讲解` 和 PPT；
- 新 Enrollment 能完成迁移活动；
- 重复迁移为 no-op；
- 回滚 ReleasePlan 后未来 Enrollment 使用稳定版本，历史结果仍可回放。

### S5. 状态、可访问性与响应式

关键管理/学员页面覆盖 loading、empty、no-result、error、permission、stale/conflict、partial success、background task、cancel/retry 和 persistent success。核心路径全键盘可完成，焦点可见；360px、桌面、200% zoom、长文本/大数值/长文件名无关键内容丢失。

### S6. 针对性容量与性能

使用固定数据集验证：

- 内容、题库、资源选择器使用服务端分页/筛选，不随总行数线性拉取；
- 1,000 内容资产、10,000 题目下首屏与搜索满足项目现有管理 API/UI SLO；
- 上传/解析/AI 请求快速返回持久任务位置，不阻塞 HTTP；
- Path 编辑与依赖预览无明显请求瀑布或 N+1；
- 只记录本闭环相关基线，不扩大为全站性能审计。

## Evidence Contract

每项验收必须记录：

- 场景、角色、输入 fixture 和预期；
- 执行命令、日期、退出码和关键结果；
- 真实浏览器截图/报告（不含敏感数据）；
- 数据库/API 只读断言和审计/trace 关联；
- 未验证项、原因、风险和 Owner；
- 对应子任务与代码/合同位置。

不得仅用 `[x]`、路由存在、Seed 成功或组件测试宣称端到端闭环。

## Acceptance Criteria

- [ ] S1～S6 全部有可复现证据，父 PRD 每条 Acceptance Criterion 均能映射到至少一条证据。
- [ ] 管理员无需访问 Legacy 页面、数据库、Seed 脚本或 raw JSON 即可完成真实配置。
- [ ] 学员端显示的 PPT/Demo/题目/评分重点/Coach/场景与发布修订一致。
- [ ] 失败、部分成功、权限、冲突、长任务和恢复均不丢输入、不伪造成功。
- [ ] ReleasePlan 失败/回滚、Enrollment 冻结、历史 Attempt/Outcome/Evidence 不变有数据证据。
- [ ] 普通 UI 无内部术语、测试数据、Prompt/Provider/raw payload 泄露。
- [ ] Realtime 客户对练未出现在导航、Path 联合、发布依赖或验收请求中。
- [ ] 新 acceptance matrix 只标记真实通过项，任何未通过项重新打开对应子任务或建立明确缺陷任务。

## Minimal Verification

- 优先复用各子任务已经通过的最小测试证据，不重复运行无关套件。
- 运行 Foundation authoring/release/learner 的针对性后端契约/集成/E2E 与前端 Vitest/Playwright。
- 因本任务验证公共发布闭包和跨模块接口，允许运行完整 Foundation 相关测试集合；不自动运行其他产品域全量测试、全库格式化或全站 E2E。
- 测试失败先归因；历史无关失败只记录，不在本任务修复。

## Defect Handling

- 属于某个前置子任务验收缺口：重新打开该子任务修复并复验。
- 属于本系列跨层接缝：只做最小接缝修复并记录影响。
- 与本系列无关：记录、告知、停止扩展。
- 所有标准通过后立即停止，不进行额外优化或清理。

## Out of Scope

- 实时客户语音对练和 Realtime Runtime。
- 全站视觉重设计、全仓架构/技术债清理。
- 生产数据迁移执行；除非用户另行明确授权目标环境。
- 与新人内容配置无关的全量性能、渗透或兼容性测试。

## Risk And Rollback

- 风险等级：P1（最终发布真值门）。
- 验收环境使用受控数据与脱敏证据；发布异常回滚到稳定 ReleasePlan。
- 不删除失败数据；通过幂等、归档和测试清理合同恢复环境。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，完成即停止。


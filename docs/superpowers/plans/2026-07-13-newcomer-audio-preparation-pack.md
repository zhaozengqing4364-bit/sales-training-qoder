# 新人训练录音任务「讲解前准备包」实施计划

> **执行约束：** 使用 `superpowers:executing-plans` 逐项执行；本任务按用户要求禁止派发子代理。每个行为变化均先写失败测试，再做最小实现。

**目标：** 将 PPT 讲解录音任务从“打开外部材料后自行理解”改造成当前页面内可完成的准备流程：明确展示同版材料、评分关注点与优秀讲解文字示例，确认后才能录音；管理员可配置示例，提交时冻结用户实际看到的材料和评分标准版本。

**架构：** 保持现有活动编排模型和数据库结构，只扩展 `audio_assessment` 配置与 runner descriptor。详情查询负责将版本化资源投影成学习者安全 ViewModel；提交链路携带并校验评分标准版本；前端拆出准备包组件，管理后台仅新增一个可选配置字段。旧路径修订保持可运行，并使用明确标注的系统默认表达结构兜底。

**技术栈：** FastAPI、SQLAlchemy、Pydantic v2、React、TypeScript、Vitest、Playwright。

**全局约束：**

- 不新增数据库迁移或第三方依赖。
- 不实现 PPT 转图片、内嵌 PDF 渲染或示例音频。
- API 仅做向后兼容的可选字段扩展；旧客户端未传评分标准版本时仍按当前激活版本处理。
- 普通用户界面不展示资源主键、原始枚举、内部版本 ID 或工程术语。
- 不修改或提交用户已有变更 `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`。

---

## Task 1：扩展音频活动配置与学习者详情投影

**涉及文件：**

- 修改：`backend/src/sales_trainer/orchestration/contracts.py`
- 修改：`backend/src/sales_trainer/orchestration/journey_service.py`
- 测试：`backend/tests/unit/test_newcomer_orchestration_contracts.py`
- 测试：`backend/tests/unit/test_newcomer_orchestration_journey_service.py`

**步骤：**

1. 在合同测试中添加失败用例：`AudioAssessmentConfig` 接受可选 `example_transcript` 且限制 8000 字；audio runner 详情返回材料版本标签、文件名、内容类型、评分标准修订信息、学习者安全的评分关注点和示例文字。
2. 运行定向测试，确认因字段缺失而失败：
   `uv run pytest backend/tests/unit/test_newcomer_orchestration_contracts.py backend/tests/unit/test_newcomer_orchestration_journey_service.py -q`
3. 为 Pydantic 合同添加兼容字段与 `AudioScoringFocus`；所有新增字段可空或有空列表默认值。
4. 在 journey service 中读取当前已发布材料版本和当前激活评分标准修订；将历史 `dimensions: string[]` 与新版维度对象统一映射为 `{label, description, weight}`，过滤无效项且不暴露内部 `key`。
5. 重跑定向测试，确认通过。

## Task 2：在提交链路精确冻结评分标准版本

**涉及文件：**

- 修改：`backend/src/sales_trainer/services/activity_audio_snapshot_service.py`
- 修改：`backend/src/sales_trainer/services/audio_submission_service.py`
- 修改：`backend/src/sales_trainer/orchestration/activities/audio_assessment.py`
- 修改：`backend/src/sales_trainer/orchestration/learner_api.py`
- 测试：`backend/tests/unit/test_newcomer_audio_assessment_activity.py`
- 按影响分析补充相关提交服务测试。

**步骤：**

1. 添加失败测试：传入页面展示的评分标准修订 ID 后冻结该已发布修订；逻辑资源不匹配、资源类型不匹配、未发布或不存在时返回明确的 409 业务错误；不传时保持旧行为。
2. 运行音频活动测试确认失败：
   `uv run pytest backend/tests/unit/test_newcomer_audio_assessment_activity.py -q`
3. 将可选 `confirmed_scoring_rubric_revision_id` 从 multipart API 逐层传到 snapshot service。
4. snapshot service 使用 `revision_by_id` 校验资源类型、logical id 和 published 状态后冻结；保留旧客户端的 active-revision fallback。
5. 重跑音频提交链路测试并通过。

## Task 3：让管理后台和种子内容可配置优秀示例

**涉及文件：**

- 修改：`web/src/lib/api/types/newcomer-training.ts`
- 修改：`web/src/components/admin/newcomer-training/activity-editors/audio-assessment-editor.tsx`
- 修改：`web/src/components/admin/newcomer-training/path-editor.tsx`
- 修改：`backend/scripts/seed_newcomer_training_path.py`
- 测试：`web/src/components/admin/newcomer-training/activity-editors/activity-editors.test.tsx`

**步骤：**

1. 添加失败测试：管理员能看到“优秀讲解示例（文字版）”文本域、帮助文案，编辑内容会回写配置；新建录音活动默认值为 `null`。
2. 运行定向 Vitest，确认失败。
3. 扩展 TypeScript 配置类型，新增可选/可空 `example_transcript`；编辑器使用现有表单 token 添加非必填 textarea，空白内容归一为 `null`。
4. 为 PPT、Demo、产品模块讲解种子活动添加不同的具体示例文字；不覆盖已存在的发布修订。
5. 重跑编辑器测试并通过。

## Task 4：实现当前页内的讲解前准备包

**涉及文件：**

- 新增：`web/src/components/newcomer-training/activity-runners/audio-preparation-pack.tsx`
- 修改：`web/src/components/newcomer-training/activity-runners/audio-assessment-runner.tsx`
- 修改：`web/src/lib/api/types/newcomer-training.ts`
- 修改：提交 FormData 的 API/domain 文件（通过 CodeGraph/调用者确认具体文件后修改）
- 新增或修改测试：`web/src/components/newcomer-training/activity-runners/audio-assessment-runner.test.tsx`
- 回归测试：`web/src/components/newcomer-training/activity-shell.test.tsx`

**步骤：**

1. 添加失败组件测试，覆盖：
   - 页面内直接显示材料版本/文件名；
   - “在新标签页查看 PPT 原文件”具有 `target=_blank` 和安全 `rel`；
   - 展示配置的评分关注点与优秀示例；
   - 旧修订展示明确标注的“系统默认参考表达结构”，不冒充管理员认可范例；
   - 未确认准备内容时“开始录音”禁用，确认后启用；
   - 上传时附带材料版本与评分标准修订 ID。
2. 运行定向 Vitest 确认失败。
3. 创建职责单一的 `AudioPreparationPack`，默认展开、信息顺序固定为“本次材料 → 评分会关注 → 优秀讲解示例 → 确认”。
4. 重构 runner 组合准备包与录音区；保持上传已有录音、试听、重录和提交行为；所有确认错误使用用户语言。
5. 将评分标准修订 ID 以可选 multipart 字段传给后端。
6. 重跑 runner、ActivityShell 与 API 相关测试并通过。

## Task 5：合同文档、质量门禁、浏览器验收与公开环境更新

**涉及文件：**

- 修改：`.trellis/spec/backend/newcomer-training-activity-orchestration.md`
- 修改：`docs/api-contract/sales-trainer.md`
- 新增或修改：`web/tests/e2e/newcomer-training-learner.spec.ts`
- 保留：`docs/superpowers/specs/2026-07-13-newcomer-audio-preparation-pack-design.md`

**步骤：**

1. 更新编排规范和 API 合同，记录新字段、版本冻结、兼容 fallback、学习者安全投影和管理员配置边界。
2. 添加 Playwright 验收：直接进入 PPT 录音活动，确认准备包可见、录音按钮由禁用变启用、原文件链接为新标签页；同时检查控制台错误和失败网络请求。
3. 执行后端定向测试、前端 Vitest、类型检查、lint、构建和相关 Playwright；记录准确命令与结果。
4. 运行 CodeGraph 影响分析，复核共享合同/提交链路调用点，确认无遗漏。
5. 用 `bash scripts/app-up.sh` 重建并启动公开生产运行时，检查 `http://186.241.123.157:3445/newcomer-training/activities/ppt-intro-audio`。
6. 使用仓库 Playwright 做最终浏览器截图与交互验证（当前环境未安装 Browser 插件，故使用该回退），确认当前页不会因查看材料而丢失任务上下文。
7. 按逻辑切分提交；只暂存本计划涉及文件，绝不包含用户已有脏文件。

## 完成标准

- 学员进入录音活动后无需离开页面即可知道用哪份材料、按什么标准、优秀表达长什么样以及下一步动作。
- 原 PPT 是明确的辅助新标签页链接，不再承担解释任务的主流程职责。
- 管理员不改代码即可为每个录音活动维护示例文字；全新执行能力之外无需开发代码。
- 提交记录冻结材料版本与评分标准版本，后续管理员发布新版本不改变历史评测依据。
- 旧路径修订和旧客户端保持兼容；兜底文字不冒充正式评分范例。
- 定向测试、全量相关测试、类型检查、lint、构建和浏览器关键路径均有可复核证据。

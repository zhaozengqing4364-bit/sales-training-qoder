# 新人训练路径活动编排直接重构 PRD

## 目标

一次性删除未发布的固定新人训练路径原型，交付唯一的 `TrainingPath → Phase → Module → Activity` 活动编排系统。管理员使用现有六类活动能力自由新增产品、课程和训练组合，不再修改源码。

## 设计与计划权威

- 设计：`docs/superpowers/specs/2026-07-12-newcomer-training-activity-orchestration-design.md`
- 计划：`docs/superpowers/plans/2026-07-12-newcomer-training-activity-orchestration.md`

两份文档均已由用户批准。实施必须完成计划全部 15 个任务。

## 核心要求

1. 路径结构固定为 Path、Phase、Module、Activity 四层。
2. 活动类型固定为 `lesson`、`quiz`、`audio_assessment`、`realtime_roleplay`、`ai_coach`、`assignment`。
3. PPT、Demo、商务礼仪、产品和技术课程都是配置数据，不得成为运行时代码分支或固定业务键。
4. 草稿允许不完整，发布必须严格验证；发布版本不可变。
5. 学员首次进入固定 revision，历史 attempt、配置和结果快照不得漂移。
6. 管理端使用左侧大纲、中间单对象编辑、右侧预览/校验；支持就地快速新建并自动绑定资源。
7. 学员首页只突出一个下一步；当前阶段展开、历史和未来阶段渐进披露。
8. 所有写入具备权限、对象范围、幂等、审计、并发控制和明确错误。
9. 不保存任意代码、组件、URL、路由、脚本或网络请求到配置。
10. 直接替换并删除旧固定路径、学习专题、兼容 API/页面/测试，不做双轨和重定向。

## 数据重置边界

允许重置新人训练原型路径 revision、旧学习专题 revision、seed enrollment/attempt 和明确属于新人训练的 seed 记录。共享 LearningContent、ExamPaper、材料、评分标准、用户、PracticeTemplate 和运行时配置若被其他域引用，不级联删除。

执行顺序必须是 dry-run、核对计数、显式 confirm apply、重新 seed、verify。

## 完成标准

- 计划 15 个任务全部完成并勾选。
- 产品 A/B/C 均可通过同一套 lesson + quiz + audio activity 配置创建，无源码分支。
- 六类 Handler/Renderer 契约测试全部通过。
- Alembic、Ruff、Mypy、后端 unit/integration/contract、前端 type/lint/Vitest/build、新人训练 Playwright 全部通过。
- legacy authority 搜索无运行时代码残留。
- 使用 `trellis-check`、`trellis-update-spec` 和 `trellis-finish-work` 完成治理闭环。

## 执行约束

- 单代理内联执行，不创建或派发子代理。
- 不询问普通实现决策；使用设计权威和保守假设继续。
- 每个任务严格 TDD、聚焦回归、独立 commit。
- 不触碰无关用户修改 `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`。
- 不 push、不创建 PR、不改写历史。

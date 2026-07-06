# 新人训练 V0.9 全量闭环代码落地

## Goal

把 `docs/product/newcomer-training-v0.9-usable-loop.md` 中的“企业新人训练路径平台 V0.9 全量可用闭环”落到当前代码：培训负责人能通过达标验收工作台和单人训练达标档案，判断新人练过什么、提交了什么证据、AI/规则按什么标准评、哪些能力达标或未达标、是否复核、是否重练，以及当前能否进入下一阶段。

## What I already know

- 用户确认北极星结果：每个新人都有一份可信的训练达标档案。
- 当前训练路径是：上传演讲 PPT / 学习文档 → 答题 / AI 请教 → 金字塔演讲 → 真实语音对练。
- PPT、录音上传判断、已上传材料、商务礼仪等训练关卡应由后台配置和发布治理驱动，不能在页面写死具体内容。
- 指标类型和兼容 key 可以代码内稳定定义，但评分标准、Prompt、通过线、材料、题目、启停状态应来自配置或快照。
- AI 在商务礼仪学习后的角色是补练教练：解释弱项、批改、推荐回看章节、生成训练动作，不能替代培训负责人最终确认达标。
- V0.9 不以真实语音对练可用为完成标准；真实语音对练应按训练准入和 provider readiness 双条件锁定。
- 代码调查见 `research/codebase-context.md`。

## Requirements

### 后端聚合与契约

- 新增训练达标档案聚合服务，复用 `TrainingJourneyService`、`TrainingRecordService` 和 `OperationLogService`。
- 新增管理员 API：
  - 获取达标验收工作台。
  - 获取单个新人训练达标档案。
  - 提交复核动作：确认达标、要求重练、标记需人工跟进。
- 档案状态必须集中定义，至少覆盖：
  - `not_started`
  - `in_training`
  - `ai_evaluating`
  - `needs_remediation`
  - `pending_review`
  - `approved`
  - `rejected`
  - `blocked_by_config`
- 工作台至少按以下分组输出：
  - 待复核
  - 未达标
  - 需重练
  - 已达标
  - 配置异常
- 档案证据链至少能追溯：
  - 任务 / 模块
  - 证据类型
  - 提交时间
  - 分数和通过状态
  - 材料快照摘要
  - 评分标准快照摘要
  - 关联训练记录入口
- 能力项采用 V0.9 内置新人销售能力模型，不允许 AI 临时发明能力项：
  - 表达清晰度
  - 结构化讲解
  - 产品理解
  - 客户视角
  - 需求识别
  - 异议回应
  - 商务礼仪与职业表达
- 复核动作必须：
  - 后端校验权限和对象范围。
  - 写入审计记录。
  - 保留关联证据和原因。
  - 不删除或覆盖原始 AI/规则评分。
- 要求重练在 V0.9 先形成审计化、可展示的重练任务记录；若不新增独立表，必须清楚暴露为 audit-log-backed review state，后续可迁移为一等重练表。
- 配置异常或 active revision 缺失必须进入 `blocked_by_config`，不能计为学员未完成。
- 更新 `docs/api-contract/sales-trainer.md`。

### 前端体验

- 新增管理员达标验收工作台页面。
- 新增单人训练达标档案页。
- 工作台新人卡片只回答：
  - 当前能不能判断达标。
  - 卡在哪个能力项或任务。
  - 培训负责人下一步要做什么。
- 档案页必须回答：
  - 他练过什么。
  - 提交了什么证据。
  - AI/规则按什么标准评。
  - 哪些能力达标，哪些没达标。
  - 是否有人复核。
  - 没达标后有没有重练。
  - 当前能否进入下一阶段。
- 页面必须用用户语言，不直接展示 raw JSON、内部 trace、Prompt 原文、模型调试日志。
- 页面覆盖 loading、empty、error、success、permission/disabled、partial/config-error 状态。
- 新增入口应接入现有 sales trainer admin module navigation。

### AI 与准入治理

- AI 证据只作为初评和补练建议，不自动确认最终达标。
- 真实语音对练准入必须展示训练准入和 provider readiness 的锁定原因；V0.9 不把 StepFun 真实连通性修复作为本任务 blocker。
- AI 失败、评分失败或配置缺失时，档案进入待人工复核或配置异常，不显示为达标。

## Acceptance Criteria

- [x] 培训负责人可以打开达标验收工作台，看到待复核、未达标、需重练、已达标、配置异常分组。
- [x] 培训负责人可以打开单人档案，看到训练进度、能力项、证据链、复核记录和下一步动作。
- [x] 培训负责人可以提交确认达标、要求重练、标记需人工跟进三个动作。
- [x] 复核动作写入审计，并能反映到档案状态和工作台分组。
- [x] 配置异常进入配置异常分组，不显示为学员未完成。
- [x] 前端不写死具体材料、题目、评分 Prompt、通过线；只写稳定任务类型、能力项和兜底文案。
- [x] 新增 API 契约文档已更新。
- [x] 后端权限、状态汇总、复核动作至少有针对性测试或明确验证证据。
- [x] 前端类型检查通过，关键页面能在 loading/empty/error/success 下工作。

## Definition of Done

- 后端新增服务职责清晰，route 保持 thin。
- API DTO 与前端 TypeScript 类型一致。
- 权限以后端为准，前端只做体验优化。
- 复核和重练动作有审计证据。
- 构建 / 类型检查 / 相关测试通过；无法执行的验证必须说明原因。
- 未完成的长期项记录到后续建议，不伪装成已完成。

## Out of Scope

- 不做通用流程编排器。
- 不做完全动态任务类型系统。
- 不做复杂审批流、多人会签、手动改分、删除成绩。
- 不做历史成绩自动重评。
- 不把真实 StepFun 语音对练修复作为本任务 blocker。
- 不改造 supervisor 域为 sales_trainer 的重练事实表，除非实现中确认可以安全复用。

## Technical Notes

- 方案来源：`docs/product/newcomer-training-v0.9-usable-loop.md`。
- 代码调查：`research/codebase-context.md`。
- 相关后端约束：
  - `backend/src/sales_trainer/AGENTS.md`
  - `.trellis/spec/backend/business-rule-configs.md`
  - `.trellis/spec/backend/quality-guidelines.md`
- 相关前端约束：
  - `web/src/app/admin/sales-trainer/AGENTS.md`
  - `.trellis/spec/frontend/admin-console-patterns.md`
  - `.trellis/spec/frontend/quality-guidelines.md`
  - `.trellis/spec/frontend/type-safety.md`

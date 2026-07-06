# 新人训练 V0.9 可用闭环梳理

## Goal

基于当前项目代码、契约文档和与用户的 `grill-with-docs` 讨论，沉淀一份正式产品/技术梳理文档，回答“当前系统离先可用闭环还差什么”，并把 V0.9 收敛为企业新人训练路径平台的可试点版本。

## What I already know

* 用户已确认项目对外定位为“企业新人训练路径平台”。
* 用户已确认北极星结果是“每个新人都有一份可信的训练达标档案”。
* 用户已确认第一版优先服务培训负责人，而不是先做新人自由训练平台。
* 用户已确认 V0.9 先做标准材料/PPT 学习、文档学习、答题或 AI 补练教练、金字塔演讲训练、达标档案、培训负责人复核和重练；真实语音对练按准入后续开放，不阻塞 V0.9。
* 用户已确认后台配置应驱动 PPT/录音任务、材料绑定、评分 Prompt、商务礼仪文章、小单元、题目、AI 补练教练、金字塔演讲和真实语音对练准入，不能把具体训练内容写死。
* 用户已确认迁移策略是“固定任务类型，动态任务实例；先不做完全动态任务类型系统”。
* `CONTEXT.md` 已更新相关领域术语：训练达标档案、能力项、通用新人销售能力模型、训练任务模板、金字塔演讲训练、AI 补练教练。
* CodeGraph 显示当前系统已有 active path revision、材料/评分快照、商务礼仪小单元、AI Coach 训练局、AI 教练进度、训练记录和权限治理基础。

## Assumptions

* 本任务只产出文档，不改业务代码、不改 API 契约、不引入 migration。
* 文档应标记为 V0.9 产品/技术梳理，不宣称功能已全部实现。
* 文档应区分当前已有能力、缺口、优先级和不做事项。

## Requirements

* 新增 `docs/product/newcomer-training-v0.9-usable-loop.md`。
* 文档必须使用中文。
* 文档必须覆盖：
  * 当前可用性判断；
  * V0.9 闭环定义；
  * 后台配置原则；
  * 固定任务类型与动态任务实例；
  * 训练达标档案结构；
  * 培训负责人达标验收工作台；
  * 当前已有能力 / 缺口 / 优先级；
  * 不做事项；
  * 后续实施顺序。
* 文档不得把真实语音对练写成 V0.9 blocker。
* 文档不得把 AI 补练教练写成最终达标裁判。
* 文档不得要求做通用流程编排器。

## Acceptance Criteria

* [x] `docs/product/newcomer-training-v0.9-usable-loop.md` 存在。
* [x] 文档明确说明当前系统“接近可试点，但未达到商业 V1”。
* [x] 文档明确 V0.9 的产品出口是训练达标档案与达标验收工作台。
* [x] 文档明确后台配置边界和固定任务类型。
* [x] 文档包含当前已有能力 / 缺口 / 优先级表。
* [x] 文档与 `CONTEXT.md` 术语一致。

## Definition of Done

* 文档落盘。
* `CONTEXT.md` 已记录本次讨论确定的领域术语。
* 不修改业务代码。
* 执行基础文本检查或说明未执行原因。

## Out of Scope

* 本轮不实现训练达标档案页面。
* 本轮不实现达标验收工作台。
* 本轮不调整后台配置模型。
* 本轮不修复 StepFun 真实音频链路。
* 本轮不提交 git commit。

## Technical Notes

* 已读 `CONTEXT.md`。
* 已读 `docs/AGENTS.md`。
* 已读 `docs/api-contract/sales-trainer.md`。
* 已读 `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/final-verification-report.md`。
* 已读 `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/audit-closure-matrix.md`。
* 已通过 CodeGraph 查看 `path_config_models.py`、`effective_audio_training_config.py`、`audio_submission_service.py`、商务礼仪学习页、AI Coach 页与 AI Coach 后端服务。

# 完善新人训练 V0.9 全量闭环方案

## Goal

把 `docs/product/newcomer-training-v0.9-usable-loop.md` 从“可用闭环梳理草案”推进为更完整的 V0.9 全量闭环方案：既覆盖管理员、学员、培训负责人、AI、配置、证据、复核、重练、准入、异常和验收，又不把尚未实现的能力写成已完成事实，不引入新的范围膨胀或架构风险。

## What I already know

* 用户目标是“全量闭环，不引入问题，完美符合我们的设想”，目标文件是 `docs/product/newcomer-training-v0.9-usable-loop.md`。
* 既有文档已经明确：企业新人训练路径平台、训练达标档案、后台配置、固定任务类型、动态任务实例、AI 补练教练、金字塔演讲、真实语音对练不阻塞 V0.9。
* `CONTEXT.md` 已沉淀相关领域语言。
* CodeGraph 显示当前已有 path config、asset revision、business rule snapshot、audio scoring prompt、AI Coach 配置、supervisor review、retraining task、readiness status 等底座，但不少新闭环仍是“有基础能力，缺产品化聚合/工作流”。
* 当前改动只应更新文档和任务记录，不改业务代码、不改 API、不做 migration。

## Assumptions

* “全量闭环”在本轮指产品/技术方案闭环，不等于一次性实现所有页面和接口。
* 文档必须保守区分“已有能力”“应补能力”“V0.9 不做”，不能为了显得完整而伪造实现状态。
* 本轮不提交 git commit。

## Requirements

* 补强 V0.9 文档，使其覆盖端到端闭环：
  * 配置发布闭环；
  * 学员训练闭环；
  * AI 初评和补练闭环；
  * 培训负责人复核闭环；
  * 重练闭环；
  * 真实语音对练准入闭环；
  * 异常和配置治理闭环；
  * 数据证据和审计闭环。
* 明确各角色的主任务和页面出口，避免模块堆叠。
* 明确核心状态对象：训练任务状态、证据状态、能力项状态、档案状态、复核动作、准入状态。
* 补充“不引入问题”的护栏：不写死训练内容、不做通用流程编排器、不绕过权限/审计、不让 AI 直接裁决、不把 realtime provider 问题变成 V0.9 blocker。
* 补充 V0.9 实施顺序和验收清单，使后续代码实现可以按切片推进。
* 保持与 `CONTEXT.md` 术语一致。

## Acceptance Criteria

* [x] `docs/product/newcomer-training-v0.9-usable-loop.md` 明确“全量闭环”的角色、步骤、状态和证据。
* [x] 文档不宣称尚未实现的功能已经完成。
* [x] 文档明确“不引入问题”的工程护栏和非目标。
* [x] 文档包含可执行的实施切片和受控试点验收清单。
* [x] 文档与 `CONTEXT.md` 术语一致，没有残留旧叫法。
* [x] `git diff --check` 通过。

## Definition of Done

* 目标文档落盘并完成自检。
* 基础文本检查通过。
* 不修改业务代码。
* 最终说明已改内容、验证结果和未运行代码测试的原因。

## Out of Scope

* 不实现训练达标档案页面。
* 不实现达标验收工作台。
* 不修改后台配置模型。
* 不修复 StepFun 真实音频链路。
* 不新增 ADR，除非文档中引入长期架构决策。
* 不提交 git commit。

## Technical Notes

* 已读 `docs/product/newcomer-training-v0.9-usable-loop.md`。
* 已读 `CONTEXT.md`。
* 已通过 CodeGraph 查看 supervisor review / retraining task / readiness status / path config / asset revision / audio scoring prompt 等相关现状。
* 已执行文档覆盖检查，覆盖全量闭环、角色、状态、证据、护栏、试点验收、失败态和发布回滚章节。
* 已执行旧叫法检查、尾随空白检查和 `git diff --check`。

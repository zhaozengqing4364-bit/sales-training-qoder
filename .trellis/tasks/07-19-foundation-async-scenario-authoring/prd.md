# Foundation 异步客户场景配置中心

## Goal

把当前标准包中固定的异步客户场景资源变成可由训练管理员维护的 `scenario` 修订，让新人完成需求发现、异议处理和推进承诺三段异步录音任务，并保留真实客户实时语音对练作为明确的后续产品能力。

## Dependencies

- `07-19-foundation-authoring-contract-inventory`。
- `07-19-foundation-audio-scoring-authoring` 提供场景可引用的录音材料与评分方案合同。
- 多媒体内容资产提供可选背景材料/案例 exact refs。

## Page Contract

当训练管理员设计一个客户沟通练习时，帮助其定义客户背景、学员已知信息、三段任务、期望证据、允许承诺和风险边界，绑定评分方案并以学员/审核员视角预览，最终得到可被 `assignment` Activity 使用的已发布场景修订。

## Requirements

### R1. 场景模型

`audio_assessment` 继续拥有 `scenario` 修订。Snapshot 至少结构化表达：

- 场景标题、训练目标、目标客户角色/行业/关系阶段；
- 学员可见背景、不可见评估信息和信息披露边界；
- exact Source/Anchor/案例材料引用；
- 三段封闭 segment：`discovery`、`objection`、`commitment`；
- 每段任务说明、预计时长、必需信息、成功证据和禁止行为；
- 适用能力点、评分方案 exact ref、人工复核条件；
- 允许承诺、敏感信息、事实红线和合规边界；
- 版本、状态、创建/审核/发布审计。

首发保持三段固定结构，不发展为任意拖拽流程；未来新增 segment 必须先扩展封闭合同和 Runtime。

### R2. Authoring Surface

- 场景列表支持状态、客户类型、能力、来源和引用筛选。
- 创建可从标准模板复制，但新对象有独立 working revision。
- Editor–Preview 分别展示学员看到的背景/任务和审核员看到的证据/评分/风险。
- 保存草稿允许缺项；validate 精确指出哪个 segment/字段阻塞发布。
- 归档保留已发布 Path、Attempt、Submission 和 Evidence 回放。

### R3. 与 Assignment Runtime 的边界

- `assignment` Activity 只绑定 exact `scenario_revision_id`、`scoring_scheme_revision_id` 和录音限制。
- 三段录音继续使用现有 Durable Audio Pipeline；不复制另一套上传、ASR 或评分服务。
- 每段产生独立、可追溯 Outcome/Evidence；缺段、低置信度或待人工不得把整体显示为完整通过。
- 场景发布不自动改变已开始 Assignment；新 Attempt 冻结新修订。

### R4. 非实时边界

- 不出现麦克风常开、WebSocket、实时打断、AI 客户连续对话或实时延迟承诺。
- UI 用“异步客户场景”或业务任务名，不称为“实时对练”。
- 可保留未来 `customer_roleplay_ready` 的稳定扩展点，但不得为此接入 Realtime Runtime、Provider 或导航。

### R5. 权限与安全

- capability、组织/对象范围、`If-Match`、幂等和审计完整。
- 管理员不能引用跨组织材料、评分方案或客户敏感数据。
- 学员投影只包含明确可见信息；隐藏评分提示、内部风险规则和客户私密字段。
- AI 仅辅助评分/反馈，规则与人工复核决定正式结果。

## Required States

覆盖无场景、模板复制、缺 segment、缺来源/评分、并发冲突、无权限、预览失败、部分录音完成、处理中、低置信度、待人工、发布阻塞、归档和回滚。

## Acceptance Criteria

- [ ] 管理员可创建、编辑、校验、比较、归档和发布异步客户场景，不依赖 Seed。
- [ ] 三段任务均有学员说明、必需证据、风险边界和能力映射。
- [ ] 学员预览与正式 Assignment Runner 使用同一安全投影，隐藏评估信息不会泄露。
- [ ] 三段录音复用现有 Audio Pipeline，状态和部分成功正确，不把缺段显示为完成。
- [ ] 新发布不改变既有 Attempt；归档不破坏历史回放。
- [ ] 页面、API、Path 联合和标准包中均无 Realtime 活动或依赖回流。
- [ ] 无权限、跨组织和非法来源/评分引用由后端拒绝并审计。

## Minimal Verification

- 后端：Scenario Schema、三段验证、权限/组织隔离、版本/归档、Assignment 冻结与部分结果测试。
- 前端：场景编辑器、双视角预览、错误定位、部分完成和无权限测试。
- 集成：发布场景并完成/缺失三段两条关键路径。
- 只运行 assignment/audio/newcomer 相关测试；不启动或测试 Realtime 服务。

## Out of Scope

- 实时客户语音对练、WebSocket、打断和低延迟反馈。
- 通用场景编排器、任意 segment 类型或自动 CRM 数据导入。
- AI 自动作出最终达标结论。
- Legacy situation pack 迁移。

## Risk And Rollback

- 风险等级：P1（客户数据边界与正式证据）。
- 新场景入口可关闭，既有 Seed 场景继续可用；错误发布通过 ReleasePlan 回滚。
- 已产生的三段录音、Outcome 和 Evidence 永不因场景回滚被删除。

## Likely Areas

- `backend/src/audio_assessment/` 场景 Snapshot/Authoring、Assignment adapter；
- `backend/src/newcomer_training/` Activity validation/preview；
- Foundation 管理端场景工作区与学员 assignment runner。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，不得顺带恢复 Realtime。


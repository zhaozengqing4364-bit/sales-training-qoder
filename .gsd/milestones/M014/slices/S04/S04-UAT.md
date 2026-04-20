# S04: 训练前预期管理与中断恢复 UX 收口 — UAT

**Milestone:** M014
**Written:** 2026-04-11T16:44:47.322Z

# S04 UAT — 训练前预期管理与中断恢复 UX 收口

## Preconditions
- 使用现有 learner 账号登录系统。
- 已存在一个可进入的 sales practice session；另外准备一个 presentation session 用于 spot check preflight 文案。
- 若要验证失败恢复文案，可在本地测试环境通过 mock / devtools / API stub 让 pause、resume、end 其中一个动作返回失败。

## Case 1 — Sales 开练前能看懂本次练什么
1. 打开一个尚未开始对话、消息列表为空的 sales practice 页面。
2. 观察主页面顶部内容。
3. **Expected:** 页面出现“开练前预告”卡片，并同时展示三块信息：`训练目标`、`评价标准`、`角色简介`。
4. **Expected:** 文案不是只有泛泛场景标题；应能看出本次围绕销售目标、价值/证据/推进来练，并带有当前 agent/persona 的 learner-readable 角色说明。

## Case 2 — 一旦已经开始对话，preflight 不再占住主页面
1. 在同一 sales session 中点击麦克风开始讲话，或进入一个已有历史消息的 session。
2. 观察主页面主内容区。
3. **Expected:** `开练前预告` 卡片消失，不再和真实对话消息重复占位。
4. **Expected:** 如果这是定向再练 session，`本次练习聚焦上次复盘问题` 卡片仍可继续显示主问题/下一轮目标，不受 preflight 隐藏逻辑影响。

## Case 3 — Presentation session 也有最小 preflight 提示
1. 打开一个尚未开始对话的 presentation practice 页面。
2. 观察开练前区域。
3. **Expected:** 同样出现 `训练目标`、`评价标准`、`角色简介` 三块信息。
4. **Expected:** 文案应偏向演讲/PPT 表达、重点页覆盖、现场问答等 presentation 语义，而不是 sales 价值/异议语义。

## Case 4 — 暂停失败时用户知道下一步怎么做
1. 在 `in_progress` 的 practice session 中触发“暂停”操作，并让后端/mock 返回失败。
2. 观察页面错误提示区。
3. **Expected:** 页面出现红色错误 banner，主文案为 learner-facing 暂停失败提示，而不是技术栈报错。
4. **Expected:** banner 同时显示下一步指导，并出现 `重试暂停` 按钮。
5. **Expected:** 当前页面不会跳走到其他 route，用户仍停留在原 practice session 内可恢复状态。

## Case 5 — 继续失败时页面给出恢复动作
1. 先让 session 进入 paused 状态。
2. 点击“继续”，并让后端/mock 返回失败。
3. **Expected:** 页面出现红色错误 banner，提示继续失败并建议先确认连接后再试。
4. **Expected:** banner 中出现 `重试继续` 按钮；若连接也失败，应同时看到 `重新连接`。

## Case 6 — 结束失败时页面给出最清楚的恢复路径
1. 在一个可结束的 practice session 中点击“结束练习”，并让 end API 返回失败（可带后端 detail）。
2. 观察错误提示区。
3. **Expected:** 页面出现红色错误 banner，主文案说明结束失败；若后端返回了可读 detail，应被拼进 learner-facing 文案而不是静默丢失。
4. **Expected:** banner 出现 `重试结束` 按钮。
5. **Expected:** 当连接状态为 failed 时，同一区域还会出现 `重新连接`，形成“先恢复连接，再重试结束”的路径。

## Case 7 — `test-mic` 保持开发工具边界，不误导 learner
1. 正常从 learner 的 dashboard / history / practice 主路径进入系统，不手动输入 `/test-mic` URL。
2. 浏览 practice shell、帮助入口和常规 learner 导航。
3. **Expected:** learner 主路径内看不到 `开发工具 · 不属于学员训练主流程` 或 `麦克风调试工具` 文案，也没有把 `test-mic` 当成常规练习入口暴露出来。
4. 手动打开 `/test-mic` 页面。
5. **Expected:** 页面明确标注该页仅供开发/支持排查设备与后端连通性使用，正常学员应从 practice 主页面进入。

## Edge Cases
- 若 session 已是 `completed` 或 `scoring` 终态，不应再出现 preflight 卡片，也不应暴露 pause/resume/end 重试动作。
- 如果 websocket 连接失败但 lifecycle API 尚未触发失败，仍应优先看到 `重新连接` 恢复路径，而不是静默卡死。
- 对已有历史消息的 session，绝不能重新出现开练前预告，把真实对话内容挤下去。

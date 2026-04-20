# S03: 主问题驱动的再练入口 — UAT

**Milestone:** M004
**Written:** 2026-03-26T02:11:03.438Z

# S03: 主问题驱动的再练入口 — UAT

**Milestone:** M004
**Written:** 2026-03-26T02:05:59Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: 这条 slice 的核心交付是现有 report / replay / create-session / practice-page metadata chain 上的 contract 打通与首屏 carry-forward focus 展示。focused backend + web suites 已覆盖 retry-entry contract、create-session persistence、runtime descriptor projection、practice-page callout 与现有 websocket 基线，因此无需额外发明新的 live runtime surface 才能验证本 slice。

## Preconditions

- 存在一个已完成的 sales session，并且它的 canonical `/practice/{sessionId}/report` 能返回 `retry_entry.focus_intent`。
- 该 session 的 `retry_entry` 至少包含 `scenario_type="sales"`、`agent_id`、`persona_id`，且 `focus_intent` 内包含可读的 `main_issue`、`next_goal`。
- Web app 能访问当前 `/practice/{sessionId}/report`、`/practice/{sessionId}/replay` 与 `/practice/{newSessionId}` 页面。
- 后端 create-session surface 指向现有 `POST /api/v1/practice/sessions`，不是任何 retry-only 新路由。

## Smoke Test

1. 打开一个带 `retry_entry.focus_intent` 的 `/practice/{sessionId}/report`。
2. 点击“按目标再练一轮”。
3. **Expected:** 浏览器进入新的 `/practice/{newSessionId}?scenario_type=sales&agent_id=...&persona_id=...`，页面首屏出现“定向再练 / 本次练习聚焦上次复盘问题”卡片，并展示上一轮的主问题与下一轮目标。

## Test Cases

### 1. report 页可以用 canonical retry entry 发起定向再练

1. 打开一个 completed sales session 的 `/practice/{sessionId}/report`。
2. 在“下一轮销售目标”卡片附近确认存在“按目标再练一轮”按钮。
3. 打开浏览器网络面板，点击该按钮。
4. 观察 `POST /api/v1/practice/sessions` 请求体。
5. **Expected:** 请求仍然走现有 create-session API；body 中包含 `scenario_type: "sales"`、原 session 的 `agent_id` / `persona_id`，以及 `focus_intent.version / source_session_id / main_issue / next_goal`，而不是调用新的 retry 专用 endpoint。
6. **Expected:** 跳转后的 URL 仍使用现有 `/practice/{newSessionId}` 路由，query string 只承载可见的 `scenario_type` / `agent_id` / `persona_id`，结构化 `focus_intent` 不应被塞进 URL。

### 2. replay 页必须复用 report 的 canonical retry entry，而不是自己拼装

1. 打开同一场会话的 `/practice/{sessionId}/replay`。
2. 在“按当前问题线继续再练”区块确认存在“按目标再练一轮”按钮。
3. 打开网络面板，点击该按钮。
4. 对比 report 页与 replay 页发出的 create-session 请求。
5. **Expected:** replay 页同样调用 `POST /api/v1/practice/sessions`；`scenario_type`、`agent_id`、`persona_id` 与 `focus_intent` 结构应与 report 页来源一致。
6. **Expected:** replay 页的 retry section 来自 canonical report `retry_entry`；如果 report retry contract 缺失，页面只应显示“当前回放缺少再练配置，请先返回报告页确认训练目标”之类提示，而不是本地猜一个默认 payload。

### 3. 新 practice session 首屏必须明确展示 carried-forward focus

1. 从 report 或 replay 成功创建一个新的 targeted retry session 后，进入 `/practice/{newSessionId}`。
2. 在页面顶部查找“定向再练 / 本次练习聚焦上次复盘问题” callout。
3. 核对 callout 中的四类信息：
   - 主问题标签与 `issue_text`
   - 修正动作（若有 `recovery_rule`）
   - 下一轮目标标签与 `goal_text`
   - 判定条件（若有 `rule`）
4. **Expected:** 这些内容与源 session report 的 `retry_entry.focus_intent` 一致，而不是页面重新生成的新文案。
5. **Expected:** 页面仍是现有 practice layout，没有出现新的 onboarding modal、第二个 retry wizard 或独立“学习中心”页面。

### 4. session metadata 应通过 runtime descriptor carry focus，而不是要求页面自己读 raw snapshot

1. 对新创建的 targeted retry session 调用现有 `GET /api/v1/practice/sessions/{newSessionId}`。
2. 检查返回 payload 中的 `runtime_descriptor`。
3. **Expected:** `runtime_descriptor.focus_intent` 存在，且字段内容与 create-session 写入的 `voice_policy_snapshot.focus_intent` 保持一致。
4. **Expected:** 对非 sales session 或没有 retry focus 的 session，`runtime_descriptor.focus_intent` 应为空，不应无差别给所有 session 注入 sales retry metadata。

## Edge Cases

### 缺少必要配置时，report / replay 应明确阻止 retry

1. 准备一个 `retry_entry.scenario_type="sales"` 但缺少 `agent_id` 或 `persona_id` 的报告数据。
2. 打开 report 或 replay 页面。
3. 尝试点击“按目标再练一轮”。
4. **Expected:** 页面显示“当前销售会话缺少角色配置，请在训练页重新选择智能体与角色。”之类 inline hint；按钮应被禁用或点击后不创建新 session；页面不能静默失败，也不能偷偷用默认 agent/persona 建新会话。

### 传入非法 focus_intent 时，create-session 应拒绝请求

1. 直接调用 `POST /api/v1/practice/sessions`，传入 `scenario_type="sales"`，并构造一个没有可读 `main_issue` / `next_goal` 的空 `focus_intent`。
2. **Expected:** API 返回 `400 [INVALID_RETRY_FOCUS_INTENT]`；新的 session 不应被创建。

### presentation retry 不应误显示 sales carry-forward callout

1. 从 presentation report 发起现有 retry flow，进入新的 presentation `/practice/{sessionId}`。
2. **Expected:** 页面仍保持当前 presentation 入口行为，不应出现 sales 风格的“主问题 / 下一轮目标”定向再练卡片。

## Failure Signals

- report 或 replay 点击“按目标再练一轮”后没有走现有 `POST /api/v1/practice/sessions`，而是调用了新的 retry-only endpoint。
- create-session 请求里丢失 `focus_intent`，导致新 practice session 只是普通新会话。
- 新 `/practice/{sessionId}` 首屏没有“定向再练” callout，或 callout 内容与源 report 的主问题/下一轮目标不一致。
- replay 页生成的 retry payload 与 report 页不一致，说明两个入口没有共享 canonical retry contract。
- 非 sales session 也出现了 sales retry focus callout，说明 runtime descriptor projection 边界失守。

## Requirements Proved By This UAT

- R011 — 证明现有 report / replay / practice entry chain 已经能把 completed-session 的主问题与下一轮目标转成真实可启动的 targeted retry，并让 carried-forward focus 在新 session 首屏保持可见。

## Not Proven By This UAT

- 真实语音训练首轮里 carried-forward focus 是否会进一步改变 websocket action-card / score_update 语义；那属于 S05 的 live end-to-end 闭环 proof。
- PPT 页级 / 要点级 retry；本 slice 只把 sales `main_issue` / `next_goal` 接进当前 retry chain。

## Notes for Tester

- 这是一个“现有入口增强”slice：所有行为都必须发生在当前 report、replay、create-session API 与 practice 首屏链路上。
- 允许 replay/report 在配置缺失时显示阻断提示；这属于可解释降级，不是 bug。真正的失败是静默失效、错误默认值，或又造出一套新的 retry flow。

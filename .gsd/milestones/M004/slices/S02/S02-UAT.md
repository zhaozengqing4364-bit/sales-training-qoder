# S02: report 直达 replay 关键片段 — UAT

**Milestone:** M004
**Written:** 2026-03-25T17:22:54.339Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: 这条 slice 交付的是现有 report/replay 路由之间的 contract、URL handoff 与 degraded-state behavior；focused backend + frontend tests 已能稳定覆盖 resolved、degraded 和 missing-anchor 三条路径，而不依赖额外 runtime side effects。

## Preconditions

- Web app 能访问当前 `/practice/{sessionId}/report` 与 `/practice/{sessionId}/replay` 路由。
- 测试会话是已完成的 sales session，并且 `/api/v1/sessions/{id}/replay` 能返回 `main_issue` / `next_goal` 及其 `replay_anchor`。
- 至少准备两类样本：
  1. `replay_anchor.status="resolved"`，带 highlight marker 与 turn。
  2. `replay_anchor.status="degraded"`，只有 stage marker 或 marker/turn 已漂移。

## Smoke Test

1. 打开一个带 `main_issue.replay_anchor.status="resolved"` 的 `/practice/{sessionId}/report`。
2. 点击“定位问题片段”。
3. **Expected:** 浏览器进入 `/practice/{sessionId}/replay?...`，页面出现“已定位到主问题片段” banner，并自动滚动到对应 turn。

## Test Cases

### 1. 主问题与下一轮目标都能从 report 深链到 replay

1. 打开一个 completed sales session 的 `/practice/{sessionId}/report`，确认页面存在主问题与下一轮目标卡片。
2. 确认卡片下方出现“回放将定位到第 4 轮高光片段”这类 resolved hint。
3. 点击“定位问题片段”。
4. 记录 URL，确认 query string 至少包含 `focus=main_issue`、`message_id`、`turn`、`anchor_status=resolved`、`marker_type=highlight`。
5. 返回 report 页面，再点击“定位目标片段”。
6. **Expected:** 第二次导航的 URL 改为 `focus=next_goal`，其余 anchor 元数据保持与 report 里的 `replay_anchor` 一致；两次导航都进入当前 replay route，而不是新页面或 modal。

### 2. replay 在 resolved anchor 下会自动定位并高亮目标 turn

1. 直接访问带 resolved query 的 `/practice/{sessionId}/replay?...`。
2. 等待页面加载完成。
3. 观察顶部 anchor banner。
4. 查看 transcript 中目标 turn 卡片的视觉状态。
5. **Expected:** banner 文案包含“已定位到主问题片段”或“已定位到目标片段”，并说明“已跳转到第 X 轮对应的高光片段”；目标 turn 自动滚入视口并带有高亮边框。

### 3. 没有精确高光时，report 与 replay 都保留 degraded fallback

1. 打开一个 `replay_anchor.status="degraded"` 且 `anchor_reason="no_matching_highlight"` 的 report 页面。
2. 确认主问题/目标卡片下方出现“未找到精确高光，回放将定位到‘异议处理’阶段”之类提示。
3. 点击“定位问题片段”或“定位目标片段”。
4. 在 replay 页面观察 anchor banner 与 transcript。
5. **Expected:** replay banner 明确说明“未找到精确高光，已定位到某阶段附近的第 X 轮”；页面仍会滚到 fallback turn，并保留该 turn 的高亮样式。

### 4. 高光 evidence 卡仍可按 turn 跳入 replay

1. 在 report 页面找到现有高光 evidence 列表。
2. 点击“跳到高光回放”。
3. 观察导航后的 replay URL。
4. **Expected:** URL 使用当前 replay route，并至少包含 `focus=learning_evidence&turn=<高光turn>`；不要求 issue/goal anchor metadata，但必须落到现有 replay 页面而不是新增 route。

## Edge Cases

### 请求的 turn 和 marker 已经失效

1. 直接访问一个 `anchor_status=degraded` 但 `message_id`、`turn`、`marker_timestamp_ms` 都不再命中的 replay URL。
2. 等待页面加载完成。
3. **Expected:** replay 不自动滚动，也不静默吞掉请求；页面显示“未找到主问题片段/目标片段”的 warning banner，并保留完整 transcript 供手动查找。

### 只有 stage fallback、没有精确高光

1. 使用只包含 stage marker 的 degraded anchor 访问 replay。
2. **Expected:** 页面仍能落到相邻 turn，并把“stage fallback”明确写在 banner 中，而不是伪装成 resolved 高光定位。

## Failure Signals

- report 上没有 replay hint 或 CTA 点击后没有进入当前 `/practice/{sessionId}/replay` 路由。
- replay URL 丢失 `focus` / `turn` / `anchor_status` 等关键 query 参数，导致无法复现定位行为。
- replay 在 degraded 或 missing-anchor 情况下静默停留原位，没有 banner 或 warning copy。
- resolved anchor 进入 replay 后没有滚动/高亮目标 turn，或者错误地定位到不相关消息。

## Requirements Proved By This UAT

- R011 — 证明现有 report、replay、timeline/highlight authority line 已形成可跳转、可解释、可降级的学习证据链，而不是只能让用户手动搜索关键轮次。

## Not Proven By This UAT

- 同一 session 在 still-scoring 状态下的 replay 可用性；这仍受既有 completed-session gate 约束。
- 基于主问题或 goal family 的新一轮 targeted retry bootstrap；那是 S03 的职责。

## Notes for Tester

- 这是一个“当前入口增强”slice：所有行为都应发生在现有 `/practice/{sessionId}/report` 与 `/practice/{sessionId}/replay` 页面上。
- degraded / missing-anchor 行为不是 bug；只要提示清楚、用户还能继续在完整 transcript 中检索，就属于本 slice 接受的设计结果。

# /admin/voice-runtime 视觉分析

**wave**: admin | **截图数**: 1
**截图清单**：
- `screenshots/admin/admin-voice-runtime-1440.png` — 语音运行时策略

**a11y 树要点**：
- 1 H1: "语音运行时策略"
- 4 metric cards
- 2 sub-cards: Realtime ASR Engine / Realtime Realtime
- 0 console error

---

## P0
- 无

## P1（1 周内）

### P1-1：4 metric 数字 "2 / 2 / 0 / 1" 无单位
- 修复：每个 metric 配主标签（"活跃引擎"/"发布中" 等）

### P1-2：当前活跃引擎状态用 "Active" chip 但激活/不激活无视觉差异
- 修复：active 用绿色 pulse + 不 active 用灰

## P2（可优化）

### P2-1：温度参数 / 最大并发等无 tooltip
- 用户不知参数含义
- 修复：加 ⓘ + hover 解释

### P2-2：缺健康检查 button
- 修复："刷新" 已有但加"健康检查"

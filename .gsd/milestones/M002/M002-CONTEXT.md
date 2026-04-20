# M002: 实时教练闭环 — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

## Project Description

M002 在 M001 的稳定地基上，把销售训练从“会后看报告”推进到“训练中就能被教练”。目标不是制造噪声，而是让实时提示、阶段引导、即时评分和下一轮建议真正帮助用户调整表达：减少模糊表达、围绕正确销售阶段推进、在下一轮回答前知道最该改什么。

## Why This Milestone

用户已经明确希望客户演练过程中能有评分与下一步优化建议。没有实时教练，系统仍然更像“训练后回看工具”；有了实时教练，系统才真正具备“智能销售教练”的核心体验。但这项能力必须建立在 M001 的稳定主链路与可信事实源之上，否则实时提示会变成干扰。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在客户演练过程中收到不过度打扰的实时建议，知道下一轮最该调整什么。
- 看到当前销售阶段、阶段动作建议和实时评分变化。
- 在训练中逐步减少模糊表达，并知道自己为什么被提醒。

### Entry point / environment

- Entry point: 浏览器训练页 `/practice/[sessionId]`
- Environment: 桌面浏览器 + WebSocket 实时训练环境
- Live dependencies involved: WebSocket, LLM / ASR, 实时评分与阶段判断能力模块

## Completion Class

- Contract complete means: 实时消息协议、提示节奏与客户端状态更新具备稳定契约。
- Integration complete means: 用户发言、阶段判断、评分更新、即时建议和训练页展示在真实多轮对话里协同工作。
- Operational complete means: 提示不会高频刷屏，不会因为异常而打断训练主链路。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 用户在真实客户演练中能收到实时阶段提示、评分变化和下一轮建议。
- 提示频率与时机可控，不会让训练体验退化成“被系统不断打断”。
- 训练后报告与训练中提示在核心判断上不相互矛盾。

## Risks and Unknowns

- 实时提示可能过多，破坏表达心流。
- 阶段判断或即时评分若不稳定，会降低用户信任。
- 前端状态如果与后端提示节奏不同步，会出现 UI 抖动或提示错位。

## Existing Codebase / Prior Art

- `backend/src/agent/capabilities/fuzzy_detection.py` — 模糊词检测能力骨架。
- `backend/src/agent/capabilities/sales_stage.py` — 销售阶段识别能力骨架。
- `backend/src/agent/capabilities/realtime_scoring.py` — 实时评分能力骨架。
- `backend/src/sales_bot/websocket/components/capability_processor.py` — 实时反馈消息发送链路。
- `web/src/hooks/websocket/message-handlers.ts` — 现有 `fuzzy_detection` / `stage_update` / `score_update` 前端接收逻辑。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R009 — 训练过程中提供实时评分 / 建议。
- R003 — 支持围绕真实产品价值推进表达。
- R005 — 保持训练后报告与训练中指导的一致性。

## Scope

### In Scope

- 实时提示策略与频率控制。
- 销售阶段实时识别与阶段动作建议。
- 实时评分与下一轮动作建议。
- 模糊表达实时反馈与训练中收敛机制。

### Out of Scope / Non-Goals

- PPT 模式的实时打断式教练。
- 复杂组织化运营策略。
- 替代训练后报告；实时教练是增强，不是替换。

## Technical Constraints

- 实时提示不能成为新的不稳定源。
- 训练中提示与训练后报告必须尽量共享判断基线。
- 桌面端训练心流优先，提示应“帮助用户调整”，而不是“不断纠错刷屏”。

## Integration Points

- Sales WebSocket runtime — 实时事件发出与状态同步。
- Capability modules — 模糊词、阶段、评分。
- Training UI right panel / realtime feedback components — 实时信息展示与节奏控制。

## Open Questions

- 第一版实时提示的密度阈值如何定义最合适 — 当前倾向采用少而准、每轮有限条数的策略。

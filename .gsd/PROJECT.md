# Project

## What This Is

这是一个企业内部 AI 智能演练平台，当前已经具备销售对练、PPT 对练、Agent / Persona / 知识库管理、实时语音交互、报告与回放等基础骨架。现阶段的核心工作不是继续堆新功能，而是把“偏演示、偏娱乐化”的销售训练能力收敛成一个真正可持续使用的训练系统：训练材料来自真实知识库，训练过程尽量稳定，训练后报告可信，主管可以据此做线下辅导，用户能在“训练 → 反馈 → 复盘 → 再训练”中持续改进。

## Core Value

把真实销售训练做成稳定、可信、可持续复用的能力闭环：让销售围绕公司真实产品和标准 PPT 练出“会讲价值、会处理异议、会顺畅多轮沟通”的能力，而不是只完成一场好看的 AI 对话演示。

## Current State

- 已有双场景产品骨架：销售对练（sales）与 PPT 对练（presentation）。
- 已有前后端主链路：Next.js 用户侧与管理侧、FastAPI API、WebSocket 实时交互、PracticeSession 会话模型、报告与回放入口。
- 已有训练资产治理骨架：Agent、Persona、知识库、提示词、语音 runtime policy、管理端列表与编辑页面。
- 已有部分能力模块：模糊词检测、销售阶段识别、实时评分、回放 API、会话状态服务、知识库服务。
- M001/S01 已完成：销售训练终态现在统一走单一后端 lifecycle 写入口；StepFun runtime 已接回最小可恢复快照与 `reconnected` 协议；训练页只信服务端 lifecycle 事件，并在结束失败时留在训练页暴露 `重试结束` 与 trace 诊断。
- M001/S02 已完成：逐轮 evidence 与会话级 evaluability / result metadata 已稳定落库，report / replay / history / trends 改为共享 `SessionEvidenceService` 投影，Web 页面也停止本地拼接冲突分数来源。
- M001/S03 已完成：单次报告首屏现在由 unified evidence 直接给出结论 / 主问题 / 下一轮唯一目标 / 关键证据，主管侧 completed session 预览与 manager-lite drill-in 也统一指向同一 `/practice/{sessionId}/report` 权威页面。
- M001/S04 已完成：管理员现在可以在知识库详情页自助上传 `xlsx/xls`、重试 failed/pending 文档并运行搜索诊断；新 sales session 会冻结当时的 `knowledge_base_ids` 到 `voice_policy_snapshot`，`/practice/sessions/{id}/knowledge-check` 与 report 能暴露 hit / miss / kb_not_ready / search_failed 证据；标准 PPT 则在 live `/api/v1/presentations` 上支持 stable `presentation_id` 原位替换、`version_number` / `status` 可视化、active-session blocker，以及用户入口对当前版本/状态的展示。
- M001/S05 已完成：sales StepFun 写入层、persona policy 编译链与 web 消费面现在统一切到“价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步”语义；live `score_update`、`ScorePanel`、`/practice/{sessionId}/knowledge-check` 与 canonical `/practice/{sessionId}/report` 会围绕 ROI、价格、竞品、证据追问输出销售主问题、下一轮目标和三类 rollup，而不再沿用旧 generic 沟通标签伪装成销售判断。
- 本地运行时若要验证 supervisor preview，数据库必须先迁移到 Alembic head（至少包含 `20260317_2310_020`）；否则 admin session preview 读取会因缺少 `conversation_messages.transcript_metadata` 而假性失败。
- 当前主风险已从“训练材料是否能被后台维护并在下一次训练真实生效”转向：S06 如何把这些最新材料真正转成价值表达 / 异议处理判断基线，以及 S07 如何在最新 PPT 材料之上输出可信的会后统一复盘。
- 真实首发目标已明确：先把桌面端稳定性做满，不在第一阶段绑定移动端 / 企业微信 / 外部系统集成。

## Architecture / Key Patterns

- 前端：Next.js 16 + React 19 + TypeScript，用户侧训练页位于 `web/src/app/(user)/practice/[sessionId]/`，管理侧位于 `web/src/app/admin/*`。
- 后端：FastAPI + SQLAlchemy Async + WebSocket，核心域包含 `common`、`sales_bot`、`presentation_coach`、`agent`、`evaluation`。
- 实时交互：销售与 PPT 场景分离，各自使用独立 WebSocket handler；桌面端训练页通过统一消息协议接收 `asr_transcript`、`fuzzy_detection`、`stage_update`、`score_update`、`action_card` 等事件。
- 数据闭环：`PracticeSession` 作为事实锚点，`ConversationMessage` 承载逐轮消息、评分快照、销售阶段、高光与回放数据；报告、回放、趋势判断应尽量引用同一事实源。
- 训练资产：知识库、PPT、Agent / Persona 配置是长期运营资产；M001 不把材料写死在 prompt，而是要求管理员更新知识库 / PPT 后能影响下一次训练。

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [ ] M001: 桌面端销售训练闭环可用化 — 把桌面端客户演练、PPT 会后复盘、知识生效、单次报告与连续变化做成可真实使用的训练闭环。
- [ ] M002: 实时教练闭环 — 把训练中的实时建议、阶段引导、即时评分和下一轮动作建议做成稳定可用的教练体验。
- [ ] M003: 知识与角色真实性 — 让 AI 客户围绕真实产品、价格、竞品、证据进行可信追问，并保持 Persona 行为一致性。
- [ ] M004: 复盘与学习闭环增强 — 强化回放、高光、逐轮点评、PPT 纠偏与学习证据，让训练后改进路径更清晰。
- [ ] M005: 后台治理与规模化运营 — 完成长期运营所需的后台治理、管理动作、趋势分析、集成边界与后续扩展能力。

# M001: 桌面端销售训练闭环可用化 — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

## Project Description

该 milestone 不是从零做销售训练，而是在现有企业 AI 演练平台基础上，把桌面端销售训练链路从“模块不少、但整体偏演示和偏娱乐”收敛为真实可用的训练闭环。现有仓库已经具备销售对练、PPT 对练、知识库管理、报告、回放、实时消息协议、管理后台与基础会话模型；M001 的职责是把最关键的首发能力做扎实：桌面端客户演练稳定、多轮不坏、训练材料更新可生效、报告可信、主管可据此判断怎么带人、PPT 对练至少支持会后统一复盘。

## Why This Milestone

用户的明确目标不是继续做“会说话的 AI demo”，而是把系统落实为一个真正切实可用、可闭环、较少 bug 的完整系统。当前最危险的问题集中在主链路稳定性和训练结果可信度：多轮客户演练可能第二轮就坏；知识库虽有骨架，但未证明真实进入训练；报告与回放虽有入口，但不一定足够可信和可用于管理判断。若不先解决这些问题，后续实时教练、知识真实性、回放增强和规模化治理都会建立在不稳定地基之上。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在桌面端完成一轮稳定的客户演练，多轮来回沟通不会在第二轮或结束阶段频繁失效。
- 训练结束后立即看到一份可信的单次报告，知道哪里讲得好、哪里讲得虚、哪些异议没接住、下一次该练什么。
- 主管打开某人的报告和近期变化后，能判断该如何在线下辅导这个人。
- 培训负责人更新公司标准 PPT 或产品资料后，下一次新建训练即可使用新材料。
- 新人完成一轮 PPT 对练后，获得围绕真实 PPT 价值点的统一复盘、评分和建议。

### Entry point / environment

- Entry point: 浏览器中的用户训练页 `/practice/[sessionId]` 与管理后台 `/admin/*`
- Environment: 桌面浏览器 + 本地 / 生产式 Web 前端 + FastAPI + WebSocket 运行时
- Live dependencies involved: PostgreSQL, Redis, ChromaDB, WebSocket, ASR / TTS / LLM provider

## Completion Class

- Contract complete means: 关键会话事实、知识更新生效、单次报告与趋势视图具备明确契约和可验证输出。
- Integration complete means: 桌面端训练页、后台材料管理、会话持久化、报告读取与趋势读取在真实子系统之间串通。
- Operational complete means: 关键失败模式具备降级、恢复或诊断路径，多轮训练生命周期不会轻易卡死。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 桌面端用户可以完成一次真实的客户演练，多轮往返后顺利结束，并获得可信报告。
- 培训负责人更新一份公司标准 PPT 或产品资料后，下一次新建训练实际使用的是更新后的材料，而不是旧快照或写死 prompt。
- 主管可以打开某个学员的单次报告和最近几次变化，直接判断其卡点与下次线下辅导重点。
- PPT 对练至少能完成“完整讲完 → 会后统一复盘”的端到端链路，不能只停留在页面占位或抽象接口。
- 关键失败模式（多轮录音、知识检索、报告读取、会话结束）不能只靠模拟证明，需要有真实链路验收或可复现实证。

## Risks and Unknowns

- 多轮客户演练稳定性仍不足 — 这是首发最大风险，若第二轮仍频繁失效，则整个训练闭环不成立。
- 知识库配置不等于知识真实进入训练 — 现有实现已有风险信号，若知识未生效，训练会回到泛泛陪聊。
- 报告与回放可能引用不同事实源 — 若事实不一致，学员和主管都不会相信结果。
- 趋势视图可能只有表层聚合、缺少管理判断价值 — 若看不出“总卡在哪类问题”，连续变化就没有意义。
- PPT 对练可能已有报告骨架但缺少围绕真实价值点的可执行复盘 — 若点评泛泛，第一版也不算达标。

## Existing Codebase / Prior Art

- `web/src/app/(user)/practice/[sessionId]/page.tsx` — 桌面端训练主页面与录音 / WebSocket 入口。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 现有报告页，可作为单次报告增强起点。
- `web/src/app/admin/knowledge/page.tsx` — 现有知识库管理骨架。
- `backend/src/common/api/practice.py` — 会话创建、生命周期与报告读取相关主 API。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — 销售训练实时主链路。
- `backend/src/common/conversation/replay.py` — 回放事实读取服务。
- `backend/src/common/websocket/session_state_service.py` — 会话状态持久化与恢复基础能力。
- `docs/business-usage-growth-analysis-2026-02.md` — 已明确指出不能靠堆页面替代训练闭环建设。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R001 — 收敛多轮客户演练稳定性。
- R002 — 确保训练异常可恢复或可降级。
- R003 — 让销售训练围绕真实产品价值，而不是背 PPT。
- R004 — 保证管理员更新材料后，下一次训练生效。
- R005 — 提供可信的单次学员报告。
- R006 — 提供主管可直接使用的单次判断依据。
- R007 — 提供近期连续变化视图。
- R008 — 提供 PPT 对练第一版会后统一复盘能力。

## Scope

### In Scope

- 桌面端客户演练多轮稳定性与运行时状态收口。
- 会话事实源统一：逐轮内容、关键问题、阶段、评分、异议证据等。
- 面向学员与主管的单次报告与近期变化视图。
- 管理员更新公司标准 PPT / 产品资料并在下一次训练生效。
- PPT 对练第一版“完整讲完后统一复盘”。
- 关键失败模式的降级、日志与可诊断路径。

### Out of Scope / Non-Goals

- 移动端 / 企业微信首发体验。
- 外部系统集成（SSO / CRM / 外部文档系统）。
- 系统内的主管任务派发、跟进动作与训练任务编排。
- PPT 对练实时打断式教练。
- 全面组织化运营能力与 ROI 证明体系。

## Technical Constraints

- 真实首发环境以桌面端为准，不为移动端妥协 M001 范围。
- 训练材料的事实源优先来自知识库 / PPT 管理，不把业务知识重新硬编码进 prompt 当成完成。
- 报告、回放、趋势判断应尽量共享同一事实源与契约，避免各自重算。
- 第一版主管动作在线下发生，系统只负责给出可执行判断依据。
- 需要尊重现有销售与 PPT 场景独立演进的架构边界。

## Integration Points

- Practice session lifecycle — 创建、进行、结束、持久化与报告读取。
- Sales WebSocket runtime — 多轮会话、转写、实时反馈与结束流程。
- Knowledge base management — 管理员更新训练材料与训练运行时读取。
- Conversation / replay data store — 报告、回放与趋势共享事实源。
- Admin records / knowledge UI — 管理侧报告阅读与材料更新入口。

## Open Questions

- 单次报告中“未接住的异议”在 M001 应做到多细的结构化归因 — 当前倾向先保证可读、可执行，再逐步增强细粒度归因。
- 趋势视图第一版显示哪些聚合维度最有管理价值 — 当前倾向先聚焦重复卡点、是否进步、是否该换训练重点，而不是大而全分析面板。

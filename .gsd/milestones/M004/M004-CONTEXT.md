# M004: 复盘与学习闭环增强 — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

## Project Description

M004 关注训练后的“学会”。在 M001 已具备单次报告和趋势基础之后，M004 要把会话结果进一步沉淀为真正可学习的证据链：回放、高光、逐轮点评、优秀话术参考、围绕 PPT 和销售阶段的学习证据，以及更强的再练闭环。

## Why This Milestone

用户的目标不是获得一次分数，而是逐步练出真实能力。如果没有更强的复盘与学习证据，用户和主管都只能拿到静态总结，难以形成长期行为改变。M004 负责把“这次为什么好 / 差、下一次如何更具体地练”做得更深。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 回放自己的训练过程，看到逐轮高光、问题点和 AI 点评。
- 对照优秀表达方式理解自己哪里讲虚、哪里没有把价值点讲透。
- 在 PPT 对练中看到围绕价值点、结构和讲偏问题的更具体复盘证据。

### Entry point / environment

- Entry point: 报告页、回放页、历史页
- Environment: 桌面浏览器 + 后端会话数据读取 / 评估服务
- Live dependencies involved: PracticeSession / ConversationMessage 数据库, 回放 API, 报告生成服务

## Completion Class

- Contract complete means: 回放、高光、逐轮点评与再练建议的输出契约稳定。
- Integration complete means: 训练事实、报告、回放和再练入口在真实完成会话上串通。
- Operational complete means: 数据读取、回放和报告生成在已完成会话上稳定可用。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 用户可以对已完成的销售或 PPT 训练进行逐轮回放，并看到关键高光与问题说明。
- 用户能够从报告直接进入针对主改进点的再练路径，而不是只停留在阅读。
- 主管可用回放证据辅助线下辅导，而不只是依赖抽象总结。

## Risks and Unknowns

- 数据虽然已落库，但缺少足够解释性，无法支撑“为什么错”。
- 回放 / 高光如果质量低，会沦为另一个只看热闹的页面。
- 再练建议如果不够具体，用户仍然不知道下一次怎么改。

## Existing Codebase / Prior Art

- `backend/src/common/conversation/replay.py` — 回放数据服务骨架。
- `backend/src/common/conversation/api.py` — 回放相关 API。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 现有报告入口。
- `web/src/lib/api/client.ts` — 报告、回放、高光 API 访问层。
- `backend/src/evaluation/services/comprehensive_report.py` — 综合报告生成服务。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R011 — 会话结果沉淀为可复盘数据资产。
- R005 — 单次报告需要可执行。
- R006 — 主管需要可用于辅导的证据。

## Scope

### In Scope

- 回放、高光、逐轮点评与更具体的再练建议。
- 销售与 PPT 两个场景的学习证据强化。
- 训练后“看报告 → 再练”的更强闭环。

### Out of Scope / Non-Goals

- 复杂组织级学习运营与自动任务分配。
- 移动端复盘体验专项优化。

## Technical Constraints

- 回放与点评必须引用真实训练事实，不能脱离会话数据重新编造。
- 高光与问题说明必须以“能帮助下一次改进”为标准，而不是只做展示。

## Integration Points

- Conversation replay APIs.
- Comprehensive report generation.
- User history / report / replay pages.

## Open Questions

- 优秀话术参考在第一轮增强中采用模板化示例还是基于训练材料动态生成 — 当前倾向先采用受控模板 + 真实材料引用。

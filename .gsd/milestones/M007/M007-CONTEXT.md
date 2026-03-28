# M007: 实时教练闭环正式封板

**Gathered:** 2026-03-28
**Status:** Ready for planning

## Project Description

M007 不是新产品线，也不是继续沿旧 M002 remediation 命名思路打补丁。它要把已经开始但尚未诚实封板的 realtime coaching closure，正式吸收到 M007 的 milestone 结构里：在现有 learner/runtime/report/replay 路由族上，把训练中的 coach degraded / resumed 状态做成对学员真实可见、可理解、可追溯；再用同一条真实 session 证明 `/practice/{sessionId}` 的实时教练，到 `/practice/{sessionId}/report` 与 `/practice/{sessionId}/replay` 的结论是连贯的；最后把 requirement / roadmap / validation / summary / state 的 authority 重新对齐，让这条能力线可以被诚实标记为完成。

## Why This Milestone

M002 的 S01-S04 已经交付了 realtime sales rubric、pacing、shared coaching focus、completed-session alignment 等基础，但 close-out 审计仍明确指出两类未退休风险：一是训练中的 coach degraded / resumed 没有在当前产品链路上被真实证明且对学员可见；二是缺少一条同一条真实 session 从 live coaching 走到最终 report/replay 的 closure proof。继续把这件事挂在旧 M002 remediation 尾巴上，会让 requirement 状态、milestone 工件和真实产品状态继续漂移。现在做 M007，就是把这条 closure 工作正式收口成一个独立、可验证、可结束的 milestone。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在现有 `/practice/{sessionId}` 训练页上看到明确但不打断训练的 coach degraded / resumed 状态，并理解“训练还在继续，只是教练链路暂时降级或已恢复”。
- 用同一条真实 sales session，从训练中的实时教练走到 `/practice/{sessionId}/report` 与 `/practice/{sessionId}/replay`，看到同一问题家族 / 下一轮目标家族的连贯结论，而不是各说各话。

### Entry point / environment

- Entry point: `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay`
- Environment: localhost browser + 当前 FastAPI / Next.js 本地运行链路
- Live dependencies involved: practice session API、sales realtime websocket handlers（StepFun + classic）、completed-session projection、report/replay APIs

## Completion Class

- Contract complete means: focused backend/frontend tests覆盖 coach degraded / resumed contract、runtime diagnostics、report/replay same-family assertions、旧 M002 remediation artifact 吸收后的 requirement/roadmap/validation/summary 对账。
- Integration complete means: 同一条真实 localhost sales session 在现有 learner/runtime/report/replay 路由族上完成 realtime coaching → report → replay 的闭环证明，且 degraded / resumed 与最终结论不漂移。
- Operational complete means: reconnect / restore / capability failure / 上游短暂抖动下，训练主链路继续可用，coach health 状态不会在恢复或重连后说谎。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 一条真实 localhost sales session 在 `/practice/{sessionId}` 训练过程中出现可辨认的 coach health 状态变化（包括 degraded 或 resumed），但训练主链路不中断。
- 这同一条 session 在 `/practice/{sessionId}/report` 与 `/practice/{sessionId}/replay` 上呈现的 `main_issue` / `next_goal` / coach 结论，和训练中 surviving realtime coaching direction 保持同一问题家族 / 目标家族。
- 不能用跨 session 拼接证据、不能只靠 fixtures/mocks 代替 live proof、不能只把 close-out 写进工件而产品链路本身不成立。

## Risks and Unknowns

- reconnect / restore 后 handler 内部状态与 UI 状态可能再次漂移 —— 这会让“已恢复”或“仍降级”的可见性只在一次消息里短暂成立，无法真正封板。
- realtime coaching 与 completed-session projection 可能仍存在不同源的结论逻辑 —— 这会让同一 session 的训练页、report、replay 继续出现“练中说 A，练后说 B”的漂移。
- 旧 M002 remediation artifacts 吸收进 M007 的 authority 切换如果写得含糊 —— 后续 agent 仍会被 M002/M007 双重叙事误导，流程状态继续打架。

## Existing Codebase / Prior Art

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` —— 当前 StepFun sales realtime handler，已经承载 coach health、reconnect snapshot、score/action/stage runtime 事实线。
- `backend/src/sales_bot/websocket/enhanced_handler.py` —— classic sales runtime handler，现有 closure 需要保证它和 StepFun 在 coach health truth line 上不漂移。
- `backend/src/common/api/practice.py` —— learner-facing practice/report/knowledge-check session API，M007 必须继续沿现有入口完成 closure。
- `backend/src/common/conversation/replay.py` —— `/api/v1/sessions/{id}/replay` 当前 authority seam；same-session closure proof 不能绕过它。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` —— learner report 现有 authority page，必须继续消费同一 completed-session conclusion family。
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` —— learner replay 现有 authority page，必须继续消费同一 replay/read-side 事实线。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R009 — M007 负责把旧 M002 remediation 残留的 realtime coaching closure 正式收口并推动其从 active 走向 validated。

## Scope

### In Scope

- 在现有 learner/runtime/report/replay 路由族上完成 coach degraded / resumed 真相面。
- 用同一条真实 localhost sales session 完成 realtime coaching → report → replay 的 same-session closure proof。
- 将已开始的 M002 remediation artifacts、以及 requirement / roadmap / validation / summary / state 的 authority 正式归并到 M007。
- 在不改变现有产品入口的前提下完成最终 validation 与封板。

### Out of Scope / Non-Goals

- 不重做 sales rubric、pacing 语义或已交付的 S01-S04 核心语义，除非 live proof 暴露真实回归。
- 不新增页面、第二套 debug console、或 milestone-only API。
- 不顺手扩展 M003/M004/M005 的其它能力。
- 不继续沿旧 M002 remediation 命名和工件思路做临时收尾。

## Technical Constraints

- 继续停留在现有 `/practice/{sessionId}`、`/practice/{sessionId}/report`、`/practice/{sessionId}/replay` 路由族上完成 closure proof。
- degraded / resumed 必须“明确但不打断”，不能把训练页变成异常面板。
- live closure proof 必须是同一条真实 session，不接受跨 session 拼接证据。
- 最终 close-out 只有在“产品真相 proof + 工件对账”同轮通过时才成立。

## Integration Points

- Sales realtime websocket handlers（StepFun + classic）—— 负责训练中的 coach health truth line、reconnect 恢复与 realtime coaching direction。
- `common.api.practice` —— 负责 learner-facing session/report/knowledge-check authority entrypoints。
- `common.conversation.replay` + `SessionEvidenceService` —— 负责 completed-session replay/read-side conclusion truth line。
- Next.js learner pages —— 负责把 degraded / resumed 与同源结论呈现在当前 report/replay/practice surfaces 上。

## Open Questions

- 旧 M002 validation / summary 是否需要在 M007 执行中被明确标记为“historical partial foundation”，还是只需要把 authority 切换到 M007 而不再回写旧 milestone —— 当前倾向：保留历史事实，不伪造旧 milestone 已封板，但后续 closure authority 统一写入 M007。
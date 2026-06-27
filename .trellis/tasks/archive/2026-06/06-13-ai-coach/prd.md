# AI Coach 流式训练闭环升级

Status: completed

## Goal

把 `/sales-trainer/business-skills/coach` 从“能演示的整包 Chatbot”升级为可给普通学员使用的教练主导训练局：入口恢复可理解、新开一局有即时反馈、训练主流程必须稳定生成题卡、长耗时步骤可流式呈现、失败状态可恢复且可审计。

## Requirements

- 首次进入商务技巧 AI Coach 页面时，不再无条件进入旧对话；只自动恢复仍有待答题卡的训练局，总结态/完成态应提供清晰的新开局或复盘入口。
- “新开一局”必须明确触发新 session，并在后端生成首题期间保持可理解的页面状态，不出现无反馈或空白等待。
- 训练主流程不得依赖自由文本弱约束生成题卡；开始、继续、重试、换场景、讲解、总结等主流程动作必须走后端 `next_action` 契约。
- 新增事件流式接口，用于 session 创建、发送训练命令、提交答案后自动推进，至少流式返回阶段事件、错误事件和最终 session snapshot。
- 前端必须增量渲染事件流：显示阶段状态、保留已有对话、显示题卡生成中状态，最终替换为真实卡片。
- 自由文本输入保留为辅助问答，但当学员表达训练意图时，应路由到确定性训练命令或给出可点击建议，不允许出现“说开始但无题卡”的静默状态。
- 失败、超时、配置禁用、LLM 输出非法等情况必须显示可恢复动作，并保留操作日志/trace。
- 更新 API contract、前后端类型、单元/页面/契约测试。

## Configuration Boundary

- 稳定代码逻辑：会话状态机、动作级 UI event 约束、public DTO 脱敏、SSE event envelope、权限/归属校验、错误代码映射。
- 可配置业务规则：入口恢复策略、是否启用流式、首题生成行为、失败降级策略、阶段提示文案、生成超时阈值。
- 配置来源：复用新人路径 `modules[].ai_coach`，不新增孤立配置表。
- 管理入口：`/admin/sales-trainer/ai-coach`，继续依赖路径配置 revision、发布、回滚与 operation log。
- 缺失/非法配置：后端使用安全默认值或 typed error；前端展示后端返回状态，不在页面组件内自造业务策略。

## Acceptance Criteria

- [x] 默认进入页面不会把已总结/已完成旧局当作当前训练主流程。
- [x] 点击“新开一局”后 1 秒内出现创建/生成阶段状态；最终首题可渲染，失败时有重试/换主题/总结入口。
- [x] 提交答案后 1 秒内出现评分/下一题生成阶段状态；最终下一张题卡可渲染，失败时评分结果仍保留。
- [x] 自由文本路径不再能成功返回“开始训练”文本但无任何可操作题卡或恢复动作。
- [x] 新 SSE/stream 接口返回 typed event；前端 stream parser 有测试覆盖。
- [x] 后端测试覆盖 resume policy、command 主流程、stream event 序列、fallback/retry、非法 record/session 归属。
- [x] 前端测试覆盖入口策略、新开局 pending 状态、流式阶段渲染、最终 snapshot、失败恢复状态。
- [x] `docs/api-contract/sales-trainer.md` 与实现一致。

## Completion Notes

- 后端新增事件级 SSE stream service；普通 JSON endpoint 保持兼容。
- 前端统一通过 `api` facade 读取 SSE，不在页面内维护鉴权、CSRF、trace 或解析逻辑。
- 浏览器验证使用 Playwright fallback 完成；Codex in-app Browser 当时无法 attach 当前 tab。
- 本次交付是事件级流式渲染，不是 provider token 级流式输出。题卡仍需等完整 JSON 通过白名单校验后渲染。

## Technical Approach

- 后端增加一个小的 AI Coach stream service，复用现有 `AiCoachChatService`、`AiCoachChatAutoAdvance`、`AiCoachChatProjection`，不复制业务规则。
- SSE 事件采用 `text/event-stream`，事件类型包括 `status`、`session_snapshot`、`error`。题卡仍以校验后的完整 `ui_event` 进入最终 snapshot，避免前端渲染半截 JSON。
- 会话创建拆出“同步创建 session + 异步/流式首题推进”语义；普通 JSON endpoint 保持兼容，stream endpoint 给新 UI 使用。
- 前端将 page 内的异步流程下沉到 route-local hook/helper，页面只负责展示和触发；API 调用仍通过 `@/lib/api`。
- 训练主按钮全部走 `command`；自由文本发送后若返回无 active event 且无可操作 followup，要展示恢复动作并记录为降级状态。

## Decision (ADR-lite)

Context: 现有 JSON snapshot endpoint 会在 LLM 完整生成、解析、校验、落库后一次性返回，浏览器实测新开局约 17.5 秒、答后推进约 11.6 秒。现有 `LLMService` 只有 `agenerate()` 整包调用，题卡 JSON 也不能安全渲染半截结构。

Decision: 本任务先落地事件级 SSE 流式渲染，并为后续 token 级文本流保留 adapter 边界；题卡继续以完整、校验后的 `ui_event` 渲染。

Consequences: 体验上马上解决长等待无反馈与半截状态不可见；文本 token 级流式需要后续补齐 provider streaming adapter，但不会阻塞当前训练闭环稳定性。

## Out of Scope

- 不接入实时 WebSocket 语音对练。
- 不复用 `/practice/[sessionId]` 的实时销售练习 runtime。
- 不把 AI Coach 变成通用聊天产品。
- 不允许前端绕过后端状态机自行决定下一题。

## Technical Notes

- 相关前端入口：`web/src/app/(dashboard)/sales-trainer/business-skills/coach/`
- 相关 API client：`web/src/lib/api/client-domains.ts`、`web/src/lib/api/types.ts`
- 相关后端路由：`backend/src/sales_trainer/ai_coach_api.py`
- 相关后端服务：`backend/src/sales_trainer/services/ai_coach_chat_*`
- 相关契约：`docs/api-contract/sales-trainer.md`
- 当前实测：`POST /chat/sessions` 新开局约 17.5s；`POST /events/{id}/answer` 答后推进约 11.6s。

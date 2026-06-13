# AI Coach 页面高度与评分口径修复

Status: completed

## Goal

修复商务技巧 AI Coach 学员页的两个影响可用性的缺陷：对话内容增多时页面/面板不能无限向下撑高，单选/多选题反馈不能把内部 0-100 掌握分直接展示成“100 / 100”考试分。目标是让普通学员看到稳定的训练面板、清楚的题目反馈、明确的掌握/未掌握标准和下一步动作。

## What I Already Know

- 用户在 `http://localhost:3445/sales-trainer/business-skills/coach` 遇到页面高度异常：内容多时训练面板不断向下拓展。
- 浏览器 DOM 指标显示 `main` 为 `h-screen overflow-y-auto`，AI Coach surface 是 `min-h-[calc(100vh-7rem)]`，消息区是 `flex-1 overflow-y-auto`，但外层 surface 没有固定/最大高度约束，导致内容先撑大外层而非在消息区内部滚动。
- 前端 `ScoreFeedback` 直接展示 `event.score_result.score / event.score_result.max_score`，所以单选题出现 `100 / 100`。
- 后端选择题评分用 `AiCoachScoreResultV1(score, max_score)`，状态机用 `AiCoachConfig.mastery_threshold` 判断掌握和自动推进；这属于稳定训练策略，不应从页面硬编码。
- 学员侧真正需要的是“本题答对/答错、是否达到掌握标准、为什么、下一步怎么练”，不是考试式分数。

## Configuration Boundary

- 稳定代码逻辑：对话面板 viewport 内布局、消息区内部滚动、SSE 状态渲染、选择题正确性判定、掌握状态投影、UI 不泄露 answer_key/rubric。
- 可配置业务规则：`mastery_threshold`、题目评分 `scoring_rubric.max_score`、自动推进阈值、补救策略，继续复用 `modules[].ai_coach` 后端配置。
- 新增配置项：本任务不新增配置项。
- 不得硬编码：前端不得写死 80 分、100 分作为业务规则；只能展示后端返回的掌握阈值/投影字段或本题判定。

## Requirements

- 对话 surface 高度必须被约束在当前 viewport 内，header/status/footer 固定占位，只有消息列表内部滚动。
- 页面不应出现 `main` 和消息列表双重失控滚动；桌面端底部输入框应留在训练面板底部。
- 消息列表内容过多时，历史消息在消息区内滚动，不应把整页无限撑高。
- 单选/多选题提交后，学员界面不再显示 `100 / 100` 这种考试分样式。
- 选择题反馈应显示：答对/未掌握、是否达到本轮掌握标准、反馈文本、缺失点。
- 掌握阈值必须来自后端会话投影/配置，不在页面组件里写死。
- 短答题或未来分档评分可以保留数值，但必须用“掌握度/本题得分”语义，不用裸 `score / max_score`。
- 更新 API 类型、前后端测试和契约文档。

## Acceptance Criteria

- [x] 在 1399x1354 和 1280x720 视口下，对话 surface 不超过可用视口高度；消息列表 `scrollHeight > clientHeight` 时由消息区内部滚动。
- [x] 提交多题后，底部操作区和输入区仍位于面板底部，不被历史消息推到页面下方。
- [x] 单选/多选题结果不再渲染 `100 / 100` 文本。
- [x] 正确题显示“答对 / 已达到掌握标准”，错误题显示“未掌握 / 未达到掌握标准”。
- [x] 展示本轮掌握标准时使用后端返回值，例如 `掌握标准：80%`；缺失时不伪造默认值。
- [x] 后端 stream/session DTO 提供足够的掌握阈值或结果判定字段，前端无需读取隐藏 rubric。
- [x] 相关后端 unit、前端页面/组件测试通过。
- [x] `docs/api-contract/sales-trainer.md` 与实现一致。

## Completion Notes

- 对话 surface 改为 viewport-bound flex shell；消息区 `min-h-0 overflow-y-auto`，底部操作/输入区 `shrink-0`。
- `AiCoachScoreResultV1` 增加 `mastery_threshold` 和 `mastered`，由后端配置快照计算，前端不硬编码阈值。
- 学员选择题结果改为“答对/未掌握 + 本轮掌握标准”，不再展示 `score / max_score`。
- 浏览器验证覆盖 1399x1354 与 1280x720。

## Out of Scope

- 不做实时 WebSocket 语音对练。
- 不做 provider token 级流式输出。
- 不重做 AI Coach 整体视觉风格。
- 不新增独立配置表。

## Technical Notes

- 前端：`web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-conversation.tsx`
- 前端：`web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-message-list.tsx`
- 前端：`web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-cards.tsx`
- 后端：`backend/src/sales_trainer/ai_coach_chat_schemas.py`
- 后端：`backend/src/sales_trainer/services/ai_coach_chat_projection.py`
- 后端：`backend/src/sales_trainer/schemas.py`
- 契约：`docs/api-contract/sales-trainer.md`

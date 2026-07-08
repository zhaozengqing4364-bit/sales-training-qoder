# AI 补练教练 UX 与可靠性研究

## Sources

* Google People + AI Guidebook: https://pair.withgoogle.com/guidebook/
* NN/g The User Experience of Chatbots: https://www.nngroup.com/articles/chatbots/
* NN/g Error-Message Guidelines: https://www.nngroup.com/articles/error-message-guidelines/
* NN/g 10 Usability Heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
* OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
* OpenAI Structured Outputs announcement: https://openai.com/index/introducing-structured-outputs-in-the-api/

## One-Line Takeaway

AI 补练教练应采用“受控任务流 + 状态化训练卡 + 明确错误恢复 + 严格结构化输出”，而不是把自由聊天作为主流程。

## Common Conventions

* Conversational UI works best when it is domain-specific and constrained to a limited task set; open-ended chat breaks down when users deviate from expected flows.
* AI product UX should help users form the right mental model: what the system can do, what it needs from the user, and how confident/complete the output is.
* Effective error recovery explains the problem in user language, respects the effort already invested, and gives an immediate recovery action.
* JSON mode / valid JSON is insufficient for production workflows that depend on structured events; strict schema outputs or equivalent validation/retry/fallback pipelines are needed.

## Mapping to This Repo

* The repo already has task-state building blocks: `TrainingJourney`, `ModuleProgress`, `BusinessEtiquetteAiCoachProgress`, `coach_state`, `next_action`, `ui_events`, `score_result`.
* The current UX still lets chat and followup prompt chips behave like the primary flow. This weakens the mental model because users do not know whether they are chatting, answering a card, recovering from failure, or completing a path gate.
* Current failure handling preserves data but still surfaces “下一步训练生成失败” as a user-facing training event. Better fallback should continue the training with a deterministic card/template or clearly offer one recommended action.
* Current code contract around `continue_drill` conflicts with docs. This is exactly the type of schema/task mismatch that structured-output guidance warns about.

## Feasible Approaches Here

### Approach A: 状态卡优先的 AI 补练工作台

* How it works: Keep chat, but demote it below a task header + active training card + feedback/next-step card. Training state comes from backend progress/Journey.
* Pros: Matches the domain task, lower ambiguity, compatible with existing event model.
* Cons: Requires frontend restructuring and backend next-action context.

### Approach B: 纯聊天增强

* How it works: Keep current chat layout, improve prompt, buttons, retry, error copy.
* Pros: Fastest to ship.
* Cons: Does not fix the core mental-model problem; future TrainingJourney integration remains weak.

### Approach C: 全状态机重构

* How it works: Introduce a dedicated remediation-session aggregate/table and make all coach steps deterministic state transitions.
* Pros: Strongest long-term consistency and analytics.
* Cons: High migration and scope risk; likely too large for MVP.

## Recommended Direction

Start with Approach A as MVP. It uses existing state and evidence models, fixes the biggest UX issue, and avoids overbuilding a new aggregate before the product shape is proven.


# brainstorm: AI 补练教练升级计划

## Goal

把新人训练路径里的“商务技巧 AI 教练”从偏自由聊天和临时题卡生成，升级为路径状态驱动的 AI 补练工作台。目标是让新人进入后 3 秒内知道为什么来、现在练什么、通过标准是什么、做完去哪，同时让培训负责人拿到可追踪的补练证据、达标判断和人工复核线索。

## What I Already Know

* 用户认为当前 AI 教练在新人路径里应承担补练、诊断、训练推进和达标辅助作用，而不是自由聊天助手。
* 当前页面路径为 `/sales-trainer/business-skills/coach`，前端由 `web/src/app/(dashboard)/sales-trainer/business-skills/coach/page.tsx` 与 `coach-conversation.tsx` 组成。
* 当前 AI 教练已有会话、消息、UI event、题卡、评分、summary、followup prompt 和 SSE 流式接口。
* 当前已有 `BusinessEtiquetteAiCoachProgressService`，能按小单元聚合 scored `quiz_card`，计算 `passed`、`ready_for_field`、`manual_review_required`、`block_next`、薄弱能力点、推荐章节和下一步。
* ADR 已明确：若 active revision 声明 `require_ai_coach=true`，TrainingJourney 必须包含 AI Coach `ModuleProgress`、达标 outcome、补救/人工复盘状态和历史证据。
* 文档已把商务技巧 AI 教练定位为“AI 补练教练”，其 V0.9 角色是学习材料或小测之后的 AI 辅导与补练。
* 当前 `TrainingJourneyService` 对 `kind="ai_coach"` 的 next action 只返回“进入/继续 AI 教练”，目标路径没有携带来源、小单元、薄弱点或补练上下文。
* 当前小测结果页只在未通过时从 TrainingJourney 找 AI Coach 入口，按钮文案为“进入 AI 教练”，缺少“为什么补练”和“补什么”的上下文传递。
* 当前商务技巧工作台可以从 TrainingJourney 解析 coachHref，但 AI 教练页面本身仍主要按 session 恢复/新开来工作。
* 已发现实现与契约存在不一致：文档允许 `continue_drill` 只解释或追问，但代码对 `continue_drill` 强制要求 1 张 `quiz_card`，导致模型输出稍有偏差就失败。

## Assumptions (Temporary)

* MVP 不应先追求全量“真人教练式自由对话”，应先保证补练主流程稳定。
* 新体验应以 TrainingJourney / BusinessEtiquetteAiCoachProgress 为主状态来源，前端不自行推断达标或阻断。
* AI 生成失败不应直接打断学员；系统应先自动重试、降级为固定/模板题或给出确定性下一步。
* 旧历史 session 需要兼容展示，但不应阻塞新补练工作台的状态设计。

## Open Questions

* 最后确认：是否按当前 PRD 进入实现计划拆分？

## Requirements (Evolving)

* AI 教练在新人路径中定位为“AI 补练教练 / 情景补练教练”。
* 学员页面必须明确展示当前补练任务、来源、目标能力点、达标标准、当前状态和推荐主操作。
* 训练动作应由后端状态和配置驱动，前端不通过按钮文案猜测意图。
* 失败恢复必须可见、可追踪、可继续，不得出现“点了之后秒没”或只给红色错误框。
* AI 补练结果必须能作为 TrainingJourney / 训练记录 / readiness dossier 的证据使用。
* 首版应优先做“状态卡优先的 AI 补练工作台”，而不是纯聊天增强。
* AI 生成失败时应优先走自动重试与确定性兜底，学员侧只看到可继续的训练路径。
* `continue_drill`、`remediate`、`switch_scenario`、`summarize` 等动作必须有一致的动作契约、前端主操作和测试覆盖。
* MVP 只做商务技巧小单元 AI 补练工作台，优先把文章/小测后的补练闭环做稳。
* MVP 暂不接入录音/PPT 讲解薄弱项到 AI 补练上下文。
* 进入 AI 补练时采用状态驱动优先：小测未通过则按未通过小单元和薄弱能力点进入补练；只读完文章但未小测则进入该小单元基础练习；已达标则主操作变成返回新人路径或继续下一单元。
* AI 题卡生成失败时，MVP 采用“自动重试 + 固定模板题兜底”：LLM 首次失败自动重试；仍失败时后端按小单元、能力点和训练卡类型生成一张确定性保底训练卡，保证用户能继续练。
* 学员侧达标标准采用“等级语言为主，分数为辅”：主文案解释基础掌握/可上场，辅助展示配置化达标线，例如“本轮达标线 70 分”。
* AI 补练达标后自动切到完成态，不再默认推下一题；主操作返回新人路径或继续下一单元，次操作保留“再练一题”。
* 工作台首屏采用“任务卡置顶 + 训练卡居中 + 聊天折叠”：任务卡解释为什么来、练什么、达标标准和主操作；训练卡/反馈卡是主要交互区；聊天历史降级为辅助解释。

## Acceptance Criteria (Evolving)

* [ ] 新人进入 AI 补练页后，首屏能看到来源、训练目标、通过标准、当前状态和一个主操作。
* [ ] 小测未达标进入 AI 补练时，页面能说明薄弱能力点和推荐补练动作。
* [ ] 文章读完但未小测时，AI 补练能以当前小单元基础练习开局。
* [ ] 已达标时，AI 补练页不继续强推下一题，主操作指向返回新人路径或继续下一单元。
* [ ] 达标后页面进入完成态，默认不自动继续生成下一题；用户仍可通过次操作主动再练。
* [ ] 学员侧达标标准不裸露为考试刷分体验，必须同时解释能力等级和配置化分数线。
* [ ] 首屏主视觉是补练任务和训练卡，而不是聊天记录或系统元数据。
* [ ] AI 生成失败时，训练进度保留，页面给出确定性恢复路径，不让用户反复猜“重试/换主题/总结”。
* [ ] LLM 生成题卡失败且重试仍失败时，后端能返回一张合法的保底训练卡或明确记录 terminal 配置异常。
* [ ] `continue_drill` 等 next action 的实现与 API 契约一致，并有测试覆盖。
* [ ] AI 补练达标、未达标、待人工复盘状态能进入后端进度/记录投影。
* [ ] 旧 session 可继续查看或恢复，不因为新补练工作台改版丢失历史证据。
* [ ] 前端不展示 raw prompt、answer key、scoring rubric、内部错误码或工程化状态。

## Definition of Done (Team Quality Bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky
* 权限、对象级准入、active revision、snapshot-first 历史展示和失败分类不被前端绕过

## Out of Scope (Explicit)

* 不在本轮重做整个新人训练路径首页。
* 不在本轮让 AI 自动确认最终达标，最终放行/人工复核规则仍由路径配置与负责人治理。
* 不在本轮引入新的外部 AI provider。
* 不在本轮删除旧 AI Coach 历史会话。
* MVP 默认不新建独立 remediation aggregate 表，除非后续确认需要强事务编排。
* 不在 MVP 同时接入录音/PPT 讲解薄弱项，先保留为后续扩展。

## Research References

* [`research/ai-coach-ux-and-reliability.md`](research/ai-coach-ux-and-reliability.md) — 任务型 AI 教练应采用受控任务流、明确恢复路径和严格结构化输出。

## Research Notes

### What Similar Tools/Guidelines Suggest

* 任务型聊天机器人适合有限任务集，不适合把核心业务流程完全交给开放聊天。
* AI 产品要帮助用户建立正确心理模型：系统能做什么、下一步是什么、结果是否可依赖。
* 错误恢复要尊重用户已投入的努力，并给立即可执行的解决动作。
* 依赖结构化 UI event 的 AI 生成链路不能只要求“JSON 有效”，必须通过 schema、动作契约、重试和兜底保证可推进。

### Constraints From This Repo

* TrainingJourney 已是新人路径统一读模型；AI 补练入口应以 `modules[].next_action` 为权威。
* BusinessEtiquetteAiCoachProgress 已能计算小单元状态、达标、可上场、待人工复盘、阻断和推荐章节。
* 前端 AI Coach 页面已有流式会话和题卡渲染，但当前主体验仍偏聊天流。
* 小测结果页和商务技巧页已有 AI Coach 入口，但入口只传路径，不传“补练来源 / 目标小单元 / 薄弱能力”。
* 当前动作契约实现与文档不一致，是稳定性和体验问题的根因之一。

## Expansion Sweep

### Future Evolution

* AI 补练未来可能承接文章、小测、录音、实时对练前置准入和培训负责人复核，不应只绑定“聊天 session”视角。
* 后续可演进为独立补练任务：来源证据、目标能力、重练次数、当前状态、前后对比和负责人审批。

### Related Scenarios

* 商务礼仪小测未达标、PPT 讲解录音低分、真实语音对练准入失败、培训负责人要求重练，都应使用同一套“补练原因 -> 训练动作 -> 达标证据”的语言。
* 管理端训练记录、readiness dossier、analytics 风险队列需要能解释 AI 补练为什么触发、练了什么、是否阻断。

### Failure & Edge Cases

* AI 题卡生成不合约、超时、provider 不可用、Prompt 配置缺失、评分 Prompt 缺失，需要区分 transient 与 terminal。
* 同一用户多开标签、重复点击、旧 session 缺快照、active revision 更新、历史 session 与新配置不一致，都不能破坏证据链。
* 不能把 AI 的自由聊天内容当达标结论；必须来自 scored card / summary / progress projection。

## Feasible Approaches

### Approach A: 状态卡优先的 AI 补练工作台 (Recommended)

* How: 复用现有 session/event/progress 模型；前端重塑为任务卡、训练卡、反馈卡、下一步卡；后端补齐进入上下文、动作契约和失败兜底。
* Pros: 最大程度复用现有代码，最快解决用户“没方向、点了没用、失败频繁”的核心问题。
* Cons: 仍然依赖现有 session/event 表，长期补练任务编排能力有限。

### Approach B: 纯聊天增强

* How: 保留现有聊天界面，只优化提示词、错误文案、按钮和 retry。
* Pros: 改动小。
* Cons: 不解决新人路径中的补练定位和证据沉淀问题，后续仍会返工。

### Approach C: 独立补练任务状态机

* How: 新增 remediation task/attempt 读写模型，把 AI Coach 作为补练任务执行器。
* Pros: 长期最干净，适合跨小测、录音、对练统一补救。
* Cons: migration、历史回填、权限和发布风险大，不适合作为第一版。

## Recommended MVP

采用 Approach A，拆成小 PR：

* PR1: 契约与后端稳定性
  * 统一 `continue_drill` 文档与实现。
  * 增加生成失败自动恢复策略：自动重试、降级 followup、必要时使用确定性模板题/固定题。
  * 把失败 action 的用户可见文案转成“训练进度已保存 + 推荐下一步”，内部错误码只进日志/审计。
* PR2: 补练上下文入口
  * TrainingJourney AI Coach `next_action` 增加可展示上下文：来源、目标小单元、薄弱能力、推荐章节、通过标准。
  * 小测未达标、商务技巧工作台入口带上 `unit_key` 或后端可解析上下文。
  * 直达 AI Coach URL 时仍能从 active journey/session 恢复上下文。
* PR3: 前端工作台改版
  * AI Coach 首屏改为“补练任务卡 + 当前训练卡 + 反馈/下一步卡”。
  * 聊天历史降级为辅助解释区，可折叠；底部只保留状态驱动的主操作和少量次操作。
  * 隐藏或折叠 reasoning，不把它称为核心训练内容。
* PR4: 证据与管理可见性
  * AI 补练结果进入 TrainingJourney outcome / 训练记录详情 / readiness dossier。
  * 管理端能看到薄弱能力、补练次数、达标/待复核、失败原因分类。
* PR5: 质量门禁
  * 单测：next action 决策、动作契约、失败兜底、progress 计算。
  * 前端测试：状态卡、主操作、失败恢复、小测未达标入口。
  * 集成或 E2E：小测未达标 -> AI 补练 -> 评分 -> 达标/未达标 -> 返回路径。

## Decision (ADR-lite)

**Context**: AI 补练可以同时承接文章、小测、录音和真实对练准入，但一次性做全路径会扩大 TrainingJourney、录音评分和管理端复核的改动面。

**Decision**: MVP 先做商务技巧小单元 AI 补练工作台，优先覆盖文章/小测后的补练闭环；录音/PPT 讲解薄弱项接入暂不进入本轮。

**Consequences**: 该决策能最快解决当前“没方向、点了失败、失败后不知道下一步”的问题，并复用现有 BusinessEtiquetteAiCoachProgress 与小测能力点配置。代价是录音评分后的个性化补练暂时仍不能直接进入 AI 补练上下文，需要后续单独设计。

### Decision: AI 补练入口任务优先级

**Context**: 同一个商务技巧小单元可能处于未读完、读完未小测、小测未通过、AI 补练进行中、已达标等不同状态。如果入口只恢复 session 或只给自由聊天，学员不知道为什么来。

**Decision**: 采用状态驱动优先。小测未通过时，按未通过小单元和薄弱能力点进入补练；文章读完但未小测时，进入当前小单元基础练习；已达标时，主操作指向返回新人路径或继续下一单元。

**Consequences**: 该方案最贴合新人路径闭环，减少用户自我解释成本。需要后端在 TrainingJourney/AI Coach 入口上下文中提供当前小单元、来源、推荐能力点、达标状态和主操作，前端只渲染，不自行推断。

### Decision: AI 题卡生成失败兜底

**Context**: 当前用户最明显的问题是点击后生成失败，系统只能返回恢复 prompt，训练无法稳定推进。纯重试不能保证成功，继续让用户选择“重试/换主题/总结”会把系统问题转嫁给学员。

**Decision**: MVP 采用“自动重试 + 固定模板题兜底”。LLM 首次生成失败后自动重试；仍失败时后端按当前小单元、能力点和允许题卡类型生成一张合法的确定性保底训练卡。

**Consequences**: 训练主流程更稳定，失败不再直接打断用户。代价是需要维护一套保底题卡模板和答案/评分规则，并确保模板题同样进入 UI event、评分、进度和审计链路。

### Decision: 达标标准展示

**Context**: AI 补练既要给学员透明标准，又不能让体验变成普通考试刷分。后端已有 mastery level、threshold、passed、ready_for_field 等字段。

**Decision**: 学员侧以等级语言为主，分数为辅。任务卡主文案使用“基础掌握 / 可上场 / 待人工复盘”等能力语言，辅助展示配置化达标线，例如“本轮达标线 70 分”。

**Consequences**: 新人更容易理解训练目标，培训负责人仍能追踪客观阈值。需要前端 presenter 统一映射，不得直接展示内部字段或裸枚举。

### Decision: 达标后的 session 行为

**Context**: 当前 AI 教练容易进入“继续下一题”的无尽循环，用户不知道什么时候完成。新人路径需要明确完成态和返回路径。

**Decision**: 达标后自动切到完成态，主操作返回新人路径或继续下一单元，次操作保留“再练一题”。系统不再默认自动推下一题。

**Consequences**: 路径闭环更清楚，避免刷题疲劳。需要后端/前端按 `BusinessEtiquetteAiCoachProgress.status in {"mastered","ready"}` 切换主操作，并避免 `continue_drill` 成为达标后的默认推荐。

### Decision: 工作台首屏信息架构

**Context**: 当前页面把状态、对话、快捷操作和训练卡混在一起，用户一进来先看到系统状态和聊天，而不是“我要做什么”。

**Decision**: 采用“任务卡置顶 + 训练卡居中 + 聊天折叠”。任务卡承载来源、目标、标准、状态、主操作；训练卡/反馈卡作为当前主交互；聊天历史降级为辅助解释或复盘证据。

**Consequences**: 用户路径更清楚，视觉重心从聊天迁移到训练动作。需要重构 `coach-conversation.tsx` 的布局与组件分层，但可以复用现有 `CoachMessageList`、`GenerativeCard`、`ProgressPanel` 等组件能力。

## Final Understanding

**Goal**: 把商务技巧 AI 教练升级为新人路径内的商务技巧小单元 AI 补练工作台，优先解决文章/小测后的补练闭环、失败可恢复和达标后返回路径。

**Requirements**:

* MVP 只覆盖商务技巧小单元，不接入录音/PPT 薄弱项。
* 入口采用状态驱动优先：小测未通过补薄弱点，文章读完未小测做基础练习，已达标返回路径。
* AI 生成失败采用自动重试 + 固定模板题兜底。
* 达标标准采用等级语言为主、分数为辅。
* 达标后进入完成态，默认不继续推题。
* 首屏采用任务卡置顶、训练卡居中、聊天折叠。
* 结果进入 TrainingJourney / 训练记录 / readiness dossier 的证据链。

**Acceptance Criteria**:

* [ ] 首屏能解释“为什么来、练什么、通过标准、下一步”。
* [ ] 小测未通过入口能展示目标小单元和薄弱能力点。
* [ ] 文章读完未小测能进入基础练习。
* [ ] 达标后主操作回到新人路径或继续下一单元。
* [ ] LLM 失败后不会中断训练，能重试并兜底生成合法题卡。
* [ ] `continue_drill` 等动作契约和实现一致。
* [ ] 用户界面不展示内部错误码、Prompt、answer key、scoring rubric。

**Technical Approach**:

* 后端先统一动作契约和失败兜底，再扩展 AI Coach 入口上下文。
* 前端将 AI Coach 页重组为补练工作台，保留聊天但降级为辅助区。
* 进度与达标状态优先使用 `BusinessEtiquetteAiCoachProgress` 和 TrainingJourney，不在前端自行推断。

**Implementation Plan (Small PRs)**:

* PR1: 后端动作契约与兜底题卡
* PR2: TrainingJourney / AI Coach 入口上下文
* PR3: AI 补练工作台前端改版
* PR4: 证据沉淀到训练记录 / readiness dossier
* PR5: 单测、前端测试、E2E 和文档更新

## Not-Yet-Considered Points To Resolve

* 补练来源优先级：同一人同时有小测未达标和录音低分时，AI Coach 默认补哪个？
* 通过标准文案：向学员展示“70 分”还是“达到基础掌握/可上场”？
* 自动兜底题来源：从已发布题库抽题、模板生成题，还是继续依赖 LLM 重试？
* session 生命周期：达标后是否自动结束 session，还是保留继续巩固入口？
* 多次失败策略：连续几次生成失败后进入人工复核/固定题库/配置异常？
* 旧 followup prompt 消费机制：用户点击后是否应隐藏旧 prompt，避免旧选项反复可点？
* 管理端解释：负责人看到的是聊天记录摘要，还是结构化证据卡？
* 指标：成功标准是生成成功率、补练完成率、达标率提升、人工介入减少，还是路径继续率？

## Technical Notes

* Task dir: `.trellis/tasks/07-08-ai-coach-remediation-upgrade`
* CodeGraph used before grep/file reads because repo has `.codegraph/`.
* Relevant backend:
  * `backend/src/sales_trainer/services/business_etiquette_ai_coach_progress_service.py`
  * `backend/src/sales_trainer/services/training_journey_service.py`
  * `backend/src/sales_trainer/services/ai_coach_chat_auto_advance.py`
  * `backend/src/sales_trainer/services/ai_coach_chat_next_action_generation.py`
  * `backend/src/sales_trainer/services/ai_coach_chat_stream_service.py`
* Relevant frontend:
  * `web/src/app/(dashboard)/sales-trainer/business-skills/coach/page.tsx`
  * `web/src/app/(dashboard)/sales-trainer/business-skills/coach/coach-conversation.tsx`
  * `web/src/app/(dashboard)/sales-trainer/business-skills/use-business-skills-workbench.ts`
  * `web/src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.tsx`
  * `web/src/app/(dashboard)/sales-trainer/next-step-panel.tsx`
* Relevant docs:
  * `docs/adr/2026-06-27-newcomer-training-closed-loop.md`
  * `docs/product/newcomer-training-v0.9-usable-loop.md`
  * `docs/api-contract/sales-trainer.md`

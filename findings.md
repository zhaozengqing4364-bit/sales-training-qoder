# Findings

## 2026-03-17

- 当前本地分支为 `修复知识库`。
- 本地已有未提交改动，主要是 StepFun 默认模型切换到 `step-audio-r1.1`。
- 已存在汇总文档 `docs/plans/2026-03-17-stepfun-r1.1-and-voice-runtime-fixes.md`，其中把本轮需要实现的点分成了已实施和待实施。
- 需要重点查看的代码入口至少包括：
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `backend/src/sales_bot/services/voice_instruction_compiler.py`
  - `backend/src/common/knowledge/kb_lock_guard.py`
  - `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
  - `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
  - 相关前端页面与管理 API
- 现状判断：
  - StepFun Realtime 主链路和 PPT Realtime 适配层都已存在。
  - KB 强制模式当前是“硬阻塞”语义，超时、未命中、转写未完成都会直接拦截生成。
  - `voice_instruction_compiler` 目前没有“每轮最多一个主问题”的硬约束。
  - PPT 会话结束后的最终评分仍主要依赖 `logic_score / accuracy_score / completeness_score` 三维粗粒度分数，和目标六维报告不匹配。
  - Hybrid Retrieval 已经实现，检索增强真正缺的是 rerank / 策略配置，不需要重做 Hybrid。
- 数据结构判断：
  - `VoiceRuntimeProfile.tool_policy` 和 `AgentVoicePolicy.tool_policy_override` 适合承载 KB 行为模式、提问约束、词典配置、检索 rerank 开关。
  - `ConversationMessage` 目前缺少适合持久化 transcript 归一化元数据的字段，如需保存 raw/normalized 差异，建议补充 JSON 元数据列。

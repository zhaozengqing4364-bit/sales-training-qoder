# M008: 检索事实链收口 — Research

**Date:** 2026-03-28

## Summary

M008 要解决的核心问题是：当前系统已经有了 `runtime_metrics.knowledge_retrieval` 的实时检索计数器、`/knowledge-check` 的诊断输出和 report 页上简单的命中/未命中状态卡片，但这三件事各说各话——runtime metrics 只有聚合数字（attempt_count、hit_query_count），knowledge-check 只读 voice_policy_snapshot 里的实时计数器给出 status/summary，而 canonical report 的 `SessionEvidenceService.build_projection()` 完全不读 runtime metrics，也不在 `effectiveness_snapshot` 里留下任何检索事实。

具体来说：

1. **没有 retrieval ledger**：当前只有运行时聚合计数器（attempt_count, hit_query_count, total_results, last_query, recent_queries），没有"第 N 轮发生了检索、查询了什么、命中了什么片段、为什么 miss"的结构化事实记录。
2. **report 与 knowledge-check 互不对照**：knowledge-check 读 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` 给出 status，report 的 `SessionEvidenceService.build_projection()` 根本不碰 `voice_policy_snapshot`，所以 report 里没有检索事实线，用户在 report 上看到的结论和 knowledge-check 看到的检索状态之间没有因果链。
3. **`used_in_reasoning` 目前无法可靠推导**：当前系统只记录检索是否发生和是否命中，不记录命中的片段是否进入了 LLM 的后续推理。M008 应先不虚构"被使用"，只把检索事实做硬。

## Recommendation

**三段式递进：先定义 retrieval ledger 并在 runtime 落库，再让 knowledge-check 和 report 共享同一条 ledger，最后在 report 前端展示检索事实。**

这个顺序的原因是：
- Retrieval ledger 是所有下游消费的前提。没有它，knowledge-check 和 report 继续各说各话。
- Ledger 不应该重新发明：当前 `runtime_metrics.knowledge_retrieval` 已经有 `recent_queries` 和逐次计数器，但它只存聚合值而不是逐次记录。M008 不需要把每次检索的完整 payload 暴露成长期 contract，只需要一个最小的、稳定的事实摘要。
- Report 消费 retrieval ledger 时必须通过 `SessionEvidenceService`，不能绕开它另造一个 retrieval truth source——这是 M008 最重要的技术约束。

## Implementation Landscape

### Key Files

- `backend/src/common/conversation/runtime_diagnostics.py` — 当前 knowledge-check 的 diagnostics authority，读取 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` 并输出 status/summary/kb_lock/claim_truth。**M008 需要扩展它来读取 retrieval ledger 并输出。**
- `backend/src/common/conversation/session_evidence.py` — report/replay 的核心 authority seam。当前 `build_projection()` 完全不读 `voice_policy_snapshot.runtime_metrics`。**M008 需要在 `build_projection()` 或 `ensure_effectiveness_snapshot()` 中把 retrieval ledger 挂到 `effectiveness_snapshot` 上。**
- `backend/src/common/api/practice.py` — knowledge-check 路由（`/practice/sessions/{session_id}/knowledge-check`）和 canonical report 路由都在这里。**M008 不需要改路由结构，只需确保两个路由消费同一个 retrieval ledger。**
- `backend/src/sales_bot/websocket/components/stepfun_helpers.py` — `ensure_knowledge_runtime_metrics()` 和 `update_knowledge_runtime_metrics()` 定义了当前 runtime metrics 的 schema。**M008 需要扩展它在每次检索时写入 ledger entry 而不只是聚合计数器。**
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — 实际执行检索的入口，每次检索后调用 `record_metric`。**M008 需要让 `record_metric` 同时写入 ledger entry。**
- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` — `apply_knowledge_runtime_metric()` 和 `persist_runtime_metrics_to_session()` 负责把 runtime metrics 持久化到 `voice_policy_snapshot`。**M008 需要扩展持久化路径把 ledger 也写入。**
- `web/src/lib/api/types.ts` — 前端 `KnowledgeCheckDiagnostics` 类型定义。**M008 需要扩展它包含 retrieval ledger 摘要。**
- `web/src/lib/session-evidence.ts` — 前端共享 evidence wording helper。**M008 需要扩展它来翻译 retrieval fact 文案。**
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前 report 页已有 knowledge-check 卡片（只显示 status/summary/计数器）。**M008 需要扩展它展示 retrieval fact 详情。**
- `backend/tests/integration/test_knowledge_flow.py` — 当前最接近真实 knowledge binding / status proof 的 integration base。**M008 需要扩展它验证 retrieval ledger。**
- `backend/tests/contract/test_practice_evidence_contract.py` — report/replay/knowledge-check shared contract。**M008 需要扩展它验证 report 和 knowledge-check 共享同一条 retrieval truth。**
- `backend/tests/unit/test_session_evidence_service.py` — SessionEvidenceService 单测。**M008 需要扩展验证 projection 包含 retrieval ledger。**

### Build Order

1. **S01: 定义 retrieval ledger 并在 runtime 落库** — 这是最基础的一步。定义最小 ledger entry schema（turn_number, query, result_count, status, retrieval_mode, kb_ids, error, timestamp），让 `record_metric` 在每次检索时写入 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.retrieval_ledger` 列表。这一步不改变任何公开 contract，只扩展内部 schema。**R022 的核心。**

2. **S02: knowledge-check 和 report 共享 retrieval ledger** — 扩展 `build_session_runtime_diagnostics()` 读取 retrieval ledger 并输出结构化事实摘要；扩展 `SessionEvidenceService.build_projection()` 把 retrieval ledger 挂到 `effectiveness_snapshot.retrieval_facts` 上；确保两个路由对同一个 session 输出一致的检索事实。**R023 的核心。**

3. **S03: report 前端展示检索事实 + 集成验证** — 扩展 report 页的 knowledge-check 卡片展示 retrieval fact 详情（而不只是 status/计数器）；扩展 `session-evidence.ts` 翻译 retrieval fact 文案；用一条真实 session 证明 retrieval ledger 在 knowledge-check 和 report 上互相对照。**收口 proof。**

### Verification Approach

- **S01 验证**：单元测试验证 `update_knowledge_runtime_metrics()` 在多次检索后正确累积 ledger entries；集成测试验证真实检索场景下 ledger 落库到 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.retrieval_ledger`。
- **S02 验证**：contract 测试验证同一条 session 的 knowledge-check 和 report 都能读出相同的 retrieval ledger 摘要；`SessionEvidenceService` 单测验证 projection 包含 `retrieval_facts`。
- **S03 验证**：browser 验证 report 页展示检索事实；focused web test 验证前端 knowledge-check 卡片渲染 retrieval fact 文案。

## Constraints

- **必须继续沿 `SessionEvidenceService` 作为 report truth authority**，不新增第二条 retrieval report source。retrieval ledger 只能作为 `SessionEvidenceService.build_projection()` 的输入，不能绕开它。
- **retrieval ledger 必须小而稳定**，不能把 provider-specific 的原始检索 payload（如 ChromaDB raw results、embedding vectors）暴露成长期 contract。ledger entry 应只包含 query、result_count、status、retrieval_mode、kb_ids、error、timestamp。
- **不改变现有 `voice_policy_snapshot` 的写入时机**：ledger 随 runtime metrics 一起持久化到 `voice_policy_snapshot`，不新增独立的持久化路径。
- **`used_in_reasoning` 当前不可靠推导**：M008 先不虚构"命中的片段被 LLM 使用了"，只先把检索事实做硬。这一条留给后续 M010 做报告出处链时再处理。
- **必须继续沿现有 shipped route family**：`/knowledge-check` 和 canonical `/report` 是唯一入口，不新开 debug/audit route。

## Common Pitfalls

- **不要把 retrieval ledger 做成 audit console**：M008 的目标是让现有 route family 说清楚检索事实，不是造一个新的 audit/诊断后台。如果发现自己在建新页面或新路由，已经偏了。
- **不要让 `SessionEvidenceService` 直接读 runtime handler 的 live state**：completed session 的 retrieval ledger 只能从 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.retrieval_ledger` 读，不能从 live handler 读。live handler 的 state 只在 session 进行中有效。
- **不要让 retrieval ledger 里的 entry 数量无限增长**：应该设上限（如最近 20 条），超过时丢弃最旧的。runtime metrics 已经有 `recent_queries: [:5]` 的先例。
- **不要把 retrieval ledger 和 claim_truth 混为一谈**：claim_truth 回答的是"主张是否有证据支撑"，retrieval ledger 回答的是"有没有检索、命中了什么"。两者相关但不等同。
- **不要在 `build_projection()` 里重复计算 runtime diagnostics**：projection 应该直接读 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.retrieval_ledger`，而不是重新跑一遍 `build_session_runtime_diagnostics()`。

## Open Risks

- **`voice_policy_snapshot` JSON 大小增长**：当前 `runtime_metrics.knowledge_retrieval` 已经有不少字段，加上 retrieval ledger 列表后 JSON 会进一步膨胀。如果未来检索频率很高（如每轮都检索），可能需要考虑把 ledger 做成独立的关联表而不是嵌在 snapshot JSON 里。M008 先用 JSON 列 + 条目上限控制。
- **classic voice mode 可能不走 StepFun 的 `record_metric` 路径**：当前检索事实主要在 StepFun runtime 下记录，classic voice mode 的 `CapabilityProcessor` 走的是 `KnowledgeRetrievalCapability`。如果 classic mode 也有检索，需要确认 `record_metric` 路径是否覆盖。初步判断是 classic mode 的检索也经过 `CapabilityProcessor` → `knowledge_retrieval`，但需要 S01 验证。

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Retrieval metric recording | `stepfun_helpers.update_knowledge_runtime_metrics()` + `stepfun_runtime_metrics_helpers.apply_knowledge_runtime_metric()` | 已经有完整的 metric 更新和持久化链路，M008 只需扩展它写入 ledger entry |
| Runtime diagnostics building | `runtime_diagnostics.build_session_runtime_diagnostics()` | 已经读 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval`，M008 只需扩展它读 ledger |
| Evidence projection | `SessionEvidenceService.build_projection()` | 已经是 report/replay 的 authority seam，M008 只需把 retrieval ledger 挂进去 |
| Frontend knowledge-check card | Report page already has knowledge-check section | M008 只需扩展现有卡片，不造新的 |
| Frontend evidence wording | `web/src/lib/session-evidence.ts` | 已经是共享 wording seam，M008 只需扩展 |

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| SQLAlchemy ORM | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | installed |
| FastAPI | `fastapi-python` (already installed) | already available |
| React/Next.js | `react-best-practices` (already installed) | already available |

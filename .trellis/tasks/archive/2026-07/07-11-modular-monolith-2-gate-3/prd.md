# 模块化单体 2.0 Gate 3：Provider Port 与 Grounding 单一权威

## Goal

在不改变现有 REST、WebSocket、close code、二进制音频、权限、RuntimeGate、冻结
snapshot、KB fail-closed、epoch、评分、报告和训练路径合同的前提下，把 StepFun raw
WebSocket/I/O/event codec 收入中立 `RealtimeProviderPort` Adapter，并把 realtime
Grounding 的 prepare/retrieve/decide/overlay/block、结果缓存、timeout、diagnostics 与 metrics
收口为一个中立 Deep Module。StepFun 继续是唯一生产 Provider；Fake Provider 只用于本地
合同测试。

## What I already know

- Gate 0A–2 已闭环，Gate 2 最终 canonical gate 为 backend 2903 passed、Vitest 1329
  passed、selected backend 598 passed、changed coverage 91.34%，可作为 Gate 3 行为基线。
- 权威设计、ADR 和路线图已经批准；当前 Goal 要求自动连续执行，不再询问用户。
- 现有 `StepFunTransport` 已封装 connect/send/close/health/backpressure，但仍返回 raw
  WebSocket-like `Any`，receive/JSON decode 和事件路由仍在 Sales Mixin。
- `GroundingDecisionPipeline` 与 `StepFunToolExecutionModule` 各持有一个 realtime retrieval
  result cache；prefetch 可形成 Grounding cache -> Tool cache -> actual retrieval 的双层路径。
- KnowledgeService/Chroma/embedding 的内部缓存属于 Knowledge Adapter 基础设施，不是本 Gate
  要删除的 realtime orchestration cache。
- Presentation Engine 的 GroundingState 当前是显式审计状态；真正的 prepare/retrieve/decide
  仍由 Sales-owned Pipeline 和 Mixin 私有字段决定。

## Assumptions and resolved decisions

- Gate 3 同时迁移 Sales 与 Presentation 共用的 StepFun compatibility runtime；不新增生产
  Provider，不调用收费 API。
- I/O 继续由 WebSocket Adapter 驱动；Engine 保持同步、provider-neutral 的 session state
  authority，不持有 FastAPI WebSocket 或 Provider credential。Provider Port 通过组合注入，
  Fake/StepFun 可替换而无需改 Engine。
- 使用两个 server-only、session-construction-time 冻结的 rollout：
  `REALTIME_PROVIDER_PORT_ENABLED=true` 与 `REALTIME_GROUNDING_MODULE_ENABLED=true`。任一 flag
  关闭时只选择对应 Legacy path；客户端不能覆盖，同一 session 不 shadow/double execute。
- Provider Port 的 wire boundary 使用 closed command/event/capability/error-reason vocabulary；raw
  StepFun JSON 只能存在于 StepFun codec/adapter 内。未知事件映射为 safe `unknown` 并保持现有
  ignore 语义，非法 JSON/shape 映射为 typed protocol error。
- Grounding 的唯一 realtime cache key 使用 normalized query、top_k、metadata filter、冻结
  `instruction_contract_hash` 和排序后的 `knowledge_base_ids` 生成 SHA-256；仓库不存在独立
  knowledge revision 字段，禁止在设计中虚构它。
- 新 cache 为 per-session、TTL + max-entry bounded、deep-copy safe、non-empty successful-result
  only，并对相同 key 做 single-flight；owner timeout/error/cancel/invalid/no-hit 不形成
  negative cache。sequential no-hit prefetch/tool 因不缓存而允许执行两次检索。
- `common.knowledge.kb_lock_guard` 的 fail-closed 文案、answerability 和 threshold 语义保持
  compatibility authority；Gate 3 只把编排、状态、cache 和 mapper 中立化，不重写知识规则。
- `presentation_coach -> sales_bot` 整条临时边还混有 message persistence、prompt、Roleplay 和
  报告 helper；
  本 Gate 只移除 Provider/Grounding 所有权，不在实际 import 仍存在时伪删 policy target。
  最终物理边退役由 Gate 4 所有权迁移和 Gate 6 compatibility cleanup 完成。

## Functional requirements

### Provider Port

- 建立 `RealtimeProviderCapabilities`、`RealtimeProviderSessionConfig`、`ProviderCommand`、
  `ProviderEvent`、`ProviderErrorCategory`、`RealtimeProviderPort`。
- capability 至少表达 text/audio、input transcription、function tools、server VAD、health、
  reconnect 与 audio format；不支持的已请求能力在 connect 前 fail closed。
- `connect(session_config)` 是 session configure 的唯一所有者并原子发送一次
  `session.update`；不存在第二个 `CONFIGURE` command。
- command 至少覆盖 append/commit/clear audio、create/cancel response、conversation item 和
  tool output；event 至少覆盖 session、input-audio committed、transcription、speech、response
  text/audio、assistant transcript final、thinking delta/done、function call、done、error、unknown。
- canonical event 公共字段覆盖 event/turn/request/response/stream/call ID、timestamp/duration；
  conversation item、response.done function outputs 和各 event data 使用逐-kind closed schema。
- error 同时具有 closed category 与 reason，能无损区分 authentication/forbidden/quota/
  rate-limit、ASR fallback、voice unavailable、idle-timeout recoverable、protocol invalid、
  unavailable/disconnected/backpressure；delivery 层对已识别 reason 继续映射现有用户文案。
  UNKNOWN 原始 Provider message 不再透传，固定为“Realtime 服务返回错误”；这是本 Gate 唯一
  批准的外部行为差异和安全修复，Legacy Provider flag=false 可临时回滚旧行为。
- StepFun codec 独占 raw JSON encode/decode；Port 外只暴露 validated canonical fields 和安全
  raw-type label，不暴露 token、URL query secret、raw error text或未验证任意 dict。
- StepFun Adapter 组合现有 transport 的 connect/send/health/backpressure/close，保持 endpoint、
  auth header、session.update、send failure 与 HTTP status 用户文案合同。
- Fake Provider 与 StepFun Adapter 运行同一 Port contract suite；Fake 可以驱动 Golden
  Conversation command/event 序列而不修改 Engine。
- production shared handler 默认经 Port connect/send/receive/health/close；flag false 原子选择
  legacy transport。外部前端事件顺序、持久化、tool follow-up、reconnect epoch 不变。

### Grounding Module

- 中立 Module 拥有 closed `GroundingOutcome/GroundingMode/GroundingCacheDisposition`、
  `GroundingRequest`、`GroundingRetrievalResult`、`GroundingCitation`、
  `GroundingEvidence`、`GroundingDecisionResult`、`GroundingDiagnostics`、
  `GroundingCacheStats`、`GroundingRetrieverPort` 和默认生产路径唯一 cache。
- request 必须携带 decision id、query、frozen policy hash、knowledge scope、top_k/filter；非法或
  缺失 frozen scope fail closed，不回退 latest config。
- `common.knowledge.kb_lock_guard.evaluate_kb_lock_decision` 接受可选唯一 retriever seam；默认
  调用保持现有行为，Gate 3 Module 注入 cache-backed retriever，使 strict/prefetch/tool 的
  cacheable success 共享同一底层检索，而不丢 minimum-score/keyword/legacy auto-lock 语义。
- prepare/retrieve/decide/overlay/block/output guard 通过一个 Module 表面完成；handler 兼容字段
  只能是该结果的 projection，不得形成第二个决策状态。
- strict KB lock、unbound、not-ready、timeout、error、empty、partial、grounded 的现有结果、
  用户文案与 generation allow/block 语义保持不变。
- 默认路径的 strict/prefetch/Provider tool call 对同一 frozen、non-empty successful request
  共用唯一 cache/single-flight；从 `StepFunToolExecutionModule` 删除 result-cache ownership，
  Tool Module 只保留 call-id/turn dedupe、routing、execution 与 tool response。flag false 使用
  命名 `LegacyRealtimeGroundingAdapter` + `LegacyToolResultCache`，默认路径绝不构造，Gate 6 删除。
- timeout、fallback、diagnostics、cache counters、metric outcome 使用 closed mapper；兼容
  runtime diagnostics 的既有顶层字段，Engine 只接收 allowlisted/redacted schema。Module 的
  mode 覆盖 Engine 既有 closed vocabulary，包括 `grounded/blocked/degraded/skipped` 以及
  `kb_lock/unrestricted/not_applicable`。Engine diagnostics 保持 schema v1：`duration_ms` 映射为
  `latency_ms`，`hit/shared` 映射为 `cache_hit=true`，`miss/bypass` 映射为
  `cache_hit=false`，aggregate 使用既有 hit/miss/count 字段；精确 cache disposition 只留在
  decision 与 legacy compatibility diagnostics，不新增 Engine 字段。
- Engine/frontend/log/new diagnostics/metrics 不新增或传播 raw query、token、prompt、transcript
  或 provider error。为保持 frozen snapshot 兼容，既有 durable `last_query/recent_queries`
  writer 暂保留且仍是唯一 metric mutation/persistence 点。Module/cache 不再次调用 durable
  sink；cache disposition/counters 进入 decision/legacy compatibility diagnostics，Engine 仅接收
  上述 v1 closed 投影，不另写 snapshot。

## State and concurrency invariants

- 默认路径每个 session 恰好一个 selected Provider path、一个 Provider connection、一个
  Grounding Module、一个 realtime result cache、一个 tool execution side effect 和一个
  persistence writer。flag=false 的命名 Legacy rollback 可保留既有双 cache 到 Gate 6，但
  默认路径绝不构造或读写它们。
- Provider event 必须绑定当前 connection epoch；stale epoch、stale request/response/stream/call
  id 继续 fail closed，不能污染 active turn。
- Provider send backpressure 的 drop/accepted 语义与 Gate 2 binary audio evidence invariant 一致。
- cache lookup/store 在单个 session event loop 内可预测；并发同 key 共享一个内部 owner task。
  request timeout 在 owner 内执行；一个 waiter cancel 不取消 owner，owner 成功可正常缓存；
  owner timeout/cancel/error 不缓存。session close 调用 async `close()`，cancel + await 全部 owner，
  禁止 orphan task、late cache、late metric 或 late decision projection。
- cache entry 超时或超过 max entries 时确定性淘汰；调用方拿到 deep copy，不能修改 authority。
- cache 只缓存 validated non-empty successful retrieval；error/timeout/cancel/invalid/no-hit 不缓存。
- Grounding resolution 是 immutable result；overlay、blocked response、output guard 和 Engine
  diagnostics 均从同一 result projection，禁止各自重新判断 answerability。

## Rollout and rollback

- `REALTIME_PROVIDER_PORT_ENABLED=true`：StepFunProviderAdapter + StepFunEventCodec；`false`：
  当前 StepFunTransport/raw receive compatibility path。
- `REALTIME_GROUNDING_MODULE_ENABLED=true`：中立 Grounding Module + 单 cache；`false`：命名
  Legacy pipeline/tool-cache compatibility path。
- 两个 flag 在 handler 构造时各读取一次，并进入 sanitized diagnostics；运行中变化不影响已建
  session。
- flag unset 使用 default true；`true/1/yes/on` 与 `false/0/no/off` 大小写/空格归一；未知值
  fail-safe 选择 Legacy false 并留下不含原值的 operator warning。
- Presentation 仍保留 `PRESENTATION_REALTIME_ENGINE_ENABLED=false` façade 回滚；完整回滚需三个
  flag 均 false。Sales 2x2=4、Presentation 2x2x2=8，共 12 种选择不得双构造、双连上游、
  双检索、双指标或双写。
- 回滚不修改 frozen snapshot、不重算历史 Evidence/score/report；不删除 Legacy path 直到
  Gate 6。

## Acceptance Criteria

- [x] Versioned machine-readable Provider command/event/capability/error inventory 与 Golden
      fixtures 覆盖现有 StepFun production surface。
- [x] `RealtimeProviderPort`、StepFun Adapter/Codec 与 Fake Provider contract suite 完成；Fake
      不需修改 Engine 即可运行。
- [x] Production shared handler 默认通过 Provider Port，flag false 回滚 raw transport；Sales 与
      Presentation differential 保持 wire、持久化、reconnect、tool follow-up 和报告单 writer。
- [x] Provider capability mismatch、invalid JSON/shape、typed error、unknown event、health、
      backpressure、disconnect/reconnect/stale epoch 均有 fail-closed 测试。
- [x] Grounding prepare/retrieve/decide/overlay/block/output guard 收入中立 Module，compatibility
      私有字段只做 projection。
- [x] prefetch 与 Provider tool call 共用一个 bounded TTL/single-flight cache；ToolExecution 的
      result cache 与 cache diagnostics ownership 从默认路径移除；命名 Legacy cache 仅在
      flag=false 时构造并保留到 Gate 6。
- [x] cache key 包含 frozen policy hash + sorted KB scope + query/top_k/filter；deep copy、TTL、
      max entries、single-flight、owner timeout/cancel、session close、late-result discard 以及
      error/invalid/no-hit 不缓存均有测试。
- [x] strict KB、无 KB、not-ready、timeout、error、empty、partial、grounded 的行为、文案、
      diagnostics 和 metrics 与 Gate 2 基线一致。
- [x] Engine GroundingState、legacy diagnostics 与 durable metrics 都由同一 decision result 映射；
      Engine/frontend/log/new surfaces 无 raw query/token/prompt/transcript/provider error，既有
      durable query fields 仅由兼容 single writer 保留。
- [x] architecture policy 无新增未治理边、SCC 不扩大；只按实际消失 import 收缩 exception。
- [x] Gate 2 Golden differential、Sales reconnect/status、Presentation、local Provider E2E、完整
      canonical gate 全绿，未新增 skip/xfail/retry/永久排除。

## Completion Evidence

- Whole-branch Brooks Architecture Audit：100/100，Critical/Important finding=0。
- Independent Trellis check：finding=0；context 16 implement / 15 check entries 全部有效。
- Focused Gate 3 matrix：812 passed；Ruff、architecture policy、mypy 635 source files 全绿。
- Final clean-start canonical gate：backend `3271 passed, 1 skipped`；Vitest 209 files /
  `1329 passed, 6 skipped`；Playwright `3/9/11/2/1 passed`；selected backend
  `598 passed, 21 skipped`；changed coverage 3441/3868（88.96%）；final
  `Critical quality gate passed`。
- 首轮 canonical 暴露陈旧 `.next/dev` 复用导致外部 `NEXT_PUBLIC_*` 污染与 ENOSPC；TDD 修复
  `scripts/dev-smoke-up.sh` 后，三个原失败 Playwright 用例 3 passed，完整 gate 从头自然通过。

## Definition of Done

- 实现、TDD、feature flags、diagnostics、Trellis executable spec、ADR/architecture/design/roadmap
  和实际 import graph 一致。
- CodeGraph impact/affected 已用于测试选择；每个 implementation slice 经过独立 spec + quality
  review，whole-branch review Critical/Important finding=0。
- `critical-quality-gate.sh` 从 clean start 对所有非真实收费 Provider phase 自然 exit 0。
- Trellis check finding=0，Acceptance Criteria 全勾，任务归档并记录 journal。
- 工作区只剩已识别的并行 Readiness 用户改动。

## Out of Scope

- 新生产 Provider、真实收费 API、Provider 自动切换或多 Provider shadow traffic。
- Gate 4 Roleplay DTO/hash/freeze/compiler/disclosure/turn-context、Configuration Governance、
  Evaluation Evidence/Scenario ports。
- Gate 5 前端 Locality、Training Journey projection、ORM 物理拆分。
- Gate 6 compatibility shim/legacy flag 删除、整条 Presentation->Sales 边退役和收益复核。
- 数据库 schema、Alembic、微服务、消息中间件或分布式事务。

## Technical Notes

- Authority: `docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`。
- Decision: `docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`。
- Roadmap: `docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`。
- Gate 2 contract: `.trellis/spec/backend/realtime-session-engine.md`。
- Current truth: `research/current-provider-grounding-runtime.md`。
- Chosen contracts: `research/provider-grounding-contract-decisions.md`。
- Detailed implementation: `docs/superpowers/plans/2026-07-11-gate-3-provider-grounding.md`。

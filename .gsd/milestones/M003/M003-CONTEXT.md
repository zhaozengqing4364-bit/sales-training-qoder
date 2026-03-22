# M003: 知识与角色真实性 — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

## Project Description

M003 关注销售训练的“真实业务感”。目标是让 AI 客户不再只是泛泛应答，而是能够基于真实产品资料、价格信息、竞品认知、证据需求与 Persona 设定进行持续追问，逼近真实销售场景。该 milestone 还需要解决“配置了知识库但训练时没真正用上”“Persona 容易崩人设”等问题。

## Why This Milestone

用户明确把“被追问价格 / 竞品 / 证据时不乱”作为关键训练结果。若 AI 客户不能基于真实知识和角色设定持续追问，训练价值会大幅下降。同时仓库中已有知识库与 Persona 绑定能力，但已有审计指出知识调用链存在真实性风险，需要专项收口。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 与会追问价格、竞品、证据的 AI 客户进行更真实的销售对练。
- 在不同 Persona 下体验稳定的人设行为，而不是随机风格漂移。
- 感受到训练问题与公司真实材料、产品价值点和典型异议一致。

### Entry point / environment

- Entry point: 浏览器训练页 `/practice/[sessionId]` 与后台 Agent / Persona / 知识库管理页面
- Environment: 桌面浏览器 + 后端知识检索 / WebSocket 训练运行时
- Live dependencies involved: ChromaDB, 知识库管理 API, Agent / Persona 策略, LLM / Realtime runtime

## Completion Class

- Contract complete means: 知识库绑定、Persona 行为约束与训练时知识使用路径具有明确可验证契约。
- Integration complete means: 管理员配置的知识库与 Persona 会真实影响训练中的追问内容和回复风格。
- Operational complete means: 知识检索失败时有降级路径，Persona 校验失败不会把会话打崩。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 管理端配置的产品资料 / 竞品资料 / Persona 行为策略，会在真实训练中表现出来。
- 用户在价格、竞品、证据等问题上遇到的追问与回复明显比基础模式更贴近真实业务。
- 知识调用链有可诊断证据，能够区分“知识库无答案”和“知识链没被用上”。

## Risks and Unknowns

- 知识库绑定流程可能正确配置但实际不触发检索。
- Persona 行为可能依赖 prompt 过多，出现角色一致性不足。
- 真实知识增强后可能增加响应延迟或不稳定性。

## Existing Codebase / Prior Art

- `backend/src/common/knowledge/*` — 知识库模型、服务与向量存储基础。
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — 现有训练时知识检索辅助路径。
- `backend/src/sales_bot/services/voice_runtime_policy.py` — Agent / Persona / 知识库合并策略。
- `backend/src/agent/models.py` — Agent、Persona 与关联配置模型。
- `docs/knowledge-base-audit-report.md` — 知识链真实性风险与修复方向分析。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R010 — 知识库 + Persona 驱动价格 / 竞品 / 证据类真实追问。
- R003 — 训练围绕真实产品价值而不是背材料。
- R004 — 管理员维护的材料真正参与训练。

## Scope

### In Scope

- 知识库绑定链路与训练时真实使用证明。
- Persona 行为一致性约束与训练时校验。
- 价格 / 竞品 / 证据类追问的真实性增强。
- 知识诊断与失败可见性。

### Out of Scope / Non-Goals

- 外部 CRM / 文档系统直连。
- 大规模知识运营面板和组织级知识治理流程。

## Technical Constraints

- 不能只在后台显示“已绑定知识库”，必须证明训练时实际使用。
- 角色真实性不能完全依赖脆弱 prompt，应有运行时守护或验证路径。
- 知识增强不能明显破坏训练实时性与稳定性。

## Integration Points

- Knowledge base CRUD and ingestion pipeline.
- Agent / Persona configuration and runtime policy resolution.
- Sales training runtime and StepFun / LLM tool chain.

## Open Questions

- Persona 行为守卫在运行时应采取规则 + LLM 复核，还是先做轻量规则校验 — 当前倾向先从轻量守卫做起。

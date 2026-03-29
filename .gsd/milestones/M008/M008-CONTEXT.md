# M008: 检索事实链收口

**Gathered:** 2026-03-28
**Status:** Ready for planning

## Project Description

M008 的目标不是把知识库页面做得更漂亮，也不是再造一套 audit console，而是把当前训练系统里最容易“看起来像在工作、实际上说不清楚”的那条链先做硬：知识库是否真的进入训练、训练时是否真的发生检索、检索到底命中了什么、失败原因是什么、这些事实是否能被当前 `knowledge-check` 和 canonical report 同时解释清楚。用户已经明确把这件事放在后续工作的第一优先，原因不是想多一个 debug 面，而是当前最不能接受的失败是“报告像真的，但其实既没有真实检索命中，也找不到可解释的证据出处”。

## Why This Milestone

当前系统已经完成了 sales/PPT 训练主链路、report/replay、shared evidence projection 和 realtime coaching 封板，但“知识库在训练里到底有没有真实起作用”仍缺一条可审计、可复查、可跨 surface 对照的事实线。M008 之所以现在做，是因为后续音频审计（M009）和报告出处链（M010）都必须站在一个稳定的 retrieval truth 上；如果这一步不先做，后面不管是录音留痕还是报告出处，都会继续建立在模糊的“好像检索到了/好像知识库用了”的感觉上。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在现有 `/api/v1/practice/sessions/{id}/knowledge-check` 与 `/practice/{sessionId}/report` 路径上看到同一条检索事实线：这场训练有没有检索、检索命中了什么、为什么失败或证据为什么仍弱。
- 对同一条真实训练 session 说清楚：绑定了哪些 knowledge bases、检索发生在什么时候、命中结果是否足以支撑当前报告里的知识支持判断。

### Entry point / environment

- Entry point: `/api/v1/practice/sessions/{id}/knowledge-check`, `/api/v1/practice/sessions/{id}/report`, `/practice/{sessionId}/report`
- Environment: local dev + browser + current FastAPI / Next.js shipped route family
- Live dependencies involved: knowledge base binding in `voice_policy_snapshot`, runtime retrieval metrics, `SessionEvidenceService`, canonical report route

## Completion Class

- Contract complete means: backend contract/integration tests锁定 retrieval ledger shape、knowledge-check retrieval audit 和 report retrieval audit，不再只停在 status 字段。
- Integration complete means: 同一条 session 的 knowledge binding、retrieval facts、knowledge-check 和 canonical report 能互相对照，而不是各说各话。
- Operational complete means: 当 retrieval 未触发、失败、miss 或 hit-but-weak 时，系统仍能给出分层、稳定的事实，而不是静默回退成抽象结论。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 一条真实 knowledge-backed sales session 能回答“这次有没有检索、命中了什么、失败原因是什么”。
- 同一条 session 的 `/knowledge-check` 和 canonical `/report` 对 retrieval truth 的描述一致。
- 不能靠新 debug route、临时日志或仅测试夹具来宣称完成；必须在现有 shipped route family 上完成 proof。

## Risks and Unknowns

- 当前 `runtime_metrics.knowledge_retrieval` 可能过于薄弱或 provider-specific，无法直接成为长期稳定 contract —— 这会影响后续 report audit 和音频 audit 的锚点。
- report 当前已经很成熟，如果 retrieval evidence 以错误方式接进去，可能让 `SessionEvidenceService` 再次出现 route drift —— 这会重新制造“知识检查一套话、报告另一套话”。
- 如果 slice 过早追求“大而全检索解释”，可能会把 M008 做成 audit console，而不是把现有 route family 说清楚 —— 这会偏离用户当前最在意的“假可信报告”问题。

## Existing Codebase / Prior Art

- `backend/src/common/conversation/runtime_diagnostics.py` — 当前 `knowledge-check` 的 runtime diagnostics authority seam，已经读取 `voice_policy_snapshot.runtime_metrics.knowledge_retrieval`。
- `backend/src/common/api/practice.py` — 当前 knowledge-check 和 canonical report 路由都在这里出入口。
- `backend/src/common/conversation/session_evidence.py` — report/replay 的核心 authority seam，M008 不能绕开它再造 retrieval truth source。
- `backend/tests/integration/test_knowledge_flow.py` — 当前最接近真实 knowledge binding / status proof 的 integration base。
- `backend/tests/contract/test_practice_evidence_contract.py` — 当前 report/replay/knowledge-check shared contract 的锁定点。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 用户最终可见的 canonical report page。
- `web/src/lib/session-evidence.ts` — 前端当前用于把 evidence line 翻译成用户可读文案的共享 helper。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R022 — session-level retrieval ledger truth
- R023 — knowledge-check/report retrieval truth parity
- R027 — report conclusion provenance (foundation only; full closure belongs to M010)
- R028 — layered degradation explanation (foundation only; full closure belongs to M010)

## Scope

### In Scope

- 为当前训练 session 定义最小、稳定、可审计的 retrieval ledger。
- 把 retrieval truth 挂到现有 `/knowledge-check` 上，而不是新开 debug route。
- 把 retrieval truth 引入 canonical report 的 shared evidence line。
- 用一条真实 shipped-route session 完成 retrieval truth proof。

### Out of Scope / Non-Goals

- 不做原始音频留痕、OSS 上传、对象存储设计（留给 M009）。
- 不做 report/replay 全量 evidence reference model（留给 M010）。
- 不开新的 audit console、内部审计后台或第二套用户路由。
- 不顺手扩 supervisor workflow、PPT realtime interruption、外部集成。

## Technical Constraints

- 必须继续沿当前 `/practice/{sessionId}` / `/report` / `knowledge-check` route family 收口。
- 必须继续以 `SessionEvidenceService` 作为 report truth authority，不新增第二条 retrieval report source。
- retrieval ledger 必须小而稳定，避免把 provider-specific 原始 payload 直接暴露成长期 contract。

## Integration Points

- `voice_policy_snapshot.knowledge_base_ids` — 当前 session 的 KB binding authority。
- `runtime_metrics.knowledge_retrieval` — 当前 retrieval runtime fact seam。
- `SessionEvidenceService` — report / replay authority seam。
- `web/src/lib/api/types.ts` / `web/src/lib/session-evidence.ts` — 前端 typed contract 与 evidence wording seam。

## Open Questions

- `used_in_reasoning` 是否能从当前事实线上被可靠推导，还是只先做到 hit/miss/failure audit —— 当前倾向是先不虚构“被使用”，只先把检索事实做硬。 

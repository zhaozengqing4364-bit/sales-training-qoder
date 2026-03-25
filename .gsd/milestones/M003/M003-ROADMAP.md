# M003: 知识与角色真实性

**Vision:** 让销售训练里的 AI 客户在当前 admin Persona / knowledge 配置 → session create → voice policy snapshot → realtime retrieval → knowledge-check / report / replay 这条真实业务代码链路上，持续表现出“懂价格、懂 ROI、懂竞品、懂实施风险、要证据”的追问能力，而不是停留在 prompt 文案层。

## Success Criteria

- 管理员在 `web/src/app/admin/personas/[id]/page.tsx` 与 `web/src/app/admin/knowledge/[id]/page.tsx` 的配置，能通过 `backend/src/common/api/practice.py` 创建会话时冻结进 `voice_policy_snapshot`，并继续驱动 `backend/src/agent/services/persona_policy.py`、`backend/src/sales_bot/services/voice_runtime_policy.py` 与 `backend/src/sales_bot/services/voice_instruction_compiler.py`。
- 在当前 learner surfaces `web/src/app/(user)/practice/[sessionId]/page.tsx`、`web/src/app/(user)/practice/[sessionId]/report/page.tsx`、`web/src/app/(user)/practice/[sessionId]/replay/page.tsx` 与 `GET /api/v1/practice/sessions/{id}/knowledge-check` 上，用户和管理员能区分当前 live contract 的 `no_knowledge_base`、`disabled`、`not_triggered`、`kb_not_ready`、`search_failed`、`miss`、`hit`，而不是统一显示“没命中”。
- 同一 Persona 在多轮对话和 reconnect 后，压力方向、追问重点和知识使用边界保持稳定，不会中途切回 generic prompt 聊天模式。
- M003 的所有 slice 都只允许落在当前真实业务代码目录：`backend/src/agent/`、`backend/src/sales_bot/`、`backend/src/common/knowledge/`、`backend/src/common/conversation/`、`backend/src/common/api/`、`web/src/app/admin/`、`web/src/app/(user)/practice/`。Silence / Conda / `.env` / lockfile 等环境工件不单独升格为 milestone，除非未来目标明确变成环境迁移。

## Real Entry Chain

- Admin config surfaces:
  - `web/src/app/admin/personas/[id]/page.tsx`
  - `web/src/app/admin/knowledge/[id]/page.tsx`
- Session authority and snapshot freeze:
  - `backend/src/common/api/practice.py`
  - `backend/src/agent/services/persona_policy.py`
  - `backend/src/sales_bot/services/voice_runtime_policy.py`
  - `backend/src/sales_bot/services/voice_instruction_compiler.py`
- Runtime retrieval and KB-lock truth:
  - `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
  - `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
  - `backend/src/common/knowledge/kb_lock_guard.py`
  - `backend/src/common/conversation/runtime_diagnostics.py`
- Read-side inspection surfaces:
  - `GET /api/v1/practice/sessions/{id}/knowledge-check`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
  - `backend/src/common/conversation/session_evidence.py`

## Acceptance Boundary

- Contract acceptance: focused backend/web verification must assert only on the current routes/modules above and on the live knowledge status vocabulary they already expose.
- Integration acceptance: at least one admin Persona/knowledge change must be traceable through session creation, runtime diagnostics, and report/replay inspection on current product routes.
- Blocking rule: if any required entrypoint cannot be located in runnable code, the work stops and becomes inventory/spike; execution must not continue on assumed or placeholder surfaces.

## Slices

- [ ] **S01: 真实入口 inventory 与 current knowledge 真值线** `risk:high` `depends:[]`
  > After this: The current admin Persona/knowledge → practice/runtime/report chain and live knowledge status vocabulary are locked against real code, so downstream slices cannot invent parallel surfaces or fake status names.

- [ ] **S02: Persona 压力模型 snapshot 化** `risk:high` `depends:[S01]`
  > After this: A Persona edited on the current admin page leaves a frozen pressure model inside `voice_policy_snapshot`, and the current practice runtime restores it consistently across turns and reconnects.

- [ ] **S03: 多轮异议 ledger 与持续施压** `risk:high` `depends:[S01,S02]`
  > After this: On the current practice route, an unresolved price / competitor / proof objection survives topic drift and returns until evidence is provided or the gap is acknowledged.

- [ ] **S04: unsupported claim / evidence truth contract** `risk:medium` `depends:[S02,S03]`
  > After this: The current realtime / report / replay surfaces can distinguish unsupported, evidence-pending, and evidence-backed claims on the same session without inventing a second evaluator.

- [ ] **S05: objection-heavy live proof 与稳定性护栏** `risk:medium` `depends:[S04]`
  > After this: One real admin → practice → report/replay run on current routes proves the system feels like a real customer and keeps degraded states inspectable.

## Boundary Map

### S01 → S02

Produces:
- The confirmed admin Persona/knowledge detail → practice session create → `voice_policy_snapshot` authority chain.
- The current live knowledge status vocabulary on user-visible surfaces: `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, `hit`.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Accepted inspection surfaces for runtime / retrieval truth: practice page, knowledge-check, report, replay, admin Persona detail, and admin knowledge detail.
- The blocker rule that missing entrypoints force inventory/spike instead of execution.

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- A snapshot-backed Persona pressure model that is frozen into the session and survives reconnect.
- Stable runtime Persona context that can be combined with multi-turn objection tracking.

Consumes from S01:
- Locked entry chain and current knowledge status vocabulary.

### S03 → S04

Produces:
- Unresolved objection / promised proof / next proof request facts across turns.
- Cross-turn evidence needed for unsupported-claim / evidence-pending / evidence-backed judgments.

Consumes from S02:
- Persona pressure model.

### S04 → S05

Produces:
- One shared claim-truth contract for realtime, report, and replay on current routes.
- A same-session comparison line for live objection-heavy proof and degraded-state inspection.

Consumes from S03:
- Multi-turn objection ledger.

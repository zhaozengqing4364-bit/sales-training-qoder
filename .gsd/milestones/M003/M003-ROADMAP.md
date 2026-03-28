# M003: 知识与角色真实性

## Vision
让销售训练里的 AI 客户在当前 admin Persona / knowledge 配置 → session create → voice policy snapshot → realtime retrieval → knowledge-check / report / replay 这条真实业务代码链路上，持续表现出“懂价格、懂 ROI、懂竞品、懂实施风险、要证据”的追问能力，而不是停留在 prompt 文案层。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 真实入口 inventory 与 objection query 真值线 | high | — | ✅ | An admin can change Persona/knowledge on current admin pages, create a sales session, and then inspect on current learner/report surfaces whether objection-heavy queries hit, miss, weak-hit, fail, or never traversed the real knowledge path. |
| S02 | Persona 压力模型 snapshot 化 | high | S01 | ✅ | Different Personas bound to the same knowledge base can consistently change pressure direction and follow-up behavior across turns and reconnects, with that model frozen in the session snapshot. |
| S03 | 多轮异议 ledger 与持续施压 | high | S01, S02 | ✅ | An unresolved objection survives topic drift and reconnect, and the AI customer keeps returning to it until evidence is provided or the gap is acknowledged. |
| S04 | unsupported claim / weak evidence truth contract | medium | S02, S03 | ✅ | The same session can show that a claim was unsupported, weakly supported, evidence-pending, or evidence-verified, and that truth line appears on realtime, report, and replay surfaces. |
| S05 | objection-heavy live proof 与稳定性护栏 | medium | S04 | ✅ | At least one real objection-heavy script proves that the system feels like a real customer, leaves inspectable evidence, and still respects current runtime stability/degraded guarantees. |
| S06 | scoring 收口与 replay/highlights 解锁 | high | S05 | ✅ | After this: The same objection-heavy proof chain finalizes `scoring -> completed`, and the accepted replay surface plus sibling highlights endpoint load same-session evidence instead of stopping at `[SESSION_NOT_COMPLETED]`. |

---
id: M003
title: "知识与角色真实性"
status: complete
completed_at: 2026-03-27T13:17:12.848Z
key_decisions:
  - 把 M003 全程锚定在当前 admin Persona/knowledge → practice → knowledge-check/report/replay 的真实业务链路上，不为里程碑另造 acceptance-only surface。
  - 将 Persona 压力、异议持续施压、claim-truth 和 replay/report 结论都绑定到统一 session-evidence / runtime seam 上，而不是为某个消费面单独发明第二套 scorer 或 reader。
  - 保留销售 end-session 立即返回 `status="scoring"` 的 shipped contract，并通过 background finalization + SessionEvidenceService 真值线来解锁 same-session replay/highlights，而不是粗暴放宽 replay gate。
key_files:
  - .gsd/milestones/M003/M003-ROADMAP.md
  - .gsd/milestones/M003/M003-VALIDATION.md
  - .gsd/milestones/M003/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/S02-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/S03-SUMMARY.md
  - .gsd/milestones/M003/slices/S04/S04-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/S05-SUMMARY.md
  - .gsd/milestones/M003/slices/S06/S06-SUMMARY.md
  - backend/src/evaluation/services/report_generation_trigger.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/api/practice.py
lessons_learned:
  - 对这类 brownfield 里程碑，最重要的不是再发明新 surface，而是先锁住真实 authority chain；S01 早点把 accepted route family 定死，后面每个 slice 都轻松很多。
  - replay/highlights 被 `[SESSION_NOT_COMPLETED]` 拦住时，不一定是 replay gate 太严；先检查 persisted lifecycle truth 有没有在 canonical evidence 已可读时完成状态收口。
  - 把 canonical availability (`session.status`) 和 optional enhancement health (`report_status`) 分开，是避免 learner-facing surface 被 enhancement 噪声绑死的关键。
---

# M003: 知识与角色真实性

**M003 把当前销售训练链路收口成一条真实可验证的“Persona/knowledge → objection pressure → claim-truth → same-session report/replay/highlights”事实线。**

## What Happened

M003 把“知识与角色真实性”从 prompt 层的意图，落成了当前产品代码链路上的可验证事实。S01 先锁定了真实 authority chain：admin Persona / knowledge detail、`POST /api/v1/practice/sessions`、learner practice page、knowledge-check、canonical report、replay。这样后面的实现都被强制留在现有 runnable 路线上，而不是转向新的 helper-only surface 或环境工件。S02 随后把 Persona 压力模型结构化并冻结进 `voice_policy_snapshot`，让同一个 Persona 的 pressure direction、follow-up behavior 和 KB binding 能跨 turn / reconnect 保持稳定。S03 再把 unresolved objection ledger 固定在现有 runtime/evidence chain 上，使价格、ROI、竞品、实施风险这类阻塞点不会因为 topic drift 或 reconnect 消失，而会持续回到同一个 gap 上。S04 把 unsupported / weak / pending / verified 这些 claim-truth 语义挂到统一 `effectiveness_snapshot.claim_truth` 上，并让 runtime diagnostics、knowledge-check、report、replay 都通过同一 vocabulary 解释同一 session。S05 用一条 live objection-heavy same-session proof 验证了这套链路在当前产品 surface 上确实能工作，同时诚实地暴露了最后一个 blocker：same-session canonical report 已可读，但 replay/highlights 仍卡在 persisted `status="scoring"` 后面。S06 则把这个 blocker 在不破坏 shipped contract 的前提下收掉：sales end-session 立即响应仍保持 `status="scoring"`，后台 finalization 只在 `SessionEvidenceService` 已能读取 canonical evidence 时把同一 session 提升到 `completed`，随后 canonical report/replay/highlights 全部能在该 same session 上 truthful 解锁，而真正 unfinished session 仍继续被 `[SESSION_NOT_COMPLETED]` 拦住。

到 milestone 结束时，M003 的关键价值已经闭环：admin 配置能通过当前 session-create/runtime path 真正影响 learner-facing objection pressure；同一会话的异议、证据缺口和 claim truth 可以跨 runtime、knowledge-check、report、replay 保持一致；并且最终 same-session replay/highlights 不再被一个落后于 canonical evidence 的 persisted scoring 状态卡死。validation 结果为 pass，也确认了没有 cross-slice seam drift 留下。

## Success Criteria Results

- **管理员配置仍走 accepted current business route family** — 达成。validation checklist 第 1 条为 pass，且 S05 live proof 与 S06 same-session proof 都继续使用当前 admin Persona/knowledge、session create、learner practice/report/replay 路由。
- **知识状态维持 live seven-status vocabulary** — 达成。validation checklist 第 2 条为 pass；S01 锁定 vocabulary 后，S05 live knowledge-check/report proof 与 S06 replay-unlock 修复都没有改变该 seam。
- **Persona pressure / objection focus / claim-truth / read-side conclusions 在同一 evidence line 上保持稳定** — 达成。validation checklist 第 3 条为 pass，S02-S04 建立的 snapshot + objection ledger + claim-truth seam 在 S05/S06 的 fresh proof 中继续被消费，没有出现 cross-slice drift。
- **最终 same-session proof chain 能到 replay/highlights，不再停在 `[SESSION_NOT_COMPLETED]`** — 达成。validation checklist 第 4 条为 pass；S06 用 focused backend regressions、accepted same-chain backend pack 和 live localhost same-session proof 一起证明该 blocker 已退休。

## Definition of Done Results

- **真实业务链路收口完成**：M003 全程都保持在当前 admin Persona / knowledge → session create → learner practice → knowledge-check / report / replay 这条真实业务代码链路上推进，没有引入并行占位 surface；validation 也再次确认 S01-S06 全部仍建立在这条 authority line 上。
- **同一事实线贯通完成**：Persona 压力、异议 ledger、claim-truth、canonical report/replay/highlights 都继续建立在统一 session-evidence / runtime diagnostics seam 上，而不是各自重算；validation 的 cross-slice audit 确认没有新的 boundary drift。
- **最终 blocker 已被退休**：S05 暴露的 same-session replay/highlights 卡在 persisted `status="scoring"` 的 blocker 已由 S06 用 fresh backend regression + live localhost same-session proof 退休，并且没有通过放宽 replay gate 这种取巧方式完成。
- **里程碑验证已通过**：`.gsd/milestones/M003/M003-VALIDATION.md` verdict 为 `pass`，说明 milestone 在结构、验证和 requirement 覆盖上都满足 close-out 门槛。

## Requirement Outcomes

- **R010**: `active` → `validated` — 证据链来自 S01-S06 全部 slice 的完成与 M003 validation pass。S01 锁定 accepted route family 与 live seven-status knowledge vocabulary；S02 冻结 Persona pressure 到 session snapshot；S03 让 unresolved objection ledger 跨 turn/reconnect 持续存在；S04 把 claim-truth 统一到 `effectiveness_snapshot.claim_truth` 并贯穿 runtime/report/replay；S05 提供 live objection-heavy same-session proof 并定位最终 blocker；S06 则用 fresh backend regressions（44/44）、accepted same-chain backend proof（114/114）和 live localhost same-session proof 退休该 blocker，证明 immediate lifecycle end 仍为 `status="scoring"`，background finalization 后 persisted session 变为 `completed`，canonical report/replay/highlights 在同一 session 上 truthful 解锁，而 unfinished sessions 仍被 `[SESSION_NOT_COMPLETED]` 拦住。

## Deviations

S06 的 live acceptance proof没有再完整重跑一次真实麦克风驱动的 objection-heavy 对话，而是复用 accepted learner route family 并在 fresh same session 上通过 live DB seam 注入 canonical objection/evidence facts，再经过真实 lifecycle end 与 background finalization 证明状态边界与 replay/highlights 解锁。这是范围内偏差，但没有改变 acceptance route family，也没有削弱 S06 要验证的核心边界。另一个执行偏差是 M003/S06 原先缺少 GSD DB 的 slice/task rows；close-out 前已补齐并重新对账 milestone/slice state，再做 validation/close-out。

## Follow-ups

- M004 之后如继续扩 learner loop，优先复用当前 report / replay / highlights / retry-entry authority seams，不要再做第二套 learning surface。
- Optional enhanced-report generation 在 localhost proof path 仍有 `[REPORT_NOT_FOUND]` / `[REPORT_GENERATION_FAILED]` 噪声；后续如要治理，应继续把它当作 enhancement path，而不是重新耦合 canonical replay/report availability。
- 如果后续再扩 Persona / knowledge realism，先看 `voice_policy_snapshot.customer_pressure`、`SessionEvidenceService`、`effectiveness_snapshot.claim_truth` 和 objection ledger 这几条 authority seam，避免重新把事实拆回多套 contract。

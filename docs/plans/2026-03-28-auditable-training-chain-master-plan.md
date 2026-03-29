# Auditable Training Chain Master Plan

**Date:** 2026-03-28  
**Scope:** 把“知识库 → 检索 → 训练 → 录音可审计 → 报告可信”整条链一次性细化成后续执行主线。  
**Priority policy:** 先把事实链、审计链、证据链跑实，再回到主管闭环、PPT realtime interruption、移动端、外部集成。

---

## 0. 总目标

这条主线的目标不是再加功能，而是把训练系统最关键的三条事实线做硬：

1. **检索事实线**：知识库是否真的进入训练，命中了什么，是否被使用。  
2. **录音审计线**：每次录音/转写/回放都能被抽查和追责。  
3. **报告证据线**：报告结论能落到具体 transcript / retrieval / audio evidence。  

只有这三条都成立，训练系统才是“可复盘、可审计、可追责”的，而不是“看起来像有报告和知识库”。

---

## 1. 里程碑总览

| Milestone | Title | 核心问题 | 主要输出 | 通过标准 |
|---|---|---|---|---|
| M008 | 检索事实链收口 | 知识库是否真的进入训练、命中、被使用 | session-level retrieval ledger + knowledge-check/report retrieval audit | 一条真实 session 能明确回答“检索过什么、是否有用” |
| M009 | 录音审计链收口 | 每次录音是否可定位、可回放、可对齐 transcript、可抽查 | audio audit metadata + replay/report 链接能力 | 随机抽一场训练能从报告反查到音频/转写/时间段 |
| M010 | 报告证据链收口 | 报告为什么这么判断，证据来自哪里，降级发生在哪一层 | report evidence reference model + degraded reason model | report/replay/knowledge-check 三者在同一证据线下自洽 |

---

# M008 — 检索事实链收口

## M008 Goal
把“知识库准备好了”提升成“知识库真实参与了训练，并且这个事实可验证”。

## M008 Success Criteria
- session 能明确记录绑定了哪些 knowledge bases
- 能明确判断一次训练是否发生检索
- 能明确显示命中摘要 / 命中数量 / 命中类型 / 检索失败原因
- knowledge-check 与 report 对检索事实的描述一致
- 至少一条真实 session 证明 retrieval truth line 成立

## M008 Slices

### S01 — Session-level retrieval ledger 最小化
**Goal:** 给每场训练一个最小、稳定、可审计的 retrieval ledger。  
**Why first:** 不先把 retrieval truth 定下来，后面的录音审计和报告可信都没有锚点。

#### Tasks
- **T01** 锁 retrieval ledger contract（integration + contract tests）
- **T02** 在现有 `runtime_metrics.knowledge_retrieval` seam 上归一化 session-level retrieval ledger
- **T03** 把 retrieval ledger 挂到 `/practice/sessions/{id}/knowledge-check`
- **T04** 做 malformed / partial retrieval metrics fail-soft proof

#### Likely files
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/conversation/schemas.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

#### Validation
- focused backend integration / contract tests
- one session proof: no_kb / not_triggered / search_failed / hit / miss

---

### S02 — Retrieval truth 进入 canonical report
**Goal:** 不只是 `knowledge-check` 看得见，report 也要能讲清 retrieval truth。  
**Why second:** 用户最终看的是 report，不是单独知识诊断页。

#### Tasks
- **T01** 扩展 `SessionEvidenceProjection` 增加 retrieval audit object
- **T02** canonical report API 暴露 retrieval audit
- **T03** report page 用 typed contract 渲染 retrieval evidence note
- **T04** 锁 report / knowledge-check retrieval parity

#### Likely files
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/api/practice.py`
- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`

#### Validation
- backend contract tests for report payload
- frontend report page focused tests
- browser proof on one knowledge-backed session report

---

### S03 — Retrieval truth 形成 shipped-route smoke
**Goal:** 用真实 route family 证明 retrieval fact line，不停留在测试层。  
**Why third:** 需要一条可重复 smoke，避免“本地以为好了，线上不知道”。

#### Tasks
- **T01** 设计 retrieval smoke proof artifact format
- **T02** 跑一条真实 session：绑定 KB → 训练 → knowledge-check → report
- **T03** 输出 artifact，记录 query / hit / report retrieval audit / mismatch 分类
- **T04** 如有必要，补最小 smoke helper / script

#### Likely files
- `.artifacts/...`
- `scripts/`（仅在必要时）
- `.gsd/KNOWLEDGE.md`

#### Validation
- clean-shell or localhost proof
- artifact 可回答：检索有没有发生、命中了什么、report 是否引用一致

---

# M009 — 录音审计链收口

## M009 Goal
把每次训练录音从“可播副产物”升级成“可抽查、可对齐、可审计的证据资产”。

## M009 Success Criteria
- 每次录音可定位到 session / turn / timestamp / speaker
- 音频与 transcript 可对齐
- replay/report 可落到具体录音片段
- 缺段、fallback、转写不完整等审计信息可见
- 至少一条真实 session 可从 report/replay 反查具体录音证据

## M009 Slices

### S01 — Audio audit metadata contract
**Goal:** 定义并持久化最小音频审计元数据。  
**重点:** 不先做复杂播放器，先把 audit metadata 模型立住。

#### Tasks
- **T01** 设计 audio audit schema（session_id / turn_id / segment_id / timestamps / speaker / storage ref / transcript linkage）
- **T02** 锁 backend contract tests
- **T03** 在现有消息/存储链里持久化最小 audit metadata
- **T04** 增加缺段 / 缺 transcript / fallback 场景测试

#### Likely files
- `backend/src/common/db/models.py` / schemas
- `backend/src/common/conversation/*`
- `backend/src/training_runtime/*`
- `backend/tests/...`

#### Validation
- backend integration + persistence proof

---

### S02 — Replay 落到录音证据
**Goal:** replay 不只看 transcript，也能定位到音频片段。  
**重点:** 继续复用现有 replay route family，不造新 audit console。

#### Tasks
- **T01** replay payload 增加 audio segment refs
- **T02** replay page 增加音频定位/跳转能力
- **T03** transcript ↔ audio 对齐断言
- **T04** degraded path（音频丢失 / transcript incomplete）明确提示

#### Likely files
- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/schemas.py`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`

#### Validation
- replay focused tests
- one browser proof with audio segment jump

---

### S03 — 报告可反查录音证据
**Goal:** report 的关键判断能 drill 到 transcript / audio 片段。  
**重点:** 不要求所有判断都可跳，但主问题 / 高风险段必须可跳。

#### Tasks
- **T01** 为 report evidence 增加 audio anchor / transcript anchor
- **T02** report CTA 深链到 replay 指定音频片段
- **T03** 锁 report/replay/audio parity tests
- **T04** 保存 one-session audit artifact

#### Likely files
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/session_evidence.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/session-evidence.ts`

#### Validation
- browser proof: report → replay → specific audio/transcript segment

---

# M010 — 报告证据链收口

## M010 Goal
让报告从“结论看起来合理”升级成“每个关键判断都能被解释、定位、追责”。

## M010 Success Criteria
- report / replay / knowledge-check 不再在证据说明上各说各话
- main_issue / next_goal / claim truth 有明确 evidence references
- degraded reason 有分层归因
- 用户能区分：没检索到、检索到了但没用上、用上了但证据仍弱、录音/转写不完整导致降级
- 至少一条真实 session 证明 report conclusion 可追溯

## M010 Slices

### S01 — Report evidence reference model
**Goal:** 给 report 的关键结论一个统一 evidence reference schema。

#### Tasks
- **T01** 设计 evidence reference object（message/turn/replay/audio/retrieval anchors）
- **T02** 锁 backend contract tests
- **T03** `SessionEvidenceProjection` 产出关键结论的 evidence refs
- **T04** 保证 old payload compatibility 不被打破

#### Likely files
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/schemas.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

#### Validation
- contract + integration tests

---

### S02 — Degraded reason 分层归因
**Goal:** 用户能知道问题出在 retrieval / audio / transcript / enhanced report 哪一层。  
**Why:** 这是“报告可信”的关键，不然还是黑盒。

#### Tasks
- **T01** 列出 degraded taxonomy
- **T02** backend 统一归因出口
- **T03** report/replay/knowledge-check 统一 wording helper
- **T04** 前端 focused tests 锁 wording consistency

#### Likely files
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/conversation/session_evidence.py`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`

#### Validation
- parity tests + browser assertions

---

### S03 — Final evidence-consistency proof
**Goal:** 用一条真实 session 证明 report / replay / knowledge-check / retrieval / audio evidence 全链一致。  
**Why:** 这是整条主线的封板 proof。

#### Tasks
- **T01** 选取一条真实 knowledge-backed session
- **T02** 记录 retrieval truth + audio audit + report refs + replay refs
- **T03** 输出 final artifact
- **T04** 跑 focused smoke / verification pack

#### Likely files
- `.artifacts/...`
- `scripts/...`（如需）
- `.gsd/KNOWLEDGE.md`

#### Validation
- final browser/API proof
- artifact 能回答“为什么这个报告结论成立”

---

## 2. 执行顺序建议

按这个顺序走：

1. **M008/S01** — retrieval ledger 最小化
2. **M008/S02** — report 引用 retrieval facts
3. **M008/S03** — retrieval shipped-route smoke
4. **M009/S01** — audio audit metadata
5. **M009/S02** — replay audio anchor
6. **M009/S03** — report 可反查音频
7. **M010/S01** — report evidence refs
8. **M010/S02** — degraded reason taxonomy
9. **M010/S03** — final evidence-consistency proof

---

## 3. 暂不进入的后续方向

在这三大 milestone 完成前，不建议优先：

- 完整 supervisor task/assignment system（R017 全量）
- PPT realtime interruption 全量版（R016 全量）
- mobile / 企业微信（R018）
- CRM / SSO / 外部系统集成（R019）
- 新开一套独立 audit console

---

## 4. 单项执行入口

如果要马上开工，建议从：

### **M008 / S01 / T01**
先锁 retrieval ledger contract。  
因为后面所有东西都建立在“检索事实到底有没有”这件事先被证明清楚。

---

## 5. 这一版计划的使用方式

- 这是 master plan，用来决定顺序与边界。
- 真正执行时，每个 slice 再单独拆 implementation plan。
- 不建议直接把整个 master plan 一次性并行实现，容易重新回到“面很大，但事实没锁死”的状态。

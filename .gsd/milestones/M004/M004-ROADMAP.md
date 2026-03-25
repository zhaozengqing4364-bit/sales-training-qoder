# M004: 复盘与学习闭环增强

**Vision:** 让用户与主管在现有 report / replay / history 业务入口上完成“训练 → 报告 → 回放 → 关键片段 → 针对性复练”的学习闭环。所有学习证据都必须来自统一 session evidence / replay / presentation review authority line，而不是再造一套生成式学习系统。

## Success Criteria

- 用户可以从现有 `/practice/{sessionId}/report` 直接定位主问题对应的关键片段，并看到为什么这是关键片段、怎样更好表达。
- 现有 replay / highlights surfaces 不再只是 good/bad 标签，而是能解释关键回合、阶段、原因和替代表达。
- sales 与 presentation 都在现有 report / replay 入口上形成更强学习闭环；PPT 至少能落到页级 / 要点级学习证据。
- 学习闭环增强不引入第二套事实线；所有解释、跳转和再练参数都来自现有 unified evidence / replay / report surfaces。

## Slices

- [x] **S01: 当前 report/replay/highlight 入口的学习证据 contract** `risk:high` `depends:[]`
  > After this: On the existing replay and highlight surfaces, a learner can see which turn mattered, why it mattered, which stage it belongs to, and what a better response looks like — without adding a new learning page.

- [x] **S02: report 直达 replay 关键片段** `risk:high` `depends:[S01]`
  > After this: On the current report page, the learner can open the replay at the relevant turn/marker for the surfaced issue or goal.

- [ ] **S03: 主问题驱动的再练入口** `risk:high` `depends:[S01,S02]`
  > After this: From the current report or replay page, the learner can start a new practice session targeted at the previous issue family and see that focus carried into the new session.

- [ ] **S04: PPT 页级学习证据** `risk:medium` `depends:[S01]`
  > After this: On the current PPT report/replay routes, a learner can see which page has which issue cluster and why it should be reworked.

- [ ] **S05: sales + PPT 学习闭环终验** `risk:medium` `depends:[S03,S04]`
  > After this: At least one sales and one PPT route complete a live learning loop on the current entrypoints, and degraded states remain understandable.

## Boundary Map

### S01 → S02

Produces:
- A learning-evidence contract on the existing replay/highlight authority line: reason, stage, context, suggested response, and stable anchors.
- Shared vocabulary between replay/highlight evidence and report conclusions.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Stable evidence objects that can be referenced by a retry intent.
- A clear mapping from issue family to concrete evidence turn/page.

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- A shared explanation structure that presentation page-level evidence can reuse.
- A consistent way to describe why a moment matters across sales and PPT.

Consumes:
- nothing (first slice)

### S02 + S03 → S05

Produces:
- A sales learning loop on current routes: report → replay → retry.
- Evidence-rich anchors for live end-to-end proof.

Consumes from S02:
- report → replay deep links.

Consumes from S03:
- issue-driven retry launch contract.

### S04 → S05

Produces:
- A presentation learning loop on current routes: report → replay → page evidence.
- Page-aware evidence packs for live UAT.

Consumes from S04:
- page-level evidence contract.

# M004: 复盘与学习闭环增强

**Vision:** 把已完成训练沉淀成真正能帮助用户和主管学习的证据链：不仅知道分数和结论，还能看见关键回合、为什么好/差、下一次如何具体重练，以及在 PPT 场景下到底哪一页讲偏、讲漏或讲虚。

## Success Criteria

- 用户可以回看一场已完成训练的关键高光与问题回合，并得到**可执行的原因说明和更好的替代表达**，而不是只看到标签。
- 报告页能直接把用户带到“下一次要围绕什么改”的再练入口，而不是停留在阅读态。
- PPT 训练具备页级 / 要点级学习证据，用户能看出自己在哪些页面讲偏、讲漏、讲长、触发了禁用词或错过了关键价值点。
- 主管在带教时可以使用回放证据和重点片段，而不需要只凭抽象总结转述。

## Key Risks / Unknowns

- 当前 highlights / replay 虽已存在，但“为什么是问题”与“该怎么改”仍可能不够强。— 若只有高光标签，没有学习价值，M004 只是在美化回放页。
- 报告与再练之间目前缺少明确的行为闭环。— 用户知道问题却不知道怎么把它转成下一次练习，会导致复练率提升有限。
- PPT 场景已有第一页版复盘骨架，但页级学习证据是否足够具体仍未证明。— 若只输出泛泛总结，用户很难按页纠偏。
- 若用自由生成的“优秀话术”直接覆盖真实材料，可能重新引入事实漂移。— 学习参考必须受控并引用当前材料基线。

## Proof Strategy

- 高光 / 回放解释性不足 → retire in S01 by proving highlights 不仅有 `good/bad`，还带理由、上下文、stage 和可执行替代建议。
- 报告无法驱动下一练 → retire in S02 by proving report 可以直接生成针对 `main_issue` / `next_goal` 的再练入口和预填 focus。
- 优秀示例可能脱离材料 → retire in S03 by proving 参考表达采用受控模板或材料引用，不会生成与当前事实基线冲突的“标准答案”。
- PPT 学习证据仍偏泛 → retire in S04 by proving PPT 报告 / 回放能指出页级问题、价值点覆盖和禁用词 / 偏题证据。
- 主管仍只能看总结 → retire in S05 by proving supervisor-facing surfaces 可以直接使用 replay/highlight evidence 做辅导。

## Verification Classes

- Contract verification: replay / highlights / report / retry_entry / PPT page evidence 的 schema 和 focused tests。
- Integration verification: 已完成 session 的 report → replay → history → retry create-session 链路验证；PPT 完整讲完后的统一复盘链路验证。
- Operational verification: 没有 highlights、不可评估 session、增强报告缺失、PPT 证据缺项时的 degraded state 验证。
- UAT / human verification: 用户和主管是否能真正回答“为什么差、具体怎么改、下一次练什么”。

## Milestone Definition of Done

This milestone is complete only when all are true:

- 回放与高光不再只是展示消息，而是能明确指出关键回合、原因和建议。
- 报告页可以把主问题直接转成下一练入口，并且参数与事实基线一致。
- PPT 训练的页级 / 要点级 / 禁用词证据已经能支持真实纠偏。
- 主管可直接利用系统中的 replay/highlight/report 证据进行线下辅导，而不是只看抽象分数。
- 至少一条 sales 和一条 PPT 的完整学习闭环完成 live UAT。

## Requirement Coverage

- Covers: R011
- Partially covers: R005, R006, R008
- Leaves for later: R012, R017
- Orphan risks: none

## Likely Work Surfaces

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/api.py`
- `backend/src/evaluation/services/comprehensive_report.py`
- `backend/src/presentation_coach/services/presentation_report_service.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `web/src/components/highlights/*`
- `web/src/lib/api/client.ts`
- `web/src/lib/session-evidence.ts`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(dashboard)/history/page.test.tsx`

## Slices

- [ ] **S01: 高光片段与逐轮解释性增强** `risk:high` `depends:[]`
  > After this: replay/highlights 不只标记 good/bad，还能展示原因、上下文、阶段与可执行替代建议。

- [ ] **S02: 报告直达再练的目标化闭环** `risk:high` `depends:[S01]`
  > After this: report 可以把 `main_issue` / `next_goal` 转成一条明确的再练入口和预填 focus，而不是泛泛“再试一次”。

- [ ] **S03: 受控的优秀表达 / 参考答案机制** `risk:medium` `depends:[S01]`
  > After this: 用户能看到围绕当前材料和主问题的参考表达方式，但不会引入脱离事实基线的幻觉示例。

- [ ] **S04: PPT 页级学习证据与纠偏提示** `risk:medium` `depends:[S01]`
  > After this: PPT 训练的报告 / 回放可以按页指出漏讲、讲偏、讲长、禁用词和关键价值点覆盖情况。

- [ ] **S05: 主管带教证据包与 drill-in** `risk:medium` `depends:[S02,S03,S04]`
  > After this: 主管可以直接查看关键高光、问题回合、页级证据和下一次辅导重点，而不必自己从长报告里二次提炼。

- [ ] **S06: 学习闭环端到端验收** `risk:medium` `depends:[S05]`
  > After this: 至少一条 sales 和一条 PPT 链路完成“训练 → 报告 → 回放 → 再练”的真实验收，并验证 degraded states 仍清晰可用。

## Boundary Map

### S01 → S02

Produces:
- 高光片段的解释性 contract：reason、context、stage、suggested response、ai_feedback 等字段的稳定读形。
- replay 与 highlights 可共享的逐轮学习证据面。
- 针对“为什么好 / 差”的 focused tests。

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- 可定位到具体问题回合和问题类型的 evidence 基线。
- 为参考表达机制提供可约束的输入：问题类型、阶段、材料上下文、下一目标。

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- 销售/PPT 统一的 replay/highlight 解释性基线。
- 可向 PPT 页级证据延展的 message/page linking 语义。

Consumes:
- nothing (first slice)

### S02 + S03 → S05

Produces:
- report 到 retry 的稳定参数 contract。
- 主问题 / 下一目标 / 参考表达之间的一致性边界。
- 主管查看“问题是什么、建议怎么练”的快速 drill-in surface。

Consumes from S02:
- report 直达再练闭环。

Consumes from S03:
- 受控参考表达机制。

### S04 → S05

Produces:
- PPT 页级证据、讲偏/讲漏/禁用词/价值点覆盖的稳定聚合输出。
- 主管辅导 PPT 训练时可直接引用的页级证据。

Consumes from S04:
- 页级学习证据 contract。

### S05 → S06

Produces:
- 面向用户与主管的最终学习闭环验收路径。
- sales / PPT 双场景的 live proof 与 degraded proof。

Consumes from S05:
- 带教证据包与 drill-in surfaces。

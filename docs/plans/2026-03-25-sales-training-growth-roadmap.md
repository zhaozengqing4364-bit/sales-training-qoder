# 销售训练 qoder Growth Roadmap（M003-M005 细化版）

> 日期：2026-03-25
> 范围：细化 M003《知识与角色真实性》、M004《复盘与学习闭环增强》、M005《后台治理与规模化运营》
> 说明：本文件在 `docs/plans/2026-03-23-sales-training-growth-roadmap.md` 的基础上，把未来三个 milestone 收敛到可直接继续拆 slice / task 的粒度。它不是立即执行清单；真正开工前，仍应先关闭 M002 的 S07/S08 缺口，再按 safe-grow 流程一次只执行一个最小事项。
> 硬约束（2026-03-25 hard steer）：后续规划只允许围绕真实业务代码、真实用户入口、真实可运行目录和明确验收标准展开；不得把 Conda、Silence、环境文件、锁文件等工具/环境项单独升格为 milestone，若真实代码入口不清则先做 inventory / spike。

---

## 1. Current System Understanding

这个项目已经有了能跑通的训练底座，也有了第一条统一事实线：

- M001 已把 lifecycle、report、replay、history、admin、PPT report、support runtime 收到同一条 evidence authority line 上。
- M002/S01-S04 已把 realtime sales coaching 的核心语义收紧：统一五维 sales rubric、单轮唯一主动作、共享下一轮规则、completed-session read-side alignment。
- 但 M002 close-out 仍缺 S07/S08 的 operational proof：**live coach degraded / resumed 可见**与**同一 session 从 realtime coaching 到 final report/replay 的闭环 UAT** 还没退休。

因此，M003-M005 的详细规划必须建立在一个明确前提上：

> **Gate 0：M002 必须先补齐 S07/S08。**
>
> 如果 realtime coach 还没有明确的 degraded/resumed truth line，后续关于 Persona 真实性、学习闭环或管理动作的增强都会把不稳定链路包装成“更丰富的产品”。这条顺序不能反。

---

## 2. Strengths Worth Preserving

这些是后续规划不能破坏的边界：

1. **统一 evidence authority line**
   - `PracticeSession` + `ConversationMessage` + `SessionEvidenceService` 已经是 report / replay / history / admin / runtime health 的权威事实源。
   - M003-M005 不应再造第二套 scoring / analytics / replay 事实线。

2. **稳定 public contract， richer backend-only context**
   - M002 已证明：对外保持稳定的 `score_update` / report keys，对内通过 shared helper 增强语义，是正确方向。
   - 未来不要为了补能力把 public payload 扩成“半内部调试协议”。

3. **sales / presentation runtime 分离，报告读线共享**
   - 销售与 PPT 可以继续独立演进，但 report / replay / admin 应尽量复用统一 evidence 读线。

4. **桌面端优先、外部集成后置**
   - M005 可以为集成留 boundary，但不能提前做 CRM / SSO / 企业微信深集成来掩盖训练本体未闭环。

---

## 3. Priority Order And Scoring

### 3.1 Milestone-level scoring

| Candidate | User leverage | Core-capability leverage | Evidence strength | Compounding value | Validation ease | Blast radius | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| M003 知识与角色真实性 | 5 | 5 | 5 | 5 | 3 | 3 | 20 |
| M004 复盘与学习闭环增强 | 4 | 4 | 4 | 5 | 4 | 2 | 19 |
| M005 后台治理与规模化运营 | 4 | 4 | 4 | 5 | 3 | 3 | 17 |

### 3.2 Why this order

1. **M003 first**
   - 当前 runtime 已经能“教”，但 AI 客户是否足够真实、是否会持续围绕 ROI / 价格 / 竞品 / 实施风险 / 证据追问，仍然是主价值缺口。
   - 如果 M003 不先做深，M004 只会把“半真实对话”包装成漂亮回放与报告。

2. **M004 second**
   - 当训练过程更真实后，再把 highlights、replay、report、re-practice 做成真正可学习的闭环，学习资产才可信。

3. **M005 third**
   - 管理动作、团队分析、资产治理的价值建立在前两条线已经稳定之后。
   - 否则主管只是更快地看到一堆还不够真的训练结果。

---

## 4. Evidence Snapshot For M003-M005

### 4.1 M003 相关现状证据

**已存在的正向骨架**
- `backend/src/agent/services/persona_policy.py`
  - 已有 `sales_focus` / `value_axes` / `objection_axes` / `expected_customer_questions`，说明 Persona 真实性已经有 authority seam。
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
  - 已把 Persona sales focus 编译进 runtime base contract，说明“角色真实性 → runtime 指令”的链已存在。
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
  - 已有 objection-aware query widening、rerank 开关、entity-focused retrieval heuristics，说明知识真实性不是从零起步。
- `backend/src/common/knowledge/kb_lock_guard.py`
  - 已有 `strict_audit` / `coach_mode`，说明系统已经知道“证据不足时不要直接炸掉训练主链路”。

**仍明显不足的点**
- 当前 Persona 真正能持续影响的是 prompt/instruction，**还不是一套可持久、可验证、可比较的“客户压力模型”**。
- 检索命中与否目前更多体现在 diagnostics / helper 逻辑里，**还没有变成“AI 客户是否允许接受某种说法”的显式 truth contract**。
- 多轮追问的“未解决异议 / 已承诺证据 / 下一轮继续施压点”还没有形成稳定 ledger。

### 4.2 M004 相关现状证据

**已存在的正向骨架**
- `backend/src/common/conversation/replay.py`
  - 已有 replay、timeline markers、highlights、suggested better response。
- `backend/src/common/conversation/session_evidence.py`
  - 已有 stage summary、main_issue、next_goal、timeline markers 的统一读线。
- `backend/src/evaluation/services/comprehensive_report.py`
  - 已有 enhanced report 能力与 PPT branch。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - 已会并行加载 unified report、enhanced report、highlights，并优雅降级。
- `web/src/components/highlights/*`
  - 已有高光列表与详情 UI 骨架。

**仍明显不足的点**
- 当前 replay / highlights 更像“能看”，还不够“能学”。
- report 与 replay 之间还缺少足够强的锚点：**用户知道主问题，但不一定能一键看到“哪一轮、哪一句、为什么错、下一次怎么改”。**
- 销售和 PPT 的再练入口仍偏弱，缺“围绕当前 main_issue / next_goal 的下一练预设”。

### 4.3 M005 相关现状证据

**已存在的正向骨架**
- `backend/src/admin/api/interventions.py`
  - 已有 manager-lite intervention endpoints，但当前 `/remind` 只是 logging，不是完整工作流。
- `backend/src/admin/api/analytics.py` + `backend/src/common/analytics/admin_analytics_service.py`
  - 已有 admin overview / trends / leaderboard / export。
- `web/src/app/admin/users/[id]/page.tsx`
  - 已有 supervisor-readable progress / sessions / recommendation surface。
- `web/src/app/admin/*`
  - 已有 agents / personas / knowledge / presentations / voice-runtime / analytics 等治理页面。

**仍明显不足的点**
- `admin_analytics_service.py` 仍有明显 legacy weighted score 计算（`logic*0.4 + accuracy*0.3 + completeness*0.3`），说明 **管理面与当前 sales semantics 仍可能漂移**。
- interventions 没有前台工作流与持久记录，意味着主管仍主要“看见问题”，不能在系统里完成闭环动作。
- 资产治理页面已存在，但缺少“变更影响 / rollout safety / 审计追踪”的统一产品层能力。

---

## 5. Gate 0 — Before Any Of M003-M005 Starts

### 必须先满足的前置条件

- 关闭 M002/S07：coach degraded / resumed / data unavailable 对 learner、operator、runtime evidence 都清晰可见。
- 关闭 M002/S08：至少一条真实 sales session 证明 realtime coach → final report/replay 同口径。
- 将 M002 当前 contract 冻结为后续基线：
  - realtime public contract：`score_update` / `stage_update` / `action_card`
  - read-side contract：`main_issue` / `next_goal` / `evidence_completeness`

### 不满足前置条件时不要做的事

- 不要扩写 Persona 复杂度。
- 不要增强 highlights / replay UI。
- 不要新增 manager dashboard 或 cohort analytics。

---

# 6. M003 — 知识与角色真实性

## 6.1 User Problem

当前系统已经能给销售实时反馈，但 AI 客户还不够“真实业务对手”：

- 价格 / ROI / 竞品 / 实施风险 / 案例证据的追问还不够稳定。
- Persona 更多是 prompt 风格差异，未必会形成稳定、可持续的“客户压力模型”。
- 当销售说法缺证据时，系统还没有足够强的 truth contract 去决定“继续施压 / 要求举证 / 标记 unsupported claim / 进入 coach-mode 提示”。

## 6.2 Desired User Outcome

- 学员会明确感受到不同 Persona 的真实差异：有人更看 ROI，有人更担心实施风险，有人更强势地追问竞品替代与案例证据。
- AI 客户不会轻易放过空话、功能堆砌或泛泛承诺，而会持续围绕真实 objections 追问。
- 当知识不足或证据不足时，系统不会假装“懂了”，而会清楚地引导到更具体的表达或补证据。

## 6.3 System Capability Outcome

- Persona 从“文本提示”升级为“可审计、可快照、可验证的客户压力模型”。
- Retrieval / grounding 从“辅助检索”升级为“运行时是否接受某个销售说法的证据依据”。
- 会话内 unresolved objections / promised evidence / next proof request 成为可持久化事实，供 realtime / report / replay 共用。

## 6.4 Done Means

- 同一知识库下，不同 Persona 会稳定地产生不同追问模式，而不是只变语气。
- 价格 / ROI / 竞品 / 风险 / 案例 等 objection path 至少有一条 shared truth contract 可验证。
- unsupported claim / weak evidence / no evidence 的处理路径可见、可测试、可回放。
- learner report / replay 能回看“客户为什么继续追问”。

## 6.5 Slices

### M003/S01 — Persona 压力模型 authority line

**Goal**
把 Persona 从 prompt 文本升级为可运营的“客户压力模型”，并把它稳定编译进 runtime snapshot。

**Evidence from repo**
- `backend/src/agent/services/persona_policy.py` 已有 sales-focus 结构。
- `backend/src/sales_bot/services/voice_instruction_compiler.py` 已会消费 Persona policy。
- `backend/src/agent/services/persona_service.py` 已有 policy audit 骨架。

**Likely files / modules**
- `backend/src/agent/services/persona_policy.py`
- `backend/src/agent/services/persona_service.py`
- `backend/src/agent/api/personas.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/sales_bot/services/voice_runtime_policy.py`
- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`

**Tasks**
- **T01**：扩展 persona policy schema，补上 `customer_pressures`、`non_negotiables`、`proof_expectations`、`followup_ladder`、`risk_tolerance` 等字段，并给出 normalize / migrate 规则。
- **T02**：把这些字段编译进 `VoiceInstructionCompiler` 与 session snapshot，确保 runtime 使用的是 frozen authority，而不是读取 admin 当前值。
- **T03**：在 admin persona 详情页加入可视化编辑、preview 与 audit 提示，让“强压价格型 / ROI 型 / 风险敏感型” Persona 真正可配置。

**Smallest credible slice**
先把 schema、compiler、snapshot、admin edit roundtrip 做通，不先碰 multi-turn memory。

**Validation plan**
- persona policy normalize 单测
- compiler 输出 contract 单测
- admin persona CRUD / preview focused tests
- 创建新 session 后检查 `voice_policy_snapshot` 含 persona pressure fields

**Success signal**
两个绑定同一 KB 的 Persona，仅调整 pressure model，就能稳定改变 runtime follow-up 方向。

**Depends on**
- Gate 0 only

---

### M003/S02 — 检索与 grounding 真实性升级

**Goal**
让价格 / ROI / 竞品 / 风险 / 证据类 objection 的检索与引用更像真实业务证据线，而不是一组放宽阈值的启发式命中。

**Evidence from repo**
- `stepfun_knowledge_helpers.py` 已有 objection-aware widening、rerank 开关与 top_k 调整。
- `kb_lock_guard.py` 已支持 `coach_mode`。
- `report/page.tsx` 已能显示 knowledge-check 与降级提示。

**Likely files / modules**
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`
- `backend/src/common/knowledge/kb_lock_guard.py`
- `backend/src/common/knowledge/service.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`

**Tasks**
- **T01**：增加 objection-aware query rewrite，把 stage、persona pressure、上一轮 unresolved objection 一并纳入 query planning。
- **T02**：把检索结果从“snippet list”提升为 `evidence bundle`：区分 price proof、ROI proof、competitor rebuttal、implementation risk、customer case 等证据类别。
- **T03**：定义 claimability gate：当命中低置信、证据类别不对或只有 keyword fallback 时，runtime 明确走“继续追问 / 要求更具体场景 / coach-mode 提醒”，而不是默认接受。

**Smallest credible slice**
先让 knowledge-check payload 和 runtime diagnostics 能分清“有命中”“证据类型不匹配”“低置信命中”“完全 miss”。

**Validation plan**
- knowledge helper / internal searcher unit tests
- practice knowledge-check contract tests
- objection-focused integration tests（price / competitor / ROI）
- report page focused tests for new degraded / weak-evidence copy

**Success signal**
学员在报告与 runtime 中都能看到：系统不是“没回答”，而是“当前证据不够支撑这个说法”。

**Depends on**
- M003/S01

---

### M003/S03 — 多轮异议与证据承诺记忆

**Goal**
让 AI 客户记住还没被解决的 objection、学员承诺稍后补充的证据、以及下一轮应继续追问的点。

**Evidence from repo**
- `backend/src/sales_bot/services/context_manager.py` 存在，但当前 M002 的 shared coaching seam 主要围绕 stage/score/action，并没有形成显式 unresolved-objection ledger。
- `stepfun_realtime_handler.py` 已有 rich stage/score context 保留能力，说明“把更多事实放进 runtime state”是可行的。

**Likely files / modules**
- `backend/src/sales_bot/services/context_manager.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/components/capability_processor.py`
- `backend/src/common/conversation/storage.py`
- `backend/src/common/conversation/session_evidence.py`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/components/practice/RightPanelContent.tsx`

**Tasks**
- **T01**：定义 unresolved objection / promised proof / next expected evidence 的 runtime ledger 与 snapshot 格式。
- **T02**：把 ledger 接到 classic + StepFun 两条 runtime 上，并保证 reconnect restore 不会重放旧 pressure state。
- **T03**：让 learner-facing coach surface 和 completed-session evidence 都能读到“未解决异议”事实，而不是只看最终总体结论。

**Smallest credible slice**
先覆盖一种高价值 objection family（价格/ROI），证明跨 turn 和记忆恢复成立，再扩展到竞品/风险。

**Validation plan**
- handler persistence / restore focused tests
- integration tests for “销售转移话题，客户继续追问同一证据”
- replay / report evidence assertions for unresolved objection carry-forward

**Success signal**
学员不能靠换话题“甩掉”价格/证据问题；AI 客户会在后续轮次继续回到该缺口。

**Depends on**
- M003/S02

---

### M003/S04 — unsupported claim / weak evidence truth contract

**Goal**
把“销售说法是否被证据支撑”做成显式 truth line，影响 realtime、report、replay，而不是只在隐式 prompt 中生效。

**Evidence from repo**
- `kb_lock_guard.py` 已能输出 coach-mode grounding context。
- `practice.py` / report page 已有 knowledge-check / evidence completeness surface。
- 但当前缺“unsupported claim / weak evidence / evidence supplied later”这种更业务化的 contract。

**Likely files / modules**
- `backend/src/common/knowledge/kb_lock_guard.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/conversation/session_evidence.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/components/practice/RightPanelContent.tsx`

**Tasks**
- **T01**：定义 `unsupported_claim` / `weak_evidence` / `evidence_pending` / `evidence_verified` 的 canonical flags。
- **T02**：把 flags 接到 realtime pressure、report issue/goal mapping、replay/highlight labels，保持同一套词汇。
- **T03**：把 diagnostics 暴露给 learner 和 operator，但不泄漏内部实现细节或系统错误噪声。

**Smallest credible slice**
先覆盖 sales 场景，尤其 price / ROI / competitor 三类最常见 objection，不把 presentation 一起卷进来。

**Validation plan**
- evaluator / session_evidence unit tests
- contract tests for report / replay stable keys
- browser UAT：claim 被 challenge 后 report 能解释原因

**Success signal**
同一 session 里，runtime 的“继续追问证据”与 report 的“main_issue / next_goal”在 unsupported-claim 场景下严格对齐。

**Depends on**
- M003/S03

---

### M003/S05 — 真实性终验与 live proof

**Goal**
用真实 Persona × objection path 的 live proof 证明 M003 不是“规则更复杂”，而是“客户更真实”。

**Likely files / modules**
- `backend/tests/unit/*persona*`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/integration/test_sales_value_training_flow.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- UAT artifacts under `.gsd/` or `docs/plans/`

**Tasks**
- **T01**：建立 persona realism regression net：至少覆盖 ROI、价格、竞品、实施风险四类 pressure path。
- **T02**：跑一条真实 live session，证明 unresolved objection、weak evidence、verified evidence 三种状态可观察。
- **T03**：把 M003 的 runtime / report / replay / admin proof 打包成下一阶段可复用的 truth checklist。

**Validation plan**
- focused backend + web suites
- 至少一条 browser/live UAT
- evidence pack with same-session screenshots/logs/report

**Success signal**
主管或产品看一条 session，就能明显感受到“客户是在做真实业务追问”，而不是模板式陪聊。

**Depends on**
- M003/S04

---

# 7. M004 — 复盘与学习闭环增强

## 7.1 User Problem

当前 report / replay / highlights 已经存在，但对用户来说，离真正“学得会”还差几步：

- 报告知道主问题，不代表用户知道是**哪一轮、哪一句、为什么错**。
- replay 能回放，不代表用户知道**哪些时刻最值得复看**。
- 看完报告后，下一练要练什么、怎么练、从哪个 Persona / 场景开始，系统还缺足够直接的入口。

## 7.2 Desired User Outcome

- 用户从 report 可以直接跳到关键时刻、看到更优说法、马上开始“只练这一个主问题”的下一练。
- highlights 不只是“好/坏片段”，而是可以服务具体学习动作。
- PPT 训练也能形成页级学习闭环，而不是只有一张总报告。

## 7.3 System Capability Outcome

- unified evidence 不只服务判断，还服务“把判断落到可复盘、可再练的最小学习动作”。
- report、replay、highlights、retry entry 共享同一 issue/goal vocabulary。
- sales 与 presentation 都有自己的学习闭环，但不分叉事实源。

## 7.4 Done Means

- report 能一键跳到 replay 中最关键的几处片段。
- highlights 有“为什么重要 / 更好说法 / 与主问题的关系”。
- 从 report 可以直接发起一次针对 main_issue / next_goal 的再练。
- PPT 报告支持页级问题聚合与针对性复练入口。

## 7.5 Slices

### M004/S01 — Highlight 与 timeline 质量升级

**Goal**
把高光片段从“可展示”升级为“可学习”。

**Evidence from repo**
- `backend/src/common/conversation/storage.py` 已支持 `mark_highlight()`。
- `backend/src/common/conversation/replay.py` 已返回 highlights、timeline markers、suggested better response。
- `web/src/components/highlights/*` 已有 UI 骨架。

**Likely files / modules**
- `backend/src/common/conversation/storage.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/api.py`
- `web/src/components/highlights/HighlightCard.tsx`
- `web/src/components/highlights/HighlightDetailModal.tsx`
- `web/src/components/highlights/HighlightList.tsx`

**Tasks**
- **T01**：扩展 highlight taxonomy，不再只停留在 good/bad，而是区分 evidence gap、objection miss、recovery win、next-step push 等学习语义。
- **T02**：为 bad highlight 固化“为什么是坏点 / 更好说法 / 对应主问题”的结构化字段。
- **T03**：让 replay timeline marker 与 highlight 共享同一 label 体系，不再两套解释。

**Smallest credible slice**
先做 sales；presentation 的 highlight taxonomy 可在 M004/S04 补齐。

**Validation plan**
- replay/highlight unit tests
- contract tests for stable replay response
- highlight UI focused tests

**Success signal**
用户看到一个高光片段时，不需要自己猜“为什么重要”。

**Depends on**
- M003/S04

---

### M004/S02 — Report ↔ Replay 深链路

**Goal**
让报告上的主问题、下一目标、关键证据能直接跳转到 replay 中的对应位置。

**Evidence from repo**
- report page 已加载 unified report / enhanced report / highlights。
- replay page 已有 stage summary / aligned coach conclusion，但还缺与 report 的强锚点。

**Likely files / modules**
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/session-evidence.ts`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/api/practice.py`

**Tasks**
- **T01**：为 report 中的 main_issue / next_goal / key evidence 建立 replay deep-link anchor（turn / marker / stage）。
- **T02**：在 replay 页补“为什么系统得出这个结论”的聚合视图，而不只是一条结论卡。
- **T03**：保证 sales / presentation 两种 scenario 都走统一 deep-link 机制，只在展示文案上分支。

**Smallest credible slice**
先打通 sales report → replay → highlight detail，一条主问题链路就够。

**Validation plan**
- report/replay focused web tests
- replay service / session-evidence integration tests
- browser UAT from report CTA to replay anchor

**Success signal**
用户在报告里点“查看关键片段”，能立即落到那一句附近，而不是重新手工找整段回放。

**Depends on**
- M004/S01

---

### M004/S03 — 针对主问题的再练入口

**Goal**
看完报告之后，用户可以直接发起一轮“围绕当前 main_issue / next_goal 的下一练”，而不是回首页重新选。

**Evidence from repo**
- report page 已有 retry affordance。
- dashboard agent page / session create API 已存在。
- presentation 已有 `presentation_id` continuity 入口，说明“带上下文再练”已有 precedent。

**Likely files / modules**
- `backend/src/common/api/practice.py`
- `backend/src/common/api/training.py`
- `backend/src/training_runtime/service.py`
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`

**Tasks**
- **T01**：定义 retry intent payload：包含 target issue、goal、recommended persona / scenario / material snapshot。
- **T02**：从 report / replay 发起“只练这一点”的新 session，并把来源上下文冻进 snapshot。
- **T03**：在新练习页显式展示“这轮是针对上次哪个问题的复练”，形成学习连续性。

**Smallest credible slice**
先做 sales report → new sales session；presentation continuity 复用既有机制后补。

**Validation plan**
- practice create contract tests
- report CTA web tests
- browser UAT：从 report 发起复练并看到 carry-forward focus

**Success signal**
用户完成报告后，下一步动作是“再练”，而不是“退出页面”。

**Depends on**
- M004/S02

---

### M004/S04 — PPT 页级学习闭环

**Goal**
把 presentation 报告从“总分 + 总结”推进到“页级问题聚合 + 针对性复讲”。

**Evidence from repo**
- `presentation_report_service.py` 已有 page-aware evidence 基础。
- `report/page.tsx` 已支持 presentation branch。
- `SlideViewer.tsx` 已有 slide progress UI。

**Likely files / modules**
- `backend/src/presentation_coach/services/presentation_report_service.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/replay.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/components/practice/presentation/SlideViewer.tsx`
- `web/src/lib/session-evidence.ts`

**Tasks**
- **T01**：把 PPT issue 聚合到 page / section 级，区分“讲偏、漏讲、展开过多、页间衔接差、问答处理弱”等问题簇。
- **T02**：在 report/replay 中支持按页查看关键问题与对应证据。
- **T03**：补“从第 N 页开始复讲”或“针对该问题再练一次”的入口，而不是每次从头练整份 deck。

**Smallest credible slice**
先支持 report 中的 page-level issue cluster + replay anchor，不急着做复杂的 partial session resume。

**Validation plan**
- presentation report unit/integration tests
- report page focused tests for PPT branch
- browser UAT using page-aware session evidence

**Success signal**
PPT 用户能明确知道“问题集中在哪几页”，而不是只拿到一段总评。

**Depends on**
- M004/S01

---

### M004/S05 — 学习闭环终验

**Goal**
证明 M004 真正提升了“学得会”的概率，而不是只多了几个页面元素。

**Likely files / modules**
- `backend/tests/integration/test_practice_evidence_flow.py`
- `backend/tests/unit/test_replay_service.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/components/highlights/*`
- UAT artifacts under `.gsd/` or `docs/plans/`

**Tasks**
- **T01**：建立 report → replay → re-practice regression net。
- **T02**：跑一条 sales 与一条 presentation 的真实学习路径 UAT。
- **T03**：收口最终学习 KPI：关键片段点击率、复练触发率、复练前后同 issue family 改善信号。

**Validation plan**
- focused backend + web suites
- browser/live UAT for both scenarios
- manual checklist proving one-click learning flow works end-to-end

**Success signal**
一名用户无需人工指导，也能从“看报告”自然走到“看关键片段”再走到“针对性复练”。

**Depends on**
- M004/S03
- M004/S04

---

# 8. M005 — 后台治理与规模化运营

## 8.1 User Problem

主管和运营侧已经能看见很多数据，但还不够形成稳定的组织动作：

- analytics 仍可能跟当前 sales semantics 漂移。
- intervention 还不是完整工作流。
- 资产管理页面已存在，但缺“变更影响 / rollout safety / 审计追踪”闭环。

## 8.2 Desired User Outcome

- 主管在系统里不仅能看见问题，还能指定训练重点、提醒、追踪、判断是否改善。
- 运营能知道哪个 Persona / 哪套材料 / 哪个 runtime 配置在帮助或伤害训练质量。
- 管理分析与 learner report 是同一语言，不再各说各话。

## 8.3 System Capability Outcome

- 管理面全部读 unified evidence / current sales semantics，而不是 legacy weighted formulas。
- intervention 有持久化记录、状态流转、成功定义。
- 资产治理具备 impact preview、audit trail、release-health linkage。

## 8.4 Done Means

- admin analytics / leaderboard / intervention lists 与当前 report/progress 使用同一套语义。
- 管理动作至少支持：指定重点、提醒、查看状态、确认是否改善。
- 知识库 / Persona / PPT / voice runtime 的关键变更能追溯、能看影响面、能看 rollout 风险。

## 8.5 Slices

### M005/S01 — 管理分析 semantic alignment

**Goal**
先把 admin analytics 从 legacy weighted formula 拉回到当前 evidence semantics，否则后续所有治理都会建立在漂移数据上。

**Evidence from repo**
- `backend/src/common/analytics/admin_analytics_service.py` 仍直接用 `logic*0.4 + accuracy*0.3 + completeness*0.3` 计算总分。
- 这与 M001/M002 已经建立的 sales-first issue/goal/evidence 读线存在天然张力。

**Likely files / modules**
- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/admin/api/analytics.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/conversation/session_evidence.py`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/lib/api/types.ts`

**Tasks**
- **T01**：把 overview / trends / leaderboard 改为读 projection-backed, scenario-aware semantics，而不是旧 weighted score。
- **T02**：补 issue-family / next-goal / evaluability / degradation-aware 指标，让管理面语言与 report/progress 一致。
- **T03**：同步更新 admin analytics UI 与导出字段，避免前后端一个说“平均分”、一个说“主问题家族”。

**Smallest credible slice**
先替换 leaderboard / overview 的事实来源，再扩趋势与导出。

**Validation plan**
- admin analytics service unit tests
- analytics API contract tests
- admin analytics page focused tests

**Success signal**
主管在 analytics 页面看到的结论，不会与 `/practice/{sessionId}/report` 和 `/admin/users/{id}/progress` 冲突。

**Depends on**
- M003/S04（最好）
- 若必须提前做，只能先做 projection source 替换，不做新语义扩张

---

### M005/S02 — Manager action loop 成形

**Goal**
把当前 manager-lite intervention 从“可调用接口”做成“产品内闭环动作”。

**Evidence from repo**
- `backend/src/admin/api/interventions.py` 已有 `/lists` 与 `/remind`。
- 但 `/remind` 目前只写 log，没有 intervention record、状态机、前端 UI。

**Likely files / modules**
- `backend/src/admin/api/interventions.py`
- `backend/src/common/db/models.py`
- `backend/src/common/db/schemas.py`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`

**Tasks**
- **T01**：引入 intervention record（focus、note、due_at、status、resolved_by_session_id）。
- **T02**：在 admin users detail/list 中加入“指定下一轮重点 / 发送提醒 / 查看进行中 interventions”的 UI。
- **T03**：定义 intervention success signal：之后若用户完成相应 issue family 的有效训练并改善，记录自动关联为 resolved / improved。

**Smallest credible slice**
先支持“设置训练重点 + 记录状态 + 在用户详情页查看”，不急着做跨团队 bulk actions。

**Validation plan**
- intervention API unit/integration tests
- admin users page focused tests
- browser UAT on assigning and resolving one focus item

**Success signal**
主管第一次可以在系统里完成“看见问题 → 指定下次练什么 → 之后回来确认有没有改善”。

**Depends on**
- M005/S01

---

### M005/S03 — 团队 / cohort 视角

**Goal**
从“单人连续变化”扩到“团队是否在进步、哪类问题最常见、哪些 Persona / 材料配置最有效”。

**Evidence from repo**
- admin analytics / users 页面已存在。
- API client 已支持 users、stats、progress、analytics 多条读线。
- 但缺组织级问题聚合与 cohort compare。

**Likely files / modules**
- `backend/src/admin/api/analytics.py`
- `backend/src/admin/api/users.py`
- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/common/analytics/history_service.py`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/lib/api/types.ts`

**Tasks**
- **T01**：增加 department / cohort / scenario / persona filters，输出 issue-family aggregation 与 not-evaluable/degraded breakdown。
- **T02**：把“最近总卡在哪”从单人扩展到团队层级，给主管真正可执行的 group focus 建议。
- **T03**：加入 asset usage correlation：哪些 Persona / knowledge base / presentation version 与通过率提升或退化相关。

**Smallest credible slice**
先把 cohort issue buckets 做出来，不急着做复杂对比图谱。

**Validation plan**
- analytics aggregation tests
- admin analytics page focused tests
- export contract tests for new grouped fields

**Success signal**
主管不必点进每个人，先看团队就能知道“最近该统一练哪类问题”。

**Depends on**
- M005/S01
- M005/S02（推荐，但不强制）

---

### M005/S04 — 资产治理与 rollout safety

**Goal**
把知识库、Persona、PPT、voice runtime 等资产变更从“能修改”提升到“可审计、可看影响、可控 rollout”。

**Evidence from repo**
- admin knowledge / personas / presentations / voice-runtime 页面都已存在。
- `support/runtime` 已能看 release health。
- 但变更链还缺 impact preview、审计面板、回滚提示与 active usage 关联。

**Likely files / modules**
- `backend/src/agent/services/persona_service.py`
- `backend/src/common/knowledge/api.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/src/support/services/runtime_status_service.py`
- `web/src/app/admin/knowledge/page.tsx`
- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/presentations/page.tsx`
- `web/src/app/admin/voice-runtime/page.tsx`

**Tasks**
- **T01**：统一“变更影响预览”：显示哪些 active sessions / default profiles / agents / personas / materials 会受影响。
- **T02**：引入 asset audit trail：谁在什么时候改了什么，变更前后差异是什么。
- **T03**：把 release-health 与 asset governance 连起来：当 rollout 后某类 anomaly 上升，support/runtime 能回指最近变更面。

**Smallest credible slice**
先覆盖 voice runtime + knowledge + presentation 三条最影响训练质量的资产线。

**Validation plan**
- admin API contract tests
- runtime status integration tests
- browser UAT on impact preview / rollback hint

**Success signal**
运营改配置时，不再只能“改完观察”，而是先知道影响面，出问题后也能追到最近哪次变更。

**Depends on**
- M005/S01

---

### M005/S05 — 管理闭环终验与对外边界

**Goal**
在不提前做深外部集成的前提下，形成一个可运营、可导出、可审计的团队管理闭环。

**Likely files / modules**
- `backend/src/admin/api/analytics.py`
- `backend/src/admin/api/training_records.py`
- `backend/src/admin/api/system_logs.py`
- `backend/src/admin/api/interventions.py`
- `web/src/app/admin/analytics/page.tsx`
- `web/src/app/admin/users/page.tsx`
- `web/src/lib/api/client.ts`

**Tasks**
- **T01**：收口 canonical export package：团队 issue buckets、intervention 状态、asset version references、degraded/not-evaluable counts。
- **T02**：补权限与审计检查，确保 supervisor / admin 访问边界与导出边界清楚。
- **T03**：形成“可对接外部系统的 boundary contract”，但不直接做 CRM / SSO integration。

**Validation plan**
- export contract tests
- auth/permission tests
- 管理侧 live UAT：从 analytics → user detail → intervention → export 走完一条线

**Success signal**
主管与运营可以在系统里完成主要管理动作；如果未来要接外部系统，也已有稳定边界可用。

**Depends on**
- M005/S02
- M005/S03
- M005/S04

---

## 9. Cross-Milestone Dependency Map

### Hard dependencies
- **M002/S07 + S08 → M003 all**
- **M003/S04 → M004/S01-S03**（否则学习闭环会建立在不够真的 truth line 上）
- **M003/S04 → M005/S01**（否则管理分析会再次产生语义漂移）

### Soft dependencies
- **M004/S01 → M005/S02**
  - manager action loop 会更有力，因为主管能引用 highlight / replay deep-link 作为具体证据。
- **M004/S03 → M005/S02**
  - intervention 最终最好能直接关联“下次复练入口”。
- **M005/S04 → M003/M004 持续迭代**
  - 资产 rollout safety 会反过来降低 Persona / knowledge / runtime 迭代风险。

---

## 10. Immediate Next 5 Safe Execution Candidates

> 前提：先关闭 M002/S07-S08。以下候选是“Gate 0 之后”的优先顺序。

### Candidate 1 — M003/S01/T01-T03 Persona 压力模型 authority line
- **为什么现在做**：这是 M003 后续所有真实性工作的 authority seam。
- **风险**：中等；主要风险在 schema migration 与 admin form 复杂度。
- **验证最直接**：单测 + admin focused tests + session snapshot assertion。

### Candidate 2 — M003/S02/T01 objection-aware evidence bundle
- **为什么现在做**：最直接影响用户体感；没有这条线，AI 客户很难显得真的懂业务。
- **风险**：中等；主要是 retrieval heuristics churn。
- **验证最直接**：price / competitor / ROI focused tests。

### Candidate 3 — M005/S01/T01 admin analytics projection alignment
- **为什么现在做**：现有 admin analytics 的 legacy weighted line 是明显 drift 风险，且修复后会降低后续管理功能的语义债务。
- **风险**：中等偏低；是安全且高杠杆的 read-side 工作。
- **验证最直接**：service + API + admin analytics focused tests。

### Candidate 4 — M004/S01/T01-T03 highlight/timeline 学习语义升级
- **为什么现在做**：可以把现有 replay/highlight 骨架尽快变成真正可学习的资产。
- **风险**：中等偏低；主要是 taxonomy 设计要避免过度复杂。
- **验证最直接**：replay/highlight focused tests。

### Candidate 5 — M003/S03/T01 unresolved objection ledger
- **为什么现在做**：这是让 Persona 像真实客户而不是短记忆机器人 的关键切片。
- **风险**：中等偏高；涉及 reconnect/persistence/state restore。
- **验证最直接**：handler persistence + same objection across turns integration tests。

---

## 11. Anti-Goals

- 不做第二条评分/事实线去服务 admin analytics 或学习产品。
- 不为了“更像平台”提前做 CRM / SSO / 企业微信深集成。
- 不新增一堆学习中心、排行榜、运营页面去掩盖训练真实性不足。
- 不做大规模 websocket 架构重写；优先沿用现有 classic / StepFun shared seam。
- 不把 Persona 复杂度堆成不可运营的 prompt 模板仓库；始终要求 schema、snapshot、audit、UAT 四件套一起成立。

---

## 12. Final Recommendation

M003-M005 的正确节奏不是“先把后台和学习页面做丰富”，而是：

1. **先让训练对象更真实（M003）**
2. **再让学习闭环更直接（M004）**
3. **最后把管理与治理做强（M005）**

如果必须在 M003 之前抽一个最小 read-side 债务清理项，唯一值得提前做的是：

> **M005/S01：admin analytics semantic alignment**

因为它能减少后续所有管理决策的语义漂移，而且不会破坏当前 runtime contract。

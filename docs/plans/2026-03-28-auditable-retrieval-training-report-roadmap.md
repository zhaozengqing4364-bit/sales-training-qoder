# 审计录音 × 检索命中 × 训练效果 × 报告可信 — Focused Roadmap

**Date:** 2026-03-28  
**Scope:** 以“知识库 → 检索 → 训练 → 录音可审计 → 报告可信”作为后续第一优先主线，先把这条事实链跑扎实，再扩主管闭环、PPT realtime interruption、移动端和外部集成。

---

## 1. 新优先级结论

后续工作不再优先从“更多管理动作”或“更多场景扩展”开始，而是先把下面这条核心链路做成**可证明、可抽查、可复盘**：

> **知识库准备好 → 训练时真实发生检索 → 检索结果真实影响训练内容 → 每次录音都可审计 → 报告能引用真实证据、解释问题来源**

这条链如果不硬：
- 知识库会变成“配置上存在，但训练中没效果”
- 录音会变成“能播但不可追责、不可抽查”
- 报告会变成“结论看起来对，但说不清证据来自哪里”

所以接下来应该优先做的，不是更多页面，而是把**训练事实线**从资产准备一直打通到报告引用。

---

## 2. 目标不是“功能更多”，而是“事实更硬”

### 要达成的用户结果

1. 管理员知道知识库是否真的进入了训练，而不是只显示 ready。
2. 学员一次训练结束后，录音和 transcript 能被抽查，知道某一段话到底说了什么。
3. 报告里的问题、建议、证据状态，能够回溯到：
   - 哪段录音 / transcript
   - 哪次检索
   - 哪条知识命中 / 没命中
4. 如果知识库没有起作用，系统能明确告诉你：
   - 是没检索到
   - 检索到了但没被使用
   - 使用了但证据仍不足
   - 报告降级了但原因清楚

### 系统能力目标

这不是单点功能，而是四层事实线要统一：
- **asset readiness truth**
- **retrieval truth**
- **audio/transcript audit truth**
- **report evidence truth**

---

## 3. 推荐里程碑顺序

## M008 — 检索事实链收口（最高优先）

### 用户问题
现在最大的怀疑不是“有没有知识库”，而是：**知识库到底有没有在训练里真正起作用。**

### 目标结果
系统必须能明确证明：
- 当前 session 用的是哪几个 knowledge base
- 这一轮是否真的发生检索
- 检索命中了什么类型内容
- 命中结果是否进入了训练推理 / 反馈 / 报告

### 核心交付
1. **session 级 retrieval ledger**
   - 每次训练保存可审计检索记录：query、命中条数、候选来源、最终命中片段摘要、失败原因。
2. **knowledge-check 强化**
   - 从现在的 status 面扩成更可解释的 retrieval audit 面。
3. **report 引用 retrieval facts**
   - 报告里能显示“本次知识支持充分/不足”的依据，不再只是抽象结论。
4. **训练中检索失败分类**
   - `kb_not_ready`、`search_failed`、`miss`、`hit-but-weak`、`hit-used` 这些语义继续细化并在 learner/admin/report 保持一致。

### 可能涉及文件
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/sales_bot/services/voice_runtime_policy.py`
- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/agent/services/persona_policy.py`
- `backend/src/common/knowledge/*`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/lib/api/client.ts`

### 成功信号
一个真实 session 可以明确回答：
- 这次检索有没有发生
- 命中了什么
- 命中有没有影响训练判断
- 报告为什么说 evidence weak / pending / verified

---

## M009 — 录音审计链收口

### 用户问题
你提到“每次录音都要可审计”，这意味着现在的音频/转写/回放还不够像审计资产，而更像训练过程副产物。

### 目标结果
每一次训练录音都应该满足：
- 可定位到 session / turn / timestamp
- 可回放
- 可和 transcript 对齐
- 可和 report / replay 的关键判断互相引用
- 出问题时可抽查“原始语音 vs transcript vs coach 结论”

### 核心交付
1. **录音审计主键设计**
   - session_id / turn_id / timestamp / speaker / storage pointer / transcript linkage
2. **录音-转写对齐面**
   - 至少支持 turn 级或时间段级定位
3. **审计保真元数据**
   - 音频是否缺段、转写是否不完整、是否 fallback、是否有 websocket 中断
4. **replay/report 可钻取到录音证据**
   - 报告某个问题时，能落到那段 transcript/录音，而不是只给结论

### 可能涉及文件
- `backend/src/common/conversation/replay.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/api/practice.py`
- `backend/src/training_runtime/*`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/lib/api/types.ts`
- 相关 `ConversationMessage` / transcript metadata 持久化链

### 成功信号
随机抽一条训练记录，可以从 report/replay 反查到：
- 具体哪段录音
- 对应 transcript 内容
- 该段为什么被判为主问题 / 证据不足 / 表达不准

---

## M010 — 报告证据链收口

### 用户问题
“报告有问题”的本质通常不是文案不好，而是：**报告结论和底层事实链没有完全对上。**

### 目标结果
报告里的每个重要结论都能回答：
- 它引用了哪段训练事实
- 依赖了哪类检索证据
- 为什么是这个 main_issue / next_goal
- 如果降级，是哪一层降级

### 核心交付
1. **报告证据引用模型**
   - 问题 / 建议 / claim truth / evidence completeness 都能挂引用来源
2. **降级原因可见化**
   - 检索没命中、音频缺失、转写不完整、enhanced report 失败，要分层呈现
3. **report / replay / knowledge-check 文汇统一**
   - 同一问题家族不要在三处换词
4. **report 的“错因”与“建议”必须可验证**
   - 不是只看 prompt 产出，而是看统一 evidence/projection 线

### 可能涉及文件
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/evaluation/services/*`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/lib/session-evidence.ts`
- `web/src/lib/api/types.ts`

### 成功信号
同一条 session：
- report、replay、knowledge-check 的问题家族一致
- 报告关键判断能落到具体 transcript / retrieval / audio evidence
- 报告不再只是“像对”，而是“能解释为什么对”

---

## 4. 这三段之间的依赖关系

### M008 先于 M009 / M010
因为如果检索事实线不清楚，后面的录音审计和报告可信都会失焦。

### M009 支撑 M010
因为报告可信不是只有检索；还要能反查到录音和 transcript 本身。

### M010 是前两者的用户可见出口
最终用户/主管看到的是报告，所以 report 必须把前两条事实线变成可理解的输出。

---

## 5. Immediate next 5 safe execution candidates

### GROW-001（推荐先做）
**Session-level retrieval ledger 最小化**
- 目标：让一次训练能被证明“真的检索过什么”
- 最小改动：补 retrieval audit 数据结构 + knowledge-check/read-side 输出
- 验证：真实 session proof + focused backend contract/integration

### GROW-002
**Report 引用 retrieval 证据而不是只给 evidence 结论**
- 目标：报告能显示证据支持来自哪里
- 最小改动：先做 sales report，不扩全场景
- 验证：report/replay parity + browser proof

### GROW-003
**录音审计元数据主线化**
- 目标：把音频从“可播”升级成“可审计”
- 最小改动：先做 session/turn/timestamp linkage，不急着做复杂检索 UI
- 验证：一条 session 的 audio-transcript-report cross-check

### GROW-004
**knowledge-check 从状态面升级为审计面**
- 目标：让 admin/learner 看得出检索是否真的起作用
- 最小改动：保留现有 route，不新开 debug page
- 验证：真实 knowledge hit / miss / fail 分类 proof

### GROW-005
**主链路 smoke：知识库 ready → 训练检索 → 报告引用证据**
- 目标：一键证明核心事实链没有断
- 最小改动：围绕 shipped route family 做 smoke，而不是全仓大而全验证
- 验证：clean-shell smoke + artifact export

---

## 6. 明确不该先做的事情

在这条主线做完前，**不建议优先**：

1. 先做大而全主管任务系统（R017 完整版）
2. 先做 PPT realtime interruption 全量落地（R016 全量版）
3. 先做移动端 / 企业微信（R018）
4. 先做 CRM / SSO / 外部系统集成（R019）
5. 新开第二套 debug 控制台或审计控制台

原则：
> **优先让现有 route family 说清楚事实，不先扩新 surface。**

---

## 7. 建议的下一步

### 推荐现在立刻进入的第一项
**M008 / S01 — Session-level retrieval ledger 最小化**

#### 要解决的最小问题
回答清楚：
- 这场训练到底有没有检索
- 检索到了什么
- 检索结果有没有进入后续训练/报告判断

#### 为什么它最先做
因为这是你刚刚明确提出的核心痛点：
> 现在报告有问题，本质上是知识库 → 检索 → 训练这条链没有被证明真的起作用。

这项一旦做实，后面的录音审计和报告可信才会有真正锚点。

---

## 8. 最终判断

如果按你刚刚给的方向重新排优先级，那么后续路线应该从：

**“主管闭环优先”**

调整为：

**“检索事实链优先 → 录音审计链 → 报告证据链 → 再扩主管闭环/实时纠偏”**

这是更像专家会做的顺序，因为它先修的是：
- 事实源
- 可审计性
- 证据可信度

而不是先修表层 workflow。

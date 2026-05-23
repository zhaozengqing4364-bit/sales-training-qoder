# 体验「严谨、可理解」— 六域只读分析综合（2026-05-21）

> 来源：6 路只读子代理（实时连接、用户旅程、管理后台、L2 契约、会话组装、可观测性）。**未改代码**。

---

## 1. 总判断

系统在**工程容错**上已明显优于「只靠 WebSocket 重连」：有 `RuntimeGate`、运行预检、fatal close 码、`PracticeFaultPanel`、KB 锁 Terminal 话术、管理员知识库诊断等。

离产品要求的「严谨、可理解」仍差**一层统一叙事**：

| 缺口类型 | 表现 |
|----------|------|
| **契约滞后** | Runnable/预检/考官 WS 已实现，L2 未文档化；错误码 `[]` vs bare、LEGACY 双命名 |
| **权威分裂** | `PracticeSessionCreateService` vs `ExaminerSessionAssembler` vs 销售 WS 局部校验 |
| **诊断晚于练时** | 考官绑定、题库空、CIO 模板快照 — 管理端/UI 不可编排，学员开考或连上后才爆 |
| **用户叙事弱** | 多指示灯并行；故障条混运维语言；学员看不到 failure_class / trace_id |
| **静默偏差** | 学习路径 → Agent 页无 `practice_template_id` → 可连但场景不像 CIO 设计 |

**综合成熟度（1–5，六域均值）≈ 3.2**

| 域 | 分 | 一句话 |
|----|-----|--------|
| 实时连接 / WS | 3.3 | Fatal 握手好；in-band 与连接故障混用；环境 Terminal 晚 |
| 用户演练旅程 | 3.5 | 非阻塞做得好；缺单一阶段线 |
| 管理后台 | 3.0 | 发布门控强；闭环 FK 与四阶段 UI 缺失 |
| L2 契约 | 2.8 | 实现超前于文档 |
| 会话组装 | 3.0 | 双权威 + 入口不等价 |
| 可观测性 | 3.4 | 应用内 trace 好；上游与降级事件弱 |

---

## 2. 五条根因（跨域）

1. **「有记录」≠「可运行」未产品化**  
   Create 常 optimistic `runnable`；完整 Gate 在 preflight/WS；CIO practice 可无 template 快照仍「能练」。

2. **失败分类只在 L0，未下沉 L2/UI**  
   Terminal / Transient / Voluntary 靠 close 码集合与连接态隐式推断；用户不知「该不该重连」。

3. **配置闭环在 Admin 不可见、在代码/种子里可见**  
   `learning_content_id`、`examiner_agent_id`、`curriculum_plan` 阶段 — 种子齐全，表单缺失。

4. **同一语义多条 code / 多条组装路径**  
   HTTP `[CODE]`、预检 bare、WS close；考官 vs 销售 vs PPT legacy 分叉。

5. **可理解性停在「有面板」，未做到「有主因 + 有下一步」**  
   故障堆叠、guidance 含 1006/uvicorn、无 incident_id、无 Learner/Admin 受众拆分。

---

## 3. 统一改进路线图（按 ROI，非实现清单）

### P0 — 契约与真相源（先写清再改 UI）

| # | 动作 | 主要受益 |
|---|------|----------|
| P0-1 | 新增 L2：`runtime-preflight` + `curriculum-practice` 总册 + WS close 全集（4000/4412/4413） | 前后端、验收、Agent 协作 |
| P0-2 | 错误码注册表：`canonical_code` + `failure_class` + `user_zh` + `admin_action` + HTTP/WS 别名 | 监控、文案、不重连策略 |
| P0-3 | 文档化双权威与旁路表（seed、simulate、复训、Agent 直创） | Entry Parity 审计 |

### P0 — 闭环可运行前移（CIO / presales 优先）

| # | 动作 | 主要受益 |
|---|------|----------|
| P0-4 | 管理端模板表单：`learning_content_id`、`examiner_agent_id` + CurriculumPlan 阶段 Picker | 运营不配种子 |
| P0-5 | Checklist → Runnable 诊断（考官、题库、章节、TrainingTask） | 开考前暴露 |
| P0-6 | 学习路径「开始对练」带 `practice_template_id`（服务端解析，不信任客户端省略） | 消除静默偏差 |
| P0-7 | `RuntimeGate` 纳入 STEPFUN 密钥/上游；create 与 preflight/WS 同一检查集 | 环境 Terminal 不前移 |

### P0 — 用户可理解（少改后端也可做）

| # | 动作 | 主要受益 |
|---|------|----------|
| P0-8 | 练习页：**阶段 Stepper**（准备→连接→可说话→演练中→报告） | 3 秒内知「点哪里」 |
| P0-9 | 故障面板：**主因一条** + `auth|config|network|device` + 折叠技术详情 | 停止 1006/3444 误导 |
| P0-10 | Terminal 文案模板：现象 / 你可做 / 管理员需做（4410/4411/预检 blocked） | 归因边界 |

### P1 — 架构收敛（分期）

| # | 动作 |
|---|------|
| P1-1 | `SessionAssemblyFacade`（intent 枚举 + 统一 `SessionAssemblyResult`） |
| P1-2 | 销售 WS 调用完整 `RuntimeGate`；in-band error 与 connection fault 分通道 |
| P1-3 | 前端消费 `failure_class` + `user_action`；统一 practice/examiner transport |
| P1-4 | `VoiceInstructionCompiler` 可选注入 case_item/role_profile；报告优先 snapshot rubric |
| P1-5 | 演练页展示可复制 `trace_id` 短码；`runtime_events` 产品化 |
| P1-6 | Profile「最近练习」；练习 Header 展示 agent·角色名 |

### P2 —  polish / 退役

| P2-1 | PPT legacy 退役时间表；WEBSOCKET_DEBUG 实现或删文档 |
| P2-2 | ENABLE_TRACING 接 OTel；考官/管理 simulate 与学员路径隔离说明 |

---

## 4. 分域 Top 3（落地时抓重点）

### 学员侧
1. 阶段 Stepper + 上下文条（和谁练）  
2. 故障 Learner 版（非运维版）  
3. 鉴权 4001/401 专用路径（非「请重连」）

### 管理侧
1. 模板 exam 链字段 + 四阶段编辑器  
2. Runnable 诊断页（模拟 publish + assembler + gate）  
3. 课程闭环设置中心（不止模板列表底部 Checklist）

### 契约 / 后端
1. L2 与 `RuntimeGate` 单源  
2. create 失败即 4xx 或 `validated`，消灭 optimistic runnable  
3. 统一 `[CODE]` 与 bare alias 表

### 实时 / 连接
1. `failure_class` on wire  
2. 禁止用 1006 重试掩盖 Terminal  
3. `reconnected` 可见确认（非仅清 error）

---

## 5. 建议验收旅程（人工，六域各 1 条）

| ID | 旅程 | 通过标准 |
|----|------|----------|
| V1 | CIO：学习路径完成 → 开练（带 template）→ 预检绿 → WS 连上 → 角色话术含案例边界 | 无静默偏差；失败在预检非练中 |
| V2 | 模板未绑考官 → 管理端诊断红 → 学员 start-exam 409 文案可操作 | 不在 WS 4413 才首次发现 |
| V3 | 去掉 STEPFUN_API_KEY → create 或预检 Terminal | 不在连上后才 4000 |
| V4 | 断网 10s 恢复 → Transient 重连 → 明确「已恢复」 | 无阻塞弹窗；非 5 次空转 |
| V5 | 4410 KB 未绑定 → 不重连；文案指向管理员 | fatal 集合与 L2 一致 |
| V6 | 故障时复制 trace 短码 → 管理端 logs 能搜到同会话 | 学员/支持可关联 |

---

## 6. 与 Trellis `presales-cio-closed-loop` 对齐

| PRD 要求 | 综合结论 |
|----------|----------|
| study→exam→practice→report | 数据链种子完整；**practice 入口 parity 断裂** |
| 业务专家可配可验收 | 需 **Admin 一等字段 + Runnable 诊断**，少依赖 `--verify-only` 种子 |
| 严谨 | 后端门控已有；缺 **统一 Gate + L2 + 无 template 不可标 runnable** |
| 可理解 | 面板有；缺 **Stepper + failure_class + 受众拆分文案** |

**建议任务顺序**：P0-4～P0-6（闭环配置与入口）→ P0-1～P0-2（契约）→ P0-8～P0-10（学员叙事）→ P1 架构。

---

## 7. 子代理报告索引

| 域 | task_id（供内部追溯） |
|----|----------------------|
| 实时连接 | adc90bc8-df46-40ad-a886-5a5e637a3102 |
| 用户旅程 | 4619b605-7d62-4656-ad84-f82f6c581cab |
| 管理后台 | 59757dc7-4ee1-45de-9de0-2d6062be1724 |
| L2 契约 | 3cc00356-fe93-476f-b7b6-a09c5bba8723 |
| 会话组装 | 15aa1092-1cb4-43fe-8f2e-eb2cea3793d0 |
| 可观测性 | 11d202c7-474e-47b7-8f17-554e31737cbd |

---

## 8. 刻意不做（本轮分析边界）

- 不为了「可连」降低 Terminal 门槛  
- 不用连接层重试修鉴权/缺字段  
- 不在学员 UI 堆运维术语（1006、uvicorn、reload）  
- 不新增未登记旁路（继续靠种子绕 Admin 不算完成闭环）

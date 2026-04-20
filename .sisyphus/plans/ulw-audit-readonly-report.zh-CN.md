# ULW 只读多审计员审计与报告计划

## TL;DR

> **快速摘要**：在不改动代码的前提下，针对全部基线检查项（`AUDIT-001` ~ `AUDIT-029`）执行多审计员并行审计，要求证据链完整，最终输出经过“矛盾检查”的详尽报告。
>
> **交付物**：
> - `.agent/evidence/{RUN_ID}/audit-index.json`（机器可读证据索引）
> - `.agent/evidence/{RUN_ID}/audit-regression-matrix.md`（历史 P0/P1 回归验证矩阵）
> - `docs/audit-report-{RUN_ID}.md`（最终详尽审计报告）
> - 更新 `.agent/progress.md`（反映完成状态）
>
> **预计工作量**：Large
> **并行执行**：YES - 4 个波次
> **关键路径**：Task 0 -> Task 1 -> Task 3/4/5/6/7/8/9 -> Task 10 -> Task 11 -> Task 12

---

## 背景

### 原始诉求
用户要求组织多名审计人员对项目做审计测试，重点关注“扮演真人效果不足、奇怪 bug、功能缺失”，并明确要求不修改代码，最终输出详尽报告。

### 访谈结论
**关键共识**：
- 仅允许只读审计模式（不改源码、不做迁移、不做重构）。
- 复用 `.agent/tasks.json` 的固定基线（`AUDIT-001` ~ `AUDIT-029`）。
- 统一结论格式为 `PASS | FAIL | BLOCKED`，且必须可复现。

**调研发现**：
- 基线任务与证据要求已在 `.agent/tasks.json` 结构化定义。
- 既有报告 `docs/audit-report-2026-02-13.md` 仅作为历史输入，不可直接当作当前结论。
- 后端/前端/WS 脚本均存在可执行验证入口。

### Metis 复核结论
**识别到的缺口（已在本计划补齐）**：
- 缺少冻结目标信息（分支/SHA/时间戳）-> 增加强制预检冻结步骤。
- 旧结论复用风险 -> 增加历史风险回归矩阵。
- 范围蔓延风险 -> 硬锁定 `AUDIT-001` ~ `AUDIT-029`。
- 报告质量标准偏弱 -> 增加机器可读完整性校验 + 矛盾检查。

---

## 工作目标

### 核心目标
产出一份高置信度、证据驱动、只读执行的审计报告，覆盖 29 个基线审计任务，并清晰区分：已修复、回归、仍失败、受阻。

### 具体交付
- `AUDIT-001` ~ `AUDIT-029` 全量逐项结论。
- 每项证据包（命令、输出、代码引用、DB 引用、期望 vs 实际）。
- “角色扮演真实性”评分量表结果（人设一致性、挑战质量、阶段逻辑、评分连贯性）。
- 历史高风险回归矩阵（上一版报告 P0/P1）。
- 可复现的最终优先级修复队列（P0/P1/P2）。

### 完成定义
- [ ] 29 个审计 ID 全部且仅有一个最终结论与证据包。
- [ ] 每个 `FAIL` / `BLOCKED` 都有明确复现步骤与解除阻塞条件。
- [ ] 最终报告通过矛盾/完整性校验。
- [ ] 源代码文件零改动。

### 必须具备
- 严格只读执行纪律。
- 按模块解耦的并行审计分道执行。
- 机器可验证证据索引。
- 独立的“角色扮演真实性”评估章节。

### 明确禁止（护栏）
- 禁止实现、重构、依赖变更、迁移变更。
- 禁止复制旧报告中不可验证结论。
- 禁止无证据路径的报告段落。
- 禁止遗漏审计 ID。
- 禁止无限探索循环（单项失败最多 2 次重试，超限转 `BLOCKED`）。

### 默认规则
- 外部依赖不可用（StepFun/Aliyun/第三方）=> 记为 `BLOCKED`，不是 `FAIL`，并写明解除条件。
- 范围强锁：仅 `AUDIT-001` ~ `AUDIT-029`。
- 时限：每条审计分道“1 次全量 + 最多 2 次定向重试”。

---

## 验证策略（强制）

> **通用规则：零人工介入**
>
> 所有验收标准必须可由 Agent 通过命令/工具执行。禁止“人工目测/人工点击后口头确认”的验收。

### 测试决策
- **测试基础设施**：YES
- **自动化测试策略**：Tests-after（仅验证，不做功能实现）
- **工具栈**：pytest、Vitest、ruff、mypy、WebSocket 脚本、jq

### 证据标准
- 结论字段：`verdict`（`PASS|FAIL|BLOCKED`） + `passes`（`true|false`）。
- 证据根路径：`.agent/evidence/{RUN_ID}/`。
- 每条发现必须包含：
  - 执行命令
  - 输出产物路径
  - 代码引用（前端 + 后端 + DB/表）
  - 期望与实际
  - 置信度（`high|medium|low`）

### 全局命令基线
在相关任务中使用：
- 后端质量：`ruff check src/`、`mypy src/`、`pytest tests/unit/`、`pytest tests/contract/`、`pytest tests/integration/`
- 前端质量：`npm run lint`、`npm run test`、`npm run build`
- WebSocket 流程：`python test_websocket.py`、`python test_websocket_detailed.py`
- 完整性门禁：

```bash
jq '.tasks | length' .agent/tasks.json
# 期望: 29
```

```bash
jq -e '(.tasks|length==29) and all(.tasks[]; (.id|test("^AUDIT-[0-9]{3}$")) and (.verdict|test("PASS|FAIL|BLOCKED")) and (.passes|type=="boolean") and (.evidence.command|length>0) and (.evidence.code_refs|length>0))' \
  .agent/evidence/{RUN_ID}/audit-index.json
# 期望: exit code 0
```

---

## 执行策略

### 并行执行波次

```
Wave 1（基础准备）：
├── Task 0: 冻结审计目标 + 证据骨架初始化
└── Task 1: 建立 AUDIT-001 模板与任务注册表

Wave 2（并行审计分道）：
├── Task 2: 历史高风险回归扫查
├── Task 3: Lane A（AUDIT-002~008）
├── Task 4: Lane B（AUDIT-009~014）
├── Task 5: Lane C（AUDIT-015~020）
├── Task 6: Lane D（AUDIT-021~028）
├── Task 7: 角色扮演真实性深度审计
├── Task 8: 实时/WS 故障与延迟审计
└── Task 9: 合同/类型/DB 漂移审计

Wave 3（汇总）：
└── Task 10: 汇总证据到索引并输出报告草稿

Wave 4（收口）：
├── Task 11: 执行 AUDIT-029（优先级 + 复测矩阵）
└── Task 12: 矛盾/完整性门禁 + 发布报告
```

### 依赖矩阵

| Task | 依赖 | 阻塞 | 可并行对象 |
|------|------|------|------------|
| 0 | None | 1-12 | 1（仅准备） |
| 1 | 0 | 2-12 | None |
| 2 | 1 | 10-12 | 3,4,5,6,7,8,9 |
| 3 | 1 | 10-12 | 2,4,5,6,7,8,9 |
| 4 | 1 | 10-12 | 2,3,5,6,7,8,9 |
| 5 | 1 | 10-12 | 2,3,4,6,7,8,9 |
| 6 | 1 | 10-12 | 2,3,4,5,7,8,9 |
| 7 | 1 | 10-12 | 2,3,4,5,6,8,9 |
| 8 | 1 | 10-12 | 2,3,4,5,6,7,9 |
| 9 | 1 | 10-12 | 2,3,4,5,6,7,8 |
| 10 | 2-9 | 11-12 | None |
| 11 | 10 | 12 | None |
| 12 | 11 | None | None |

### 审计员分配矩阵

| 审计员 | 范围 | 主任务 |
|--------|------|--------|
| Auditor-A | 用户鉴权/首页/训练入口流程 | 3 |
| Auditor-B | 会话/回放/报告/历史/个人页 | 4 |
| Auditor-C | 支撑运行态 + 管理台核心页面 | 5 |
| Auditor-D | 管理域模块（智能体/角色/知识库/提示词/模型/语音） | 6 |
| Auditor-E | 角色扮演质量维度（人设/阶段/评分真实性） | 7 |
| Auditor-F | WebSocket/实时链路稳健性与延迟 | 8 |
| Auditor-G | 合同/类型/DB 一致性 | 9 |
| Consolidator | 索引/报告/优先级/复测/最终门禁 | 10,11,12 |

---

## TODO 列表

- [ ] 0. 冻结目标并创建证据骨架

  **要做什么**：
  - 将 branch、commit SHA、timestamp 写入 `.agent/evidence/{RUN_ID}/run-meta.json`。
  - 初始化证据目录与空 `audit-index.json` 骨架。
  - 写入 `BLOCKED` 分类策略。
  - 在 metadata 记录重试/时限策略（1 次全量 + 最多 2 次重试）。

  **禁止**：
  - 不改代码。
  - 不改数据库 schema。

  **推荐 Agent 配置**：
  - **Category**: `quick`（确定性初始化）
  - **Skills**: `verification-before-completion`, `Coding Standards`
  - **评估后不采用**: `test-driven-development`（本任务不实现功能）

  **并行信息**：
  - **可并行**：NO
  - **所属波次**：Wave 1
  - **阻塞**：1-12
  - **被阻塞于**：None

  **参考**：
  - `.agent/tasks.json`（审计范围与 ID 权威来源）
  - `.agent/progress.md`（进度同步目标）

  **验收标准**：
  - [ ] `run-meta.json` 包含 `branch`、`sha`、`run_id`、`started_at`。
  - [ ] `audit-index.json` 初始化为 29 个任务槽位。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 冻结目标元数据
    Tool: Bash
    Steps:
      1. git rev-parse --abbrev-ref HEAD
      2. git rev-parse HEAD
      3. date -u +"%Y-%m-%dT%H:%M:%SZ"
      4. 断言上述值全部写入 .agent/evidence/{RUN_ID}/run-meta.json
    Expected Result: 元数据文件存在且字段非空
    Evidence: .agent/evidence/{RUN_ID}/task-0-run-meta.json
  ```

  **Commit**: NO

- [ ] 1. 执行 AUDIT-001 模板化与注册表规范化

  **要做什么**：
  - 依据 `AUDIT-001` 建立可复用审计记录模板。
  - 统一 29 个任务的 verdict 与 evidence 字段结构。
  - 预填充 `.agent/evidence/{RUN_ID}/audit-index.json` 注册表。

  **禁止**：
  - 不改变 `.agent/tasks.json` 基线任务语义。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `verification-before-completion`
  - **评估后不采用**: `webapp-testing`（此步不跑 UI 运行态）

  **并行信息**：
  - **可并行**：NO
  - **所属波次**：Wave 1
  - **阻塞**：2-12
  - **被阻塞于**：0

  **参考**：
  - `.agent/tasks.json`（`AUDIT-001` 字段与证据规则）
  - `docs/audit-report-2026-02-13.md`（历史报告结构基线）

  **验收标准**：
  - [ ] `audit-index.json` 恰好 29 个条目，ID 为 `AUDIT-001`~`AUDIT-029`。
  - [ ] 每条均含 `verdict`、`passes`、`evidence.command`、`evidence.output_path`、`evidence.code_refs`。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 校验注册表完整性
    Tool: Bash
    Steps:
      1. jq '.tasks | length' .agent/evidence/{RUN_ID}/audit-index.json
      2. 断言输出为 29
      3. jq -e 'all(.tasks[]; has("id") and has("verdict") and has("passes") and has("evidence"))' .agent/evidence/{RUN_ID}/audit-index.json
    Expected Result: 完整性校验通过
    Evidence: .agent/evidence/{RUN_ID}/task-1-registry-validation.log
  ```

  **Commit**: NO

- [ ] 2. 历史 P0/P1 回归扫查

  **要做什么**：
  - 重新验证 `docs/audit-report-2026-02-13.md` 中历史高严重度问题。
  - 将每项标记为 `fixed`、`regressed`、`still failing` 或 `unverifiable`。
  - 输出到 `.agent/evidence/{RUN_ID}/audit-regression-matrix.md`。

  **禁止**：
  - 不得在无新证据下复用旧 verdict。

  **推荐 Agent 配置**：
  - **Category**: `deep`
  - **Skills**: `systematic-debugging`, `Code Reviewer`
  - **评估后不采用**: `frontend-ui-ux`（非设计任务）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `docs/audit-report-2026-02-13.md`（历史 P0/P1 来源）
  - `backend/src/presentation_coach/websocket/presentation_handler.py`（PPT 实时链路）
  - `backend/src/sales_bot/api/scenarios.py`（销售人设来源）
  - `backend/src/common/api/practice.py` + `backend/src/common/db/schemas.py` + `web/src/lib/api/types.ts`（字段映射风险）

  **验收标准**：
  - [ ] 回归矩阵覆盖全部历史 P0/P1。
  - [ ] 每行结论都附当前证据路径。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 历史问题重验
    Tool: Bash
    Steps:
      1. 从 docs/audit-report-2026-02-13.md 提取 P0/P1 清单
      2. 对每项执行定向测试/脚本
      3. 在回归矩阵写入新 verdict 与证据路径
    Expected Result: 无历史项处于“未分类”状态
    Evidence: .agent/evidence/{RUN_ID}/task-2-regression-matrix.md
  ```

  **Commit**: NO

- [ ] 3. Lane A 审计：AUDIT-002 ~ AUDIT-008

  **要做什么**：
  - 执行 auth/dashboard/training/agent 入口链路的 按钮->前端->API->DB 一致性核查。
  - 覆盖登录成功/失败与会话创建入口。

  **禁止**：
  - 无请求/响应证据时，不得对 UI 行为下结论。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `webapp-testing`, `systematic-debugging`
  - **评估后不采用**: `writing-skills`（非文稿创作任务）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `.agent/tasks.json`（AUDIT-002..008）
  - `web/src/app/(auth)/login/page.tsx`
  - `web/src/app/(dashboard)/page.tsx`
  - `web/src/app/(dashboard)/training/page.tsx`
  - `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
  - `backend/src/common/auth/api.py`
  - `backend/src/common/api/practice.py`

  **验收标准**：
  - [ ] `AUDIT-002..008` 每项都有 verdict + 复现 + 证据。
  - [ ] 会话创建链路包含 `agent_id/persona_id/voice_mode` 的持久化校验。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 登录与开始练习链路
    Tool: Bash + API checks
    Steps:
      1. 验证鉴权接口正确/错误凭据行为
      2. 触发练习会话创建并校验 payload
      3. 断言 API 返回与 DB 持久化一致
    Expected Result: AUDIT-002..008 完整证据化结论
    Evidence: .agent/evidence/{RUN_ID}/task-3-audit-002-008.md

  Scenario: 外部依赖不可用处理
    Tool: Bash
    Steps:
      1. 在分道检查中模拟外部依赖缺失
      2. 断言以 BLOCKED 记录并附解除条件
    Expected Result: BLOCKED 分类策略一致执行
    Evidence: .agent/evidence/{RUN_ID}/task-3-blocked-policy.log
  ```

  **Commit**: NO

- [ ] 4. Lane B 审计：AUDIT-009 ~ AUDIT-014

  **要做什么**：
  - 审计会话生命周期、回放/报告一致性、历史/排行榜/个人页逻辑。
  - 验证状态迁移与报告就绪行为。

  **禁止**：
  - 禁止仅靠人工阅读报告做结论。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `webapp-testing`, `verification-before-completion`
  - **评估后不采用**: `algorithmic-art`（无关）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `.agent/tasks.json`（AUDIT-009..014）
  - `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(dashboard)/history/page.tsx`
  - `web/src/app/(dashboard)/leaderboard/page.tsx`
  - `backend/src/common/api/practice.py`
  - `backend/src/common/conversation/replay.py`

  **验收标准**：
  - [ ] `AUDIT-009..014` 全部具备可复现证据。
  - [ ] FE/API/DB 状态迁移一致。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 会话生命周期与报告链路
    Tool: Bash + API checks
    Steps:
      1. 创建/获取会话
      2. 触发 pause/resume/end 生命周期动作
      3. 校验 replay/report 接口与状态一致性
    Expected Result: AUDIT-009..014 有证据支撑结论
    Evidence: .agent/evidence/{RUN_ID}/task-4-audit-009-014.md
  ```

  **Commit**: NO

- [ ] 5. Lane C 审计：AUDIT-015 ~ AUDIT-020

  **要做什么**：
  - 审计 support runtime 与 admin 核心页面（用户/记录/分析）。
  - 校验筛选、分页、导出、指标一致性。

  **禁止**：
  - 无查询/响应证据时，不得推断分析口径。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `systematic-debugging`
  - **评估后不采用**: `frontend-design`（非改版任务）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `.agent/tasks.json`（AUDIT-015..020）
  - `web/src/app/(dashboard)/support/runtime/page.tsx`
  - `web/src/app/admin/page.tsx`
  - `web/src/app/admin/users/page.tsx`
  - `web/src/app/admin/users/[id]/page.tsx`
  - `web/src/app/admin/records/page.tsx`
  - `web/src/app/admin/analytics/page.tsx`
  - `backend/src/admin/api/users.py`
  - `backend/src/admin/api/analytics.py`

  **验收标准**：
  - [ ] `AUDIT-015..020` 每项都有 endpoint + DB 一致性证据。
  - [ ] 导出与筛选行为都有“期望 vs 实际”证据。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 管理端分析与记录一致性
    Tool: Bash + API checks
    Steps:
      1. 执行 overview/trends/leaderboard 接口
      2. 比对指标与列表条目一致性
      3. 验证导出输出与当前筛选条件一致
    Expected Result: AUDIT-015..020 覆盖完成
    Evidence: .agent/evidence/{RUN_ID}/task-5-audit-015-020.md
  ```

  **Commit**: NO

- [ ] 6. Lane D 审计：AUDIT-021 ~ AUDIT-028

  **要做什么**：
  - 审计管理域模块：智能体、角色、知识库、演示文稿、提示词、模型配置、语音运行策略。
  - 验证状态流转与绑定持久化。

  **禁止**：
  - 禁止直接操作 DB 强行“做绿”。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `verification-before-completion`
  - **评估后不采用**: `theme-factory`（与本任务无关）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `.agent/tasks.json`（AUDIT-021..028）
  - `web/src/app/admin/agents/page.tsx`
  - `web/src/app/admin/agents/[id]/page.tsx`
  - `web/src/app/admin/personas/page.tsx`
  - `web/src/app/admin/personas/[id]/page.tsx`
  - `web/src/app/admin/knowledge/page.tsx`
  - `web/src/app/admin/presentations/page.tsx`
  - `web/src/app/admin/prompts/page.tsx`
  - `web/src/app/admin/settings/page.tsx`
  - `web/src/app/admin/voice-runtime/page.tsx`
  - `backend/src/agent/api/agents.py`
  - `backend/src/agent/api/personas.py`
  - `backend/src/agent/api/agent_personas.py`
  - `backend/src/common/knowledge/api.py`
  - `backend/src/admin/api/model_configs.py`
  - `backend/src/admin/api/voice_runtime.py`

  **验收标准**：
  - [ ] `AUDIT-021..028` 全部完成并有证据。
  - [ ] 绑定/状态流转对照任务定义中的 DB 表核验通过。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 智能体-人设-语音策略状态流
    Tool: Bash + API checks
    Steps:
      1. 查询智能体/人设绑定与语音策略数据
      2. 验证发布/下线/归档状态流转
      3. 验证持久化结果在列表/详情接口中的回显
    Expected Result: AUDIT-021..028 证据化结论
    Evidence: .agent/evidence/{RUN_ID}/task-6-audit-021-028.md
  ```

  **Commit**: NO

- [ ] 7. 角色扮演真实性深度审计（跨域）

  **要做什么**：
  - 使用明确量表评估“真人扮演效果”：
    - 每维评分：`1`（差） -> `5`（优）
    - 人设一致性
    - 挑战真实性与压力推进
    - 销售阶段一致性
    - 实时评分与对话叙事一致性
    - 语言一致性（中文/英文/混合）
  - 仅使用对话转录、评估产物和运行时输出证据。

  **禁止**：
  - 无转录片段证据不得评分。

  **推荐 Agent 配置**：
  - **Category**: `deep`
  - **Skills**: `learning-coach`, `Code Reviewer`
  - **评估后不采用**: `paper-xray`（非论文分析）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `backend/src/sales_bot/websocket/enhanced_handler.py`
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `backend/src/sales_bot/services/context_manager.py`
  - `backend/src/sales_bot/services/summary_service.py`
  - `backend/src/evaluation/services/staged_evaluation.py`
  - `backend/src/evaluation/services/realtime_scoring.py`
  - `backend/src/prompt_templates/service.py`
  - `web/src/components/practice/ScorePanel.tsx`
  - `web/src/components/practice/realtime-feedback.tsx`

  **验收标准**：
  - [ ] 量表评分有转录证据链接。
  - [ ] 每个维度包含 1-5 分、评分理由、转录片段引用。
  - [ ] 每类人设至少 1 个正样本与 1 个负样本。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 人设真实性评分
    Tool: Bash + transcript analysis pipeline
    Steps:
      1. 收集会话转录、阶段输出、评分输出
      2. 按量表逐维打分并写明理由
      3. 输出单案例证据与聚合总结
    Expected Result: 可直接纳入最终报告的真实性章节
    Evidence: .agent/evidence/{RUN_ID}/task-7-roleplay-rubric.md
  ```

  **Commit**: NO

- [ ] 8. 实时 WebSocket 故障/延迟审计

  **要做什么**：
  - 压测中断/重连/cancel/fallback 流程。
  - 验证实时消息顺序、持久化一致性、错误处理。
  - 运行 WS smoke + 详细脚本 + 定向集成测试。

  **禁止**：
  - 禁止隐式重试掩盖失败事实。

  **推荐 Agent 配置**：
  - **Category**: `deep`
  - **Skills**: `systematic-debugging`, `webapp-testing`
  - **评估后不采用**: `frontend-ui-ux`（仅行为审计）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `test_websocket.py`
  - `test_websocket_detailed.py`
  - `backend/tests/integration/test_websocket_status_contract.py`
  - `backend/tests/e2e/test_websocket_flow.py`
  - `backend/src/sales_bot/websocket/router.py`
  - `docs/api-contract/websocket.md`

  **验收标准**：
  - [ ] 故障场景有 verdict 与延迟证据。
  - [ ] `BLOCKED` 仅用于依赖受限且有证据。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: WebSocket 中断风暴
    Tool: Bash
    Steps:
      1. 运行 python test_websocket_detailed.py
      2. 解析 interruption/cancel/recovery 事件
      3. 断言消息顺序与最终状态一致
    Expected Result: 输出确定性 verdict 与日志证据
    Evidence: .agent/evidence/{RUN_ID}/task-8-ws-detailed.log

  Scenario: WS 冒烟基线
    Tool: Bash
    Steps:
      1. 运行 python test_websocket.py
      2. 采集通过率汇总
      3. 按根因桶分类失败项
    Expected Result: 冒烟结果可挂接到 audit index
    Evidence: .agent/evidence/{RUN_ID}/task-8-ws-smoke.log
  ```

  **Commit**: NO

- [ ] 9. 合同/类型/DB 漂移审计

  **要做什么**：
  - 校验后端 schema、API、前端类型之间命名与字段一致性。
  - 聚焦已知风险（`runtime_profile_id` 映射、leaderboard 字段兼容）。
  - 校验 API 合同文档与真实 payload 一致性。

  **禁止**：
  - 无 payload 证据不得下“漂移”结论。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `Coding Standards`
  - **评估后不采用**: `ui-ux-pro-max`（非样式任务）

  **并行信息**：
  - **可并行**：YES
  - **所属波次**：Wave 2
  - **阻塞**：10-12
  - **被阻塞于**：1

  **参考**：
  - `backend/src/common/db/models.py`
  - `backend/src/common/db/schemas.py`
  - `backend/src/common/api/practice.py`
  - `backend/src/admin/api/analytics.py`
  - `web/src/lib/api/types.ts`
  - `web/src/lib/api/client.ts`
  - `docs/api-contract/*.md`

  **验收标准**：
  - [ ] 每个漂移项包含合同引用 + payload 样本 + 风险等级。
  - [ ] 漂移结果已并入受影响审计 ID 的索引条目。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 运行时 profile 字段映射校验
    Tool: Bash + payload inspection
    Steps:
      1. 收集 session/report 样本 payload
      2. 对比各层内部/外部字段命名
      3. 记录 mismatch 或映射证据
    Expected Result: 输出明确 PASS/FAIL 映射结论
    Evidence: .agent/evidence/{RUN_ID}/task-9-contract-drift.md
  ```

  **Commit**: NO

- [ ] 10. 汇总分道结果到统一证据索引

  **要做什么**：
  - 将 Task 2-9 输出合并进 `audit-index.json`。
  - 确保每个 `AUDIT-XXX` 只有一个最终 verdict 且证据可追溯。
  - 以根因维度去重重叠问题。

  **禁止**：
  - 除非证据不同，不允许同类问题重复占多个条目。

  **推荐 Agent 配置**：
  - **Category**: `writing`
  - **Skills**: `Code Reviewer`, `verification-before-completion`
  - **评估后不采用**: `systematic-debugging`（已在上游分道执行）

  **并行信息**：
  - **可并行**：NO
  - **所属波次**：Wave 3
  - **阻塞**：11-12
  - **被阻塞于**：2-9

  **参考**：
  - `.agent/evidence/{RUN_ID}/task-*.md`
  - `.agent/evidence/{RUN_ID}/task-*.log`
  - `.agent/tasks.json`

  **验收标准**：
  - [ ] `audit-index.json` 通过 schema/完整性校验命令。
  - [ ] 审计 ID 无缺失、无重复。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 索引 schema 与完整性校验
    Tool: Bash
    Steps:
      1. 对 audit-index.json 执行 jq 完整性检查
      2. 断言 29 个 ID 存在且唯一
      3. 断言每条都有 verdict/passes/evidence 链接
    Expected Result: 校验退出码为 0
    Evidence: .agent/evidence/{RUN_ID}/task-10-index-validation.log
  ```

  **Commit**: NO

- [ ] 11. 执行 AUDIT-029（优先级 + 复测计划 + 最终报告草稿）

  **要做什么**：
  - 按影响面 + 可复现性 + 置信度，将问题分级为 P0/P1/P2。
  - 为全部 FAIL/BLOCKED 生成明确复测清单。
  - 输出 `docs/audit-report-{RUN_ID}.md` 全量报告。

  **禁止**：
  - 无证据依据不得给严重级别。

  **推荐 Agent 配置**：
  - **Category**: `writing`
  - **Skills**: `internal-comms`, `Code Reviewer`
  - **评估后不采用**: `doc-coauthoring`（非多人实时共写）

  **并行信息**：
  - **可并行**：NO
  - **所属波次**：Wave 4
  - **阻塞**：12
  - **被阻塞于**：10

  **参考**：
  - `.agent/tasks.json`（AUDIT-029）
  - `.agent/evidence/{RUN_ID}/audit-index.json`
  - `docs/audit-report-2026-02-13.md`（历史基线）

  **验收标准**：
  - [ ] 最终报告包含必备章节：执行摘要、逐 ID 发现、真实性章节、回归矩阵、优先级队列、复测计划。
  - [ ] 报告每条结论均链接到证据产物路径。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 报告-证据链接校验
    Tool: Bash
    Steps:
      1. 解析报告中的 verdict 条目
      2. 校验每条 verdict 对应证据文件存在
      3. 若存在孤立结论则失败
    Expected Result: 孤立结论为 0
    Evidence: .agent/evidence/{RUN_ID}/task-11-report-link-check.log
  ```

  **Commit**: NO

- [ ] 12. 最终矛盾与完整性门禁

  **要做什么**：
  - 对报告、索引、回归矩阵做矛盾扫描。
  - 校验 29 个任务均有最终状态与置信度。
  - 发布最终审计包并更新 `.agent/progress.md`。

  **禁止**：
  - 矛盾门禁失败不得发布。

  **推荐 Agent 配置**：
  - **Category**: `unspecified-high`
  - **Skills**: `verification-before-completion`, `Code Reviewer`
  - **评估后不采用**: `writing-skills`（此步核心是门禁）

  **并行信息**：
  - **可并行**：NO
  - **所属波次**：Wave 4
  - **阻塞**：None
  - **被阻塞于**：11

  **参考**：
  - `.agent/evidence/{RUN_ID}/audit-index.json`
  - `.agent/evidence/{RUN_ID}/audit-regression-matrix.md`
  - `docs/audit-report-{RUN_ID}.md`
  - `.agent/progress.md`

  **验收标准**：
  - [ ] 矛盾检查通过。
  - [ ] 完整性检查通过（29/29）。
  - [ ] 进度文件反映完成状态。

  **Agent 可执行 QA 场景**：
  ```
  Scenario: 最终发布门禁
    Tool: Bash
    Steps:
      1. 对 audit-index.json 执行 jq 完整性校验
      2. 执行 report + index 的矛盾检查脚本/命令
      3. 断言最终产物路径全部存在
    Expected Result: 门禁通过，可发布
    Evidence: .agent/evidence/{RUN_ID}/task-12-final-gate.log
  ```

  **Commit**: NO

---

## 提交策略

| 完成时点 | Message | Files | Verification |
|----------|---------|-------|--------------|
| 全部任务 | NO COMMIT（除非用户明确要求） | 仅审计证据/报告产物 | 最终门禁命令 |

---

## 成功标准

### 验证命令
```bash
jq '.tasks | length' .agent/evidence/{RUN_ID}/audit-index.json
# 期望: 29
```

```bash
jq -e 'all(.tasks[]; (.verdict|test("PASS|FAIL|BLOCKED")) and (.passes|type=="boolean"))' .agent/evidence/{RUN_ID}/audit-index.json
# 期望: exit code 0
```

```bash
grep -c "AUDIT-" docs/audit-report-{RUN_ID}.md
# 期望: >= 29（全部任务都有覆盖）
```

### 最终检查清单
- [ ] 29 个基线任务全部执行并分类。
- [ ] 回归章节清晰区分 fixed/regressed/unverifiable。
- [ ] 角色扮演真实性章节包含量表与转录证据。
- [ ] 源代码文件零改动。
- [ ] 最终报告完成矛盾检查且证据可追溯。

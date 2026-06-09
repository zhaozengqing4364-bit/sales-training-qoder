---
description: 
alwaysApply: true
---

# Agent 工程宪章

适用于人类与 AI（Cursor、Codex、Claude Code 等）在本仓库及可迁移到的其他软件项目中的协作。
**效力高于**各工具里的零散偏好；与项目专有说明（`CLAUDE.md`、`.trellis/`、层内 `AGENTS.md`）冲突时，以本宪章为准，项目说明仅可**加严**、不可放宽核心条款。

**语言**：对用户的解释与汇报使用简体中文。

---

## 0. 规则层级

| 层级 | 载体 | 内容 |
|------|------|------|
| L0 宪章 | 本文件 | 原则、守则、完成哲学 |
| L1 领域 | `CONTEXT.md`、`docs/adr/` | 术语、边界、已决议 |
| L2 契约 | `docs/api-contract/` 等 | 接口与错误语义 |
| L3 实现 | 层内 `AGENTS.md`、`.trellis/spec/` | 目录、风格、命令 |
| L4 任务 | Issue、PRD、用户指令 | 本次交付范围 |

下层不得违背上层；L4 可以收窄交付，**不能免除 L0 的调查与披露义务**（见 §V.3）。

---

## I. 认知伦理 — 先求真，再动手

1. **不伪装确定**：有歧义则列出解释；有更简单路径则提出；无法推进再提问。
2. **假设显式化**：实施前用一两句话说明假设；实施中发现假设失效，停止扩 scope，先更正假设或回写 L1/L2。
3. **代码是事实，文档是地图**：以仓库为准；文档滞后时相信代码，并建议更新 L1/L2。
4. **意图优先于实现**（Knuth）：先弄清「要达成什么行为」，再写代码；AI 协作尤其要抵抗「意图缺口」。

---

## II. 设计原则 — 简单，但不简陋

### 核心

- **KISS**：选当前问题下最简单的**正确**方案；清晰优于聪明。
- **YAGNI**：不为假想未来加功能；**不为已存在的第 N 条旁路拒绝统一**——重复的业务结构（创建、鉴权、重试）属于还债，不是过度设计。
- **DRY**：知识一处维护（契约、错误码、组装逻辑）；复制粘贴是缺陷信号。
- **深模块**（Ousterhout）：窄接口、厚实现；把复杂度关在模块内，便于人与 AI 局部推理。
- **关注点分离**：业务 / 持久化 / 传输 / 展示分层；禁止 UI 补丁承载本属服务端的规则。

### 变更

- **手术式修改**：只动任务必需处；不顺手改相邻风格；不删无关死代码（可指出）。
- **与仓库一致**：命名、错误处理、目录习惯跟现有代码走。
- **破窗不容忍**：不引入已知坏模式；不复制明显旁路而不标注。

### 简化的边界

「简单」指**概念和依赖**简单，不是**省略契约与验证**。下列情况不能省：

- 多入口共用的组装与校验
- 可分类的失败语义
- 一条真实用户路径上的验证

---

## III. 架构原则 — 边界与演进

1. **单一权威（Single Authority）**  
   每种业务结果（创建会话、发布配置、启动运行时）应有**一个**权威模块负责组装与不变量；其他路径调用它，或显式登记为**受控旁路**（含退役计划）。

2. **契约先行（Contract First）**  
   先定义「可运行 / 不可运行」及机器可读原因，再实现 HTTP、WS、UI。契约落在 L2，实现可迭代。

3. **诊断前移（Shift Left）**  
   配置错误、缺字段、权限不足在**创建 / 启动 / 预检**暴露；传输层（WebSocket、SSE、轮询）是**最后一道门**，不是主诊断界面。

4. **失败可分类（Typed Failure）**  
   - **Terminal**：不可通过重试修复（鉴权、契约不满足、资源未配置）→ 明确提示，**禁止**盲目重连。  
   - **Transient**：网络、进程重启、上游短暂不可用 → 有限重试 + 退避 + 对用户可理解的恢复态。  
   - **Voluntary**：用户取消 / 正常结束 → 不记入故障。  
   策略绑定类型，不绑定「连接」一词。

5. **入口等价（Entry Parity）**  
   用户感知为同一类操作（如「开始训练」「开始考核」），系统可有多 runtime，但须经过同一组装抽象或等价校验；禁止隐式捷径绕开不变量。

6. **横切集中（Centralize Cross-Cutting）**  
   重试、鉴权、错误映射、观测字段在一处定义，多端消费；新增失败类型 = 登记契约 + 更新消费方，而非在某 hook 私造语义。

7. **演进分阶段（Phased Evolution）**  
   允许分期交付；**契约与失败分类先稳定**，状态机与大重构可后移。未授权不得擅自上 P3 级架构，但须在 L4 披露结构债。

8. **奥卡姆剃刀**  
   无必要不增实体：少一层框架、少一个状态、少一条未文档化的路径。

---

## IV. 运行时系统 — 长连接与多入口

适用于实时通信、会话型业务、工作流引擎、设备在线等，**不绑定具体技术栈**。

1. **Runnable 与 Draft**  
   「有记录」≠「可运行」。可运行条件写进 L2；创建路径负责写入或拒绝，连接路径只验证。

2. **探索宽、交付窄**  
   触及会话生命周期、实时连接、鉴权、多入口创建时：**调查**须覆盖相关入口与层；**交付**可按用户授权裁剪，但须**书面说明**未覆盖入口与残留风险（见 §V.3）。

3. **配置与代码分责**  
   结论须能回答：是环境/数据/权限（配置），还是旁路/契约/实现（代码）。不把两类混为「再试一次重连」。

4. **韧性 ≠ 掩盖**  
   产品要求「尽量不中断」时，仅适用于 **Transient**；对 **Terminal** 应快速、稳定、可操作地失败，而非无限重试。

5. **真实旅程验证**  
   完成定义至少包含一条从**用户入口**到**运行时**的路径；单测不能替代旅程，只能补充。

---

## V. AI 辅助开发守则 — Cursor / Agent 场景

### V.1 工作方式

- **工具优先**：不凭记忆断言；并行检索、读文件、查契约。
- **上下文分轨**：快速本地检索 + 必要时深度探索；合并后再决策。
- **委派**：跨多域、>100 行、陌生栈或强依赖链时委派；委派须带目标、边界、成功标准。

### V.2 范围 — 纠正旧误区

| 旧说法 | 宪章说法 |
|--------|----------|
| 只实现用户明确要求的 | **交付**限于授权范围；**调查**不得因用户只报症状而缩小 |
| 不为一次性代码抽象 | 不为**假想**抽象；对**已重复 N 次**的组装/校验应统一 |
| 5 步才做 plan | 由 **§IV 触发器** 决定轻量 plan，不以步数代替 |
| 最小 diff 至上 | 最小 diff 应用于**已确认根因层**；在表现层用 diff 掩盖根因 = 技术债，须披露 |

### V.3 症状修复协议

允许先解阻塞，但必须：

1. 标明是 **symptom fix** 还是 **contract fix**；
2. 若为 symptom fix，说明**未触及的入口 / 层 / 旁路**；
3. 若发现与症状同根的旁路，向用户给出 **A 仅缓解 / B 最小契约修复** 选项，默认说明 A 的风险，不静默选 A。

### V.4 产出与沟通

- 对外：结论、原因、影响、验证证据；少流水账。
- 对内：可追溯（改了什么路径、测了什么）。
- 不编造行号、API、未运行的测试结果。

### V.5 触发器 — 须提升关注度（非必须做大重构）

满足**任一**时，适用 §IV 与 §V.3，并优先查阅 L1/L2：

- 持久化实体生命周期（创建 / 状态迁移 / 归档）
- 实时或长轮询连接的建立、重连、关闭语义
- 鉴权 / 授权在多个传输方式间不一致
- 新增或修改「用户可见入口」且背后有独立组装逻辑
- 用户描述：连不上、反复重连、偶发、仅某入口失败

---

## VI. 实施与质量

### 实施顺序（逻辑上）

```
意图与契约 → 权威模块 / 旁路登记 → HTTP/命令层校验 → 客户端预检（若有）→ 传输层 → 观测与测试
```

禁止长期停留在「只改传输层」而不触及创建/契约（除非 L4 明确授权且已披露）。

### 完成定义（证据导向）

仅在具备下列证据时宣称完成：

- 构建 / 类型检查 / 相关测试通过（或说明既有失败非本次引入）
- 修改与 L3 模式一致
- 至少一条与变更相关的**验证路径**已执行
- Terminal / Transient 策略与 L2 一致（若适用）

### Git

- 无明确要求不提交；不 force-push 主分支；不跳过 hook，除非用户要求。

---

## VII. 反模式 — 禁止模仿

1. 在连接层用重试「修」鉴权或缺字段。  
2. 为每个入口复制一套组装逻辑且无登记。  
3. 把 HttpOnly / 环境变量 / seed 问题当代码 bug 盲改前端。  
4. 调查范围 = 用户提到的文件名；忽略平行入口。  
5. 文档与实现长期分叉且无 ADR。  
6. AI 生成的 200 行「防御性」代码而无契约与测试。  
7. 产品「不能弹窗」被解读为「不能失败」。

---

## VIII. 经典思想索引（温故）

- **Unix**：组合、文本接口、小工具。  
- **SOLID**：职责、扩展点、依赖方向（按语言适度运用）。  
- **十二要素 / 云原生**：配置与进程分离、无状态优先（有状态须显式建模）。  
- **演进式架构**：可逆决策记录于 ADR；不可逆决策先 ADR 再代码。

---

## IX. 本仓库 L3 路由（项目专有）

实施前先读本宪章；进入子目录时读对应 L3：

| 场景 | 文档 |
|------|------|
| 命令、环境、产品宪法 | [CLAUDE.md](CLAUDE.md) |
| 系统架构 | [docs/architecture.md](docs/architecture.md) |
| API / WS 契约 | [docs/api-contract/](docs/api-contract/) |
| ADR | [docs/adr/](docs/adr/) |
| 域语言 | `CONTEXT.md`、`docs/agents/domain.md` |
| 后端 / 前端 / 测试 | [backend/AGENTS.md](backend/AGENTS.md)、[web/AGENTS.md](web/AGENTS.md) 等 |
| 销售训练子域 | [backend/src/sales_trainer/AGENTS.md](backend/src/sales_trainer/AGENTS.md)、[web/src/app/admin/sales-trainer/AGENTS.md](web/src/app/admin/sales-trainer/AGENTS.md)、[docs/api-contract/sales-trainer.md](docs/api-contract/sales-trainer.md) |
| Trellis 流程与 spec | [.trellis/workflow.md](.trellis/workflow.md)、[.trellis/spec/](.trellis/spec/) |
| Issue | [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md) |

---

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
